"""Read-only catalog client. No voice design, cloning or synthesis endpoints."""
import re
import time
from threading import Lock
from urllib.parse import urlsplit

import httpx
from pydantic import ValidationError

from .schemas import CatalogVoice, VoiceCatalogResponse

BASE = "https://api.elevenlabs.io"
ID = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
LABELS = {"gender", "age", "accent", "language", "description", "use_case",
          "tone", "pitch", "pace", "pacing", "texture", "style"}


class VoiceProviderError(RuntimeError):
    """Sanitized provider error, never contains a key or upstream body."""


def approved_ids(settings):
    ids = list(dict.fromkeys(x.strip() for x in settings.elevenlabs_voice_ids.split(",") if x.strip()))
    if len(ids) > 100 or any(not ID.fullmatch(x) for x in ids):
        raise VoiceProviderError("Voice catalog configuration is invalid.")
    return ids


def public_voice(raw):
    """Expose only reviewed catalog metadata, not sharing or account fields."""
    try:
        if not isinstance(raw, dict):
            return None
        expires = raw.get("disable_at_unix")
        if isinstance(expires, (int, float)) and expires <= time.time():
            return None
        url = raw.get("preview_url")
        if not isinstance(url, str) or len(url) > 2048:
            return None
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            return None
        labels = raw.get("labels") or {}
        if not isinstance(labels, dict):
            labels = {}
        return CatalogVoice(
            voice_id=raw.get("voice_id"),
            name=str(raw.get("name") or "")[:120],
            description=str(raw.get("description") or "")[:1000],
            labels={str(k): str(v)[:200] for k, v in labels.items()
                    if k in LABELS and isinstance(v, str)},
            preview_url=url,
            category=str(raw.get("category") or "")[:80],
        )
    except (ValidationError, ValueError, TypeError):
        return None


class ElevenLabsCatalog:
    def __init__(self, settings, *, transport=None):
        self.settings = settings
        self.transport = transport
        self.lock = Lock()
        self.cached = []
        self.cache_key = None
        self.expires = 0.0

    def _fetch(self, ids):
        allowed = set(ids)
        found = {}
        seen_tokens = set()
        token = None
        try:
            with httpx.Client(base_url=BASE, timeout=self.settings.elevenlabs_timeout_seconds,
                              follow_redirects=False, transport=self.transport,
                              headers={"xi-api-key": self.settings.elevenlabs_api_key.get_secret_value()}) as client:
                for _ in range(10):
                    params = [("page_size", "100")] + [("voice_ids", i) for i in ids]
                    if token:
                        params.append(("next_page_token", token))
                    response = client.get("/v2/voices", params=params)
                    response.raise_for_status()
                    data = response.json()
                    if not isinstance(data, dict) or not isinstance(data.get("voices"), list):
                        raise VoiceProviderError("Voice catalog returned an invalid response.")
                    for raw in data["voices"]:
                        if isinstance(raw, dict) and raw.get("voice_id") in allowed:
                            voice = public_voice(raw)
                            if voice:
                                found[voice.voice_id] = voice
                    if not data.get("has_more") or len(found) == len(ids):
                        break
                    token = data.get("next_page_token")
                    if not isinstance(token, str) or not token or token in seen_tokens:
                        raise VoiceProviderError("Voice catalog pagination failed.")
                    seen_tokens.add(token)
                else:
                    raise VoiceProviderError("Voice catalog pagination limit reached.")
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise VoiceProviderError("ElevenLabs voice catalog is temporarily unavailable.") from exc
        return [found[i] for i in ids if i in found]

    def catalog(self):
        if not self.settings.elevenlabs_enabled:
            return VoiceCatalogResponse(enabled=False, reason="disabled")
        ids = approved_ids(self.settings)
        if not self.settings.elevenlabs_api_key.get_secret_value() or not ids:
            return VoiceCatalogResponse(enabled=False, reason="not_configured")
        with self.lock:
            # Cache approved metadata only; refresh on an allowlist change.
            key = tuple(ids)
            if key != self.cache_key or time.monotonic() >= self.expires:
                self.cached = self._fetch(ids)
                self.cache_key = key
                self.expires = time.monotonic() + self.settings.elevenlabs_catalog_ttl_seconds
            return VoiceCatalogResponse(enabled=True,
                reason="ready" if len(self.cached) >= 3 else "insufficient_voices",
                voices=self.cached)
