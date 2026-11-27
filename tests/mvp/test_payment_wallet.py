import base64

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from echoloom.payments.authorization import encode_base58
from echoloom.payments.models import BuyerWallet, WalletChallenge
from echoloom.db import sessions


def keypair():
    key = Ed25519PrivateKey.generate()
    return key, encode_base58(key.public_key().public_bytes_raw())


def register(client, name="buyer"):
    assert client.post("/api/account/register", json={
        "username": name, "password": "test-password",
    }).status_code == 200


def challenge(client, wallet):
    response = client.post("/api/payments/wallet/challenge", json={"wallet":wallet})
    assert response.status_code == 200, response.text
    return response.json()


def proof(key, challenge):
    return {"challenge_id":challenge["challenge_id"],
            "signature_b64":base64.b64encode(key.sign(challenge["message"].encode())).decode()}


def test_binding_and_replay(setup):
    client, *_ = setup
    key,wallet = keypair()
    assert client.post("/api/payments/wallet/challenge",json={"wallet":wallet}).status_code == 401
    register(client)
    assert client.get("/api/payments/wallet").json()["verified"] is False
    first = challenge(client,wallet)
    older = challenge(client,wallet)
    body = proof(key,first)
    assert client.post("/api/payments/wallet/verify",json=body).json() == {"wallet":wallet,"verified":True}
    assert client.get("/api/payments/wallet").json()["wallet"] == wallet
    assert client.post("/api/payments/wallet/verify",json=body).status_code == 409
    assert client.post("/api/payments/wallet/verify",json=proof(key,older)).status_code == 409


def test_wrong_key_and_expired(setup):
    client, _, _, _, engine = setup
    register(client)
    key,wallet = keypair()
    wrong,_ = keypair()
    attempt = challenge(client,wallet)
    assert client.post("/api/payments/wallet/verify",json=proof(wrong,attempt)).status_code == 403
    with sessions(engine)() as db:
        row = db.get(WalletChallenge,attempt["challenge_id"])
        row.expires_at_unix = 1
        db.commit()
    assert client.post("/api/payments/wallet/verify",json=proof(key,attempt)).status_code == 409
    assert client.get("/api/payments/wallet").json()["verified"] is False


def test_cross_account_and_duplicate_wallet(setup):
    client, _, _, settings, _ = setup
    settings.allow_additional_accounts = True
    register(client,"buyer1")
    key,wallet = keypair()
    attempt = challenge(client,wallet)
    assert client.post("/api/payments/wallet/verify",json=proof(key,attempt)).status_code == 200
    client.post("/api/account/logout")
    register(client,"buyer2")
    assert client.post("/api/payments/wallet/verify",json=proof(key,attempt)).status_code == 404
    second = challenge(client,wallet)
    assert client.post("/api/payments/wallet/verify",json=proof(key,second)).status_code == 409
    assert client.get("/api/payments/wallet").json()["verified"] is False
