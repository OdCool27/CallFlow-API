"""Upgrade the original SQLite schema in place, retaining a backup first."""
import sqlite3
from pathlib import Path

from sqlalchemy import inspect

from app.database import Base
from app import models


def initialize_database(engine):
    with engine.connect() as conn:
        if conn.exec_driver_sql("PRAGMA user_version").scalar() > 1:
            raise RuntimeError("Database schema is newer than this application")
    inspector = inspect(engine)
    if "calls" in inspector.get_table_names() and "source" not in {c["name"] for c in inspector.get_columns("calls")}:
        path = engine.url.database
        if path and path != ":memory:":
            backup = Path(path + ".pre-ami.bak")
            if backup.exists():
                raise RuntimeError("Migration backup already exists; inspect it before retrying")
            with sqlite3.connect(path) as src, sqlite3.connect(backup) as dst:
                src.backup(dst)
        indexes = inspector.get_indexes("calls")
        with engine.begin() as conn:
            conn.exec_driver_sql("BEGIN IMMEDIATE")
            conn.exec_driver_sql("ALTER TABLE calls RENAME TO calls_legacy")
            for index in indexes:
                name = index["name"].replace('"', '""')
                conn.exec_driver_sql(f'DROP INDEX "{name}"')
            models.Call.__table__.create(conn)
            conn.exec_driver_sql("""
                INSERT INTO calls (id, customer_id, agent_id, direction, status,
                    started_at, ended_at, notes, source, connected_seconds, tracking_incomplete)
                SELECT id, customer_id, agent_id, direction, status,
                    started_at, ended_at, notes, 'LEGACY', 0, 1 FROM calls_legacy
            """)
            conn.exec_driver_sql("DROP TABLE calls_legacy")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_calls_status ON calls(status)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_calls_started_at ON calls(started_at)")
        conn.exec_driver_sql("PRAGMA user_version=1")
