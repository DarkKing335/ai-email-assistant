"""
Config — đọc cấu hình từ biến môi trường (.env).

Dùng python-dotenv nếu có; nếu không cài cũng không sao (chỉ đọc os.environ).
"""
import os

try:
    from dotenv import load_dotenv
    # Nạp .env ở thư mục backend/ (đi lên 3 cấp: config.py -> orchestrator -> src -> backend)
    _BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    load_dotenv(os.path.join(_BACKEND_DIR, ".env"))
except ImportError:
    pass


class Settings:
    # --- OpenAI (primary) ---
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "").strip()
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

    # --- Gemini (fallback) ---
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()

    # --- Orchestrator behaviour ---
    # Dưới ngưỡng này thì degrade về GENERAL_GREETING.
    CONFIDENCE_THRESHOLD: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.6"))

    @property
    def has_openai(self) -> bool:
        return bool(self.OPENAI_API_KEY)

    @property
    def has_gemini(self) -> bool:
        return bool(self.GEMINI_API_KEY)


settings = Settings()
