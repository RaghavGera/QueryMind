"""
Security review of 2026-10-24: what /health reveals, the headers on every API
response, request size limits, and which refused requests don't use a question.
No database or model needed.
"""

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.main as main_module
from app.intent_extractor import QueryIntent
from testing.test_auth import FakeStore
from testing.test_phase4 import build_mock_schema


class _HealthyDB:
    config = SimpleNamespace(host="ep-secret-host.us-west-2.aws.neon.tech", port=5432, database="querymind-db")

    def test_connection(self):
        return True

    def execute_query(self, query, params=None, max_rows=None, **kwargs):
        return [{"category": "Laptops", "max_price": 1999}]


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", "s" * 48)
    store = FakeStore()
    model_calls = []

    def extract(question, context):
        model_calls.append(question)
        return QueryIntent(query_type="aggregate", tables=["products"], columns=["products.category"],
                           aggregations=["MAX(products.price)"], group_by=["products.category"])

    monkeypatch.setattr(main_module, "_store", store)
    monkeypatch.setattr(main_module, "extract_intent", extract)
    monkeypatch.setattr(main_module, "SchemaIntrospector",
                        lambda _db, *a: type("I", (), {"introspect": lambda self: build_mock_schema()})())
    main_module.app.dependency_overrides[main_module.get_db] = lambda: _HealthyDB()

    def call(method, path, **kwargs):
        async def go():
            transport = httpx.ASGITransport(app=main_module.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://api.test") as client:
                return await client.request(method, path, **kwargs)
        return asyncio.run(go())

    def questions_used():
        return sum(store.usage.values())

    yield SimpleNamespace(call=call, store=store, model_calls=model_calls, questions_used=questions_used)
    main_module.app.dependency_overrides.clear()


# --------------------------------------------------------------------------- #
# F1: /health is public, so it doesn't say where the database lives
# --------------------------------------------------------------------------- #

def test_health_does_not_reveal_the_database_address(api):
    response = api.call("GET", "/health")
    assert response.status_code == 200
    assert response.json()["database"] == {"database": "querymind-db", "connected": True}
    assert "neon.tech" not in response.text and "5432" not in response.text


# --------------------------------------------------------------------------- #
# F3: security headers on every API response, errors included
# --------------------------------------------------------------------------- #

EXPECTED_HEADERS = {
    "strict-transport-security": "max-age=63072000; includeSubDomains",
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "no-referrer",
    "cache-control": "no-store",
    "content-security-policy": "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
}


@pytest.mark.parametrize("method, path, kwargs", [
    ("GET", "/workspaces", {}),
    ("GET", "/health", {}),
    ("GET", "/no-such-page", {}),                                            # 404
    ("POST", "/query", {"content": b"x" * (70 * 1024),
                        "headers": {"content-type": "application/json"}}),   # 413 from a middleware
    ("POST", "/query", {"json": {"question": "q" * 1001}}),                  # 422 from the endpoint
])
def test_every_response_carries_the_security_headers(api, method, path, kwargs):
    response = api.call(method, path, **kwargs)
    for name, value in EXPECTED_HEADERS.items():
        assert response.headers.get(name) == value, (path, response.status_code, name)


def test_the_interactive_docs_keep_working(api):
    # Swagger UI loads its script from a CDN, which the API's CSP would block.
    response = api.call("GET", "/docs")
    assert response.status_code == 200
    assert "content-security-policy" not in response.headers
    assert response.headers["x-content-type-options"] == "nosniff"


# --------------------------------------------------------------------------- #
# F2 + F7: limits on what a question can be, and refused requests are free
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("kwargs, status, message", [
    ({"content": b"{not json", "headers": {"content-type": "application/json"}}, 422, None),
    ({"json": {}}, 422, None),                                                  # no question
    ({"json": {"question": "   "}}, 400, "cannot be empty"),
    ({"json": {"question": "q" * 1001}}, 422, "up to 1,000 characters"),
    ({"json": {"question": "Top products?", "clarification_context": "y" * 501}}, 422, "up to 500 characters"),
    ({"json": {"question": "Top products?", "workspace_id": "42"}}, 401, None),  # someone's workspace, signed out
])
def test_a_refused_request_does_not_use_a_question(api, kwargs, status, message):
    response = api.call("POST", "/query", **kwargs)
    assert response.status_code == status
    if message:
        assert message in response.json()["error"]
    assert api.model_calls == [], "the model was never asked"
    assert api.questions_used() == 0, "so the visitor keeps the question"


def test_an_oversized_body_is_refused_before_it_is_read(api):
    body = b'{"question": "' + b"q" * (70 * 1024) + b'"}'
    for path in ("/query", "/query/tweak", "/query/confirm"):
        response = api.call("POST", path, content=body, headers={"content-type": "application/json"})
        assert response.status_code == 413, path
        assert "up to 1,000 characters" in response.json()["error"]
    assert api.model_calls == [] and api.questions_used() == 0


def test_a_question_that_reaches_the_model_is_counted_once(api):
    response = api.call("POST", "/query", json={"question": "Which category has the priciest product?"})
    assert response.status_code == 200 and response.json()["status"] == "success"
    assert len(api.model_calls) == 1 and api.questions_used() == 1
    assert response.headers["x-usage-used"] == "1"


def test_the_longest_allowed_question_still_goes_through(api):
    response = api.call("POST", "/query", json={"question": "q" * 1000})
    assert response.status_code == 200
    assert api.questions_used() == 1
