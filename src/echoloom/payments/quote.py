"""Server-authoritative pricing and immutable signed quote creation."""
import base64
import secrets
import time
from datetime import UTC, datetime
from uuid import uuid4

import httpx
from fastapi import HTTPException
from sqlalchemy import select

from ..db import Character, RehearsalScene
from ..marketplace_models import CharacterListing, ListingRevision, MarketplaceCreator
from .authorization import (
    Authorization, Payout, decode_pubkey, order_reference_hash, serialize_authorization,
)
from .models import PaymentOrder, CreatorEarningSnapshot
from .schemas import QuoteResponse
from .signer import AuthorizationSigner
from .solana_rpc import load_config, pda

PRICE = 1_000_000


def split_payouts(wallet_a, wallet_b, platform, buyer):
    amounts = {}
    for wallet, amount in ((wallet_a, 450_000), (wallet_b, 450_000), (platform, 100_000)):
        try:
            raw = decode_pubkey(wallet)
        except ValueError:
            raise HTTPException(409, "Invalid recipient wallet") from None
        if not any(raw) or wallet == buyer:
            raise HTTPException(409, "Buyer cannot receive a payout")
        amounts[wallet] = amounts.get(wallet, 0) + amount
    return tuple(Payout(w, amounts[w]) for w in sorted(amounts, key=decode_pubkey))


def creator_details(db, actor, owner):
    if actor.get("source_listing_id"):
        listing = db.get(CharacterListing, actor["source_listing_id"])
        if not listing or not listing.monetization_enabled:
            raise HTTPException(409, "Character is not eligible for paid scenes")
        revision = db.scalar(select(ListingRevision).where(
            ListingRevision.listing_id == listing.id,
            ListingRevision.revision == actor.get("source_listing_revision"),
        ))
        creator = db.get(MarketplaceCreator, listing.creator_id)
        if (
            revision and creator and creator.account_id and creator.is_approved and creator.wallet_verified_at
            and revision.payout_wallet_address
            and revision.payout_wallet_address == creator.wallet_address
        ):
            return dict(wallet=revision.payout_wallet_address, creator_account_id=creator.account_id,
                            character_id=listing.character_id, listing_id=listing.id,
                            listing_revision=revision.revision,
                            character_name=str(revision.public_data.get("name") or "Character")[:80])
    else:
        character = db.get(Character, actor.get("source_character_id") or actor.get("id"))
        if character and character.owner_id == owner:
            creator = db.scalar(select(MarketplaceCreator).where(
                MarketplaceCreator.account_id == owner,
            ))
            if creator and creator.is_approved and creator.wallet_verified_at and creator.wallet_address:
                return dict(wallet=creator.wallet_address, creator_account_id=owner,
                            character_id=character.id, listing_id=None, listing_revision=None,
                            character_name=str(actor.get("name") or "Character")[:80])
    raise HTTPException(409, "A creator payout wallet is not verified")


def creator_wallet(db, actor, owner):
    return creator_details(db, actor, owner)["wallet"]


def create_quote(db, settings, owner, request, verified_wallet):
    if not owner:
        raise HTTPException(401, "Sign in before purchasing")
    if not settings.solana_payments_enabled:
        raise HTTPException(503, "Wallet checkout is not enabled")
    if verified_wallet != request.buyer_wallet:
        raise HTTPException(403, "Verify the buyer wallet before purchasing")
    scene = db.get(RehearsalScene, str(request.scene_id))
    if not scene or scene.owner_id != owner:
        raise HTTPException(404, "Scene not found")
    cast = scene.document.get("cast", [])
    if scene.document.get("demo") or len(cast) != 2:
        raise HTTPException(409, "Scene is not eligible for purchase")
    attribution = [creator_details(db, actor, owner) for actor in cast]
    wallets = [line['wallet'] for line in attribution]
    payouts = split_payouts(*wallets, settings.solana_platform_wallet, request.buyer_wallet)
    try:
        signer = AuthorizationSigner.from_keypair_file(settings.solana_backend_signer_path)
        config, domain, version = load_config(settings, signer)
        order_id = uuid4()
        expiry = int(time.time()) + 900
        product = f"scene-unlock-40:{scene.id}"
        receipt = pda(settings.solana_program_id, b"purchase_receipt", order_reference_hash(order_id))
        message = serialize_authorization(Authorization(
            domain, settings.solana_program_id, config, order_id,
            request.buyer_wallet, product, settings.solana_mint, PRICE,
            payouts, version, expiry, secrets.token_bytes(32),
        ))
        signature = signer.sign(message)
    except (ValueError, TypeError, OSError, KeyError, IndexError, httpx.HTTPError):
        raise HTTPException(503, "Payment deployment is not ready") from None
    row = PaymentOrder(
        id=str(order_id), scene_id=scene.id, account_id=owner,
        buyer_wallet=request.buyer_wallet, product_id=product,
        program_id=settings.solana_program_id, mint=settings.solana_mint,
        config_pda=config, receipt_pda=receipt, amount_minor_units=PRICE,
        payout_lines=[{"wallet": p.wallet, "amount_minor_units": p.amount} for p in payouts],
        config_version=version, expires_at_unix=expiry, signer_pubkey=signer.public_key,
        authorization_message_b64=base64.b64encode(message).decode("ascii"),
        authorization_signature_b64=base64.b64encode(signature).decode("ascii"),
    )
    db.add(row)
    db.flush()
    for slot, line in enumerate(attribution):
        db.add(CreatorEarningSnapshot(order_id=row.id, cast_slot=slot,
                                      amount_minor_units=450_000, **line))
    db.commit()
    return QuoteResponse(
        order_id=order_id, expires_at=datetime.fromtimestamp(expiry, UTC).isoformat(),
        program_id=row.program_id, mint=row.mint, amount_minor_units=PRICE,
        payout_lines=row.payout_lines, config_pda=config, receipt_pda=receipt,
        signer_pubkey=row.signer_pubkey, authorization_message_b64=row.authorization_message_b64,
        authorization_signature_b64=row.authorization_signature_b64,
    )
