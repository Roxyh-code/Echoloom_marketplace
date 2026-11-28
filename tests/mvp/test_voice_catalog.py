import httpx
import pytest
from echoloom.config import Settings
from echoloom.voice.elevenlabs import ElevenLabsCatalog, VoiceProviderError
from test_marketplace import register_account


def raw(id):
    return {"voice_id": id, "name": "Voice " + id, "description": "Calm",
            "labels": {"gender": "female", "secret": "not public"},
            "preview_url": "https://example.com/preview.mp3", "category": "premade",
            "sharing": {"private": "not public"}}


def settings():
    return Settings(_env_file=None, elevenlabs_enabled=True,
                    elevenlabs_api_key="test-key", elevenlabs_voice_ids="a,b,c")


def test_catalog_filters_and_caches():
    calls = []
    def handler(request):
        calls.append(request)
        assert request.url.path == "/v2/voices"
        assert request.headers["xi-api-key"] == "test-key"
        assert request.url.params.get_list("voice_ids") == ["a", "b", "c"]
        return httpx.Response(200, json={"voices": [raw("c"), raw("private"), raw("a"), raw("b")], "has_more": False})
    catalog = ElevenLabsCatalog(settings(), transport=httpx.MockTransport(handler))
    result = catalog.catalog()
    assert result.reason == "ready"
    assert [v.voice_id for v in result.voices] == ["a", "b", "c"]
    assert result.voices[0].labels == {"gender": "female"}
    assert "private" not in result.model_dump_json()
    assert catalog.catalog() == result
    assert len(calls) == 1


def test_disabled_missing_config_and_provider_failure():
    s = settings()
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(403, text="private upstream error")
    catalog = ElevenLabsCatalog(s, transport=httpx.MockTransport(handler))
    s.elevenlabs_enabled = False
    assert catalog.catalog().reason == "disabled"
    s.elevenlabs_enabled = True
    s.elevenlabs_voice_ids = ""
    assert catalog.catalog().reason == "not_configured"
    assert not calls
    s.elevenlabs_voice_ids = "a,b,c"
    with pytest.raises(VoiceProviderError, match="temporarily unavailable"):
        catalog.catalog()


def test_catalog_requires_login_and_is_off_by_default(setup):
    client = setup[0]
    setup[3].elevenlabs_enabled = False
    assert client.get("/api/voice/catalog").status_code == 401
    register_account(setup)
    assert client.get("/api/voice/catalog").json() == {"enabled": False, "reason": "disabled", "voices": []}


def test_unavailable_and_invalid_previews_are_excluded():
    expired = raw("a") | {"disable_at_unix": 1}
    invalid = raw("b") | {"preview_url": "http://example.com/not-secure"}
    transport = httpx.MockTransport(lambda _: httpx.Response(200, json={"voices": [expired, invalid, raw("c")]}))
    result = ElevenLabsCatalog(settings(), transport=transport).catalog()
    assert result.reason == "insufficient_voices"
    assert [v.voice_id for v in result.voices] == ["c"]
