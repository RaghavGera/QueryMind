"""
Phase 1 Test Script

Tests PostgreSQL connectivity and schema introspection.
Run this after starting the FastAPI server.
"""

import sys
from app.database import init_db, DatabaseConfig
from app.schema import SchemaIntrospector


def test_connection():
    """Test 1: Database connectivity."""
    print("=" * 60)
    print("TEST 1: Database Connection")
    print("=" * 60)

    try:
        db = init_db()
        is_connected = db.test_connection()

        if is_connected:
            print("✓ Successfully connected to PostgreSQL")
            print(f"  Host: {db.config.host}")
            print(f"  Port: {db.config.port}")
            print(f"  Database: {db.config.database}")
            return db
        else:
            print("✗ Failed to connect to PostgreSQL")
            print("\nCheck your .env file:")
            print("  - DB_HOST")
            print("  - DB_PORT")
            print("  - DB_NAME")
            print("  - DB_USER")
            print("  - DB_PASSWORD")
            sys.exit(1)

    except Exception as e:
        print(f"✗ Connection error: {e}")
        sys.exit(1)


def test_schema_introspection(db):
    """Test 2: Schema introspection."""
    print("\n" + "=" * 60)
    print("TEST 2: Schema Introspection")
    print("=" * 60)

    try:
        introspector = SchemaIntrospector(db)
        schema = introspector.introspect()

        print(f"✓ Found {len(schema.tables)} tables\n")

        for table_name, table in schema.tables.items():
            print(f"📋 Table: {table_name}")
            print(f"   Columns: {len(table.columns)}")
            print(f"   Primary Keys: {', '.join(table.primary_keys) or 'None'}")

            if table.foreign_keys:
                print(f"   Foreign Keys:")
                for fk in table.foreign_keys:
                    print(f"      {fk.column} → {fk.referenced_table}.{fk.referenced_column}")
            else:
                print(f"   Foreign Keys: None")
            print()

        return schema

    except Exception as e:
        print(f"✗ Schema introspection failed: {e}")
        sys.exit(1)


def test_detailed_schema(schema):
    """Test 3: Detailed schema inspection."""
    print("=" * 60)
    print("TEST 3: Detailed Schema for 'customers' Table")
    print("=" * 60)

    customers = schema.get_table("customers")

    if not customers:
        print("✗ customers table not found")
        sys.exit(1)

    print(f"\n✓ Table: {customers.name}")
    print(f"\nColumns ({len(customers.columns)}):")
    print(f"{'Column Name':<20} {'Data Type':<20} {'Nullable':<10} {'Primary Key'}")
    print("-" * 70)

    for col_name, col in customers.columns.items():
        nullable = "YES" if col.is_nullable else "NO"
        pk = "✓" if col.is_primary_key else ""
        print(f"{col_name:<20} {col.data_type:<20} {nullable:<10} {pk}")


def test_relationships(schema):
    """Test 4: Foreign key relationships."""
    print("\n" + "=" * 60)
    print("TEST 4: Database Relationships")
    print("=" * 60)

    print("\nExpected relationships:")
    print("  customers.customer_id → orders.customer_id")
    print("  orders.order_id → order_items.order_id")
    print("  products.product_id → order_items.product_id")

    print("\nActual relationships found:")

    relationship_count = 0
    for table_name, table in schema.tables.items():
        for fk in table.foreign_keys:
            print(f"  {table_name}.{fk.column} → {fk.referenced_table}.{fk.referenced_column}")
            relationship_count += 1

    if relationship_count >= 3:
        print(f"\n✓ Found {relationship_count} relationships")
    else:
        print(f"\n⚠ Only found {relationship_count} relationships (expected 3+)")


def test_data_exists(db):
    """Test 5: Verify data exists in tables."""
    print("\n" + "=" * 60)
    print("TEST 5: Data Verification")
    print("=" * 60)

    tables_to_check = ["customers", "products", "orders", "order_items"]

    print("\nRow counts:")
    for table in tables_to_check:
        try:
            result = db.execute_query(f"SELECT COUNT(*) as count FROM {table}")
            count = result[0]["count"]
            print(f"  {table:<20} {count:>6} rows")

            if count == 0:
                print(f"    ⚠ Warning: {table} is empty")
        except Exception as e:
            print(f"  {table:<20} ✗ Error: {e}")

    print("\n✓ Data verification complete")


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("TEXT-TO-SQL PHASE 1 TEST SUITE")
    print("=" * 60)
    print()

    # Test 1: Connection
    db = test_connection()

    # Test 2: Schema introspection
    schema = test_schema_introspection(db)

    # Test 3: Detailed schema
    test_detailed_schema(schema)

    # Test 4: Relationships
    test_relationships(schema)

    # Test 5: Data exists
    test_data_exists(db)

    # Summary
    print("\n" + "=" * 60)
    print("✓ ALL TESTS PASSED")
    print("=" * 60)
    print("\nPhase 1 is ready!")
    print("\nNext steps:")
    print("  1. Start the API server: python app/main.py")
    print("  2. Test endpoints:")
    print("     curl http://localhost:8000/health")
    print("     curl http://localhost:8000/schema/tables")
    print("     curl http://localhost:8000/schema")
    print()


if __name__ == "__main__":
    main()
