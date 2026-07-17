from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Single source of truth for backend configuration.

    Both the summarizer service and the orchestrator use the same provider order:
    Groq (primary) then Gemini (fallback). All provider config is shared.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Groq (primary: summarizer + orchestrator routing) ---
    groq_api_key: SecretStr | None = None
    groq_model: str | None = None

    # --- Gemini (fallback: summarizer + orchestrator) ---
    gemini_api_key: SecretStr | None = None
    gemini_model: str | None = None

    # --- Summarizer tuning ---
    summarizer_max_messages: int = Field(default=20, ge=1, le=100)
    summarizer_max_normalized_chars: int = Field(default=100_000, ge=1_000)
    summarizer_provider_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    summarizer_retry_delay_seconds: float = Field(default=0.25, ge=0, le=30)

    # --- Orchestrator tuning ---
    # Routing decisions below this confidence degrade to the safe fallback template.
    confidence_threshold: float = Field(default=0.6, ge=0, le=1)

    @property
    def has_groq(self) -> bool:
        # Groq needs both a key and a model (no sensible default model).
        return bool(
            self.groq_api_key
            and self.groq_api_key.get_secret_value().strip()
            and self.groq_model
        )

    @property
    def has_gemini(self) -> bool:
        return bool(self.gemini_api_key and self.gemini_api_key.get_secret_value().strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
