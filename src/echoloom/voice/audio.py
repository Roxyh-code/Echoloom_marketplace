"""On-demand audio of server-authorized revealed story text."""
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Lock
import httpx
from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from ..db import RehearsalScene
from ..scene_access import preview, total_limit
from ..rehearsal_domain import history, reading_view, version
from .elevenlabs import BASE, ID, VoiceProviderError
from .models import VoiceUsage

MAX_BYTES = 8 * 1024 * 1024

def visible_block(db, owner, scene_id, body, narrator):
    row = db.get(RehearsalScene, str(scene_id))
    if not owner or not row or row.owner_id != owner:
        raise HTTPException(404, "Scene not found.")
    doc = preview(row.document, total_limit(db,row))
    doc, v = reading_view(doc, version(doc,body.version_id))
    for n in history(doc,v["head"]):
        if n["id"] != body.node_id:
            continue
        for b in n["blocks"]:
            if b["id"] != body.block_id:
                continue
            if b["type"] == "dialogue":
                actor = next((a for a in doc["cast"] if a["id"] == b["character_id"]), {})
                voice = actor.get("voice_identity") or {}
                vid = voice.get("voice_id") if voice.get("provider") == "elevenlabs" else None
            else:
                vid = narrator
            if not isinstance(vid,str) or not ID.fullmatch(vid):
                raise HTTPException(409,"No approved voice for this passage.")
            text = b["text"].strip()
            if not text or len(text)>2000:
                raise HTTPException(422,"Passage must contain 1–2000 characters.")
            return vid,text
    raise HTTPException(404,"Passage is not in the revealed story.")

def reserve(db, owner, amount, settings):
    day = datetime.now(UTC).date().isoformat()
    for scope, limit in [("global",settings.elevenlabs_audio_global_daily_chars),("account:"+owner,settings.elevenlabs_audio_daily_chars)]:
        if amount>limit:
            db.rollback()
            raise HTTPException(429,"Daily audio generation limit reached.")
        if db.get(VoiceUsage,(scope,day)) is None:
            try:
                with db.begin_nested():
                    db.add(VoiceUsage(scope=scope,day=day,characters=0))
                    db.flush()
            except IntegrityError:
                pass
        changed=db.execute(update(VoiceUsage).where(VoiceUsage.scope==scope,VoiceUsage.day==day,
            VoiceUsage.characters<=limit-amount).values(characters=VoiceUsage.characters+amount))
        if changed.rowcount!=1:
            db.rollback()
            raise HTTPException(429,"Daily audio generation limit reached.")
    db.commit()

class AudioService:
    def __init__(self,settings,catalog,factory):
        self.settings=settings
        self.catalog=catalog
        self.factory=factory
        self.lock=Lock()
    def enabled(self):
        return bool(self.settings.elevenlabs_enabled and self.settings.elevenlabs_audio_enabled
                    and self.settings.elevenlabs_api_key.get_secret_value())
    def synthesize(self,voice,text):
        try:
            with httpx.Client(base_url=BASE,timeout=self.settings.elevenlabs_timeout_seconds,
                              follow_redirects=False,headers={"xi-api-key":self.settings.elevenlabs_api_key.get_secret_value()}) as client:
                with client.stream("POST","/v1/text-to-speech/"+voice,params={"output_format":"mp3_44100_128"},
                        json={"text":text,"model_id":self.settings.elevenlabs_tts_model}) as r:
                    r.raise_for_status()
                    if not r.headers.get("content-type","").lower().startswith("audio/"):
                        raise VoiceProviderError("Unexpected audio response.")
                    data=bytearray()
                    for chunk in r.iter_bytes():
                        data.extend(chunk)
                        if len(data)>MAX_BYTES:
                            raise VoiceProviderError("Audio response too large.")
                    if not data:
                        raise VoiceProviderError("Empty audio response.")
                    return bytes(data)
        except httpx.HTTPError:
            raise VoiceProviderError("ElevenLabs audio generation failed. Check access or credits.") from None
    def audio(self,owner,scene_id,body):
        if not self.enabled():
            raise HTTPException(503,"Story audio is disabled.")
        with self.factory() as db:
            voice,text=visible_block(db,owner,scene_id,body,self.settings.elevenlabs_narrator_voice_id)
        return self.cached_audio(owner, str(scene_id), voice, text)

    def cached_audio(self, owner, scope, voice, text):
        """Shared quota and cache; callers authorize text and scope first."""
        if not self.enabled():
            raise HTTPException(503, "Voice synthesis is disabled.")
        catalog=self.catalog.catalog()
        if not catalog.enabled or voice not in {v.voice_id for v in catalog.voices}:
            raise HTTPException(409,"This voice is no longer approved.")
        digest=hashlib.sha256(json.dumps([owner,scope,voice,text,self.settings.elevenlabs_tts_model,
                "mp3_44100_128"],ensure_ascii=False).encode()).hexdigest()
        target=Path(self.settings.elevenlabs_audio_directory)/(digest+".mp3")
        with self.lock:
            if target.is_file() and 0<target.stat().st_size<=MAX_BYTES:
                return target.read_bytes(),True
            with self.factory() as db:
                reserve(db,owner,len(text),self.settings)
            data=self.synthesize(voice,text)
            target.parent.mkdir(parents=True,exist_ok=True)
            tmp=None
            try:
                with NamedTemporaryFile(dir=target.parent,delete=False) as f:
                    tmp=Path(f.name)
                    f.write(data)
                os.replace(tmp,target)
            finally:
                if tmp:
                    tmp.unlink(missing_ok=True)
            return data,False
