from test_marketplace import register_account, seed_character, publish, publish_payload
from test_payment_wallet import keypair, proof
from echoloom.db import sessions
from echoloom.marketplace_models import CharacterListing, ListingRevision
from sqlalchemy import select


def test_payout_onboarding_and_revision_preservation(setup):
    client, _, _, settings, engine = setup
    owner = register_account(setup)
    cid = seed_character(setup, owner)
    listing = publish(client, cid)
    key, wallet = keypair()
    path = "/api/payments/creator/wallet/"
    assert client.post(path + "challenge", json={"wallet": wallet}).status_code == 403
    settings.solana_creator_self_service_enabled = True
    c = client.post(path + "challenge", json={"wallet": wallet})
    assert c.status_code == 200, c.text
    signed = proof(key, c.json())
    assert client.post("/api/payments/wallet/verify", json=signed).status_code == 409
    result = client.post(path + "verify", json=signed)
    assert result.status_code == 200, result.text
    assert result.json()["ready"] and result.json()["wallet"] == wallet
    assert client.post(path + "verify", json=signed).status_code == 409
    assert client.get("/api/payments/wallet").json()["verified"] is False
    enabled = publish(client, cid, enable_earnings=True)
    assert enabled["monetization_enabled"] is True
    edited = publish(client, cid, name="Mira updated")
    assert edited["monetization_enabled"] is True
    assert edited["latest_revision"] == enabled["latest_revision"] + 1
    with sessions(engine)() as db:
        old = db.scalar(select(ListingRevision).where(ListingRevision.listing_id == listing["listing_id"],
            ListingRevision.revision == 1))
        assert old.payout_wallet_address is None
        latest = db.scalar(select(ListingRevision).where(ListingRevision.listing_id == listing["listing_id"],
            ListingRevision.revision == edited["latest_revision"]))
        assert latest.payout_wallet_address == wallet
    assert publish(client, cid, enable_earnings=False)["monetization_enabled"] is False


def test_unverified_cannot_enable(setup):
    client, *_ = setup
    owner = register_account(setup)
    cid = seed_character(setup, owner)
    assert client.post("/api/marketplace/listings", json=publish_payload(cid, enable_earnings=True)).status_code == 409
