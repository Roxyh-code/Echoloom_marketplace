# FastAPI to Solana implementation handoff

This is the integration contract for the FastAPI payments backend. The backend now implements server-verified wallet binding, quotes, typed transaction preparation plans, order verification, reconciliation, and paid sentence entitlements. The browser wallet UI remains a later phase. Payments remain disabled unless the Devnet settings and signer are configured; this is not a deployment statement.

## Program and PDA addresses

- Checked-in local program ID: `2GKAJH8MWn8qZXB966AGDmbmZztKy5wjRVzLpPuQLjeu`. A fresh local `anchor keys sync` may generate a different ID per machine; keep `declare_id!`, `Anchor.toml`, IDL, and local client settings synchronized. This is not a deployment ID.
- Generated IDL: [`../../solana/idl/echoloom_marketplace.json`](../../solana/idl/echoloom_marketplace.json). This address is local-only and is not a production deployment approval.
- Config PDA: `find_program_address([utf8("marketplace_config")], program_id)`.
- Receipt PDA: `find_program_address([utf8("purchase_receipt"), order_reference_hash_32_bytes], program_id)`.
- Use the canonical bump returned by Solana PDA derivation; never choose a bump manually.

## Implemented Anchor instructions

All account orders below are the generated IDL order.

| Instruction | Arguments | Accounts in order |
| --- | --- | --- |
| `initialize_marketplace` | `args: { platform_treasury_owner: Pubkey, authorization_signer: Pubkey, pause_authority: Pubkey, deployment_domain_hash: [u8;32] }` | `bootstrap_authority` signer/writable, `config` writable PDA, `payment_mint`, `token_program`, `system_program` |
| `update_marketplace_config` | `new_treasury: Pubkey` | `config_authority` signer, `config` writable PDA |
| `rotate_authorized_signer` | `new_signer: Pubkey` | `config_authority` signer, `new_signer` signer, `config` writable PDA |
| `rotate_config_authority` | `new_authority: Pubkey` | `current_authority` signer, `new_authority` signer, `config` writable PDA |
| `rotate_pause_authority` | `new_authority: Pubkey` | `config_authority` signer, `new_authority` signer, `config` writable PDA |
| `pause_marketplace` | none | `pause_authority` signer, `config` writable PDA, `clock` |
| `resume_marketplace` | none | `config_authority` signer, `config` writable PDA, `clock` |
| `purchase` | **none** | `buyer` signer/writable, `config`, `receipt` writable, `payment_mint`, `buyer_source` writable, `recipient_0` writable, `recipient_1` writable, `recipient_2` writable, `token_program`, `system_program`, `instructions_sysvar`, `clock` |

Rotation instructions require both the existing authority and the new key to sign. The treasury update requires the existing Config Authority. Payment mint, classic token program, and deployment domain cannot be changed by an instruction.

`purchase` has no arguments intentionally. It reads all authorized economic terms from the previous Ed25519 instruction; this avoids duplicating the 462-byte message in transaction data and avoids accepting frontend-supplied terms independently.

For `purchase`, the three destination slots are always present. Active slots are the signed recipients' canonical classic-token ATAs. Each inactive slot must equal `buyer_source`, a writable canonical unused sentinel. The FastAPI transaction builder must follow the generated IDL and this sentinel rule.

## Authorization bytes

The Backend Authorization Signer signs a fixed 462-byte message. Use explicit byte concatenation, raw public-key/hash bytes, and little-endian integers. No JSON, Borsh struct encoding, floats, or native-memory serialization is used.

| Offset | Size | Field | Encoding |
| ---: | ---: | --- | --- |
| 0 | 32 | authorization domain hash | SHA256(`echoloom:purchase-authorization:v1`) |
| 32 | 1 | schema version | `1` |
| 33 | 32 | deployment domain hash | raw configured bytes |
| 65 | 32 | program ID | raw Pubkey bytes |
| 97 | 32 | config PDA | raw Pubkey bytes |
| 129 | 32 | order reference hash | raw hash bytes |
| 161 | 32 | buyer | raw Pubkey bytes |
| 193 | 32 | product hash | raw hash bytes |
| 225 | 32 | mint | raw Pubkey bytes |
| 257 | 32 | token program | raw Pubkey bytes |
| 289 | 8 | gross amount | `u64` little-endian token minor units |
| 297 | 1 | recipient count | 1–3 |
| 298 | 120 | recipient entries | three `(Pubkey[32], u64 LE)` entries |
| 418 | 4 | config version | `u32` little-endian |
| 422 | 8 | expiry | `i64` little-endian Unix seconds |
| 430 | 32 | nonce | random nonzero bytes |

Entries are sorted by raw Pubkey bytes, unique, positive, and sum exactly to gross. Unused entries are `(default Pubkey, 0)`. The current Rust and TypeScript vector is in [`../../solana/fixtures/authorization-v1.json`](../../solana/fixtures/authorization-v1.json); serialized length is 462 bytes.

Hash contracts:

- Order reference: `SHA256(ASCII "echoloom:order-ref:v1" || 16 raw UUID bytes)`. Generate and persist a random UUIDv4 before creating the quote. Do not hash UUID text or pass the UUID string to chain.
- Product: `SHA256(ASCII "echoloom:product:v1" || u16_le(UTF8 byte length) || UTF8 product identifier)`. The identifier is opaque and 1–128 UTF-8 bytes.
- Authorization domain: `SHA256(ASCII "echoloom:purchase-authorization:v1")`.

The program checks this message's schema/domain, program, config, buyer, mint, token program, config version, expiry, nonce, payout bounds, and amount conservation. It does not independently know the product price, listing owner/revision, creator eligibility, quote correctness, or business split. The Backend Authorization Signer is trusted to sign correct commerce terms and payout lines.

## Ed25519 instruction construction

Use the official Solana SDK Ed25519 builder. The transaction order is optional compute budget/ATA setup, exactly one Ed25519 verify instruction, then `purchase` immediately after it. No instruction may appear between verification and purchase.

For the SDK builder used with the pinned Solana family, the instruction data is exactly `16 + 32 + 64 + 462` bytes:

- 16-byte header, one signature, zero padding.
- Public key offset 16; signature offset 48; message offset 112.
- All three referenced instruction indices are `u16::MAX` (self/current Ed25519 instruction).
- No accounts, no cross-instruction references, no trailing bytes.
- Public key bytes equal the configured Backend Authorization Signer.

The precompile performs cryptographic verification. The Anchor program checks the precompile ID, adjacency, stack height 1, one-signature header, offsets, signer, and exact message length. Calls via CPI fail before payment execution.

## Keys, token accounts, and transaction flow

1. FastAPI binds the buyer wallet only after a one-time domain-bound wallet challenge is signed and verified. Creator payout wallets use a separate signed verification flow.
2. Create an immutable quote/order and payout snapshot. Keep exact amount, mint, decimals, recipients, order UUID, expiry, config version, authorization signer key version, and signed-message hash.
3. Derive product/order hashes and the Config/Receipt PDAs. Verify the RPC endpoint genesis/cluster against configured deployment metadata before preparing a transaction.
4. Use classic SPL Token only: `TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA`. This Phase C Devnet configuration requires six decimals and checks the configured mint's live decimals before quoting and preparing. Create missing ATAs idempotently in a separate setup transaction before the Ed25519 instruction.
5. The backend uses a small typed adapter over the existing `httpx` JSON-RPC dependency and returns a typed instruction plan; it does not add a Python Solana SDK dependency. The wallet client serializes and signs the transaction. Add the Ed25519 instruction, then `purchase` with buyer source and fixed recipient slots. The Buyer pays receipt rent and authorizes token spending; there is no vault or custody.
6. Submit and retain the signature/order association. A failed transaction may still charge SOL fees but must not charge token payouts or create the receipt.
7. The configured default is `finalized`: keep the order pending until finalized transaction and receipt verification complete. `confirmed` is an explicit lower-finality settings override with reorganization risk. Do not grant access based only on a wallet return value or client status.

## Expiry, size and recipient limits (added 2026-11-26)

- Authorization expiry must satisfy `now < expires_at <= now + 1800` on the cluster clock at execution time. Sign `expires_at` equal to the Quote expiry (15 minutes) and keep the backend clock synchronized; the cap was raised from 900 so a 900-second Quote no longer sits exactly on the limit.
- The buyer must not appear in the payout lines. The platform treasury in `MarketplaceConfig` is not enforced by `purchase`; the backend must include the platform line itself.
- Size estimates for a legacy transaction (buyer as only signer): about 1152 bytes with three distinct recipients and existing ATAs, about 1204 with compute-budget instructions, about 1226 with one ATA created in the same transaction and about 1310 with three. The limit is 1232. Create missing recipient ATAs in a separate earlier transaction, or use a versioned transaction with an address lookup table.

## Receipt parsing and RPC verification

Receipt allocation is 287 bytes. The Borsh data offsets below exclude no bytes; the first 8 bytes are the Anchor discriminator `SHA256("account:PurchaseReceipt")[0..8]`:

| Offset | Size | Field |
| ---: | ---: | --- |
| 0 | 8 | Anchor discriminator |
| 8 | 1 | receipt version |
| 9 | 1 | canonical PDA bump |
| 10 | 32 | buyer |
| 42 | 32 | order reference hash |
| 74 | 32 | product hash |
| 106 | 32 | mint |
| 138 | 8 | gross amount (`u64 LE`) |
| 146 | 1 | recipient count |
| 147 | 120 | three fixed payout entries |
| 267 | 4 | config version (`u32 LE`) |
| 271 | 8 | creation Unix timestamp (`i64 LE`) |
| 279 | 8 | creation slot (`u64 LE`) |

The current Anchor IDL exposes the receipt address as an unchecked account because it must accept safe system-owned prefunding before first initialization. Receipt parsing therefore uses this reviewed fixed Borsh contract and the Rust `PurchaseReceipt` definition, not an IDL account decoder. Verify:

- RPC genesis/cluster and expected program ID.
- Successful transaction status and selected finality.
- Transaction payer/buyer and exact program instruction ordering.
- Every classic SPL token transfer: mint, source authority, destination ATA, owner, and amount; sum equals gross.
- Receipt owner equals the Echoloom program, discriminator/version/bump are valid, PDA recomputes from the order hash, and every stored field equals the immutable order snapshot.
- A failed transaction has no receipt and no net token movement. A DB uniqueness constraint prevents duplicate order/signature grants.

The receipt is permanent and public. It includes no names, emails, scene content, or app account IDs.

## Failure cases

Expect rejection for wrong bootstrap/admin/pause signer; malformed or wrong Ed25519 instruction; cross-instruction offsets; CPI purchase; pause or stale config version; wrong program/config/buyer/mint/token program; expired/overlong authorization; zero/invalid nonce/hash; bad receipt PDA or replay; wrong source authority/mint; noncanonical or frozen/missing recipient ATA; unsupported Token-2022; unsorted/duplicate/self recipient; zero payout; total mismatch/overflow; insufficient buyer balance; and any failed `TransferChecked` CPI.

## Implemented FastAPI responsibilities

- Wallet challenge creation, nonce expiry/single-use checks, Buyer Wallet Binding, and separate Creator Payout Wallet Verification.
- Explicit creator monetization eligibility. New immutable `ListingRevision` snapshots must contain verified payout wallets; never rewrite historical revisions.
- Payment Quotes/Orders, immutable listing/revision/payout snapshots, idempotency, backend authorization signing/key custody and rotation, order status, rate limits, and audit trails.
- Independent RPC/genesis, transaction error, payer, mint, exact transfer, receipt, finality, and replay verification.
- Idempotent Payment-to-Entitlement mapping, chain-success/database-failure recovery, and reconciliation.
- Scene Access grants exactly 40 cumulative additional sentences per verified paid order, preserving the existing 40 generated-sentence free allowance for every non-demo Scene and the demo-scene exemption. Quote expiry does not expire an earned grant.

## Required integration tests

Reuse the JSON authorization vector and add Python-to-Rust byte-for-byte tests; tests for wallet challenge replay, authorization expiry/rotation, all payout counts and aggregation, duplicate DB processing, finalized/pending/failed RPC status, wrong transfer/receipt fields, replayed signatures, concurrent verification, and chain-finalized/database-failed recovery. Never test with real user funds or public clusters as part of this integration phase.
