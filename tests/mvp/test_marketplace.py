r"""Marketplace publishing and public-discovery integration tests.

Step 8C: publishing an owned character requires an authenticated local account,
not an approved creator or a Solana wallet. Monetization remains disabled
until a separate, signed wallet-onboarding workflow exists.

Run from repository root:
    .\.venv\Scripts\python.exe -m pytest -q tests/mvp/test_marketplace.py

Uses the project's existing isolated `setup` fixture: no live API or wallet.
"""

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
PASSWORD = "test-password-12345"
PUBLIC_KEYS = {
    "listing_id",
    "name",
    "short_description",
    "tags",
    "public_personality",
    "revision",
    "creator_display_name",
    "cover_image_url",
}


def register_account(setup, username="alice"):
    client, _, _, _, engine = setup
    response = client.post(
        "/api/account/register", json={"username": username, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    with sessions(engine)() as db:
        account = db.scalar(select(Account).where(Account.username == username))
        assert account is not None
        return account.id


def login(client, username="alice"):
    result = client.post(
        "/api/account/login", json={"username": username, "password": PASSWORD}
    )
    assert result.status_code == 200, result.text


def seed_character(setup, account_id, *, with_cover=False, archived=False):
    """Create a private character, but deliberately do not seed a creator."""
    _, _, _, settings, engine = setup
    with sessions(engine)() as db:
        character = Character(
            owner_id=account_id,
            original_description=SECRET,
            current_profile_version=1,
            archived=archived,
        )
        db.add(character)
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
                change_summary="Private test profile",
            )
        )
        if with_cover:
            settings.image_directory.mkdir(parents=True, exist_ok=True)
            image_name = f"{character.id}.png"
            Image.new("RGB", (10, 10), (120, 60, 160)).save(
                settings.image_directory / image_name
            )
            portrait = Portrait(
                character_id=character.id,
                parent_image_id=None,
                provider="test",
                model="test-image",
                prompt=SECRET,
                file_path=image_name,
                version=1,
            )
            db.add(portrait)
            db.flush()
            character.current_image_id = portrait.id
        db.commit()
        return character.id


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


def publish(client, character_id, **overrides):
    result = client.post(
        "/api/marketplace/listings", json=publish_payload(character_id, **overrides)
    )
    assert result.status_code == 200, result.text
    return result.json()


def test_first_publish_without_wallet_auto_creates_creator_and_disables_monetization(setup):
    client, _, _, _, engine = setup
    assert client.get("/api/marketplace/listings").json() == []
    account_id = register_account(setup)
    character_id = seed_character(setup, account_id)

    listing_response = publish(client, character_id)
    assert listing_response["status"] == "published"
    assert listing_response["latest_revision"] == 1
    assert listing_response["character_id"] == character_id

    with sessions(engine)() as db:
        creator = db.scalar(
            select(MarketplaceCreator).where(MarketplaceCreator.account_id == account_id)
        )
        assert creator is not None  # Not pre-approved or created by a wallet flow.
        assert creator.wallet_address is None
        assert creator.wallet_verified_at is None
        assert creator.is_approved is False
        listing = db.scalar(
            select(CharacterListing).where(CharacterListing.id == listing_response["listing_id"])
        )
        assert listing.creator_id == creator.id
        assert listing.monetization_enabled is False
        revision = db.scalar(
            select(ListingRevision).where(ListingRevision.listing_id == listing.id)
        )
        assert revision.payout_wallet_address is None


def test_public_listing_is_anonymous_and_never_leaks_private_data(setup):
    client, _, _, _, engine = setup
    account_id = register_account(setup)
    character_id = seed_character(setup, account_id)
    result = publish(client, character_id)
    listing_id = result["listing_id"]

    assert client.post("/api/account/logout").status_code == 200
    browse = client.get("/api/marketplace/listings")
    assert browse.status_code == 200, browse.text
    assert len(browse.json()) == 1
    detail = client.get(f"/api/marketplace/listings/{listing_id}")
    assert detail.status_code == 200, detail.text
    public = detail.json()
    assert set(public) == PUBLIC_KEYS
    assert public["name"] == "Mira"
    assert public["revision"] == 1
    assert public["creator_display_name"].startswith("Creator ")
    assert browse.json()[0] == public
    assert SECRET not in browse.text + detail.text
    for private_key in ("profile_json", "wallet_address", "account_id", "monetization_enabled"):
        assert private_key not in detail.text
    with sessions(engine)() as db:
        assert db.scalar(select(CharacterListing)).status == "published"


def test_duplicate_publish_is_idempotent_and_edits_create_immutable_revisions(setup):
    client, _, _, _, engine = setup
    account_id = register_account(setup)
    character_id = seed_character(setup, account_id)
    first = publish(client, character_id)
    again = publish(client, character_id)
    assert again["listing_id"] == first["listing_id"]
    assert again["latest_revision"] == 1

    changed = publish(
        client, character_id, short_description="An entirely new public description."
    )
    assert changed["listing_id"] == first["listing_id"]
    assert changed["latest_revision"] == 2
    with sessions(engine)() as db:
        revisions = db.scalars(
            select(ListingRevision)
            .where(ListingRevision.listing_id == first["listing_id"])
            .order_by(ListingRevision.revision)
        ).all()
        assert [r.revision for r in revisions] == [1, 2]
        assert revisions[0].public_data["short_description"] == "A determined art restorer."
        assert revisions[1].public_data["short_description"] == (
            "An entirely new public description."
        )
        assert revisions[0].profile_revision_id == revisions[1].profile_revision_id
        assert all(r.payout_wallet_address is None for r in revisions)
        assert db.get(CharacterListing, first["listing_id"]).monetization_enabled is False

    detail = client.get(f"/api/marketplace/listings/{first['listing_id']}")
    assert detail.status_code == 200
    assert detail.json()["revision"] == 2


def test_legacy_wallet_and_unapproved_creator_do_not_block_publication_or_enable_sales(setup):
    client, _, _, _, engine = setup
    account_id = register_account(setup)
    character_id = seed_character(setup, account_id)
    legacy_wallet = "TEST_UNVERIFIED_WALLET_DO_NOT_PAY"
    with sessions(engine)() as db:
        creator = MarketplaceCreator(
            account_id=account_id,
            wallet_address=legacy_wallet,
            wallet_verified_at=None,
            display_name="Mira Studio",
            is_approved=False,
        )
        db.add(creator)
        db.commit()

    result = publish(client, character_id)
    with sessions(engine)() as db:
        assert len(db.scalars(select(MarketplaceCreator)).all()) == 1
        listing = db.get(CharacterListing, result["listing_id"])
        assert listing.monetization_enabled is False
        revision = db.scalar(
            select(ListingRevision).where(ListingRevision.listing_id == listing.id)
        )
        assert revision.payout_wallet_address is None
    detail = client.get(f"/api/marketplace/listings/{result['listing_id']}")
    assert detail.status_code == 200
    assert detail.json()["creator_display_name"] == "Mira Studio"
    assert legacy_wallet not in detail.text


def test_unpublish_hides_listing_and_cover_and_republish_keeps_history(setup):
    client, _, _, _, engine = setup
    account_id = register_account(setup)
    character_id = seed_character(setup, account_id, with_cover=True)
    first = publish(client, character_id)
    listing_id = first["listing_id"]
    cover_url = f"/api/marketplace/listings/{listing_id}/cover"
    assert client.get(f"/api/marketplace/listings/{listing_id}").json()[
        "cover_image_url"
    ] == cover_url

    assert client.post("/api/account/logout").status_code == 200
    cover = client.get(cover_url)
    assert cover.status_code == 200, cover.text
    assert cover.headers["content-type"].startswith("image/png")
    assert cover.content.startswith(b"\x89PNG")
    assert client.get(f"/api/marketplace/listings/{listing_id}").status_code == 200

    login(client)
    hidden = client.post(f"/api/marketplace/listings/{listing_id}/unpublish")
    assert hidden.status_code == 200, hidden.text
    assert hidden.json()["status"] == "unpublished"
    assert client.get("/api/marketplace/listings").json() == []
    assert client.get(f"/api/marketplace/listings/{listing_id}").status_code == 404
    assert client.get(cover_url).status_code == 404
    owner = client.get(f"/api/marketplace/listings/{listing_id}/owner")
    assert owner.status_code == 200
    assert owner.json()["latest_revision"] == 1

    again = publish(client, character_id)
    assert again["listing_id"] == listing_id
    assert again["latest_revision"] == 2
    assert client.get(cover_url).status_code == 200
    with sessions(engine)() as db:
        listing = db.get(CharacterListing, listing_id)
        assert listing.monetization_enabled is False
        assert len(
            db.scalars(select(ListingRevision).where(ListingRevision.listing_id == listing_id)).all()
        ) == 2


def test_anon_write_and_owner_api_require_authentication(setup):
    client = setup[0]
    account_id = register_account(setup)
    character_id = seed_character(setup, account_id)
    listing_id = publish(client, character_id)["listing_id"]
    assert client.post("/api/account/logout").status_code == 200

    assert client.get(f"/api/marketplace/listings/{listing_id}/owner").status_code == 401
    assert client.post(f"/api/marketplace/listings/{listing_id}/unpublish").status_code == 401
    assert client.post(
        "/api/marketplace/listings", json=publish_payload(character_id)
    ).status_code == 401
    assert client.get(f"/api/marketplace/listings/{listing_id}").status_code == 200


def test_another_user_cannot_publish_or_manage_someone_elses_character(setup):
    client, _, _, settings, engine = setup
    alice_id = register_account(setup, "alice")
    alice_character = seed_character(setup, alice_id)
    alice_listing = publish(client, alice_character)["listing_id"]

    settings.allow_additional_accounts = True  # Isolated test app only.
    bob_id = register_account(setup, "bob")
    bob_character = seed_character(setup, bob_id)
    # Bob has never had a MarketplaceCreator; that is not an access restriction.
    with sessions(engine)() as db:
        assert db.scalar(
            select(MarketplaceCreator).where(MarketplaceCreator.account_id == bob_id)
        ) is None

    assert client.post(
        "/api/marketplace/listings", json=publish_payload(alice_character)
    ).status_code == 404
    assert client.get(f"/api/marketplace/listings/{alice_listing}/owner").status_code == 404
    assert client.post(
        f"/api/marketplace/listings/{alice_listing}/unpublish"
    ).status_code == 404
    assert publish(client, bob_character)["status"] == "published"
    assert len(client.get("/api/marketplace/listings").json()) == 2


def test_invalid_or_unsafe_publish_payload_is_rejected(setup):
    client = setup[0]
    account_id = register_account(setup)
    character_id = seed_character(setup, account_id)
    for override in (
        {"wallet_address": "ATTACKER_WALLET"},
        {"payout_wallet_address": "ATTACKER_WALLET"},
        {"monetization_enabled": True},
        {"creator_id": "SPOOFED"},
        {"private_information": SECRET},
        {"rights_confirmed": False},
        {"tags": ["Mystery", "mystery"]},
    ):
        rejected = client.post(
            "/api/marketplace/listings", json=publish_payload(character_id, **override)
        )
        assert rejected.status_code == 422, (override, rejected.text)


def test_archived_character_cannot_be_published(setup):
    client = setup[0]
    account_id = register_account(setup)
    character_id = seed_character(setup, account_id, archived=True)
    response = client.post(
        "/api/marketplace/listings", json=publish_payload(character_id)
    )
    assert response.status_code == 409, response.text


def test_public_browse_limit_is_validated(setup):
    client = setup[0]
    assert client.get("/api/marketplace/listings?limit=0").status_code == 422
    assert client.get("/api/marketplace/listings?limit=101").status_code == 422
    assert client.get("/api/marketplace/listings?limit=50").status_code == 200


def test_owned_listings_are_authenticated_and_allowlisted(setup):
    client, _, _, _, _ = setup
    assert client.get("/api/marketplace/my-listings").status_code == 401
    account_id = register_account(setup)
    assert client.get("/api/marketplace/my-listings").json() == []
    character_id = seed_character(setup, account_id)
    listing = publish(client, character_id)
    owned = client.get("/api/marketplace/my-listings")
    assert owned.status_code == 200, owned.text
    assert len(owned.json()) == 1
    info = owned.json()[0]
    assert info == {
        "listing_id": listing["listing_id"],
        "character_id": character_id,
        "status": "published",
        "latest_revision": 1,
        "name": "Mira",
        "short_description": "A determined art restorer.",
        "tags": ["Mystery", "Adventure"],
        "public_personality": ["Calm", "Determined"],
        "rights_basis": "original",
    }
    assert SECRET not in owned.text
    assert "wallet_address" not in owned.text
    assert client.post("/api/account/logout").status_code == 200
    assert client.get("/api/marketplace/my-listings").status_code == 401


def test_owned_listing_management_survives_unpublish_and_edits(setup):
    client, _, _, _, _ = setup
    account_id = register_account(setup)
    character_id = seed_character(setup, account_id)
    first = publish(client, character_id)
    hidden = client.post(
        f"/api/marketplace/listings/{first['listing_id']}/unpublish"
    )
    assert hidden.status_code == 200
    owned = client.get("/api/marketplace/my-listings").json()
    assert len(owned) == 1
    assert owned[0]["status"] == "unpublished"
    assert owned[0]["short_description"] == "A determined art restorer."
    assert client.get("/api/marketplace/listings").json() == []
    republished = publish(
        client, character_id,
        short_description="Edited public story summary.",
        rights_basis="licensed",
    )
    assert republished["listing_id"] == first["listing_id"]
    assert republished["latest_revision"] == 2
    again = client.get("/api/marketplace/my-listings").json()
    assert again[0]["status"] == "published"
    assert again[0]["short_description"] == "Edited public story summary."
    assert again[0]["rights_basis"] == "licensed"


def test_other_creator_cannot_enumerate_owned_listings(setup):
    client, _, _, settings, _ = setup
    alice_id = register_account(setup, "alice")
    alice_character = seed_character(setup, alice_id)
    publish(client, alice_character)
    settings.allow_additional_accounts = True
    register_account(setup, "bob")
    assert client.get("/api/marketplace/my-listings").json() == []
