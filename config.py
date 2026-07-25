"""Application configuration loaded from environment variables."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
IMPORTS_DIR = DATA_DIR / "imports"
ORIGINALS_DIR = DATA_DIR / "originals"
LOGS_DIR = DATA_DIR / "logs"
EXPORTS_DIR = DATA_DIR / "exports"
DATABASE_PATH = DATA_DIR / "session.db"


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    openai_api_key: str | None
    openai_model: str = "gpt-4o-mini"
    admin_user_ids: frozenset[int] = frozenset()

    # Telegram Mini App
    mini_app_host: str = "127.0.0.1"
    mini_app_port: int = 8080
    mini_app_url: str | None = None
    mini_app_auth_max_age_seconds: int = 86400
    mini_app_static_dir: Path | None = None

    # Failover Provider Keys
    gemini_api_key: str | None = None
    gemini_model: str | None = None

    github_token: str | None = None
    github_model: str | None = None

    openrouter_api_key: str | None = None
    openrouter_model: str | None = None

    groq_api_key: str | None = None
    groq_model: str | None = None

    deepseek_api_key: str | None = None
    deepseek_model: str | None = None


def ensure_directories() -> None:
    """Create runtime directories if they are missing."""
    for path in (DATA_DIR, IMPORTS_DIR, ORIGINALS_DIR, LOGS_DIR, EXPORTS_DIR):
        path.mkdir(parents=True, exist_ok=True)


def load_settings() -> Settings:
    """Load settings from .env and process environment variables."""
    load_dotenv(BASE_DIR / ".env")

    import os

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip() or None
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    admin_ids_raw = os.getenv("ADMIN_TELEGRAM_USER_IDS", "").strip()
    admin_user_ids = frozenset(
        int(value.strip())
        for value in admin_ids_raw.split(",")
        if value.strip().isdigit()
    )

    # Mini App settings
    host = os.getenv("MINI_APP_HOST", "127.0.0.1").strip()
    port_str = os.getenv("MINI_APP_PORT", "8080").strip()
    port = int(port_str) if port_str.isdigit() else 8080
    # Allow overriding with a manually set URL (e.g., from ngrok in dev)
    # but default to the self-hosted URL.
    url = os.getenv("MINI_APP_URL") or f"http://{host}:{port}"
    
    # Default static dir to the built frontend assets relative to the project root
    static_dir_default = str(BASE_DIR / "frontend" / "dist")
    mini_app_static_dir_str = os.getenv("MINI_APP_STATIC_DIR", static_dir_default).strip()
    mini_app_static_dir = Path(mini_app_static_dir_str)

    return Settings(
        telegram_bot_token=token,
        openai_api_key=openai_key,
        openai_model=model,
        admin_user_ids=admin_user_ids,
        mini_app_host=host,
        mini_app_port=port,
        mini_app_url=url,
        mini_app_auth_max_age_seconds=int(
            (os.getenv("MINI_APP_AUTH_MAX_AGE_SECONDS", "").strip() or "86400")
        ),
        mini_app_static_dir=mini_app_static_dir,
        gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip() or None,
        gemini_model=os.getenv("GEMINI_MODEL", "").strip() or None,
        github_token=os.getenv("GITHUB_TOKEN", "").strip() or None,
        github_model=os.getenv("GITHUB_MODEL", "").strip() or None,
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY", "").strip() or None,
        openrouter_model=os.getenv("OPENROUTER_MODEL", "").strip() or None,
        groq_api_key=os.getenv("GROQ_API_KEY", "").strip() or None,
        groq_model=os.getenv("GROQ_MODEL", "").strip() or None,
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", "").strip() or None,
        deepseek_model=os.getenv("DEEPSEEK_MODEL", "").strip() or None,
    )
