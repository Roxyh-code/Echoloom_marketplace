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

GitHub Actions checks the Python backend, Next.js production build, and the extracted mobile UI in Chromium using mocked AI providers and temporary data. Playwright's test server runs only with `ECHOLOOM_TEST_SERVER=1`.

## Safety and limitations

**Do not publish this stage as a public multi-user marketplace.** Legacy account and database compatibility models remain, but the old standalone chat/story and companion/calendar routes have been removed. The app still uses local-only account semantics. Public DTOs, creator ownership proofs, real wallet authentication, backend price authority, payment receipt verification and paid-scene access controls must be implemented before deployment. Only original or properly licensed characters may be commercially listed; do not upload copyrighted character art without permission. Never add `.env`, `work/`, keys, customer data or third-party commercial UI assets to git.

## Live-model acceptance (Phase 2)

The CI suite uses simulated AI providers. For a billable, opt-in real-model smoke run with an isolated database and a manual story-quality rubric, follow [docs/LIVE_MODEL_ACCEPTANCE.md](docs/LIVE_MODEL_ACCEPTANCE.md). This does **not** run automatically in CI and is **not** a Solana payment test.

## Reader free limit (current prototype)

All real two-character scenes (private or public/mixed casts) are free for the **first 40 generated story sentences**. The server does not allow reading sentence 41 or further AI generation after the sentence cap. The wallet-unlock UI explains the next phase, but **Solana checkout is not integrated**. The prepared example Demo remains exempt. See [docs/HACKATHON_CONTRACT.md](docs/HACKATHON_CONTRACT.md) for the updated policy and current anti-abuse limits.


## Character creation performance

Character Studio now saves the AI-generated **profile first** and opens the character detail immediately. The initial portrait is rendered **asynchronously** in a background worker; the character remains usable while it is generating. A progress message on the detail page and `GET /api/creator/jobs/{request_id}` report its status. Image errors leave the profile intact, with an image-only retry. The creation request ID is reusable after a lost HTTP response or server restart, so a retry does not regenerate the character profile.

For GPT Image API generation, `IMAGE_INITIAL_QUALITY=medium` (default) provides a first-portrait quality/performance tradeoff; `IMAGE_INITIAL_QUALITY=low` is suitable for faster draft previews, and `auto` uses the model's default. Quality is intentionally **not overridden on edits** or unknown image model names. Keep `IMAGE_MODEL` set to a model your OpenAI project can access. Existing `API_TIMEOUT_SECONDS` controls provider timeout. Review safe backend log lines `creator stage=profile`, `creator stage=portrait`, and `provider=openai kind=image elapsed=...` to distinguish profile time from image service latency (no profile text or secret is logged).

**Deployment note:** This optimization uses an in-process daemon worker in the same **single-worker local prototype** environment as rehearsal jobs. A multi-process deployment needs a persistent external queue, a lease/recovery mechanism, and job monitoring before treating image generation as production-reliable. Running multiple image workers simultaneously against the same local SQLite database is not supported.

## Faster Character creation: parallel Profile + portrait

When creating a Character, the backend launches two **concurrent AI requests**
from the same original text description: (1) structured Profile generation and
(2) initial portrait generation. Because the image prompt uses the **original
description**, its appearance may differ from extra visual details invented
later by the Profile model. Add explicit appearance details when that matters,
or edit the portrait afterward.

The UI opens the saved Character as soon as its Profile is ready, while a
progress message shows that the portrait continues in the background.
Creation and image results use the same `request_id` so repeated
submissions cannot launch duplicate in-flight requests. Failed image calls
preserve the Profile; use **Retry portrait**, not Create Character again.

For the initial GPT Image render, configure `IMAGE_INITIAL_QUALITY=medium`
(default) or `low` for a faster draft; `auto` uses provider defaults.
This does not affect portrait edits or non-GPT image models.
Real image latency has not been benchmarked in CI (fake provider only).

**Deployment limit:** This uses an in-memory background thread for a
single-process local MVP, not a durable task queue. With a process crash in
the middle of an external paid image request, recovering it may require a new
image call. Never automatically retry an uncertain billable request.
