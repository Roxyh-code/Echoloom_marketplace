import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from echoloom.payments.signer import AuthorizationSigner, verify_signature


def test_signer_file_and_tampering(tmp_path):
    key = Ed25519PrivateKey.generate()
    raw = key.private_bytes_raw() + key.public_key().public_bytes_raw()
    path = tmp_path / "signer.json"
    path.write_text(json.dumps(list(raw)))
    signer = AuthorizationSigner.from_keypair_file(path)
    message = bytes([7]) * 462
    signature = signer.sign(message)
    assert len(signature) == 64
    assert verify_signature(signer.public_key, message, signature)
    assert not verify_signature(signer.public_key, b"\x00" + message[1:], signature)
    assert not verify_signature(signer.public_key, message, signature[:-1])
    with pytest.raises(ValueError):
        signer.sign(b"short")
    path.write_text(json.dumps(list(raw[:32] + bytes(32))))
    with pytest.raises(ValueError):
        AuthorizationSigner.from_keypair_file(path)


@pytest.mark.parametrize("contents", ["not json", "[]", "[true]", "{}"])
def test_malformed_keypair(tmp_path, contents):
    path = tmp_path / "invalid.json"
    path.write_text(contents)
    with pytest.raises(ValueError):
        AuthorizationSigner.from_keypair_file(path)
