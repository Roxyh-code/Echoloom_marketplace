"""Verify exact successful Devnet purchase and grant one entitlement atomically."""
import base64
from hashlib import sha256
from struct import pack

import httpx
from fastapi import HTTPException
from solders.pubkey import Pubkey
from solders.signature import Signature
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..db import RehearsalScene
from ..scene_access import generated
from .authorization import ALPHABET, TOKEN_PROGRAM, decode_pubkey
from .models import Entitlement, Payment, PaymentOrder
from .orders import paid_sentence_allowance
from .receipt import expected_receipt, validate_receipt
from .signer import verify_signature
from .solana_rpc import DEVNET_GENESIS, SolanaRPCError, pda, rpc_call

ED25519 = "Ed25519SigVerify111111111111111111111111111"
ATA = "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"
SYSTEM = "11111111111111111111111111111111"
INSTRUCTIONS = "Sysvar1nstructions1111111111111111111111111"
CLOCK = "SysvarC1ock11111111111111111111111111111111"
PURCHASE = sha256(b"global:purchase").digest()[:8]


def decode_data(value):
    if not isinstance(value, str) or len(value) > 4096:
        raise ValueError("Invalid instruction data")
    n = 0
    for char in value:
        n = n * 58 + ALPHABET.index(char)
    return bytes(len(value) - len(value.lstrip("1"))) + n.to_bytes((n.bit_length()+7)//8, "big")


def recipient_ata(wallet, mint):
    return pda(ATA, decode_pubkey(wallet), decode_pubkey(TOKEN_PROGRAM), decode_pubkey(mint))


def check_transaction(order, signature, tx):
    """Verify legacy/v0 jsonParsed instructions and scoped inner SPL transfers."""
    meta = tx["meta"]
    if meta is None or meta["err"] is not None:
        raise ValueError("Transaction failed")
    envelope = tx["transaction"]
    message = envelope["message"]
    keys = message["accountKeys"]
    if not keys or keys[0]["pubkey"] != order.buyer_wallet or not keys[0]["signer"]:
        raise ValueError("Unexpected fee payer")
    if envelope["signatures"][0] != signature:
        raise ValueError("Transaction signature mismatch")
    instructions = message["instructions"]
    matches = [i for i, ix in enumerate(instructions) if ix["programId"] == order.program_id]
    if len(matches) != 1 or matches[0] == 0:
        raise ValueError("Expected one top-level purchase")
    index = matches[0]
    purchase, ed = instructions[index], instructions[index - 1]
    if decode_data(purchase["data"]) != PURCHASE or ed["programId"] != ED25519 or ed["accounts"]:
        raise ValueError("Invalid purchase instruction ordering")
    if sum(ix["programId"] == ED25519 for ix in instructions) != 1:
        raise ValueError("Unexpected extra authorization")
    signed = base64.b64decode(order.authorization_message_b64, validate=True)
    sig = base64.b64decode(order.authorization_signature_b64, validate=True)
    if not verify_signature(order.signer_pubkey, signed, sig):
        raise ValueError("Invalid stored authorization")
    header = bytes([1, 0]) + pack("<7H", 48, 65535, 16, 65535, 112, 462, 65535)
    if decode_data(ed["data"]) != header + decode_pubkey(order.signer_pubkey) + sig + signed:
        raise ValueError("Authorization bytes mismatch")
    accounts = purchase["accounts"]
    if len(accounts) != 12:
        raise ValueError("Invalid purchase account count")
    source = accounts[4]
    payouts = sorted(order.payout_lines, key=lambda p: decode_pubkey(p["wallet"]))
    destinations = [recipient_ata(p["wallet"], order.mint) for p in payouts]
    expected = [order.buyer_wallet, order.config_pda, order.receipt_pda, order.mint, source,
                *destinations, *([source] * (3 - len(destinations))),
                TOKEN_PROGRAM, SYSTEM, INSTRUCTIONS, CLOCK]
    if accounts != expected or source in destinations:
        raise ValueError("Purchase accounts mismatch")
    groups = [g for g in (meta.get("innerInstructions") or []) if g["index"] == index]
    if len(groups) != 1:
        raise ValueError("Missing purchase inner instructions")
    transfers = [ix for ix in groups[0]["instructions"] if ix["programId"] == TOKEN_PROGRAM]
    if len(transfers) != len(payouts):
        raise ValueError("Wrong number of token transfers")
    for ix, line, destination in zip(transfers, payouts, destinations):
        parsed = ix["parsed"]
        info = parsed["info"]
        if (parsed["type"] != "transferChecked" or info["source"] != source
                or info["destination"] != destination or info["authority"] != order.buyer_wallet
                or info["mint"] != order.mint or info["tokenAmount"]["decimals"] != 6
                or int(info["tokenAmount"]["amount"]) != line["amount_minor_units"]):
            raise ValueError("Token transfer mismatch")
    if sum(p["amount_minor_units"] for p in payouts) != order.amount_minor_units:
        raise ValueError("Gross amount mismatch")
    return tx["slot"]


def chain_evidence(settings, order, signature):
    """Return (status, reason, slot); RPC failure never grants access."""
    url = settings.solana_rpc_url
    commitment = settings.solana_payment_commitment
    try:
        if rpc_call(url, "getGenesisHash", []) != DEVNET_GENESIS:
            return "pending", "deployment_unavailable", None
        if order.program_id != settings.solana_program_id or order.mint != settings.solana_mint:
            return "pending", "deployment_mismatch", None
        status = rpc_call(url, "getSignatureStatuses", [[signature], {"searchTransactionHistory": True}])["value"][0]
        if status is None:
            return "pending", "transaction_not_found", None
        if status["err"] is not None:
            return "rejected", "transaction_failed", None
        accepted = {"finalized"} if commitment == "finalized" else {"confirmed", "finalized"}
        if status["confirmationStatus"] not in accepted:
            return "pending", "awaiting_confirmation", None
        tx = rpc_call(url, "getTransaction", [signature, {
            "encoding": "jsonParsed", "commitment": commitment, "maxSupportedTransactionVersion": 0,
        }])
        if tx is None:
            return "pending", "transaction_not_available", None
        slot = check_transaction(order, signature, tx)
        if slot != status["slot"]:
            raise ValueError("Transaction slot mismatch")
        address, _ = expected_receipt(order)
        if str(address) != order.receipt_pda:
            raise ValueError("Receipt address mismatch")
        receipt = rpc_call(url, "getAccountInfo", [order.receipt_pda, {
            "encoding": "base64", "commitment": commitment, "minContextSlot": slot,
        }])["value"]
        if receipt is None:
            return "pending", "receipt_not_available", None
        if receipt["owner"] != order.program_id or receipt["executable"]:
            raise ValueError("Invalid receipt owner")
        validate_receipt(base64.b64decode(receipt["data"][0], validate=True), order, slot)
        return "paid", None, slot
    except (httpx.HTTPError, SolanaRPCError):
        return "pending", "rpc_unavailable", None
    except (ValueError, KeyError, TypeError, IndexError, OverflowError):
        # Malformed RPC/invalid evidence never unlocks; retries with valid evidence remain possible.
        return "rejected", "verification_failed", None


def result(db, order, status, reason=None):
    scene = db.get(RehearsalScene, order.scene_id)
    used = generated(scene.document) if scene and scene.owner_id == order.account_id else 0
    return {"status": status, "reason": reason, "scene_allowance": {
        "used": used, "limit": 40 + paid_sentence_allowance(db, order.scene_id, order.account_id),
    }}


def verify_order(db, settings, owner, body):
    if not owner:
        raise HTTPException(401, "Sign in before verifying payment")
    order = db.get(PaymentOrder, str(body.order_id))
    if not order or order.account_id != owner:
        raise HTTPException(404, "Order not found")
    try:
        signature = str(Signature.from_string(body.tx_signature))
        if signature != body.tx_signature:
            raise ValueError("Noncanonical signature")
    except ValueError:
        raise HTTPException(422, "Invalid transaction signature") from None
    existing = db.get(Payment, order.id)
    if existing:
        return result(db, order, "paid" if existing.tx_signature == signature else "rejected",
                      None if existing.tx_signature == signature else "order_already_paid")
    if not settings.solana_payments_enabled:
        raise HTTPException(503, "Wallet checkout is not enabled")
    if db.scalar(select(Payment.order_id).where(Payment.tx_signature == signature)):
        return result(db, order, "rejected", "signature_already_used")
    status, reason, slot = chain_evidence(settings, order, signature)
    if status != "paid":
        return result(db, order, status, reason)
    try:
        db.add(Payment(order_id=order.id, tx_signature=signature, verified_slot=slot))
        db.flush()
        db.add(Entitlement(order_id=order.id))
        order.status = "paid"
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.get(Payment, order.id)
        if existing and existing.tx_signature == signature:
            return result(db, order, "paid")
        return result(db, order, "rejected", "order_or_signature_already_used")
    return result(db, order, "paid")
