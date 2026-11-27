#!/usr/bin/env bash
set -euo pipefail
umask 077
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
for tool in git anchor solana solana-keygen solana-test-validator cargo-build-sbf node npm; do
  command -v "$tool" >/dev/null || { echo "Missing tool: $tool" >&2; exit 1; }
done
PYTHON="${ECHOLOOM_PYTHON:-$(command -v python3)}"
PYTHON="$( "$PYTHON" -c 'import sys; print(sys.executable)' )"
"$PYTHON" -c 'import echoloom.payments.verification, pytest'
"$PYTHON" -m pytest -q tests/mvp/test_payment_*.py
# Fresh scratch copy avoids changing tracked declare_id, Anchor.toml or IDL,
# and prevents accidentally reusing deployment keypairs.
SCRATCH="$(mktemp -d -t echoloom-localnet.XXXXXXXX)"
cleanup() { rm -rf -- "$SCRATCH"; }
trap cleanup EXIT
mkdir -p "$SCRATCH/solana" "$SCRATCH/scripts"
cp -a solana/Anchor.toml solana/Cargo.toml solana/Cargo.lock solana/package.json solana/package-lock.json solana/tsconfig.json "$SCRATCH/solana/"
for dir in programs tests fixtures idl scripts; do
  mkdir -p "$SCRATCH/solana/$dir"
  # Copy tracked files only; no generated target directories or private keys.
  while IFS= read -r -d '' path; do
    mkdir -p "$SCRATCH/$(dirname "$path")"
    cp -p "$path" "$SCRATCH/$path"
  done < <(git ls-files -z -- "solana/$dir")
done
cp scripts/localnet_payment_bridge.py "$SCRATCH/scripts/"
export ECHOLOOM_PYTHON="$PYTHON"
export ECHOLOOM_PYTHON_BRIDGE=1
cd "$SCRATCH/solana"
mkdir -p target/deploy
solana-keygen new --no-bip39-passphrase --silent -o target/deploy/echoloom_marketplace-keypair.json >/dev/null
anchor keys sync
bash scripts/test-localnet.sh
echo "Local payment suite completed successfully."
