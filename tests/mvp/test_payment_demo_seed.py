import pytest
from sqlalchemy import select
from echoloom.db import sessions, RehearsalScene
from echoloom.payments.demo_seed import seed_accounts, prepare_scene, demo_id, ACCOUNTS
from echoloom.marketplace_models import MarketplaceCreator, CharacterListing, ListingRevision
from echoloom.payments.models import Payment, Entitlement
from echoloom.scene_access import status
from test_payment_wallet import keypair, proof
from test_marketplace import publish


def test_demo_seed_requires_real_payout_setup(setup):
    client, _, _, settings, engine = setup
    settings.solana_creator_self_service_enabled = True
    with sessions(engine)() as db:
        credentials = seed_accounts(db)
        with pytest.raises(ValueError):
            seed_accounts(db)
        with pytest.raises(ValueError, match="enable earnings"):
            prepare_scene(db)
    for credential, name in zip(credentials, ("Mira", "Rowan")):
        assert client.post("/api/account/login", json=credential).status_code == 200
        key, wallet = keypair()
        challenge = client.post("/api/payments/creator/wallet/challenge", json={"wallet": wallet})
        assert challenge.status_code == 200
        assert client.post("/api/payments/creator/wallet/verify", json=proof(key, challenge.json())).status_code == 200
        publish(client, demo_id(name), name=name, enable_earnings=True)
        client.post("/api/account/logout")
    with sessions(engine)() as db:
        result = prepare_scene(db)
        row = db.get(RehearsalScene, result["scene_id"])
        assert row.owner_id == demo_id(ACCOUNTS[2])
        assert not row.document["demo"]
        assert status(db, row)["payment_required"]
        assert status(db, row)["generated_sentences"] == 40
        assert db.query(Payment).count() == db.query(Entitlement).count() == 0
    assert client.post("/api/account/login", json=credentials[2]).status_code == 200
    assert client.get("/api/rehearsal/scenes/" + result["scene_id"]).status_code == 200
