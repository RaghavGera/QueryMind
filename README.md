# Text-to-SQL System with Clarification Engine

A production-quality Text-to-SQL system that detects ambiguity, asks for clarification, and generates safe PostgreSQL queries.

## Project Status

**Phase 1: PostgreSQL Connection & Schema Introspection** ✅ (Current)

## Architecture Overview

```
User Question
  ↓
Intent Extractor (Phase 2)
  ↓
Ambiguity Engine (Phase 3)
  ↓
 ┌───────────────┐
 │               │
CLEAR        AMBIGUOUS
 │               │
 ↓               ↓
Query Planner   Clarification (Phase 4)
 │               │
 ↓               ↓
SQL Generator ← Resolved Intent (Phase 5)
 ↓
SQL Validator (Phase 6)
 ↓
PostgreSQL Execution (Phase 7)
 ↓
Natural Language Response (Phase 8)
```

## Phase 1: Setup & Database Connection

### What Phase 1 Does

✓ Connects to PostgreSQL database  
✓ Introspects database schema automatically  
✓ Extracts tables, columns, data types  
✓ Identifies primary keys and foreign keys  
✓ Maps relationships between tables  
✓ Provides FastAPI endpoints for testing  

### Project Structure

```
text-to-sql/
│
├── app/
│   ├── main.py          # FastAPI application
│   ├── database.py      # PostgreSQL connection handling
│   └── schema.py        # Schema introspection
│
├── benchmark/
│   └── text_to_sql_benchmark_with_sql.xlsx  # 100 test questions
│
├── database/
│   └── text_to_sql_database.sql             # PostgreSQL schema + data
│
├── .env                 # Environment variables (create from .env.example)
├── .env.example         # Template for environment variables
├── requirements.txt     # Python dependencies
└── README.md           # This file
```

## Prerequisites

- Python 3.9+
- PostgreSQL 12+ installed and running
- pip for Python package management

## Installation & Setup

### Step 1: Install Python Dependencies

```bash
pip install -r requirements.txt
```

### Step 2: Set Up PostgreSQL Database

First, create the database:

```bash
psql -U postgres
CREATE DATABASE text_to_sql;
\q
```

Then load the schema and data:

```bash
psql -U postgres -d text_to_sql -f database/text_to_sql_database.sql
```

Verify the data was loaded:

```bash
psql -U postgres -d text_to_sql -c "SELECT COUNT(*) FROM customers;"
```

You should see 500 customers.

### Step 3: Configure Environment Variables

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` with your database credentials:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=text_to_sql
DB_USER=postgres
DB_PASSWORD=your_actual_password
```

**IMPORTANT:** Never commit `.env` to version control.

### Step 4: Start the Application

```bash
python -m uvicorn app.main:app --reload
```

Or directly:

```bash
python app/main.py
```

The API will start at: http://localhost:8000

## Testing Phase 1

### Test 1: Health Check

```bash
curl http://localhost:8000/health
```

Expected output:
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

### Test 2: List All Tables

```bash
curl http://localhost:8000/schema/tables
```

Expected output:
```json
{
  "tables": ["customers", "orders", "order_items", "products"],
  "count": 4
}
```

### Test 3: View Full Schema

```bash
curl http://localhost:8000/schema
```

This returns the complete schema with all tables, columns, types, and relationships.

### Test 4: View Specific Table Schema

```bash
curl http://localhost:8000/schema/tables/customers
```

Expected output shows customers table structure with:
- customer_id (primary key)
- first_name, last_name, email
- country, signup_date
- Data types and nullable flags

### Test 5: Verify Relationships

```bash
curl http://localhost:8000/schema/tables/orders
```

Should show foreign key:
- orders.customer_id → customers.customer_id

## Database Schema

The system introspects this schema automatically:

### Tables

**customers**
- customer_id (PK)
- first_name, last_name, email
- country
- signup_date

**products**
- product_id (PK)
- product_name
- category
- price

**orders**
- order_id (PK)
- customer_id (FK → customers)
- order_date
- status

**order_items**
- order_item_id (PK)
- order_id (FK → orders)
- product_id (FK → products)
- quantity
- unit_price

### Relationships

```
customers.customer_id → orders.customer_id
orders.order_id → order_items.order_id
products.product_id → order_items.product_id
```

## Key Design Decisions

### Why Schema Introspection?

The system reads the schema directly from PostgreSQL instead of hardcoding it. This means:

✓ Schema changes are detected automatically  
✓ The system adapts to different databases  
✓ No manual schema configuration needed  
✓ Relationships are discovered, not declared  

### Why Read-Only SQL?

Phase 1 includes a safety check in `database.py` that blocks non-SELECT queries:

```python
if not query_upper.startswith("SELECT"):
    raise ValueError("Only SELECT queries are allowed")
```

This prevents accidental or malicious:
- Data modification (UPDATE, DELETE)
- Schema changes (DROP, ALTER)
- Data insertion (INSERT)

### Why Connection Context Managers?

`database.py` uses context managers (`with` statements) to ensure:

✓ Connections are always closed  
✓ Transactions are committed on success  
✓ Transactions are rolled back on error  
✓ No connection leaks  

## What's Next

Phase 2 will add:
- Intent extraction from natural language questions
- OpenAI integration
- Structured intent representation
- Entity recognition (table/column names)

## Troubleshooting

### "Connection refused"

- Check PostgreSQL is running: `psql -U postgres -c "SELECT 1;"`
- Verify DB_HOST and DB_PORT in .env

### "Database does not exist"

```bash
createdb -U postgres text_to_sql
psql -U postgres -d text_to_sql -f database/text_to_sql_database.sql
```

### "Role does not exist"

Update DB_USER in .env to your actual PostgreSQL username.

### Import errors

```bash
pip install -r requirements.txt --upgrade
```

## License

Internal project.
