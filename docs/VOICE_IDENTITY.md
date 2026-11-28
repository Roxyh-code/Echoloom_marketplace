# Character Voice Identity — phase 18A

Existing voices only. No new voice design, cloning, TTS synthesis, or paid audio generation in this phase. No migration; the standalone VoiceIdentity schema will be persisted by the explicit selection workflow in 18B, then pinned into public listings and scene cast snapshots. Never let the profile-generation model invent provider voice IDs.

## Setup (local)
Create an ElevenLabs API key with voice-read access and add it to the root ignored .env. Never commit or send it to the browser.

```dotenv
ELEVENLABS_API_KEY=your-private-key
ELEVENLABS_ENABLED=true
ELEVENLABS_VOICE_IDS=comma-separated-reviewed-voice-ids
```

Run `python scripts/list_elevenlabs_voices.py` to inventory existing accessible voices, including IDs, labels and existing preview URLs. Add appropriate voices in ElevenLabs My Voices first if required. Review usage rights and account tier before allowlisting; prefer stable Infinity voices. Do not allowlist private clones, unconsented voices or restricted assets. The script does not add or generate any voices. A catalog of 30–50 approved voices is a target, not seeded data; at least three usable distinct IDs are required for the three-choice experience.

Restart FastAPI. Sign in and GET /api/voice/catalog (e.g. in the logged-in browser at http://127.0.0.1:3000/api/voice/catalog). The server reads only allowlisted IDs using GET /v2/voices, filters unavailable/missing-preview voices, and caches metadata for one hour by default. Preview URLs are provider-supplied HTTPS links, not new synthesis. Key remains server-side. Disabled/missing config is explicit; upstream errors are sanitized. Existing voice rights are operator-reviewed, not certified by the API.

## Next phases
18B: profile-conditioned ranking with three diverse candidates, preview and explicit save, publication and immutable cast identity. 18C: on-demand authorized story audio, cache and generation limits. Until then no voice-selection UI or playback exists. Standard CI uses mocked provider responses only; live account access and preview playback need acceptance testing.

Official docs: https://elevenlabs.io/docs/api-reference/voices/search and https://elevenlabs.io/docs/overview/capabilities/voices.

## Phase 18B
Run alembic upgrade head (0012). Open a saved Character Studio detail page: automatic three-candidate matching if no voice is selected; existing provider preview URLs, explicit confirmation, optional rematch. The existing LLM ranks a metadata shortlist of at most 16 approved IDs; invalid/unavailable ranking falls back to metadata matching. In-memory results cached by profile version and catalog, no new voice synthesis. Confirmed identities live independently of profile revisions, and publishing pins the current selected identity. Existing scene snapshots remain unchanged. No custom voice or cloning. Existing characters/listings migrate with null voice; select and republish/recast to use audio. Actual provider test pending.

## Phase 18C
Apply migration 0013. Explicitly set ELEVENLABS_AUDIO_ENABLED=true to enable billable synthesis. The reader offers sequential playback of revealed passages using pinned character voices. Narration/action is skipped unless ELEVENLABS_NARRATOR_VOICE_ID is approved and configured. Uses per-block POST /v1/text-to-speech/{voice_id}, not joint Text to Dialogue, for granular cache reuse and cost control. No automatic generation on reading, arbitrary text endpoint, or extra entitlement. Cache scoped to owner/scene/exact text/voice/model in work/voice-audio. Default daily attempted-character caps: 5,000/account, 20,000 globally, UTC, not provider credit counts. Failures reserve budget; no automatic retry. Single-worker cache lock; production multi-worker coordination, retention/cleanup and billing need further work. Audio text leaves the app on explicit playback; provider retention follows account policy. Real audio calls and browser playback unverified.
