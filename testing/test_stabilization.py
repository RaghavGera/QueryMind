"""
Phase 1 stabilization tests.

Covers, without touching the network or a database:
  * LLM retry/backoff and the typed errors raised when retries run out
  * the /query endpoint never leaking a traceback (structured JSON errors)
  * the "top N <things>" ranking safety net (the Q2 regression)
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
import openai
import pytest
from fastapi.responses import JSONResponse

import app.intent_extractor as extractor
import app.main as main_module
from app.ambiguity_detector import AmbiguityDetector
from app.intent_converter import convert_query_intent
from app.intent_extractor import IntentExtractionError, QueryIntent
from app.sql_generator import GenerationStatus, SQLGenerator
from testing.test_phase4 import build_mock_schema


# ---------------------------------------------------------------------- #
# Fakes
# ---------------------------------------------------------------------- #

def _http_response(status: int, headers: dict | None = None) -> httpx.Response:
    return httpx.Response(
        status, headers=headers or {}, request=httpx.Request("POST", "https://llm.test/v1/chat")
    )


def _rate_limit_error(retry_after: str | None = None) -> openai.RateLimitError:
    headers = {"retry-after": retry_after} if retry_after else {}
    return openai.RateLimitError("rate limited", response=_http_response(429, headers), body=None)


class _FakeCompletions:
    """Raises the queued errors in order, then returns a canned intent."""

    def __init__(self, errors=(), arguments='{"query_type": "select", "tables": ["customers"]}'):
        self.errors = list(errors)
        self.calls = 0
        self.arguments = arguments

    def create(self, **kwargs):
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)
        function_call = type("FC", (), {"arguments": self.arguments})()
        message = type("M", (), {"function_call": function_call})()
        return type("R", (), {"choices": [type("C", (), {"message": message})()]})()


class _FakeClient:
    def __init__(self, completions):
        self.chat = type("Chat", (), {"completions": completions})()


@pytest.fixture
def sleeps(monkeypatch):
    """Record backoff sleeps instead of actually sleeping."""
    recorded = []
    monkeypatch.setattr(extractor.time, "sleep", recorded.append)
    return recorded


def _use_client(monkeypatch, completions):
    monkeypatch.setattr(extractor, "get_openai_client", lambda: _FakeClient(completions))


SCHEMA_CONTEXT = {"tables": ["customers"], "columns": {"customers": ["customer_id"]}}


# ---------------------------------------------------------------------- #
# Retry / backoff
# ---------------------------------------------------------------------- #

def test_retries_rate_limit_then_succeeds(monkeypatch, sleeps):
    completions = _FakeCompletions(errors=[_rate_limit_error(), _rate_limit_error()])
    _use_client(monkeypatch, completions)

    intent = extractor.extract_intent("show customers", SCHEMA_CONTEXT)

    assert intent.tables == ["customers"]
    assert completions.calls == 3
    assert len(sleeps) == 2
    assert sleeps[1] > sleeps[0] * 0.9  # backoff grows


def test_retry_after_header_is_honored(monkeypatch, sleeps):
    completions = _FakeCompletions(errors=[_rate_limit_error(retry_after="3")])
    _use_client(monkeypatch, completions)

    extractor.extract_intent("show customers", SCHEMA_CONTEXT)

    assert sleeps == [3.0]


def test_retry_after_is_capped(monkeypatch, sleeps):
    completions = _FakeCompletions(errors=[_rate_limit_error(retry_after="600")])
    _use_client(monkeypatch, completions)

    extractor.extract_intent("show customers", SCHEMA_CONTEXT)

    assert sleeps == [extractor.LLM_BACKOFF_CAP_SECONDS]


def test_exhausted_rate_limit_raises_typed_error(monkeypatch, sleeps):
    errors = [_rate_limit_error() for _ in range(extractor.LLM_MAX_RETRIES + 1)]
    completions = _FakeCompletions(errors=errors)
    _use_client(monkeypatch, completions)

    with pytest.raises(IntentExtractionError) as excinfo:
        extractor.extract_intent("show customers", SCHEMA_CONTEXT)

    assert excinfo.value.kind == "rate_limited"
    assert excinfo.value.retry_after
    assert completions.calls == extractor.LLM_MAX_RETRIES + 1


def test_connection_errors_are_retried_and_reported_unavailable(monkeypatch, sleeps):
    request = httpx.Request("POST", "https://llm.test/v1/chat")
    errors = [openai.APIConnectionError(request=request) for _ in range(extractor.LLM_MAX_RETRIES + 1)]
    _use_client(monkeypatch, _FakeCompletions(errors=errors))

    with pytest.raises(IntentExtractionError) as excinfo:
        extractor.extract_intent("show customers", SCHEMA_CONTEXT)

    assert excinfo.value.kind == "unavailable"


def test_non_transient_errors_are_not_retried(monkeypatch, sleeps):
    bad_request = openai.BadRequestError("bad", response=_http_response(400), body=None)
    completions = _FakeCompletions(errors=[bad_request])
    _use_client(monkeypatch, completions)

    with pytest.raises(IntentExtractionError) as excinfo:
        extractor.extract_intent("show customers", SCHEMA_CONTEXT)

    assert excinfo.value.kind == "invalid_response"
    assert completions.calls == 1
    assert sleeps == []


def test_unparseable_arguments_are_invalid_response(monkeypatch, sleeps):
    _use_client(monkeypatch, _FakeCompletions(arguments="{not json"))

    with pytest.raises(IntentExtractionError) as excinfo:
        extractor.extract_intent("show customers", SCHEMA_CONTEXT)

    assert excinfo.value.kind == "invalid_response"


def test_max_tokens_stays_pinned():
    # Higher values caused 429/502 on the Groq free tier.
    assert extractor.LLM_MAX_TOKENS == 800


# ---------------------------------------------------------------------- #
# /query never leaks a traceback
# ---------------------------------------------------------------------- #

class _FakeDB:
    def __init__(self, rows=None):
        self.rows = rows if rows is not None else []

    def execute_query(self, query, params=None):
        return self.rows


class _FakeIntrospector:
    def __init__(self, db):
        pass

    def introspect(self):
        return build_mock_schema()


@pytest.fixture
def pipeline(monkeypatch):
    """Call the /query handler directly with a fake DB and schema."""
    monkeypatch.setattr(main_module, "SchemaIntrospector", _FakeIntrospector)
    db = _FakeDB([{"customer_id": 1}])

    def post(question="show customers"):
        request = main_module.QueryRequest(question=question)
        response = asyncio.run(main_module.run_query(request, db))
        if isinstance(response, JSONResponse):
            return response.status_code, json.loads(response.body)
        return 200, response

    return post


@pytest.mark.parametrize(
    "kind,status",
    [("rate_limited", 429), ("unavailable", 503), ("invalid_response", 502)],
)
def test_llm_failures_map_to_honest_statuses(pipeline, monkeypatch, kind, status):
    def boom(question, schema_context):
        raise IntentExtractionError("provider said no", kind=kind, retry_after=8.0)

    monkeypatch.setattr(main_module, "extract_intent", boom)

    code, body = pipeline()

    assert code == status
    assert body["status"] == "error"
    assert body["error"]
    assert body["result"] == {"columns": [], "rows": []}
    assert "Traceback" not in json.dumps(body)


def test_unexpected_exception_returns_structured_500(pipeline, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("kaboom with secrets")

    monkeypatch.setattr(
        main_module, "extract_intent",
        lambda q, c: QueryIntent(query_type="select", tables=["customers"]),
    )
    monkeypatch.setattr(main_module, "convert_query_intent", boom)

    code, body = pipeline()

    assert code == 500
    assert body["status"] == "error"
    assert body["error"]
    assert "kaboom" not in json.dumps(body)  # internals are logged, not returned


def test_happy_path_still_returns_rows(pipeline, monkeypatch):
    monkeypatch.setattr(
        main_module,
        "extract_intent",
        lambda q, c: QueryIntent(
            query_type="select", tables=["customers"], columns=["customers.customer_id"]
        ),
    )

    code, body = pipeline()

    assert code == 200
    assert body["status"] == "success"
    assert body["result"]["rows"] == [{"customer_id": 1}]


def test_empty_question_is_a_400(pipeline):
    code, body = pipeline(question="   ")
    assert code == 400
    assert body["error"]


def test_assumptions_are_surfaced_as_warnings(pipeline, monkeypatch):
    monkeypatch.setattr(
        main_module,
        "extract_intent",
        lambda q, c: QueryIntent(
            query_type="select",
            tables=["products"],
            columns=["products.product_name"],
            group_by=["products.product_name"],
            limit=10,
        ),
    )

    code, body = pipeline("What were our top 10 products?")

    assert code == 200
    assert body["status"] == "success"
    assert any("ranked by units sold" in w for w in body["warnings"])


# ---------------------------------------------------------------------- #
# Ranking safety net (Q2: "What were our top 10 products?")
# ---------------------------------------------------------------------- #

@pytest.fixture
def schema():
    return build_mock_schema()


def _generate(schema, intent: QueryIntent, question: str):
    structured = convert_query_intent(intent, question, schema=schema)
    result = SQLGenerator(schema, AmbiguityDetector(schema)).generate(structured)
    return structured, result


def test_top_n_products_without_aggregation_ranks_by_units_sold(schema):
    # The failure seen live: group_by present, aggregations missing.
    intent = QueryIntent(
        query_type="select",
        tables=["products"],
        columns=["products.product_name"],
        group_by=["products.product_name"],
        limit=10,
    )

    structured, result = _generate(schema, intent, "What were our top 10 products?")

    assert result.status == GenerationStatus.SUCCESS, result
    assert 'SUM("order_items"."quantity")' in result.sql
    assert 'ORDER BY SUM("order_items"."quantity") DESC' in result.sql
    assert "LIMIT 10" in result.sql
    assert 'INNER JOIN' in result.sql
    assert structured.recognized_entities["assumptions"]


def test_top_n_limit_is_parsed_from_the_question_when_model_omits_it(schema):
    intent = QueryIntent(
        query_type="aggregate",
        tables=["products"],
        columns=["product_name"],
        group_by=["product_name"],
    )

    _, result = _generate(schema, intent, "Show me the top 5 products")

    assert result.status == GenerationStatus.SUCCESS, result
    assert "LIMIT 5" in result.sql


def test_model_supplied_aggregation_is_left_untouched(schema):
    intent = QueryIntent(
        query_type="aggregate",
        tables=["products", "order_items"],
        columns=["products.product_name"],
        aggregations=["SUM(order_items.quantity * order_items.unit_price)"],
        group_by=["products.product_name"],
        order_by={"column": "SUM(order_items.quantity * order_items.unit_price)", "direction": "desc"},
        limit=10,
    )

    structured, result = _generate(schema, intent, "top 10 products by revenue")

    assert result.status == GenerationStatus.SUCCESS, result
    assert "unit_price" in result.sql
    assert not structured.recognized_entities.get("assumptions")


def test_non_ranking_group_by_still_asks_for_clarification(schema):
    intent = QueryIntent(
        query_type="select",
        tables=["products"],
        columns=["products.category"],
        group_by=["products.category"],
    )

    _, result = _generate(schema, intent, "Show products grouped by category")

    assert result.status == GenerationStatus.NEEDS_CLARIFICATION


def test_ranking_without_an_unambiguous_metric_still_asks_for_clarification(schema):
    # customers have no child table with a quantity column, so "top customers"
    # genuinely is ambiguous (orders? spend?) and must not be guessed.
    intent = QueryIntent(
        query_type="select",
        tables=["customers"],
        columns=["customers.first_name"],
        group_by=["customers.first_name"],
        limit=10,
    )

    _, result = _generate(schema, intent, "Show me the top 10 customers")

    assert result.status == GenerationStatus.NEEDS_CLARIFICATION
