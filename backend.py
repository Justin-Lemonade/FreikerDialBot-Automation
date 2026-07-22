"""The shared backend that every frontend -- the Telegram bot, the Mini
App, and any future frontend -- wires up identically and calls into.

This exists to close a duplication that had crept in: bot.py and
mini_app_api.py were each independently constructing the exact same
Database -> StatisticsEngine -> SessionManager -> QueueEngine -> Importer
sequence. Neither frontend needs to know how these pieces fit together
-- they should just ask for a Backend and use it.

Including `importer` and `parser` here (even though the Mini App doesn't
call them yet) is deliberate: "Mini App import" is a named future
feature, and this is what makes it cost near-zero when it's built --
just a new endpoint calling self.backend.importer, no new wiring.
"""

from __future__ import annotations

from dataclasses import dataclass

from ai_parser import AIParser
import config as _config
from config import Settings, load_settings
from database import Database
from importer import Importer
from queue_engine import QueueEngine
from session_manager import SessionManager
from statistics_engine import StatisticsEngine


@dataclass(frozen=True)
class Backend:
    """Every shared service a frontend might need. Frontends should read
    from this instead of constructing Database/QueueEngine/etc.
    themselves -- that construction should happen exactly once, here."""

    settings: Settings
    database: Database
    statistics: StatisticsEngine
    session_manager: SessionManager
    queue_engine: QueueEngine
    importer: Importer
    parser: AIParser


def build_backend(settings: Settings | None = None, database: Database | None = None) -> Backend:
    """Wire up one shared backend instance.

    `settings` and `database` can both be injected -- tests want an
    isolated temp-file Database and sometimes a synthetic Settings;
    production code (bot.py, mini_app_api.py) just calls
    build_backend() with no arguments and gets the normal on-disk
    database and real environment settings.
    """
    settings = settings or load_settings()
    database = database if database is not None else Database(path=_config.DATABASE_PATH)
    statistics = StatisticsEngine(database)
    session_manager = SessionManager(database, statistics)
    queue_engine = QueueEngine(database, statistics=statistics, session_manager=session_manager)
    parser = AIParser(settings)
    importer = Importer(parser, database, session_manager=session_manager)
    return Backend(
        settings=settings,
        database=database,
        statistics=statistics,
        session_manager=session_manager,
        queue_engine=queue_engine,
        importer=importer,
        parser=parser,
    )
