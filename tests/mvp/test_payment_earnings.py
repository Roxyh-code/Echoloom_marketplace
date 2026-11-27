from echoloom.db import sessions
from echoloom.payments.models import CreatorEarningSnapshot, Payment
from test_payment_orders import order
from test_marketplace import register_account


def test_earnings_verified_owner_scoped_and_grouped(setup):
    client, _, _, _, engine = setup
    assert client.get("/api/payments/creator/earnings").status_code == 401
    owner = register_account(setup)
    with sessions(engine)() as db:
        db.add_all([order("paid", status="paid"), order("pending"), order("old", status="paid")])
        db.flush()
        db.add_all([Payment(order_id="paid", tx_signature="sig", verified_slot=1),
                    Payment(order_id="old", tx_signature="old-sig", verified_slot=2)])
        for oid, slot, account in [("paid", 0, owner), ("paid", 1, owner),
                                  ("pending", 0, owner), ("pending", 1, "other")]:
            db.add(CreatorEarningSnapshot(order_id=oid, cast_slot=slot,
                creator_account_id=account, character_id=str(slot), character_name="Mira",
                wallet="creator", amount_minor_units=450000))
        db.commit()
    result = client.get("/api/payments/creator/earnings")
    assert result.status_code == 200
    data = result.json()
    assert data["totals"] == [{"mint": "mint", "amount_minor_units": 900000}]
    assert data["paid_unlocks"] == 1
    assert len(data["characters"]) == 2
    assert len(data["recent_transactions"]) == 1
    assert data["recent_transactions"][0]["amount_minor_units"] == 900000
    assert data["recent_transactions"][0]["signature"] == "sig"
