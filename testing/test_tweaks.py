"""Quick tweaks: signed plans, allowed changes only, and /query/tweak end to end (no database, no model)."""

import asyncio
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.main as main_module
from app import tweaks
from app.ambiguity_detector import AmbiguityDetector
from app.intent_converter import convert_query_intent
from app.intent_extractor import QueryIntent
from app.sql_generator import SQLGenerator
from testing.test_auth import FakeStore
from testing.test_phase4 import build_mock_schema


@pytest.fixture(autouse=True)
def secret(monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", "s" * 48)
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client.apps.googleusercontent.com")


def _intent(**overrides):
    fields = dict(
        query_type="aggregate", tables=["products"], columns=["products.category"],
        aggregations=["MAX(products.price)"], group_by=["products.category"],
        order_by={"column": "MAX(products.price)", "direction": "desc"},
        conditions=[{"column": "price", "operator": ">", "value": 100, "table": "products"}], limit=5,
    )
    fields.update(overrides)
    return convert_query_intent(QueryIntent(**fields), "Which category has the priciest products?", schema=build_mock_schema())


# --------------------------------------------------------------------------- #
# Signed plans
# --------------------------------------------------------------------------- #

def test_a_plan_round_trips_and_cannot_be_forged(monkeypatch):
    intent = _intent()
    token = tweaks.sign_plan(intent, "demo")
    read, workspace = tweaks.read_plan(token)
    assert read == intent and workspace == "demo"

    packed, signature = token.split(".")
    for forged in (packed + "x." + signature, packed + "." + signature[:-2] + "AA", "garbage", ""):
        with pytest.raises(tweaks.TweakError, match="can't be adjusted"):
            tweaks.read_plan(forged)
    monkeypatch.setenv("SESSION_SECRET", "t" * 48)
    with pytest.raises(tweaks.TweakError):
        tweaks.read_plan(token)  # another server's (or an old) secret


def test_without_a_secret_there_are_no_tweaks(monkeypatch):
    monkeypatch.delenv("SESSION_SECRET")
    assert tweaks.sign_plan(_intent(), "demo") is None
    with pytest.raises(tweaks.TweakError) as info:
        tweaks.read_plan("a.b")
    assert info.value.status == 503


# --------------------------------------------------------------------------- #
# What can change
# --------------------------------------------------------------------------- #

def test_the_controls_an_answer_offers():
    controls = {c["id"]: c for c in tweaks.describe(_intent(), build_mock_schema())}
    assert controls["agg:0"]["options"] == ["MAX", "MIN", "AVG", "SUM", "COUNT"], "price is a number"
    assert controls["sort"]["value"] == "desc" and controls["limit"]["value"] == 5
    assert controls["where:0"] == {**controls["where:0"], "type": "number", "operator": ">", "value": 100}


def test_text_columns_offer_no_sum_or_average():
    intent = _intent(aggregations=["MAX(products.product_name)"], order_by={"column": "MAX(products.product_name)", "direction": "desc"})
    control = next(c for c in tweaks.describe(intent, build_mock_schema()) if c["id"] == "agg:0")
    assert control["options"] == ["MAX", "MIN", "COUNT"]
    with pytest.raises(tweaks.TweakError, match="can't use SUM"):
        tweaks.apply(intent, {"agg:0": "SUM"}, build_mock_schema())


def test_max_to_min_takes_the_sort_and_the_column_name_with_it():
    schema = build_mock_schema()
    changed, summary = tweaks.apply(_intent(), {"agg:0": "min", "sort": "asc", "limit": 3, "where:0": {"operator": "<", "value": "250"}}, schema)
    assert changed.aggregations[0].aggregation_type.value == "MIN" and changed.aggregations[0].alias == "min_price"
    assert changed.order_by[0].column == "MIN(products.price)" and changed.order_by[0].direction.value == "ASC"
    assert changed.limit == 3 and (changed.conditions[0].operator.value, changed.conditions[0].value) == ("<", 250)
    assert summary == ["MIN instead of MAX of price", "lowest first", "top 3", "price < 250"]
    sql = SQLGenerator(schema, AmbiguityDetector(schema), strict=False).generate(changed).sql
    assert 'MIN("products"."price")' in sql and "LIMIT 3" in sql and "%s" in sql, "values stay parameters"


@pytest.mark.parametrize("changes, message", [
    ({"agg:7": "MIN"}, "can't be changed"),                         # not offered
    ({"tables": ["querymind_meta.users"]}, "can't be changed"),    # no structure changes, ever
    ({"limit": 0}, "between 1 and 1,000"),
    ({"limit": 5000}, "between 1 and 1,000"),
    ({"where:0": {"operator": "LIKE", "value": "x"}}, "can't be compared with LIKE"),
    ({"where:0": {"value": "lots"}}, "needs a number"),
    ({"sort": "sideways"}, "highest first or lowest first"),
    ({"agg:0": "MAX"}, "Nothing changed"),
    ({}, "Choose something"),
])
def test_only_offered_changes_of_the_right_type(changes, message):
    with pytest.raises(tweaks.TweakError, match=message):
        tweaks.apply(_intent(), changes, build_mock_schema())


def test_dates_must_be_real_dates():
    intent = convert_query_intent(QueryIntent(
        query_type="select", tables=["orders"], columns=["orders.order_id"],
        conditions=[{"column": "order_date", "operator": ">", "value": "2025-01-01", "table": "orders"}]),
        "Orders after 2025", schema=build_mock_schema())
    with pytest.raises(tweaks.TweakError, match="needs a date"):
        tweaks.apply(intent, {"where:0": {"value": "next tuesday"}}, build_mock_schema())
    changed, _ = tweaks.apply(intent, {"where:0": {"value": "2025-06-30"}}, build_mock_schema())
    assert changed.conditions[0].value == "2025-06-30"


def test_writes_and_comparisons_offer_nothing():
    update = convert_query_intent(QueryIntent(query_type="update", tables=["products"], values={"price": "1"},
                                              conditions=[{"column": "product_id", "operator": "=", "value": 1, "table": "products"}]),
                                  "Set price", schema=build_mock_schema())
    assert tweaks.describe(update, build_mock_schema()) == []


# --------------------------------------------------------------------------- #
# Through the API
# --------------------------------------------------------------------------- #

class _RowsDB:
    def __init__(self):
        self.queries = []

    def execute_query(self, query, params=None, max_rows=None):
        self.queries.append((query, params))
        return [{"category": "Laptops", "agg": 1}]


@pytest.fixture
def api(monkeypatch):
    store = FakeStore()
    db = _RowsDB()
    monkeypatch.setattr(main_module, "_store", store)
    monkeypatch.setattr(main_module, "SchemaIntrospector", lambda _db, *a: type("I", (), {"introspect": lambda self: build_mock_schema()})())
    monkeypatch.setattr(main_module, "extract_intent", lambda q, c: QueryIntent(
        query_type="aggregate", tables=["products"], columns=["products.category"], aggregations=["MAX(products.price)"],
        group_by=["products.category"], order_by={"column": "MAX(products.price)", "direction": "desc"}, limit=1))
    main_module.app.dependency_overrides[main_module.get_db] = lambda: db

    def call(path, json):
        async def go():
            transport = httpx.ASGITransport(app=main_module.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://api.test") as client:
                return await client.post(path, json=json)
        return asyncio.run(go())

    yield type("Api", (), {"call": staticmethod(call), "store": store, "db": db})
    main_module.app.dependency_overrides.clear()


def test_an_answer_can_be_tweaked_without_using_a_question(api):
    first = api.call("/query", {"question": "Which category has the most expensive product?"}).json()
    assert first["status"] == "success" and first["intent_token"]
    assert {c["id"] for c in first["tweaks"]} >= {"agg:0", "sort", "limit"}
    used = dict(api.store.usage)

    tweaked = api.call("/query/tweak", {"intent_token": first["intent_token"], "changes": {"agg:0": "MIN", "sort": "asc"}}).json()
    assert tweaked["status"] == "success" and 'MIN("products"."price")' in tweaked["sql"]
    assert tweaked["adjusted"] == ["MIN instead of MAX of price", "lowest first"]
    assert tweaked["explanation"].startswith("Finds the lowest price for each category")
    assert tweaked["intent_token"] != first["intent_token"], "the new answer can be tweaked again"
    questions = {k: v for k, v in api.store.usage.items() if not k.startswith("runs:")}
    assert questions == used, "no question was used"
    assert any(k.startswith("runs:") for k in api.store.usage), "but the run was counted"


def test_tweak_runs_have_their_own_daily_cap(api, monkeypatch):
    monkeypatch.setenv("ANON_TWEAK_DAILY_LIMIT", "1")
    token = api.call("/query", {"question": "q"}).json()["intent_token"]
    assert api.call("/query/tweak", {"intent_token": token, "changes": {"agg:0": "MIN"}}).status_code == 200
    refused = api.call("/query/tweak", {"intent_token": token, "changes": {"agg:0": "AVG"}})
    assert refused.status_code == 429 and "adjusted runs today" in refused.json()["error"]


def test_a_forged_token_or_someone_elses_workspace_is_refused(api, monkeypatch):
    assert api.call("/query/tweak", {"intent_token": "nope.nope", "changes": {"sort": "asc"}}).status_code == 400
    other = tweaks.sign_plan(_intent(), "42")  # a workspace this (signed-out) caller can't use
    refused = api.call("/query/tweak", {"intent_token": other, "changes": {"sort": "asc"}})
    assert refused.status_code == 401


def test_an_adjusted_answer_can_be_run_again_as_it_is(api):
    token = api.call("/query", {"question": "q"}).json()["intent_token"]
    tweaked = api.call("/query/tweak", {"intent_token": token, "changes": {"agg:0": "MIN"}}).json()
    again = api.call("/query/tweak", {"intent_token": tweaked["intent_token"], "rerun": True}).json()
    assert again["status"] == "success" and again["sql"] == tweaked["sql"] and again["adjusted"] == []
    assert api.call("/query/tweak", {"intent_token": token}).status_code == 400, "no changes and no rerun"


def test_sort_summaries_follow_the_column_type():
    schema = build_mock_schema()
    by_date = convert_query_intent(QueryIntent(
        query_type="select", tables=["orders"], columns=["orders.order_id"],
        order_by={"column": "order_date", "direction": "desc", "table": "orders"}, limit=10), "Latest orders", schema=schema)
    assert tweaks.apply(by_date, {"sort": "asc"}, schema)[1] == ["oldest first"]
    by_name = _intent(aggregations=["MAX(products.product_name)"], order_by={"column": "products.category", "direction": "asc"})
    assert tweaks.apply(by_name, {"sort": "desc"}, schema)[1] == ["Z to A"]
