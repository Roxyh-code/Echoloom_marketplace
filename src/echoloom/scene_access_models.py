"""Server-owned Marketplace Scene quotas. No browser-generated credit or payment flags."""
from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base, now


class SceneAccess(Base):
    __tablename__ = "marketplace_scene_access"

    scene_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("rehearsal_scenes.id", ondelete="CASCADE"), primary_key=True
    )
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("user_accounts.id", ondelete="CASCADE"), index=True
    )
    opening_available: Mapped[int] = mapped_column(default=0, server_default="0")
    directions_available: Mapped[int] = mapped_column(default=0, server_default="0")
    opening_consumed: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0"
    )
    trial_granted: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0"
    )
    created_at: Mapped[str] = mapped_column(String(40), default=now)


class SceneTrialClaim(Base):
    """Never grant a second account trial, even after its first Scene is deleted."""

    __tablename__ = "marketplace_trial_claims"
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("user_accounts.id", ondelete="CASCADE"), primary_key=True
    )
    # Deliberately not a foreign key: deleting a completed Scene does not reset a trial.
    scene_id: Mapped[str] = mapped_column(String(36))
    created_at: Mapped[str] = mapped_column(String(40), default=now)


class SceneUsage(Base):
    """One logical generation, possibly spanning failed/retried worker attempts."""

    __tablename__ = "marketplace_scene_usage"
    operation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    scene_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("rehearsal_scenes.id", ondelete="CASCADE"), index=True
    )
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("user_accounts.id", ondelete="CASCADE")
    )
    category: Mapped[str] = mapped_column(String(16))  # opening | direction
    status: Mapped[str] = mapped_column(String(16))  # reserved | charged | refunded
    created_at: Mapped[str] = mapped_column(String(40), default=now)
