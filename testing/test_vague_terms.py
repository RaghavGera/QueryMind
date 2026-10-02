"""
Ambiguity-is-a-feature tests: vague wording must produce a clarification
question, never a guessed threshold/window/metric.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from app import vague_terms
from app.ambiguity_detector import AmbiguityDetector, AmbiguityType
from app.intent_converter import convert_query_intent
from app.intent_extractor import QueryIntent
from app.sql_generator import GenerationStatus, SQLGenerator
from testing.test_phase4 import build_mock_schema


@pytest.mark.parametrize("question,term", [
    ("Show me expensive products.", "expensive"),
    ("Show me cheap electronics.", "cheap"),
    ("Show me customers with high spending.", "high"),
    ("List large orders", "large"),
])
def test_vague_threshold_is_flagged(question, term):
    assert vague_terms.vague_threshold_term(question) == term


@pytest.mark.parametrize("question", [
    "What are the top 10 most expensive products?",
    "Find products costing more than 500.",
    "Show products over 100",
    "Show me the 5 cheapest products",
    "Which category has the highest average price?",
    "How many customers are there?",
    "Show me expensive products.\n\nUser clarification: price above 500",
    "Show me expensive products.\n\nUser clarification: the pricey ones",  # clarified once -> never loop
])
def test_threshold_not_flagged_when_given(question):
    assert vague_terms.vague_threshold_term(question) is None


@pytest.mark.parametrize("question", ["Show me recent orders.", "Give me the recently placed orders"])
def test_vague_recency_is_flagged(question):
    assert vague_terms.vague_recency_term(question)


@pytest.mark.parametrize("question", [
    "Show orders from the last 7 days",
    "Show the 10 most recent orders",
    "How many new customers signed up last month?",
    "Show me recent orders.\n\nUser clarification: last week",
])
def test_recency_not_flagged_when_window_given(question):
    assert vague_terms.vague_recency_term(question) is None


@pytest.mark.parametrize("question", [
    "Show me the top customers.",
    "Show me the best products.",
    "Show me popular products.",
    "What are the most popular categories?",
])
def test_ranking_without_metric_is_flagged(question):
    assert vague_terms.needs_ranking_metric(question)


@pytest.mark.parametrize("question", [
    "What are the top 10 customers by total spending?",
    "Give me the biggest spenders.",
    "What are our best-selling products?",
    "What are the top 5 products by quantity sold?",
    "What are the top 10 most expensive products?",
    "Which customers have placed the most orders?",
    "Show me the top customers.\n\nUser clarification: by spending",
])
def test_ranking_not_flagged_when_metric_named(question):
    assert vague_terms.needs_ranking_metric(question) is None


# ---------------------------------------------------------------------- #
# End to end through detector + generator, with the "helpful guess" an LLM
# actually produced in the eval run.
# ---------------------------------------------------------------------- #

@pytest.fixture
def schema():
    return build_mock_schema()


def _generate(schema, intent, question):
    structured = convert_query_intent(intent, question, schema=schema)
    return SQLGenerator(schema, AmbiguityDetector(schema)).generate(structured)


def test_guessed_price_threshold_is_not_executed(schema):
    guessed = QueryIntent(
        query_type="filter",
        tables=["products"],
        columns=["products.product_name", "products.price"],
        conditions=[{"column": "price", "operator": ">", "value": 500}],
        order_by={"column": "price", "direction": "desc"},
    )

    result = _generate(schema, guessed, "Show me expensive products.")

    assert result.status == GenerationStatus.NEEDS_CLARIFICATION
    assert result.sql is None
    assert any("expensive" in q for q in result.clarification_questions)


def test_guessed_spend_ranking_is_not_executed(schema):
    guessed = QueryIntent(
        query_type="aggregate",
        tables=["customers", "orders", "order_items"],
        columns=["customers.first_name"],
        aggregations=["SUM(order_items.quantity * order_items.unit_price)"],
        group_by=["customers.first_name"],
        order_by={"column": "SUM(order_items.quantity * order_items.unit_price)", "direction": "desc"},
        limit=10,
    )

    result = _generate(schema, guessed, "Show me the top customers.")

    assert result.status == GenerationStatus.NEEDS_CLARIFICATION
    assert any("ranked by" in q for q in result.clarification_questions)


def test_guessed_recency_window_is_not_executed(schema):
    guessed = QueryIntent(
        query_type="select",
        tables=["orders"],
        columns=["orders.order_id", "orders.order_date"],
        conditions=[{"column": "order_date", "operator": ">=", "value": "2026-09-01"}],
    )

    result = _generate(schema, guessed, "Show me recent orders.")

    assert result.status == GenerationStatus.NEEDS_CLARIFICATION
    assert any("time window" in q for q in result.clarification_questions)


def test_clarified_question_proceeds(schema):
    clarified = QueryIntent(
        query_type="filter",
        tables=["products"],
        columns=["products.product_name", "products.price"],
        conditions=[{"column": "price", "operator": ">", "value": 500}],
    )

    result = _generate(
        schema, clarified, "Show me expensive products.\n\nUser clarification: price above 500"
    )

    assert result.status == GenerationStatus.SUCCESS, result
    assert "> %s" in result.sql
    assert result.params == [500]


def test_top_products_still_answers_with_assumption(schema):
    intent = QueryIntent(
        query_type="aggregate",
        tables=["products", "order_items"],
        columns=["products.product_name"],
        aggregations=["SUM(order_items.quantity)"],
        group_by=["products.product_name"],
        order_by={"column": "SUM(order_items.quantity)", "direction": "desc"},
        limit=10,
    )

    structured = convert_query_intent(intent, "What were our top 10 products?", schema=schema)
    result = SQLGenerator(schema, AmbiguityDetector(schema)).generate(structured)

    assert result.status == GenerationStatus.SUCCESS, result
    assert structured.recognized_entities["assumptions"]


def test_qualified_condition_column_is_normalized(schema):
    intent = QueryIntent(
        query_type="count",
        tables=["customers"],
        columns=["customers.customer_id"],
        aggregations=["COUNT(customers.customer_id)"],
        conditions=[{"column": "customers.signup_date", "operator": "BETWEEN",
                     "value": ["2026-09-01", "2026-09-30"]}],
    )

    structured = convert_query_intent(intent, "How many new customers signed up last month?", schema=schema)
    condition = structured.conditions[0]
    assert (condition.table, condition.column) == ("customers", "signup_date")

    result = SQLGenerator(schema, AmbiguityDetector(schema)).generate(structured)
    assert result.status == GenerationStatus.SUCCESS, result  # no false "which date column?" question
    assert result.params == ["2026-09-01", "2026-09-30"]
