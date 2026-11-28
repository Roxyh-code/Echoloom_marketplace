# Devnet deployment readiness

Keep SOLANA_PAYMENTS_ENABLED=false until the shared deployment is initialized. Configure program ID, mint, config PDA, platform wallet, deployment domain hash, RPC URL, and a local private signer file (never commit it). The signer public key must match the initialized config. Use a classic six-decimal SPL mint. Default finality is finalized.

The authenticated scene-specific GET /api/payments/readiness/{scene_id} returns a safe reason code: payments_disabled, scene_ineligible, creator_payout_unavailable, buyer_is_recipient, deployment_config_invalid, chain_config_unavailable, ready. It never returns secret material. Exhausted scene access checks readiness and enables quote only when preflight passes. Quote independently checks chain state again. Wallet binding works even when payments are disabled. Creator monetization configuration is separate; do not rewrite historical listing revisions.

After deployment: configure and restart API, verify the signer and treasury, prepare eligible creators, fund the Devnet buyer, check readiness, obtain quote, confirm transaction, verify receipt, and check 40 additional sentences. No real funds.

## November 28, 2026: teammate Devnet public configuration

The public Program ID, Config PDA, ECHOTEST Mint, Treasury and signer **public key** are now supplied and staged in both `.env.example` and `web/.env.example`. The frontend validates public pins against the signed backend quote. Backend and frontend use the complete Devnet RPC genesis hash. The current teammate source adds strict six-decimal mint validation and a mandatory treasury payout. **No signer private key or actual purchase was provided**; default `SOLANA_PAYMENTS_ENABLED=false` is intentional.

Read [DEVNET_INTEGRATION.md](DEVNET_INTEGRATION.md) and run `python scripts/check_devnet_handoff.py --offline` then a read-only Devnet check before enabling any checkout. Do not treat public creator addresses as verified payout ownership; verify each wallet in the creator onboarding flow. Preserve Localnet tests in disposable scratch environments.
