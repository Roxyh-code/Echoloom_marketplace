"""Devnet-only quote configuration checks and canonical PDA derivation."""
import base64
from hashlib import sha256

import httpx
from solders.pubkey import Pubkey

from .authorization import TOKEN_PROGRAM, decode_pubkey

DEVNET_GENESIS = "EtWTRABZaYq6iMfeYKouRu166VU2xqa1"


def pda(program_id: str, *seeds: bytes) -> str:
    return str(Pubkey.find_program_address(list(seeds), Pubkey.from_string(program_id))[0])


def rpc_call(url, method, params):
    response = httpx.post(
        url, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
        timeout=10,
    )
    response.raise_for_status()
    body = response.json()
    if "error" in body or "result" not in body:
        raise ValueError("Solana RPC returned an error")
    return body["result"]


def account(url, address, owner):
    result = rpc_call(url, "getAccountInfo", [
        address, {"encoding": "base64", "commitment": "confirmed"},
    ])["value"]
    if not result or result["owner"] != owner or result["executable"]:
        raise ValueError("Unexpected Solana account")
    return base64.b64decode(result["data"][0], validate=True)


def load_config(settings, signer):
    """Validate live configuration instead of signing against stale settings."""
    url = settings.solana_rpc_url
    program = settings.solana_program_id
    config = pda(program, b"marketplace_config")
    if settings.solana_config_pda and config != settings.solana_config_pda:
        raise ValueError("Config PDA mismatch")
    if rpc_call(url, "getGenesisHash", []) != DEVNET_GENESIS:
        raise ValueError("Only Solana Devnet is supported")
    deployed = rpc_call(url, "getAccountInfo", [
        program, {"encoding": "base64", "commitment": "confirmed"},
    ])["value"]
    if not deployed or not deployed["executable"]:
        raise ValueError("Marketplace program is not executable")
    raw = account(url, config, program)
    domain = bytes.fromhex(settings.solana_deployment_domain_hash)
    if len(domain) != 32 or not any(domain):
        raise ValueError("Invalid deployment domain")
    if (
        len(raw) != 239
        or raw[:8] != sha256(b"account:MarketplaceConfig").digest()[:8]
        or raw[8] != 1
        or raw[74:106] != decode_pubkey(signer.public_key)
        or raw[106:138] != decode_pubkey(settings.solana_mint)
        or raw[138:170] != decode_pubkey(TOKEN_PROGRAM)
        or raw[170:202] != decode_pubkey(settings.solana_platform_wallet)
        or raw[202:234] != domain
        or raw[238] != 0
    ):
        raise ValueError("Marketplace config does not match deployment settings")
    mint = account(url, settings.solana_mint, TOKEN_PROGRAM)
    if len(mint) != 82 or mint[44] != 6 or mint[45] != 1:
        raise ValueError("Expected initialized classic SPL mint with six decimals")
    return config, domain, int.from_bytes(raw[234:238], "little")
