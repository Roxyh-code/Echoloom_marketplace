"""Strict API contracts for public Marketplace character listings.

These schemas define what a creator may explicitly publish and what a buyer
may receive. They must not be built by serializing a private Character profile.
Wallet identities, payout addresses, and image selection are server-owned.
"""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MarketplaceSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ListingPublicFields(MarketplaceSchema):
    """Allowlisted, user-approved character metadata (no secrets or prompts)."""

    name: str = Field(min_length=1, max_length=80)
    short_description: str = Field(min_length=1, max_length=320)
    tags: list[str] = Field(default_factory=list, max_length=8)
    public_personality: list[str] = Field(default_factory=list, max_length=6)

    @field_validator("tags", "public_personality")
    @classmethod
    def validate_labels(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values]
        if any(not value or len(value) > 40 for value in normalized):
            raise ValueError("Each tag or public trait must contain 1–40 characters.")
        if len({value.casefold() for value in normalized}) != len(normalized):
            raise ValueError("Duplicate tags or public traits are not allowed.")
        return normalized


class ListingPublishRequest(ListingPublicFields):
    """Creator-supplied fields for initial publication or a new revision.

    The service must obtain creator identity, payout wallet and character
    ownership from verified server-side state, not from this request.
    """

    character_id: UUID
    rights_basis: Literal["original", "licensed"]
    rights_confirmed: Literal[True]
    # None preserves an existing enabled listing; True explicitly opts in.
    enable_earnings: bool | None = None

    def public_payload(self) -> dict:
        """Return only fields explicitly allowed in a public revision."""
        return ListingPublicFields(
            name=self.name,
            short_description=self.short_description,
            tags=self.tags,
            public_personality=self.public_personality,
        ).model_dump(mode="json")


class ListingPublicResponse(ListingPublicFields):
    """Safe representation for discovery and public listing detail pages."""

    listing_id: UUID
    revision: int = Field(ge=1)
    creator_display_name: str = Field(min_length=1, max_length=80)
    cover_image_url: str | None = None


class ListingOwnerResponse(MarketplaceSchema):
    """Private creator dashboard metadata, never returned by public routes."""

    listing_id: UUID
    character_id: UUID
    status: Literal["published", "unpublished"]
    latest_revision: int = Field(ge=0)
    monetization_enabled: bool = False


class ListingOwnerDetailResponse(ListingOwnerResponse):
    """Private owner-only listing snapshot, including unpublished revisions.

    Still allowlisted: no character profile, prompt, payout wallet, account ID
    or private story data is serialized into the dashboard.
    """

    name: str = Field(min_length=1, max_length=80)
    short_description: str = Field(min_length=1, max_length=320)
    tags: list[str] = Field(default_factory=list, max_length=8)
    public_personality: list[str] = Field(default_factory=list, max_length=6)
    rights_basis: Literal["original", "licensed"]
