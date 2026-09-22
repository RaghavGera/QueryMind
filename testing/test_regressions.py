import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from app.intent_converter import convert_query_intent
from app.intent_extractor import QueryIntent
from app.models import (
    Aggregation,
    AggregationType,
    OrderBy,
    OrderDirection,
    QueryType,
    StructuredIntent,
)
from app.sql_generator import GenerationStatus, SQLGenerator
from testing.test_phase4 import build_mock_schema


@pytest.fixture
def schema():
    return build_mock_schema()


def generate(schema, *, columns=None, aggregations=None, group_by=None, order_by=None, tables=None):
    intent = StructuredIntent(
        query_type=QueryType.AGGREGATE if aggregations else QueryType.SELECT,
        tables=tables or ["products"],
        columns=columns or [],
        aggregations=aggregations or [],
        group_by=group_by or [],
        order_by=order_by or [],
        original_question="regression test",
    )
    return SQLGenerator(schema).generate(intent)


def test_simple_column_selection(schema):
    result = generate(schema, columns=["product_name"])
    assert result.status == GenerationStatus.SUCCESS
    assert result.sql == 'SELECT "product_name"\nFROM "products"'


@pytest.mark.parametrize("function", [AggregationType.COUNT, AggregationType.SUM, AggregationType.AVG])
def test_basic_aggregations(schema, function):
    column = None if function == AggregationType.COUNT else "price"
    result = generate(
        schema,
        tables=["products"],
        aggregations=[Aggregation(aggregation_type=function, column=column, alias="value")],
    )
    assert result.status == GenerationStatus.SUCCESS
    expected = "COUNT(*)" if function == AggregationType.COUNT else f'{function.value}("price")'
    assert expected in result.sql


def test_group_by_and_order_by_aggregation(schema):
    result = generate(
        schema,
        tables=["products"],
        columns=["category"],
        aggregations=[Aggregation(aggregation_type=AggregationType.SUM, column="price", alias="total")],
        group_by=["category"],
        order_by=[OrderBy(column="SUM(price)", direction=OrderDirection.DESC)],
    )
    assert result.status == GenerationStatus.SUCCESS
    assert 'GROUP BY "category"' in result.sql
    assert 'ORDER BY SUM("price") DESC' in result.sql


def test_converter_removes_aggregation_expression_and_derives_fk_join(schema):
    query_intent = QueryIntent(
        query_type="aggregate",
        tables=["order_items"],
        columns=["products.product_name", "SUM(order_items.quantity)"],
        aggregations=["SUM(order_items.quantity)"],
        group_by=["products.product_id", "products.product_name"],
        order_by={"column": "SUM(order_items.quantity)", "direction": "desc"},
        limit=10,
    )
    intent = convert_query_intent(query_intent, "top products by quantity sold", schema=schema)
    result = SQLGenerator(schema).generate(intent)
    assert "SUM(order_items.quantity)" not in intent.columns
    assert intent.tables == ["order_items", "products"]
    assert intent.joins[0].left_column == "product_id"
    assert result.status == GenerationStatus.SUCCESS
    assert 'INNER JOIN "products" ON "order_items"."product_id" = "products"."product_id"' in result.sql
    assert 'ORDER BY SUM("order_items"."quantity") DESC' in result.sql


def test_qualified_columns_require_existing_table_and_column(schema):
    missing_column = generate(schema, columns=["products.not_a_column"])
    assert missing_column.status == GenerationStatus.ERROR
    assert "does not exist" in missing_column.error_message

    missing_table = generate(schema, tables=["not_a_table"], columns=["name"])
    assert missing_table.status == GenerationStatus.ERROR


def test_aggregate_expression_in_columns_is_rejected(schema):
    result = generate(schema, columns=["SUM(price)"])
    assert result.status == GenerationStatus.ERROR
    assert "Invalid SELECT expression" in result.error_message


def test_empty_result_shape_is_supported():
    schema = build_mock_schema()
    result = generate(schema, columns=["product_name"])
    assert result.status == GenerationStatus.SUCCESS
    assert result.params == []