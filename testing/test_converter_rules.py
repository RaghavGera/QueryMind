"""Deterministic converter rules: 'how many' counts and anti-joins."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from app.ambiguity_detector import AmbiguityDetector
from app.intent_converter import IntentConversionError, convert_query_intent
from app.intent_extractor import QueryIntent
from app.sql_generator import GenerationStatus, SQLGenerator
from testing.test_phase4 import build_mock_schema


@pytest.fixture
def schema():
    return build_mock_schema()


def _generate(schema, intent, question):
    structured = convert_query_intent(intent, question, schema=schema)
    return structured, SQLGenerator(schema, AmbiguityDetector(schema)).generate(structured)


def test_how_many_without_aggregation_becomes_count(schema):
    # The model sometimes answers "How many ...?" with a row listing.
    intent = QueryIntent(
        query_type="select",
        tables=["customers"],
        conditions=[{"column": "customers.signup_date", "operator": "BETWEEN",
                     "value": ["2026-09-01", "2026-09-30"]}],
    )

    structured, result = _generate(schema, intent, "How many new customers signed up last month?")

    assert result.status == GenerationStatus.SUCCESS, result
    assert result.sql.startswith('SELECT COUNT(*) AS "count_all"')
    assert structured.recognized_entities["assumptions"]


def test_how_many_drops_plain_columns_when_it_adds_the_count(schema):
    intent = QueryIntent(query_type="select", tables=["customers"], columns=["customers.customer_id"])

    _, result = _generate(schema, intent, "How many customers are there?")

    assert result.sql.startswith("SELECT COUNT(*)")
    assert "customer_id" not in result.sql.split("FROM")[0]


def test_how_many_keeps_model_supplied_aggregation(schema):
    intent = QueryIntent(
        query_type="count",
        tables=["customers"],
        columns=["customers.customer_id"],
        aggregations=["COUNT(customers.customer_id)"],
    )

    structured, result = _generate(schema, intent, "How many customers are there?")

    assert 'COUNT("customers"."customer_id")' in result.sql
    assert not structured.recognized_entities.get("assumptions")


def test_non_how_many_listing_is_untouched(schema):
    intent = QueryIntent(query_type="select", tables=["customers"], columns=["customers.email"])

    _, result = _generate(schema, intent, "List the emails of all customers.")

    assert "COUNT" not in result.sql


def test_never_ordered_becomes_a_left_anti_join(schema):
    intent = QueryIntent(
        query_type="select",
        tables=["customers", "orders"],
        columns=["customers.customer_id", "customers.first_name"],
        conditions=[{"column": "orders.order_id", "operator": "IS NULL", "value": None}],
    )

    _, result = _generate(schema, intent, "Find customers who have never placed an order.")

    assert result.status == GenerationStatus.SUCCESS, result
    assert 'FROM "customers"' in result.sql
    assert 'LEFT JOIN "orders" ON "customers"."customer_id" = "orders"."customer_id"' in result.sql
    assert 'WHERE "orders"."order_id" IS NULL' in result.sql
    assert "INNER JOIN" not in result.sql


def test_unqualified_is_null_column_is_resolved_for_anti_join(schema):
    intent = QueryIntent(
        query_type="select",
        tables=["customers", "orders"],
        columns=["customers.customer_id"],
        conditions=[{"column": "order_id", "operator": "IS NULL", "value": None}],
    )

    _, result = _generate(schema, intent, "customers without orders")

    assert "LEFT JOIN" in result.sql


def test_is_null_on_the_base_table_is_not_an_anti_join(schema):
    intent = QueryIntent(
        query_type="select",
        tables=["orders", "customers"],
        columns=["orders.order_id"],
        conditions=[{"column": "customers.country", "operator": "IS NULL", "value": None}],
    )

    _, result = _generate(schema, intent, "Show orders from customers with no country")

    assert "LEFT JOIN" not in result.sql


def test_having_without_aggregation_is_a_conversion_error_not_a_crash(schema):
    intent = QueryIntent(
        query_type="select",
        tables=["customers"],
        conditions=[{"column": "COUNT(orders.order_id)", "operator": ">", "value": 5}],
    )

    with pytest.raises(IntentConversionError):
        convert_query_intent(intent, "customers with more than 5 orders", schema=schema)
