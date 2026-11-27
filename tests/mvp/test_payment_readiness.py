from types import SimpleNamespace
from hashlib import sha256

from echoloom.payments import readiness as r
from echoloom.payments.authorization import encode_base58


def wallet(n):
    return encode_base58(bytes([n])*32)


def test_disabled_no_rpc(monkeypatch):
    settings = SimpleNamespace(solana_payments_enabled=False)
    monkeypatch.setattr(r, "load_config", lambda *args: (_ for _ in ()).throw(AssertionError()))
    assert r.deployment_readiness(settings) == (False, "payments_disabled")


def test_invalid_config():
    settings = SimpleNamespace(solana_payments_enabled=True, solana_program_id="",
                               solana_mint="", solana_platform_wallet="")
    assert r.deployment_readiness(settings) == (False, "deployment_config_invalid")


def test_live_config_check(monkeypatch):
    settings = SimpleNamespace(solana_payments_enabled=True, solana_program_id=wallet(1),
        solana_mint=wallet(2), solana_platform_wallet=wallet(3), solana_config_pda="",
        solana_deployment_domain_hash=sha256(b"test").hexdigest(), solana_backend_signer_path="test")
    monkeypatch.setattr(r.AuthorizationSigner, "from_keypair_file", lambda path: object())
    monkeypatch.setattr(r, "load_config", lambda *args: (wallet(4), bytes(32), 1))
    assert r.deployment_readiness(settings) == (True, "ready")
    def fail(*args):
        raise ValueError("not deployed")
    monkeypatch.setattr(r, "load_config", fail)
    assert r.deployment_readiness(settings) == (False, "chain_config_unavailable")


def test_scene_eligibility(monkeypatch):
    settings = SimpleNamespace(solana_payments_enabled=True, solana_platform_wallet=wallet(3))
    scene = SimpleNamespace(owner_id="owner", document={"cast":[{},{}]})
    monkeypatch.setattr(r, "creator_wallet", lambda *args: wallet(1))
    monkeypatch.setattr(r, "verified_wallet", lambda *args: wallet(1))
    assert r.checkout_readiness(None, settings, scene) == (False, "buyer_is_recipient")
    monkeypatch.setattr(r, "verified_wallet", lambda *args: wallet(4))
    monkeypatch.setattr(r, "deployment_readiness", lambda *args: (True,"ready"))
    assert r.checkout_readiness(None, settings, scene) == (True,"ready")
    scene.document["demo"] = True
    assert r.checkout_readiness(None, settings, scene) == (False,"scene_ineligible")
