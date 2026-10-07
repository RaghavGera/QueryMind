"""GET /schema: the live schema plus the database name the app chrome shows."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.main as main_module
from testing.test_phase4 import build_mock_schema


class _Introspector:
    def __init__(self, db):
        pass

    def introspect(self):
        return build_mock_schema()


class _DB:
    config = type("Config", (), {"host": "h", "port": 5432, "database": "demo_db"})()


def test_schema_response_includes_database_name(monkeypatch):
    monkeypatch.setattr(main_module, "SchemaIntrospector", _Introspector)
    body = asyncio.run(main_module.get_schema(_DB()))

    assert body["database"] == "demo_db"
    assert set(body["tables"]) == set(build_mock_schema().tables)
    orders = body["tables"]["orders"]
    assert orders["primary_keys"] and orders["foreign_keys"], "keys still reported"
