"""Cross-language fixture and instruction ABI drift checks."""
import json
from pathlib import Path
from hashlib import sha256

ROOT = Path(__file__).resolve().parents[2]


def test_anchor_fixture_matches_python_fixture():
    rust = json.loads((ROOT / "solana/fixtures/authorization-v1.json").read_text())
    python = json.loads((ROOT / "tests/mvp/fixtures/authorization-v1.json").read_text())
    assert rust == python


def test_purchase_instruction_abi():
    idl = json.loads((ROOT / "solana/idl/echoloom_marketplace.json").read_text())
    purchase = next(i for i in idl["instructions"] if i["name"] == "purchase")
    assert purchase["args"] == []
    assert bytes(purchase["discriminator"]) == sha256(b"global:purchase").digest()[:8]
    assert [a["name"] for a in purchase["accounts"]] == [
        "buyer", "config", "receipt", "payment_mint", "buyer_source",
        "recipient_0", "recipient_1", "recipient_2", "token_program",
        "system_program", "instructions_sysvar", "clock",
    ]
