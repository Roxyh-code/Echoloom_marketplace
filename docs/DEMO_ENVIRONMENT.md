# Repeatable Devnet demo environment

This offline operator tool creates three accounts and two original fictional listings in a **separate** disposable SQLite database. No model calls, wallet proofs, payments, earnings or entitlements are fabricated. The prepared story is authored sample text, not live AI output. Keep the normal database untouched.

From repository root, stop backend first. Run:

```powershell
python scripts/prepare_demo.py init --db work/demo-payment.db --confirm-disposable-demo
```

Save the three randomly generated passwords privately; they are printed once. Never commit them. In the backend terminal set temporary environment variables (do not overwrite your normal .env):

```powershell
$env:DATABASE_URL = "sqlite:///./work/demo-payment.db"
$env:SOLANA_CREATOR_SELF_SERVICE_ENABLED = "true"
python -m uvicorn echoloom.api:app --reload --port 8000
```

Start frontend as usual. Sign in as demo_mira, verify payout wallet, enable earnings and save listing. Repeat with demo_rowan using another wallet. Optional: generate portraits through the UI before saving listings (requires image API); no art is seeded. Then stop backend and run:

```powershell
python scripts/prepare_demo.py scene --db work/demo-payment.db --confirm-disposable-demo
```

The command checks both current listing revisions and verified payouts, creates a new normal metered scene for demo_buyer with exactly 40 already-revealed authored sample sentences, and prints scene ID. It does not touch existing scenes. Restart backend with same demo environment and log in as demo_buyer; open My Stories and select The Lighthouse Key. Use a third distinct wallet. Checkout verification can be tested before deployment; actual payment needs valid Devnet configuration and tokens. Re-run scene command for another fresh checkout after payment or listing edits. Do not describe prepared text as AI-generated in the demo.

To return to normal local data, stop backend and remove temporary env overrides in PowerShell:

```powershell
Remove-Item Env:DATABASE_URL
Remove-Item Env:SOLANA_CREATOR_SELF_SERVICE_ENABLED
```

No automatic deployment, no wallet secrets, no production database changes. Never reuse demo credentials or enable the demo self-service flag for a production deployment.
