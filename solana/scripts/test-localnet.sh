#!/usr/bin/env bash
set -euo pipefail

# Keep locally generated keypairs readable only by the current user.
umask 077

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOLANA_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
cd "${SOLANA_DIR}"

mkdir -p .local
chmod 700 .local
for name in bootstrap-authority test-payer test-buyer cpi-wrapper-keypair; do
  key_path=".local/${name}.json"
  if [[ ! -s "${key_path}" ]]; then
    solana-keygen new --no-bip39-passphrase --silent -o "${key_path}" >/dev/null
  fi
  chmod 600 "${key_path}"
done

export ECHOOLOOM_BOOTSTRAP_KEYPAIR_PATH="${SOLANA_DIR}/.local/bootstrap-authority.json"
export ECHOOLOOM_BOOTSTRAP_AUTHORITY="$(solana-keygen pubkey "${ECHOOLOOM_BOOTSTRAP_KEYPAIR_PATH}")"
export ANCHOR_PROVIDER_URL="http://127.0.0.1:8899"
export ANCHOR_WALLET="${SOLANA_DIR}/.local/test-payer.json"

if [[ "$(anchor --version)" != "anchor-cli 1.1.2" ]]; then
  echo "This workspace requires the installed Anchor CLI 1.1.2." >&2
  exit 1
fi
if [[ "$(solana --version)" != solana-cli\ 3.* ]]; then
  echo "This workspace requires the installed Solana 3.x CLI." >&2
  exit 1
fi

# A directory can exist while still being an incomplete extraction (for example,
# an archive containing only part of node_modules). Check the actual test runner.
if ! npm ls --depth=0 >/dev/null 2>&1; then
  npm ci
fi

echo "Building Anchor program with the local bootstrap authority..."
anchor build
IDL_SOURCE="${SOLANA_DIR}/target/idl/echoloom_marketplace.json"
IDL_DEST="${SOLANA_DIR}/idl/echoloom_marketplace.json"
if [[ ! -s "${IDL_SOURCE}" ]]; then
  echo "Anchor build did not produce ${IDL_SOURCE}." >&2
  exit 1
fi
install -m 644 "${IDL_SOURCE}" "${IDL_DEST}"

echo "Starting local Solana validator..."
solana-test-validator \
  --ledger .local/ledger \
  --reset \
  --quiet \
  --bind-address 127.0.0.1 \
  >.local/validator.log 2>&1 &
validator_pid=$!
cleanup() {
  kill "${validator_pid}" 2>/dev/null || true
  wait "${validator_pid}" 2>/dev/null || true
}
trap cleanup EXIT

ready=0
for _ in $(seq 1 60); do
  if solana cluster-version --url "${ANCHOR_PROVIDER_URL}" >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 1
done
if [[ "${ready}" != 1 ]]; then
  cat .local/validator.log >&2
  echo "Local validator did not become ready." >&2
  exit 1
fi

solana airdrop 100 --url "${ANCHOR_PROVIDER_URL}" --keypair "${ANCHOR_WALLET}" >/dev/null
solana airdrop 10 --url "${ANCHOR_PROVIDER_URL}" --keypair "${ECHOOLOOM_BOOTSTRAP_KEYPAIR_PATH}" >/dev/null

cargo-build-sbf \
  --manifest-path tests/cpi_wrapper/Cargo.toml \
  --sbf-out-dir target/deploy
solana program deploy \
  --program-id .local/cpi-wrapper-keypair.json \
  --url "${ANCHOR_PROVIDER_URL}" \
  --keypair "${ANCHOR_WALLET}" \
  target/deploy/echoloom_purchase_cpi_wrapper.so >/dev/null

anchor test \
  --provider.cluster Localnet \
  --provider.wallet "${ANCHOR_WALLET}" \
  --validator legacy \
  --skip-local-validator \
  --skip-build
