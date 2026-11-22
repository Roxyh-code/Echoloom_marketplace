# EchoLoom Marketplace · Dev3pack 2026

**Stage 1 baseline** — extracted from the pre-existing [EchoLoom V2](https://github.com/Roxyh-code/Echoloom_V2). This repository currently runs the existing mobile character creation and interactive **two-character rehearsal** app. The marketplace, creator payouts and Web3 checkout **have not been implemented**.

> Source provenance and the boundary between pre-hackathon and new work: [docs/MIGRATION.md](docs/MIGRATION.md). Team integration fields: [docs/HACKATHON_CONTRACT.md](docs/HACKATHON_CONTRACT.md).

## Intended MVP

Discover properly authorized characters → select two → enter a new scenario → get a server quote → pay creators and the platform on Solana Devnet → receive a server-verified scene entitlement → direct/read/save the AI performance.

## Technology

- Frontend: Next.js 16 / React 19 / TypeScript, **existing mobile UI** in `web/` (planned redesign: editorial bookshop/character marketplace UI).
- Backend: FastAPI, SQLAlchemy, Alembic and LangGraph in `src/echoloom/`.
- Accounts: legacy **local-only** login for testing, **not yet** wallet-based marketplace authentication.

## Local setup

Requires **Python 3.12+** and a supported Node.js version for Next.js 16 (Node 22 recommended). From the repository root:

```bash
python -m venv .venv
# Windows PowerShell: .\\.venv\\Scripts\\python.exe -m pip install -e ".[dev]"
.venv/bin/python -m pip install -e ".[dev]"
cp .env.example .env     # Windows PowerShell: Copy-Item .env.example .env
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m uvicorn echoloom.api:app --host 127.0.0.1 --port 8000 --reload
```

In a second terminal:

```bash
cd web
npm ci
npm run dev
```

Open **http://127.0.0.1:3000/rehearsal**. Choose the **station reunion demo** to exercise the prepared scene without model keys. To generate your own characters/portraits/scenes, set the provider model names and private API keys in the ignored `.env` file. The old app's character and scene records are **not copied**; this is a clean database.

On Windows, use `.\\.venv\\Scripts\\python.exe` instead of `.venv/bin/python` in the backend commands. No user secrets or local databases are tracked.

## Tests

```bash
python -m pytest -q tests/mvp/test_creator.py tests/mvp/test_rehearsal.py tests/mvp/test_rehearsal_format.py tests/mvp/test_rehearsal_attribution.py tests/mvp/test_rehearsal_quality.py tests/mvp/test_checkpoint_recovery.py tests/mvp/test_migrations.py tests/mvp/test_providers.py
cd web && npm ci && npm run typecheck && npm run build
```

The CI workflow runs the Python and Next.js checks. Selected Playwright test specs remain in `web/e2e/` but are not part of initial CI.

## Safety and limitations

**Do not publish this stage as a public multi-user marketplace.** Legacy account and database compatibility models remain, but the old standalone chat/story and companion/calendar routes have been removed. The app still uses local-only account semantics. Public DTOs, creator ownership proofs, real wallet authentication, backend price authority, payment receipt verification and paid-scene access controls must be implemented before deployment. Only original or properly licensed characters may be commercially listed; do not upload copyrighted character art without permission. Never add `.env`, `work/`, keys, customer data or third-party commercial UI assets to git.
