# Marketplace integration contract (planning only)

**Status: to be agreed by both developers; no Solana or order implementation yet.**

## Roles

App/AI developer: safe public catalog, two-character casting, scene setup, quotes, orders, DB and server-side paid entitlements. Solana developer: wallet adapter, Devnet token transfer, atomic creator/platform split and transaction fixture data. Integration owned jointly.

## Frozen fields needed before implementation

- Listing: `listing_id`, `character_id`, `published_profile_version`, `creator_id`, `creator_wallet`, `display_portrait_url`, `license_scope`, `price_minor_units`.
- Scene draft: `scene_id`, exactly two listing IDs, their published version snapshots, buyer session, premise and optional mood/setting.
- Quote: `order_id`, `quote_id`, `scene_id`, `buyer_wallet`, `token_mint`, `expires_at`, `total_minor_units`, `payout_lines[{wallet, amount_minor_units}]`, unique `order_reference`.
- Verify result: `pending | paid | rejected`, verified signature and reason. Access: `buyer_wallet`, `scene_id`, `allowed_directions`, status.

For the demo, an example 1.00 test USDC scene splits as 0.45 / 0.45 / 0.10 (creators A/B/platform). These are **illustrative**, not validated economics. Backend freezes all amounts and recipient wallets; combine lines for duplicate creator wallets. Never trust the browser's price or a browser-provided `paid` flag. Authenticate buyer wallet with a server challenge and signature. Verify exact mint, payer, signature status, recipient totals and unique reference on chain before issuing the entitlement. One purchase should unlock one scene and at most five directed continuations.

## Milestones

- G0: standalone baseline and two demo characters.
- G1: shared JSON quote / order / receipt fixture accepted by both developers.
- G2: App exposes a real quote; Solana helper signs a Devnet payment.
- G3: server verifies payout and grants access exactly once.
- G4: end-to-end demo plus negative payment and access tests.

Do not let optional NFT minting, per-minute billing or resale royalties block G0–G4.
