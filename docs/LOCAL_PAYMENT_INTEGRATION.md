# Local payment integration

Imported Ibrahim's workspace at b9aa40132b6a1c29143b99f0c8220aa1b4331e8b; Rust source unchanged. Historical handoff is upstream reference, not a claim all backend features exist here.

From WSL/Linux, clone into Linux filesystem. Install upstream README's Anchor CLI 1.1.2, Solana CLI 3.x, Rust, Node/npm, and Python project in Linux virtualenv (not Windows venv). From root:

```bash
python -m pytest -q tests/mvp/test_payment_anchor_contract.py
export ECHOLOOM_PYTHON="$(command -v python)"
export ECHOLOOM_PYTHON_BRIDGE=1
cd solana
bash scripts/test-localnet.sh
```

Fresh local program keypair mismatch: follow upstream README (anchor keys sync, rebuild). All keys disposable. Do not run against existing validator or other service on port 8899; runner resets its local ledger. Report npm lock errors rather than silently changing dependencies.

Opt-in test uses Python split/authorization/signature, sends Anchor transaction on local validator, checks exact token deltas, and uses Python transaction/receipt validators on actual loopback RPC evidence. Tampered order is rejected. Not full HTTP/DB entitlement or Phantom test. Normal Devnet guards unchanged. No public deployment or funds needed. Default Python CI runs static ABI/fixture checks; actual validator execution requires toolchain and has not been verified.

## PR 15: repeatable local E2E

Run from a Linux/WSL clone with Python package installed editable into the active Linux venv, Anchor 1.1.2, Solana 3.x, Rust and Node/npm:

```bash
export ECHOLOOM_PYTHON="$(command -v python)"
bash scripts/run-local-payment-e2e.sh
```

The wrapper runs Python payment regressions, makes a disposable scratch copy of tracked Solana sources (working-tree versions), creates a fresh local program key, runs Anchor key sync there, then starts the upstream validator runner. No tracked program ID edits, no default wallet, no deployment. Port 8899 must be free. Scratch build/ledger is removed when the wrapper exits. The test bridge imports the installed Python project; use editable install from the same clone. Dependency/build downloads may require internet access.

The real transaction test additionally writes the verified order into a temporary SQLite DB, invokes the production verification service against loopback evidence with a process-local genesis substitution, verifies account isolation, repeated verification, one grant, 40→80 allowance, and 0.45 token earnings for each creator. It also retries the same on-chain purchase and asserts no extra debit. Order and creator attribution are seeded test fixtures, not a full live HTTP quote/onboarding/Phantom test. No production network guard is changed. Actual local validator execution is still outstanding.
