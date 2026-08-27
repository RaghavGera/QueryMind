# Phase 1 Setup Guide

## Quick Start Commands

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Up Environment Variables

```bash
cp .env.example .env
```

Then edit `.env` with your actual PostgreSQL credentials:

```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=text_to_sql
DB_USER=your_postgres_username
DB_PASSWORD=your_postgres_password
```

### 3. Create and Load Database

**Option A: If database doesn't exist**

```bash
# Create database
psql -U postgres -c "CREATE DATABASE text_to_sql;"

# Load schema and data
psql -U postgres -d text_to_sql -f database/text_to_sql_database.sql
```

**Option B: If database exists**

```bash
# Just load the data
psql -U postgres -d text_to_sql -f database/text_to_sql_database.sql
```

### 4. Run Test Script

```bash
python test_phase1.py
```

This will verify:

- ✓ Database connection
- ✓ Schema introspection
- ✓ Table detection (customers, products, orders, order_items)
- ✓ Foreign key relationships
- ✓ Data exists in all tables

### 5. Start the API Server

```bash
python -m app.main
```

Or:

```bash
uvicorn app.main:app --reload
```

Server will start at: http://localhost:8000

### 6. Test the API Endpoints

**Health Check:**

```bash
curl http://localhost:8000/health
```

**List Tables:**

```bash
curl http://localhost:8000/schema/tables
```

**View Full Schema:**

```bash
curl http://localhost:8000/schema
```

**View Specific Table:**

```bash
curl http://localhost:8000/schema/tables/customers
curl http://localhost:8000/schema/tables/orders
```

## Expected Output Examples

### test_phase1.py

```
============================================================
TEXT-TO-SQL PHASE 1 TEST SUITE
============================================================

============================================================
TEST 1: Database Connection
============================================================
✓ Successfully connected to PostgreSQL
  Host: localhost
  Port: 5432
  Database: text_to_sql

============================================================
TEST 2: Schema Introspection
============================================================
✓ Found 4 tables

📋 Table: customers
   Columns: 6
   Primary Keys: customer_id
   Foreign Keys: None

📋 Table: products
   Columns: 4
   Primary Keys: product_id
   Foreign Keys: None

📋 Table: orders
   Columns: 4
   Primary Keys: order_id
   Foreign Keys:
      customer_id → customers.customer_id

📋 Table: order_items
   Columns: 5
   Primary Keys: order_item_id
   Foreign Keys:
      order_id → orders.order_id
      product_id → products.product_id

...

============================================================
✓ ALL TESTS PASSED
============================================================

Phase 1 is ready!
```

### /health endpoint

```json
{
  "status": "healthy",
  "database": {
    "host": "localhost",
    "port": 5432,
    "database": "text_to_sql",
    "connected": true
  }
}
```

### /schema/tables endpoint

```json
{
  "tables": ["customers", "order_items", "orders", "products"],
  "count": 4
}
```

## Troubleshooting

### Error: "DB_USER and DB_PASSWORD must be set"

- Make sure `.env` file exists (copy from `.env.example`)
- Verify DB_USER and DB_PASSWORD are set in `.env`

### Error: "Connection refused"

- Check PostgreSQL is running: `psql -U postgres -c "SELECT 1;"`
- Verify DB_HOST and DB_PORT in `.env`

### Error: "database does not exist"

```bash
createdb -U postgres text_to_sql
psql -U postgres -d text_to_sql -f database/text_to_sql_database.sql
```

### Error: "role does not exist"

- Update DB_USER in `.env` to match your PostgreSQL username
- Default is usually `postgres`

### Import errors

```bash
pip install -r requirements.txt --upgrade
```

## What Phase 1 Delivers

✅ **Database Connection**: Secure connection with environment variable configuration  
✅ **Schema Introspection**: Automatic detection of tables, columns, types  
✅ **Primary Keys**: Identifies all primary keys  
✅ **Foreign Keys**: Maps all relationships between tables  
✅ **Safety**: Read-only SQL execution (blocks INSERT/UPDATE/DELETE/DROP)  
✅ **FastAPI Endpoints**: RESTful API for health checks and schema viewing  
✅ **Production Patterns**: Connection pooling, context managers, error handling

## Project Structure After Phase 1

```
text-to-sql/
│
├── app/
│   ├── __init__.py
│   ├── main.py           # FastAPI app with endpoints
│   ├── database.py       # PostgreSQL connection & query execution
│   └── schema.py         # Schema introspection logic
│
├── benchmark/
│   └── text_to_sql_benchmark_with_sql.xlsx
│
├── database/
│   └── text_to_sql_database.sql
│
├── .env                  # Your credentials (create this)
├── .env.example          # Template
├── .gitignore
├── requirements.txt
├── README.md
├── SETUP.md             # This file
└── test_phase1.py       # Test script
```

## Ready for Phase 2?

Once all tests pass and the API is working, you're ready for Phase 2: Intent Extraction.

Phase 2 will add:

- Natural language question parsing
- Intent extraction using OpenAI
- Entity recognition (table/column identification)
- Structured intent representation
