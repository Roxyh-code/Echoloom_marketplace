"""Validate the fixed Anchor PurchaseReceipt against an immutable order."""
from hashlib import sha256
from struct import pack, unpack_from

from solders.pubkey import Pubkey

from .authorization import decode_pubkey, order_reference_hash, product_hash

RECEIPT_DISCRIMINATOR = sha256(b"account:PurchaseReceipt").digest()[:8]


def expected_receipt(order):
    return Pubkey.find_program_address(
        [b"purchase_receipt", order_reference_hash(order.id)],
        Pubkey.from_string(order.program_id),
    )


def validate_receipt(raw: bytes, order, slot: int):
    address, bump = expected_receipt(order)
    if str(address) != order.receipt_pda:
        raise ValueError("Receipt PDA mismatch")
    if len(raw) != 287 or raw[:8] != RECEIPT_DISCRIMINATOR or raw[8:10] != bytes([1, bump]):
        raise ValueError("Invalid receipt discriminator, version or bump")
    payouts = sorted(order.payout_lines, key=lambda p: decode_pubkey(p["wallet"]))
    if not 1 <= len(payouts) <= 3:
        raise ValueError("Invalid payout count")
    entries = b"".join(
        decode_pubkey(p["wallet"]) + pack("<Q", p["amount_minor_units"]) for p in payouts
    ).ljust(120, b"\0")
    expected = b"".join((
        decode_pubkey(order.buyer_wallet), order_reference_hash(order.id),
        product_hash(order.product_id), decode_pubkey(order.mint),
        pack("<QB", order.amount_minor_units, len(payouts)), entries,
        pack("<I", order.config_version),
    ))
    if raw[10:271] != expected:
        raise ValueError("Receipt terms differ from signed order")
    created, receipt_slot = unpack_from("<qQ", raw, 271)
    if not 0 < created < order.expires_at_unix or receipt_slot != slot:
        raise ValueError("Receipt timestamp or slot mismatch")
