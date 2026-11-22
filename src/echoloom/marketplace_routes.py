"""Marketplace listing HTTP routes.

Public discovery and public listing covers require publication, not a verified
payout wallet or creator monetization approval. Writes and owner data remain
authenticated and ownership-checked in marketplace_service.py.
"""

from pathlib import Path
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy import and_, select

from .db import Portrait
from .marketplace_models import CharacterListing, ListingRevision
from .marketplace_schemas import (
    ListingOwnerResponse,
    ListingPublicResponse,
    ListingPublishRequest,
)
from .marketplace_service import (
    get_owner_listing,
    get_public_listing,
    list_public_listings,
    publish_listing,
    unpublish_listing,
)


def register_marketplace(app: FastAPI, factory, settings) -> None:
    """Register listing routes; use the application's existing DB/session setup."""

    @app.get(
        "/api/marketplace/listings",
        response_model=list[ListingPublicResponse],
    )
    def browse_listings(limit: int = Query(default=50, ge=1, le=100)):
        with factory() as db:
            return list_public_listings(db, limit=limit)

    @app.get(
        "/api/marketplace/listings/{listing_id}",
        response_model=ListingPublicResponse,
    )
    def read_listing(listing_id: UUID):
        with factory() as db:
            return get_public_listing(db, listing_id)

    @app.get("/api/marketplace/listings/{listing_id}/cover")
    def listing_cover(listing_id: UUID):
        """Serve only the published revision's pinned portrait.

        Unlike paid scenes, public discovery does not require payout-wallet
        verification. Unpublishing immediately hides this public cover.
        The private character image endpoint must not be used here.
        """
        with factory() as db:
            file_path = db.scalar(
                select(Portrait.file_path)
                .join(ListingRevision, ListingRevision.portrait_id == Portrait.id)
                .join(
                    CharacterListing,
                    and_(
                        CharacterListing.id == ListingRevision.listing_id,
                        CharacterListing.latest_revision == ListingRevision.revision,
                    ),
                )
                .where(
                    CharacterListing.id == str(listing_id),
                    CharacterListing.status == "published",
                )
            )

        if not file_path:
            raise HTTPException(status_code=404, detail="Cover not found.")
        root = Path(settings.image_directory).resolve()
        target = (root / file_path).resolve()
        if not target.is_relative_to(root) or not target.is_file():
            raise HTTPException(status_code=404, detail="Cover not found.")
        return FileResponse(target)

    @app.post(
        "/api/marketplace/listings",
        response_model=ListingOwnerResponse,
    )
    def publish(body: ListingPublishRequest, request: Request):
        # Only server-created identity state is trusted. Never accept owner or
        # payout wallet from request JSON/headers.
        account_id = getattr(request.state, "user_id", None)
        with factory() as db:
            return publish_listing(db, body, account_id=account_id)

    @app.get(
        "/api/marketplace/listings/{listing_id}/owner",
        response_model=ListingOwnerResponse,
    )
    def read_own_listing(listing_id: UUID, request: Request):
        account_id = getattr(request.state, "user_id", None)
        with factory() as db:
            return get_owner_listing(db, listing_id, account_id=account_id)

    @app.post(
        "/api/marketplace/listings/{listing_id}/unpublish",
        response_model=ListingOwnerResponse,
    )
    def unpublish(listing_id: UUID, request: Request):
        account_id = getattr(request.state, "user_id", None)
        with factory() as db:
            return unpublish_listing(db, listing_id, account_id=account_id)
