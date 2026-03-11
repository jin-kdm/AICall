import os

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database (PostgreSQL for production, SQLite for local dev)
    database_url: str = "sqlite+aiosqlite:///./aicall.db"

    # OpenAI
    openai_api_key: str = ""

    # Twilio
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""

    # TTS settings
    tts_provider: str = "openai"
    tts_voice: str = "alloy"
    tts_model: str = "tts-1"

    # STT settings
    stt_provider: str = "openai"
    stt_model: str = "whisper-1"

    # Branch decision settings
    branch_model: str = "gpt-4o-mini"

    # VAD settings
    vad_aggressiveness: int = 2
    vad_silence_timeout_ms: int = 800
    vad_min_speech_ms: int = 250

    # Audio cache
    audio_cache_dir: str = "./audio_cache"

    # Supabase Storage (for cloud audio cache)
    supabase_url: str = ""
    supabase_key: str = ""
    supabase_storage_bucket: str = "audio-cache"

    # Server
    server_host: str = "0.0.0.0"
    server_port: int = 8000
    ws_base_url: str = ""

    # CORS
    cors_origins: str = "http://localhost:5173"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def use_supabase_storage(self) -> bool:
        return bool(self.supabase_url and self.supabase_key)

    @property
    def effective_ws_base_url(self) -> str:
        """Auto-detect WebSocket URL from Railway or fall back to configured value."""
        # Railway provides RAILWAY_PUBLIC_DOMAIN automatically — always prefer it
        # (WS_BASE_URL env var may contain a stale domain after redeployment)
        railway_domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN")
        if railway_domain:
            return f"wss://{railway_domain}"
        if self.ws_base_url:
            return self.ws_base_url
        return "wss://localhost:8000"


settings = Settings()
