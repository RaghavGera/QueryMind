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
python testing/test_phase1.py
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
└── testing/
    └── test_phase1.py   # Test script
```

## Ready for Phase 2?

Once all tests pass and the API is working, you're ready for Phase 2: Intent Extraction.

Phase 2 will add:

- Natural language question parsing
- Intent extraction using OpenAI
- Entity recognition (table/column identification)
- Structured intent representation

---

# Current setup (backend, frontend, deployment, tests)

The sections above are the original Phase 1 database walkthrough. This section
is the up-to-date reference.

## Environment variables

Backend (`.env` locally; the service's Environment screen on Render):

| Variable | Required | Notes |
|---|---|---|
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | yes | Set **all five**. Setting only `DATABASE_URL` is ignored and silently falls back to `localhost:5432` (this caused an outage once). |
| `GROQ_API_KEY` / `MISTRAL_API_KEY` / `GEMINI_API_KEY` / `OPENAI_API_KEY` | one of them | The provider is inferred from whichever key is set. |
| `LLM_PROVIDER` | no | `groq` (default if only `GROQ_API_KEY` is set), `mistral`, `gemini` or `openai`. |
| `QUERYMIND_LLM_MODEL` | no (required for `gemini`) | Overrides the provider's default model. |
| `BACKEND_CORS_ORIGINS` | no | Comma-separated; defaults include `http://localhost:5173` and the Vercel URL. |
| `QUERYMIND_ENABLE_WRITES` | no | `true` allows confirmed natural-language INSERT/UPDATE. **Off by default** - leave it off on a public demo database. |
| `QUERYMIND_CONFIRM_SECRET` | with writes | Long random string; keeps confirmation tokens valid across restarts/instances. |

Frontend (Vercel project settings): `VITE_API_BASE_URL` = the backend URL.
The Vercel project's **Root Directory must be `frontend/`** so `frontend/vercel.json`
(the SPA rewrite for `/app`, `/architecture`, `/developers`) takes effect.

## LLM provider and rate limits

All LLM calls go through `app/openai_client.py` (OpenAI-compatible protocol, using
the standard `tools` / `tool_choice` API). `max_tokens` is pinned at 800.
Groq's free tier for the current key is 8,000 tokens/minute and 1,000
requests/day, so the extractor keeps its prompt small (about 830 tokens for a typical
question) and retries 429/5xx with backoff. After switching provider, run the
eval harness (below) before trusting it: `python -m testing.eval_harness --offline`.

## Running locally

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload          # backend on :8000
cd frontend && npm install && npm run dev   # frontend on :5173
```

## Tests

```bash
pip install pytest
python -m testing.run_tests            # every offline suite (no DB, no network)
python -m testing.run_tests --live     # also test_phase1/2 (need a DB / API key)
```

The files in `testing/` mix pytest files and standalone scripts, so use the
runner rather than `pytest testing/`.

## Eval harness

```bash
python -m testing.eval_harness                           # live Render backend
python -m testing.eval_harness --base-url http://localhost:8000
python -m testing.eval_harness --offline                 # real LLM, in-memory schema, no DB
python -m testing.eval_harness --only q2-top-10-products --runs 5   # measure variance
```

Questions and expectations live in `testing/eval_questions.json`. Exit code is
non-zero if any `core` question fails; `known_gap` questions are reported only.
Throttling/outages are reported as INFRA, not as pipeline failures.

## Natural-language writes (INSERT / UPDATE)

`POST /query` never writes. For a write it returns `status: "needs_confirmation"`,
a `preview` (with the affected-row count for UPDATEs) and a `confirmation_token`
(signed, single-use, 5 minutes). `POST /query/confirm {"confirmation_token": "..."}`
then executes exactly that statement and rolls back if the affected row count
changed. With `QUERYMIND_ENABLE_WRITES` unset the preview is returned with
`status: "blocked"` and nothing can be confirmed. Natural-language DELETE is refused.
