"""
Phase 2 analytics: period-over-period comparison, top-N per group (window
function), nested aggregates and date bucketing.
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from app.ambiguity_detector import AmbiguityDetector
from app.intent_converter import IntentConversionError, convert_query_intent, period_bounds
from app.intent_extractor import QueryIntent
from app.models import StructuredIntent
from app.sql_generator import GenerationStatus, SQLGenerator
from testing.test_phase4 import build_mock_schema

TODAY = date(2026, 10, 2)
REVENUE = "SUM(order_items.quantity * order_items.unit_price)"


@pytest.fixture
def schema():
    return build_mock_schema()


def _generate(schema, intent, question, today=TODAY):
    structured = convert_query_intent(intent, question, schema=schema, today=today)
    return structured, SQLGenerator(schema, AmbiguityDetector(schema)).generate(structured)


# ---------------------------------------------------------------------- #
# Period bounds (computed from today's date, never by the LLM)
# ---------------------------------------------------------------------- #

@pytest.mark.parametrize("grain,offset,today,start,end", [
    ("quarter", 0, date(2026, 10, 2), date(2026, 10, 1), date(2027, 1, 1)),
    ("quarter", -1, date(2026, 10, 2), date(2026, 7, 1), date(2026, 10, 1)),
    ("quarter", -1, date(2026, 2, 14), date(2025, 10, 1), date(2026, 1, 1)),
    ("quarter", 0, date(2026, 6, 30), date(2026, 4, 1), date(2026, 7, 1)),
    ("month", 0, date(2026, 12, 31), date(2026, 12, 1), date(2027, 1, 1)),
    ("month", -1, date(2026, 1, 15), date(2025, 12, 1), date(2026, 1, 1)),
    ("month", -2, date(2026, 1, 15), date(2025, 11, 1), date(2025, 12, 1)),
    ("year", 0, date(2026, 10, 2), date(2026, 1, 1), date(2027, 1, 1)),
    ("year", -1, date(2026, 10, 2), date(2025, 1, 1), date(2026, 1, 1)),
])
def test_period_bounds(grain, offset, today, start, end):
    assert period_bounds(grain, offset, today) == (start, end)


def test_unknown_grain_is_rejected():
    with pytest.raises(IntentConversionError):
        period_bounds("fortnight", 0, TODAY)


# ---------------------------------------------------------------------- #
# Period-over-period comparison
# ---------------------------------------------------------------------- #

def _comparison_intent(**comparison_overrides):
    comparison = {"date_column": "orders.order_date", "grain": "quarter",
                  "direction": "increase", "period": "this"}
    comparison.update(comparison_overrides)
    entity = ["customers.customer_id", "customers.first_name", "customers.last_name"]
    return QueryIntent(
        query_type="aggregate",
        tables=["customers", "orders", "order_items"],
        columns=entity,
        aggregations=[REVENUE],
        group_by=entity,
        comparison=comparison,
    )


def test_spending_increased_this_quarter(schema):
    structured, result = _generate(
        schema, _comparison_intent(), "Show customers whose spending increased this quarter"
    )

    assert result.status == GenerationStatus.SUCCESS, result
    sql = result.sql
    assert sql.startswith("SELECT COALESCE(")
    assert 'FULL OUTER JOIN' in sql
    assert 'AS "cur"' in sql and 'AS "prev"' in sql
    assert 'WHERE (COALESCE("cur"."metric_value", 0) - COALESCE("prev"."metric_value", 0)) > 0' in sql
    assert 'ORDER BY (COALESCE("cur"."metric_value", 0) - COALESCE("prev"."metric_value", 0)) DESC' in sql
    assert 'AS "current_value"' in sql and 'AS "previous_value"' in sql and 'AS "change"' in sql
    assert '"orders"."order_date" >= %s AND "orders"."order_date" < %s' in sql
    # current period first, then the previous one
    assert result.params == ["2026-10-01", "2027-01-01", "2026-07-01", "2026-10-01"]
    # the quarter is not over yet -> say so
    assert any("still in progress" in w for w in result.warnings + structured.recognized_entities["assumptions"])


def test_decrease_and_change_directions(schema):
    _, decrease = _generate(schema, _comparison_intent(direction="decreased"), "spending decreased this quarter")
    assert ") < 0" in decrease.sql and decrease.sql.rstrip().endswith(") ASC")

    _, change = _generate(schema, _comparison_intent(direction="change"), "spending change this quarter")
    assert ") <> 0" in change.sql and "ORDER BY ABS(" in change.sql


def test_last_period_is_complete_and_not_flagged_in_progress(schema):
    structured, result = _generate(
        schema, _comparison_intent(period="last", grain="month"), "spending increased last month"
    )

    assert result.params[:2] == ["2026-09-01", "2026-10-01"]
    assert result.params[2:] == ["2026-08-01", "2026-09-01"]
    assert not structured.recognized_entities.get("assumptions")


def test_comparison_applies_existing_filters_to_both_periods(schema):
    intent = _comparison_intent()
    intent.conditions = [{"column": "orders.status", "operator": "=", "value": "completed"}]

    _, result = _generate(schema, intent, "completed spending increased this quarter")

    assert result.sql.count('LOWER("orders"."status") = LOWER(%s)') == 2
    assert result.params == [
        "completed", "2026-10-01", "2027-01-01",
        "completed", "2026-07-01", "2026-10-01",
    ]


def test_comparison_limit_is_kept(schema):
    intent = _comparison_intent()
    intent.limit = 10
    _, result = _generate(schema, intent, "top 10 customers whose spending increased this quarter")
    assert result.sql.rstrip().endswith("LIMIT 10")


def test_comparison_without_a_period_asks(schema):
    _, result = _generate(schema, _comparison_intent(grain=None), "Show customers whose spending increased")

    assert result.status == GenerationStatus.NEEDS_CLARIFICATION
    assert any("quarter" in q for q in result.clarification_questions)


def test_comparison_on_a_non_date_column_is_rejected(schema):
    _, result = _generate(schema, _comparison_intent(date_column="orders.status"), "spending increased")
    assert result.status == GenerationStatus.ERROR
    assert "not a date column" in result.error_message


def test_comparison_on_an_unknown_column_is_rejected(schema):
    _, result = _generate(schema, _comparison_intent(date_column="orders.nope"), "spending increased")
    assert result.status == GenerationStatus.ERROR


def test_comparison_needs_exactly_one_metric(schema):
    intent = _comparison_intent()
    intent.aggregations = [REVENUE, "COUNT(orders.order_id)"]
    with pytest.raises(IntentConversionError):
        convert_query_intent(intent, "spending increased", schema=schema, today=TODAY)


# ---------------------------------------------------------------------- #
# Top N per group
# ---------------------------------------------------------------------- #

def _top_n_intent(**overrides):
    base = dict(
        query_type="aggregate",
        tables=["products", "order_items"],
        columns=["products.category", "products.product_name"],
        aggregations=[REVENUE],
        group_by=["products.category", "products.product_name"],
        order_by={"column": REVENUE, "direction": "desc"},
        limit=5,
        top_n_per_group={"partition_by": ["products.category"], "n": 5},
    )
    base.update(overrides)
    return QueryIntent(**base)


def test_top_n_per_group_uses_a_window_function(schema):
    structured, result = _generate(schema, _top_n_intent(), "top 5 products by revenue in each category")

    assert result.status == GenerationStatus.SUCCESS, result
    sql = result.sql
    assert sql.startswith("SELECT * FROM (")
    assert (
        'ROW_NUMBER() OVER (PARTITION BY "products"."category" '
        'ORDER BY SUM("order_items"."quantity" * "order_items"."unit_price") DESC) AS "rank_in_group"'
    ) in sql
    assert 'WHERE "rank_in_group" <= 5' in sql
    assert sql.rstrip().endswith('ORDER BY "category", "rank_in_group"')
    assert structured.limit is None  # a stray overall LIMIT would cut off whole groups
    assert "LIMIT" not in sql


def test_top_n_partition_column_is_added_to_select_and_group_by(schema):
    intent = _top_n_intent(columns=["products.product_name"], group_by=["products.product_name"])
    structured, result = _generate(schema, intent, "top 5 products by revenue in each category")

    assert "products.category" in structured.columns and "products.category" in structured.group_by
    assert result.status == GenerationStatus.SUCCESS, result


def test_top_n_per_group_without_ordering_asks(schema):
    _, result = _generate(schema, _top_n_intent(order_by=None), "top 5 products in each category")
    assert result.status == GenerationStatus.NEEDS_CLARIFICATION


def test_top_n_per_group_rejects_a_bad_partition_column(schema):
    intent = _top_n_intent(top_n_per_group={"partition_by": ["products.nope"], "n": 5})
    _, result = _generate(schema, intent, "top 5 products by revenue in each category")
    assert result.status == GenerationStatus.ERROR


@pytest.mark.parametrize("spec", [{"partition_by": ["products.category"]}, {"partition_by": [], "n": 3}, {"n": "x"}])
def test_malformed_top_n_spec_is_a_conversion_error(schema, spec):
    with pytest.raises(IntentConversionError):
        convert_query_intent(_top_n_intent(top_n_per_group=spec), "q", schema=schema)


# ---------------------------------------------------------------------- #
# Nested aggregates (average order value)
# ---------------------------------------------------------------------- #

def test_average_order_value(schema):
    intent = QueryIntent(
        query_type="aggregate",
        tables=["orders", "order_items"],
        aggregations=[f"AVG({REVENUE})"],
        group_by=["orders.order_id"],
    )

    _, result = _generate(schema, intent, "What is the average order value?")

    assert result.status == GenerationStatus.SUCCESS, result
    assert result.sql.startswith('SELECT AVG("inner_query"."agg_value") AS "avg_sum_')
    assert 'SELECT SUM("order_items"."quantity" * "order_items"."unit_price") AS "agg_value"' in result.sql
    assert 'GROUP BY "orders"."order_id"' in result.sql
    assert result.sql.rstrip().endswith('AS "inner_query"')


def test_nested_aggregate_drops_ordering_and_limit(schema):
    intent = QueryIntent(
        query_type="aggregate",
        tables=["orders", "order_items"],
        aggregations=[f"MAX({REVENUE})"],
        group_by=["orders.order_id"],
        order_by={"column": REVENUE, "direction": "desc"},
        limit=1,
    )
    _, result = _generate(schema, intent, "What is the largest order total?")

    assert result.status == GenerationStatus.SUCCESS, result
    assert "LIMIT" not in result.sql and "ORDER BY" not in result.sql


def test_nested_aggregate_without_a_grouping_asks(schema):
    intent = QueryIntent(query_type="aggregate", tables=["orders", "order_items"], aggregations=[f"AVG({REVENUE})"])

    _, result = _generate(schema, intent, "What is the average order value?")

    assert result.status == GenerationStatus.NEEDS_CLARIFICATION
    assert any("for each what" in q for q in result.clarification_questions)


# ---------------------------------------------------------------------- #
# Date bucketing
# ---------------------------------------------------------------------- #

def _monthly_revenue(**overrides):
    base = dict(
        query_type="aggregate",
        tables=["orders", "order_items"],
        columns=["DATE_TRUNC('month', orders.order_date)"],
        aggregations=[REVENUE],
        group_by=["DATE_TRUNC('month', orders.order_date)"],
        order_by={"column": "DATE_TRUNC('month', orders.order_date)", "direction": "asc"},
    )
    base.update(overrides)
    return QueryIntent(**base)


def test_monthly_revenue(schema):
    _, result = _generate(schema, _monthly_revenue(), "Show monthly revenue")

    assert result.status == GenerationStatus.SUCCESS, result
    assert result.sql.startswith("SELECT DATE_TRUNC('month', \"orders\".\"order_date\") AS \"month\", SUM(")
    assert "GROUP BY DATE_TRUNC('month', \"orders\".\"order_date\")" in result.sql
    assert "ORDER BY DATE_TRUNC('month', \"orders\".\"order_date\") ASC" in result.sql


@pytest.mark.parametrize("expression", [
    "DATE_TRUNC('century', orders.order_date)",
    "DATE_TRUNC('month', orders.nope)",
    "DATE_TRUNC('month', orders.order_date); DROP TABLE orders",
    "DATE_TRUNC('month', orders.order_date) || 'x'",
    "strftime('%Y-%m', orders.order_date)",
])
def test_bad_date_bucket_expressions_are_rejected(schema, expression):
    intent = _monthly_revenue(columns=[expression], group_by=[expression], order_by=None)
    _, result = _generate(schema, intent, "Show monthly revenue")

    assert result.sql is None
    assert result.status in (GenerationStatus.ERROR, GenerationStatus.NEEDS_CLARIFICATION)


# ---------------------------------------------------------------------- #
# Serialization (resolve_ambiguity clones intents through to_dict/from_dict)
# ---------------------------------------------------------------------- #

def test_new_slots_survive_a_dict_round_trip(schema):
    comparison = convert_query_intent(_comparison_intent(), "q", schema=schema, today=TODAY)
    clone = StructuredIntent.from_dict(comparison.to_dict())
    assert clone.comparison == comparison.comparison

    top_n = convert_query_intent(_top_n_intent(), "q", schema=schema)
    assert StructuredIntent.from_dict(top_n.to_dict()).top_n_per_group == top_n.top_n_per_group

    nested = convert_query_intent(
        QueryIntent(query_type="aggregate", tables=["orders", "order_items"],
                    aggregations=[f"AVG({REVENUE})"], group_by=["orders.order_id"]),
        "q", schema=schema,
    )
    assert StructuredIntent.from_dict(nested.to_dict()).outer_aggregation == nested.outer_aggregation
