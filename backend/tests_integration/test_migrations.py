"""Migrations against a real Postgres+pgvector (uses TEST_DATABASE_URL; wipes it)."""
import os

import pytest

URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="set TEST_DATABASE_URL to run integration tests")
if URL:
    os.environ.update(DATABASE_URL=URL, DATA_DIR="/tmp/ra_test_data")


def _fresh():
    from sqlalchemy import text

    from app.db import engine

    with engine.begin() as c:
        c.execute(text("DROP SCHEMA public CASCADE"))
        c.execute(text("CREATE SCHEMA public"))
    return engine


def _version(engine):
    from sqlalchemy import text

    with engine.connect() as c:
        return c.scalar(text("SELECT version_num FROM alembic_version"))


def test_fresh_database_gets_full_schema_with_indexes():
    from sqlalchemy import inspect, text

    from app.db import init_db

    engine = _fresh()
    init_db()
    insp = inspect(engine)
    assert {"documents", "chunks", "research_runs", "eval_sets", "eval_runs", "query_expansions"} <= set(insp.get_table_names())
    assert "ocr_pages" in {c["name"] for c in insp.get_columns("documents")}
    with engine.connect() as c:
        defs = " ".join(r[0] for r in c.execute(text("SELECT indexdef FROM pg_indexes WHERE tablename='chunks'")))
    assert "USING hnsw" in defs and "vector_cosine_ops" in defs and "USING gin" in defs
    assert _version(engine) == "0002"


def test_init_is_idempotent():
    from app.db import init_db

    engine = _fresh()
    init_db(); init_db(); init_db()
    assert _version(engine) == "0002"


def test_pre_migration_database_is_adopted_without_data_loss():
    """Simulates a database made by create_all() in Parts 1-4: tables exist, no alembic_version, no ocr_pages."""
    from alembic import command
    from sqlalchemy import inspect, text

    from app.db import alembic_config, init_db

    engine = _fresh()
    with engine.begin() as c:
        c.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        command.upgrade(alembic_config(c), "0001")
        c.execute(text("INSERT INTO documents (id, filename, title, sha256, mime, num_pages, num_chunks, status, created_at) "
                       "VALUES (gen_random_uuid(), 'old.pdf', 'Old', 'abc', 'application/pdf', 3, 0, 'ready', now())"))
        c.execute(text("DROP TABLE alembic_version"))  # now it looks like a legacy install
    init_db()
    assert _version(engine) == "0002"
    assert "ocr_pages" in {c["name"] for c in inspect(engine).get_columns("documents")}
    with engine.connect() as c:
        assert c.execute(text("SELECT title, ocr_pages FROM documents")).one() == ("Old", 0)


def test_downgrade_and_upgrade_roundtrip():
    from alembic import command
    from sqlalchemy import inspect

    from app.db import alembic_config, init_db

    engine = _fresh()
    init_db()
    with engine.begin() as c:
        command.downgrade(alembic_config(c), "0001")
    assert "ocr_pages" not in {c["name"] for c in inspect(engine).get_columns("documents")}
    init_db()
    assert "ocr_pages" in {c["name"] for c in inspect(engine).get_columns("documents")}
