import pytest
from sqlalchemy.exc import IntegrityError

from echoloom.db import Base, make_engine, sessions
from echoloom.payments.models import Entitlement, Payment, PaymentOrder
from echoloom.payments.orders import paid_sentence_allowance


@pytest.fixture
def db(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'orders.db'}")
    Base.metadata.create_all(engine)
    with sessions(engine)() as session:
        yield session
    engine.dispose()


def order(identifier, **changes):
    values = dict(
        id=identifier, scene_id="scene", account_id="account",
        buyer_wallet="buyer", product_id="scene-unlock-40:scene",
        program_id="program", mint="mint", config_pda="config",
        receipt_pda=f"receipt-{identifier}", amount_minor_units=1000000,
        payout_lines=[{"wallet": "creator", "amount_minor_units": 900000},
                      {"wallet": "platform", "amount_minor_units": 100000}],
        config_version=1, expires_at_unix=1800000000,
        signer_pubkey="signer", authorization_message_b64="fixture",
        authorization_signature_b64="fixture",
    )
    values.update(changes)
    return PaymentOrder(**values)


def test_cumulative_and_scoped_grants(db):
    db.add_all([order("a"), order("b"), order("pending"),
                order("other", account_id="other")])
    db.commit()
    assert paid_sentence_allowance(db, "scene", "account") == 0
    for identifier in ("a", "b", "other"):
        db.add(Payment(order_id=identifier, tx_signature=identifier, verified_slot=1))
        db.get(PaymentOrder, identifier).status = "paid"
        db.flush()
        db.add(Entitlement(order_id=identifier))
    db.commit()
    assert paid_sentence_allowance(db, "scene", "account") == 80
    assert paid_sentence_allowance(db, "scene", "other") == 40
    assert paid_sentence_allowance(db, "different", "account") == 0


def test_duplicate_signature_rejected(db):
    db.add_all([order("a"), order("b")])
    db.commit()
    db.add(Payment(order_id="a", tx_signature="same", verified_slot=1))
    db.commit()
    db.add(Payment(order_id="b", tx_signature="same", verified_slot=1))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_grant_requires_payment(db):
    db.add(order("a"))
    db.commit()
    db.add(Entitlement(order_id="a"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_one_grant_per_order(db):
    db.add(order("a", status="paid"))
    db.commit()
    db.add(Payment(order_id="a", tx_signature="sig", verified_slot=1))
    db.commit()
    db.add(Entitlement(order_id="a"))
    db.commit()
    db.add(Entitlement(order_id="a"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


@pytest.mark.parametrize("changes", [{"amount_minor_units": 0}, {"status": "invalid"},
                                      {"config_version": -1}])
def test_order_constraints(db, changes):
    db.add(order("a", **changes))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
