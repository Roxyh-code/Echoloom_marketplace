#!/usr/bin/env bash
set -euo pipefail

# Build with a dedicated local-only bootstrap authority. Never use this key for
# production deployments.
umask 077

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOLANA_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
cd "${SOLANA_DIR}"

if ! command -v solana-keygen >/dev/null 2>&1; then
  echo "solana-keygen was not found on PATH. Install the Solana CLI first." >&2
  exit 1
fi
if ! command -v anchor >/dev/null 2>&1; then
  echo "anchor was not found on PATH. Install the required Anchor CLI first." >&2
  exit 1
fi

mkdir -p .local
chmod 700 .local
BOOTSTRAP_KEYPAIR="${SOLANA_DIR}/.local/bootstrap-authority.json"

if [[ ! -s "${BOOTSTRAP_KEYPAIR}" ]]; then
  solana-keygen new --no-bip39-passphrase --silent -o "${BOOTSTRAP_KEYPAIR}" >/dev/null
fi
chmod 600 "${BOOTSTRAP_KEYPAIR}"

if ! ECHOOLOOM_BOOTSTRAP_AUTHORITY="$(solana-keygen pubkey "${BOOTSTRAP_KEYPAIR}")"; then
  echo "Could not read the local bootstrap-authority keypair." >&2
  exit 1
fi
export ECHOOLOOM_BOOTSTRAP_AUTHORITY

anchor build "$@"

IDL_SOURCE="${SOLANA_DIR}/target/idl/echoloom_marketplace.json"
IDL_DEST="${SOLANA_DIR}/idl/echoloom_marketplace.json"
if [[ ! -s "${IDL_SOURCE}" ]]; then
  echo "Anchor build completed, but the generated IDL was not found at ${IDL_SOURCE}." >&2
  exit 1
fi
install -m 644 "${IDL_SOURCE}" "${IDL_DEST}"
echo "Updated ${IDL_DEST} from the successful Anchor build."
