"""Read-only verification of the public Solana Devnet handoff.

No wallet, transaction signing, private key, or payment is used.
Run: python scripts/check_devnet_handoff.py --offline
Run: python scripts/check_devnet_handoff.py   # live Devnet RPC required
"""
import argparse
import json
from hashlib import sha256

from solders.pubkey import Pubkey

from echoloom.payments.authorization import TOKEN_PROGRAM, decode_pubkey
from echoloom.payments.solana_rpc import DEVNET_GENESIS, account, pda, rpc_call

RPC_URL = "https://api.devnet.solana.com"
PROGRAM = "DDNC5iENR2hGuqYUWdng2Yru94YugtJLf37QEqutVH4J"
CONFIG = "9FcbxfJejy34TDxtQkNPp4R5LsB6q8gfx1dJb2S6PiAa"
MINT = "8APFzFSd3uFnYSojta6j198bTndRoWCfhx6YxXwu7h2V"
TREASURY = "2Y6iE7Fev4GzfmEtFXBrgy47T82ATxxib9ViRPiuzMC2"
SIGNER = "Dj1g1qvkbKtrVzzSuqY4zC7QRxEneU8jh5CYMo36Cxb"
DOMAIN = "7fd12cd1cd604a1789ce37dce563043aaea9f06c0e81f00d851c6cbce92d237a"
ATA_PROGRAM = "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"
RECIPIENTS = {
    "treasury": (TREASURY, "JC6Q8SMGykzJAh9tAcmY8pD5xy8B91qksv1idyhU3HLv"),
    "creator_a": ("FTkj7J5gVF7CPyk27CE3pbqXDS9KA5TegWC8Wm96aJVR", "DPVWxWwhGUnqWRiDUtcq4CtupxRUngHsmyk1voFjhxxT"),
    "creator_b": ("9gcWe7HEzjyJ6hZSuq7Ft7tK8EtVjjEMU6EujTrM38XF", "2SH6N4KER92Vrh2ZNZV9n28StzM4r78shgjxMAjyNTTZ"),
}


def associated_token_address(owner: str) -> str:
    return str(Pubkey.find_program_address(
        [decode_pubkey(owner), decode_pubkey(TOKEN_PROGRAM), decode_pubkey(MINT)],
        Pubkey.from_string(ATA_PROGRAM),
    )[0])


def check_public_addresses() -> dict:
    assert pda(PROGRAM, b"marketplace_config") == CONFIG, "Incorrect marketplace config PDA"
    assert len(bytes.fromhex(DOMAIN)) == 32 and any(bytes.fromhex(DOMAIN))
    assert len(decode_pubkey(SIGNER)) == 32
    addresses = {}
    for role, (owner, supplied_ata) in RECIPIENTS.items():
        derived = associated_token_address(owner)
        assert derived == supplied_ata, f"{role}: associated token address mismatch"
        addresses[role] = {"owner": owner, "ata": derived}
    return {"program_id": PROGRAM, "config_pda": CONFIG, "mint": MINT,
            "token_decimals": 6, "authorization_signer": SIGNER, "recipients": addresses}


def check_live_deployment(url: str) -> dict:
    result = check_public_addresses()
    assert rpc_call(url, "getGenesisHash", []) == DEVNET_GENESIS, "RPC is not Solana Devnet"
    program = rpc_call(url, "getAccountInfo",
                       [PROGRAM, {"encoding": "base64", "commitment": "confirmed"}])["value"]
    assert program and program.get("executable"), "Configured program has not been deployed"
    raw = account(url, CONFIG, PROGRAM)
    assert len(raw) == 239, "Unexpected marketplace config account size"
    assert raw[:8] == sha256(b"account:MarketplaceConfig").digest()[:8], "Invalid account discriminator"
    assert raw[8] == 1, "Unsupported marketplace config version"
    assert raw[74:106] == decode_pubkey(SIGNER), "Deployed backend signer differs"
    assert raw[106:138] == decode_pubkey(MINT), "Deployed payment mint differs"
    assert raw[138:170] == decode_pubkey(TOKEN_PROGRAM), "Deployed token program differs"
    assert raw[170:202] == decode_pubkey(TREASURY), "Deployed platform treasury differs"
    assert raw[202:234] == bytes.fromhex(DOMAIN), "Deployment domain differs"
    assert raw[238] == 0, "Marketplace has been paused"
    mint = account(url, MINT, TOKEN_PROGRAM)
    assert len(mint) == 82 and mint[44] == 6 and mint[45] == 1, "Payment mint is not initialized, classic SPL, six decimals"
    result["config_version"] = int.from_bytes(raw[234:238], "little")
    assert result["config_version"] >= 1, "Config version must be positive"
    for role, (owner, ata) in RECIPIENTS.items():
        tokens = account(url, ata, TOKEN_PROGRAM)
        assert len(tokens) == 165, f"{role}: invalid SPL Token account size"
        assert tokens[:32] == decode_pubkey(MINT), f"{role}: token mint mismatch"
        assert tokens[32:64] == decode_pubkey(owner), f"{role}: token owner mismatch"
    result["rpc_url"] = url
    result["public_deployment_verified"] = True
    result["checkout_ready"] = False  # Cannot prove private signer custody, buyer balance or owner verification.
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="Check public PDA/ATA derivations without RPC")
    parser.add_argument("--rpc-url", default=RPC_URL, help="Solana Devnet JSON-RPC endpoint")
    args = parser.parse_args()
    try:
        result = check_public_addresses() if args.offline else check_live_deployment(args.rpc_url)
    except (AssertionError, ValueError, KeyError, IndexError, OSError, RuntimeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    except Exception as exc:
        # RPC timeout/connection failures are not evidence of a failed deployment.
        print(json.dumps({"ok": False, "error": type(exc).__name__ + ": " + str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps({"ok": True, "mode": "offline" if args.offline else "live", **result}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
