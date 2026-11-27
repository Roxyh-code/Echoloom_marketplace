"""Durable payment records. Only a future trusted verifier may grant access."""
from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base, now, uid


class PaymentOrder(Base):
    __tablename__ = "payment_orders"
    __table_args__ = (
        CheckConstraint("amount_minor_units > 0", name="ck_order_amount"),
        CheckConstraint("config_version >= 0", name="ck_order_config_version"),
        CheckConstraint("status IN ('pending', 'paid', 'rejected', 'expired')", name="ck_order_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    # Historical IDs deliberately survive deletion of a scene or local account.
    scene_id: Mapped[str] = mapped_column(String(36), index=True)
    account_id: Mapped[str] = mapped_column(String(36), index=True)
    buyer_wallet: Mapped[str] = mapped_column(String(44))
    product_id: Mapped[str] = mapped_column(String(128))
    program_id: Mapped[str] = mapped_column(String(44))
    mint: Mapped[str] = mapped_column(String(44))
    config_pda: Mapped[str] = mapped_column(String(44))
    receipt_pda: Mapped[str] = mapped_column(String(44), unique=True)
    amount_minor_units: Mapped[int] = mapped_column(BigInteger)
    payout_lines: Mapped[list] = mapped_column(JSON)
    config_version: Mapped[int] = mapped_column(BigInteger)
    expires_at_unix: Mapped[int] = mapped_column(BigInteger)
    signer_pubkey: Mapped[str] = mapped_column(String(44))
    authorization_message_b64: Mapped[str] = mapped_column(Text)
    authorization_signature_b64: Mapped[str] = mapped_column(String(88))
    status: Mapped[str] = mapped_column(String(16), default="pending", server_default="pending")
    created_at: Mapped[str] = mapped_column(String(40), default=now)


class Payment(Base):
    """One independently verified transaction per order (not a client claim)."""

    __tablename__ = "payments"
    order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("payment_orders.id"), primary_key=True
    )
    tx_signature: Mapped[str] = mapped_column(String(88), unique=True)
    verified_slot: Mapped[int] = mapped_column(BigInteger)
    verified_at: Mapped[str] = mapped_column(String(40), default=now)


class Entitlement(Base):
    """Append-only grant ledger: at most one grant per verified payment."""

    __tablename__ = "payment_entitlements"
    __table_args__ = (
        CheckConstraint("extra_sentences = 40", name="ck_entitlement_sentences"),
    )
    order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("payments.order_id"), primary_key=True
    )
    extra_sentences: Mapped[int] = mapped_column(default=40, server_default="40")
    created_at: Mapped[str] = mapped_column(String(40), default=now)


class BuyerWallet(Base):
    """Verified checkout identity, independent of creator payout credentials."""
    __tablename__ = "payment_buyer_wallets"
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("user_accounts.id", ondelete="CASCADE"), primary_key=True
    )
    wallet: Mapped[str] = mapped_column(String(44), unique=True)
    verified_at: Mapped[str] = mapped_column(String(40), default=now)


class WalletChallenge(Base):
    __tablename__ = "payment_wallet_challenges"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("user_accounts.id", ondelete="CASCADE"), index=True
    )
    wallet: Mapped[str] = mapped_column(String(44))
    message: Mapped[str] = mapped_column(Text)
    expires_at_unix: Mapped[int] = mapped_column(BigInteger)
    consumed_at: Mapped[str | None] = mapped_column(String(40), default=None)
