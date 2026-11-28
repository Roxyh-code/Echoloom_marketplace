"""Operator-only inventory of voices visible to the configured API account."""
import json
import httpx
from echoloom.config import Settings
from echoloom.voice.elevenlabs import BASE, public_voice

def main():
    settings = Settings()
    key = settings.elevenlabs_api_key.get_secret_value()
    if not key:
        raise SystemExit("Set ELEVENLABS_API_KEY in the local .env first.")
    token = None
    seen = set()
    output = []
    try:
        with httpx.Client(base_url=BASE, timeout=settings.elevenlabs_timeout_seconds,
                          follow_redirects=False, headers={"xi-api-key": key}) as client:
            for _ in range(20):
                params = {"page_size": 100}
                if token:
                    params["next_page_token"] = token
                response = client.get("/v2/voices", params=params)
                response.raise_for_status()
                data = response.json()
                for raw in data["voices"]:
                    voice = public_voice(raw)
                    if voice:
                        output.append(voice.model_dump())
                if not data.get("has_more"):
                    break
                token = data.get("next_page_token")
                if not isinstance(token, str) or not token or token in seen:
                    raise ValueError("invalid pagination")
                seen.add(token)
            else:
                raise ValueError("inventory pagination limit")
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        raise SystemExit("Voice inventory unavailable; check API key and account permissions.") from None
    print(json.dumps(output, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
