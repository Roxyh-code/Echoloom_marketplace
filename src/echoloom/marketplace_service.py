"""Marketplace listing business logic, independent of HTTP route registration.

Call write functions only with a server-authenticated account_id.  Wallet
verification and HTTP authorization are added in later integration steps.
This module never returns private character profiles or prompt data.
"""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import and_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .db import Character, Portrait, ProfileRevision, now
from .marketplace_models import CharacterListing, ListingRevision, MarketplaceCreator
from .marketplace_schemas import (
    ListingOwnerResponse,
    ListingPublicFields,
    ListingPublicResponse,
    ListingPublishRequest,
)


def _creator(db: Session, account_id: str | None, *, approved: bool = True):
    """Resolve an existing server-bound identity, never a submitted wallet."""
    if not account_id:
        raise HTTPException(status_code=401, detail="Authentication required.")
    creator = db.scalar(
        select(MarketplaceCreator).where(MarketplaceCreator.account_id == account_id)
    )
    if creator is None:
        raise HTTPException(status_code=403, detail="Creator account required.")
    if approved and not creator.is_approved:
        raise HTTPException(status_code=403, detail="Creator is not approved.")
    if not creator.wallet_address:
        raise HTTPException(status_code=409, detail="Verified payout wallet required.")
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
    # Validate the stored JSON against an explicit allowlist.  Never serialize
    # Character, ProfileRevision.profile_json, or the payout wallet.
    public = ListingPublicFields.model_validate(revision.public_data)
    return ListingPublicResponse(
        **public.model_dump(),
        listing_id=listing.id,
        revision=revision.revision,
        creator_display_name=creator.display_name,
        # Route to be added in Step 6. The future image endpoint must verify
        # the published listing and serve this revision's pinned portrait only.
        cover_image_url=(
            f"/api/marketplace/listings/{listing.id}/cover"
            if revision.portrait_id
            else None
        ),
    )


def _published_query():
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
        .where(
            CharacterListing.status == "published",
            MarketplaceCreator.is_approved.is_(True),
        )
    )


def list_public_listings(db: Session, *, limit: int = 50) -> list[ListingPublicResponse]:
    """Public browsing: only approved creators' currently published listings."""
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


def get_owner_listing(
    db: Session, listing_id: UUID, *, account_id: str | None
) -> ListingOwnerResponse:
    creator = _creator(db, account_id, approved=False)
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
    """Publish an owned Character, creating an immutable public revision.

    Requires a creator identity already linked to this local account after
    verified wallet sign-in. No endpoint may bind a wallet from body data.
    """
    creator = _creator(db, account_id)
    character = db.get(Character, str(body.character_id))
    if character is None or character.owner_id != account_id:
        raise HTTPException(status_code=404, detail="Character not found.")
    if character.archived:
        raise HTTPException(status_code=409, detail="Archived characters cannot be published.")

    profile = db.scalar(
        select(ProfileRevision).where(
            ProfileRevision.character_id == character.id,
            ProfileRevision.version == character.current_profile_version,
        )
    )
    if profile is None:
        raise HTTPException(status_code=409, detail="Character profile revision missing.")

    if character.current_image_id:
        portrait = db.get(Portrait, character.current_image_id)
        if portrait is None or portrait.character_id != character.id:
            raise HTTPException(status_code=409, detail="Character portrait is invalid.")
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
            and previous.payout_wallet_address == creator.wallet_address
            and previous.rights_basis == body.rights_basis
        ):
            # A duplicate identical publish request has no additional effect.
            return _owner_view(listing)

    try:
        if listing is None:
            listing = CharacterListing(
                character_id=character.id,
                creator_id=creator.id,
                status="published",
                latest_revision=1,
            )
            db.add(listing)
            db.flush()
            next_revision = 1
        else:
            # Optimistic compare-and-swap protects against concurrent publish
            # operations assigning the same revision number.
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
                payout_wallet_address=creator.wallet_address,
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
    """Disable new discovery/sales without removing old revision snapshots."""
    creator = _creator(db, account_id, approved=False)
    listing = db.scalar(
        select(CharacterListing).where(
            CharacterListing.id == str(listing_id),
            CharacterListing.creator_id == creator.id,
        )
    )
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found.")
    if listing.status != "unpublished":
        listing.status = "unpublished"
        listing.updated_at = now()
        db.commit()
        db.refresh(listing)
    return _owner_view(listing)
