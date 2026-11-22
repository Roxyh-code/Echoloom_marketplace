"""Marketplace ownership and published-character snapshots.

This module defines tables only. Wallet verification, publication permissions,
public-field filtering, and revision immutability are enforced in the service
layer added in later steps.
"""

from sqlalchemy import Boolean, ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base, now, uid


class MarketplaceCreator(Base):
    """Creator identity linked to a verified Solana wallet.

    `account_id` bridges the existing local Character.owner_id model. The
    wallet must be bound only after server-side wallet-signature verification;
    never create an identity solely from a browser-supplied address.
    """

    __tablename__ = "marketplace_creators"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    account_id: Mapped[str | None] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="SET NULL"),
        unique=True,
        nullable=True,
    )
    wallet_address: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(80))
    is_approved: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0"
    )
    created_at: Mapped[str] = mapped_column(String(40), default=now)
    updated_at: Mapped[str] = mapped_column(String(40), default=now)


class CharacterListing(Base):
    """One public-listing lifecycle per existing private Character."""

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
    latest_revision: Mapped[int] = mapped_column(default=0, server_default="0")
    created_at: Mapped[str] = mapped_column(String(40), default=now)
    updated_at: Mapped[str] = mapped_column(String(40), default=now)


class ListingRevision(Base):
    """Frozen public data and payout wallet for one published revision.

    A service must construct `public_data` from an explicit allowlist, check
    ownership and licensing, and never mutate a saved ListingRevision.
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
    payout_wallet_address: Mapped[str] = mapped_column(String(64))
    rights_basis: Mapped[str] = mapped_column(String(20))  # original | licensed
    rights_confirmed_at: Mapped[str] = mapped_column(String(40), default=now)
    created_at: Mapped[str] = mapped_column(String(40), default=now)
