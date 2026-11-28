from collections import OrderedDict
from threading import Lock
from uuid import UUID
from fastapi import HTTPException, Request, Response
from sqlalchemy import select, update
from ..db import Character, ProfileRevision, now
from ..schemas import Profile
from .elevenlabs import ElevenLabsCatalog, VoiceProviderError
from .schemas import VoiceCatalogResponse, VoiceIdentity, VoiceSelection, AudioRequest
from .audio import AudioService
from .matching import recommend


def register_voice(app, settings, factory):
    catalog = ElevenLabsCatalog(settings)
    audio = AudioService(settings,catalog,factory)
    cache = OrderedDict()
    gate = Lock()

    def owner(request):
        uid = getattr(request.state, "user_id", None)
        if not uid:
            raise HTTPException(401, "Sign in to access character voices.")
        return uid

    def own(db, request, cid):
        account = owner(request)
        char = db.get(Character, str(cid))
        if not char or char.owner_id != account or char.archived:
            raise HTTPException(404, "Character not found.")
        return char

    def get_catalog():
        try:
            return catalog.catalog()
        except VoiceProviderError as exc:
            raise HTTPException(503, str(exc)) from None

    @app.get("/api/voice/catalog", response_model=VoiceCatalogResponse)
    def voice_catalog(request: Request):
        owner(request)
        return get_catalog()

    @app.get("/api/voice/characters/{cid}")
    def character_voice(cid: UUID, request: Request):
        with factory() as db:
            char = own(db, request, cid)
            return {"enabled": settings.elevenlabs_enabled, "voice": char.voice_identity,
                    "profile_version": char.current_profile_version}

    @app.post("/api/voice/characters/{cid}/recommend")
    def recommendations(cid: UUID, request: Request):
        with factory() as db:
            char = own(db, request, cid)
            profile = db.scalar(select(ProfileRevision).where(ProfileRevision.character_id == char.id,
                ProfileRevision.version == char.current_profile_version))
            if not profile:
                raise HTTPException(409, "Character profile missing.")
            current = char.current_profile_version
            data = Profile.model_validate(profile.profile_json)
        available = get_catalog()
        if available.reason != "ready":
            return {"reason": available.reason, "choices": [], "profile_version": current}
        key = (str(cid), current, tuple(v.model_dump_json() for v in available.voices))
        # Single-process demo cache avoids re-running ranking on refresh.
        with gate:
            if key not in cache:
                choices, method = recommend(data, available.voices, app.state.text)
                cache[key] = {"reason": method, "choices": choices, "profile_version": current}
                if len(cache) > 256:
                    cache.popitem(last=False)
            cache.move_to_end(key)
            return cache[key]

    @app.put("/api/voice/characters/{cid}")
    def select_voice(cid: UUID, body: VoiceSelection, request: Request):
        with factory() as db:
            char = own(db, request, cid)
            if char.current_profile_version != body.expected_profile_version:
                raise HTTPException(409, "Character changed. Refresh voice suggestions.")
        available = get_catalog()
        chosen = next((v for v in available.voices if v.voice_id == body.voice_id), None)
        if not available.enabled or chosen is None:
            raise HTTPException(422, "Voice is not in the approved catalog.")
        identity = VoiceIdentity(voice_id=chosen.voice_id, name=chosen.name).model_dump()
        with factory() as db:
            char = own(db, request, cid)
            result = db.execute(update(Character).where(Character.id == char.id,
                Character.owner_id == owner(request), Character.archived == False,
                Character.current_profile_version == body.expected_profile_version)
                .values(voice_identity=identity, updated_at=now()))
            if result.rowcount != 1:
                raise HTTPException(409, "Character changed. Refresh voice suggestions.")
            db.commit()
        return {"voice": identity}


    @app.get("/api/voice/audio/status")
    def audio_status(request: Request):
        owner(request)
        return {"enabled":audio.enabled(),"narration":bool(settings.elevenlabs_narrator_voice_id)}

    @app.post("/api/voice/scenes/{scene_id}/audio")
    def story_audio(scene_id: UUID, body: AudioRequest, request: Request):
        try:
            data,cached=audio.audio(owner(request),scene_id,body)
            return Response(content=data,media_type="audio/mpeg",headers={
                "Cache-Control":"private, no-store","X-Audio-Cache":"hit" if cached else "miss"})
        except VoiceProviderError as exc:
            raise HTTPException(503,str(exc)) from None
