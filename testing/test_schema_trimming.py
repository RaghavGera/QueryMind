"""
Per-request schema trimming: only tables relevant to the question (plus their
foreign-key neighbours) are sent to the LLM; nothing recognised -> full schema.
Validation keeps using the full schema.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

import app.intent_extractor as extractor
from app.intent_extractor import (
    QueryIntent,
    relevant_tables,
    trim_schema_context,
    validate_intent_against_schema,
)
from app.main import _schema_context
from testing.llm_fakes import FakeCompletions, use_providers
from testing.test_phase4 import build_mock_schema


@pytest.fixture
def full_context():
    return _schema_context(build_mock_schema())


def _user_prompt(request):
    return next(m["content"] for m in request["messages"] if m["role"] == "user")


def test_trimming_keeps_only_relevant_tables(full_context):
    """(c) customers question -> customers + its FK neighbour orders; nothing else."""
    trimmed = trim_schema_context("How many customers are from each country?", full_context)

    assert trimmed["tables"] == ["customers", "orders"]
    assert set(trimmed["columns"]) == {"customers", "orders"}
    assert trimmed["relationships"] == ["orders.customer_id -> customers.customer_id"]
    assert "products" not in str(trimmed) and "order_items" not in str(trimmed)


def test_empty_recognizer_result_falls_back_to_full_schema(full_context, monkeypatch):
    """(d) recognizer finds nothing -> the full schema, unchanged."""
    monkeypatch.setattr(extractor.EntityRecognizer, "recognize_entities", lambda self, q: [])

    assert trim_schema_context("How many customers are there?", full_context) is full_context


def test_unrecognisable_question_uses_full_schema(full_context):
    # "region" is not a table or column; the LLM must see everything to map it.
    assert relevant_tables("Which region generated the most revenue?", full_context) == []
    assert trim_schema_context("Which region generated the most revenue?", full_context) is full_context


def test_foreign_key_neighbours_are_included_in_both_directions(full_context):
    # products is referenced by order_items -> order_items comes along.
    assert relevant_tables("What were our top 10 products?", full_context) == ["products", "order_items"]
    # orders references customers and is referenced by order_items.
    assert set(relevant_tables("Show cancelled orders.", full_context)) == {"customers", "orders", "order_items"}


def test_metric_words_bring_in_fact_tables(full_context):
    # Only "customer" is named, but revenue lives in order_items (two FKs away).
    tables = relevant_tables("How much revenue has each customer generated?", full_context)
    assert "order_items" in tables


def test_relationships_outside_the_trimmed_set_are_dropped(full_context):
    trimmed = trim_schema_context("What were our top 10 products?", full_context)
    assert trimmed["relationships"] == ["order_items.product_id -> products.product_id"]


def test_malformed_relationships_are_ignored(full_context):
    context = dict(full_context, relationships=["garbage", *full_context["relationships"]])
    assert relevant_tables("How many customers are from each country?", context) == ["customers", "orders"]


def test_context_without_columns_is_returned_as_is():
    context = {"tables": ["customers"]}
    assert trim_schema_context("customers", context) is context


def test_prompt_contains_only_the_trimmed_schema(full_context, monkeypatch):
    completions = FakeCompletions()
    use_providers(monkeypatch, groq=completions)

    extractor.extract_intent("How many customers are from each country?", full_context)

    prompt = _user_prompt(completions.requests[0])
    assert "customers(" in prompt and "orders(" in prompt
    assert "products(" not in prompt and "order_items(" not in prompt


def test_validation_still_uses_the_full_schema(full_context):
    # The model answered with a table that was trimmed from its prompt; it is
    # still a real table, so validation (against the full schema) accepts it.
    trimmed = trim_schema_context("How many customers are from each country?", full_context)
    assert "products" not in trimmed["columns"]

    intent = QueryIntent(query_type="select", tables=["products"], columns=["price"])
    ok, errors = validate_intent_against_schema(intent, full_context)
    assert ok, errors

    bogus = QueryIntent(query_type="select", tables=["invoices"], columns=["total"])
    ok, errors = validate_intent_against_schema(bogus, full_context)
    assert not ok
