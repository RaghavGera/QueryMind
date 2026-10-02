"""HAVING support: conditions on aggregates are rendered safely, never as WHERE."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from app.ambiguity_detector import AmbiguityDetector
from app.intent_converter import convert_query_intent
from app.intent_extractor import QueryIntent
from app.sql_generator import GenerationStatus, SQLGenerator
from testing.test_phase4 import build_mock_schema


@pytest.fixture
def schema():
    return build_mock_schema()


def _generate(schema, intent, question):
    structured = convert_query_intent(intent, question, schema=schema)
    return structured, SQLGenerator(schema, AmbiguityDetector(schema)).generate(structured)


def _orders_over_5():
    return QueryIntent(
        query_type="aggregate",
        tables=["customers", "orders"],
        columns=["customers.first_name", "customers.last_name"],
        aggregations=["COUNT(orders.order_id)"],
        group_by=["customers.customer_id", "customers.first_name", "customers.last_name"],
        conditions=[{"column": "COUNT(orders.order_id)", "operator": ">", "value": 5}],
    )


def test_aggregate_condition_becomes_having(schema):
    structured, result = _generate(schema, _orders_over_5(), "Which customers have placed more than 5 orders?")

    assert not structured.conditions
    assert len(structured.having_conditions) == 1
    assert result.status == GenerationStatus.SUCCESS, result
    assert 'HAVING COUNT("orders"."order_id") > %s' in result.sql
    assert "WHERE" not in result.sql
    assert result.params == [5]


def test_having_and_where_coexist(schema):
    intent = _orders_over_5()
    intent.conditions.append({"column": "customers.country", "operator": "=", "value": "India"})

    _, result = _generate(schema, intent, "Which Indian customers have placed more than 5 orders?")

    assert result.status == GenerationStatus.SUCCESS, result
    assert result.sql.index("WHERE") < result.sql.index("GROUP BY") < result.sql.index("HAVING")
    assert result.params == ["India", 5]


def test_having_on_arithmetic_aggregate(schema):
    intent = QueryIntent(
        query_type="aggregate",
        tables=["products", "order_items"],
        columns=["products.product_name"],
        aggregations=["SUM(order_items.quantity * order_items.unit_price)"],
        group_by=["products.product_name"],
        conditions=[{
            "column": "SUM(order_items.quantity * order_items.unit_price)",
            "operator": ">", "value": 10000,
        }],
    )

    _, result = _generate(schema, intent, "Which products generated more than 10,000 in revenue?")

    assert result.status == GenerationStatus.SUCCESS, result
    assert 'HAVING SUM("order_items"."quantity" * "order_items"."unit_price") > %s' in result.sql
    assert result.params == [10000]


@pytest.mark.parametrize("column", [
    "COUNT(orders.order_id); DROP TABLE orders",
    "SUM(order_items.quantity) -- ",
    "COUNT(nonexistent.column)",
    "SUM(order_items.nope)",
])
def test_malicious_or_unknown_having_columns_are_rejected(schema, column):
    intent = _orders_over_5()
    intent.conditions = [{"column": column, "operator": ">", "value": 5}]

    structured = convert_query_intent(intent, "q", schema=schema)
    result = SQLGenerator(schema, AmbiguityDetector(schema)).generate(structured)

    assert result.sql is None
    assert result.status in (GenerationStatus.ERROR, GenerationStatus.NEEDS_CLARIFICATION)
