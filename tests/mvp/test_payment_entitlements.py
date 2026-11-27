"""Verified grants extend the actual server-side story limit."""
from uuid import uuid4

from echoloom.db import sessions
from echoloom.payments.models import Entitlement, Payment, PaymentOrder
from echoloom.rehearsal_schema import Block, Performance
from test_marketplace import register_account
from test_rehearsal import quick
from test_scene_access import access, command, generate, request_scene, story_text


def grant(db, owner, scene, paid=True):
    oid = str(uuid4())
    db.add(PaymentOrder(
        id=oid, scene_id=scene, account_id=owner,
        buyer_wallet="buyer", product_id=f"scene-unlock-40:{scene}",
        program_id="program", mint="mint", config_pda="config",
        receipt_pda=oid, amount_minor_units=1000000,
        payout_lines=[], config_version=1, expires_at_unix=1800000000,
        signer_pubkey="signer", authorization_message_b64="fixture",
        authorization_signature_b64="fixture", status="paid" if paid else "pending",
    ))
    db.flush()
    if paid:
        db.add(Payment(order_id=oid, tx_signature=oid, verified_slot=1))
        db.flush()
        db.add(Entitlement(order_id=oid))
    db.commit()


def test_verified_grants_extend_generation_read_and_export(setup, monkeypatch):
    client, fake, _, _, engine = setup
    owner = register_account(setup)
    a, b = quick(client, "Rin"), quick(client, "Tao")
    scene = request_scene(client, character_ids=[a, b])
    sid = scene["id"]
    def output(start):
        return Performance(blocks=[Block(
            type="narration", character_id=None,
            text=" ".join(f"Sentence {i}." for i in range(start, start+46)),
        )])
    monkeypatch.setattr(fake, "rehearsal", lambda context: output(1))
    scene = generate(client, scene)["scene"]
    assert access(client, scene)["generated_sentences"] == 40
    assert command(client, scene).status_code == 402
    with sessions(engine)() as db:
        grant(db, owner, sid, paid=False)
    assert access(client, scene)["free_sentence_limit"] == 40
    with sessions(engine)() as db:
        grant(db, owner, sid)
    assert access(client, scene)["free_sentence_limit"] == 80
    assert access(client, scene)["free_sentences_remaining"] == 40
    monkeypatch.setattr(fake, "rehearsal", lambda context: output(41))
    scene = generate(client, scene)["scene"]
    assert access(client, scene)["generated_sentences"] == 80
    assert "Sentence 80." in story_text(scene)
    assert "Sentence 81." not in story_text(scene)
    assert command(client, scene, "read", revealed=80).status_code == 200
    scene = client.get(f"/api/rehearsal/scenes/{sid}").json()
    assert command(client, scene, "read", revealed=81).status_code == 402
    export = client.get(f"/api/rehearsal/scenes/{sid}/export")
    assert "Sentence 80." in export.text and "Sentence 81." not in export.text
    with sessions(engine)() as db:
        grant(db, owner, sid)
    assert access(client, scene)["free_sentence_limit"] == 120
    assert access(client, scene)["free_sentences_remaining"] == 40
    fresh = request_scene(client, character_ids=[a, b])
    assert access(client, fresh)["free_sentence_limit"] == 40
