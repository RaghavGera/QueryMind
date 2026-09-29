"""Targeted test for arithmetic-expression support in aggregations."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_phase4 import build_mock_schema
from app.models import Aggregation, AggregationType, QueryType, StructuredIntent
from app.sql_generator import GenerationStatus, SQLGenerator, SQLGenerationError

passed = failed = 0

def check(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}")

schema = build_mock_schema()
gen = SQLGenerator(schema)

# 1. Expression aggregation validates and renders correctly
print("TEST 1: SUM(quantity * unit_price) expression aggregation")
intent = StructuredIntent(
    query_type=QueryType.AGGREGATE,
    tables=["order_items"],
    columns=[],
    aggregations=[Aggregation(
        aggregation_type=AggregationType.SUM,
        column="order_items.quantity * order_items.unit_price",
        alias="total_revenue",
    )],
    original_question="What is total revenue?",
)
result = gen.generate(intent)
print("  SQL:", result.sql.replace("\n", " "))
check("status is SUCCESS", result.status == GenerationStatus.SUCCESS)
check(
    "renders quoted expression",
    'SUM("order_items"."quantity" * "order_items"."unit_price")' in result.sql,
)

# 2. Expression with GROUP BY (the region->country revenue question shape)
print("TEST 2: revenue per country with GROUP BY")
intent = StructuredIntent(
    query_type=QueryType.AGGREGATE,
    tables=["customers", "orders", "order_items"],
    columns=["customers.country"],
    group_by=["customers.country"],
    aggregations=[Aggregation(
        aggregation_type=AggregationType.SUM,
        column="order_items.quantity * order_items.unit_price",
        alias="total_revenue",
    )],
    order_by=[],
    original_question="Which country generated the most revenue?",
)
from app.models import Join, JoinType, OrderBy, OrderDirection
intent.joins = [
    Join(join_type=JoinType.INNER, left_table="orders", left_column="customer_id", right_table="customers", right_column="customer_id"),
    Join(join_type=JoinType.INNER, left_table="order_items", left_column="order_id", right_table="orders", right_column="order_id"),
]
intent.order_by = [OrderBy(column="SUM(order_items.quantity * order_items.unit_price)", direction=OrderDirection.DESC)]
intent.limit = 5
result = gen.generate(intent)
print("  SQL:", result.sql.replace("\n", " ") if result.sql else None)
check("status is SUCCESS", result.status == GenerationStatus.SUCCESS)
check("has GROUP BY country", result.sql is not None and 'GROUP BY "customers"."country"' in result.sql)
check(
    "order by renders expression",
    result.sql is not None and 'ORDER BY SUM("order_items"."quantity" * "order_items"."unit_price") DESC' in result.sql,
)

# 3. Invalid column inside expression is rejected
print("TEST 3: expression with unknown column is rejected")
intent = StructuredIntent(
    query_type=QueryType.AGGREGATE,
    tables=["order_items"],
    aggregations=[Aggregation(
        aggregation_type=AggregationType.SUM,
        column="order_items.quantity * order_items.nope",
    )],
    original_question="bad column",
)
result = gen.generate(intent)
check("status is ERROR", result.status == GenerationStatus.ERROR)
check("mentions bad column", "nope" in (result.error_message or ""))

# 4. SQL injection attempt in expression is rejected
print("TEST 4: injection attempt is rejected")
intent = StructuredIntent(
    query_type=QueryType.AGGREGATE,
    tables=["order_items"],
    aggregations=[Aggregation(
        aggregation_type=AggregationType.SUM,
        column="order_items.quantity); DROP TABLE customers; --",
    )],
    original_question="injection",
)
result = gen.generate(intent)
check("status is ERROR", result.status == GenerationStatus.ERROR)

# 5. Plain column aggregation still works (regression)
print("TEST 5: plain column aggregation unchanged")
intent = StructuredIntent(
    query_type=QueryType.AGGREGATE,
    tables=["order_items"],
    aggregations=[Aggregation(
        aggregation_type=AggregationType.SUM,
        column="order_items.quantity",
        alias="total_qty",
    )],
    original_question="total quantity",
)
result = gen.generate(intent)
check("status is SUCCESS", result.status == GenerationStatus.SUCCESS)
check("renders plain column", 'SUM("order_items"."quantity")' in result.sql)

print(f"\nResult: {passed}/{passed + failed} checks passed")
if failed:
    sys.exit(1)

# ---------------------------------------------------------------------
# TEST 6: join direction — FK holder joins when referenced table is FROM
# ---------------------------------------------------------------------
print("TEST 6: join swaps sides when right table is already the FROM table")
from app.models import JoinType
intent = StructuredIntent(
    query_type=QueryType.AGGREGATE,
    tables=["orders", "customers", "order_items"],
    columns=["customers.country"],
    group_by=["customers.country"],
    aggregations=[Aggregation(
        aggregation_type=AggregationType.SUM,
        column="order_items.quantity * order_items.unit_price",
        alias="total_revenue",
    )],
    joins=[
        Join(join_type=JoinType.INNER, left_table="orders", left_column="customer_id",
             right_table="customers", right_column="customer_id"),
        # right_table ("orders") is the FROM table: must swap to join order_items
        Join(join_type=JoinType.INNER, left_table="order_items", left_column="order_id",
             right_table="orders", right_column="order_id"),
    ],
    original_question="revenue per country",
)
result = gen.generate(intent)
print("  SQL:", result.sql.replace("\n", " ") if result.sql else None)
check("status is SUCCESS", result.status == GenerationStatus.SUCCESS)
check(
    "joins order_items, not orders twice",
    result.sql is not None and 'INNER JOIN "order_items" ON "orders"."order_id" = "order_items"."order_id"' in result.sql,
)
check(
    "no duplicate table",
    result.sql is not None and result.sql.count('FROM "orders"') == 1,
)

# ---------------------------------------------------------------------
# TEST 7: converter dedups qualified/unqualified aggregation columns
# ---------------------------------------------------------------------
print("TEST 7: converter drops plain column consumed by qualified aggregation")
from app.intent_converter import convert_query_intent
from app.intent_extractor import QueryIntent
qi = QueryIntent(
    query_type="count",
    tables=["customers"],
    columns=["customer_id", "COUNT(customers.customer_id)"],
    aggregations=["count"],
)
si = convert_query_intent(qi, "How many customers?", schema=schema)
check("plain column removed", si.columns == [])
check("aggregation kept", len(si.aggregations) == 1 and si.aggregations[0].column == "customers.customer_id")

print(f"\nFinal result: {passed}/{passed + failed} checks passed")
sys.exit(0 if failed == 0 else 1)
