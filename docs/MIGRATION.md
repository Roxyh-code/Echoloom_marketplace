# Stage 1 extraction / source provenance

Source: [Roxyh-code/Echoloom_V2](https://github.com/Roxyh-code/Echoloom_V2) at commit `4c6b5ad5d9b333dfa5bf50f8be7ef1665d57b4cf` (main at extraction). Target: `Roxyh-code/Echoloom_marketplace`, branch `migration/stage1-extraction`.

## Pre-existing work copied (NOT hackathon-original)

- **Two-actor rehearsal:** `src/echoloom/rehearsal_{service,graph,domain,schema}.py`, the existing LangGraph choreography, scene data, directions, versions, persistence and its mobile app UI.
- **Character/portrait creation:** `src/echoloom/creator_{service,domain,schemas}.py`, `schemas.py`, `providers.py`, `web/components/mobile-character-studio.tsx`, relevant API clients and existing character image assets.
- **Runtime:** existing FastAPI `api.py`, `db.py`, `config.py`, local accounts, Alembic revisions 0001-0005, the original Next.js configuration, tests and fake-provider fixtures.

All copied source modules retain their pre-existing functionality unless explicitly noted. The one intentional behavior change at extraction is `COMPANION_WORKER_ENABLED` defaulting to false in `config.py`; it is not part of this hackathon's user flow.

## Intentionally excluded from the target

- `literature/`, `experiments/`, `schemas/`, `data/`, `demo/` and most historical project documentation.
- Former standalone chat/companion, old creator story-editor and other unrelated Next.js pages and components, plus their browser tests.
- Any personal `.env`, `work/`, local SQLite DB, private character content, model credentials, Google Calendar OAuth tokens or secrets.

## Temporary compatibility debt

The **backend** currently still contains `story_service.py`, `companion_service.py`, `calendar_*.py`, `chat_memory.py` and their legacy DB models because the original `api.py` and Alembic revisions refer to them. They are **not** part of the planned Marketplace MVP. The companion worker is disabled by default; the old companion UI is not copied. Deleting those modules without first narrowing `api.py` and the shared models breaks the imported rehearsal and character code. Refactor this boundary after preserving a tested working baseline.

The existing local-account system is **not** multi-user authorization for a public marketplace. Do **not** deploy this extraction as an open Marketplace or assume it has paid scene entitlements.

## Hackathon-original work still to build

Public creator-owned listings and safe DTOs; marketplace and casting UI; immutable price quotes and scene orders; wallet sign-in; Solana Devnet atomic split payments; server-side receipt verification; paid-scene entitlements and usage limits; creator earnings and demo proof. None of those are included in the source baseline.

## Acceptance and test guidance

1. `python -m pip install -e ".[dev]"` and `python -m alembic upgrade head` from repository root.
2. `python -m pytest -q tests/mvp/test_creator.py tests/mvp/test_rehearsal.py tests/mvp/test_rehearsal_format.py tests/mvp/test_rehearsal_attribution.py tests/mvp/test_rehearsal_quality.py tests/mvp/test_checkpoint_recovery.py tests/mvp/test_migrations.py tests/mvp/test_providers.py`.
3. `cd web && npm ci && npm run typecheck && npm run build`.
4. Run FastAPI and Next.js locally; visit `/rehearsal`, select the prepared railway-station demo and exercise create/direct/save. Custom scenes require provider credentials.

The GitHub Actions workflow checks Python and Next.js. UI E2E tests are preserved, but not executed by the initial CI job. Record CI results before calling the extraction validated.
