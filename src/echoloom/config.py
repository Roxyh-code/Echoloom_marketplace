from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./work/echoloom.db"
    image_directory: Path = Path("work/portraits")
    llm_provider: str = "openai"
    llm_model: str = ""
    llm_api_key: SecretStr = SecretStr("")
    image_provider: str = "openai"
    image_model: str = ""
    # First portrait only: low is faster, medium balances quality/speed.
    # Set IMAGE_INITIAL_QUALITY=auto to retain provider defaults.
    image_initial_quality: Literal["auto", "low", "medium", "high"] = "medium"
    image_api_key: SecretStr = SecretStr("")
    max_profile_input_chars: int = Field(5000, ge=100, le=20000)
    max_chat_context_tokens: int = Field(12000, ge=2000, le=64000)
    max_output_tokens: int = Field(1500, ge=128, le=8000)
    max_image_bytes: int = Field(10 * 1024 * 1024, ge=1024, le=25 * 1024 * 1024)
    image_requests_per_hour: int = Field(6, ge=1, le=100)
    api_timeout_seconds: float = Field(90, ge=1, le=300)
    story_max_output_tokens: int = Field(3500, ge=1000, le=8000)
    story_max_context_tokens: int = Field(24000, ge=6000, le=64000)

    # Off by default for baseline comparison and existing deployments.
    rehearsal_consistency_enabled: bool = False
    rehearsal_quality_timeout_seconds: float = Field(150, ge=60, le=300)

    # Optional rehearsal experiment. No Mem0 import, files or API calls when off.
    memory_enabled: bool = False
    memory_directory: Path = Path("work/memory")
    memory_llm_model: str = "gpt-4.1-mini"
    memory_embedding_model: Literal["text-embedding-3-small"] = "text-embedding-3-small"
    memory_top_k: int = Field(5, ge=1, le=20)
    memory_context_bytes: int = Field(3000, ge=500, le=12000)
    memory_timeout_seconds: float = Field(15, ge=1, le=60)
    memory_index_batch_size: int = Field(4, ge=1, le=20)

    # Independent, off-by-default Character Chat memory experiment.
    chat_memory_enabled: bool = False
    chat_memory_directory: Path = Path("work/chat-memory")
    chat_memory_context_bytes: int = Field(2400, ge=300, le=12000)
    chat_memory_backfill_limit: int = Field(50, ge=0, le=2000)

    app_origin: str = "http://127.0.0.1:3000"
    google_client_id: str = ""
    google_client_secret: SecretStr = SecretStr("")
    google_redirect_uri: str = (
        "http://127.0.0.1:8000/api/integrations/google-calendar/callback"
    )
    calendar_key_file: Path = Path("work/secrets/calendar.key")
    calendar_encryption_key: SecretStr = SecretStr("")
    companion_worker_enabled: bool = False
    allow_additional_accounts: bool = False

    firecrawl_enabled: bool = False
    firecrawl_api_key: SecretStr = SecretStr("")
    firecrawl_max_credits: int = Field(100, ge=10, le=500)
    firecrawl_timeout_seconds: float = Field(90, ge=10, le=150)
    firecrawl_daily_runs_per_account: int = Field(5, ge=1, le=100)
    firecrawl_daily_runs_global: int = Field(20, ge=1, le=500)

    # Existing ElevenLabs voices only; opt in after reviewing voice rights.
    elevenlabs_enabled: bool = False
    elevenlabs_api_key: SecretStr = SecretStr("")
    elevenlabs_voice_ids: str = ""
    elevenlabs_catalog_ttl_seconds: int = Field(3600, ge=60, le=86400)
    elevenlabs_timeout_seconds: float = Field(15, ge=1, le=60)

    elevenlabs_audio_enabled: bool = False
    elevenlabs_tts_model: Literal["eleven_multilingual_v2", "eleven_flash_v2_5", "eleven_v3"] = "eleven_multilingual_v2"
    elevenlabs_narrator_voice_id: str = ""
    elevenlabs_audio_directory: Path = Path("work/voice-audio")
    elevenlabs_audio_daily_chars: int = Field(5000, ge=1, le=100000)
    elevenlabs_audio_global_daily_chars: int = Field(20000, ge=1, le=1000000)

    # Devnet checkout remains opt-in and fails closed without wallet verification.
    solana_payments_enabled: bool = False
    solana_creator_self_service_enabled: bool = False
    solana_rpc_url: str = "https://api.devnet.solana.com"
    solana_program_id: str = ""
    solana_mint: str = ""
    solana_config_pda: str = ""
    solana_platform_wallet: str = ""
    solana_deployment_domain_hash: str = ""
    solana_expected_signer_pubkey: str = ""
    solana_backend_signer_path: str = ""
    # Finalized is safest; confirmed is an explicit Devnet demo override.
    solana_payment_commitment: Literal["confirmed", "finalized"] = "finalized"
