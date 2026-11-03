"""SQLite engine, session management, and Alembic initialization."""

from __future__ import annotations

import os
from pathlib import Path
from threading import RLock

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


DEFAULT_DATABASE_URL = os.getenv("INCIDENT_AGENT_DATABASE_URL", "sqlite:///./data/incidents.db")


class Database:
    """Own one SQLAlchemy engine and provide transaction-scoped sessions."""

    def __init__(self, url: str = DEFAULT_DATABASE_URL) -> None:
        self.url = url
        parsed_url = make_url(url)
        if parsed_url.get_backend_name() != "sqlite":
            raise ValueError("Incident storage only supports local SQLite database URLs")
        self.database_path = parsed_url.database
        connect_args: dict[str, object] = {"check_same_thread": False, "timeout": 30}
        engine_options: dict[str, object] = {"connect_args": connect_args, "pool_pre_ping": True}
        if self.database_path in (None, "", ":memory:"):
            engine_options["poolclass"] = StaticPool
        self.engine: Engine = create_engine(url, **engine_options)
        event.listen(self.engine, "connect", self._enable_sqlite_foreign_keys)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False, class_=Session)
        self._initialized = False
        self._initialization_lock = RLock()

    @staticmethod
    def _enable_sqlite_foreign_keys(connection: object, _: object) -> None:
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    def initialize(self) -> None:
        """Apply database migrations once for this engine lifecycle."""
        with self._initialization_lock:
            if self._initialized:
                return
            if self.database_path and self.database_path != ":memory:":
                Path(self.database_path).expanduser().parent.mkdir(parents=True, exist_ok=True)
            project_root = Path(__file__).resolve().parents[3]
            config = Config(str(project_root / "alembic.ini"))
            config.attributes["database_url"] = self.url
            with self.engine.connect() as connection:
                config.attributes["connection"] = connection
                command.upgrade(config, "head")
            self._initialized = True

    def session(self) -> Session:
        """Create a session after ensuring the schema is initialized."""
        self.initialize()
        return self.session_factory()

    def check_ready(self) -> bool:
        """Confirm migrations are applied and the local database accepts queries."""
        try:
            self.initialize()
            with self.engine.connect() as connection:
                return connection.exec_driver_sql("SELECT 1").scalar_one() == 1
        except SQLAlchemyError:
            return False

    def close(self) -> None:
        """Release pooled connections during application shutdown."""
        with self._initialization_lock:
            self.engine.dispose()
            self._initialized = False
