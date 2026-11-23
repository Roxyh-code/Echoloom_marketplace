"""Step 1/2: mixed cast API, published revision pinning and privacy regression."""

from uuid import uuid4

from sqlalchemy import select

from echoloom.companion_models import Account
from echoloom.db import sessions
from echoloom.local_accounts import password_hash
from test_marketplace import (
    PASSWORD,
    SECRET,
    login,
    publish,
    publish_payload,
    register_account,
    seed_character,
)


def request_scene(client, sources, operation_id=None):
    return client.post(
        "/api/rehearsal/scenes",
        json={
            "operation_id": operation_id or str(uuid4()),
            "cast_sources": sources,
            "setup": {"premise": "Two characters meet at the deserted station."},
        },
    )


def listing_ref(listing, revision=None):
    return {
        "source": "listing",
        "listing_id": listing["listing_id"],
        "expected_revision": revision or listing["latest_revision"],
    }


def private_ref(cid):
    return {"source": "private", "character_id": cid}


def add_other_account(setup):
    engine = setup[4]
    with sessions(engine)() as db:
        row = Account(username="bob", password_hash=password_hash(PASSWORD))
        db.add(row)
        db.commit()
        return row.id


def test_published_two_creator_cast_uses_only_allowlisted_data_and_pinned_portraits(setup):
    client, _, _, _, _ = setup
    alice = register_account(setup)
    char_a = seed_character(setup, alice, with_cover=True)
    listing_a = publish(client, char_a)
    bob = add_other_account(setup)
    assert client.post("/api/account/logout").status_code == 200
    login(client, "bob")
    char_b = seed_character(setup, bob, with_cover=True)
    listing_b = publish(client, char_b, name="Rowan", short_description="A weary navigator.")
    assert client.post("/api/account/logout").status_code == 200
    login(client)

    operation_id = str(uuid4())
    response = request_scene(client, [listing_ref(listing_a), listing_ref(listing_b)], operation_id)
    assert response.status_code == 201, response.text
    scene = response.json()
    actors = scene["document"]["cast"]
    assert [a["name"] for a in actors] == ["Mira", "Rowan"]
    assert len({a["id"] for a in actors}) == 2
    assert all(a["source_character_id"] is None for a in actors)
    assert [a["source_listing_id"] for a in actors] == [listing_a["listing_id"], listing_b["listing_id"]]
    assert all(a["source_listing_revision"] == 1 for a in actors)
    assert all(a["slot"] in (0, 1) for a in actors)
    assert SECRET not in response.text
    assert char_a not in response.text and char_b not in response.text
    assert all(a["profile"]["private_information"] == "" for a in actors)
    assert all(a["profile"]["backstory"] == "" for a in actors)
    assert actors[0]["profile"]["personality"]["core_traits"] == ["Calm", "Determined"]
    assert actors[1]["description"] == "A weary navigator."

    # Safe retries do not create extra scene records.
    retry = request_scene(client, [listing_ref(listing_a), listing_ref(listing_b)], operation_id)
    assert retry.status_code == 201
    assert retry.json()["id"] == scene["id"]
    assert len(client.get("/api/rehearsal/scenes").json()) == 1

    cover = client.get(actors[1]["avatar"])
    assert cover.status_code == 200 and cover.content.startswith(b"\x89PNG")
    # A scene owner may use the pinned image after unpublishing; anonymous
    # catalog access still obeys the live publication status.
    login(client, "bob")
    unpub = client.post(f"/api/marketplace/listings/{listing_b['listing_id']}/unpublish")
    assert unpub.status_code == 200
    assert client.get(f"/api/marketplace/listings/{listing_b['listing_id']}/cover").status_code == 404
    login(client)
    assert client.get(actors[1]["avatar"]).status_code == 200
    assert request_scene(client, [listing_ref(listing_a), listing_ref(listing_b)]).status_code == 404
    assert client.post(
        f"/api/rehearsal/scenes/{scene['id']}/commands",
        json={
            "operation_id": str(uuid4()), "expected_revision": scene["revision"],
            "kind": "cast", "character_ids": [char_a, char_b],
        },
    ).status_code == 409


def test_mixed_cast_private_ownership_duplicate_and_revision_guards(setup):
    client, _, _, _, _ = setup
    alice = register_account(setup)
    public_cid = seed_character(setup, alice)
    listing = publish(client, public_cid)
    private = client.post(
        "/api/rehearsal/characters",
        json={"operation_id": str(uuid4()), "name": "Jun", "description": "A careful investigator at the station."},
    )
    assert private.status_code == 201, private.text
    private_cid = private.json()["character_id"]

    valid = request_scene(client, [private_ref(private_cid), listing_ref(listing)])
    assert valid.status_code == 201, valid.text
    cast = valid.json()["document"]["cast"]
    assert cast[0]["source_character_id"] == private_cid
    assert cast[1]["source_character_id"] is None
    assert cast[0]["id"] == private_cid
    assert cast[1]["id"] != public_cid

    # Publish a fully valid private character to exercise cross-source
    # identity de-duplication without relying on the privacy test's seed.
    private_listing = publish(client, private_cid, name="Jun")
    dup = request_scene(client, [private_ref(private_cid), listing_ref(private_listing)])
    assert dup.status_code == 422
    assert request_scene(client, [listing_ref(listing), listing_ref(listing)]).status_code == 422
    assert request_scene(client, [private_ref(private_cid), listing_ref(listing, revision=2)]).status_code == 409
    assert request_scene(client, [private_ref(private_cid), {
        "source": "listing", "listing_id": str(uuid4()), "expected_revision": 1
    }]).status_code == 404
    assert request_scene(client, [private_ref(private_cid)]).status_code == 422
    assert request_scene(client, [private_ref(private_cid), {
        "source": "listing", "listing_id": listing["listing_id"]
    }]).status_code == 422
    assert request_scene(client, [private_ref(private_cid), {
        "source": "listing", "listing_id": listing["listing_id"], "character_id": public_cid,
        "expected_revision": 1
    }]).status_code == 422


def test_cannot_cast_others_private_character_or_read_scene_portrait(setup):
    client, _, _, _, _ = setup
    alice = register_account(setup)
    own_char = client.post(
        "/api/rehearsal/characters",
        json={"operation_id": str(uuid4()), "name": "Alice", "description": "A traveler at the station."},
    ).json()["character_id"]
    listing = publish(client, seed_character(setup, alice, with_cover=True))
    scene = request_scene(client, [private_ref(own_char), listing_ref(listing)]).json()
    bob = add_other_account(setup)
    bob_char = seed_character(setup, bob)
    assert request_scene(client, [private_ref(bob_char), listing_ref(listing)]).status_code == 404

    assert client.post("/api/account/logout").status_code == 200
    assert client.get(scene["document"]["cast"][1]["avatar"]).status_code == 401
    login(client, "bob")
    assert client.get(scene["document"]["cast"][1]["avatar"]).status_code == 404
    assert client.get(f"/api/rehearsal/scenes/{scene['id']}").status_code == 404


def test_published_edit_does_not_change_existing_scene_snapshot(setup):
    client, _, _, _, _ = setup
    alice = register_account(setup)
    a = seed_character(setup, alice)
    b = seed_character(setup, alice)
    la = publish(client, a)
    lb = publish(client, b)
    before = request_scene(client, [listing_ref(la), listing_ref(lb)])
    assert before.status_code == 201
    sid = before.json()["id"]
    edited = client.post(
        "/api/marketplace/listings",
        json=publish_payload(a, name="Mira Revised", short_description="A different public summary."),
    )
    assert edited.status_code == 200, edited.text
    after = client.get(f"/api/rehearsal/scenes/{sid}")
    assert after.status_code == 200
    actor = after.json()["document"]["cast"][0]
    assert actor["name"] == "Mira"
    assert actor["description"] == "A determined art restorer."
    assert actor["source_listing_revision"] == 1
    assert request_scene(client, [listing_ref(la), listing_ref(lb)]).status_code == 409
    assert request_scene(client, [listing_ref(edited.json()), listing_ref(lb)]).status_code == 201


def test_legacy_private_cast_still_creates_scene(setup):
    client = setup[0]
    first = client.post(
        "/api/rehearsal/characters",
        json={"operation_id": str(uuid4()), "name": "Dara", "description": "An observant historian."},
    ).json()["character_id"]
    second = client.post(
        "/api/rehearsal/characters",
        json={"operation_id": str(uuid4()), "name": "Emil", "description": "A guarded detective."},
    ).json()["character_id"]
    result = client.post("/api/rehearsal/scenes", json={
        "operation_id": str(uuid4()), "character_ids": [first, second],
        "setup": {"premise": "A strange meeting at the station."},
    })
    assert result.status_code == 201, result.text
    assert [a["source_character_id"] for a in result.json()["document"]["cast"]] == [first, second]
