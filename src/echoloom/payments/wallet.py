"""Account-scoped, domain-bound, single-use Ed25519 buyer-wallet challenges."""
import base64
import binascii
import secrets
import time
from datetime import UTC, datetime
from uuid import uuid4

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from fastapi import HTTPException
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from solders.pubkey import Pubkey

from ..db import now
from .authorization import decode_pubkey
from .models import BuyerWallet, WalletChallenge

TTL = 300
MAX_OUTSTANDING = 5


def require_owner(owner):
    if not owner:
        raise HTTPException(401, "Sign in before connecting a wallet")


def verified_wallet(db, owner):
    row = db.get(BuyerWallet, owner) if owner else None
    return row.wallet if row else None


def create_challenge(db, settings, owner, wallet):
    require_owner(owner)
    try:
        raw = decode_pubkey(wallet)
        if not any(raw) or not Pubkey.from_bytes(raw).is_on_curve():
            raise ValueError("Expected wallet public key")
    except ValueError:
        raise HTTPException(422, "Invalid wallet address") from None
    clock = int(time.time())
    db.execute(delete(WalletChallenge).where(
        WalletChallenge.account_id == owner, WalletChallenge.expires_at_unix <= clock,
    ))
    count = db.scalar(select(func.count()).select_from(WalletChallenge).where(
        WalletChallenge.account_id == owner,
        WalletChallenge.consumed_at.is_(None),
        WalletChallenge.expires_at_unix > clock,
    ))
    if count >= MAX_OUTSTANDING:
        db.rollback()
        raise HTTPException(429, "Too many outstanding wallet challenges")
    identifier = str(uuid4())
    expiry = clock + TTL
    expiry_text = datetime.fromtimestamp(expiry, UTC).isoformat()
    message = (
        "Echoloom wallet verification v1\n"
        f"Origin: {settings.app_origin.rstrip('/')}\n"
        "Network: solana:devnet\n"
        "Purpose: Bind buyer wallet to this Echoloom account; no payment is authorized.\n"
        f"Account: {owner}\nWallet: {wallet}\nChallenge: {identifier}\n"
        f"Nonce: {secrets.token_hex(32)}\nExpires: {expiry_text}"
    )
    db.add(WalletChallenge(id=identifier, account_id=owner, wallet=wallet,
                           message=message, expires_at_unix=expiry))
    db.commit()
    return {"challenge_id": identifier, "message": message, "expires_at": expiry_text}


def verify_challenge(db, settings, owner, body):
    require_owner(owner)
    row = db.get(WalletChallenge, str(body.challenge_id))
    if not row or row.account_id != owner:
        raise HTTPException(404, "Wallet challenge not found")
    clock = int(time.time())
    if row.consumed_at or row.expires_at_unix <= clock:
        raise HTTPException(409, "Wallet challenge expired or already used")
    if row.message.splitlines()[1] != f"Origin: {settings.app_origin.rstrip('/')}":
        raise HTTPException(409, "Wallet challenge origin changed")
    try:
        sig = base64.b64decode(body.signature_b64, validate=True)
        if len(sig) != 64:
            raise ValueError("Invalid signature length")
        Ed25519PublicKey.from_public_bytes(decode_pubkey(row.wallet)).verify(
            sig, row.message.encode("utf-8")
        )
    except (InvalidSignature, ValueError, binascii.Error):
        raise HTTPException(403, "Wallet signature verification failed") from None
    wallet = row.wallet
    # Conditional update is the replay barrier, including concurrent requests.
    consumed = db.execute(update(WalletChallenge).where(
        WalletChallenge.id == row.id, WalletChallenge.account_id == owner,
        WalletChallenge.consumed_at.is_(None),
        WalletChallenge.expires_at_unix > int(time.time()),
    ).values(consumed_at=now()))
    if consumed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Wallet challenge expired or already used")
    try:
        binding = db.get(BuyerWallet, owner)
        if binding:
            binding.wallet = wallet
            binding.verified_at = now()
        else:
            db.add(BuyerWallet(account_id=owner, wallet=wallet))
        # Invalidate older challenges for this account, preventing stale rebinding.
        db.execute(update(WalletChallenge).where(
            WalletChallenge.account_id == owner,
            WalletChallenge.consumed_at.is_(None),
        ).values(consumed_at=now()))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Wallet is already bound to another account") from None
    return {"wallet": wallet, "verified": True}
