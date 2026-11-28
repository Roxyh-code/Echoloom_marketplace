# Intelligent Character Research

Firecrawl powers optional research of existing fictional characters from a short description, with no URL entry. The current implementation (PR #67) replaces the earlier blocking research flow in PR #65.

## Current workflow

1. Save a baseline profile with the configured text model; start the portrait worker independently.
2. In the background, classify the input. Skip original, private, real-person or unclear identities. Only classifier-derived public fictional identifiers should reach Firecrawl.
3. Reuse cached lore or use Firecrawl v2 Search with Scrape options to discover up to three public sources, then the autonomous Agent to obtain structured lore and reported source references. Search excerpts are untrusted hints.
4. Synthesize a proposed profile that respects explicit user instructions. Preserve the initial name, appearance and visual style.
5. Show the owner a research update and expandable sources. Apply explicitly to create a new profile revision only when the base version still matches. Existing story snapshots are not modified.

Provider errors leave the baseline profile usable. The application does not silently replace the portrait, voice or intervening profile edits. Research is not a licensing audit; sources are agent-reported, not independently fact-checked.

## Configuration

After migration 0014 (or current Alembic head), set `FIRECRAWL_ENABLED=true` and `FIRECRAWL_API_KEY` in the ignored root .env, restart FastAPI and verify `research_enabled` at /api/health. Sign in before using research. See [.env.example](../.env.example) for all settings.

Defaults: 100 Agent credits per run (separate Search usage is additional), 90-second Agent polling deadline, five attempted research runs per account and twenty globally per UTC day. These are single-server application limits; network/cancellation can extend the deadline. Cache lasts up to 24 hours in one process. Restart interrupts in-process jobs; no automatic paid retry. Durable shared queues, independently verified provenance and timeline-aware knowledge gates remain future work.

See [nonblocking research](CHARACTER_RESEARCH_BACKGROUND.md) and [official Agent API](https://docs.firecrawl.dev/api-reference/endpoint/agent). Standard CI for #67 passed; real provider accuracy, latency and credit usage require live acceptance.
