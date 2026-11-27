import json
from dataclasses import replace
from pathlib import Path
from uuid import UUID

import pytest

from echoloom.payments.authorization import (
    Authorization,
    Payout,
    decode_pubkey,
    encode_base58,
    order_reference_hash,
    product_hash,
    serialize_authorization,
)


@pytest.fixture
def vector():
    return json.loads(
        (Path(__file__).parent / "fixtures" / "authorization-v1.json").read_text()
    )


@pytest.fixture
def authorization(vector):
    return Authorization(
        deployment_domain_hash=bytes.fromhex(vector["deployment_domain_hash_hex"]),
        program_id=vector["program_id"],
        config_pda=vector["config_pda"],
        order_id=UUID(hex=vector["order_uuid_hex"]),
        buyer=vector["buyer"],
        product_id=vector["product_identifier"],
        mint=vector["mint"],
        gross_amount=vector["gross_amount"],
        payouts=tuple(
            Payout(p["owner"], p["amount"])
            for p in vector["recipients"][:vector["recipient_count"]]
        ),
        config_version=vector["config_version"],
        expires_at_unix=vector["expires_at_unix"],
        nonce=bytes.fromhex(vector["nonce_hex"]),
    )


def test_rust_fixture(authorization, vector):
    message = serialize_authorization(authorization)
    assert len(message) == vector["serialized_message_length"] == 462
    assert message.hex() == vector["serialized_message_hex"]
    assert order_reference_hash(authorization.order_id).hex() == vector["order_reference_hash_hex"]
    assert product_hash(authorization.product_id).hex() == vector["product_hash_hex"]


def test_sort_by_raw_key(authorization):
    assert serialize_authorization(authorization) == serialize_authorization(
        replace(authorization, payouts=authorization.payouts[::-1])
    )


@pytest.mark.parametrize("change", [
    {"gross_amount": 1}, {"gross_amount": True}, {"gross_amount": 2**64},
    {"payouts": ()}, {"nonce": bytes(32)}, {"nonce": b"short"},
    {"config_version": -1}, {"expires_at_unix": 2**63},
    {"product_id": ""}, {"product_id": "é" * 65}, {"mint": "invalid"},
])
def test_invalid_fields(authorization, change):
    with pytest.raises(ValueError):
        serialize_authorization(replace(authorization, **change))


def test_invalid_recipients(authorization):
    first, second = authorization.payouts
    for payouts in (
        (first, first),
        (Payout(authorization.buyer, first.amount), second),
        (Payout(first.wallet, 0), Payout(second.wallet, authorization.gross_amount)),
    ):
        with pytest.raises(ValueError):
            serialize_authorization(replace(authorization, payouts=payouts))


@pytest.mark.parametrize("raw", [bytes(32), bytes(range(32)), bytes([255])*32])
def test_base58_round_trip(raw):
    assert decode_pubkey(encode_base58(raw)) == raw
