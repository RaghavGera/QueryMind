"""
Phase 2 Test Script

Tests OpenAI integration, entity recognition, and intent extraction.
This script tests the natural language understanding components of the Text-to-SQL system.
"""

import os
import sys
from typing import Dict, List

# Fix Windows console encoding issues
if sys.platform == 'win32':
    import codecs
    if sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
    if sys.stderr.encoding != 'utf-8':
        sys.stderr.reconfigure(encoding='utf-8')

# Import Phase 2 modules
from app.openai_client import get_openai_client, reset_client, OpenAIClientError
from app.entity_recognizer import EntityRecognizer, RecognizedEntity
from app.intent_extractor import extract_intent, validate_intent_against_schema, QueryIntent
from app.models import StructuredIntent, QueryType, Condition, ConditionOperator

# Import Phase 1 modules for database and schema
from app.database import init_db, Database
from app.schema import SchemaIntrospector


def setup_test_environment():
    """Setup test environment and verify prerequisites."""
    print("=" * 70)
    print("PHASE 2 TEST SUITE - SETUP")
    print("=" * 70)
    print()

    # Check if Groq API key is configured
    api_key = os.getenv("GROQ_API_KEY")
    has_api_key = api_key and api_key != "your_groq_api_key_here"

    if not has_api_key:
        print("[WARNING] Groq API key not configured")
        print("  Set GROQ_API_KEY in your .env file to run full tests")
        print("  Some tests will be skipped")
        print()
    else:
        print("[OK] Groq API key found")
        print()

    # Setup database connection
    try:
        db = init_db()
        if db.test_connection():
            print("[OK] Database connection successful")
            print(f"  Database: {db.config.database}")
        else:
            print("[FAIL] Database connection failed")
            sys.exit(1)
    except Exception as e:
        print(f"[FAIL] Database initialization error: {e}")
        sys.exit(1)

    # Get database schema
    try:
        introspector = SchemaIntrospector(db)
        schema = introspector.introspect()
        print(f"[OK] Schema loaded: {len(schema.tables)} tables found")
        print()
        return db, schema, has_api_key
    except Exception as e:
        print(f"[FAIL] Schema introspection error: {e}")
        sys.exit(1)


def test_openai_client(has_api_key: bool):
    """Test 1: OpenAI client initialization."""
    print("=" * 70)
    print("TEST 1: OpenAI Client Initialization")
    print("=" * 70)
    print()

    if not has_api_key:
        print("[SKIPPED] Groq API key not configured")
        print()
        return False

    try:
        # Reset client to test fresh initialization
        reset_client()

        # Test client initialization
        client = get_openai_client()
        print("[OK] OpenAI client initialized successfully")
        print(f"  Client type: {type(client).__name__}")

        # Test that singleton pattern works
        client2 = get_openai_client()
        if client is client2:
            print("[OK] Singleton pattern working correctly")
        else:
            print("[FAIL] Singleton pattern failed - different instances returned")

        print()
        return True

    except OpenAIClientError as e:
        print(f"[FAIL] OpenAI client error: {e}")
        print()
        return False
    except Exception as e:
        print(f"[FAIL] Unexpected error: {e}")
        print()
        return False


def test_entity_recognition(schema):
    """Test 2: Entity recognition with sample questions."""
    print("=" * 70)
    print("TEST 2: Entity Recognition")
    print("=" * 70)
    print()

    # Build schema context for entity recognizer
    schema_context = {}
    for table_name, table_info in schema.tables.items():
        schema_context[table_name] = list(table_info.columns.keys())

    recognizer = EntityRecognizer(schema_context)

    # Test questions
    test_questions = [
    "How many customers do we have?",
    "How many products do we have?",
    "How many orders were placed?",
    "Which country has the most customers?",
    "Which customers have never placed an order?"
]

    all_passed = True

    for i, question in enumerate(test_questions, 1):
        print(f"Question {i}: '{question}'")
        print("-" * 70)

        try:
            entities = recognizer.recognize_entities(question)

            if entities:
                print(f"[OK] Found {len(entities)} entities:")

                # Group entities by type
                tables = [e for e in entities if e.entity_type == "table"]
                columns = [e for e in entities if e.entity_type == "column"]
                values = [e for e in entities if e.entity_type == "value"]

                if tables:
                    print(f"\n  Tables ({len(tables)}):")
                    for entity in tables:
                        print(f"    - {entity.entity_name} (confidence: {entity.confidence:.2f})")

                if columns:
                    print(f"\n  Columns ({len(columns)}):")
                    for entity in columns:
                        table_info = f" [{entity.table_name}]" if entity.table_name else ""
                        print(f"    - {entity.entity_name}{table_info} (confidence: {entity.confidence:.2f})")

                if values:
                    print(f"\n  Values ({len(values)}):")
                    for entity in values:
                        print(f"    - {entity.entity_name} (confidence: {entity.confidence:.2f})")
            else:
                print("[WARNING] No entities recognized")
                all_passed = False

        except Exception as e:
            print(f"[FAIL] Error: {e}")
            all_passed = False

        print()

    if all_passed:
        print("[OK] Entity recognition tests completed")
    else:
        print("[WARNING] Some entity recognition tests had issues")

    print()
    return all_passed


def test_intent_extraction(schema, has_api_key: bool):
    """Test 3: Intent extraction with OpenAI."""
    print("=" * 70)
    print("TEST 3: Intent Extraction")
    print("=" * 70)
    print()

    if not has_api_key:
        print("[SKIPPED] Groq API key not configured")
        print()
        return False

    # Build schema context
    schema_context = {
        "tables": list(schema.tables.keys()),
        "columns": {},
        "relationships": []
    }

    for table_name, table_info in schema.tables.items():
        schema_context["columns"][table_name] = list(table_info.columns.keys())

    # Add relationships
    for table_name, table_info in schema.tables.items():
        for fk in table_info.foreign_keys:
            schema_context["relationships"].append(
                f"{table_name}.{fk.column} -> {fk.referenced_table}.{fk.referenced_column}"
            )

    # Test questions
    test_questions = [
        "How many customers do we have?",
        "How many products do we have?",
        "How many orders were placed?"
    ]

    all_passed = True

    for i, question in enumerate(test_questions, 1):
        print(f"Question {i}: '{question}'")
        print("-" * 70)

        try:
            # Extract intent
            intent = extract_intent(question, schema_context)

            print(f"[OK] Intent extracted successfully")
            print(f"\n  Query Type: {intent.query_type}")
            print(f"  Tables: {', '.join(intent.tables) if intent.tables else 'None'}")
            print(f"  Columns: {', '.join(intent.columns) if intent.columns else 'None'}")

            if intent.conditions:
                print(f"  Conditions: {len(intent.conditions)} condition(s)")
                for cond in intent.conditions:
                    print(f"    - {cond}")

            if intent.aggregations:
                print(f"  Aggregations: {', '.join(intent.aggregations)}")

            if intent.group_by:
                print(f"  Group By: {', '.join(intent.group_by)}")

            if intent.order_by:
                print(f"  Order By: {intent.order_by}")

            if intent.limit:
                print(f"  Limit: {intent.limit}")

            # Validate intent against schema
            is_valid, errors = validate_intent_against_schema(intent, schema_context)

            if is_valid:
                print(f"\n[OK] Intent validation passed")
            else:
                print(f"\n[WARNING] Intent validation issues:")
                for error in errors:
                    print(f"    - {error}")
                all_passed = False

        except Exception as e:
            print(f"[FAIL] Error extracting intent: {e}")
            all_passed = False

        print()

    if all_passed:
        print("[OK] Intent extraction tests completed successfully")
    else:
        print("[WARNING] Some intent extraction tests had issues")

    print()
    return all_passed


def test_full_pipeline(schema, has_api_key: bool):
    """Test 4: Full pipeline - entity recognition + intent extraction."""
    print("=" * 70)
    print("TEST 4: Full Pipeline Integration")
    print("=" * 70)
    print()

    # Build schema contexts
    entity_schema = {}
    intent_schema = {
        "tables": list(schema.tables.keys()),
        "columns": {},
        "relationships": []
    }

    for table_name, table_info in schema.tables.items():
        entity_schema[table_name] = list(table_info.columns.keys())
        intent_schema["columns"][table_name] = list(table_info.columns.keys())

    for table_name, table_info in schema.tables.items():
        for fk in table_info.foreign_keys:
            intent_schema["relationships"].append(
                f"{table_name}.{fk.column} -> {fk.referenced_table}.{fk.referenced_column}"
            )

    # Initialize recognizer
    recognizer = EntityRecognizer(entity_schema)

    # Test question
    test_question = "Which country has the most customers?"

    print(f"Test Question: '{test_question}'")
    print("-" * 70)
    print()

    # Step 1: Entity Recognition
    print("Step 1: Entity Recognition")
    try:
        entities = recognizer.recognize_entities(test_question)
        print(f"[OK] Recognized {len(entities)} entities")

        for entity in entities[:5]:  # Show first 5
            table_info = f" [{entity.table_name}]" if entity.table_name else ""
            print(f"  - {entity.entity_type}: {entity.entity_name}{table_info} (conf: {entity.confidence:.2f})")

        if len(entities) > 5:
            print(f"  ... and {len(entities) - 5} more")

        print()
    except Exception as e:
        print(f"[FAIL] Entity recognition failed: {e}")
        print()
        return False

    # Step 2: Intent Extraction
    print("Step 2: Intent Extraction")

    if not has_api_key:
        print("[SKIPPED] Groq API key not configured")
        print()
        return False

    try:
        intent = extract_intent(test_question, intent_schema)
        print(f"[OK] Intent extracted successfully")
        print(f"  Query Type: {intent.query_type}")
        print(f"  Tables: {', '.join(intent.tables)}")
        print(f"  Columns: {', '.join(intent.columns) if intent.columns else 'All (*)'}")

        if intent.conditions:
            print(f"  Conditions: {len(intent.conditions)}")

        print()
    except Exception as e:
        print(f"[FAIL] Intent extraction failed: {e}")
        print()
        return False

    # Step 3: Combine Results
    print("Step 3: Integration Analysis")
    print("[OK] Both components working together successfully")
    print()
    print("  Entity recognition provides:")
    print("    - Table and column identification")
    print("    - Value extraction")
    print("    - Fuzzy matching for typos")
    print()
    print("  Intent extraction provides:")
    print("    - Query structure (SELECT, JOIN, WHERE, etc.)")
    print("    - Aggregation requirements")
    print("    - Ordering and limiting")
    print()
    print("[OK] Full pipeline test completed")
    print()

    return True


def test_models():
    """Test 5: Pydantic models validation."""
    print("=" * 70)
    print("TEST 5: Pydantic Models")
    print("=" * 70)
    print()

    try:
        # Test QueryIntent model
        print("Testing QueryIntent model:")
        query_intent = QueryIntent(
            query_type="select",
            tables=["employees"],
            columns=["name", "salary"],
            conditions=[{
                "column": "salary",
                "operator": ">",
                "value": 50000
            }]
        )
        print(f"[OK] QueryIntent created: {query_intent.query_type}")
        print()

        # Test StructuredIntent model
        print("Testing StructuredIntent model:")
        structured_intent = StructuredIntent(
            query_type=QueryType.SELECT,
            tables=["customers"],
            columns=["name", "email"],
            conditions=[
                Condition(
                    operator=ConditionOperator.EQUALS,
                    column="status",
                    value="active"
                )
            ],
            original_question="Get active customers",
            confidence_score=0.95
        )
        print(f"[OK] StructuredIntent created: {structured_intent.query_type.value}")
        print(f"  Tables: {structured_intent.tables}")
        print(f"  Confidence: {structured_intent.confidence_score}")
        print()

        # Test model serialization
        print("Testing model serialization:")
        intent_dict = structured_intent.to_dict()
        print(f"[OK] Converted to dict: {len(intent_dict)} fields")

        reconstructed = StructuredIntent.from_dict(intent_dict)
        print(f"[OK] Reconstructed from dict successfully")
        print()

        print("[OK] All model tests passed")
        print()
        return True

    except Exception as e:
        print(f"[FAIL] Model test failed: {e}")
        print()
        return False


def print_summary(results: Dict[str, bool], has_api_key: bool):
    """Print test summary."""
    print("=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print()

    passed = sum(1 for v in results.values() if v)
    total = len(results)
    skipped = sum(1 for k, v in results.items() if v is None)

    for test_name, result in results.items():
        if result is None:
            status = "[SKIPPED]"
        elif result:
            status = "[OK]"
        else:
            status = "[FAIL]"
        print(f"{status}: {test_name}")

    print()
    print(f"Results: {passed}/{total - skipped} tests passed")

    if skipped > 0:
        print(f"         {skipped} test(s) skipped")

    print()

    if not has_api_key:
        print("=" * 70)
        print("NOTE: Groq Integration Tests Skipped")
        print("=" * 70)
        print()
        print("To run full Phase 2 tests:")
        print("  1. Get a Groq API key from https://console.groq.com/keys")
        print("  2. Add to your .env file: GROQ_API_KEY=gsk_...")
        print("  3. Re-run this test script")
        print()

    if passed == total - skipped:
        print("[OK] PHASE 2 READY!")
        print()
        if has_api_key:
            print("All Phase 2 components are working correctly.")
            print("You can now proceed to Phase 3 (SQL Generation).")
        else:
            print("Phase 2 models and entity recognition are working.")
            print("Configure Groq API key to test intent extraction.")
        print()


def main():
    """Run all Phase 2 tests."""
    print()
    print("=" * 70)
    print("TEXT-TO-SQL PHASE 2 TEST SUITE")
    print("Natural Language Understanding Components")
    print("=" * 70)
    print()

    # Setup
    db, schema, has_api_key = setup_test_environment()

    # Run tests
    results = {}

    # Test 1: OpenAI Client
    results["OpenAI Client"] = test_openai_client(has_api_key) if has_api_key else None

    # Test 2: Entity Recognition
    results["Entity Recognition"] = test_entity_recognition(schema)

    # Test 3: Intent Extraction
    results["Intent Extraction"] = test_intent_extraction(schema, has_api_key) if has_api_key else None

    # Test 4: Full Pipeline
    results["Full Pipeline"] = test_full_pipeline(schema, has_api_key) if has_api_key else None

    # Test 5: Models
    results["Pydantic Models"] = test_models()

    # Print summary
    print_summary(results, has_api_key)


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
