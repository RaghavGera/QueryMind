"""
The connection pool against a real PostgreSQL (skipped without one). With one
connection in the pool, every request gets the same server session, so
anything a request leaves behind would show up in the next one.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import Database, DatabaseConfig
from app.workspaces import DEMO, ScopedDatabase, WorkspaceStore


@pytest.fixture
def single(db, monkeypatch):
    """A second Database on the same server whose pool holds one connection."""
    monkeypatch.setenv("DB_POOL_MAX_SIZE", "1")
    WorkspaceStore(db).ensure_schema()  # the demo's read-only role
    one = Database(DatabaseConfig())
    yield one
    one.close()


def _session(database):
    with database.get_connection() as conn:
        return conn.execute(
            "SELECT pg_backend_pid() AS pid, current_user AS who, current_setting('transaction_read_only') AS ro, "
            "current_setting('search_path') AS path, current_setting('statement_timeout') AS timeout"
        ).fetchone()


def test_a_read_leaves_nothing_behind_on_the_reused_connection(single):
    before = _session(single)
    rows = ScopedDatabase(single, DEMO).execute_query("SELECT current_user AS who, current_setting('transaction_read_only') AS ro")
    assert rows == [{"who": "querymind_demo", "ro": "on"}], "the read ran as the demo role, read-only"
    after = _session(single)
    assert after["pid"] == before["pid"], "the same pooled server session was reused"
    assert after == before, "role, read-only, search_path and timeout are back to the session's own"
    with single.get_connection() as conn:  # and the next request can write
        conn.execute("CREATE TEMP TABLE pool_probe (n int)")
        conn.execute("INSERT INTO pool_probe VALUES (1)")


def test_a_failed_query_does_not_poison_the_connection(single):
    with pytest.raises(Exception):
        single.execute_query("SELECT * FROM no_such_table_anywhere")
    assert single.execute_query("SELECT 1 AS ok") == [{"ok": 1}]


def test_a_connection_closed_by_the_server_is_replaced(db, single):
    # What Neon does to idle connections when its compute scales to zero.
    pid = _session(single)["pid"]
    with db.get_connection() as conn:
        assert conn.execute("SELECT pg_terminate_backend(%s) AS done", (pid,)).fetchone()["done"]
    assert single.execute_query("SELECT 1 AS ok") == [{"ok": 1}], "no error reaches the caller"
    assert _session(single)["pid"] != pid
