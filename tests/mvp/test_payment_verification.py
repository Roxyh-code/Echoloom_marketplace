import base64
from struct import pack
from types import SimpleNamespace
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from solders.signature import Signature

from echoloom.db import sessions
from echoloom.payments.authorization import (
    Authorization, Payout, encode_base58, decode_pubkey, order_reference_hash,
    product_hash, serialize_authorization, TOKEN_PROGRAM,
)
from echoloom.payments.models import PaymentOrder, Payment, Entitlement
from echoloom.payments.receipt import RECEIPT_DISCRIMINATOR, expected_receipt, validate_receipt
from echoloom.payments.signer import AuthorizationSigner
from echoloom.payments.schemas import VerifyRequest
from echoloom.payments import verification as v


def wallet(n):
    return encode_base58(bytes([n]) * 32)


@pytest.fixture
def evidence():
    order = PaymentOrder(
        id=str(uuid4()), scene_id="scene", account_id="owner", buyer_wallet=wallet(4),
        product_id="scene-unlock-40:scene", program_id=wallet(5), mint=wallet(6),
        config_pda=wallet(7), amount_minor_units=1000000,
        payout_lines=[{"wallet": wallet(1), "amount_minor_units": 900000},
                      {"wallet": wallet(2), "amount_minor_units": 100000}],
        config_version=1, expires_at_unix=1800000000,
    )
    address, bump = expected_receipt(order)
    order.receipt_pda = str(address)
    signer = AuthorizationSigner(Ed25519PrivateKey.generate())
    order.signer_pubkey = signer.public_key
    signed = serialize_authorization(Authorization(
        bytes([9])*32, order.program_id, order.config_pda, order.id,
        order.buyer_wallet, order.product_id, order.mint, 1000000,
        (Payout(wallet(1), 900000), Payout(wallet(2), 100000)),
        1, order.expires_at_unix, bytes([8])*32,
    ))
    sig = signer.sign(signed)
    order.authorization_message_b64 = base64.b64encode(signed).decode()
    order.authorization_signature_b64 = base64.b64encode(sig).decode()
    receipt = RECEIPT_DISCRIMINATOR + bytes([1, bump]) + (
        decode_pubkey(order.buyer_wallet) + order_reference_hash(order.id)
        + product_hash(order.product_id) + decode_pubkey(order.mint)
        + pack("<QB", 1000000, 2) + decode_pubkey(wallet(1)) + pack("<Q", 900000)
        + decode_pubkey(wallet(2)) + pack("<Q", 100000) + bytes(40)
        + pack("<IqQ", 1, 1799999900, 42)
    )
    signature = str(Signature.from_bytes(bytes([2])*64))
    source = wallet(11)
    destinations = [v.recipient_ata(p["wallet"], order.mint) for p in order.payout_lines]
    header = bytes([1,0]) + pack("<7H",48,65535,16,65535,112,462,65535)
    tx = {
        "slot":42, "transaction":{"signatures":[signature],"message":{
            "accountKeys":[{"pubkey":order.buyer_wallet,"signer":True}],
            "instructions":[
                {"programId":v.ED25519,"accounts":[],
                 "data":encode_base58(header+decode_pubkey(signer.public_key)+sig+signed)},
                {"programId":order.program_id,"data":encode_base58(v.PURCHASE),
                 "accounts":[order.buyer_wallet,order.config_pda,order.receipt_pda,
                             order.mint,source,*destinations,source,TOKEN_PROGRAM,
                             v.SYSTEM,v.INSTRUCTIONS,v.CLOCK]},
            ]}},
        "meta":{"err":None,"innerInstructions":[{"index":1,"instructions":[
            {"programId":TOKEN_PROGRAM,"parsed":{"type":"transferChecked","info":{
                "source":source,"destination":destination,"authority":order.buyer_wallet,
                "mint":order.mint,"tokenAmount":{"decimals":6,"amount":str(p["amount_minor_units"])}
            }}} for destination,p in zip(destinations,order.payout_lines)
        ]}]},
    }
    return order,receipt,signature,tx


def test_receipt_and_transaction(evidence):
    order,receipt,sig,tx=evidence
    validate_receipt(receipt,order,42)
    assert v.check_transaction(order,sig,tx)==42


@pytest.mark.parametrize("offset",[0,8,9,10,42,74,106,138,146,147,267,279])
def test_receipt_tamper(evidence,offset):
    order,receipt,_,_=evidence
    changed=bytearray(receipt)
    changed[offset]^=1
    with pytest.raises(ValueError):
        validate_receipt(bytes(changed),order,42)


def test_wrong_transfer(evidence):
    order,_,sig,tx=evidence
    tx["meta"]["innerInstructions"][0]["instructions"][0]["parsed"]["info"]["tokenAmount"]["amount"]="1"
    with pytest.raises(ValueError):
        v.check_transaction(order,sig,tx)


@pytest.mark.parametrize("confirmation,expected",[("processed","pending"),("confirmed","pending"),("finalized","paid")])
def test_finality(evidence,monkeypatch,confirmation,expected):
    order,receipt,sig,tx=evidence
    settings=SimpleNamespace(solana_rpc_url="test",solana_payment_commitment="finalized",
                             solana_program_id=order.program_id,solana_mint=order.mint)
    responses={
        "getGenesisHash":v.DEVNET_GENESIS,
        "getSignatureStatuses":{"value":[{"err":None,"confirmationStatus":confirmation,"slot":42}]},
        "getTransaction":tx,
        "getAccountInfo":{"value":{"owner":order.program_id,"executable":False,
                                   "data":[base64.b64encode(receipt).decode(),"base64"]}},
    }
    monkeypatch.setattr(v,"rpc_call",lambda url,method,params: responses[method])
    assert v.chain_evidence(settings,order,sig)[0]==expected


def test_atomic_idempotent_grant(setup,evidence,monkeypatch):
    _,_,_,settings,engine=setup
    order,_,sig,_=evidence
    settings.solana_payments_enabled=True
    monkeypatch.setattr(v,"chain_evidence",lambda *args: ("paid",None,42))
    with sessions(engine)() as db:
        db.add(order)
        db.commit()
        body=VerifyRequest(order_id=order.id,tx_signature=sig)
        first=v.verify_order(db,settings,"owner",body)
        second=v.verify_order(db,settings,"owner",body)
        assert first==second
        assert first["scene_allowance"]["limit"]==80
        assert db.query(Payment).count()==1
        assert db.query(Entitlement).count()==1
        other=VerifyRequest(order_id=order.id,tx_signature=str(Signature.from_bytes(bytes([3])*64)))
        assert v.verify_order(db,settings,"owner",other)["status"]=="rejected"


def test_rpc_error_is_retryable(evidence, monkeypatch):
    from echoloom.payments.solana_rpc import SolanaRPCError
    order, _, sig, _ = evidence
    settings = SimpleNamespace(solana_rpc_url="test", solana_payment_commitment="finalized",
        solana_program_id=order.program_id, solana_mint=order.mint)
    def unavailable(*args):
        raise SolanaRPCError("temporary RPC rejection")
    monkeypatch.setattr(v, "rpc_call", unavailable)
    assert v.chain_evidence(settings, order, sig) == ("pending", "rpc_unavailable", None)
