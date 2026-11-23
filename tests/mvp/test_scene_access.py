"""Marketplace Scene Access: server-side first trial and metered AI generations.

All tests use the deterministic local FakeText provider; no wallet or LLM key.
"""
from uuid import uuid4

from sqlalchemy import select

from echoloom.db import sessions
from echoloom.scene_access_models import SceneAccess, SceneTrialClaim, SceneUsage
from echoloom.rehearsal_schema import Performance, StateChange
from test_marketplace import publish, register_account, seed_character
from test_rehearsal import wait, quick


def new_marketplace_scene(setup, ids=None):
    client, *_ = setup
    if ids is None:
        owner = register_account(setup)
        ids = [
            publish(client, seed_character(setup, owner)),
            publish(client, seed_character(setup, owner)),
        ]
    body = {
        "operation_id": str(uuid4()),
        "cast_sources": [
            {"source": "listing", "listing_id": record["listing_id"],
             "expected_revision": record["latest_revision"]}
            for record in ids
        ],
        "setup": {"premise": "Two strangers confront their shared past in a station."},
    }
    response = client.post("/api/rehearsal/scenes", json=body)
    assert response.status_code == 201, response.text
    return response.json(), ids


def make_command(scene, kind="continue", **data):
    return {
        "operation_id": str(uuid4()),
        "expected_revision": scene["revision"],
        "kind": kind,
        **data,
    }


def submit(client, scene, kind="continue", **data):
    return client.post(
        f"/api/rehearsal/scenes/{scene['id']}/commands",
        json=make_command(scene, kind, **data),
    )


def allowance(client, scene):
    response = client.get(f"/api/rehearsal/scenes/{scene['id']}/access")
    assert response.status_code == 200, response.text
    return response.json()


def start_and_wait(client, scene, kind="continue", **data):
    response = submit(client, scene, kind, **data)
    assert response.status_code == 200, response.text
    return wait(client, response.json())


def test_trial_opening_one_direction_then_payment_required(setup):
    client, _, _, _, engine = setup
    scene, _ = new_marketplace_scene(setup)
    before = allowance(client, scene)
    assert before == {
        "mode": "marketplace", "opening_available": 0,
        "directions_available": 0, "opening_consumed": False,
        "trial_eligible": True, "payment_required": False,
    }
    first = start_and_wait(client, scene)
    assert first["status"] == "completed", first
    scene = first["scene"]
    assert allowance(client, scene)["opening_consumed"] is True
    assert allowance(client, scene)["directions_available"] == 1

    second = start_and_wait(client, scene, "direction", text="Let Mira confess the truth.")
    assert second["status"] == "completed", second
    scene = second["scene"]
    assert allowance(client, scene)["directions_available"] == 0
    assert allowance(client, scene)["payment_required"] is True

    denied = submit(client, scene, "continue")
    assert denied.status_code == 402, denied.text
    assert len(client.get("/api/rehearsal/scenes").json()) == 1
    with sessions(engine)() as db:
        journal = list(db.scalars(select(SceneUsage)))
        assert len(journal) == 2
        assert all(u.status == "charged" for u in journal)
        assert sorted(u.category for u in journal) == ["direction", "opening"]


def test_first_trial_does_not_repeat_for_new_scene_after_delete(setup):
    client, _, _, _, engine = setup
    original, records = new_marketplace_scene(setup)
    second, _ = new_marketplace_scene(setup, records)
    assert allowance(client, second)["trial_eligible"] is True
    first_job = start_and_wait(client, original)
    assert first_job["status"] == "completed"
    assert allowance(client, second)["payment_required"] is True
    assert submit(client, second).status_code == 402
    assert client.delete(f"/api/rehearsal/scenes/{original['id']}").status_code == 204
    assert submit(client, second).status_code == 402
    with sessions(engine)() as db:
        claim = db.scalar(select(SceneTrialClaim))
        assert claim.scene_id == original["id"]
        assert db.get(SceneAccess, original["id"]) is None


def test_failed_opening_refunds_and_can_claim_other_scene(setup):
    client, fake, _, _, engine = setup
    scene, records = new_marketplace_scene(setup)
    other, _ = new_marketplace_scene(setup, records)
    fake.fail = True
    failed = start_and_wait(client, scene)
    assert failed["status"] == "failed"
    assert allowance(client, scene)["trial_eligible"] is True
    with sessions(engine)() as db:
        assert db.scalar(select(SceneTrialClaim)) is None
        usage = db.scalar(select(SceneUsage))
        assert usage.status == "refunded"
    fake.fail = False
    success = start_and_wait(client, other)
    assert success["status"] == "completed"
    assert allowance(client, scene)["payment_required"] is True
    assert allowance(client, other)["opening_consumed"] is True


def test_failed_direction_refunds_retry_uses_one_credit(setup):
    client, fake, *_ = setup
    scene, _ = new_marketplace_scene(setup)
    opening = start_and_wait(client, scene)
    assert opening["status"] == "completed"
    scene = opening["scene"]
    fake.fail = True
    response = submit(client, scene, "direction", text="Reveal what changed.")
    assert response.status_code == 200
    failed = wait(client, response.json())
    assert failed["status"] == "failed"
    assert allowance(client, scene)["directions_available"] == 1
    fake.fail = False
    retry = client.post(f"/api/rehearsal/jobs/{failed['id']}/retry")
    assert retry.status_code == 200, retry.text
    result = wait(client, {"job_id": retry.json()["job_id"]})
    assert result["status"] == "completed"
    assert allowance(client, scene)["directions_available"] == 0
    replay = client.post(f"/api/rehearsal/jobs/{failed['id']}/retry")
    assert replay.json()["job_id"] == retry.json()["job_id"]


def test_same_operation_id_does_not_charge_twice(setup):
    client, _, _, _, engine = setup
    scene, _ = new_marketplace_scene(setup)
    body = make_command(scene, "continue")
    url = f"/api/rehearsal/scenes/{scene['id']}/commands"
    first = client.post(url, json=body)
    assert first.status_code == 200
    j = wait(client, first.json())
    assert j["status"] == "completed"
    repeated = client.post(url, json=body)
    assert repeated.status_code == 200
    assert repeated.json()["job_id"] == first.json()["job_id"]
    assert allowance(client, scene)["directions_available"] == 1
    with sessions(engine)() as db:
        assert len(db.scalars(select(SceneUsage)).all()) == 1


def test_manual_operations_free_ai_rewrite_and_branch_metered(setup):
    client, _, _, _, _ = setup
    scene, _ = new_marketplace_scene(setup)
    j = start_and_wait(client, scene)
    scene = j["scene"]
    assert submit(client, scene, "rename", name="New title").status_code == 200
    scene = client.get(f"/api/rehearsal/scenes/{scene['id']}").json()
    assert allowance(client, scene)["directions_available"] == 1
    j = start_and_wait(client, scene, "branch", text="A surprising visitor arrives.")
    assert j["status"] == "completed"
    assert allowance(client, j["scene"])["directions_available"] == 0
    denied = submit(client, j["scene"], "replay", text="Try again.")
    assert denied.status_code == 402


def test_private_and_demo_rehearsals_remain_unmetered(setup):
    client, *_ = setup
    a, b = quick(client, "Rin"), quick(client, "Tao")
    private = client.post("/api/rehearsal/scenes", json={
        "operation_id": str(uuid4()),
        "character_ids": [a, b],
        "setup": {"premise": "A long-awaited reunion at the station."},
    })
    assert private.status_code == 201
    scene = private.json()
    assert allowance(client, scene)["mode"] == "private"
    for _ in range(3):
        job = start_and_wait(client, scene)
        assert job["status"] == "completed", job
        scene = job["scene"]
    assert allowance(client, scene)["payment_required"] is False


def test_partial_generated_result_charged_once_and_retry_not_charged_again(setup, monkeypatch):
    client, fake, *_ = setup
    scene, _ = new_marketplace_scene(setup)
    # Force an error only after the first generated block has been durably saved.
    old_provider = fake.rehearsal
    def two_blocks(context):
        output = old_provider(context)
        output.changes = [StateChange(after_block=1, text="A revealed detail.")]
        return output
    monkeypatch.setattr(fake, "rehearsal", two_blocks)
    from echoloom import rehearsal_service
    original = rehearsal_service.state_change
    def fail_after_first(*args, **kwargs):
        raise RuntimeError("Injected second-block failure")
    monkeypatch.setattr(rehearsal_service, "state_change", fail_after_first)
    failed = start_and_wait(client, scene)
    assert failed["status"] == "failed"
    assert failed["scene"]["document"]["nodes"]
    assert allowance(client, scene)["opening_consumed"] is True
    assert allowance(client, scene)["directions_available"] == 1
    monkeypatch.setattr(rehearsal_service, "state_change", original)
    monkeypatch.setattr(fake, "rehearsal", old_provider)
    retry = client.post(f"/api/rehearsal/jobs/{failed['id']}/retry")
    assert retry.status_code == 200, retry.text
    done = wait(client, {"job_id": retry.json()["job_id"]})
    assert done["status"] == "completed"
    assert allowance(client, done["scene"])["directions_available"] == 1
