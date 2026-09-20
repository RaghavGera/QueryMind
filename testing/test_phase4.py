"""
Phase 4 Test Script

Tests the SQL Generation engine, with a focus on how it detects and acts on
ambiguities from Phase 3 before ever emitting a query:
  - clean intents generate correct, parameterized SQL
  - dangerous intents (DELETE/UPDATE without WHERE) get BLOCKED, not run
  - a single fuzzy table match gets auto-resolved and SQL still comes out
  - a multi-way fuzzy table match asks for clarification instead of guessing
  - a table with no plausible match at all is a hard ERROR
  - joins, aggregations, GROUP BY/HAVING, INSERT and full-table-write bypass
    all produce the expected SQL shape

Unlike test_phase1-3.py, this script does NOT require a live database
connection. SQL generation and ambiguity detection only need a
DatabaseSchema object, so we build one in-memory that mirrors the real
e-commerce schema (customers, products, orders, order_items) from
database/text_to_sql_database.sql. This keeps the suite runnable in any
environment, including CI, with zero setup.
"""

import sys
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if sys.platform == 'win32':
    import codecs
    if sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
    if sys.stderr.encoding != 'utf-8':
        sys.stderr.reconfigure(encoding='utf-8')

from app.models import (
    AggregationType,
    Aggregation,
    Condition,
    ConditionOperator,
    Join,
    JoinType,
    OrderBy,
    OrderDirection,
    QueryType,
    StructuredIntent,
)
from app.schema import ColumnInfo, DatabaseSchema, ForeignKey, TableInfo
from app.sql_generator import GenerationStatus, SQLGenerationResult, SQLGenerator


# ====================================================================== #
# Mock schema (mirrors database/text_to_sql_database.sql)
# ====================================================================== #

def build_mock_schema() -> DatabaseSchema:
    """Build an in-memory DatabaseSchema matching the sample e-commerce DB."""

    def col(name, dtype, pk=False, nullable=False):
        return ColumnInfo(name=name, data_type=dtype, is_nullable=nullable, is_primary_key=pk)

    customers = TableInfo(
        name="customers",
        columns={
            "customer_id": col("customer_id", "integer", pk=True),
            "first_name": col("first_name", "character varying"),
            "last_name": col("last_name", "character varying"),
            "email": col("email", "character varying"),
            "country": col("country", "character varying"),
            "signup_date": col("signup_date", "date"),
        },
        primary_keys=["customer_id"],
    )

    products = TableInfo(
        name="products",
        columns={
            "product_id": col("product_id", "integer", pk=True),
            "product_name": col("product_name", "character varying"),
            "category": col("category", "character varying"),
            "price": col("price", "numeric"),
        },
        primary_keys=["product_id"],
    )

    orders = TableInfo(
        name="orders",
        columns={
            "order_id": col("order_id", "integer", pk=True),
            "customer_id": col("customer_id", "integer"),
            "order_date": col("order_date", "date"),
            "status": col("status", "character varying"),
        },
        primary_keys=["order_id"],
        foreign_keys=[ForeignKey(column="customer_id", referenced_table="customers", referenced_column="customer_id")],
    )

    order_items = TableInfo(
        name="order_items",
        columns={
            "order_item_id": col("order_item_id", "integer", pk=True),
            "order_id": col("order_id", "integer"),
            "product_id": col("product_id", "integer"),
            "quantity": col("quantity", "integer"),
            "unit_price": col("unit_price", "numeric"),
        },
        primary_keys=["order_item_id"],
        foreign_keys=[
            ForeignKey(column="order_id", referenced_table="orders", referenced_column="order_id"),
            ForeignKey(column="product_id", referenced_table="products", referenced_column="product_id"),
        ],
    )

    schema = DatabaseSchema()
    schema.tables = {
        "customers": customers,
        "products": products,
        "orders": orders,
        "order_items": order_items,
    }
    return schema


# ====================================================================== #
# Test harness helpers
# ====================================================================== #

PASS = "[PASS]"
FAIL = "[FAIL]"


def header(title: str) -> None:
    print("=" * 70)
    print(title)
    print("=" * 70)


def check(label: str, condition: bool, detail: str = "") -> bool:
    tag = PASS if condition else FAIL
    print(f"{tag} {label}" + (f" -- {detail}" if detail and not condition else ""))
    return condition


def show_result(result: SQLGenerationResult) -> None:
    print(f"    status: {result.status.value}")
    if result.sql:
        print("    sql:")
        for line in result.sql.splitlines():
            print(f"      {line}")
        print(f"    params: {result.params}")
    if result.warnings:
        print(f"    warnings: {result.warnings}")
    if result.clarification_questions:
        print(f"    clarification_questions: {result.clarification_questions}")
    if result.error_message:
        print(f"    error_message: {result.error_message}")


# ====================================================================== #
# Individual tests
# ====================================================================== #

def test_simple_select(schema) -> bool:
    header("TEST 1: Simple SELECT with WHERE")
    gen = SQLGenerator(schema)
    intent = StructuredIntent(
        query_type=QueryType.SELECT,
        tables=["customers"],
        columns=["first_name", "last_name", "email"],
        conditions=[Condition(operator=ConditionOperator.EQUALS, column="country", value="India")],
        original_question="Get names and emails of customers from India",
    )
    result = gen.generate(intent)
    show_result(result)

    ok = True
    ok &= check("status is SUCCESS", result.status == GenerationStatus.SUCCESS)
    ok &= check("SQL selects the right columns", '"first_name"' in result.sql and '"email"' in result.sql)
    ok &= check("SQL filters on country", 'WHERE "country" = %s' in result.sql)
    ok &= check("param carries the filter value", result.params == ["India"])
    return ok


def test_select_with_join_and_order(schema) -> bool:
    header("TEST 2: SELECT with JOIN, ORDER BY, LIMIT")
    gen = SQLGenerator(schema)
    intent = StructuredIntent(
        query_type=QueryType.SELECT,
        tables=["orders", "customers"],
        columns=["customers.first_name", "orders.order_date"],
        joins=[Join(
            join_type=JoinType.INNER,
            left_table="orders",
            right_table="customers",
            left_column="customer_id",
            right_column="customer_id",
        )],
        order_by=[OrderBy(column="orders.order_date", direction=OrderDirection.DESC)],
        limit=5,
        original_question="Show the 5 most recent orders with customer names",
    )
    result = gen.generate(intent)
    show_result(result)

    ok = True
    ok &= check("status is SUCCESS", result.status == GenerationStatus.SUCCESS)
    ok &= check("SQL contains an INNER JOIN", "INNER JOIN" in result.sql)
    ok &= check("SQL orders by order_date DESC", 'ORDER BY "orders"."order_date" DESC' in result.sql)
    ok &= check("SQL has LIMIT 5", "LIMIT 5" in result.sql)
    return ok


def test_aggregation_group_by_having(schema) -> bool:
    header("TEST 3: Aggregation with GROUP BY and HAVING")
    gen = SQLGenerator(schema)
    intent = StructuredIntent(
        query_type=QueryType.AGGREGATE,
        tables=["order_items"],
        aggregations=[Aggregation(aggregation_type=AggregationType.SUM, column="unit_price", alias="total_spent")],
        group_by=["product_id"],
        having_conditions=[Condition(operator=ConditionOperator.GREATER_THAN, column="total_spent", value=1000)],
        original_question="Total revenue per product, only products over 1000",
    )
    result = gen.generate(intent)
    show_result(result)

    ok = True
    ok &= check("status is SUCCESS", result.status == GenerationStatus.SUCCESS)
    ok &= check("SQL has SUM aggregation with alias", 'SUM("unit_price") AS "total_spent"' in result.sql)
    ok &= check("SQL has GROUP BY", 'GROUP BY "product_id"' in result.sql)
    ok &= check("SQL has HAVING", "HAVING" in result.sql and "total_spent" in result.sql)
    return ok


def test_count_star(schema) -> bool:
    header("TEST 4: COUNT(*) query")
    gen = SQLGenerator(schema)
    intent = StructuredIntent(
        query_type=QueryType.COUNT,
        tables=["customers"],
        aggregations=[Aggregation(aggregation_type=AggregationType.COUNT, alias="customer_count")],
        conditions=[Condition(operator=ConditionOperator.EQUALS, column="country", value="Canada")],
        original_question="How many customers are in Canada?",
    )
    result = gen.generate(intent)
    show_result(result)

    ok = True
    ok &= check("status is SUCCESS", result.status == GenerationStatus.SUCCESS)
    ok &= check("SQL uses COUNT(*)", 'COUNT(*) AS "customer_count"' in result.sql)
    return ok


def test_delete_without_where_blocked(schema) -> bool:
    header("TEST 5: DELETE without WHERE is BLOCKED, not executed")
    gen = SQLGenerator(schema)
    intent = StructuredIntent(
        query_type=QueryType.DELETE,
        tables=["customers"],
        original_question="Delete customers",
    )
    result = gen.generate(intent)
    show_result(result)

    ok = True
    ok &= check("status is BLOCKED", result.status == GenerationStatus.BLOCKED)
    ok &= check("no SQL was generated", result.sql is None)
    ok &= check("a clarification question was raised", len(result.clarification_questions) > 0)
    return ok


def test_delete_without_where_still_blocked_even_with_bypass_flag(schema) -> bool:
    header("TEST 6: allow_full_table_write does NOT bypass the ambiguity gate")
    gen = SQLGenerator(schema)
    intent = StructuredIntent(
        query_type=QueryType.DELETE,
        tables=["customers"],
        original_question="Delete customers",
    )
    # Even asking nicely with allow_full_table_write=True must not skip the
    # CRITICAL ambiguity check -- that's a deliberate, separate safety net.
    result = gen.generate(intent, allow_full_table_write=True)
    show_result(result)
    return check("status is still BLOCKED", result.status == GenerationStatus.BLOCKED)


def test_update_without_where_blocked_then_allowed(schema) -> bool:
    header("TEST 7: UPDATE without WHERE - blocked, then explicitly allowed once filtered")
    gen = SQLGenerator(schema)

    unfiltered = StructuredIntent(
        query_type=QueryType.UPDATE,
        tables=["orders"],
        update_values={"status": "cancelled"},
        original_question="Cancel all orders",
    )
    blocked_result = gen.generate(unfiltered)
    show_result(blocked_result)
    ok = check("unfiltered UPDATE is BLOCKED", blocked_result.status == GenerationStatus.BLOCKED)

    filtered = StructuredIntent(
        query_type=QueryType.UPDATE,
        tables=["orders"],
        update_values={"status": "cancelled"},
        conditions=[Condition(operator=ConditionOperator.EQUALS, column="status", value="pending")],
        original_question="Cancel all pending orders",
    )
    allowed_result = gen.generate(filtered)
    show_result(allowed_result)
    ok &= check("filtered UPDATE succeeds", allowed_result.status == GenerationStatus.SUCCESS)
    ok &= check("SQL has SET and WHERE", "SET" in allowed_result.sql and "WHERE" in allowed_result.sql)
    return ok


def test_delete_with_where_succeeds(schema) -> bool:
    header("TEST 8: DELETE with WHERE succeeds")
    gen = SQLGenerator(schema)
    intent = StructuredIntent(
        query_type=QueryType.DELETE,
        tables=["order_items"],
        conditions=[Condition(operator=ConditionOperator.EQUALS, column="order_id", value=42)],
        original_question="Delete items for order 42",
    )
    result = gen.generate(intent)
    show_result(result)

    ok = True
    ok &= check("status is SUCCESS", result.status == GenerationStatus.SUCCESS)
    ok &= check("SQL deletes from order_items with a filter", "DELETE FROM" in result.sql and "WHERE" in result.sql)
    ok &= check("param carries the order_id", result.params == [42])
    return ok


def test_insert(schema) -> bool:
    header("TEST 9: INSERT")
    gen = SQLGenerator(schema)
    intent = StructuredIntent(
        query_type=QueryType.INSERT,
        tables=["products"],
        insert_values={"product_name": "Wireless Mouse", "category": "Electronics", "price": 19.99},
        original_question="Add a new product called Wireless Mouse",
    )
    result = gen.generate(intent)
    show_result(result)

    ok = True
    ok &= check("status is SUCCESS", result.status == GenerationStatus.SUCCESS)
    ok &= check("SQL is an INSERT INTO products", "INSERT INTO" in result.sql and '"products"' in result.sql)
    ok &= check("params match the insert values", result.params == ["Wireless Mouse", "Electronics", 19.99])
    return ok


def test_single_fuzzy_table_match_auto_resolved(schema) -> bool:
    header("TEST 10: Single fuzzy table match is auto-resolved, SQL still generated")
    gen = SQLGenerator(schema)
    intent = StructuredIntent(
        query_type=QueryType.SELECT,
        tables=["cusomer"],  # typo -- fuzzy-matches only "customers"
        columns=["first_name"],
        original_question="Get all customer first names",
    )
    result = gen.generate(intent)
    show_result(result)

    ok = True
    ok &= check(
        "status is SUCCESS_WITH_WARNINGS",
        result.status == GenerationStatus.SUCCESS_WITH_WARNINGS,
    )
    ok &= check("SQL was still produced", result.sql is not None)
    ok &= check("SQL selects from the corrected table", '"customers"' in (result.sql or ""))
    ok &= check("a warning documents the auto-resolution", len(result.warnings) > 0)
    return ok


def test_multi_way_fuzzy_table_match_needs_clarification(schema) -> bool:
    header("TEST 11: Multi-way fuzzy table match asks for clarification")
    gen = SQLGenerator(schema)
    intent = StructuredIntent(
        query_type=QueryType.SELECT,
        tables=["order"],  # matches both "orders" and "order_items"
        columns=["order_id"],
        original_question="Get order ids",
    )
    result = gen.generate(intent)
    show_result(result)

    ok = True
    ok &= check(
        "status is NEEDS_CLARIFICATION",
        result.status == GenerationStatus.NEEDS_CLARIFICATION,
    )
    ok &= check("no SQL was generated", result.sql is None)
    ok &= check("a clarification question was raised", len(result.clarification_questions) > 0)
    return ok


def test_nonexistent_table_is_hard_error(schema) -> bool:
    header("TEST 12: Table with no plausible match at all is a hard ERROR")
    gen = SQLGenerator(schema)
    intent = StructuredIntent(
        query_type=QueryType.SELECT,
        tables=["widgets"],
        columns=["id"],
        original_question="Get all widgets",
    )
    result = gen.generate(intent)
    show_result(result)

    ok = True
    ok &= check("status is ERROR", result.status == GenerationStatus.ERROR)
    ok &= check("no SQL was generated", result.sql is None)
    ok &= check("error message names the bad table", "widgets" in (result.error_message or ""))
    return ok


def test_non_strict_mode_proceeds_with_warnings(schema) -> bool:
    header("TEST 13: non-strict mode proceeds on non-critical ambiguity instead of asking")
    gen = SQLGenerator(schema, strict=False, auto_resolve=False)
    intent = StructuredIntent(
        query_type=QueryType.SELECT,
        tables=["order"],  # multi-way match, HIGH severity, no suggested_resolution
        columns=["order_id"],
        original_question="Get order ids",
    )
    result = gen.generate(intent)
    show_result(result)

    ok = True
    ok &= check(
        "status is SUCCESS or SUCCESS_WITH_WARNINGS (not blocked)",
        result.status in (GenerationStatus.SUCCESS, GenerationStatus.SUCCESS_WITH_WARNINGS),
    )
    ok &= check("SQL was generated despite the ambiguity", result.sql is not None)
    ok &= check("the ambiguity is at least recorded as a warning", len(result.warnings) > 0)
    return ok


def test_in_and_between_operators(schema) -> bool:
    header("TEST 14: IN and BETWEEN operators render correctly")
    gen = SQLGenerator(schema)
    intent = StructuredIntent(
        query_type=QueryType.SELECT,
        tables=["orders"],
        columns=["order_id"],
        conditions=[
            Condition(operator=ConditionOperator.IN, column="status", value=["pending", "shipped"]),
            Condition(operator=ConditionOperator.BETWEEN, column="order_date",
                      value=["2026-01-01", "2026-06-30"], logic="AND"),
        ],
        original_question="Orders pending or shipped between Jan and June 2026",
    )
    result = gen.generate(intent)
    show_result(result)

    ok = True
    ok &= check("status is SUCCESS", result.status == GenerationStatus.SUCCESS)
    ok &= check("IN clause has two placeholders", "IN (%s, %s)" in result.sql)
    ok &= check("BETWEEN clause is present", "BETWEEN %s AND %s" in result.sql)
    ok &= check(
        "params contain both IN values and both BETWEEN values",
        result.params == ["pending", "shipped", "2026-01-01", "2026-06-30"],
    )
    return ok


# ====================================================================== #
# Runner
# ====================================================================== #

def print_summary(results: Dict[str, bool]) -> None:
    header("PHASE 4 TEST SUMMARY")
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    for name, ok in results.items():
        print(f"{PASS if ok else FAIL} {name}")
    print()
    print(f"Result: {passed}/{total} tests passed")
    if passed == total:
        print("ALL TESTS PASSED")
    else:
        print(f"{total - passed} TEST(S) FAILED")


def main() -> None:
    header("TEXT-TO-SQL PHASE 4 TEST SUITE")
    print("SQL Generation Engine (with ambiguity-aware gatekeeping)")
    print()

    schema = build_mock_schema()
    print(f"Mock schema loaded: {len(schema.tables)} tables ({', '.join(schema.tables)})")
    print()

    tests = [
        ("Simple SELECT with WHERE", test_simple_select),
        ("SELECT with JOIN/ORDER BY/LIMIT", test_select_with_join_and_order),
        ("Aggregation with GROUP BY/HAVING", test_aggregation_group_by_having),
        ("COUNT(*) query", test_count_star),
        ("DELETE without WHERE is blocked", test_delete_without_where_blocked),
        ("Bypass flag does not defeat ambiguity gate", test_delete_without_where_still_blocked_even_with_bypass_flag),
        ("UPDATE without WHERE blocked, then allowed once filtered", test_update_without_where_blocked_then_allowed),
        ("DELETE with WHERE succeeds", test_delete_with_where_succeeds),
        ("INSERT", test_insert),
        ("Single fuzzy table match auto-resolved", test_single_fuzzy_table_match_auto_resolved),
        ("Multi-way fuzzy table match needs clarification", test_multi_way_fuzzy_table_match_needs_clarification),
        ("Nonexistent table is a hard error", test_nonexistent_table_is_hard_error),
        ("Non-strict mode proceeds with warnings", test_non_strict_mode_proceeds_with_warnings),
        ("IN and BETWEEN operators", test_in_and_between_operators),
    ]

    results: Dict[str, bool] = {}
    for name, fn in tests:
        try:
            results[name] = fn(schema)
        except Exception as e:
            print(f"{FAIL} {name} raised an exception: {e}")
            import traceback
            traceback.print_exc()
            results[name] = False
        print()

    print_summary(results)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest suite interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
