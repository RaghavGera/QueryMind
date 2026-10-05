"""
Natural-language INSERT/UPDATE: value extraction -> SQL -> preview ->
confirmation token -> guarded execution. No network or database needed.
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.responses import JSONResponse

import app.database as database
import app.main as main_module
from app import writes
from app.ambiguity_detector import AmbiguityDetector
from app.database import Database, DatabaseConfig, WriteConflictError
from app.intent_converter import IntentConversionError, convert_query_intent
from app.intent_extractor import QueryIntent
from app.sql_generator import GenerationStatus, SQLGenerator
from testing.test_phase4 import build_mock_schema


@pytest.fixture
def schema():
    return build_mock_schema()


@pytest.fixture(autouse=True)
def _secret(monkeypatch):
    monkeypatch.setenv("QUERYMIND_CONFIRM_SECRET", "test-secret")
    monkeypatch.delenv("QUERYMIND_ENABLE_WRITES", raising=False)
    writes._used_nonces.clear()


# ---------------------------------------------------------------------- #
# Tokens
# ---------------------------------------------------------------------- #

def test_token_round_trip():
    token = writes.issue_token("UPDATE t SET a = %s WHERE b = %s", [1, "x"], expected_rows=3)
    authorized = writes.redeem_token(token)
    assert authorized == {"sql": "UPDATE t SET a = %s WHERE b = %s", "params": [1, "x"], "expected_rows": 3}


def test_token_is_single_use():
    token = writes.issue_token("INSERT INTO t (a) VALUES (%s)", [1])
    writes.redeem_token(token)
    with pytest.raises(writes.ConfirmationError, match="already used"):
        writes.redeem_token(token)


def test_token_expires():
    token = writes.issue_token("INSERT INTO t (a) VALUES (%s)", [1], now=1000.0)
    with pytest.raises(writes.ConfirmationError, match="expired"):
        writes.redeem_token(token, now=1000.0 + writes.TOKEN_TTL_SECONDS + 1)


def test_tampered_token_is_rejected():
    token = writes.issue_token("UPDATE t SET a = %s WHERE b = %s", [1, 2])
    body, signature = token.split(".")
    forged_body = writes._b64(
        json.dumps({"v": 1, "sql": "UPDATE t SET a = 0", "params": [], "exp": 9e12, "nonce": "n"}).encode()
    )
    for forged in (f"{forged_body}.{signature}", f"{body}.{writes._b64(b'nope')}", "garbage", ""):
        with pytest.raises(writes.ConfirmationError):
            writes.redeem_token(forged)


def test_token_signed_with_another_secret_is_rejected(monkeypatch):
    token = writes.issue_token("INSERT INTO t (a) VALUES (%s)", [1])
    monkeypatch.setenv("QUERYMIND_CONFIRM_SECRET", "different")
    with pytest.raises(writes.ConfirmationError, match="Invalid"):
        writes.redeem_token(token)


# ---------------------------------------------------------------------- #
# Database.execute_write guards
# ---------------------------------------------------------------------- #

class _FakeCursor:
    def __init__(self, conn):
        self.conn = conn
        self.rowcount = conn.rowcount

    def execute(self, sql, params=None):
        self.conn.executed.append((sql, params))

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeConnection:
    def __init__(self, rowcount):
        self.rowcount = rowcount
        self.executed = []
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return _FakeCursor(self)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


@pytest.fixture
def real_db(monkeypatch):
    monkeypatch.setenv("DB_USER", "u")
    monkeypatch.setenv("DB_PASSWORD", "p")
    return Database(DatabaseConfig())


def _patch_connect(monkeypatch, rowcount):
    conn = _FakeConnection(rowcount)
    monkeypatch.setattr(database.psycopg, "connect", lambda *a, **k: conn)
    return conn


@pytest.mark.parametrize("sql", [
    "DELETE FROM products WHERE price > 1",
    "DROP TABLE products",
    "SELECT 1",
    "INSERT INTO a (b) VALUES (1); DROP TABLE a",
    "UPDATE products SET price = 1",
    "",
])
def test_execute_write_rejects_everything_but_guarded_insert_update(real_db, monkeypatch, sql):
    conn = _patch_connect(monkeypatch, 1)
    with pytest.raises(ValueError):
        real_db.execute_write(sql)
    assert conn.executed == []  # never reached the database


def test_execute_write_commits_when_row_count_matches(real_db, monkeypatch):
    conn = _patch_connect(monkeypatch, 2)
    affected = real_db.execute_write('UPDATE "p" SET "a" = %s WHERE "b" = %s', (1, 2), expected_rows=2)
    assert affected == 2 and conn.committed and conn.closed


def test_execute_write_rolls_back_when_row_count_changed(real_db, monkeypatch):
    conn = _patch_connect(monkeypatch, 7)
    with pytest.raises(WriteConflictError):
        real_db.execute_write('UPDATE "p" SET "a" = %s WHERE "b" = %s', (1, 2), expected_rows=2)
    assert conn.rolled_back and not conn.committed and conn.closed


# ---------------------------------------------------------------------- #
# Converter / generator
# ---------------------------------------------------------------------- #

def _update_intent(**overrides):
    base = dict(
        query_type="update",
        tables=["products"],
        values={"price": "999"},
        conditions=[{"column": "product_name", "operator": "=", "value": "Laptop 1", "table": "products"}],
    )
    base.update(overrides)
    return QueryIntent(**base)


def test_update_is_converted_and_values_are_coerced(schema):
    structured = convert_query_intent(_update_intent(), "Change the price of Laptop 1 to 999", schema=schema)
    assert structured.update_values == {"price": 999.0}

    result = SQLGenerator(schema, AmbiguityDetector(schema)).generate(structured)
    assert result.status == GenerationStatus.SUCCESS, result
    assert result.sql == (
        'UPDATE "products"\nSET "price" = %s\nWHERE LOWER("products"."product_name") = LOWER(%s)'
    )
    assert result.params == [999.0, "Laptop 1"]


def test_insert_is_converted(schema):
    intent = QueryIntent(
        query_type="insert",
        tables=["products"],
        values={"product_name": "Wireless Mouse", "category": "Accessories", "price": "19.99"},
    )
    structured = convert_query_intent(intent, "Add a product", schema=schema)
    result = SQLGenerator(schema, AmbiguityDetector(schema)).generate(structured)

    assert result.status == GenerationStatus.SUCCESS, result
    assert result.sql.startswith('INSERT INTO "products" ("product_name", "category", "price")')
    assert result.params == ["Wireless Mouse", "Accessories", 19.99]


def test_insert_missing_required_values_asks_instead_of_failing(schema):
    intent = QueryIntent(query_type="insert", tables=["customers"], values={"first_name": "Asha"})
    structured = convert_query_intent(intent, "Add a customer named Asha", schema=schema)

    result = SQLGenerator(schema, AmbiguityDetector(schema)).generate(structured)

    assert result.status == GenerationStatus.NEEDS_CLARIFICATION
    asked = " ".join(result.clarification_questions)
    for column in ("last_name", "email", "country", "signup_date"):
        assert f"'{column}'" in asked
    assert "customer_id" not in asked  # auto-generated key


def test_update_without_where_is_blocked(schema):
    structured = convert_query_intent(
        _update_intent(conditions=None), "Set all prices to 5", schema=schema
    )
    result = SQLGenerator(schema, AmbiguityDetector(schema)).generate(structured)
    assert result.status == GenerationStatus.BLOCKED
    assert result.sql is None


def test_unknown_column_in_values_is_rejected(schema):
    structured = convert_query_intent(_update_intent(values={"nope": 1}), "q", schema=schema)
    result = SQLGenerator(schema, AmbiguityDetector(schema)).generate(structured)
    assert result.status == GenerationStatus.ERROR
    assert "nope" in result.error_message


@pytest.mark.parametrize("overrides,message", [
    ({"values": None}, "couldn't tell which values"),
    ({"values": {}}, "couldn't tell which values"),
    ({"tables": ["products", "orders"]}, "exactly one table"),
    ({"values": {"orders.status": "x"}}, "does not belong"),
    ({"values": {"price": "cheap"}}, "expects a number"),
    ({"conditions": [{"column": "status", "operator": "=", "value": "x", "table": "orders"}]}, "can only filter"),
])
def test_bad_write_intents_raise_conversion_errors(schema, overrides, message):
    with pytest.raises(IntentConversionError, match=message):
        convert_query_intent(_update_intent(**overrides), "q", schema=schema)


def test_injection_in_values_stays_a_parameter(schema):
    payload = "x'; DROP TABLE products; --"
    intent = _update_intent(values={"product_name": payload})
    structured = convert_query_intent(intent, "q", schema=schema)
    result = SQLGenerator(schema, AmbiguityDetector(schema)).generate(structured)

    assert "DROP" not in result.sql
    assert payload in result.params


# ---------------------------------------------------------------------- #
# API flow
# ---------------------------------------------------------------------- #

class _Introspector:
    def __init__(self, db):
        pass

    def introspect(self):
        return build_mock_schema()


class _WriteDB:
    def __init__(self, matching_rows=1, write_error=None):
        self.matching_rows = matching_rows
        self.write_error = write_error
        self.writes = []

    def execute_query(self, sql, params=None):
        assert sql.startswith("SELECT COUNT(*)")
        return [{"affected_rows": self.matching_rows}]

    def execute_write(self, sql, params=None, expected_rows=None):
        if self.write_error:
            raise self.write_error
        self.writes.append((sql, params, expected_rows))
        return expected_rows


def _call(coro):
    response = asyncio.run(coro)
    if isinstance(response, JSONResponse):
        return response.status_code, json.loads(response.body)
    return 200, response


def _ask(monkeypatch, db, intent, question="q", **request_fields):
    monkeypatch.setattr(main_module, "SchemaIntrospector", _Introspector)
    monkeypatch.setattr(main_module, "extract_intent", lambda q, c: intent)
    return _call(main_module.run_query(main_module.QueryRequest(question=question, **request_fields), db))


def _confirm(db, token):
    return _call(main_module.confirm_write(main_module.ConfirmRequest(confirmation_token=token), db))


def test_writes_are_blocked_but_previewed_by_default(monkeypatch):
    db = _WriteDB(matching_rows=1)
    code, body = _ask(monkeypatch, db, _update_intent(), "Change the price of Laptop 1 to 999")

    assert code == 200
    assert body["status"] == "blocked"
    assert "disabled" in body["error_message"]
    assert body["preview"]["affected_rows"] == 1
    assert "confirmation_token" not in body
    assert db.writes == []


def test_update_requires_confirmation_then_executes_once(monkeypatch):
    monkeypatch.setenv("QUERYMIND_ENABLE_WRITES", "true")
    db = _WriteDB(matching_rows=2)

    code, body = _ask(monkeypatch, db, _update_intent(), "Change the price of Laptop 1 to 999")

    assert body["status"] == "needs_confirmation"
    assert body["preview"]["summary"].endswith("2 row(s) will be changed.")
    assert body["preview"]["set"] == {"price": 999.0}
    assert db.writes == []  # asking never writes

    token = body["confirmation_token"]
    code, done = _confirm(db, token)
    assert code == 200 and done == {"status": "executed", "rows_affected": 2}
    assert len(db.writes) == 1
    sql, params, expected = db.writes[0]
    assert sql.startswith('UPDATE "products"') and list(params) == [999.0, "Laptop 1"] and expected == 2

    code, replay = _confirm(db, token)
    assert code == 400 and "already used" in replay["error"]
    assert len(db.writes) == 1


def test_user_setting_can_turn_writes_off_even_when_the_server_allows_them(monkeypatch):
    monkeypatch.setenv("QUERYMIND_ENABLE_WRITES", "true")
    db = _WriteDB(matching_rows=1)
    code, body = _ask(monkeypatch, db, _update_intent(), "Change the price of Laptop 1 to 999", allow_writes=False)

    assert code == 200
    assert body["status"] == "blocked"
    assert "turned off in Settings" in body["error_message"]
    assert body["preview"]["affected_rows"] == 1  # still shows what would have changed
    assert "confirmation_token" not in body
    assert db.writes == []


def test_user_setting_cannot_turn_writes_on_when_the_server_disallows_them(monkeypatch):
    monkeypatch.delenv("QUERYMIND_ENABLE_WRITES", raising=False)
    db = _WriteDB(matching_rows=1)
    code, body = _ask(monkeypatch, db, _update_intent(), "Change the price of Laptop 1 to 999", allow_writes=True)

    assert body["status"] == "blocked"
    assert "disabled on this deployment" in body["error_message"]
    assert "confirmation_token" not in body


@pytest.mark.parametrize("strict", [True, False])
def test_clarification_setting_reaches_the_generator(monkeypatch, strict):
    seen = {}
    real_generator = main_module.SQLGenerator

    def spy(schema, detector=None, strict=True, **kwargs):
        seen["strict"] = strict
        return real_generator(schema, detector, strict=strict, **kwargs)

    monkeypatch.setattr(main_module, "SQLGenerator", spy)
    _ask(monkeypatch, _WriteDB(), _update_intent(), "Change the price of Laptop 1 to 999", strict=strict)
    assert seen["strict"] is strict


def test_health_reports_whether_writes_are_enabled(monkeypatch):
    class _HealthyDB:
        config = type("C", (), {"host": "h", "port": 5432, "database": "d"})()

        def test_connection(self):
            return True

    monkeypatch.delenv("QUERYMIND_ENABLE_WRITES", raising=False)
    assert _call(main_module.health_check(_HealthyDB()))[1]["writes_enabled"] is False
    monkeypatch.setenv("QUERYMIND_ENABLE_WRITES", "true")
    assert _call(main_module.health_check(_HealthyDB()))[1]["writes_enabled"] is True


def test_update_matching_nothing_is_reported(monkeypatch):
    monkeypatch.setenv("QUERYMIND_ENABLE_WRITES", "true")
    code, body = _ask(monkeypatch, _WriteDB(matching_rows=0), _update_intent())
    assert body["status"] == "error"
    assert "nothing to update" in body["error"]


def test_insert_confirmation_expects_one_row(monkeypatch):
    monkeypatch.setenv("QUERYMIND_ENABLE_WRITES", "true")
    db = _WriteDB()
    intent = QueryIntent(
        query_type="insert", tables=["products"],
        values={"product_name": "Wireless Mouse", "category": "Accessories", "price": 19.99},
    )
    _, body = _ask(monkeypatch, db, intent, "Add a new product")
    assert body["status"] == "needs_confirmation"
    assert body["preview"]["action"] == "insert"

    _confirm(db, body["confirmation_token"])
    assert db.writes[0][2] == 1


def test_confirm_is_forbidden_when_writes_disabled():
    token = writes.issue_token("INSERT INTO t (a) VALUES (%s)", [1])
    code, body = _confirm(_WriteDB(), token)
    assert code == 403 and body["status"] == "error"


def test_confirm_rejects_forged_tokens(monkeypatch):
    monkeypatch.setenv("QUERYMIND_ENABLE_WRITES", "true")
    db = _WriteDB()
    code, body = _confirm(db, "x.y")
    assert code == 400 and db.writes == []


def test_row_count_conflict_is_a_409(monkeypatch):
    monkeypatch.setenv("QUERYMIND_ENABLE_WRITES", "true")
    token = writes.issue_token('UPDATE "p" SET "a" = %s WHERE "b" = %s', [1, 2], expected_rows=1)
    db = _WriteDB(write_error=WriteConflictError("would now affect 9 row(s)"))
    code, body = _confirm(db, token)
    assert code == 409 and "9 row" in body["error"]


def test_database_errors_do_not_leak_details(monkeypatch):
    monkeypatch.setenv("QUERYMIND_ENABLE_WRITES", "true")
    token = writes.issue_token("INSERT INTO t (a) VALUES (%s)", [1], expected_rows=1)
    db = _WriteDB(write_error=RuntimeError("null value in column x violates not-null constraint\nDETAIL: secret"))
    code, body = _confirm(db, token)
    assert code == 500
    assert "secret" not in json.dumps(body)


def test_filtered_delete_is_never_executed(monkeypatch):
    monkeypatch.setenv("QUERYMIND_ENABLE_WRITES", "true")
    intent = QueryIntent(
        query_type="delete", tables=["customers"],
        conditions=[{"column": "customer_id", "operator": "=", "value": 5}],
    )
    db = _WriteDB()
    code, body = _ask(monkeypatch, db, intent, "Delete customer 5")

    assert body["status"] == "blocked"
    assert body["sql"] is None
    assert db.writes == []
