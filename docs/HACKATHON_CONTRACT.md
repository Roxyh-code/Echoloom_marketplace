# Marketplace integration contract (planning only)

**Historical planning record:** The original proposals below are preserved for decision history. They do not describe the current implementation. The active demo uses 40 free sentences per normal scene, +40 per verified purchase, 1 six-decimal test token and 45/45/10 split. See [README](../README.md) and [Architecture](ARCHITECTURE.md) for current code and validation status.

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

### Decision 3 — free/paid quota, retries and new-scene pricing: **Option A selected by product owner; teammate approval pending**

**Purchasing model: Scene + direction packs.**
- **First-ever scene:** free opening generation + **one** user-directed continuation (Decision 1). No Solana payment or creator payout for the trial.
- **Unlock the initial free scene:** a paid purchase adds **five** directions to that same scene.
- **Refill an existing scene:** after the available directions are exhausted, a new paid purchase adds **five more directions** without closing or replacing the scene; repeated refills are allowed.
- **Create any later scene:** purchase a new scene pack covering **one** opening generation **plus five** directions; further directions require refills.
- **Demo price hypothesis:** 1.00 **test** USDC per paid unlock, refill or subsequent-scene pack, subject to joint agreement on actual amount and token mint. All paid pack purchases follow Decision 2's 45% / 45% / 10% creator/platform split, based on the scene's two creator-wallet snapshots.
- **No calendar expiry** on an already purchased pack, subject to the service continuing to operate.

**Direction accounting and failure policy:**
- Reading, saving/viewing, editing a scene title, or manually editing existing text consumes **zero** directions.
- A successful AI continuation, a successful AI rewrite/regeneration requested by the user, or a successful AI-generated new branch from history consumes **one** direction each.
- AI calls that fail without generating a usable/persisted result consume **zero** directions.
- A retry of the **same operation_id** must return the existing operation result without charging another direction or double-generating. Persist an operation record and use an atomic reservation/commit-or-release pattern to avoid concurrency overspend; do not trust client-side counters.
- Rewriting content to a *new* result (even if disliked by user) costs a direction if successful; manual edits do not.
- A scene's two roles and associated creator ownership/payout-wallet snapshots are fixed for that scene. Changing one or both characters requires a **new** scene purchase (unless it is the user's first-ever free scene).
- The **first-ever free trial is one per verified user identity**, enforced server-side; exact anti-abuse account/wallet linkage remains a separate technical decision. Wallet-only Sybil protection is not assumed.

**Status:** Option A and the recommended metering/edge-case rules selected by product owner on **2026-11-22**. Solana teammate review and approval remain **pending**. These decisions supersede the older “one paid scene may have only one five-direction pack” assumption.

### Decision 4 — Solana network and payment token: **pending product owner choice and teammate approval**

Still to confirm: cluster (Devnet/Testnet/Mainnet), exact payment token mint, decimals, RPC, faucets/token provisioning, and whether to use an existing test USDC mint or mint a custom token.


## Milestones

- G0: standalone baseline and two demo characters.
- G1: shared JSON quote / order / receipt fixture accepted by both developers.
- G2: App exposes a real quote; Solana helper signs a Devnet payment.
- G3: server verifies payout and grants access exactly once.
- G4: end-to-end demo plus negative payment and access tests.

Do not let optional NFT minting, per-minute billing or resale royalties block G0–G4.


## Phase 2 Step 3 — server-side scene access (implemented in prototype)

- Marketplace-cast scenes (one or two Listing sources) are metered; existing private-only and prepared demo Rehearsal scenes remain unmetered.
- Creating a draft does not spend anything. The first *successful AI opening* across this local account's Marketplace scenes claims one free opening and **one** free AI direction. The entitlement is bound to that Scene.
- Each subsequent successful AI continuation, direction, branch, replay or AI-generating plot edit costs one direction. Manual edits, read, rename, setup, review and export do not spend direction quota. The source of truth is `marketplace_scene_access` and `marketplace_scene_usage`, not browser state.
- One `operation_id` reserves an allowance transactionally. The first durably stored generated block commits its charge. Failures with **zero** saved generated blocks refund it, including the trial claim when no opening was created; retries of the same logical job share the original usage root, even after partial failures. Scene deletion never renews a completed trial.
- Existing scenes with Marketplace actors from before this migration are initialized lazily. `GET /api/rehearsal/scenes/{id}/access` reports status (owner only); exhausted generations fail with HTTP 402. No endpoint accepts prices, wallet IDs, or client-declared access grants.
- Phase 4 must add trusted, receipt-verified pack grants (five directions for refills; one opening plus five directions for subsequent scenes). No fake paid unlock exists in this phase.
- **Security boundary:** the current local login is *not verified identity* or a Sybil-resistant public authentication system. The one-free-scene rule is enforceable only per local account and is unsuitable for a public launch until identity/anti-abuse design is completed.

## Phase 2 · 40-sentence free preview (revised product decision, 2026-11-23)

**This supersedes the old first-ever 1 Opening + 1 Direction quota and the Marketplace-only billing rule above.** Historical sections remain for context; they no longer describe runtime behavior.

- Every **non-demo** AI Scene has exactly **40 free AI-generated sentences**, regardless of cast source: two private, mixed private/public, or two published Marketplace Listings. Creator payouts remain a *separate* concern from AI inference billing.
- The free allowance is **per Scene** in this prototype. Generation is counted by server-side sentence boundaries, not clicking the Continue button or browser-visible CSS lines. An output that would cross 40 is persisted only through sentence 40. Existing Scene versions are projected to exclude material beyond that cap.
- Next line can reveal existing content only through sentence 40. The **41st read** is rejected with HTTP 402. AI generation after the 40th saved sentence is also rejected. The backend enforces both; the frontend merely displays status and opens an unlock explanation sheet.
- Saving, reviewing and exporting the first 40 sentences remain possible. Neither frontend state nor a wallet-connect attempt can grant credits. The current wallet sheet is honest about unavailable checkout; **no paid unlock, signature verification, mint or receipt verifier is implemented**.
- A prepared Demo Scene is exempt. There is no deduction of previous generated paragraphs for existing users: their original stored text is preserved, but API views/exports beyond 40 are gated until verified paid entitlement exists.
- **Open commercialization decisions:** per-Scene free preview can be repeated with fresh Scenes; production launch must address free-scene farming and verified user identity. We also need server-side paid read/generation entitlements and economic evaluation of 40 free sentences. The earlier 45/45/10 split remains a proposal for two third-party published Listings, with distinct rules needed for private/published combinations.
