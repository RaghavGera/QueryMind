"""Plain-English explanations of generated queries (app/explain.py), through the real converter and generator."""

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ambiguity_detector import AmbiguityDetector
from app.explain import explain_intent, words
from app.intent_converter import convert_query_intent
from app.intent_extractor import QueryIntent
from app.sql_generator import SQLGenerator
from testing.test_phase4 import build_mock_schema

REV = "SUM(order_items.quantity * order_items.unit_price)"
cases = [
 ("How many customers are there?", dict(query_type="count", tables=["customers"], aggregations=["COUNT(customers.customer_id)"])),
 ("Which region generated the most revenue?", dict(query_type="aggregate", tables=["customers","orders","order_items"], columns=["customers.country"], aggregations=[REV], group_by=["customers.country"], order_by={"column": REV, "direction": "desc"})),
 ("Show customers from India.", dict(query_type="select", tables=["customers"], columns=["customers.first_name","customers.last_name"], conditions=[{"column":"country","operator":"=","value":"India","table":"customers"}])),
 ("Find products costing more than 500.", dict(query_type="select", tables=["products"], columns=["products.product_name","products.price"], conditions=[{"column":"price","operator":">","value":500,"table":"products"}])),
 ("Which customers have placed more than 5 orders?", dict(query_type="aggregate", tables=["customers","orders"], columns=["customers.first_name"], aggregations=["COUNT(orders.order_id)"], group_by=["customers.customer_id","customers.first_name"], conditions=[{"column":"COUNT(orders.order_id)","operator":">","value":5}])),
 ("Find customers who have never placed an order.", dict(query_type="select", tables=["customers","orders"], columns=["customers.first_name","customers.last_name"], conditions=[{"column":"orders.order_id","operator":"IS NULL"}])),
 ("Show monthly revenue from orders.", dict(query_type="aggregate", tables=["orders","order_items"], columns=["DATE_TRUNC('month', orders.order_date)"], aggregations=[REV], group_by=["DATE_TRUNC('month', orders.order_date)"], order_by={"column":"DATE_TRUNC('month', orders.order_date)","direction":"asc"})),
 ("What is the average order value?", dict(query_type="aggregate", tables=["orders","order_items"], aggregations=["AVG(SUM(order_items.quantity * order_items.unit_price))"], group_by=["orders.order_id"])),
 ("What were the top 5 products by revenue in each category?", dict(query_type="aggregate", tables=["products","order_items"], columns=["products.category","products.product_name"], aggregations=[REV], group_by=["products.category","products.product_name"], order_by={"column":REV,"direction":"desc"}, top_n_per_group={"partition_by":["products.category"],"n":5})),
 ("What are the top 10 most expensive products?", dict(query_type="select", tables=["products"], columns=["products.product_name","products.price"], order_by={"column":"products.price","direction":"desc"}, limit=10)),
 ("Show customers whose spending increased this quarter", dict(query_type="aggregate", tables=["customers","orders","order_items"], columns=["customers.customer_id","customers.first_name"], aggregations=[REV], group_by=["customers.customer_id","customers.first_name"], comparison={"date_column":"orders.order_date","grain":"quarter","direction":"increase","period":"this"})),
 ("Show orders placed after January 1, 2025.", dict(query_type="select", tables=["orders"], columns=["orders.order_id","orders.order_date"], conditions=[{"column":"order_date","operator":">","value":"2025-01-01","table":"orders"}])),
 ("Show all customers.", dict(query_type="select", tables=["customers"])),
 ("Show customers whose name contains Ann", dict(query_type="select", tables=["customers"], columns=["customers.first_name"], conditions=[{"column":"first_name","operator":"LIKE","value":"%Ann%","table":"customers"}])),
]

EXPECTED = {
    "How many customers are there?": "Counts customers.",
    "Which region generated the most revenue?": "Adds up quantity × unit price for each country, only where status is Completed, highest first, and shows the top result.",
    "Show customers from India.": "Lists first name and last name of customers, only where country is India.",
    "Find products costing more than 500.": "Lists product name and price of products, only where price is more than 500.",
    "Which customers have placed more than 5 orders?": "Counts orders for each customer, keeping only results where the number of orders is more than 5.",
    "Find customers who have never placed an order.": "Lists first name and last name of customers with no orders.",
    "Show monthly revenue from orders.": "Adds up quantity × unit price for each month of order date, only where status is Completed, in date order.",
    "What is the average order value?": "Works out the total of quantity × unit price for each order, then averages those totals.",
    "What were the top 5 products by revenue in each category?": "Adds up quantity × unit price for each category and product name, only where status is Completed, highest first, keeping the top 5 in each category.",
    "What are the top 10 most expensive products?": "Lists product name and price of products, sorted by price, highest first, and shows the top 10.",
    "Show customers whose spending increased this quarter": "Adds up quantity × unit price for each customer, only where status is Completed, comparing 2026-10-01 to 2026-12-31 with 2026-07-01 to 2026-09-30 and keeping those where it went up.",
    "Show orders placed after January 1, 2025.": "Lists order id and order date of orders, only where order date is after 2025-01-01.",
    "Show all customers.": "Lists every column of customers.",
    "Show customers whose name contains Ann": "Lists first name of customers, only where first name contains Ann.",
}


@pytest.mark.parametrize("question, fields", cases, ids=[q for q, _ in cases])
def test_every_query_shape_reads_as_plain_english(question, fields):
    schema = build_mock_schema()
    intent = convert_query_intent(QueryIntent(**fields), question, schema=schema, today=date(2026, 10, 20))
    result = SQLGenerator(schema, AmbiguityDetector(schema), strict=False).generate(intent)
    assert result.intent is not None, result.error_message
    assert explain_intent(result.intent, schema) == EXPECTED[question]


def test_column_words():
    assert words("order_items.unit_price") == "unit price"
    assert words("DATE_TRUNC('week', orders.order_date)") == "week of order date"
    assert words("SUM(order_items.quantity * order_items.unit_price)") == "the total of quantity × unit price"
    assert words("COUNT(orders.order_id)") == "the number of orders"


def test_writes_are_not_explained():
    from app.models import QueryType, StructuredIntent
    update = StructuredIntent(query_type=QueryType.UPDATE, tables=["products"], update_values={"price": 1}, original_question="x")
    assert explain_intent(update) == ""
