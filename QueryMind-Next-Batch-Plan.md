# QueryMind: next batch (tracks A–F)

> **Status: saved for later on 2026-10-06, not started.** The owner approved the scope (all of A–F). To resume, say "start the saved QueryMind plan" and the work begins at F1. The separate database move (Render → Neon) is still due **before 2026-10-23**.
>
> **Update 2026-10-07: done as part of the frontend redesign.**
> - From Track A:
>   - Developers page documents the real API;
>   - trust/safety copy rewritten to verifiable facts;
>   - Schema tab reads `GET /schema`, which now returns `database`;
>   - the app chrome shows the real database and status (via `/schema`, not `/health`);
>   - the README's false lines are fixed.
> - From F2: route-level lazy loading (main bundle 750 KB → 308 KB).
>
> **Still open:** B, C, D, E, F1, the CI workflows in F2, and the full README rewrite.

## Context

Phases 0–2 of the build plan are done and verified live: the eval passes 41/41, the 4-entry AI chain is in place, and Settings toggles, history Reopen/Re-run and Saved queries all work. A read-only review on 2026-10-06 found the Phase 3 gaps below.

All six tracks are in this batch. The **database move stays out**: it has to happen before 2026-10-23.

Build-plan rules apply throughout:
- strict honesty, with measured numbers only;
- SQL is generated, never free-written;
- verify fixes live;
- a conventional commit and a CHANGELOG entry per change;
- no pipeline redesign.

**Delivery:** one local commit per track (not pushed). The owner pushes when ready, then the live site is verified.

## Implementation order

The order follows the dependencies: F1 → B → C → D → E → A → F2. A comes late because its honest page copy describes what B–E actually ship.

### F1. Groundwork (`chore:`)
- **`app/main.py`:** replace `@app.on_event("startup")` with a `lifespan` context manager. This removes the 2 pytest deprecation warnings and gives D a place to create its table.
- **`requirements.txt`:** re-encode from UTF-16 to UTF-8, with identical pins. GitHub currently shows it as binary.
- **New `requirements-dev.txt`:** `-r requirements.txt` + `pytest==9.1.1`.

### B. Safe, concurrent query execution (`feat:`/`fix:`)
- **Endpoints:** change all of them in `app/main.py` from `async def` to `def`. Today the blocking AI calls (up to 12 s) and DB calls run on the event loop, so one slow request blocks every other visitor. As plain `def`, FastAPI runs them in its threadpool. The token store is already safe: `app/writes.py` `_lock`.
  - Update `_call()` in `testing/test_writes.py` to accept plain return values as well as coroutines.
- **`Database.execute_query(query, params, max_rows=None)`** in `app/database.py`:
  - `conn.read_only = True`;
  - timeout via `SELECT set_config('statement_timeout', %s, true)`. Bound parameters fail with `SET ... = %s` under psycopg 3;
  - `fetchmany(max_rows + 1)`.

  Env: `QUERY_TIMEOUT_SECONDS` (8), `MAX_RESULT_ROWS` (1000).
- **`/query`:** cut the rows at the cap. Set `result.truncated: true` and add a warning; `ResultsView.jsx` shows "Showing the first 1,000 rows". A timeout returns an honest error ("took longer than 8 s").
- **Schema cache:** a TTL cache (`SCHEMA_CACHE_SECONDS`, 60) around `SchemaIntrospector(db).introspect()` for `/query` and `/schema*`, with a reset hook for tests.
- **Optional `DB_SSLMODE`:** add it and quote values in `DatabaseConfig.connection_string`. This is prep for the Neon move.

### C. Protect the AI quota (`feat:`)
- **New `app/rate_limit.py`:** an in-memory sliding window per key, lock-protected, with an injectable clock for tests. Env:
  - `RATE_LIMIT_PER_MINUTE` (10)
  - `RATE_LIMIT_PER_DAY` (200)
  - `TRUSTED_PROXY_HOPS` (1)
- **Client IP:** the `X-Forwarded-For` entry `TRUSTED_PROXY_HOPS` from the right (Render's proxy appends the real IP), falling back to `request.client.host`. After deploy, confirm the hop count once from a log line that records only the header's entry count, never IPs.
- **Optional API keys:** `X-API-Key` matched with `hmac.compare_digest` against `QUERYMIND_API_KEYS` (comma-separated). Keys get their own, higher limits: `API_KEY_RATE_LIMIT_PER_MINUTE` (60) and `API_KEY_RATE_LIMIT_PER_DAY` (2000).
- **Middleware:** applies to `POST /query` only (the endpoint that spends AI tokens). Preflights are not counted.
  - Over the limit returns 429 `{error, retry_after}`.
  - The middleware is added **before** CORS, so CORS stays outermost and the browser can read the 429 message.

### D. Usage analytics + audit log (`feat:`)
- **New `app/query_log.py`.** At startup (lifespan) it creates `querymind_meta.query_log`. The schema reader only reads `public` (`app/schema.py`), so the AI never sees this table.
  - **Columns:** `created_at`, question (≤500 chars), clarified, status, error_kind, sql, params jsonb, provider, model, prompt/completion tokens, llm_seconds, total_ms, row_count, truncated. No IPs.
  - **Retention:** `QUERY_LOG_RETENTION_DAYS` (30), pruned at startup.
  - **Failure handling:** if the DDL or an insert fails, logging switches itself off with a warning. `/query` never fails because of it.
- **Model and token info:** `app/intent_extractor.py` `_log_usage` also stores `{provider, model, tokens, seconds}` in a thread-local, read through `consume_last_usage()`. No signature change: the tests monkeypatch `extract_intent(q, c)`.
- **Recording:** `/query` records each request through a single-worker `ThreadPoolExecutor`, so the insert stays off the response path.
- **`GET /stats?days=7`:** aggregates only, no question texts.
  - totals by status;
  - success and clarification rates;
  - p50/p90 `total_ms`;
  - model share;
  - average tokens;
  - top error kinds.
- **Frontend:** new `pages/UsagePage.jsx` plus a sidebar "Usage" item (`Sidebar.jsx` `items`), with stat tiles and a model-share bar. Consult the **dataviz** skill before building the tiles.

### E. Features (`feat:`)
- **Explain (no AI tokens).** New `app/explain.py` `explain_intent(intent)` builds plain English from `StructuredIntent`: tables, columns, conditions, aggregations, group_by, order_by/limit, HAVING, comparison, top-N per group, date bucketing.
  - `SQLGenerator.generate` exposes the final `working_intent` on `SQLGenerationResult`. That is the intent the SQL came from, after auto-resolution.
  - `/query` adds `explanation` on success.
  - `Dashboard.jsx` passes `onExplain` to the existing `SqlPanel` Explain button, which toggles the text. History and saved snapshots store it too (`services/storedQueries.js` `makeSnapshot`).
- **CSV export.** New pure `frontend/src/lib/csv.js`:
  - RFC 4180 quoting;
  - null → empty;
  - cells starting with `= + - @` prefixed with `'` (spreadsheet formula injection).

  A "Download CSV" button in `ResultsView.jsx`, with a note when rows are truncated or come from a snapshot.
- **Show what was assumed.** In `SQLGenerator`'s non-strict branch (`app/sql_generator.py`, "proceeding anyway" warnings), append the final conditions/order actually used, via `explain.py` helpers, e.g. "…; used: price > 100". (Vague-term ambiguities only carry `{"term","kind"}`, so the warning describes the final conditions rather than matching a column.)

### A. Make every claim true (`fix:`/`docs:`)
- **Backend:** `GET /schema` adds `"database": db.config.database`.
- **New pure `frontend/src/services/schemaShape.js`:** converts the `/schema` response into the shapes `SchemaTableCard`/`SchemaRelationships` already render (`relationships: {from,to,label}` from `foreign_keys`). It drops the fake `rowCount`s; the card shows a count only when present.
- **`services/schemaApi.js`:** call `GET /schema` through the existing `request()` helper, exported from `queryApi.js`. The mock data import goes.
- **New `hooks/useBackendInfo.js`:** fetches `/schema` once (`/health` is avoided because Brave Shields blocks it). It feeds:
  - `AppLayout.jsx`: "Workspace: <real db>" and "Connected"/"Unreachable" instead of a fixed "Operational";
  - `Sidebar.jsx`: the footer;
  - `SchemaPage.jsx`: the header.
- **`pages/Developers.jsx`:** document the real API.
  - Real `curl`/`fetch` for `POST /query`, with the fields in `SETUP.md`, plus `explanation` and `truncated`.
  - `/query/confirm`, `/schema`, `/stats`, `/health`, and the `X-API-Key` limits from C.
  - Webhooks and SDK either marked "Planned" or removed.
- **Trust points (`data/mockData.js`):** only verifiable facts:
  - read-only transactions + 8 s timeout (B);
  - parameterized SQL with identifiers checked against the live schema;
  - writes off by default, previewed, single-use confirmation tokens;
  - DELETE refused;
  - query audit log (D);
  - credentials stay server-side.

  Drop "per-workspace permissions" and "encrypted at rest".
- **`Product.jsx`:** "explainable" stays (E makes it true).
- **`README.md`:** current status, live URLs, the AI chain, PostgreSQL (not MySQL), the new features, a pointer to `SETUP.md`, the date. **`SETUP.md`:** every new env var and response field.

### F2. CI + bundle (`ci:`/`perf:`)
- **`.github/workflows/ci.yml`** (push/PR):
  - **Backend:** Python 3.10 with a `postgres:16` service seeded via `psql -f database/text_to_sql_database.sql`, so the DB tests actually run. Then `pip install -r requirements-dev.txt` and `pytest testing -q`.
  - **Frontend:** Node 24, `npm ci && npm test && npm run build`.
- **`.github/workflows/nightly-eval.yml`:**
  - runs on a cron schedule and manually (`workflow_dispatch`);
  - runs `python -m testing.eval_harness --json eval.json` against live (about 41 AI requests a day) and uploads the JSON.
  - **Eval exit codes** (`testing/eval_harness.py` `summarize`/`main`): `core_failed` currently counts outages, so a Gemini 503 would fail the nightly run. The tool will exit 1 for real failures and 2 for outage-only runs; the workflow turns 2 into a warning.
  - **Caveat:** GitHub pauses scheduled workflows after 60 days with no repo activity.
- **`frontend/src/App.jsx`:** `React.lazy` + `Suspense` for the routes. Report the measured bundle sizes before and after (main chunk today: 750 KB).

## Verification
- **Per track:** `pytest testing -q` (293 passing today, plus the new tests) and `cd frontend && npm test && npm run build && npm run lint`.
- **New backend tests:**
  - a write inside `execute_query` is rejected (read-only);
  - `pg_sleep(10)` is cancelled by the timeout;
  - the row cap sets `truncated`;
  - the schema cache serves within its TTL;
  - rate limiter: window math, day cap, `X-Forwarded-For` hops, API-key limits, 429 body visible with CORS headers;
  - query log records/prunes and disables itself on DB errors;
  - `/stats` aggregates;
  - `explain_intent` for every intent type (filters, HAVING, comparison, top-N, nested, bucketing);
  - the assumed-value warning text;
  - `/schema` includes `database`;
  - two concurrent `/query` calls overlap. With fake AI calls sleeping 1 s each, the total is about 1 s, not 2 s.
- **New frontend tests (node --test):** `csv.js` (quoting, injection guard), `schemaShape.js`.
- **Local end-to-end:**
  - backend + Vite dev server driven with headless Chrome (temp `playwright-core`);
  - Schema tab shows the 4 real tables, no fake counts; top bar shows the real DB name;
  - Explain toggles text; CSV downloads;
  - Usage page shows tiles after a few questions;
  - with `RATE_LIMIT_PER_MINUTE=2`, the 3rd question shows the 429 message;
  - Developers page has no SDK claim.
- **Measurements to report (no estimates):** wall time for two concurrent `/query` requests before vs after B; bundle sizes before vs after F2.
- **After pushing** (Render + Vercel deploy):
  - live eval 41/41;
  - `/schema` has `database`; `/stats` responds;
  - Render log line confirms the `X-Forwarded-For` hop count;
  - the CI workflow is green on GitHub.
