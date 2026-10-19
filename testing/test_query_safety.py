"""
Phase 3 safety: read-only transactions, the statement timeout, the row cap,
and endpoints that don't block each other.
"""

import asyncio
import json
import sys
import time
from pathlib import Path

import httpx
import pytest
from fastapi.responses import JSONResponse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.main as main_module
from app.database import QueryTimeoutError, max_result_rows, query_timeout_ms
from app.intent_extractor import QueryIntent
from testing.test_phase4 import build_mock_schema


# --------------------------------------------------------------------------- #
# Against a real PostgreSQL (skipped without one)
# --------------------------------------------------------------------------- #

def test_a_write_dressed_as_a_select_is_refused(db):
    # "SELECT ... INTO" creates a table and starts with SELECT, so only the
    # READ ONLY transaction stands between it and the database.
    with pytest.raises(Exception, match="read-only transaction"):
        db.execute_query("SELECT 1 AS x INTO TEMP TABLE qm_read_only_probe")


def test_slow_queries_are_stopped_at_the_timeout(db, monkeypatch):
    monkeypatch.setenv("QUERY_TIMEOUT_SECONDS", "0.5")
    started = time.monotonic()
    with pytest.raises(QueryTimeoutError, match="0.5 s"):
        db.execute_query("SELECT pg_sleep(5)")
    assert time.monotonic() - started < 4, "cancelled by the server, not waited out"
    assert db.execute_query("SELECT 1 AS ok") == [{"ok": 1}], "the next query is unaffected"


def test_max_rows_fetches_one_extra_row_to_detect_a_capped_result(db):
    assert len(db.execute_query("SELECT generate_series(1, 50) AS n", max_rows=10)) == 11
    assert len(db.execute_query("SELECT generate_series(1, 5) AS n", max_rows=10)) == 5


def test_settings_fall_back_to_defaults(monkeypatch):
    for bad in ("", "abc", "-3", "0"):
        monkeypatch.setenv("QUERY_TIMEOUT_SECONDS", bad)
        monkeypatch.setenv("MAX_RESULT_ROWS", bad)
        assert query_timeout_ms() == 8000 and max_result_rows() == 1000


# --------------------------------------------------------------------------- #
# Through /query with a fake database
# --------------------------------------------------------------------------- #

class _RowsDB:
    def __init__(self, rows=None, error=None):
        self.rows, self.error, self.max_rows = rows or [], error, None

    def execute_query(self, query, params=None, max_rows=None):
        self.max_rows = max_rows
        if self.error:
            raise self.error
        return self.rows if max_rows is None else self.rows[: max_rows + 1]


class _Introspector:
    def __init__(self, db):
        pass

    def introspect(self):
        return build_mock_schema()


@pytest.fixture
def ask(monkeypatch):
    monkeypatch.setattr(main_module, "SchemaIntrospector", _Introspector)
    monkeypatch.setattr(
        main_module, "extract_intent",
        lambda q, c: QueryIntent(query_type="select", tables=["customers"], columns=["customers.customer_id"]),
    )

    def post(db):
        response = main_module.run_query(main_module.QueryRequest(question="show customer ids"), db)
        if isinstance(response, JSONResponse):
            return response.status_code, json.loads(response.body)
        return 200, response

    return post


def test_results_over_the_cap_are_cut_and_flagged(ask, monkeypatch):
    monkeypatch.setenv("MAX_RESULT_ROWS", "3")
    db = _RowsDB([{"customer_id": i} for i in range(10)])
    code, body = ask(db)
    assert code == 200 and db.max_rows == 3
    assert body["result"]["rows"] == [{"customer_id": 0}, {"customer_id": 1}, {"customer_id": 2}]
    assert body["result"]["truncated"] is True
    assert any("Showing the first 3 rows" in w for w in body["warnings"])


def test_results_within_the_cap_are_not_flagged(ask, monkeypatch):
    monkeypatch.setenv("MAX_RESULT_ROWS", "3")
    code, body = ask(_RowsDB([{"customer_id": i} for i in range(3)]))
    assert len(body["result"]["rows"]) == 3 and body["result"]["truncated"] is False
    assert not any("Showing the first" in w for w in body.get("warnings", []))


def test_a_timeout_is_an_honest_504(ask):
    code, body = ask(_RowsDB(error=QueryTimeoutError("The query took longer than 8 s and was stopped.")))
    assert code == 504
    assert body["error"].startswith("The query took longer than 8 s") and "narrower" in body["error"]
    assert body["sql"], "the SQL that timed out is shown"


def test_two_slow_questions_run_side_by_side(monkeypatch):
    # The endpoint is a plain function, so FastAPI runs it in its threadpool:
    # two one-second answers take about one second together, not two.
    monkeypatch.setenv("QUERYMIND_SERVICE_KEY", "k" * 32)
    monkeypatch.setattr(main_module, "_run_pipeline", lambda q, r, db: time.sleep(1) or {"status": "success", "result": {"columns": [], "rows": []}})
    main_module.app.dependency_overrides[main_module.get_db] = lambda: object()

    async def both():
        transport = httpx.ASGITransport(app=main_module.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://api.test") as client:
            ask = lambda: client.post("/query", json={"question": "q"}, headers={"X-Service-Key": "k" * 32})
            started = time.monotonic()
            responses = await asyncio.gather(ask(), ask())
            return time.monotonic() - started, responses

    try:
        elapsed, responses = asyncio.run(both())
    finally:
        main_module.app.dependency_overrides.clear()
    assert [r.status_code for r in responses] == [200, 200]
    assert elapsed < 1.8, f"took {elapsed:.2f} s: the requests ran one after the other"
