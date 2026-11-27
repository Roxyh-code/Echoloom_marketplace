import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import HTTPException
from sqlalchemy import select

from echoloom.db import sessions
from echoloom.marketplace_models import CharacterListing, ListingRevision, MarketplaceCreator
from echoloom.payments.authorization import encode_base58
from echoloom.payments.creator_demo import activate_demo_pair
from echoloom.payments.models import BuyerWallet
from echoloom.payments.quote import creator_wallet, split_payouts
from test_marketplace import register_account, seed_character, publish


def wallet():
    return encode_base58(Ed25519PrivateKey.generate().public_key().public_bytes_raw())


def test_demo_activation_requires_verified_wallets_and_preserves_revisions(setup):
    client, _, _, _, engine = setup
    owners, ids, wallets = [], [], [wallet(), wallet()]
    for name in ("demo_alice", "demo_bob"):
        client.post("/api/account/logout")
        owner = register_account(setup, name)
        owners.append(owner)
        ids.append(publish(client, seed_character(setup, owner))["listing_id"])
    with sessions(engine)() as db:
        db.add(BuyerWallet(account_id=owners[0], wallet=wallets[0]))
        db.commit()
        with pytest.raises(ValueError, match="verify a wallet"):
            activate_demo_pair(db, ids)
        db.rollback()
        assert all(not db.get(CharacterListing, i).monetization_enabled for i in ids)
        db.add(BuyerWallet(account_id=owners[1], wallet=wallets[1]))
        db.commit()
        rows = activate_demo_pair(db, ids)
        db.commit()
        assert [x["revision"] for x in rows] == [2, 2]
        assert activate_demo_pair(db, ids) == rows
        db.commit()
        for i, w in zip(ids, wallets):
            old = db.scalar(select(ListingRevision).where(ListingRevision.listing_id == i, ListingRevision.revision == 1))
            assert old.payout_wallet_address is None
            with pytest.raises(HTTPException):
                creator_wallet(db, {"source_listing_id": i, "source_listing_revision": 1}, "buyer")
            assert creator_wallet(db, {"source_listing_id": i, "source_listing_revision": 2}, "buyer") == w
        platform, buyer = wallet(), wallet()
        payouts = split_payouts(*wallets, platform, buyer)
        assert {p.wallet: p.amount for p in payouts} == {wallets[0]:450000, wallets[1]:450000, platform:100000}
        assert all(db.get(CharacterListing, i).latest_revision == 2 for i in ids)
