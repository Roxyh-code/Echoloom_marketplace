# Echoloom Marketplace: Solana Devnet handoff

**Status:** Public deployment parameters integrated on the `fix/devnet-payment-handoff-20261128` development branch; **payments remain disabled by default**. No live purchase, signature, balance transfer, Devnet receipt, or 40-to-80 entitlement has been asserted by this integration.

## Provenance and compatibility

- Public parameters were supplied by the Solana teammate and corroborated with the [teammate's contract repository](https://github.com/ibrahimMohamed124/echoloom-smart-contract). His `lib.rs` declares the Devnet program ID below.
- The local Anchor source now includes the deployed contract's **six-decimal mint requirement** and **mandatory treasury payout**. The checked-in `solana/idl/devnet/echoloom_marketplace.json` is made from that repository's published IDL schema with the supplied Devnet address. The teammate's original `target/idl/echoloom_marketplace.json` lives on his machine and was not accessible here; **deployed binary equivalence and original build artifact matching have not been independently proven**.
- Localnet testing is preserved via `bash scripts/run-local-payment-e2e.sh`. That wrapper uses disposable keys and `anchor keys sync` in scratch, not the real Devnet identities. Do not run local reset/identity scripts with real Devnet keypairs.

| Public deployment parameter | Value |
| --- | --- |
| Cluster | Solana Devnet |
| Program ID | `DDNC5iENR2hGuqYUWdng2Yru94YugtJLf37QEqutVH4J` |
| Config PDA | `9FcbxfJejy34TDxtQkNPp4R5LsB6q8gfx1dJb2S6PiAa` |
| ECHOTEST classic SPL mint | `8APFzFSd3uFnYSojta6j198bTndRoWCfhx6YxXwu7h2V` |
| Decimals | 6 |
| Token Program | `TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA` |
| Treasury wallet | `2Y6iE7Fev4GzfmEtFXBrgy47T82ATxxib9ViRPiuzMC2` |
| Treasury ATA | `JC6Q8SMGykzJAh9tAcmY8pD5xy8B91qksv1idyhU3HLv` |
| Authorized backend signer **public** key | `Dj1g1qvkbKtrVzzSuqY4zC7QRxEneU8jh5CYMo36Cxb` |
| Deployment domain hash | `7fd12cd1cd604a1789ce37dce563043aaea9f06c0e81f00d851c6cbce92d237a` |
| Creator A wallet / ATA | `FTkj7J5gVF7CPyk27CE3pbqXDS9KA5TegWC8Wm96aJVR` / `DPVWxWwhGUnqWRiDUtcq4CtupxRUngHsmyk1voFjhxxT` |
| Creator B wallet / ATA | `9gcWe7HEzjyJ6hZSuq7Ft7tK8EtVjjEMU6EujTrM38XF` / `2SH6N4KER92Vrh2ZNZV9n28StzM4r78shgjxMAjyNTTZ` |

The Config PDA and the three ATAs above have been locally derived from their seeds, wallet addresses, mint and associated-token program. **Their existence, balance and ownership on Devnet must still be checked against RPC.** Do not confuse public wallets with verified app accounts.

## 1. Copy configuration

Backend, from repository root:

```powershell
Copy-Item .env.example .env
# Edit .env: preserve existing private AI keys, database path and session settings.
# Public SOLANA_* deployment values are already populated in the example.
# Keep SOLANA_PAYMENTS_ENABLED=false until all checks and signer custody pass.
```

Frontend, from repository root:

```powershell
Copy-Item web/.env.example web/.env.local
# The Next.js server proxies /api/* to http://127.0.0.1:8000 unless
# API_BASE_URL is overridden (server-side only).
```

Frontend uses Wallet Standard (Phantom / supported Devnet wallet) with no private key. Payment instructions are built from the **backend-signed quote**, not untrusted creator wallet fields. Public `NEXT_PUBLIC_*` pins guard against building the frontend against a different program, config, mint, domain, signer or treasury. The backend validates live RPC config and refuses unverified orders. The Next.js frontend must be restarted after editing `web/.env.local`; rebuild for deployments.

## 2. Read-only check, **no secret keys**

```bash
python scripts/check_devnet_handoff.py --offline
python scripts/check_devnet_handoff.py
```

- Offline verifies canonical Config PDA and all three derived ATAs, and does not contact Solana.
- Live mode requires Devnet RPC. It checks full Devnet genesis hash, executable program, account discriminator/length/version, public authorization signer, mint, token program, treasury, domain hash, pause flag, mint decimals and all supplied recipient token accounts.
- These checks **do not certify bytecode provenance**, buyer funds, wallet ownership or completed payment. An RPC timeout is inconclusive, not proof that a deployment failed.
- Both frontend and backend now compare the **full** `getGenesisHash` result `EtWTRABZaYq6iMfeYKouRu166VU2xqa1wcaWoxPkrZBG` (not its shortened network identifier).

## 3. Backend signer custody remains necessary

The user-supplied `NEXT_PUBLIC_ECHOOLOOM_PAYMENT_SIGNER` is **a public key only**. It cannot sign payment authorizations.

- The backend needs `SOLANA_BACKEND_SIGNER_PATH` pointing to a securely stored 64-byte Solana CLI JSON keypair whose **public** key equals `Dj1g1qvkbKtrVzzSuqY4zC7QRxEneU8jh5CYMo36Cxb`. `SOLANA_EXPECTED_SIGNER_PUBKEY` pins this identity. It is checked against the on-chain config before quotes are issued.
- Do **not** request or post private key material, seed phrases or private JSON in chat, GitHub, `.env` or a frontend variable. If the existing signer is held only by the teammate, a safer path is to generate a new backend-controlled signing key in a protected environment and ask the Devnet **Config Authority** to execute the program's `rotate_authorized_signer` instruction. After on-chain confirmation, update the public signer pins and restart the backend. That administrative transaction is not done by this branch.
- Neither the platform's treasury wallet nor Creator A/B wallets should be stored as private keys by the app.

## 4. Prepare a genuine two-creator purchase

1. Create/choose two original, rights-cleared marketplace characters. Each creator account must complete the existing payout wallet challenge and sign verification with the wallet that controls the configured payout address. The public addresses supplied above cannot be automatically treated as verified.
2. Approve/enable the two creators as required; explicitly opt each listing into monetization. Create a **new** scene using those current public listing revisions. Historical scenes pin earlier revisions.
3. The buyer must use a **third**, distinct Devnet wallet, with sufficient ECHOTEST tokens (at least 1 per purchase) **and Devnet SOL** for transaction fees and any missing associated-token-account rent. A token mint address does not itself supply airdrop or mint authority. Coordinate test-token funding with the mint authority.
4. Only after public deployment checks, secure backend signer custody and eligible creators are satisfied, set `SOLANA_PAYMENTS_ENABLED=true` **in the backend only**, restart FastAPI, and check `GET /api/payments/readiness/{scene_id}`. If it does not report `ready`, **do not bypass the guard**.
5. Using Phantom (or another compatible Wallet Standard account), connect and verify buyer ownership, request a quote, confirm the actual transaction, and let the server verify it via `POST /api/payments/verify`. Any missing recipient ATAs are created in a **separate** setup transaction; only the buyer signs and broadcasts the purchase.
6. Confirm actual chain evidence: buyer -1.000000 ECHOTEST, Creator A +0.450000, Creator B +0.450000, treasury +0.100000, exactly one purchase receipt PDA, verified payment record, account/scene allowance **40 → 80**, updated creator earnings, and no second charge from repeated verification. Then repeat with a distinct order to test **80 → 120**.

For isolated demo accounts and a prepared scene, see [DEMO_ENVIRONMENT.md](DEMO_ENVIRONMENT.md). It does not fake wallet signatures, payments, or earnings. For local-validator tests, use [LOCAL_PAYMENT_INTEGRATION.md](LOCAL_PAYMENT_INTEGRATION.md).

## 5. Known limitations

This branch does not perform any real buyer wallet signature, token minting, Solana transaction, or privileged signer rotation. Live Devnet receipt/earnings acceptance is still to be run with authorized wallets. The deployed binary has not been independently compared against the Rust source or the teammate's locally generated build artifact. There is no automatic creator wallet verification from the public address list, and there should be no privileged backend signing key in a public repository.

Checkout remains opt-in and fails closed when its prerequisites are absent; the 40-sentence free allowance is unchanged.
