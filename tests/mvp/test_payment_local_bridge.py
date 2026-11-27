"""Smoke-test the real bridge CLI without requiring a validator."""
import base64
import json
import subprocess
import sys
from pathlib import Path

from echoloom.payments.authorization import encode_base58
from echoloom.payments.signer import verify_signature


def test_local_bridge_sign_cli():
    root = Path(__file__).resolve().parents[2]
    wallet = lambda n: encode_base58(bytes([n]) * 32)
    data = dict(test_seed=list(range(32)), domain="09" * 32, program=wallet(5),
                config=wallet(7), buyer=wallet(4), mint=wallet(6),
                creators=[wallet(1), wallet(2)], treasury=wallet(3), version=1)
    run = subprocess.run([sys.executable, str(root / "scripts/localnet_payment_bridge.py"), "sign"],
                         input=json.dumps(data), capture_output=True, text=True, check=True, timeout=30)
    order = json.loads(run.stdout)
    assert sorted(p["amount_minor_units"] for p in order["payout_lines"]) == [100000, 450000, 450000]
    assert verify_signature(order["signer_pubkey"], base64.b64decode(order["authorization_message_b64"]),
                            base64.b64decode(order["authorization_signature_b64"]))
