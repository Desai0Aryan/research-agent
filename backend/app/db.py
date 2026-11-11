import logging
from collections.abc import Iterator
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from .config import get_settings

log = logging.getLogger(__name__)
engine = create_engine(get_settings().database_url, pool_pre_ping=True, pool_size=10)
SessionLocal = sessionmaker(engine, expire_on_commit=False)
BASELINE = "0001"  # schema created by create_all() in releases before migrations existed


def get_db() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


def alembic_config(connection=None) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
    if connection is not None:
        cfg.attributes["connection"] = connection
    return cfg


def init_db() -> None:
    """Bring the schema to the latest revision. Safe to run on every start and from several workers at once."""
    with engine.begin() as conn:
        conn.execute(text("SELECT pg_advisory_xact_lock(727274)"))  # serialize concurrent starters
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        tables = set(inspect(conn).get_table_names())
        cfg = alembic_config(conn)
        if "documents" in tables and "alembic_version" not in tables:
            log.info("Adopting pre-migration database at baseline %s", BASELINE)
            command.stamp(cfg, BASELINE)
        command.upgrade(cfg, "head")
