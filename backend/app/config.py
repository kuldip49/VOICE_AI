"""Application configuration loaded from environment variables / .env file.

Secrets (API keys) live ONLY here on the backend and are never sent to the frontend.
"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "SalesPilot AI"
    environment: str = "development"

    # Database. SQLite for the MVP; swap to postgresql+psycopg://... in production.
    database_url: str = f"sqlite:///{(DATA_DIR / 'salespilot.db').as_posix()}"

    # LLM provider: "auto" prefers configured Grok, then Gemini, then reachable Ollama.
    llm_provider: str = "auto"  # auto | grok | gemini | ollama | demo
    grok_api_key: str = ""
    grok_model: str = "grok-4.7"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"
    gemini_embedding_model: str = "gemini-embedding-001"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    llm_timeout_seconds: float = 30.0

    # Inbound phone calls (Exotel AgentStream + Sarvam realtime speech)
    exotel_account_sid: str = ""
    exotel_api_key: str = ""
    exotel_api_token: str = ""
    exotel_phone_number: str = ""  # ExoPhone in E.164 format
    exotel_public_wss_url: str = ""  # public WSS URL configured in Exotel's Voicebot applet
    exotel_sample_rate: int = 16000
    sarvam_api_key: str = ""
    sarvam_stt_model: str = "saaras:v4"
    sarvam_tts_model: str = "bulbul:v3"
    sarvam_voice_en: str = "ishita"
    sarvam_voice_hi: str = "priya"

    # Security
    admin_api_key: str = ""  # when set, CRM/admin endpoints require header X-Admin-Key
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    max_upload_mb: int = 5
    rate_limit_per_minute: int = 60

    # Business calendar
    timezone: str = "Asia/Kolkata"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
