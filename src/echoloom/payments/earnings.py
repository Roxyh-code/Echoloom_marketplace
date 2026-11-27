"""Owner-scoped reporting from verified payments and immutable attribution."""
from sqlalchemy import select

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
    return dict(totals=[dict(mint=mint, amount_minor_units=amount) for mint, amount in totals.items()],
        paid_unlocks=len(transactions), characters=list(characters.values()),
        recent_transactions=list(transactions.values())[:50])
