"""
Real-World Ambiguity Detection Test

Tests the ambiguity detection engine on realistic business questions
to see how well it identifies unclear queries and generates clarification questions.
"""

import os
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Fix Windows console encoding issues
if sys.platform == 'win32':
    import codecs
    if sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
    if sys.stderr.encoding != 'utf-8':
        sys.stderr.reconfigure(encoding='utf-8')

# Import modules
from app.ambiguity_detector import AmbiguityDetector, AmbiguityType, SeverityLevel
from app.models import StructuredIntent, QueryType, Condition, ConditionOperator, Aggregation, AggregationType
from app.database import init_db
from app.schema import SchemaIntrospector
from app.entity_recognizer import EntityRecognizer
from app.intent_extractor import extract_intent


def setup():
    """Setup test environment."""
    db = init_db()
    if not db.test_connection():
        print("Database connection failed!")
        sys.exit(1)

    introspector = SchemaIntrospector(db)
    schema = introspector.introspect()

    return db, schema


def create_mock_intent_from_question(question: str, schema) -> StructuredIntent:
    """
    Create a mock structured intent from a question.
    This simulates what Phase 2 would produce.
    """

    question_lower = question.lower()

    # Question 1: "How many new customers did we get last month?"
    if "how many" in question_lower and "customers" in question_lower and "last month" in question_lower:
        return StructuredIntent(
            query_type=QueryType.COUNT,
            tables=["customers"],
            columns=["customer_id"],
            aggregations=[
                Aggregation(
                    aggregation_type=AggregationType.COUNT,
                    column="customer_id",
                    alias="new_customers"
                )
            ],
            original_question=question,
            confidence_score=0.75
        )

    # Question 2: "What were our sales last month?"
    if "sales" in question_lower and "last month" in question_lower:
        return StructuredIntent(
            query_type=QueryType.SELECT,
            tables=["orders"],
            columns=["total_amount"],
            aggregations=[
                Aggregation(
                    aggregation_type=AggregationType.SUM,
                    column="total_amount",
                    alias="total_sales"
                )
            ],
            original_question=question,
            confidence_score=0.70
        )

    # Question 3: "Who are our best customers?"
    if "best customers" in question_lower:
        return StructuredIntent(
            query_type=QueryType.SELECT,
            tables=["customers"],
            columns=["name"],
            limit=10,
            original_question=question,
            confidence_score=0.65
        )

    # Question 4: "Which products are performing well?"
    if "products" in question_lower and "performing" in question_lower:
        return StructuredIntent(
            query_type=QueryType.SELECT,
            tables=["products"],
            columns=["product_name"],
            original_question=question,
            confidence_score=0.60
        )

    # Question 5: "Which customers are inactive?"
    if "customers" in question_lower and "inactive" in question_lower:
        return StructuredIntent(
            query_type=QueryType.SELECT,
            tables=["customers"],
            columns=["name", "email"],
            original_question=question,
            confidence_score=0.70
        )

    # Question 6: "What is our conversion rate?"
    if "conversion rate" in question_lower:
        return StructuredIntent(
            query_type=QueryType.SELECT,
            tables=["customers", "orders"],
            columns=["*"],
            original_question=question,
            confidence_score=0.50
        )

    # Question 7: "How much revenue did Electronics generate?"
    if "revenue" in question_lower and "electronics" in question_lower:
        return StructuredIntent(
            query_type=QueryType.SELECT,
            tables=["products", "order_items"],
            columns=["total_price"],
            aggregations=[
                Aggregation(
                    aggregation_type=AggregationType.SUM,
                    column="total_price",
                    alias="total_revenue"
                )
            ],
            conditions=[
                Condition(
                    operator=ConditionOperator.EQUALS,
                    column="category",
                    value="Electronics",
                    table="products"
                )
            ],
            original_question=question,
            confidence_score=0.75
        )

    # Question 8: "Which country is doing the best?"
    if "country" in question_lower and "best" in question_lower:
        return StructuredIntent(
            query_type=QueryType.SELECT,
            tables=["customers"],
            columns=["country"],
            group_by=["country"],
            limit=1,
            original_question=question,
            confidence_score=0.60
        )

    # Question 9: "Do repeat customers spend more?"
    if "repeat customers" in question_lower and "spend" in question_lower:
        return StructuredIntent(
            query_type=QueryType.SELECT,
            tables=["customers", "orders"],
            columns=["name", "total_amount"],
            original_question=question,
            confidence_score=0.55
        )

    # Question 10: "What is our return rate?"
    if "return rate" in question_lower:
        return StructuredIntent(
            query_type=QueryType.SELECT,
            tables=["orders"],
            columns=["*"],
            original_question=question,
            confidence_score=0.50
        )

    # Default fallback
    return StructuredIntent(
        query_type=QueryType.SELECT,
        tables=["customers"],
        columns=["*"],
        original_question=question,
        confidence_score=0.30
    )


def test_question(detector: AmbiguityDetector, question: str, schema, question_num: int):
    """Test a single question for ambiguities."""
    print("=" * 80)
    print(f"QUESTION {question_num}: \"{question}\"")
    print("=" * 80)
    print()

    # Create mock intent
    intent = create_mock_intent_from_question(question, schema)

    # Show what we're analyzing
    print("Parsed Intent:")
    print(f"  Query Type: {intent.query_type.value}")
    print(f"  Tables: {', '.join(intent.tables)}")
    print(f"  Columns: {', '.join(intent.columns) if intent.columns else 'All (*)'}")
    if intent.conditions:
        print(f"  Conditions: {len(intent.conditions)}")
    if intent.aggregations:
        print(f"  Aggregations: {', '.join([agg.aggregation_type.value for agg in intent.aggregations])}")
    if intent.group_by:
        print(f"  Group By: {', '.join(intent.group_by)}")
    if intent.limit:
        print(f"  Limit: {intent.limit}")
    print(f"  Confidence: {intent.confidence_score:.2f}")
    print()

    # Detect ambiguities
    try:
        result = detector.detect_ambiguities(intent)

        print("Ambiguity Analysis:")
        print("-" * 80)

        if result.has_ambiguities:
            print(f"✓ Ambiguities Detected: {len(result.ambiguities)}")
            print(f"  Critical: {result.critical_count}")
            print(f"  High: {result.high_count}")
            print(f"  Can proceed to SQL: {'No' if not result.can_proceed else 'Yes (with clarification)'}")
            print()

            # Show each ambiguity
            for i, amb in enumerate(result.ambiguities, 1):
                severity_icon = {
                    SeverityLevel.CRITICAL: "🔴",
                    SeverityLevel.HIGH: "🟠",
                    SeverityLevel.MEDIUM: "🟡",
                    SeverityLevel.LOW: "🟢"
                }.get(amb.severity, "⚪")

                print(f"{i}. {severity_icon} {amb.ambiguity_type.value.upper().replace('_', ' ')} [{amb.severity.value}]")
                print(f"   Description: {amb.description}")
                print(f"   ❓ Clarification: {amb.clarification_question}")

                if amb.options:
                    print(f"   Options ({len(amb.options)}):")
                    for j, opt in enumerate(amb.options[:5], 1):  # Show first 5
                        # Format option display based on type
                        if 'table_name' in opt:
                            print(f"      {j}. {opt['table_name']}")
                        elif 'qualified_name' in opt:
                            print(f"      {j}. {opt['qualified_name']}")
                        elif 'function' in opt:
                            print(f"      {j}. {opt['function']} - {opt.get('description', '')}")
                        elif 'column' in opt:
                            print(f"      {j}. Order by: {opt['column']} {opt.get('direction', 'ASC')}")
                        elif 'action' in opt:
                            print(f"      {j}. {opt['action']}: {opt.get('description', '')}")
                        else:
                            print(f"      {j}. {opt}")

                    if len(amb.options) > 5:
                        print(f"      ... and {len(amb.options) - 5} more options")

                if amb.suggested_resolution:
                    print(f"   💡 Suggested: {amb.suggested_resolution}")

                print()
        else:
            print("✓ No ambiguities detected - Query is clear!")
            print("  This query can proceed directly to SQL generation.")
            print()

    except Exception as e:
        print(f"❌ Error analyzing question: {e}")
        import traceback
        traceback.print_exc()
        print()

    print()


def main():
    """Run real-world ambiguity detection tests."""
    print()
    print("=" * 80)
    print("REAL-WORLD AMBIGUITY DETECTION TEST")
    print("Testing business questions for clarity and completeness")
    print("=" * 80)
    print()

    # Setup
    print("Setting up...")
    db, schema = setup()
    detector = AmbiguityDetector(schema)
    print(f"✓ Connected to database: {db.config.database}")
    print(f"✓ Loaded schema: {len(schema.tables)} tables")
    print()

    # Real-world questions to test
    questions = [
        "How many new customers did we get last month?",
        "What were our sales last month?",
        "Who are our best customers?",
        "Which products are performing well?",
        "Which customers are inactive?",
        "What is our conversion rate?",
        "How much revenue did Electronics generate?",
        "Which country is doing the best?",
        "Do repeat customers spend more?",
        "What is our return rate?"
    ]

    # Test each question
    for i, question in enumerate(questions, 1):
        test_question(detector, question, schema, i)

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()
    print(f"Tested {len(questions)} real-world business questions")
    print()
    print("Key Insights:")
    print("  • Most business questions contain implicit assumptions")
    print("  • Time references ('last month') need clarification")
    print("  • Comparative terms ('best', 'performing well') are ambiguous")
    print("  • Multiple interpretation paths exist for most queries")
    print()
    print("The ambiguity engine helps ensure we generate the RIGHT SQL,")
    print("not just syntactically correct SQL.")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
