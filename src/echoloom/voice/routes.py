from fastapi import HTTPException, Request
from .elevenlabs import ElevenLabsCatalog, VoiceProviderError
from .schemas import VoiceCatalogResponse


def register_voice(app, settings):
    catalog = ElevenLabsCatalog(settings)

    @app.get("/api/voice/catalog", response_model=VoiceCatalogResponse)
    def voice_catalog(request: Request):
        if not getattr(request.state, "user_id", None):
            raise HTTPException(401, "Sign in to access character voices.")
        try:
            return catalog.catalog()
        except VoiceProviderError as exc:
            raise HTTPException(503, str(exc)) from None
