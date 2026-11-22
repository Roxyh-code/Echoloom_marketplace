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

### Decision 2 — creator/platform revenue split: **Option A selected by product owner; teammate approval pending**

- **Fixed split for every paid unlock:** Creator A **45%**, Creator B **45%**, Echoloom platform **10%**. At the illustrative (not final) 1.00 test USDC charge, these shares are **0.45 / 0.45 / 0.10 USDC**.
- If both characters belong to the same creator payout wallet, **merge the two creator payout lines** (90% to that wallet, 10% to platform). For other duplicate recipient wallets, aggregate exact amounts before constructing the transaction.
- Free-trial generation and its one free direction have **no on-chain split payout**; this choice applies only to successful **paid** purchases.
- Use backend-authoritative percentages, recipient wallet snapshots and integer token minor units. Record a fixed quote; do not accept browser-supplied prices, payout accounts or `paid` flags. Quote expiry, token mint, gas cost, platform cost coverage and paid pack scope remain to be jointly confirmed.
- Verify payer, successful transaction and finality, mint, exact recipient totals and unique order reference server-side; reject replayed signatures. This is a **demo revenue model, not a claim that a 10% platform share covers inference cost**.
- **Status:** Option A selected by product owner on 2026-11-22, awaiting Solana teammate approval. This does not itself approve the illustrative token price.

### Decision 3 — free/paid quota, retries and new-scene pricing: **pending product owner selection and teammate approval**

Decision 1 fixes the first free scene opening + one free direction, and five additional directions after a paid unlock of that free scene. Still to freeze: quota replenishment, how subsequent new scenes are purchased, whether a new-scene purchase includes an opening, and retry/failure/duplicate-request accounting.


## Milestones

- G0: standalone baseline and two demo characters.
- G1: shared JSON quote / order / receipt fixture accepted by both developers.
- G2: App exposes a real quote; Solana helper signs a Devnet payment.
- G3: server verifies payout and grants access exactly once.
- G4: end-to-end demo plus negative payment and access tests.

Do not let optional NFT minting, per-minute billing or resale royalties block G0–G4.
