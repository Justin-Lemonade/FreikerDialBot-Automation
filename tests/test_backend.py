from __future__ import annotations

from config import Settings
from database import Database
from backend import build_backend


def _settings() -> Settings:
    return Settings(telegram_bot_token="x", openai_api_key=None)


def test_build_backend_wires_consistent_shared_instances(tmp_path):
    database = Database(path=tmp_path / "backend.db")

    backend = build_backend(settings=_settings(), database=database)

    # All engines must share the exact same Database instance -- if two
    # different Database objects ever ended up pointing at different
    # engines, that would silently split the data two ways.
    assert backend.database is database
    assert backend.session_manager.database is database
    assert backend.queue_engine.database is database
    assert backend.importer.database is database

    # StatisticsEngine must be the one shared instance too -- SessionManager
    # and QueueEngine both need to record events through the same object.
    assert backend.session_manager.statistics is backend.statistics
    assert backend.queue_engine.statistics is backend.statistics

    # QueueEngine needs the same SessionManager the frontend will use for
    # session lifecycle, not a second independent one.
    assert backend.queue_engine.session_manager is backend.session_manager

    # Importer must be wired to the same SessionManager too, so imports
    # actually create sessions the rest of the backend can see.
    assert backend.importer.session_manager is backend.session_manager


def test_build_backend_creates_a_fresh_database_when_none_given(tmp_path, monkeypatch):
    # Point the default on-disk database path at a tmp location so this
    # test doesn't touch the real project database.
    import config

    monkeypatch.setattr(config, "DATABASE_PATH", tmp_path / "default.db")

    backend = build_backend(settings=_settings())

    assert backend.database.count_customers() == 0


def test_build_backend_uses_provided_settings_without_reloading_env(tmp_path):
    database = Database(path=tmp_path / "backend2.db")
    settings = Settings(
        telegram_bot_token="explicit-token",
        openai_api_key=None,
        admin_user_ids=frozenset({777}),
    )

    backend = build_backend(settings=settings, database=database)

    assert backend.settings is settings
    assert backend.settings.telegram_bot_token == "explicit-token"
    assert backend.parser.settings is settings
