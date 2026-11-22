# Marketplace integration contract (planning only)

**Status: to be agreed by both developers; no Solana or order implementation yet.**

## Roles

App/AI developer: safe public catalog, two-character casting, scene setup, quotes, orders, DB and server-side paid entitlements. Solana developer: wallet adapter, Devnet token transfer, atomic creator/platform split and transaction fixture data. Integration owned jointly.

## Frozen fields needed before implementation

- Listing: `listing_id`, `character_id`, `published_profile_version`, `creator_id`, `creator_wallet`, `display_portrait_url`, `license_scope`, `price_minor_units`.
- Scene draft: `scene_id`, exactly two listing IDs, their published version snapshots, buyer session, premise and optional mood/setting.
- Quote: `order_id`, `quote_id`, `scene_id`, `buyer_wallet`, `token_mint`, `expires_at`, `total_minor_units`, `payout_lines[{wallet, amount_minor_units}]`, unique `order_reference`.
- Verify result: `pending | paid | rejected`, verified signature and reason. Access: `buyer_wallet`, `scene_id`, `allowed_directions`, status.

## Product decision log (owner selections; **teammate approval pending**)

### Decision 1 — monetization: **C3 selected by product owner**

- **First-time trial:** the user's first scene is free, including its initial AI-generated opening and **one** user-directed continuation.
- **After free trial:** a Solana payment unlocks **five additional** user-directed continuations **on that same scene**. The demo payment price is not finalized; 1.00 test USDC is an illustrative figure only.
- **Free use incurs no creator payout transaction**; creator/platform revenue shares apply when a paid unlock occurs. Costs of the trial are borne by the application during the demo, not charged on-chain.
- **Server-side quota and entitlement are required:** frontend counters are not authoritative. Exact identity/anti-abuse binding and rules for subsequent new scenes will be agreed in later decisions; a wallet-only first-use counter is not robust against multiple-wallet farming.
- **Status:** selected by product owner on 2026-11-22; not yet reviewed or approved by Solana teammate. This decision **supersedes the previous paid-before-first-scene demo assumption**.

### Decision 2 — creator/platform revenue split: **pending product owner choice and teammate approval**

For illustration only, one paid unlock priced at 1.00 test USDC could split 0.45 / 0.45 / 0.10 (creator A / creator B / platform); these are **not agreed rates or validated economics**. The backend must freeze all amounts and recipients. Merge payout lines when both roles have the same creator wallet. Never trust a browser-supplied price or `paid` flag. Authenticate buyer wallet with server challenge and signature; verify mint, payer, transaction success/finality, recipients, amounts, and a unique order reference before granting **additional paid directions**. Reject replayed signatures and duplicate orders.


## Milestones

- G0: standalone baseline and two demo characters.
- G1: shared JSON quote / order / receipt fixture accepted by both developers.
- G2: App exposes a real quote; Solana helper signs a Devnet payment.
- G3: server verifies payout and grants access exactly once.
- G4: end-to-end demo plus negative payment and access tests.

Do not let optional NFT minting, per-minute billing or resale royalties block G0–G4.
