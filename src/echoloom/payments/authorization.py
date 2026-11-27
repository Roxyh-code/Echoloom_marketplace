"""Fixed-width Solana purchase authorization v1 (no network or key access)."""
from dataclasses import dataclass
from hashlib import sha256
from struct import pack
from uuid import UUID

ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
AUTHORIZATION_DOMAIN_HASH = sha256(b"echoloom:purchase-authorization:v1").digest()
MESSAGE_LENGTH = 462


def encode_base58(raw: bytes) -> str:
    number = int.from_bytes(raw, "big")
    result = ""
    while number:
        number, remainder = divmod(number, 58)
        result = ALPHABET[remainder] + result
    return "1" * (len(raw) - len(raw.lstrip(b"\0"))) + result


def decode_pubkey(value: str) -> bytes:
    if not isinstance(value, str) or not 32 <= len(value) <= 44:
        raise ValueError("Invalid public key length")
    number = 0
    for char in value:
        if char not in ALPHABET:
            raise ValueError("Invalid base58 public key")
        number = number * 58 + ALPHABET.index(char)
    raw = b"\0" * (len(value) - len(value.lstrip("1")))
    raw += number.to_bytes((number.bit_length() + 7) // 8, "big")
    if len(raw) != 32 or encode_base58(raw) != value:
        raise ValueError("Expected canonical 32-byte public key")
    return raw


def order_reference_hash(order_id: UUID | str) -> bytes:
    order = order_id if isinstance(order_id, UUID) else UUID(order_id)
    return sha256(b"echoloom:order-ref:v1" + order.bytes).digest()


def product_hash(identifier: str) -> bytes:
    raw = identifier.encode("utf-8")
    if not 1 <= len(raw) <= 128:
        raise ValueError("Product identifier must contain 1–128 UTF-8 bytes")
    return sha256(b"echoloom:product:v1" + pack("<H", len(raw)) + raw).digest()


def _uint(value: int, bits: int) -> int:
    if type(value) is not int or not 0 <= value < 2**bits:
        raise ValueError(f"Expected unsigned {bits}-bit integer")
    return value


def _nonzero32(value: bytes) -> bytes:
    if not isinstance(value, bytes) or len(value) != 32 or not any(value):
        raise ValueError("Expected nonzero 32-byte field")
    return value


@dataclass(frozen=True)
class Payout:
    wallet: str
    amount: int


@dataclass(frozen=True)
class Authorization:
    deployment_domain_hash: bytes
    program_id: str
    config_pda: str
    order_id: UUID
    buyer: str
    product_id: str
    mint: str
    gross_amount: int
    payouts: tuple[Payout, ...]
    config_version: int
    expires_at_unix: int
    nonce: bytes


def serialize_authorization(value: Authorization) -> bytes:
    """Validate and encode canonical payout entries; caller chooses commerce terms."""
    buyer = _nonzero32(decode_pubkey(value.buyer))
    gross = _uint(value.gross_amount, 64)
    if not gross or not 1 <= len(value.payouts) <= 3:
        raise ValueError("Expected positive gross and 1–3 recipients")
    entries = []
    seen = set()
    for payout in value.payouts:
        owner = _nonzero32(decode_pubkey(payout.wallet))
        amount = _uint(payout.amount, 64)
        if owner == buyer or owner in seen or amount == 0:
            raise ValueError("Invalid, duplicate or buyer payout recipient")
        seen.add(owner)
        entries.append((owner, amount))
    if sum(amount for _, amount in entries) != gross:
        raise ValueError("Payouts must sum to gross")
    entries.sort(key=lambda item: item[0])
    slots = b"".join(owner + pack("<Q", amount) for owner, amount in entries)
    slots += bytes(40 * (3 - len(entries)))
    expiry = value.expires_at_unix
    if type(expiry) is not int or not 0 < expiry < 2**63:
        raise ValueError("Expected positive i64 Unix expiry")
    result = b"".join((
        AUTHORIZATION_DOMAIN_HASH, b"\x01",
        _nonzero32(value.deployment_domain_hash),
        _nonzero32(decode_pubkey(value.program_id)),
        _nonzero32(decode_pubkey(value.config_pda)),
        order_reference_hash(value.order_id), buyer,
        product_hash(value.product_id),
        _nonzero32(decode_pubkey(value.mint)),
        decode_pubkey(TOKEN_PROGRAM),
        pack("<QB", gross, len(entries)), slots,
        pack("<Iq", _uint(value.config_version, 32), expiry),
        _nonzero32(value.nonce),
    ))
    if len(result) != MESSAGE_LENGTH:
        raise ValueError("Invalid authorization length")
    return result
