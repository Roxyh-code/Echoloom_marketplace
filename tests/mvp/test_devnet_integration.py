"""Offline regression coverage for public Solana Devnet handoff and fail-closed signer pins."""
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from echoloom.payments import readiness, solana_rpc
from echoloom.payments.authorization import encode_base58

ROOT = Path(__file__).resolve().parents[2]
PROGRAM = "DDNC5iENR2hGuqYUWdng2Yru94YugtJLf37QEqutVH4J"
CONFIG = "9FcbxfJejy34TDxtQkNPp4R5LsB6q8gfx1dJb2S6PiAa"
MINT = "8APFzFSd3uFnYSojta6j198bTndRoWCfhx6YxXwu7h2V"
TREASURY = "2Y6iE7Fev4GzfmEtFXBrgy47T82ATxxib9ViRPiuzMC2"
SIGNER = "Dj1g1qvkbKtrVzzSuYqZ4zC7QRxEneU8jh5CYMo36Cxb"


def read_env(path):
    return dict(line.split("=", 1) for line in path.read_text().splitlines()
                if line and not line.startswith("#") and "=" in line)


def test_public_handoff_addresses_and_idl_schema():
    run = subprocess.run(
        [sys.executable, "scripts/check_devnet_handoff.py", "--offline"],
        cwd=ROOT, capture_output=True, text=True, timeout=30,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    status = json.loads(run.stdout)
    assert status["ok"] and status["mode"] == "offline"
    assert status["program_id"] == PROGRAM
    assert status["config_pda"] == CONFIG
    assert status["mint"] == MINT
    assert set(status["recipients"]) == {"creator_a", "creator_b", "treasury"}
    assert solana_rpc.DEVNET_GENESIS == "EtWTRABZaYq6iMfeYKouRu166VU2xqa1wcaWoxPkrZBG"

    deployed = json.loads((ROOT / "solana/idl/devnet/echoloom_marketplace.json").read_text())
    local = json.loads((ROOT / "solana/idl/echoloom_marketplace.json").read_text())
    assert deployed.pop("address") == PROGRAM
    assert local.pop("address") != PROGRAM
    assert deployed == local  # ABI must be identical even though the program IDs differ.
    errors = {e["name"] for e in deployed["errors"]}
    assert "MissingTreasuryPayout" in errors and "InvalidMintDecimals" in errors


def test_frontend_backend_public_env_pins_match():
    backend = read_env(ROOT / ".env.example")
    frontend = read_env(ROOT / "web/.env.example")
    pairs = [
        ("SOLANA_PROGRAM_ID", "NEXT_PUBLIC_ECHOOLOOM_PROGRAM_ID", PROGRAM),
        ("SOLANA_MINT", "NEXT_PUBLIC_ECHOOLOOM_TOKEN_MINT", MINT),
        ("SOLANA_CONFIG_PDA", "NEXT_PUBLIC_ECHOOLOOM_CONFIG_PDA", CONFIG),
        ("SOLANA_PLATFORM_WALLET", "NEXT_PUBLIC_ECHOOLOOM_TREASURY_WALLET", TREASURY),
        ("SOLANA_EXPECTED_SIGNER_PUBKEY", "NEXT_PUBLIC_ECHOOLOOM_PAYMENT_SIGNER", SIGNER),
        ("SOLANA_DEPLOYMENT_DOMAIN_HASH", "NEXT_PUBLIC_ECHOOLOOM_DOMAIN_HASH", frontend["NEXT_PUBLIC_ECHOOLOOM_DOMAIN_HASH"]),
    ]
    for b, f, expected in pairs:
        assert backend[b] == frontend[f] == expected
    assert backend["SOLANA_PAYMENTS_ENABLED"] == "false"
    assert backend["SOLANA_BACKEND_SIGNER_PATH"] == ""
    assert frontend["NEXT_PUBLIC_SOLANA_CLUSTER"] == "devnet"
    assert frontend["NEXT_PUBLIC_ECHOOLOOM_TOKEN_DECIMALS"] == "6"


def test_mismatched_private_signer_fails_before_rpc(monkeypatch):
    wrong_pubkey = encode_base58(bytes([2]) * 32)
    settings = SimpleNamespace(
        solana_payments_enabled=True, solana_program_id=PROGRAM, solana_mint=MINT,
        solana_platform_wallet=TREASURY, solana_config_pda=CONFIG,
        solana_deployment_domain_hash="7fd12cd1cd604a1789ce37dce563043aaea9f06c0e81f00d851c6cbce92d237a",
        solana_backend_signer_path="placeholder", solana_expected_signer_pubkey=SIGNER,
    )
    monkeypatch.setattr(readiness.AuthorizationSigner, "from_keypair_file",
                        lambda *_: SimpleNamespace(public_key=wrong_pubkey))
    monkeypatch.setattr(readiness, "load_config",
                        lambda *_: (_ for _ in ()).throw(AssertionError("Must not call RPC")))
    assert readiness.deployment_readiness(settings) == (False, "deployment_config_invalid")
