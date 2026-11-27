"""Test-only bridge: Python authorization and receipt verification on loopback."""
import base64
import json
import secrets
import sys
import time
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
from uuid import uuid4

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from echoloom.payments.authorization import Authorization, serialize_authorization, order_reference_hash
from echoloom.payments.quote import split_payouts, PRICE
from echoloom.payments.signer import AuthorizationSigner
from echoloom.payments.solana_rpc import rpc_call, pda, DEVNET_GENESIS
from echoloom.payments.verification import check_transaction
from echoloom.payments.receipt import validate_receipt

URL = "http://127.0.0.1:8899"


def sign(data):
    signer = AuthorizationSigner(Ed25519PrivateKey.from_private_bytes(bytes(data["test_seed"])))
    order_id = uuid4()
    expiry = int(time.time()) + 900
    product = "scene-unlock-40:" + str(uuid4())
    payouts = split_payouts(*data["creators"], data["treasury"], data["buyer"])
    message = serialize_authorization(Authorization(
        bytes.fromhex(data["domain"]), data["program"], data["config"], order_id,
        data["buyer"], product, data["mint"], PRICE, payouts, data["version"],
        expiry, secrets.token_bytes(32),
    ))
    return dict(id=str(order_id), product_id=product, program_id=data["program"],
                config_pda=data["config"], mint=data["mint"], buyer_wallet=data["buyer"],
                receipt_pda=pda(data["program"], b"purchase_receipt", order_reference_hash(order_id)),
                amount_minor_units=PRICE, config_version=data["version"], expires_at_unix=expiry,
                payout_lines=[dict(wallet=p.wallet, amount_minor_units=p.amount) for p in payouts],
                signer_pubkey=signer.public_key,
                authorization_message_b64=base64.b64encode(message).decode(),
                authorization_signature_b64=base64.b64encode(signer.sign(message)).decode())


def local_genesis():
    genesis = rpc_call(URL, "getGenesisHash", [])
    if not isinstance(genesis, str) or not genesis or genesis in {DEVNET_GENESIS, "5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp", "4uhcVJyU9pJkvQyS88uRDiswHXSCkY3z"}:
        raise ValueError("Expected disposable local validator, not a public cluster")
    return genesis


def verify(data):
    local_genesis()
    order = SimpleNamespace(**data["order"])
    signature = data["signature"]
    tx = rpc_call(URL, "getTransaction", [signature, {
        "encoding": "jsonParsed", "commitment": "confirmed", "maxSupportedTransactionVersion": 0,
    }])
    slot = check_transaction(order, signature, tx)
    account = rpc_call(URL, "getAccountInfo", [order.receipt_pda, {
        "encoding": "base64", "commitment": "confirmed", "minContextSlot": slot,
    }])["value"]
    if not account or account["owner"] != order.program_id or account["executable"]:
        raise ValueError("Invalid receipt account")
    validate_receipt(base64.b64decode(account["data"][0], validate=True), order, slot)
    return {"verified": True, "slot": slot}


def verify_ledger(data):
    """Exercise production verifier and reporting with a disposable real DB.

    Only the test subprocess substitutes the known local genesis. Never change
    the deployment settings or the production network guard.
    """
    from echoloom.db import Base, RehearsalScene, make_engine, sessions
    from echoloom.companion_models import Account
    from echoloom.payments.models import PaymentOrder, Payment, Entitlement, CreatorEarningSnapshot
    from echoloom.payments.schemas import VerifyRequest
    from echoloom.payments import verification
    from echoloom.payments.earnings import creator_earnings
    from echoloom.scene_access import status
    from sqlalchemy import select, func

    genesis = local_genesis()
    terms = data["order"]
    creators = data["creators"]
    assert len(creators) == 2 and len(set(creators)) == 2
    assert len(terms["payout_lines"]) == 3
    for wallet in creators:
        assert next(p["amount_minor_units"] for p in terms["payout_lines"] if p["wallet"] == wallet) == 450000
    settings = SimpleNamespace(solana_rpc_url=URL, solana_payment_commitment="confirmed",
        solana_program_id=terms["program_id"], solana_mint=terms["mint"], solana_payments_enabled=True)
    with TemporaryDirectory(prefix="echoloom-local-ledger-") as tmp:
        engine = make_engine("sqlite:///" + str(Path(tmp) / "test.db"))
        try:
            Base.metadata.create_all(engine)
            with sessions(engine)() as db:
                db.add_all([Account(id=x, username=x, password_hash="test-only") for x in ("buyer", "creator-a", "creator-b")])
                db.flush()
                scene = RehearsalScene(id=str(uuid4()), owner_id="buyer", document={"free_generated_sentences": 40})
                db.add(scene)
                db.flush()
                order = PaymentOrder(**terms, account_id="buyer", scene_id=scene.id)
                db.add(order)
                db.flush()
                for slot, wallet in enumerate(creators):
                    db.add(CreatorEarningSnapshot(order_id=order.id, cast_slot=slot,
                        creator_account_id=("creator-a", "creator-b")[slot], character_id=str(uuid4()),
                        character_name=("Mira", "Rowan")[slot], wallet=wallet,
                        amount_minor_units=450000, listing_id=None, listing_revision=None))
                db.commit()
                before = status(db, scene)
                assert before["payment_required"] and before["free_sentence_limit"] == 40
                assert creator_earnings(db, "creator-a")["totals"] == []
                body = VerifyRequest(order_id=order.id, tx_signature=data["signature"])
                with patch.object(verification, "DEVNET_GENESIS", genesis):
                    from fastapi import HTTPException
                    try:
                        verification.verify_order(db, settings, "creator-a", body)
                    except HTTPException as exc:
                        assert exc.status_code == 404
                    else:
                        raise AssertionError("Foreign account verified order")
                    first = verification.verify_order(db, settings, "buyer", body)
                    assert first["status"] == "paid", first
                    repeat = verification.verify_order(db, settings, "buyer", body)
                    assert first == repeat
                after = status(db, scene)
                assert after["free_sentence_limit"] == 80 and after["free_sentences_remaining"] == 40
                assert db.scalar(select(func.count()).select_from(Payment)) == 1
                assert db.scalar(select(func.count()).select_from(Entitlement)) == 1
                earnings = [creator_earnings(db, x) for x in ("creator-a", "creator-b")]
                assert all(e["totals"] == [{"mint": terms["mint"], "amount_minor_units": 450000}]
                           and e["paid_unlocks"] == 1 for e in earnings)
                assert creator_earnings(db, "buyer")["totals"] == []
                return {"verified": True, "before": 40, "after": 80, "payments": 1,
                        "entitlements": 1, "creator_amounts": [450000, 450000]}
        finally:
            engine.dispose()


if __name__ == "__main__":
    data = json.load(sys.stdin)
    if sys.argv[1:] == ["sign"]:
        result = sign(data)
    elif sys.argv[1:] == ["verify"]:
        result = verify(data)
    elif sys.argv[1:] == ["verify-ledger"]:
        result = verify_ledger(data)
    else:
        raise SystemExit("Expected sign, verify or verify-ledger")
    print(json.dumps(result))
