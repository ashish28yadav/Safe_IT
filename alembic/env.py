from logging.config import fileConfig
import os
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine, pool
from sqlalchemy.engine import make_url

from incident_agent.storage.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.attributes.get("database_url") or os.getenv(
        "INCIDENT_AGENT_DATABASE_URL", config.get_main_option("sqlalchemy.url")
    )
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True,
                      dialect_opts={"paramstyle": "named"}, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = config.attributes.get("database_url") or os.getenv(
        "INCIDENT_AGENT_DATABASE_URL", config.get_main_option("sqlalchemy.url")
    )
    external_connection = config.attributes.get("connection")
    if external_connection is not None:
        context.configure(connection=external_connection, target_metadata=target_metadata,
                          compare_type=True, transactional_ddl=True)
        with context.begin_transaction():
            context.run_migrations()
        return
    connect_args = {"check_same_thread": False, "timeout": 30} if url.startswith("sqlite") else {}
    parsed_url = make_url(url)
    if parsed_url.get_backend_name() == "sqlite" and parsed_url.database not in (None, "", ":memory:"):
        Path(parsed_url.database).expanduser().parent.mkdir(parents=True, exist_ok=True)
    connectable = create_engine(url, poolclass=pool.NullPool, connect_args=connect_args)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True,
                          transactional_ddl=connection.dialect.name == "sqlite")
        with context.begin_transaction():
            context.run_migrations()
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
