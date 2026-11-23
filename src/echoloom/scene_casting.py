"""Resolve user-selected cast sources into immutable, privacy-safe scene actors.

A public Listing is a published *projection* of a private Character, NOT
permission to read that Character's full ProfileRevision. Published scenes
expose actor snapshots back to their owners through the Rehearsal API.
"""

from fastapi import HTTPException
from sqlalchemy import select

from .db import Character, ProfileRevision, uid
from .marketplace_models import CharacterListing, ListingRevision
from .marketplace_schemas import ListingPublicFields
from .schemas import Personality, Profile


def snapshot_private_character(db, cid, owner):
    """Preserve the existing owner-only private snapshot contract."""
    c = db.get(Character, str(cid))
    if not c or c.owner_id != owner:
        raise HTTPException(404, "Character not found. Choose another actor.")
    p = db.scalar(
        select(ProfileRevision).where(
            ProfileRevision.character_id == c.id,
            ProfileRevision.version == c.current_profile_version,
        )
    )
    if p is None:
        raise HTTPException(409, "Character profile revision missing.")
    profile = Profile.model_validate(p.profile_json)
    return {
        "id": c.id,
        "source_character_id": c.id,
        "name": profile.name,
        "profile": profile.model_dump(),
        "description": c.original_description,
        "snapshot_revision": c.current_profile_version,
        "avatar": f"/api/characters/{c.id}/images/{c.current_image_id}/file"
        if c.current_image_id
        else None,
    }


def resolve_cast_sources(db, sources, owner):
    """Validate two private/Marketplace sources and pin exactly one revision each."""
    if not owner:
        raise HTTPException(401, "Sign in before casting Marketplace characters.")
    if len(sources) != 2:
        raise HTTPException(422, "Choose exactly two characters.")

    cast = []
    seen_characters = set()
    for slot, source in enumerate(sources):
        if source.source == "private":
            actor = snapshot_private_character(db, source.character_id, owner)
            underlying_id = actor["source_character_id"]
        else:
            listing = db.get(CharacterListing, str(source.listing_id))
            if not listing or listing.status != "published":
                raise HTTPException(404, "Published listing not found.")
            if listing.latest_revision != source.expected_revision:
                raise HTTPException(409, "Listing was updated. Refresh the character before casting.")
            pinned = db.scalar(
                select(ListingRevision).where(
                    ListingRevision.listing_id == listing.id,
                    ListingRevision.revision == source.expected_revision,
                )
            )
            if pinned is None:
                raise HTTPException(409, "Listing revision is unavailable.")

            # Only public creator-approved fields may flow to the consumer's
            # serialized Scene. Never load ProfileRevision.profile_json here.
            public = ListingPublicFields.model_validate(pinned.public_data)
            safe_profile = Profile(
                name=public.name,
                short_description=public.short_description,
                personality=Personality(core_traits=public.public_personality),
            )
            actor = {
                "id": uid(),  # scene-local, not the creator's private Character ID
                "source_character_id": None,
                "source_listing_id": listing.id,
                "source_listing_revision": pinned.revision,
                "name": public.name,
                "profile": safe_profile.model_dump(),
                "description": public.short_description,
                "snapshot_revision": pinned.character_version,
                # Placeholder is replaced with a scene-owner-only pinned URL.
                "avatar": "pending-scene-portrait" if pinned.portrait_id else None,
            }
            underlying_id = listing.character_id

        if underlying_id in seen_characters:
            raise HTTPException(422, "Choose two different characters.")
        seen_characters.add(underlying_id)
        actor["slot"] = slot
        cast.append(actor)
    return cast


def rebind_marketplace_avatars(cast, scene_id):
    """Bind public actor portrait references to this specific scene.

    Also rebinds cloned casts from a prior saved scene so the child does not
    depend on the parent scene remaining available.
    """
    for slot, actor in enumerate(cast):
        if actor.get("source_listing_id") and actor.get("avatar"):
            actor["avatar"] = f"/api/rehearsal/scenes/{scene_id}/cast/{slot}/portrait"
