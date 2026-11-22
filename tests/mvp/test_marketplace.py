r"""End-to-end tests for public Marketplace listings and creator authorization.

Run from the repository root with:
    .\.venv\Scripts\python.exe -m pytest -q tests/mvp/test_marketplace.py

This file uses the project's existing `setup` fixture. Test creator-wallet links
are inserted directly into the isolated test database; no live wallet identity
or public creator-registration endpoint is assumed to exist yet.
"""

from uuid import uuid4

from PIL import Image
from sqlalchemy import select

from echoloom.companion_models import Account
from echoloom.db import Character, Portrait, ProfileRevision, sessions
from echoloom.marketplace_models import (
    CharacterListing,
    ListingRevision,
    MarketplaceCreator,
)

SECRET = "NEVER_EXPOSE_THIS_PRIVATE_BACKSTORY_OR_PROMPT"


def register_account(setup, username="alice"):
    client, _, _, _, engine = setup
    response = client.post(
        "/api/account/register",
        json={"username": username, "password": "test-password-12345"},
    )
    assert response.status_code == 200, response.text
    with sessions(engine)() as db:
        account = db.scalar(select(Account).where(Account.username == username))
        assert account is not None
        return account.id


def seed_creator_and_character(
    setup, account_id, *, approved=True, wallet=None, with_cover=False
):
    """Seed a test-approved Creator; do not emulate wallet verification in HTTP."""
    _, _, _, settings, engine = setup
    wallet = wallet or "TEST_WALLET_" + uuid4().hex

    with sessions(engine)() as db:
        creator = MarketplaceCreator(
            account_id=account_id,
            wallet_address=wallet,
            display_name="Alice's Studio",
            is_approved=approved,
        )
        character = Character(
            owner_id=account_id,
            original_description=SECRET,
            current_profile_version=1,
        )
        db.add_all([creator, character])
        db.flush()
        db.add(
            ProfileRevision(
                character_id=character.id,
                version=1,
                profile_json={
                    "name": "Mira",
                    "backstory": SECRET,
                    "private_information": SECRET,
                    "internal_prompt": SECRET,
                },
                change_summary="Test-only private profile",
            )
        )

        if with_cover:
            images = settings.image_directory
            images.mkdir(parents=True, exist_ok=True)
            (images / "public_mira.png").parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (10, 10), (120, 60, 160)).save(
                images / "public_mira.png"
            )
            portrait = Portrait(
                character_id=character.id,
                parent_image_id=None,
                provider="test",
                model="test-image",
                prompt=SECRET,
                file_path="public_mira.png",
                version=1,
            )
            db.add(portrait)
            db.flush()
            character.current_image_id = portrait.id

        db.commit()
        return creator.id, character.id, wallet


def publish_payload(character_id, **overrides):
    data = {
        "character_id": character_id,
        "name": "Mira",
        "short_description": "A determined art restorer.",
        "tags": ["Mystery", "Adventure"],
        "public_personality": ["Calm", "Determined"],
        "rights_basis": "original",
        "rights_confirmed": True,
    }
    data.update(overrides)
    return data


def test_public_listing_can_be_browsed_anonymously_without_private_data(setup):
    client = setup[0]
    assert client.get("/api/marketplace/listings").status_code == 200
    assert client.get("/api/marketplace/listings").json() == []

    account_id = register_account(setup)
    _, character_id, wallet = seed_creator_and_character(setup, account_id)
    response = client.post(
        "/api/marketplace/listings", json=publish_payload(character_id)
    )
    assert response.status_code == 200, response.text
    listing_id = response.json()["listing_id"]

    assert client.post("/api/account/logout").status_code == 200
    results = client.get("/api/marketplace/listings")
    assert results.status_code == 200, results.text
    assert len(results.json()) == 1
    detail = client.get(f"/api/marketplace/listings/{listing_id}")
    assert detail.status_code == 200, detail.text
    public = detail.json()
    assert public["name"] == "Mira"
    assert public["revision"] == 1
    assert public["creator_display_name"] == "Alice's Studio"
    assert set(public) == {
        "name", "short_description", "tags", "public_personality",
        "listing_id", "revision", "creator_display_name", "cover_image_url",
    }
    assert SECRET not in detail.text
    assert wallet not in detail.text
    assert "profile_json" not in detail.text


def test_republish_creates_immutable_revision_and_preserves_payout_snapshot(setup):
    client, _, _, _, engine = setup
    account_id = register_account(setup)
    creator_id, character_id, wallet = seed_creator_and_character(setup, account_id)
    payload = publish_payload(character_id)

    first = client.post("/api/marketplace/listings", json=payload)
    assert first.status_code == 200, first.text
    listing_id = first.json()["listing_id"]
    assert first.json()["latest_revision"] == 1

    duplicate = client.post("/api/marketplace/listings", json=payload)
    assert duplicate.status_code == 200, duplicate.text
    assert duplicate.json()["listing_id"] == listing_id
    assert duplicate.json()["latest_revision"] == 1

    updated = client.post(
        "/api/marketplace/listings",
        json=publish_payload(character_id, short_description="A new public description."),
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["latest_revision"] == 2

    with sessions(engine)() as db:
        listing = db.scalar(
            select(CharacterListing).where(CharacterListing.id == listing_id)
        )
        revisions = db.scalars(
            select(ListingRevision)
            .where(ListingRevision.listing_id == listing_id)
            .order_by(ListingRevision.revision)
        ).all()
        assert listing.latest_revision == 2
        assert len(revisions) == 2
        assert revisions[0].public_data["short_description"] == (
            "A determined art restorer."
        )
        assert revisions[1].public_data["short_description"] == (
            "A new public description."
        )
        assert revisions[0].payout_wallet_address == wallet
        assert revisions[1].payout_wallet_address == wallet
        assert revisions[0].profile_revision_id == revisions[1].profile_revision_id
        assert revisions[0].revision == 1
        assert revisions[1].revision == 2
        assert db.get(MarketplaceCreator, creator_id) is not None

    detail = client.get(f"/api/marketplace/listings/{listing_id}")
    assert detail.status_code == 200
    assert detail.json()["revision"] == 2
    assert detail.json()["short_description"] == "A new public description."


def test_unpublish_hides_listing_but_keeps_revision_and_can_republish(setup):
    client, _, _, _, engine = setup
    account_id = register_account(setup)
    _, character_id, _ = seed_creator_and_character(setup, account_id)
    result = client.post("/api/marketplace/listings", json=publish_payload(character_id))
    assert result.status_code == 200, result.text
    listing_id = result.json()["listing_id"]

    hidden = client.post(f"/api/marketplace/listings/{listing_id}/unpublish")
    assert hidden.status_code == 200, hidden.text
    assert hidden.json()["status"] == "unpublished"
    assert client.get("/api/marketplace/listings").json() == []
    assert client.get(f"/api/marketplace/listings/{listing_id}").status_code == 404
    owner = client.get(f"/api/marketplace/listings/{listing_id}/owner")
    assert owner.status_code == 200
    assert owner.json()["latest_revision"] == 1

    again = client.post("/api/marketplace/listings", json=publish_payload(character_id))
    assert again.status_code == 200, again.text
    assert again.json()["listing_id"] == listing_id
    assert again.json()["latest_revision"] == 2
    with sessions(engine)() as db:
        assert len(
            db.scalars(
                select(ListingRevision).where(ListingRevision.listing_id == listing_id)
            ).all()
        ) == 2


def test_noncreator_unapproved_and_other_character_cannot_publish(setup):
    client, _, _, settings, engine = setup
    owner_id = register_account(setup, "alice")
    _, character_id, _ = seed_creator_and_character(setup, owner_id)

    settings.allow_additional_accounts = True  # Isolated test app only.
    other_id = register_account(setup, "bob")
    response = client.post(
        "/api/marketplace/listings", json=publish_payload(character_id)
    )
    assert response.status_code == 403, response.text  # Bob is not a creator.

    creator_id, bob_character_id, _ = seed_creator_and_character(
        setup, other_id, approved=False
    )
    response = client.post(
        "/api/marketplace/listings", json=publish_payload(bob_character_id)
    )
    assert response.status_code == 403, response.text  # Bob not approved.

    with sessions(engine)() as db:
        db.get(MarketplaceCreator, creator_id).is_approved = True
        db.commit()
    response = client.post(
        "/api/marketplace/listings", json=publish_payload(character_id)
    )
    assert response.status_code == 404, response.text  # Alice owns this character.
    assert client.post(
        "/api/marketplace/listings", json=publish_payload(bob_character_id)
    ).status_code == 200


def test_owner_endpoints_are_private_and_public_input_is_strict(setup):
    client = setup[0]
    account_id = register_account(setup)
    _, character_id, wallet = seed_creator_and_character(setup, account_id)
    response = client.post("/api/marketplace/listings", json=publish_payload(character_id))
    assert response.status_code == 200, response.text
    listing_id = response.json()["listing_id"]
    assert client.post("/api/account/logout").status_code == 200

    assert client.get(f"/api/marketplace/listings/{listing_id}/owner").status_code == 401
    assert client.post(f"/api/marketplace/listings/{listing_id}/unpublish").status_code == 401
    assert client.post(
        "/api/marketplace/listings", json=publish_payload(character_id)
    ).status_code == 401
    assert client.get(f"/api/marketplace/listings/{listing_id}").status_code == 200

    login = client.post(
        "/api/account/login",
        json={"username": "alice", "password": "test-password-12345"},
    )
    assert login.status_code == 200, login.text
    assert client.post(
        "/api/marketplace/listings",
        json=publish_payload(character_id, wallet_address=wallet),
    ).status_code == 422
    assert client.post(
        "/api/marketplace/listings",
        json=publish_payload(character_id, private_information=SECRET),
    ).status_code == 422
    assert client.post(
        "/api/marketplace/listings",
        json=publish_payload(character_id, rights_confirmed=False),
    ).status_code == 422
    assert client.post(
        "/api/marketplace/listings",
        json=publish_payload(character_id, tags=["Mystery", "mystery"]),
    ).status_code == 422


def test_cover_requires_active_published_listing(setup):
    client = setup[0]
    account_id = register_account(setup)
    _, character_id, _ = seed_creator_and_character(
        setup, account_id, with_cover=True
    )
    result = client.post("/api/marketplace/listings", json=publish_payload(character_id))
    assert result.status_code == 200, result.text
    listing_id = result.json()["listing_id"]
    cover_url = f"/api/marketplace/listings/{listing_id}/cover"
    assert client.get(f"/api/marketplace/listings/{listing_id}").json()[
        "cover_image_url"
    ] == cover_url

    assert client.post("/api/account/logout").status_code == 200
    cover = client.get(cover_url)
    assert cover.status_code == 200, cover.text
    assert cover.headers["content-type"].startswith("image/png")
    assert cover.content.startswith(b"\x89PNG")

    login = client.post(
        "/api/account/login",
        json={"username": "alice", "password": "test-password-12345"},
    )
    assert login.status_code == 200, login.text
    assert client.post(
        f"/api/marketplace/listings/{listing_id}/unpublish"
    ).status_code == 200
    assert client.get(cover_url).status_code == 404


def test_browse_limit_is_validated(setup):
    client = setup[0]
    assert client.get("/api/marketplace/listings?limit=0").status_code == 422
    assert client.get("/api/marketplace/listings?limit=101").status_code == 422
    assert client.get("/api/marketplace/listings?limit=50").status_code == 200
