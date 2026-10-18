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


def test_aggregation_aliases_read_as_headings():
    from app.intent_converter import readable_alias

    assert readable_alias("SUM", "order_items.quantity * order_items.unit_price") == "sum_quantity_x_unit_price"
    assert readable_alias("COUNT", "orders.order_id") == "count_order_id"
    assert readable_alias("COUNT", None) == "count_all"
    assert readable_alias("AVG_SUM", "order_items.quantity * order_items.unit_price") == "avg_sum_quantity_x_unit_price"


def test_aggregation_aliases_never_collide():
    from app.intent_converter import convert_aggregations

    aggs = convert_aggregations(["SUM(orders.amount)", "SUM(payments.amount)", "SUM(refunds.amount)"], [])
    assert [a.alias for a in aggs] == ["sum_amount", "sum_amount_2", "sum_amount_3"]


# --- Sales count completed orders only (owner decision 2026-10-18) -------------

_SALES_NOTE = "Sales count completed orders only; pending and cancelled orders are excluded."


def _sales_intent(**overrides):
    fields = dict(
        query_type="aggregate",
        tables=["order_items", "orders"],
        aggregations=["SUM(order_items.quantity * order_items.unit_price)"],
        conditions=[{"column": "orders.order_date", "operator": "BETWEEN", "value": ["2026-09-01", "2026-09-30"]}],
    )
    fields.update(overrides)
    return QueryIntent(**fields)


def _status_conditions(intent):
    return [(c.table, c.column, c.value) for c in intent.conditions if c.column == "status"]


def test_total_sales_counts_completed_orders_only(schema):
    intent = convert_query_intent(_sales_intent(), "Give me the total sales of last month.", schema=schema)
    assert _status_conditions(intent) == [("orders", "status", "Completed")]
    assert _SALES_NOTE in intent.recognized_entities["assumptions"]
    result = SQLGenerator(schema).generate(intent)
    assert result.status == GenerationStatus.SUCCESS
    assert result.params == ["2026-09-01", "2026-09-30", "Completed"]


def test_sales_rule_joins_orders_when_only_line_items_were_named(schema):
    intent = convert_query_intent(
        _sales_intent(tables=["order_items"], conditions=[]), "What is our total revenue?", schema=schema
    )
    assert "orders" in intent.tables
    assert _status_conditions(intent) == [("orders", "status", "Completed")]
    assert SQLGenerator(schema).generate(intent).status == GenerationStatus.SUCCESS


@pytest.mark.parametrize("question", [
    "What was the revenue from cancelled orders?",
    "Total sales including pending orders",
    "Revenue by order status",
    "Total revenue from completed orders",
])
def test_sales_rule_steps_aside_when_the_user_names_a_status(schema, question):
    intent = convert_query_intent(_sales_intent(conditions=[]), question, schema=schema)
    assert _status_conditions(intent) == []
    assert _SALES_NOTE not in intent.recognized_entities.get("assumptions", [])


def test_sales_rule_keeps_an_existing_status_filter(schema):
    intent = convert_query_intent(
        _sales_intent(conditions=[{"column": "orders.status", "operator": "=", "value": "Pending"}]),
        "What are our sales?",
        schema=schema,
    )
    assert _status_conditions(intent) == [("orders", "status", "Pending")]


def test_sales_rule_ignores_non_sales_questions(schema):
    counting = QueryIntent(query_type="count", tables=["customers"], aggregations=["COUNT(customers.customer_id)"])
    assert _status_conditions(convert_query_intent(counting, "How many customers are there?", schema=schema)) == []
    priced = QueryIntent(query_type="aggregate", tables=["products"], aggregations=["AVG(products.price)"])
    assert _status_conditions(convert_query_intent(priced, "What is the average product price?", schema=schema)) == []
