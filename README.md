<div align="center">
  <img src="docs/assets/readme-hero.svg" alt="Echoloom: discover characters, publish your own, and direct shared stories" width="100%" />
  <h1>Echoloom</h1>
  <p><strong>Your favorite characters. Stories only you can direct.</strong></p>
  <p>A character marketplace and AI-powered story studio where you can create a character, share them with others, and bring two characters into a story of your own.</p>
  <p><a href="demo/Echoloom_Character_Marketplace_Demo.mp4"><strong>Watch the product demo</strong></a> · <a href="#quick-start"><strong>Get started</strong></a> · <a href="#architecture"><strong>Explore the architecture</strong></a></p>
  <p>
    <a href="https://github.com/Roxyh-code/Echoloom_marketplace/actions/workflows/ci.yml"><img src="https://github.com/Roxyh-code/Echoloom_marketplace/actions/workflows/ci.yml/badge.svg" alt="CI status" /></a>
    <img src="https://img.shields.io/badge/Next.js-16-15131F?logo=nextdotjs" alt="Next.js 16" />
    <img src="https://img.shields.io/badge/FastAPI-Python%203.12%2B-15131F?logo=fastapi" alt="FastAPI / Python 3.12+" />
    <img src="https://img.shields.io/badge/AI-LangGraph-6E52C8" alt="LangGraph" />
    <img src="https://img.shields.io/badge/status-hackathon%20prototype-9B73DB" alt="Hackathon prototype" />
  </p>
</div>

> **Project status:** Working local prototype, not a production or paid marketplace. Public character listings and AI story rehearsal are implemented; wallet authentication, Solana checkout and creator payouts are not. The banner above is an illustration of the flow, not an app screenshot.

---

## The idea

Stories do not have to end where their authors left them.

What if two characters from different worlds met? What if a favorite character chose another path? What if you could decide how their next conversation unfolds rather than simply reading it?

**Echoloom turns characters into the starting point of collaborative storytelling.** Creators build original or properly licensed characters, readers discover and cast them, and an AI-powered rehearsal engine develops the scene as the reader directs, revises and branches the narrative.

Unlike a single-character chat interface, Echoloom is designed around **two-character scenes, creative direction and revisitable story versions**.

## Watch it in action

[**▶ Watch the recorded character-to-marketplace walkthrough (MP4)**](demo/Echoloom_Character_Marketplace_Demo.mp4)

The video shows the running app's character creation, profile editing, publishing, listing updates and entry into a two-character scene. It was recorded using deterministic AI demo fixtures and the real frontend/API workflow, not a live paid-model session. See [demo/README.md](demo/README.md) for the recording scope.

### From character to story

```mermaid
flowchart LR
    A["Discover characters"] --> B["Create or choose a character"]
    B --> C["Edit profile & portrait"]
    C --> D["Publish a public listing"]
    D --> E["Cast two characters"]
    A --> E
    E --> F["Set a scene"]
    F --> G["Read, direct & branch"]
    G --> H["Save & revisit"]
    H --> G
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
| **Creator publishing** | Publish an owned character with a public profile and rights confirmation; edit listing details, retain listing revisions, or unpublish. |
| **Two-character casting** | Choose two private characters, two published characters or a mixed pair. The backend verifies access to each source and uses listing revisions for public casts. |
| **Interactive rehearsal** | Set a premise, cast and scene constraints; generate a scene, reveal the story in sentence-sized steps, give directions, revise, branch and review versions. |
| **My Stories** | Reopen drafts, inspect versions, save a result and export story text. |
| **Free preview** | Real scenes currently include **40 free AI-generated sentences per scene**, enforced on the server. The prepared sample demo is exempt. |

The project uses a consistent, mobile-first **dark fantasy / moonlit violet** interface. Discover, Characters and My Stories share the same app frame and bottom navigation.

## Architecture

Echoloom separates the character marketplace, scene orchestration and model integrations behind a FastAPI application.

```mermaid
flowchart TB
    subgraph WEB["Frontend · Next.js 16 / React 19 / TypeScript"]
      UI["Discover · Character Studio · My Stories"]
    end
    subgraph API["Backend · FastAPI / Python"]
      AUTH["Local session & ownership checks"]
      CREATOR["Character profiles / portrait jobs"]
      MARKET["Listings / revisions / publishing"]
      SCENE["Casting / scene access / rehearsal service"]
    end
    subgraph AI["AI orchestration"]
      GRAPH["LangGraph scene workflow"]
      MODELS["Configured text & image providers"]
    end
    DB[("SQLAlchemy · SQLite / Alembic")]
    UI --> AUTH
    AUTH --> CREATOR
    AUTH --> MARKET
    AUTH --> SCENE
    CREATOR --> MODELS
    SCENE --> GRAPH
    GRAPH --> MODELS
    CREATOR --> DB
    MARKET --> DB
    SCENE --> DB
```

| Layer | Stack |
| --- | --- |
| Web app | Next.js 16, React 19, TypeScript, CSS |
| API / validation | Python 3.12+, FastAPI, Pydantic |
| Narrative orchestration | LangGraph 1.2.20 |
| Persistence / migrations | SQLAlchemy, SQLite for the local prototype, Alembic |
| Model services | Configurable text and image provider adapters |
| Testing | Pytest, Playwright, GitHub Actions |

**Implementation note:** Portrait generation currently uses in-process background work appropriate for a single-worker demo; it is **not** a production-grade distributed task queue.

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

## Repository map

```text
Echoloom_marketplace/
├── web/
│   ├── app/                   # Next.js routes and styles
│   ├── components/            # Discover, Character Studio, Story Studio
│   └── e2e/                   # Playwright browser tests
├── src/echoloom/
│   ├── creator_*.py           # Character profiles and portraits
│   ├── marketplace_*.py       # Public listings and revisions
│   ├── rehearsal_*.py         # Scene engine and LangGraph workflow
│   └── scene_access*.py       # Server-enforced reading allowance
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

Playwright tests cover marketplace publishing, casting, character editing, story rehearsal, navigation and shared mobile-frame geometry. CI provisions a temporary Python test server, a Chromium browser and **fake AI providers**, so normal automated checks do not incur model usage fees. See [.github/workflows/ci.yml](.github/workflows/ci.yml) for the reproducible workflow.

## What's next

The product vision includes **creator compensation for stories that use published characters**, but the payment layer is not live.

| Workstream | Status |
| --- | --- |
| Character creation, discovery and publishing | Implemented in local prototype |
| Public/private two-character casting | Implemented in local prototype |
| Scene editing, branching and saved results | Implemented in local prototype |
| Server-enforced 40-sentence preview | Implemented in local prototype |
| Wallet-based sign-in and public multi-user security | Planned |
| Solana checkout, receipt verification and paid access | Planned |
| Creator/platform on-chain revenue splits | Proposed; not implemented |
| Production job queue, operations and licensing review | Required before launch |

The monetization split, token details and paid scene packs are **design proposals**, not implemented or deployed functionality. See the [integration contract](docs/HACKATHON_CONTRACT.md) for the decision history and current implementation boundary.

## Project background & responsible use

This repository was developed for **Dev3pack 2026** and builds on pre-existing character-creation and two-actor rehearsal work in [Echoloom V2](https://github.com/Roxyh-code/Echoloom_V2). The [migration record](docs/MIGRATION.md) documents what predates the hackathon and what was built or changed afterward.

**Local prototype only:** Authentication is not hardened for a public multi-user service. Use original characters or material you are licensed to distribute, and do not treat demo portraits as commercially reusable assets. The absence of a license file does not grant permission to redistribute third-party artwork or the repository's code.

For questions, bug reports and suggested contributions, open a [GitHub issue](https://github.com/Roxyh-code/Echoloom_marketplace/issues) or a pull request. For more technical detail, see [live-model acceptance](docs/LIVE_MODEL_ACCEPTANCE.md), [UI documentation](docs/EDITORIAL_UI.md) and the [product demo notes](demo/README.md).
