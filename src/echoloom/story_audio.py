"""On-demand speech for already revealed, authorized scene text."""
import hashlib
import re
import threading
import time
from collections import OrderedDict, deque
from uuid import UUID

import httpx
from fastapi import HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from .db import RehearsalScene
from .rehearsal_domain import history, sentences
from .scene_access import total_limit


class SpeechRequest(BaseModel):
    version_id: str = Field(max_length=60)
    block_id: str = Field(max_length=60)
    sentence_count: int = Field(ge=1, le=100)


def speech_text(db, row, body):
    doc = row.document
    v = doc.get("versions", {}).get(body.version_id)
    if not v:
        raise HTTPException(404, "Story version not found.")
    cap = total_limit(db, row)
    left = v.get("revealed", 0)
    if cap is not None:
        left = min(left, cap)
    for node in history(doc, v["head"]):
        for block in node["blocks"]:
            units = sentences(block["text"])
            if block["id"] == body.block_id:
                if body.sentence_count > min(left, len(units)):
                    raise HTTPException(403, "Reveal the passage first.")
                text = "".join(units[:body.sentence_count]).strip()
                if not text or len(text) > 2000:
                    raise HTTPException(422, "Passage is too long.")
                slot = next((a.get("slot", i) for i, a in enumerate(doc["cast"])
                    if a["id"] == block.get("character_id")), None)
                return text, slot if block["type"] != "narration" else None
            left -= len(units)
    raise HTTPException(404, "Passage not found.")


def register_story_audio(app, factory, settings):
    # Bounded, process-local cache; keys include owner and exact authorized text.
    cache = OrderedDict()
    attempts = {}
    guard = threading.Lock()

    def configured():
        return bool(settings.elevenlabs_api_key.get_secret_value() and
                    settings.elevenlabs_voice_a and settings.elevenlabs_voice_b)

    @app.get("/api/story-audio/status")
    def audio_status(request: Request):
        return {"available": configured() and bool(getattr(request.state, "user_id", None))}

    @app.post("/api/story-audio/{scene_id}")
    def audio(scene_id: UUID, body: SpeechRequest, request: Request):
        owner = getattr(request.state, "user_id", None)
        if not owner:
            raise HTTPException(401, "Sign in first.")
        if not configured():
            raise HTTPException(503, "Story audio is not configured.")
        with factory() as db:
            row = db.get(RehearsalScene, str(scene_id))
            if not row or row.owner_id != owner:
                raise HTTPException(404, "Scene not found.")
            text, slot = speech_text(db, row, body)
        voice = (settings.elevenlabs_voice_a if slot == 0 else settings.elevenlabs_voice_b
                 if slot == 1 else settings.elevenlabs_voice_narrator or settings.elevenlabs_voice_a)
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", voice):
            raise HTTPException(503, "Invalid voice configuration.")
        key = (owner, voice, settings.elevenlabs_model, hashlib.sha256(text.encode()).hexdigest())
        with guard:
            if key in cache:
                cache.move_to_end(key)
                return Response(cache[key], media_type="audio/mpeg", headers={"Cache-Control":"private, no-store"})
            now = time.monotonic()
            # Prevent unbounded owner map and expensive bursts in local demo.
            for account in list(attempts):
                if not attempts[account] or now - attempts[account][-1] >= 3600:
                    del attempts[account]
            q = attempts.setdefault(owner, deque())
            while q and now - q[0] >= 3600:
                q.popleft()
            if len(q) >= 60:
                raise HTTPException(429, "Hourly story audio limit reached.")
            q.append(now)
        try:
            with httpx.Client(timeout=45, follow_redirects=False) as client:
                with client.stream("POST", "https://api.elevenlabs.io/v1/text-to-speech/" + voice,
                    params={"output_format":"mp3_44100_128"},
                    headers={"xi-api-key":settings.elevenlabs_api_key.get_secret_value(), "Accept":"audio/mpeg"},
                    json={"text":text, "model_id":settings.elevenlabs_model}) as r:
                    r.raise_for_status()
                    if not r.headers.get("content-type", "").startswith("audio/"):
                        raise ValueError("Invalid audio")
                    data = bytearray()
                    for chunk in r.iter_bytes():
                        data.extend(chunk)
                        if len(data) > 4_000_000:
                            raise ValueError("Audio too large")
            if not data:
                raise ValueError("Empty audio")
        except (httpx.HTTPError, ValueError):
            raise HTTPException(502, "ElevenLabs could not generate audio. Check credits and voice configuration.") from None
        result = bytes(data)
        with guard:
            cache[key] = result
            while len(cache) > 32 or sum(map(len, cache.values())) > 24_000_000:
                cache.popitem(last=False)
        return Response(result, media_type="audio/mpeg", headers={"Cache-Control":"private, no-store"})
