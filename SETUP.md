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
  },
  "writes_enabled": false
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
| `GEMINI_API_KEY`, `GROQ_API_KEY` | at least one | Each provider with a key joins the failover chain; one without a key is skipped silently. `GEMINI_API_KEY` enables all three Gemini entries. |
| `LLM_PROVIDER_ORDER` | no | Try order, default `gemini-lite,groq,gemini-lite-alt,gemini-flash` (`gemini` = all three Gemini entries). Unknown names are ignored. |
| `GEMINI_LITE_MODEL` | no | Default `gemini-3.5-flash-lite` (free tier: 500 requests/day, 15/minute). |
| `GEMINI_LITE_ALT_MODEL` | no | Default `gemini-3.1-flash-lite` (free tier: 500 requests/day, 15/minute; separate quota). |
| `GEMINI_FLASH_MODEL` | no | Default `gemini-3.8-flash` (free tier: 20 requests/day). |
| `GROQ_MODEL` | no | Default `qwen/qwen3.8-27b`. Older copies of `.env.example` suggested `llama-3.1-70b-versatile`; make sure a stale value is not set. |
| `LLM_TIMEOUT_SECONDS` | no | Per-request LLM timeout before failing over to the next entry. Default `12`. |
| `LOG_LEVEL` | no | Python log level for the app (default `INFO`). At `INFO` every request logs `LLM request served provider=... seconds=...`. |
| `BACKEND_CORS_ORIGINS` | no | Comma-separated; defaults include `http://localhost:5173` and the Vercel URL. |
| `BACKEND_CORS_ORIGIN_REGEX` | no | Origins matched by pattern as well. Default allows this project's Vercel deployment URLs (`https://query-mind-….vercel.app`) and `http://localhost:<port>` / `http://127.0.0.1:<port>`. Set to an empty string to disable. |
| `QUERYMIND_ENABLE_WRITES` | no | `true` allows confirmed natural-language INSERT/UPDATE. **Off by default** - leave it off on a public demo database. |
| `QUERYMIND_CONFIRM_SECRET` | with writes | Long random string; keeps confirmation tokens valid across restarts/instances. |

Frontend (Vercel project settings): `VITE_API_BASE_URL` = the backend URL.
The Vercel project's **Root Directory must be `frontend/`** so `frontend/vercel.json`
(the SPA rewrite for `/app`, `/architecture`, `/developers`) takes effect.

## LLM providers, failover and rate limits

All LLM calls go through `app/openai_client.py`. The chain has four entries:
Gemini 3.5 Flash-Lite, Groq, Gemini 3.1 Flash-Lite, then Gemini 3.8 Flash (the
Gemini ones via Google AI Studio,
`https://generativelanguage.googleapis.com/v1beta/openai/`, sharing
`GEMINI_API_KEY`; Gemini's free-tier quotas are per model). The order follows
what was measured on 2026-10-05: 3.5 Flash-Lite answered all 41 eval questions
correctly in ~1-3 s per call; Groq answered live requests in <1 s but has the
smallest daily budget (~140-150 questions); 3.1 Flash-Lite took ~4 s and often
returned 503 or hit the timeout; 3.8 Flash allows only 20 requests/day. Both
providers have free tiers that need no payment method (Mistral and Cerebras
were dropped because they require one). The Gemini model IDs were checked
against the API's model list on 2026-10-02; note `gemini-2.5-flash` is still
listed but returns 404 "no longer available to new users", and
`gemini-3.8-flash` intermittently returns 503 "high demand" (the chain fails
over). Each request uses the standard `tools` API (`tool_choice` is `auto` for
Gemini, the only value its compatibility layer documents, and `required` for
Groq) and `max_tokens=800` for every entry.

Failover policy per request (`_create_completion_with_retry` in `app/intent_extractor.py`):

| Provider response | What happens |
|---|---|
| 429 mentioning a daily quota (tokens/requests per day, TPD/RPD, `...PerDay...` quota IDs, "daily") | That entry is parked for the time it reports (Groq: "try again in 3m53s", Gemini: "retry in 10h5m39s"; default 15 min) and the next entry is tried immediately. No retry. Gemini's per-model quotas mean Flash-Lite running out does not park Flash. |
| 429 per-minute | One retry after `Retry-After` (or ~1 s); if `Retry-After` is over 8 s, no wait. Then the next provider. |
| 5xx, timeout (`LLM_TIMEOUT_SECONDS`, default 12 s), connection error | Next provider. |
| Other 4xx (bad key, unknown model, rejected request) or an unusable answer | Next provider, so one misconfigured provider cannot take `/query` down. |

`/query` returns 429 only when every configured provider is rate limited or
parked, 503 when they failed for a mix of reasons, 502 when none returned a
usable intent. The OpenAI SDK's own automatic retries are disabled
(`max_retries=0`) so they cannot stack under this policy. Each served request
logs `provider`, `model`, `prompt_tokens` and `completion_tokens`.

Measured on 2026-10-02: Groq's free tier for this project's key is 8,000
tokens/minute, 1,000 requests/day and 200,000 tokens/day; one extraction
request ("What were our top 10 products?", schema trimmed to 2 tables) used 1,028 prompt + 139 completion
tokens, so the daily token cap allows roughly 170 questions.

**Render:** after deploying, `GEMINI_API_KEY` must be set on the service. An
entry without a key is skipped silently, so without it the chain is Groq only.
If `LLM_PROVIDER_ORDER` or `GEMINI_MODEL` were set there from an earlier
version of these docs, remove them (`GEMINI_MODEL` is no longer read).

### Prompt size

Only the tables relevant to the question are sent: `EntityRecognizer` finds
the tables (or columns) the question names, metric words such as "revenue"
add the tables that hold quantity/price columns, and every table one foreign
key away is added. If nothing is recognised the full schema is sent. Request
validation still uses the full schema. To see the decision for every
question in `testing/test_questions.txt` without calling an API:

```bash
python -m testing.measure_prompt_tokens --dry-run
python -m testing.measure_prompt_tokens --provider gemini-lite   # real usage.prompt_tokens, spends quota
```

After switching provider, run the eval harness before trusting it:
`python -m testing.eval_harness --offline`.

## Running locally

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload          # backend on :8000
cd frontend && npm install && npm run dev   # frontend on :5173
```

## Tests

```bash
pip install pytest
pytest testing/                        # everything; no LLM tokens are spent
python -m testing.run_tests --live     # also the tests that call a real LLM provider
```

`testing/conftest.py` lets pytest run the older script-style suites too (they
can still be run directly, e.g. `python -m testing.test_phase4`). Tests that
need PostgreSQL are skipped when the database is unreachable.

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

A caller can also opt out per request with `"allow_writes": false` (the app's
Settings page sends this; it defaults to `true` for API callers). A write needs
**both** the server switch and the caller's opt-in. `GET /health` reports the
server switch as `"writes_enabled"`.

## Request options for `POST /query`

| Field | Default | Meaning |
|---|---|---|
| `question` | required | The natural-language question. |
| `clarification_context` | `null` | The user's answer to a clarification question. |
| `strict` | `true` | `false` answers ambiguous questions with the model's best guess and reports the ambiguity in `warnings` instead of asking. Critical ambiguities (e.g. an UPDATE with no WHERE) still block. Settings toggle: *Ask for clarification*. |
| `allow_writes` | `true` | `false` blocks INSERT/UPDATE for this request (preview only). Settings toggle: *Allow write queries*. |
| `allow_full_table_write` | `false` | Low-level escape hatch in the generator; a WHERE-less UPDATE is still blocked as a critical ambiguity. |
