"""Operator-only Devnet demo monetization; no public approval endpoint."""
from copy import deepcopy

from sqlalchemy import select, update
from solders.pubkey import Pubkey

from ..db import Character, now
from ..marketplace_models import CharacterListing, ListingRevision, MarketplaceCreator
from .authorization import decode_pubkey
from .models import BuyerWallet


def activate_demo_pair(db, listing_ids):
    """Activate two existing published listings in one transaction.

    Operator must obtain explicit creator consent to use the already verified
    wallet for demo payouts. Never accept a caller-supplied payout address.
    Caller commits only after this function succeeds.
    """
    if len(listing_ids) != 2 or len(set(listing_ids)) != 2:
        raise ValueError("Choose two distinct published listings")
    prepared = []
    for listing_id in listing_ids:
        listing = db.get(CharacterListing, listing_id)
        if not listing or listing.status != "published":
            raise ValueError("Listing must exist and be published")
        creator = db.get(MarketplaceCreator, listing.creator_id)
        character = db.get(Character, listing.character_id)
        if not creator or not creator.account_id or not character or character.archived or character.owner_id != creator.account_id:
            raise ValueError("Listing owner is not eligible")
        binding = db.get(BuyerWallet, creator.account_id)
        if not binding or not binding.verified_at:
            raise ValueError("Creator must first verify a wallet in their own account")
        raw = decode_pubkey(binding.wallet)
        if not any(raw) or not Pubkey.from_bytes(raw).is_on_curve():
            raise ValueError("Invalid creator wallet")
        if creator.wallet_address and creator.wallet_address != binding.wallet:
            raise ValueError("Existing payout wallet differs; rotation is not supported")
        other = db.scalar(select(MarketplaceCreator).where(
            MarketplaceCreator.wallet_address == binding.wallet,
            MarketplaceCreator.id != creator.id,
        ))
        if other:
            raise ValueError("Wallet already belongs to another creator")
        previous = db.scalar(select(ListingRevision).where(
            ListingRevision.listing_id == listing.id,
            ListingRevision.revision == listing.latest_revision,
        ))
        if previous is None:
            raise ValueError("Missing published revision")
        prepared.append((listing, creator, binding, previous))
    if len({x[1].id for x in prepared}) != 2 or len({x[2].wallet for x in prepared}) != 2:
        raise ValueError("Demo requires two distinct creators and wallets")
    result = []
    for listing, creator, binding, previous in prepared:
        creator.wallet_address = binding.wallet
        creator.wallet_verified_at = binding.verified_at
        creator.is_approved = True
        creator.updated_at = now()
        if not (listing.monetization_enabled and previous.payout_wallet_address == binding.wallet):
            revision = listing.latest_revision + 1
            changed = db.execute(update(CharacterListing).where(
                CharacterListing.id == listing.id,
                CharacterListing.status == "published",
                CharacterListing.latest_revision == previous.revision,
            ).values(latest_revision=revision, monetization_enabled=True, updated_at=now()))
            if changed.rowcount != 1:
                raise ValueError("Listing changed; retry after review")
            db.add(ListingRevision(
                listing_id=listing.id, revision=revision,
                profile_revision_id=previous.profile_revision_id,
                character_version=previous.character_version,
                portrait_id=previous.portrait_id,
                public_data=deepcopy(previous.public_data),
                voice_identity=deepcopy(previous.voice_identity),
                payout_wallet_address=binding.wallet,
                rights_basis=previous.rights_basis,
                rights_confirmed_at=previous.rights_confirmed_at,
            ))
        else:
            revision = previous.revision
        result.append({"listing_id": listing.id, "revision": revision, "wallet": binding.wallet})
    db.flush()
    return result
