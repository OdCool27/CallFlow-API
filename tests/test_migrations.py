from sqlalchemy import create_engine, inspect, text
from app.migrations import initialize_database


def test_upgrade_original_database_preserves_rows(tmp_path):
    path = tmp_path / "original.db"
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE agents (id INTEGER PRIMARY KEY, name TEXT, extension TEXT UNIQUE, department TEXT NOT NULL)")
        conn.exec_driver_sql("CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT, phone_number TEXT, email TEXT)")
        conn.exec_driver_sql("CREATE TABLE calls (id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL REFERENCES customers(id), agent_id INTEGER NOT NULL REFERENCES agents(id), direction TEXT, status TEXT, started_at DATETIME, ended_at DATETIME, notes TEXT)")
        conn.exec_driver_sql("CREATE INDEX ix_calls_id ON calls(id)")
        conn.exec_driver_sql("INSERT INTO agents VALUES (1, 'Agent', '102', 'Support')")
        conn.exec_driver_sql("INSERT INTO customers VALUES (1, 'Customer', '555', NULL)")
        conn.exec_driver_sql("INSERT INTO calls VALUES (1, 1, 1, 'INBOUND', 'COMPLETED', '2026-01-01 12:00:00', '2026-01-01 12:01:00', 'Preserve me')")
    initialize_database(engine)
    initialize_database(engine)
    with engine.connect() as conn:
        row = conn.execute(text("SELECT * FROM calls")).mappings().one()
        assert row["notes"] == "Preserve me"
        assert row["source"] == "LEGACY"
        assert row["tracking_incomplete"] == 1
        assert conn.exec_driver_sql("PRAGMA user_version").scalar() == 1
        assert conn.exec_driver_sql("PRAGMA foreign_key_check").all() == []
    assert path.with_name("original.db.pre-ami.bak").exists()
    assert {c["name"]: c for c in inspect(engine).get_columns("calls")}["customer_id"]["nullable"]
    engine.dispose()
