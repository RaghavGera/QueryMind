"""Text comparisons are case-insensitive; non-text columns are left alone."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from app.models import Condition, ConditionOperator, QueryType, StructuredIntent
from app.sql_generator import GenerationStatus, SQLGenerator
from testing.test_phase4 import build_mock_schema


def _sql(conditions, tables=None, columns=None):
    intent = StructuredIntent(
        query_type=QueryType.SELECT,
        tables=tables or ["orders"],
        columns=columns or ["order_id"],
        conditions=conditions,
        original_question="test",
    )
    result = SQLGenerator(build_mock_schema()).generate(intent)
    assert result.status == GenerationStatus.SUCCESS, result
    return result.sql, result.params


def test_status_equality_ignores_case():
    sql, params = _sql([Condition(column="status", operator=ConditionOperator.EQUALS, value="cancelled")])
    assert 'LOWER("status") = LOWER(%s)' in sql
    assert params == ["cancelled"]


def test_qualified_text_column_and_not_equals():
    sql, _ = _sql([Condition(table="customers", column="country", operator=ConditionOperator.NOT_EQUALS, value="india")],
                  tables=["customers"], columns=["customer_id"])
    assert 'LOWER("customers"."country") != LOWER(%s)' in sql


def test_in_list_ignores_case():
    sql, params = _sql([Condition(column="status", operator=ConditionOperator.IN, value=["completed", "pending"])])
    assert 'LOWER("status") IN (LOWER(%s), LOWER(%s))' in sql
    assert params == ["completed", "pending"]


def test_like_becomes_ilike():
    sql, _ = _sql([Condition(column="first_name", operator=ConditionOperator.LIKE, value="jo%")],
                  tables=["customers"], columns=["customer_id"])
    assert '"first_name" ILIKE %s' in sql


@pytest.mark.parametrize("column,table,value,fragment", [
    ("order_date", "orders", "2025-01-01", '"order_date" = %s'),   # date column
    ("order_id", "orders", 5, '"order_id" = %s'),                    # integer column
    ("price", "products", 9.5, '"price" = %s'),                      # numeric column
])
def test_non_text_columns_are_untouched(column, table, value, fragment):
    sql, _ = _sql([Condition(column=column, operator=ConditionOperator.EQUALS, value=value)],
                  tables=[table], columns=[column])
    assert fragment in sql
    assert "LOWER" not in sql
