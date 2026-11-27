import base64
import json
from hashlib import sha256
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import HTTPException

from echoloom.config import Settings
from echoloom.db import RehearsalScene, sessions
from echoloom.payments import quote
from echoloom.payments.authorization import encode_base58
from echoloom.payments.models import PaymentOrder
from echoloom.payments.schemas import QuoteRequest
from echoloom.payments.signer import verify_signature


def wallet(n):
    return encode_base58(bytes([n]) * 32)


def test_split_and_merge():
    payouts = quote.split_payouts(wallet(1), wallet(1), wallet(3), wallet(4))
    assert [(p.wallet, p.amount) for p in payouts] == [(wallet(1), 900000), (wallet(3), 100000)]
    with pytest.raises(HTTPException):
        quote.split_payouts(wallet(1), wallet(2), wallet(3), wallet(1))


def test_quote_disabled_and_unverified(setup):
    client, _, _, settings, _ = setup
    body = {"scene_id": str(uuid4()), "buyer_wallet": wallet(4)}
    assert client.post("/api/payments/quote", json=body).status_code == 401
    assert client.post("/api/account/register", json={
        "username": "buyer", "password": "test-password",
    }).status_code == 200
    assert client.post("/api/payments/quote", json=body).status_code == 503
    settings.solana_payments_enabled = True
    assert client.post("/api/payments/quote", json=body).status_code == 403
    assert client.post("/api/payments/quote", json={**body, "amount": 1}).status_code == 422


def test_signed_quote_persisted(setup, tmp_path, monkeypatch):
    _, _, _, _, engine = setup
    key = Ed25519PrivateKey.generate()
    path = tmp_path / "signer.json"
    path.write_text(json.dumps(list(key.private_bytes_raw() + key.public_key().public_bytes_raw())))
    settings = Settings(_env_file=None, solana_payments_enabled=True,
                        solana_backend_signer_path=str(path),
                        solana_program_id=wallet(5), solana_mint=wallet(6),
                        solana_platform_wallet=wallet(3))
    sid = str(uuid4())
    monkeypatch.setattr(quote, "creator_details", lambda db, actor, owner: dict(
        wallet=actor["wallet"], creator_account_id="fixture-creator",
        character_id="fixture-character", listing_id=None, listing_revision=None,
        character_name="Fixture"))
    monkeypatch.setattr(quote, "load_config", lambda s, k: (wallet(7), sha256(b"test").digest(), 1))
    with sessions(engine)() as db:
        # Real account FK for the test scene.
        from echoloom.companion_models import Account
        db.add(Account(id="buyer", username="buyer", password_hash="fixture"))
        db.flush()
        db.add(RehearsalScene(id=sid, owner_id="buyer",
                              document={"cast": [{"wallet": wallet(1)}, {"wallet": wallet(2)}]}))
        db.commit()
        request = QuoteRequest(scene_id=sid, buyer_wallet=wallet(4))
        with pytest.raises(HTTPException) as exc:
            quote.create_quote(db, settings, "other", request, wallet(4))
        assert exc.value.status_code == 404
        result = quote.create_quote(db, settings, "buyer", request, wallet(4))
        row = db.get(PaymentOrder, str(result.order_id))
        assert row.status == "pending" and row.amount_minor_units == 1_000_000
        assert sum(p.amount_minor_units for p in result.payout_lines) == 1_000_000
        message = base64.b64decode(result.authorization_message_b64)
        assert len(message) == 462
        assert verify_signature(result.signer_pubkey, message,
                                base64.b64decode(result.authorization_signature_b64))
