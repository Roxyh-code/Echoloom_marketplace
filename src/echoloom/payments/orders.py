"""Read-only accounting helpers. Grant creation is reserved for verification."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Entitlement, PaymentOrder


def paid_sentence_allowance(db: Session, scene_id: str, account_id: str) -> int:
    """Sum durable grants for this exact scene and account, never pending quotes."""
    return int(db.scalar(
        select(func.coalesce(func.sum(Entitlement.extra_sentences), 0))
        .join(PaymentOrder, PaymentOrder.id == Entitlement.order_id)
        .where(
            PaymentOrder.scene_id == scene_id,
            PaymentOrder.account_id == account_id,
            PaymentOrder.status == "paid",
        )
    ) or 0)
