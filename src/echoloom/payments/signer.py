"""Load Solana CLI keypairs and sign fixed authorization messages."""
import json
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from .authorization import MESSAGE_LENGTH, decode_pubkey, encode_base58


class AuthorizationSigner:
    def __init__(self, key: Ed25519PrivateKey):
        self._key = key

    @classmethod
    def from_keypair_file(cls, path: str | Path):
        """Read a 64-byte Solana CLI JSON keypair; validate its public half."""
        try:
            values = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
            if (
                not isinstance(values, list)
                or len(values) != 64
                or any(type(v) is not int or not 0 <= v <= 255 for v in values)
            ):
                raise ValueError("Invalid keypair")
            raw = bytes(values)
            signer = cls(Ed25519PrivateKey.from_private_bytes(raw[:32]))
            if signer._key.public_key().public_bytes_raw() != raw[32:]:
                raise ValueError("Public key mismatch")
            return signer
        except (OSError, ValueError, TypeError):
            raise ValueError("Cannot load valid Solana signer keypair") from None

    @property
    def public_key(self) -> str:
        return encode_base58(self._key.public_key().public_bytes_raw())

    def sign(self, message: bytes) -> bytes:
        if not isinstance(message, bytes) or len(message) != MESSAGE_LENGTH:
            raise ValueError("Expected 462-byte authorization")
        return self._key.sign(message)


def verify_signature(public_key: str, message: bytes, signature: bytes) -> bool:
    if len(message) != MESSAGE_LENGTH or len(signature) != 64:
        return False
    try:
        Ed25519PublicKey.from_public_bytes(decode_pubkey(public_key)).verify(
            signature, message
        )
        return True
    except (InvalidSignature, ValueError):
        return False
