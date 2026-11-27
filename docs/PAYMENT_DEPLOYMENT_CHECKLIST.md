# Devnet deployment readiness

Keep SOLANA_PAYMENTS_ENABLED=false until the shared deployment is initialized. Configure program ID, mint, config PDA, platform wallet, deployment domain hash, RPC URL, and a local private signer file (never commit it). The signer public key must match the initialized config. Use a classic six-decimal SPL mint. Default finality is finalized.

The authenticated scene-specific GET /api/payments/readiness/{scene_id} returns a safe reason code: payments_disabled, scene_ineligible, creator_payout_unavailable, buyer_is_recipient, deployment_config_invalid, chain_config_unavailable, ready. It never returns secret material. Exhausted scene access checks readiness and enables quote only when preflight passes. Quote independently checks chain state again. Wallet binding works even when payments are disabled. Creator monetization configuration is separate; do not rewrite historical listing revisions.

After deployment: configure and restart API, verify the signer and treasury, prepare eligible creators, fund the Devnet buyer, check readiness, obtain quote, confirm transaction, verify receipt, and check 40 additional sentences. No real funds.
