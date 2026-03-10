from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
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

    # Server
    server_host: str = "0.0.0.0"
    server_port: int = 8000
    ws_base_url: str = "wss://localhost:8000"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
