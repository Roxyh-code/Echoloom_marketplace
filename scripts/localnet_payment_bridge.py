"""Test-only bridge: Python authorization and receipt verification on loopback."""
import base64
import json
import secrets
import sys
import time
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


def verify(data):
    if rpc_call(URL, "getGenesisHash", []) == DEVNET_GENESIS:
        raise ValueError("Expected disposable local validator")
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


if __name__ == "__main__":
    data = json.load(sys.stdin)
    if sys.argv[1:] == ["sign"]:
        result = sign(data)
    elif sys.argv[1:] == ["verify"]:
        result = verify(data)
    else:
        raise SystemExit("Expected sign or verify")
    print(json.dumps(result))
