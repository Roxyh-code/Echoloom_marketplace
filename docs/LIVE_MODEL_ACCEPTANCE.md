# Phase 2: real-model Marketplace acceptance

## Scope and truth-in-testing

Existing CI tests use simulated AI text. Passing them proves API/state/UI
integration, **not** that the live model writes coherent fiction.

The opt-in smoke runner uses a real configured OpenAI text provider through
FastAPI, LangGraph and the real asynchronous Rehearsal worker. It creates a
temporary database, two original fictional public Listings, a first free Scene,
and exercises two model generations (which usually generate fewer than 40 sentences). It verifies:

1. Listing-only safe snapshots never contain hidden Character private fields.
2. Two real-model sample generations before the 40-sentence cap generate stored text.
3. Attributions contain only the two Scene actor IDs or null narrator.
4. The 41st attempted read is rejected with HTTP 402; new generation is blocked after 40 generated sentences.
5. Read/save/reopen preserves exact generated text and Scene provenance.

The run does NOT call an image-generation model or issue any Solana payments.

## Running real AI

Install the project as described in README.md. In the untracked, ignored .env
or process environment, configure these variables with your own accessible model:

    LLM_PROVIDER=openai
    LLM_MODEL=(your selected actual model ID)
    LLM_API_KEY=(your private API key)

From repository root, explicitly opt in to the billable test:

    python scripts/marketplace_live_smoke.py --allow-billable

To select a report path and timeout:

    python scripts/marketplace_live_smoke.py --allow-billable --timeout 300 --output work/qa/acceptance.json

The --allow-billable flag is mandatory. Without it, **no live call occurs**.
The provider may retry malformed outputs, so the test can trigger more than two
billable model API calls even though it requests two successful scene segments.
The script isolates the database and user identity, and deletes its scenes on
exit. It does not modify production/private character records.

The output JSON report is written under work/qa by default (ignored by Git).
It includes fictional AI-generated prose and model name to permit direct
qualitative review. Review this file before sending it to someone else; never
commit it alongside .env or key material.

## Manual quality gate

The report contains five human review questions with null scores. Complete each
after reading the generated opening and direction:

- Are Mira and Rowan's *published* persona traits reflected by distinct voices?
- Does the next segment progress instead of repeating or looping?
- Is the sealed-letter hard rule preserved with no invented events?
- Does neither character gain unexplained knowledge or inappropriate agency?
- Are prose, pacing, attribution, and small-screen reader UX convincing?

**Recommendation for demo sign-off:** automated checks pass, all five manual
categories score at least 4/5, and there is no rule/privacy violation.
This is a project acceptance threshold, not a statistical quality benchmark.

## Real-device UI check

The smoke script tests real **backend** generation and persistence, not actual
browser UI or screenshots. Separately, run the normal app locally using a
disposable account and authorized original characters. On a 375–390px mobile
viewport, check this workflow:

Discover → select two public Listings → Setup → Start rehearsal → read each
sentence → continue once → observe unlock-required banner → review/save →
My Stories → reopen without generation. Inspect loading, retry, scroll, and
the readability of each role's portrait/name.

The temporary Scene created by the smoke script is deliberately deleted when
the script exits, so it cannot be browsed in the ordinary local app afterward.

Also review a Chinese-language scene and a mixed private/public cast in a
separate trial before any production claim. Those combinations remain
automatically tested with fake providers but not by this two-call live runner.

## Offline regression in CI

    python -m pytest -q tests/mvp/test_marketplace_live_smoke.py

These tests inject a fake provider and validate the smoke runner's API
assertions, isolation and evidence format. A green GitHub Actions build should
be described as **harness verified, live run pending** unless someone explicitly
performed the billable run.

Known non-production constraints: current local account identity is not
verified or Sybil-resistant. Wallet checkout/paid unlock is a separate phase.

**Updated 40-sentence contract:** The live smoke's two model samples need not exhaust 40 sentences. It verifies the 41st Next line is unauthorized. The deterministic offline suite additionally tests the exact 40th sentence, truncation of a 46-sentence response, and private/public parity. No live Solana unlock is claimed.
