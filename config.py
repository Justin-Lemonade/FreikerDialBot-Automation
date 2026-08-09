"""Application configuration loaded from environment variables."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

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
    # Off by default -- when False (the default), every /api endpoint
    # except the static frontend itself requires a valid Authorization:
    # tma <initData> header. This should only ever be set True for local
    # browser testing outside a real Telegram client, where no initData
    # exists at all. See MINI_APP_API.md for the full auth model.
    mini_app_allow_anonymous: bool = False

    @property
    def mini_app_allowed_origins(self) -> frozenset[str]:
        """Origins the Mini App API will echo back in
        Access-Control-Allow-Origin, instead of the previous unconditional
        '*'. '*' let any website's JS read responses from this API in a
        browser that sends credentials/initData -- CORS is a browser-only
        protection (server-to-server or curl requests were never affected
        either way), but there is no reason to disable it for arbitrary
        third-party origins when the real set of legitimate callers is
        small and known: the deployed Mini App's own public URL (whatever
        ngrok/host serves it in production) plus the Vite dev server used
        during local frontend development.
        """
        origins = {"http://localhost:5173", "http://127.0.0.1:5173"}
        if self.mini_app_url:
            parsed = urlparse(self.mini_app_url)
            if parsed.scheme and parsed.netloc:
                origins.add(f"{parsed.scheme}://{parsed.netloc}")
        origins.update(self.mini_app_extra_allowed_origins)
        return frozenset(origins)

    # Comma-separated extra origins (e.g. a custom domain fronting the
    # Mini App) to allow beyond mini_app_url and the Vite dev server --
    # set via MINI_APP_EXTRA_ALLOWED_ORIGINS, not required for the
    # common ngrok/self-hosted case.
    mini_app_extra_allowed_origins: frozenset[str] = frozenset()

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
    # Explicit opt-in only -- see the Settings field docstring above.
    mini_app_allow_anonymous = os.getenv("MINI_APP_ALLOW_ANONYMOUS", "").strip() == "1"
    extra_origins_raw = os.getenv("MINI_APP_EXTRA_ALLOWED_ORIGINS", "").strip()
    mini_app_extra_allowed_origins = frozenset(
        origin.strip() for origin in extra_origins_raw.split(",") if origin.strip()
    )

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
        mini_app_allow_anonymous=mini_app_allow_anonymous,
        mini_app_extra_allowed_origins=mini_app_extra_allowed_origins,
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
