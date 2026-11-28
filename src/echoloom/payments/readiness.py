"""Fail-closed checkout preflight. Never signs a quote or grants an entitlement."""
import httpx
from fastapi import HTTPException

from .authorization import decode_pubkey
from .quote import creator_wallet
from .signer import AuthorizationSigner
from .solana_rpc import load_config, pda
from .wallet import verified_wallet


def deployment_readiness(settings):
    if not settings.solana_payments_enabled:
        return False, "payments_disabled"
    try:
        for key in (settings.solana_program_id, settings.solana_mint, settings.solana_platform_wallet):
            if not any(decode_pubkey(key)):
                raise ValueError("Invalid public key")
        if settings.solana_config_pda and settings.solana_config_pda != pda(settings.solana_program_id, b"marketplace_config"):
            raise ValueError("Invalid config PDA")
        domain = bytes.fromhex(settings.solana_deployment_domain_hash)
        if len(domain) != 32 or not any(domain):
            raise ValueError("Invalid domain")
        signer = AuthorizationSigner.from_keypair_file(settings.solana_backend_signer_path)
        expected = getattr(settings, "solana_expected_signer_pubkey", "")
        if expected and decode_pubkey(expected) != decode_pubkey(signer.public_key):
            raise ValueError("Signer keypair differs from the deployed authorization signer")
    except (ValueError, TypeError, OSError):
        return False, "deployment_config_invalid"
    try:
        load_config(settings, signer)
    except (ValueError, TypeError, OSError, KeyError, IndexError, httpx.HTTPError):
        return False, "chain_config_unavailable"
    return True, "ready"


def checkout_readiness(db, settings, scene):
    if not settings.solana_payments_enabled:
        return False, "payments_disabled"
    if not scene.owner_id or scene.document.get("demo") or len(scene.document.get("cast", [])) != 2:
        return False, "scene_ineligible"
    try:
        recipients = [creator_wallet(db, actor, scene.owner_id) for actor in scene.document["cast"]]
        for recipient in recipients:
            if not any(decode_pubkey(recipient)):
                raise ValueError("Invalid recipient")
    except (HTTPException, ValueError, TypeError):
        return False, "creator_payout_unavailable"
    buyer = verified_wallet(db, scene.owner_id)
    if buyer and buyer in [*recipients, settings.solana_platform_wallet]:
        return False, "buyer_is_recipient"
    return deployment_readiness(settings)
