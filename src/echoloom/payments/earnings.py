"""Owner-scoped reporting from verified payments and immutable attribution."""
from sqlalchemy import select, and_
from ..marketplace_models import CharacterListing, ListingRevision, MarketplaceCreator

from .models import CreatorEarningSnapshot, Payment, PaymentOrder


def creator_earnings(db, owner):
    rows = db.execute(select(CreatorEarningSnapshot, Payment, PaymentOrder.mint)
        .join(Payment, Payment.order_id == CreatorEarningSnapshot.order_id)
        .join(PaymentOrder, PaymentOrder.id == Payment.order_id)
        .where(CreatorEarningSnapshot.creator_account_id == owner,
               PaymentOrder.status == "paid")
        .order_by(Payment.verified_at.desc(), Payment.order_id, CreatorEarningSnapshot.cast_slot)).all()
    totals, characters, transactions = {}, {}, {}
    for line, payment, mint in rows:
        totals[mint] = totals.get(mint, 0) + line.amount_minor_units
        key = (mint, line.character_id)
        entry = characters.setdefault(key, dict(mint=mint, character_id=line.character_id,
            name=line.character_name, amount_minor_units=0))
        entry["amount_minor_units"] += line.amount_minor_units
        tx = transactions.setdefault(payment.order_id, dict(signature=payment.tx_signature,
            verified_at=payment.verified_at, mint=mint, amount_minor_units=0, characters=[]))
        tx["amount_minor_units"] += line.amount_minor_units
        tx["characters"].append(dict(name=line.character_name, amount_minor_units=line.amount_minor_units))
    creator = db.scalar(select(MarketplaceCreator).where(MarketplaceCreator.account_id == owner))
    listings = []
    if creator:
        for listing, revision in db.execute(select(CharacterListing, ListingRevision)
            .join(ListingRevision, and_(ListingRevision.listing_id == CharacterListing.id,
                ListingRevision.revision == CharacterListing.latest_revision))
            .where(CharacterListing.creator_id == creator.id)
            .order_by(CharacterListing.updated_at.desc())).all():
            enabled = bool(listing.status == "published" and listing.monetization_enabled
                and creator.is_approved and creator.wallet_verified_at and creator.wallet_address
                and revision.payout_wallet_address == creator.wallet_address)
            listings.append(dict(character_id=listing.character_id, listing_id=listing.id,
                name=revision.public_data.get("name", "Character"),
                status="unpublished" if listing.status != "published" else
                    ("enabled" if enabled else "setup_required")))
    return dict(listings=listings,
        payout_wallet=creator.wallet_address if creator and creator.wallet_verified_at else None,
        totals=[dict(mint=mint, amount_minor_units=amount) for mint, amount in totals.items()],
        paid_unlocks=len(transactions), characters=list(characters.values()),
        recent_transactions=list(transactions.values())[:50])
