<div align="center">
  <h1>Echoloom</h1>
  <p><strong>Your favorite characters. Stories only you can direct.</strong></p>
  <p>A character marketplace and AI-powered story studio where you can create a character, share them with others, and bring two characters into a story of your own.</p>
  <p><a href="demo/Echoloom_Character_Marketplace_Demo.mp4"><strong>Watch the product demo</strong></a> · <a href="#quick-start"><strong>Get started</strong></a> · <a href="#architecture"><strong>Explore the architecture</strong></a></p>
  <p>
    <a href="https://github.com/Roxyh-code/Echoloom_marketplace/actions/workflows/ci.yml"><img src="https://github.com/Roxyh-code/Echoloom_marketplace/actions/workflows/ci.yml/badge.svg" alt="CI status" /></a>
    <img src="https://img.shields.io/badge/Next.js-16-15131F?logo=nextdotjs" alt="Next.js 16" />
    <img src="https://img.shields.io/badge/FastAPI-Python%203.12%2B-15131F?logo=fastapi" alt="FastAPI / Python 3.12+" />
    <img src="https://img.shields.io/badge/AI-LangGraph-6E52C8" alt="LangGraph" />
    <img src="https://img.shields.io/badge/Firecrawl-Autonomous%20research-FF6B35" alt="Firecrawl Agent and Search" />
    <img src="https://img.shields.io/badge/ElevenLabs-Character%20voice-15131F" alt="ElevenLabs voice matching and TTS" />
    <img src="https://img.shields.io/badge/Solana-Devnet%20integration-15131F?logo=solana" alt="Solana Devnet integration" />
    <img src="https://img.shields.io/badge/status-hackathon%20prototype-9B73DB" alt="Hackathon prototype" />
  </p>
</div>

<table>
  <tr>
    <td align="center"><img src="docs/assets/screenshots/editorial-marketplace.png" alt="Actual Discover marketplace screen" width="195" /></td>
    <td align="center"><img src="docs/assets/screenshots/editorial-character-library.png" alt="Actual character library screen with publishing and earnings entries" width="195" /></td>
    <td align="center"><img src="docs/assets/screenshots/editorial-character-creation.png" alt="Actual character creation screen" width="195" /></td>
    <td align="center"><img src="docs/assets/screenshots/editorial-story-reader.png" alt="Actual interactive story reader screen" width="195" /></td>
  </tr>
  <tr>
    <td align="center"><b>Discover</b></td>
    <td align="center"><b>Character Studio</b></td>
    <td align="center"><b>Create</b></td>
    <td align="center"><b>Story Reader</b></td>
  </tr>
</table>

<p align="center"><small>Actual running application screenshots captured by Playwright in <a href="https://github.com/Roxyh-code/Echoloom_marketplace/actions/runs/46083665183">CI run 46083665183</a>, using deterministic demo fixtures. Captured before the latest research and voice features; not design mockups or evidence of live provider calls or Solana settlement.</small></p>

> **Project status:** Local hackathon prototype. Character creation, autonomous web research, persistent voice selection, on-demand story audio, publishing, interactive rehearsal, wallet verification, signed checkout and earnings reporting are implemented. Standard CI passed for the research and voice integrations. Live provider acceptance, full local-validator execution and live Devnet settlement remain separate checks. Research, voice synthesis and payments are opt-in server features.

---

## The idea

Stories do not have to end where their authors left them.

What if two characters from different worlds met? What if a favorite character chose another path? What if you could decide how their next conversation unfolds rather than simply reading it?

**Echoloom turns characters into the starting point of collaborative storytelling.** Creators build original or properly licensed characters, readers discover and cast them, and an AI-powered rehearsal engine develops the scene as the reader directs, revises and branches the narrative.

Unlike a single-character chat interface, Echoloom is designed around **two-character scenes, creative direction and revisitable story versions**.

## Watch it in action

[**▶ Watch the recorded character-to-marketplace walkthrough (MP4)**](demo/Echoloom_Character_Marketplace_Demo.mp4)

This earlier video shows the running app's character creation, profile editing, publishing, listing updates and entry into a two-character scene. It was recorded using deterministic AI demo fixtures and the real frontend/API workflow, not a live paid-model session. It predates Firecrawl research and ElevenLabs dialogue playback. See [demo/README.md](demo/README.md) for the recording scope.

### From character to story

```mermaid
flowchart LR
    A["Discover characters"] --> B["Create or choose a character"]
    B --> C["Profile · portrait · voice"]
    B -.-> R["Optional background research"]
    R -.-> C
    C --> D["Publish a public listing"]
    D --> E["Cast two characters"]
    A --> E
    E --> F["Set a scene"]
    F --> G["Read, direct & branch"]
    G --> H["Save & revisit"]
    H --> G
    G --> I["40 free sentences reached"]
    I --> J["Verified paid unlock"]
    J --> G
    J --> K["Creator earnings"]
```

### A glimpse of the character shelf

<table>
  <tr>
    <td align="center"><img src="web/public/portraits/mira.webp" alt="Mira, demo character portrait" width="156" /></td>
    <td align="center"><img src="web/public/portraits/leo.webp" alt="Leo, demo character portrait" width="156" /></td>
    <td align="center"><img src="web/public/portraits/red-horn.webp" alt="Vesper, concept character artwork" width="156" /></td>
    <td align="center"><img src="web/public/portraits/red-boy.webp" alt="Ren, concept character artwork" width="156" /></td>
  </tr>
  <tr>
    <td align="center"><b>Mira</b></td>
    <td align="center"><b>Leo</b></td>
    <td align="center"><b>Vesper</b></td>
    <td align="center"><b>Ren</b></td>
  </tr>
</table>

<p><small>These are existing <strong>development-only placeholder illustrations</strong>, not evidence of public listing ownership or commercially cleared art. Some preview cards cannot be cast. Original licenses have not been verified; see <a href="docs/SAMPLE_ART_ASSETS.md">sample-art provenance and restrictions</a>.</small></p>

## What you can build today

| Experience | Current implementation |
| --- | --- |
| **Discover** | Browse published characters, search and filter the character catalog, and open public or private character details. |
| **Character Studio** | Create an AI-assisted character profile, generate a portrait, edit/refine the profile and manage portrait versions. The profile can appear while the initial portrait finishes asynchronously. |
| **Intelligent Character Research** | Firecrawl Search + Scrape and Agent discover public fictional-character lore from a short description. The initial profile is usable first; research produces a reviewable update with source references. |
| **Character Voice Identity** | Three candidates from an approved ElevenLabs voice catalog, matched to the profile; audition an original dialogue line and confirm a persistent voice. |
| **Voiced storytelling** | Tap the speaker beside a revealed dialogue or narration block to hear it with the pinned character voice or configured narrator. |
| **Creator publishing** | Publish an owned character with a public profile and rights confirmation; edit listing details, retain listing revisions, or unpublish. |
| **Two-character casting** | Choose two private characters, two published characters or a mixed pair. The backend verifies access to each source and uses listing revisions for public casts. |
| **Interactive rehearsal** | Set a premise, cast and scene constraints; generate a scene, reveal the story in sentence-sized steps, give directions, revise, branch and review versions. |
| **My Stories** | Reopen drafts, inspect versions, save a result and export story text. |
| **Free preview** | 40 free AI-generated sentences per normal scene, enforced on the server. The original built-in sample demo is exempt. |
| **Wallet connection** | Devnet-compatible Wallet Standard connection, signed ownership verification and restoration of an existing verified binding. |
| **Creator earnings** | Account-level payout wallet setup, per-listing monetization opt-in, zero-income listings and verified-payment reporting. |
| **Paid unlock** | Signed quote, client transaction builder, Anchor settlement, server-side receipt verification and 40 additional sentences per verified purchase. Live chain acceptance pending. |

The project uses a consistent, mobile-first **dark fantasy / moonlit violet** interface. Discover, Characters and My Stories share the same app frame and bottom navigation.

## From a character idea to a living story

Three integrations address different parts of the creative experience: **Firecrawl** enriches character knowledge, **ElevenLabs** gives a character a consistent voice, and **Solana** supports creator compensation through verified story unlocks.

### Intelligent character research · Firecrawl

A user can start with just a character name or short description. The studio saves a baseline profile first and continues research in the background, rather than making the reader wait for a deep-research job.

```mermaid
flowchart LR
    A["Short description"] --> B["Save baseline profile"]
    B --> C["Portrait and voice selection"]
    B --> D["Identify existing fictional character"]
    D --> E["Firecrawl Search + Scrape"]
    E --> F["Firecrawl Agent"]
    F --> G["Structured lore and sources"]
    G --> H["Review and apply update"]
    H --> I["New profile revision"]
```

- **Autonomous discovery:** no URL entry or manual source collection. Search discovers up to three sources and passes source hints to Firecrawl Agent, which returns structured facts covering identity, history, personality, motivation, relationships, speech, abilities and knowledge.
- **Nonblocking creation:** original or ambiguous characters skip paid research; provider failures leave the baseline character usable. An explicit, version-checked update preserves name, appearance and visual style, and does not overwrite intervening edits or existing story snapshots.
- **Responsible research:** source links are agent-reported, not independently fact-checked. Public availability does not establish commercialization rights. Paid research is owner-scoped and budgeted; the cache is process-local.

See [Character Research](docs/CHARACTER_RESEARCH.md) and [background research implementation](docs/CHARACTER_RESEARCH_BACKGROUND.md).

### Character voice identity · ElevenLabs

Rather than assigning a random generic narrator, Echoloom matches a character to existing, operator-approved voices using age, personality and speaking-style metadata. Each candidate can read the same short original dialogue line before the user confirms a voice.

```mermaid
flowchart LR
    A["Character profile"] --> B["Approved ElevenLabs voice catalog"]
    B --> C["Rank three candidates"]
    C --> D["Audition and confirm"]
    D --> E["Persistent voice identity"]
    E --> F["Published revision / cast snapshot"]
    F --> G["Revealed story dialogue"]
    G --> H["Tap speaker · ElevenLabs TTS"]
```

Voice selection is independent of ordinary profile edits. Public listing revisions and story casts pin the selected voice, so playback does not silently change when a creator rematches a character. The reader synthesizes only the requested, authorized revealed passage; narration is optional. Cache and per-account/global daily character limits control synthesis cost. No voice cloning, custom voice design or automatic billable audio is implemented.

See [Voice Identity](docs/VOICE_IDENTITY.md) for catalog, audition, playback and configuration details.

## Architecture

Echoloom separates creative orchestration from financial settlement. FastAPI is authoritative for scene access, pricing and attribution; the Solana program settles signed purchase terms and creates a durable receipt.

```mermaid
flowchart TB
    UI["Next.js / React · Character Studio · Marketplace · Story Studio"]
    WALLET["Wallet Standard · Phantom / compatible wallet"]
    API["FastAPI · session and ownership checks"]
    MARKET["Character profiles · listing revisions · cast snapshots"]
    CREATE["Character Studio · visual profile · background research"]
    FIRE["Firecrawl · Search / Scrape / Agent"]
    VOICE["Voice matching · authorized per-block playback"]
    ELEVEN["ElevenLabs · voice catalog / TTS"]
    STORY["Rehearsal engine · server-side sentence meter"]
    GRAPH["LangGraph · configured model adapters"]
    PAY["Quote · Ed25519 signer · payment verification"]
    DB[("SQLite · SQLAlchemy · Alembic")]
    CHAIN["Solana · Anchor marketplace program"]
    RECEIPT["Purchase receipt · SPL token transfers"]
    UI --> API
    UI <--> WALLET
    API --> MARKET
    API --> CREATE
    API --> VOICE
    CREATE --> FIRE
    CREATE --> DB
    VOICE --> ELEVEN
    VOICE --> DB
    MARKET --> VOICE
    STORY --> VOICE
    API --> STORY
    API --> PAY
    STORY --> GRAPH
    MARKET --> DB
    STORY --> DB
    PAY --> DB
    WALLET --> CHAIN
    CHAIN --> RECEIPT
    RECEIPT -->|"RPC evidence"| PAY
    PAY -->|"Verified entitlement"| STORY
```

| Layer | Stack |
| --- | --- |
| Web app | Next.js 16, React 19, TypeScript, CSS |
| API / validation | Python 3.12+, FastAPI, Pydantic |
| Narrative orchestration | LangGraph 1.2.20, configurable text/image adapters |
| Character research | Firecrawl v2 Search, Scrape and Agent; structured evidence and reviewable profile updates |
| Voice & audio | ElevenLabs existing voice catalog, profile-conditioned ranking, on-demand text-to-speech |
| Persistence | SQLAlchemy, SQLite, Alembic |
| Wallet / blockchain | Wallet Standard, @solana/web3.js 1.98.4, Solana classic SPL Token |
| Smart contract | Rust, Anchor 1.1.2 |
| Authorization | Ed25519, cryptography, solders |
| Testing | Pytest, Playwright, GitHub Actions, local validator suite |

See the [architecture and API guide](docs/ARCHITECTURE.md) for module boundaries, payment sequence and trust assumptions.

**Implementation note:** Portrait and research workers run in-process for a single-worker demo, not a production-grade distributed task queue. A restart can interrupt research. Portraits use only the committed visual profile; provider safety decisions are respected and an illustrated placeholder remains available if generation fails.

## Quick start

### Requirements

- **Python 3.12+** and **Node.js 22** (recommended for Next.js 16)
- npm
- A local terminal; provider credentials only if you want to generate new AI content

**1. Clone and set up the backend** (macOS / Linux):

```bash
git clone https://github.com/Roxyh-code/Echoloom_marketplace.git
cd Echoloom_marketplace
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env
python -m alembic upgrade head
python -m uvicorn echoloom.api:app --host 127.0.0.1 --port 8000 --reload
```

**Windows PowerShell** alternative, from the cloned repository root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn echoloom.api:app --host 127.0.0.1 --port 8000 --reload
```

**2. Start the frontend** in a second terminal:

```bash
cd web
npm ci
npm run dev
```

**3. Open [http://127.0.0.1:3000/marketplace](http://127.0.0.1:3000/marketplace).**

Browse the characters, open **Characters** to create a profile, or visit **My Stories** for the prepared railway-station demo. You can explore that prepared demo **without model API keys**. Generating your own profiles, portraits or scenes requires configured providers.

### Optional: enable real AI generation

Copy [.env.example](.env.example) to a local `.env` (already ignored by Git). Provide model identifiers and API keys that your account can access:

```dotenv
LLM_PROVIDER=openai
LLM_MODEL=your-supported-text-model
LLM_API_KEY=your-private-key
IMAGE_PROVIDER=openai
IMAGE_MODEL=your-supported-image-model
IMAGE_API_KEY=your-private-key
```

The web app proxies `/api/*` to `http://127.0.0.1:8000` by default. Set `API_BASE_URL` in the frontend environment only if your API runs at another address. **Never commit API keys, database files or character/customer data.**

### Optional: enable Firecrawl research

Sign in to Echoloom and configure the [Firecrawl API key](https://www.firecrawl.dev/app) in the root `.env`:

```dotenv
FIRECRAWL_ENABLED=true
FIRECRAWL_API_KEY=your-private-key
FIRECRAWL_MAX_CREDITS=100
FIRECRAWL_TIMEOUT_SECONDS=90
FIRECRAWL_DAILY_RUNS_PER_ACCOUNT=5
FIRECRAWL_DAILY_RUNS_GLOBAL=20
```

Restart FastAPI and confirm `research_enabled: true` at `/api/health`. In Characters → Create, leave **Research character** enabled. Create normally, then review the Firecrawl sources and choose **Apply update** when research is ready. The Agent credit cap does not include the separate Search request. Actual latency and credit consumption depend on the provider and task.

### Optional: enable ElevenLabs voices

Create a server-side API key with voice-read and (for synthesis) text-to-speech access. Inventory accessible voices using `python scripts/list_elevenlabs_voices.py`, then allowlist IDs whose usage rights you have reviewed. The app does not require or create voice clones.

```dotenv
ELEVENLABS_ENABLED=true
ELEVENLABS_API_KEY=your-private-key
ELEVENLABS_VOICE_IDS=comma-separated-approved-voice-ids
ELEVENLABS_AUDIO_ENABLED=true
ELEVENLABS_TTS_MODEL=eleven_multilingual_v2
ELEVENLABS_NARRATOR_VOICE_ID=
ELEVENLABS_AUDIO_DAILY_CHARS=5000
ELEVENLABS_AUDIO_GLOBAL_DAILY_CHARS=20000
```

Restart FastAPI. Create or open a character, audition and confirm a recommended voice. Enable audio only when you intend to incur synthesis usage. Configure an approved narrator ID to voice narration/action; otherwise those blocks remain text-only. Republish/recast older listings or scenes as needed to pin selected voices. All provider keys remain on the server.

### Updating an existing checkout

```bash
git switch main
git pull --ff-only origin main
python -m alembic upgrade head
```

Preserve your existing `.env` and add only missing settings. Restart the backend and frontend. The voice and research migrations are included in Alembic head.

## Creator economy

Publishing is free. A creator must verify a payout wallet, satisfy creator approval requirements and opt in a listing before it becomes eligible for paid scenes. A buyer can use a different wallet from their payout wallet.

| Product rule | Implemented demo terms |
| --- | --- |
| Free allowance | 40 AI-generated sentences per normal scene |
| Paid unlock | +40 sentences on the same scene, no calendar expiry |
| Price | 1 test token (1,000,000 minor units; six decimals) |
| Creator A | 45% |
| Creator B | 45% |
| Platform | 10% |

Free usage creates no payout. If both cast slots have the same recipient wallet, the backend aggregates the two shares. Paid quotes require two eligible payout recipients (which may be the same wallet); the buyer cannot be a recipient. The token is a configured classic SPL test mint, not necessarily USDC. Network fees and token-account rent are separate from the pack price. This is a demo economic model, not a claim of profitable inference economics.

```mermaid
flowchart LR
    B["Buyer · 1 test token"] --> S["Anchor purchase"]
    S --> A["Creator A · 0.45"]
    S --> C["Creator B · 0.45"]
    S --> T["Platform · 0.10"]
    S --> R["Receipt"]
    R --> V["Backend verification"]
    V --> E["+40 sentences"]
    V --> D["Earnings dashboard"]
```

### Try creator onboarding without a deployed contract

For a disposable local demo only, set `SOLANA_CREATOR_SELF_SERVICE_ENABLED=true` and restart FastAPI. Open Characters → Publish → Set up earnings, verify the payout wallet, return to publishing, enable earnings and save. Leave the flag off for administrator-approved onboarding. Payment itself remains disabled until a verified Devnet configuration is available.

For three prepared accounts, two original listings and a 40-sentence checkout scene, follow the [isolated demo runbook](docs/DEMO_ENVIRONMENT.md). No wallet proofs or payments are fabricated.

### Enable Devnet checkout

Only after the program and config have been deployed and independently checked, configure the values in [.env.example](.env.example) using the [deployment checklist](docs/PAYMENT_DEPLOYMENT_CHECKLIST.md). The backend signer file must stay outside the repository. Keep `SOLANA_PAYMENTS_ENABLED=false` until readiness checks pass. Buyer and recipient wallets must use Devnet test assets, never real funds.

## Repository map

```text
Echoloom_marketplace/
├── web/
│   ├── app/                   # Next.js routes and styles
│   ├── components/            # Discover, Character Studio, Story Studio
│   └── e2e/                   # Playwright browser tests
├── src/echoloom/
│   ├── creator_*.py           # Character profiles and background workers
│   ├── character_research.py  # Firecrawl Search / Scrape / Agent
│   ├── portrait_prompt.py     # Task-scoped visual profile
│   ├── voice/                 # ElevenLabs catalog, ranking, auditions and audio
│   ├── marketplace_*.py       # Public listings and revisions
│   ├── rehearsal_*.py         # Scene engine and LangGraph workflow
│   ├── scene_access*.py       # Server-enforced reading allowance
│   └── payments/             # Wallets, quotes, receipts, entitlements, earnings
├── solana/                    # Anchor program, IDL and validator tests
├── scripts/                   # Local integration and demo preparation
├── tests/mvp/                 # Backend and integration tests
├── alembic/                   # Database migrations
├── demo/                      # Recorded product walkthrough
├── docs/                      # Architecture, provenance and contracts
└── .env.example               # Configuration template
```

## Testing

Backend regression tests:

```bash
python -m pytest -q tests/mvp
```

Frontend checks (inside `web/`):

```bash
npm run typecheck
npm run build
```

Pytest covers research discovery, background execution and explicit revision application, voice catalog/selection/audio, and visual-profile isolation. Playwright covers marketplace publishing, casting, character editing, story rehearsal, inline voice controls, navigation and shared mobile-frame geometry. CI provisions a temporary Python test server, a Chromium browser and **fake AI providers**, so normal automated checks do not incur model usage fees. See [.github/workflows/ci.yml](.github/workflows/ci.yml) for the reproducible workflow.

## Validation and remaining work

| Workstream | Evidence / status |
| --- | --- |
| Character, marketplace and rehearsal flows | Implemented; browser and backend regression tests |
| Firecrawl autonomous research | PR #65 and nonblocking update #67 merged; standard CI passed ([#67 run](https://github.com/Roxyh-code/Echoloom_marketplace/actions/runs/46098152199)); live latency, source quality and credit usage not independently measured |
| ElevenLabs voice identity and inline playback | PRs #59–63 merged; mocked provider regression tests; live synthesis and playback acceptance remain separate |
| Visual profile and portrait fallback | PRs #66–67 merged; standard CI passed; provider approval is not guaranteed |
| Wallet persistence and creator onboarding | Implemented; PRs #49–51 merged with passing standard CI; local user testing reported |
| Payment integration safeguards | PR #52 merged; standard CI passed |
| Local validator and ledger acceptance | PR #53 merged; standard CI passed; full validator run not confirmed |
| Disposable demo environment | PR #54 merged; standard CI passed; actual operator run not confirmed |
| Devnet settlement and earnings | Deployment parameters and live end-to-end acceptance outstanding |
| Production readiness | Public authentication hardening, cross-device order reconciliation, concurrency safeguards, job queue, operations and licensing review outstanding |

Run payment regressions from the root:

```bash
python -m pytest -q tests/mvp -k payment
```

For real local-validator testing, install the Linux/WSL toolchain and follow [Local payment integration](docs/LOCAL_PAYMENT_INTEGRATION.md):

```bash
bash scripts/run-local-payment-e2e.sh
```

The standard CI workflow does not execute that full validator suite. The local bridge uses seeded order attribution and is not a complete browser/HTTP checkout test. The final demo must verify actual balance changes, receipt, 40→80→120 access, repeated verification and both creators' earnings. The [historical integration decision log](docs/HACKATHON_CONTRACT.md) includes superseded proposals; use this README and the current implementation guide for active behavior.

## Project background & responsible use

This repository was developed for **Dev3pack 2026** and builds on pre-existing character-creation and two-actor rehearsal work in [Echoloom V2](https://github.com/Roxyh-code/Echoloom_V2). The [migration record](docs/MIGRATION.md) documents what predates the hackathon and what was built or changed afterward.

**Local prototype only:** Authentication is not hardened for a public multi-user service. Use original characters or material you are licensed to distribute, and do not treat demo portraits as commercially reusable assets. The absence of a license file does not grant permission to redistribute third-party artwork or the repository's code.

For questions, bug reports and suggested contributions, open a [GitHub issue](https://github.com/Roxyh-code/Echoloom_marketplace/issues) or a pull request. For more technical detail, see [live-model acceptance](docs/LIVE_MODEL_ACCEPTANCE.md), [UI documentation](docs/EDITORIAL_UI.md) and the [product demo notes](demo/README.md).
