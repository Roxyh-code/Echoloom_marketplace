# Devnet demo creator setup

This is an operator-only local SQLite utility, not a general creator onboarding UI. Never run against production data. Stop the local API while applying changes and back up the demo DB. No chain deployment or funds required.

1. Register two distinct demo creator accounts. In each account create and publish an original character. Record the listing UUID from its marketplace detail/API response.
2. In each account verify a different Phantom test wallet via the existing checkout wallet challenge (a non-demo story must reach its allowance to expose checkout). This proves wallet ownership, not consent to monetization. Obtain explicit consent from each creator to reuse that wallet for Devnet payouts.
3. With the API stopped, run from repository root:

```powershell
python scripts/activate_demo_creators.py --db work/echoloom.db --listing <LISTING_A_UUID> --listing <LISTING_B_UUID> --confirm-devnet-demo-consent
```

Use the actual local DB path, not necessarily the example. The tool rejects missing bindings, duplicate creators, duplicate wallets, unpublished listings and unsupported wallet rotation. It copies the verified binding timestamp, approves the creators, and creates new immutable payout snapshots atomically. Repeating the same activation is idempotent. No secret keys are needed or printed.

4. Restart API. Sign in to a third buyer account, verify a third wallet, and select the newly monetized public listings from Discover. Create a NEW scene so it pins the new revisions. Older scenes retain their original payout snapshot and are not silently migrated. Editing or unpublishing a listing disables monetization; rerun explicit activation if appropriate.
5. After shared Devnet configuration is ready, fund buyer with test SOL and the agreed SPL token, run readiness check, and buy 40 sentences. Expected distinct payout shares: 450000, 450000, 100000 minor units.

This utility deliberately does not create fake verification records, enable payments, mint tokens, or change chain configuration. A full self-service creator payout consent/signature and approval workflow remains future work.
