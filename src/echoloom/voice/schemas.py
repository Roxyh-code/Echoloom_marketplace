from typing import Literal
from pydantic import Field
from ..schemas import Model

VoiceId = str


class VoiceIdentity(Model):
    """Only a selected stable identity, not an API key or preview URL.

    Persistence and owner-controlled confirmation are introduced in phase 18B.
    """
    provider: Literal["elevenlabs"] = "elevenlabs"
    voice_id: VoiceId = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=120)


class CatalogVoice(VoiceIdentity):
    description: str = Field(default="", max_length=1000)
    labels: dict[str, str] = Field(default_factory=dict)
    preview_url: str
    category: str = ""


class VoiceCatalogResponse(Model):
    enabled: bool
    reason: Literal["disabled", "not_configured", "ready", "insufficient_voices"]
    voices: list[CatalogVoice] = Field(default_factory=list)


class VoiceSelection(Model):
    voice_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    expected_profile_version: int = Field(ge=1)


class VoiceRankItem(Model):
    voice_id: str
    reason: str = Field(min_length=1, max_length=240)


class VoiceRanking(Model):
    choices: list[VoiceRankItem] = Field(min_length=3, max_length=3)
