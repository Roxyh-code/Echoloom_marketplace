"""Separate signed payout onboarding. No chain transaction or buyer-wallet rebinding."""
from sqlalchemy import select, update, or_
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException

from ..db import now
from ..marketplace_models import MarketplaceCreator
from ..marketplace_service import _creator
from .wallet import require_owner, create_challenge, consume_challenge, PAYOUT_PURPOSE
from .authorization import decode_pubkey


def status(db, settings, owner):
    require_owner(owner)
    creator = db.scalar(select(MarketplaceCreator).where(MarketplaceCreator.account_id == owner))
    approved = bool(creator and creator.is_approved)
    wallet = creator.wallet_address if creator and creator.wallet_verified_at else None
    return dict(wallet=wallet, approved=approved, ready=bool(wallet and approved),
                setup_allowed=bool(approved or settings.solana_creator_self_service_enabled))


def payout_challenge(db, settings, owner, wallet):
    current = status(db, settings, owner)
    if not current["setup_allowed"]:
        raise HTTPException(403, "Creator approval required; contact the demo operator")
    if current["wallet"] and current["wallet"] != wallet:
        raise HTTPException(409, "Payout wallet rotation is not supported")
    if wallet == settings.solana_platform_wallet:
        raise HTTPException(409, "Platform wallet cannot be a creator payout wallet")
    return create_challenge(db, settings, owner, wallet, purpose=PAYOUT_PURPOSE)


def verify_payout(db, settings, owner, body):
    if not status(db, settings, owner)["setup_allowed"]:
        raise HTTPException(403, "Creator approval required; contact the demo operator")
    wallet = consume_challenge(db, settings, owner, body, purpose=PAYOUT_PURPOSE)
    creator = _creator(db, owner, create=True)
    if creator.wallet_address and creator.wallet_address != wallet:
        db.rollback()
        raise HTTPException(409, "Payout wallet rotation is not supported")
    if wallet == settings.solana_platform_wallet or not any(decode_pubkey(wallet)):
        db.rollback()
        raise HTTPException(409, "Invalid creator payout wallet")
    # Compare-and-set prevents two different payout proofs from racing into
    # an implicit wallet rotation, including on non-SQLite databases.
    try:
        values = dict(wallet_address=wallet, wallet_verified_at=now(), updated_at=now())
        if settings.solana_creator_self_service_enabled:
            values["is_approved"] = True
        criteria = [MarketplaceCreator.id == creator.id,
                    or_(MarketplaceCreator.wallet_address.is_(None),
                        MarketplaceCreator.wallet_address == wallet)]
        if not settings.solana_creator_self_service_enabled:
            criteria.append(MarketplaceCreator.is_approved.is_(True))
        changed = db.execute(update(MarketplaceCreator).where(*criteria).values(**values))
        if changed.rowcount != 1:
            db.rollback()
            raise HTTPException(409, "Creator setup changed; refresh and retry")
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Wallet is already assigned to a creator") from None
    return status(db, settings, owner)
