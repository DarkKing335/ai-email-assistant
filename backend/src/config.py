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

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = Field(
        default="sqlite+aiosqlite:///./email_assistant.db",
        description="SQLAlchemy async database URL.",
    )
    database_echo: bool = Field(
        default=False,
        description="Echo all SQL statements (verbose; only for debugging).",
    )

    # ── AutoReply — Whitelist cache ──────────────────────────────────────────
    whitelist_cache_ttl_seconds: int = Field(
        default=60,
        ge=0,
        description="TTL for the in-memory whitelist match cache. 0 = disabled.",
    )

    # ── AutoReply — Workflow / retry ─────────────────────────────────────────
    auto_reply_max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Max retry attempts for transient workflow failures.",
    )
    auto_reply_retry_delay_seconds: float = Field(
        default=1.0,
        ge=0,
        le=60,
        description="Base delay (seconds) between retry attempts (exponential back-off).",
    )
    auto_reply_workflow_delay_seconds: float = Field(
        default=0.0,
        ge=0,
        description="Configurable processing delay before draft generation starts.",
    )
    whitelist_rescan_lookback_hours: int = Field(
        default=24,
        ge=0,
        le=8760,
        description=(
            "How far back a newly added whitelist rule reaches when re-examining "
            "mail already filed as skipped. Bounded on purpose, like "
            "`gmail_initial_lookback_minutes`: adding a rule should pick up the "
            "mail you just watched arrive, not draft replies to a year of "
            "archive. 0 disables rescanning entirely."
        ),
    )

    # ── Bulk import limits ────────────────────────────────────────────────────
    bulk_import_max_rows: int = Field(
        default=10_000,
        ge=1,
        description="Maximum number of rows accepted in a single CSV/Excel import.",
    )

    # ── Gmail OAuth ───────────────────────────────────────────────────────────
    # Credentials come from a Google Cloud OAuth 2.0 "Web application" client.
    # See docs/setup/gmail-oauth.md.
    google_client_id: str | None = None
    google_client_secret: SecretStr | None = None
    google_redirect_uri: str = Field(
        default="http://localhost:8000/api/v1/gmail/auth/callback",
        description=(
            "Must match a redirect URI registered on the OAuth client exactly, "
            "including scheme, host, port and path."
        ),
    )
    google_oauth_scopes: str = Field(
        default=(
            "https://www.googleapis.com/auth/gmail.readonly "
            "https://www.googleapis.com/auth/gmail.compose "
            "https://www.googleapis.com/auth/userinfo.email"
        ),
        description=(
            "Space-separated. readonly polls the inbox; compose creates drafts "
            "later; userinfo.email names the connected account in the UI. "
            "Both Gmail scopes are 'sensitive' — fine in Testing mode, but they "
            "require verification before publishing."
        ),
    )

    # ── Gmail polling ─────────────────────────────────────────────────────────
    gmail_poll_interval_seconds: int = Field(
        default=60,
        ge=15,
        description=(
            "How often to ask Gmail for new mail. Distinct from the extension's "
            "refresh interval — this one spends API quota."
        ),
    )
    gmail_poll_query: str = Field(
        default="in:inbox -in:chats",
        description="Gmail search query defining which messages are considered.",
    )
    gmail_max_results_per_poll: int = Field(
        default=25,
        ge=1,
        le=100,
        description="Cap on messages fetched per poll, so a backlog cannot stampede.",
    )
    gmail_initial_lookback_minutes: int = Field(
        default=60,
        ge=0,
        description=(
            "On first connect, how far back to look. Deliberately short: "
            "connecting an account should not draft replies to a month of mail."
        ),
    )

    @property
    def has_google_oauth(self) -> bool:
        return bool(
            self.google_client_id
            and self.google_client_secret
            and self.google_client_secret.get_secret_value().strip()
        )

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
