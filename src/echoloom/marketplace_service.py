"""Marketplace listing logic: publishing and monetization are separate.

Publishing requires a server-authenticated local account owning the Character.
It does NOT require a payout wallet or creator monetization approval. A future
paid-scene service must check monetization eligibility independently.
"""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import and_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .companion_models import Account
from .db import Character, Portrait, ProfileRevision, now, uid
from .marketplace_models import CharacterListing, ListingRevision, MarketplaceCreator
from .marketplace_schemas import (
    ListingOwnerDetailResponse,
    ListingOwnerResponse,
    ListingPublicFields,
    ListingPublicResponse,
    ListingPublishRequest,
)


def _creator(
    db: Session, account_id: str | None, *, create: bool = False
) -> MarketplaceCreator:
    """Resolve creator by trusted local account ID; never accept a wallet here."""
    if not account_id:
        raise HTTPException(status_code=401, detail="Authentication required.")
    creator = db.scalar(
        select(MarketplaceCreator).where(MarketplaceCreator.account_id == account_id)
    )
    if creator is not None:
        return creator
    if not create:
        # Do not reveal whether another user's listing exists.
        raise HTTPException(status_code=404, detail="Listing not found.")

    # Login middleware normally guarantees this, but check again at the DB
    # boundary before granting a marketplace creator identity.
    if db.get(Account, account_id) is None:
        raise HTTPException(status_code=401, detail="Authentication required.")

    # Deliberately do not reveal the local login username in public discovery.
    # A custom public creator display name can be added in a later profile UI.
    creator = MarketplaceCreator(
        account_id=account_id,
        display_name=f"Creator {uid()[:8]}",
        wallet_address=None,
        wallet_verified_at=None,
        is_approved=False,
    )
    db.add(creator)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        # Two simultaneous first publications can race on unique(account_id).
        raise HTTPException(
            status_code=409, detail="Creator setup changed; please retry."
        ) from exc
    return creator


def _owner_view(listing: CharacterListing) -> ListingOwnerResponse:
    return ListingOwnerResponse(
        listing_id=listing.id,
        character_id=listing.character_id,
        status=listing.status,
        latest_revision=listing.latest_revision,
    )


def _public_view(
    listing: CharacterListing,
    revision: ListingRevision,
    creator: MarketplaceCreator,
) -> ListingPublicResponse:
    # Only publish explicit allowlisted fields. Never return profile_json,
    # the creator's local username, or a payout wallet.
    public = ListingPublicFields.model_validate(revision.public_data)
    return ListingPublicResponse(
        **public.model_dump(),
        listing_id=listing.id,
        revision=revision.revision,
        creator_display_name=creator.display_name,
        cover_image_url=(
            f"/api/marketplace/listings/{listing.id}/cover"
            if revision.portrait_id
            else None
        ),
    )


def _published_query():
    """Public discovery does not require payout-wallet verification."""
    return (
        select(CharacterListing, ListingRevision, MarketplaceCreator)
        .join(
            ListingRevision,
            and_(
                ListingRevision.listing_id == CharacterListing.id,
                ListingRevision.revision == CharacterListing.latest_revision,
            ),
        )
        .join(MarketplaceCreator, MarketplaceCreator.id == CharacterListing.creator_id)
        .where(CharacterListing.status == "published")
    )


def list_public_listings(db: Session, *, limit: int = 50) -> list[ListingPublicResponse]:
    if not 1 <= limit <= 100:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 100.")
    rows = db.execute(
        _published_query().order_by(CharacterListing.updated_at.desc()).limit(limit)
    ).all()
    return [_public_view(listing, rev, creator) for listing, rev, creator in rows]


def get_public_listing(db: Session, listing_id: UUID) -> ListingPublicResponse:
    row = db.execute(
        _published_query().where(CharacterListing.id == str(listing_id))
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Listing not found.")
    return _public_view(*row)


def list_owner_listings(
    db: Session, *, account_id: str | None
) -> list[ListingOwnerDetailResponse]:
    """Return only this account's current listing snapshots for management.

    Unlike public discovery, this includes unpublished listings. Each result
    contains only previously approved public fields and the owner's rights
    selection; private Character/profile fields are never serialized.
    """
    if not account_id:
        raise HTTPException(status_code=401, detail="Authentication required.")
    creator = db.scalar(
        select(MarketplaceCreator).where(MarketplaceCreator.account_id == account_id)
    )
    if creator is None:
        return []
    rows = db.execute(
        select(CharacterListing, ListingRevision)
        .join(
            ListingRevision,
            and_(
                ListingRevision.listing_id == CharacterListing.id,
                ListingRevision.revision == CharacterListing.latest_revision,
            ),
        )
        .where(CharacterListing.creator_id == creator.id)
        .order_by(CharacterListing.updated_at.desc())
    ).all()
    return [
        ListingOwnerDetailResponse(
            **_owner_view(listing).model_dump(),
            **ListingPublicFields.model_validate(revision.public_data).model_dump(),
            rights_basis=revision.rights_basis,
        )
        for listing, revision in rows
    ]


def get_owner_listing(
    db: Session, listing_id: UUID, *, account_id: str | None
) -> ListingOwnerResponse:
    creator = _creator(db, account_id)
    listing = db.scalar(
        select(CharacterListing).where(
            CharacterListing.id == str(listing_id),
            CharacterListing.creator_id == creator.id,
        )
    )
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found.")
    return _owner_view(listing)


def publish_listing(
    db: Session, body: ListingPublishRequest, *, account_id: str | None
) -> ListingOwnerResponse:
    """Publish an owned character, independent of Solana monetization.

    Every public edit creates a new immutable revision. New/edited revisions
    are NOT automatically eligible for payment, even if a creator record has
    a legacy wallet string. Payouts require a separate verified workflow.
    """
    if not account_id:
        raise HTTPException(status_code=401, detail="Authentication required.")

    # Check actual character ownership BEFORE auto-creating creator identity.
    character = db.get(Character, str(body.character_id))
    if character is None or character.owner_id != account_id:
        raise HTTPException(status_code=404, detail="Character not found.")
    if character.archived:
        raise HTTPException(
            status_code=409, detail="Archived characters cannot be published."
        )

    profile = db.scalar(
        select(ProfileRevision).where(
            ProfileRevision.character_id == character.id,
            ProfileRevision.version == character.current_profile_version,
        )
    )
    if profile is None:
        raise HTTPException(
            status_code=409, detail="Character profile revision missing."
        )

    if character.current_image_id:
        portrait = db.get(Portrait, character.current_image_id)
        if portrait is None or portrait.character_id != character.id:
            raise HTTPException(status_code=409, detail="Character portrait is invalid.")

    creator = _creator(db, account_id, create=True)
    public_data = body.public_payload()
    listing = db.scalar(
        select(CharacterListing).where(CharacterListing.character_id == character.id)
    )
    if listing is not None and listing.creator_id != creator.id:
        raise HTTPException(status_code=403, detail="Listing belongs to another creator.")

    if listing is not None and listing.status == "published":
        previous = db.scalar(
            select(ListingRevision).where(
                ListingRevision.listing_id == listing.id,
                ListingRevision.revision == listing.latest_revision,
            )
        )
        if (
            previous is not None
            and previous.profile_revision_id == profile.id
            and previous.portrait_id == character.current_image_id
            and previous.public_data == public_data
            and previous.payout_wallet_address is None
            and previous.rights_basis == body.rights_basis
        ):
            # Identical retries do not create extra revisions.
            return _owner_view(listing)

    try:
        if listing is None:
            listing = CharacterListing(
                character_id=character.id,
                creator_id=creator.id,
                status="published",
                monetization_enabled=False,
                latest_revision=1,
            )
            db.add(listing)
            db.flush()
            next_revision = 1
        else:
            # Compare-and-swap avoids two writers assigning one revision ID.
            previous_revision = listing.latest_revision
            next_revision = previous_revision + 1
            updated = db.execute(
                update(CharacterListing)
                .where(
                    CharacterListing.id == listing.id,
                    CharacterListing.latest_revision == previous_revision,
                )
                .values(
                    latest_revision=next_revision,
                    status="published",
                    monetization_enabled=False,
                    updated_at=now(),
                )
            )
            if updated.rowcount != 1:
                db.rollback()
                raise HTTPException(status_code=409, detail="Listing changed; retry.")

        db.add(
            ListingRevision(
                listing_id=listing.id,
                revision=next_revision,
                profile_revision_id=profile.id,
                character_version=profile.version,
                portrait_id=character.current_image_id,
                public_data=public_data,
                # Wallet activation is a separate explicit, signed operation.
                payout_wallet_address=None,
                rights_basis=body.rights_basis,
            )
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Conflicting listing update.") from exc

    db.refresh(listing)
    return _owner_view(listing)


def unpublish_listing(
    db: Session, listing_id: UUID, *, account_id: str | None
) -> ListingOwnerResponse:
    """Hide a listing, revoke its sale eligibility, retain its history."""
    creator = _creator(db, account_id)
    listing = db.scalar(
        select(CharacterListing).where(
            CharacterListing.id == str(listing_id),
            CharacterListing.creator_id == creator.id,
        )
    )
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found.")
    if listing.status != "unpublished" or listing.monetization_enabled:
        listing.status = "unpublished"
        listing.monetization_enabled = False
        listing.updated_at = now()
        db.commit()
        db.refresh(listing)
    return _owner_view(listing)
