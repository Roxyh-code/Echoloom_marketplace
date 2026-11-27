# Echoloom Marketplace Anchor program

This workspace contains the local-only Anchor program that authorizes generic SPL token purchases, pays the exact payout lines approved by the backend signer, and creates a permanent order receipt. It contains no catalog, login, scene, quota, entitlement, escrow, or refund logic.

## Toolchain and build

Use the installed Anchor CLI 1.1.2 and Solana CLI 3.x. Rust crates are pinned to Anchor `=1.1.2`, `anchor-spl =1.1.2`, and the resolved Solana 3.x API family. Do not run `solana config set` for this workspace.

Every build requires `ECHOOLOOM_BOOTSTRAP_AUTHORITY`, a base58 public key decoding to exactly 32 nonzero bytes. `build.rs` fails closed when the value is missing or malformed; it generates an immutable byte-array constant. The initializer accepts only that public key as a signer. The local test runner sets this from its dedicated test key; production must supply a separately reviewed authority.

For a local development build, run the helper from this `solana/` directory. It creates or reuses the ignored `.local/bootstrap-authority.json` keypair, exports only its public key for the build, and copies the newly generated IDL into `idl/` after a successful build:

```bash
./scripts/build-local.sh
export ECHOOLOOM_BOOTSTRAP_AUTHORITY="$(solana-keygen pubkey .local/bootstrap-authority.json)"
cargo fmt --all -- --check
cargo clippy --all-targets -- -D warnings
```

For a deliberately configured non-local build, supply the reviewed public key explicitly (the matching signer must be managed separately):

```bash
export ECHOOLOOM_BOOTSTRAP_AUTHORITY="<approved public key>"
anchor build
```

The local program ID must match the public key derived from `target/deploy/echoloom_marketplace-keypair.json`. On a fresh local workspace, if Anchor reports a mismatch after creating that keypair, run `anchor keys sync` once and rebuild. Keep `declare_id!`, `Anchor.toml`, the generated IDL address, and client configuration synchronized. The static authorization fixture in `fixtures/authorization-v1.json` is a deterministic serialization test vector; its sample `program_id` is intentionally independent of the active local program ID. A local program ID is not a deployment approval.

## Local validator tests

```bash
./scripts/test-localnet.sh
```

The script creates ignored keys in `.local/` with owner-only permissions, builds the Anchor program and refreshes `idl/echoloom_marketplace.json`, starts `solana-test-validator` bound to `127.0.0.1`, funds only local accounts, deploys the separate test-only CPI wrapper to that validator, and runs the TypeScript suite against the already-running validator without rebuilding. It installs the locked npm dependencies when the `ts-mocha` runner is missing, including when a partial `node_modules/` directory exists. It does not read the default Solana wallet, edit global Solana CLI configuration, or contact Devnet/Mainnet. `.local/`, the validator ledger, `target/`, and `node_modules/` are ignored.

The local payment mint is created by the suite with six decimals. It is a mock classic SPL Token mint; Token-2022 is rejected. No USDC mint or public cluster is configured.

The owner-supplied local validator result reports **26 passing TypeScript tests, 0 failing**, including the second block `purchase rejects invalid authorizations, accounts and payouts`. That block checks wrong or missing signers, non-adjacent or tampered Ed25519 instructions, expired or over-long authorization, paused marketplace, stale config version, wrong buyer or mint, unsorted/duplicate/buyer recipients, total mismatch, substituted recipient accounts, and a purchase accepted at a 1500-second lifetime. The suite also covers the shared authorization vector, prefunded bootstrap initialization, authority rotation and pause/resume, one-recipient payout, atomic rollback after a later payout fails, retry after unfreezing, and CPI rejection. The current Rust test run passed **4 tests and 0 failed**; this comprises the three explicit Rust `#[test]` functions plus Anchor's generated `test_id`. The TypeScript suite uses only the local validator; no Devnet/Mainnet deployment is configured.

The CI workflow defines the Solana checks, but no GitHub-hosted run has been independently verified for the current uncommitted worktree.

## TypeScript module mode

`package.json` intentionally does not set `"type": "module"`. With Node 24, `ts-mocha` ran the suite but Node emitted `MODULE_TYPELESS_PACKAGE_JSON` and reparsed the test file as ESM. The TypeScript test configuration emits CommonJS; package-wide ESM mode may change module interpretation, so keep the current setting unless compatibility is verified without changing that compiler configuration.

## Accounts and authorization

- `MarketplaceConfig` is the singleton PDA `[b"marketplace_config"]`; its serialized data is 231 bytes and its allocation is 239 bytes with discriminator.
- `PurchaseReceipt` is the permanent PDA `[b"purchase_receipt", order_reference_hash]`; its serialized data is 279 bytes and allocation is 287 bytes. There is no close instruction.
- Purchase terms are parsed from the immediately preceding Ed25519 precompile instruction. `purchase` has no instruction arguments, keeping the signed message the only source of payout data and keeping a valid transaction within Solana packet limits.
- The fixed signed authorization is exactly 462 bytes. The backend signer authorizes the economic terms; the buyer signs the transaction and funds direct `TransferChecked` CPIs.
- Payout lines are 1–3 unique, positive, raw-public-key-sorted owners. Their checked sum must equal gross amount. The program does not hardcode a business percentage or know whether FastAPI selected the right product, price, listing, creator, or wallet.
- Purchase has three explicit writable destination slots. Active slots must be classic-token ATAs for the signed owners. Inactive slots must equal the buyer source token account as a canonical unused sentinel. The source account is rejected as a destination for active payouts.
- PDA creation accepts only a system-owned, non-executable, zero-data target. It tops up rent, allocates exact space, and assigns with PDA seeds, so a rent-exempt prefund does not block initialization.
- Purchase is top-level only. The standalone wrapper exists under `tests/cpi_wrapper/` and is deployed only by the local test script.

See [`../docs/solana/FASTAPI_SOLANA_IMPLEMENTATION_HANDOFF.md`](../docs/solana/FASTAPI_SOLANA_IMPLEMENTATION_HANDOFF.md) for the full instruction, serialization, RPC verification, and future FastAPI contract.

## Design limits to know before integrating

- **Treasury is informational.** `platform_treasury_owner` is stored and can be updated, but `purchase` does not require the treasury to be a recipient. Recipients and amounts come only from the backend-signed authorization. Enforcing "treasury must receive a positive line" would be one extra check in `validate_payouts`; it is deliberately not added until the product owner confirms that the platform is paid in every purchase.
- **The buyer cannot be a recipient** (`BuyerCannotReceivePayout`, and the buyer's source account is rejected as an active destination), because inactive recipient slots use the buyer source account as the sentinel. A creator or the platform wallet therefore cannot buy a paid scene with the same wallet that appears in its payout lines. Use separate demo wallets for buying.
- **Transaction size is tight.** A legacy transaction with the Ed25519 instruction, `purchase` and three distinct recipients is about 1152 bytes (about 1204 with compute-budget instructions) against the 1232-byte limit. Creating one missing recipient ATA in the same legacy transaction already reaches about 1226 bytes; three missing ATAs reach about 1310. Create missing ATAs in a separate earlier transaction, or use a versioned transaction with an address lookup table.
- **Mint and domain are immutable.** The payment mint cannot be changed after `initialize_marketplace` and there is no close instruction, so a wrong mint requires a new program ID.

## Configuration and authority roles

Bootstrap Authority is a build-time constant and becomes the initial Config Authority. Pause Authority and Backend Authorization Signer must be distinct from one another and from the bootstrap key. Program Upgrade Authority is configured by the local validator deployment tooling and is not stored in MarketplaceConfig. Local test keypairs are never deployment keys.

The accepted mint, classic Token Program, and deployment domain hash are immutable after initialization. Treasury, signer, and authority changes use separate instructions and checked config-version increments. Pause and resume also increment the version, invalidating outstanding authorizations.

## Deployment boundary and pending decisions

Do not deploy this program. The exact production program ID, Bootstrap Authority, Upgrade Authority governance, network/genesis, payment mint, finality policy, product, price, payout policy, and signer custody remain owner decisions. The authorization lifetime cap is 1800 seconds and provisional: the program checks `expires_at - now <= cap` at execution time, so it must exceed the 15-minute (900 s) Quote window plus backend/cluster clock skew. The backend signer is trusted to choose commercial terms and exact payout splits; the program checks signatures, bounds, recipient account identity, and conservation only.

No FastAPI/Next.js integration is included. The existing 40 free generated sentences per non-demo Scene across all cast types remains unchanged until a separate paid product and entitlement policy are approved.

## Sharing the source

For source archives, exclude these path components at every depth:

```text
.git/ and **/.git/
.local/ and **/.local/
.anchor/ and **/.anchor/
target/ and **/target/
node_modules/ and **/node_modules/
.venv/, venv/, __pycache__/, .pytest_cache/, .next/
```

Also exclude `.env` and `.env.*` files except `.env.example`, local databases, logs, and private key material. Preserve public fixtures such as `fixtures/authorization-v1.json` and the generated public IDL. `.local/` contains private test keypairs and validator state; the scripts recreate it when absent. These keys are for disposable local testing only and must never be reused for Devnet or Mainnet.

From the repository root, create a ZIP from the current tracked and untracked non-ignored source files with:

```bash
python3 scripts/make-source-archive.py /tmp/Echoloom_marketplace-source.zip
```

The script refuses to overwrite an existing archive or create one inside the repository. It excludes the generated directories and local/private artifacts listed above while keeping `.env.example` and public fixtures.
