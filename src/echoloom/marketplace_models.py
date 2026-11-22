"""Marketplace creator identity and versioned public character listings.

Publishing requires an authenticated account with ownership of the Character,
not a verified Solana wallet. Monetization is a separate, opt-in capability
which requires verified payout credentials before any paid scene is quoted.
"""

from sqlalchemy import Boolean, ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base, now, uid


class MarketplaceCreator(Base):
    """Creator's local account identity; a payout wallet is optional.

    `account_id` bridges existing Character.owner_id. Publishing must check
    local account ownership. A payout wallet can be attached ONLY through a
    server-verified signature in a later monetization workflow; never accept
    a wallet address from a listing publication request.
    """

    __tablename__ = "marketplace_creators"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    account_id: Mapped[str | None] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="SET NULL"),
        unique=True,
        nullable=True,
    )
    wallet_address: Mapped[str | None] = mapped_column(
        String(64), unique=True, index=True, nullable=True, default=None
    )
    wallet_verified_at: Mapped[str | None] = mapped_column(
        String(40), nullable=True, default=None
    )
    display_name: Mapped[str] = mapped_column(String(80))
    # Approval may be used by the hackathon's later monetization allowlist.
    # It must NOT gate ordinary publishing or public discovery.
    is_approved: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0"
    )
    created_at: Mapped[str] = mapped_column(String(40), default=now)
    updated_at: Mapped[str] = mapped_column(String(40), default=now)


class CharacterListing(Base):
    """Public listing status is independent of paid-scene eligibility."""

    __tablename__ = "character_listings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    character_id: Mapped[str] = mapped_column(
        ForeignKey("characters.id", ondelete="RESTRICT"), unique=True
    )
    creator_id: Mapped[str] = mapped_column(
        ForeignKey("marketplace_creators.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), default="unpublished", server_default="unpublished"
    )
    # Server-controlled only. Initially False for all new/existing listings.
    # Can become True only after payout-wallet verification and monetization checks.
    monetization_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0"
    )
    latest_revision: Mapped[int] = mapped_column(default=0, server_default="0")
    created_at: Mapped[str] = mapped_column(String(40), default=now)
    updated_at: Mapped[str] = mapped_column(String(40), default=now)


class ListingRevision(Base):
    """Immutable public data and optional payout snapshot for one revision.

    A listing can be published without a wallet (snapshot = None). A later
    monetization action must create a NEW revision containing the verified
    payout wallet; existing historical revisions are never changed.
    A service must construct public_data from an explicit allowlist.
    """

    __tablename__ = "character_listing_revisions"
    __table_args__ = (UniqueConstraint("listing_id", "revision"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    listing_id: Mapped[str] = mapped_column(
        ForeignKey("character_listings.id", ondelete="RESTRICT"), index=True
    )
    revision: Mapped[int]
    profile_revision_id: Mapped[str] = mapped_column(
        ForeignKey("character_profiles.id", ondelete="RESTRICT")
    )
    character_version: Mapped[int]
    portrait_id: Mapped[str | None] = mapped_column(
        ForeignKey("character_images.id", ondelete="RESTRICT"), nullable=True
    )
    public_data: Mapped[dict] = mapped_column(JSON)
    payout_wallet_address: Mapped[str | None] = mapped_column(
        String(64), nullable=True, default=None
    )
    rights_basis: Mapped[str] = mapped_column(String(20))  # original | licensed
    rights_confirmed_at: Mapped[str] = mapped_column(String(40), default=now)
    created_at: Mapped[str] = mapped_column(String(40), default=now)
