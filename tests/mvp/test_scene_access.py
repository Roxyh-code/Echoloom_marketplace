"""Unified 40-sentence free preview for ALL character combinations.

No real wallet or model calls. Production-like FastAPI/worker using FakeText.
"""
from copy import deepcopy
from uuid import uuid4

from echoloom.db import RehearsalScene, sessions
from echoloom.rehearsal_schema import Block, Performance
from test_marketplace import publish, register_account, seed_character
from test_rehearsal import quick, wait


def request_scene(client, *, character_ids=None, cast_sources=None, demo=False):
    response = client.post("/api/rehearsal/scenes", json={
        "operation_id": str(uuid4()),
        **({"character_ids": character_ids} if character_ids else {}),
        **({"cast_sources": cast_sources} if cast_sources else {}),
        "demo": demo,
        "setup": {"premise": "Two travelers meet at an old railway station."},
    })
    assert response.status_code == 201, response.text
    return response.json()


def command(client, scene, kind="continue", **extra):
    return client.post(
        f"/api/rehearsal/scenes/{scene['id']}/commands",
        json={"operation_id": str(uuid4()), "expected_revision": scene["revision"],
              "kind": kind, **extra},
    )


def generate(client, scene, kind="continue", **extra):
    r = command(client, scene, kind, **extra)
    assert r.status_code == 200, r.text
    return wait(client, r.json())


def access(client, scene):
    r = client.get(f"/api/rehearsal/scenes/{scene['id']}/access")
    assert r.status_code == 200, r.text
    return r.json()


def story_text(scene):
    return "\n".join(
        block["text"]
        for node in scene["document"]["nodes"].values()
        for block in node["blocks"]
    )


def test_two_private_characters_are_metered_and_generated_sentences_count(setup):
    client, fake, *_ = setup
    a, b = quick(client, "Rin"), quick(client, "Tao")
    scene = request_scene(client, character_ids=[a, b])
    initial = access(client, scene)
    assert initial == {
        "mode": "metered",
        "free_sentence_limit": 40,
        "generated_sentences": 0,
        "free_sentences_remaining": 40,
        "payment_required": False,
        "wallet_checkout_available": False,
    }
    first = generate(client, scene)
    assert first["status"] == "completed"
    scene = first["scene"]
    assert access(client, scene)["generated_sentences"] == 2
    for _ in range(2):
        scene = generate(client, scene)["scene"]
    assert access(client, scene)["generated_sentences"] == 6
    assert access(client, scene)["payment_required"] is False
    assert all("source_listing_id" not in a for a in scene["document"]["cast"])


def test_mixed_and_public_cast_have_same_40_sentence_limit(setup):
    client, _, _, _, _ = setup
    owner = register_account(setup)
    listing_a = publish(client, seed_character(setup, owner))
    listing_b = publish(client, seed_character(setup, owner))
    owned = quick(client, "Private")
    a = {"source": "listing", "listing_id": listing_a["listing_id"],
         "expected_revision": listing_a["latest_revision"]}
    b = {"source": "listing", "listing_id": listing_b["listing_id"],
         "expected_revision": listing_b["latest_revision"]}
    mixed = request_scene(client, cast_sources=[
        {"source": "private", "character_id": owned}, a
    ])
    public = request_scene(client, cast_sources=[a, b])
    for scene in (mixed, public):
        assert access(client, scene)["mode"] == "metered"
        after = generate(client, scene)["scene"]
        assert access(client, after)["generated_sentences"] == 2


def test_generator_truncates_at_sentence_40_next_line_41_requires_wallet(setup, monkeypatch):
    client, fake, _, _, engine = setup
    a, b = quick(client, "Mira"), quick(client, "Rowan")
    scene = request_scene(client, character_ids=[a, b])
    all_sentences = " ".join(f"Sentence {i}." for i in range(1, 47))
    monkeypatch.setattr(fake, "rehearsal", lambda context: Performance(
        blocks=[Block(type="narration", character_id=None, text=all_sentences)]
    ))
    job = generate(client, scene)
    assert job["status"] == "completed", job
    scene = job["scene"]
    txt = story_text(scene)
    assert "Sentence 40." in txt
    assert "Sentence 41." not in txt
    assert access(client, scene)["free_sentences_remaining"] == 0
    assert access(client, scene)["payment_required"] is True
    assert command(client, scene, "read", revealed=40).status_code == 200
    latest = client.get(f"/api/rehearsal/scenes/{scene['id']}").json()
    over = command(client, latest, "read", revealed=41)
    assert over.status_code == 402
    assert command(client, latest, "continue").status_code == 402
    assert "Sentence 41." not in client.get("/api/rehearsal/scenes").text
    export = client.get(f"/api/rehearsal/scenes/{scene['id']}/export")
    assert export.status_code == 200
    assert "Sentence 40." in export.text and "Sentence 41." not in export.text
    # Already-readable words can still be saved without an extra charge.
    saved = command(client, latest, "result")
    assert saved.status_code == 200
    assert saved.json()["document"]["status"] == "saved"


def test_existing_legacy_50_sentence_story_does_not_expose_hidden_text(setup):
    client, fake, _, _, engine = setup
    a, b = quick(client, "Mira"), quick(client, "Rowan")
    scene = request_scene(client, character_ids=[a, b])
    job = generate(client, scene)
    assert job["status"] == "completed"
    sid = scene["id"]
    with sessions(engine)() as db:
        row = db.get(RehearsalScene, sid)
        doc = deepcopy(row.document)
        # Simulate a genuine pre-migration document without the new counter.
        doc.pop("free_generated_sentences", None)
        v = doc["versions"][doc["active_version"]]
        node = doc["nodes"][v["head"]]
        node["blocks"][0]["text"] = " ".join(f"Legacy sentence {i}." for i in range(1, 51))
        v["revealed"] = 50
        row.document = doc
        db.commit()
    response = client.get(f"/api/rehearsal/scenes/{sid}")
    assert response.status_code == 200
    assert "Legacy sentence 39." in response.text
    assert "Legacy sentence 40." in response.text
    assert "Legacy sentence 41." not in response.text
    assert "Legacy sentence 50." not in response.text
    assert "Legacy sentence 41." not in client.get("/api/rehearsal/scenes").text
    assert "Legacy sentence 41." not in client.get(
        f"/api/rehearsal/scenes/{sid}/export"
    ).text
    assert access(client, scene)["payment_required"]
    assert command(client, response.json(), "read", revealed=41).status_code == 402


def test_free_sentences_are_per_scene_even_when_reusing_private_characters(setup):
    client, *_ = setup
    a, b = quick(client, "Rin"), quick(client, "Tao")
    first = request_scene(client, character_ids=[a, b])
    first = generate(client, first)["scene"]
    new = request_scene(client, character_ids=[a, b])
    assert access(client, first)["generated_sentences"] == 2
    assert access(client, new)["generated_sentences"] == 0
    assert access(client, new)["free_sentence_limit"] == 40


def test_demo_is_exempt_and_failure_does_not_use_free_sentences(setup):
    client, fake, *_ = setup
    example = request_scene(client, demo=True)
    assert access(client, example)["mode"] == "demo"
    assert access(client, example)["payment_required"] is False
    a, b = quick(client, "Rin"), quick(client, "Tao")
    scene = request_scene(client, character_ids=[a, b])
    fake.fail = True
    failed = generate(client, scene)
    assert failed["status"] == "failed"
    assert access(client, scene)["free_sentences_remaining"] == 40
    fake.fail = False
    scene = client.get(f"/api/rehearsal/scenes/{scene['id']}").json()
    successful = generate(client, scene)
    assert successful["status"] == "completed"
    assert access(client, successful["scene"])["generated_sentences"] == 2


def test_same_operation_id_not_charged_twice(setup):
    client, *_ = setup
    a, b = quick(client, "Rin"), quick(client, "Tao")
    scene = request_scene(client, character_ids=[a, b])
    url = f"/api/rehearsal/scenes/{scene['id']}/commands"
    request = {"operation_id": str(uuid4()),
               "expected_revision": scene["revision"], "kind": "continue"}
    one = client.post(url, json=request)
    assert one.status_code == 200
    wait(client, one.json())
    again = client.post(url, json=request)
    assert again.status_code == 200
    assert one.json()["job_id"] == again.json()["job_id"]
    assert access(client, scene)["generated_sentences"] == 2
