# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Workspaces (Phase 4).** A question runs against a workspace: the shared, read-only demo, or a
  signed-in user's own (one per user; a new one replaces it; uploads expire after 7 days,
  connections after 24 hours, removed at startup and on lookup). `GET /workspaces`,
  `DELETE /workspaces/{id}`, `workspace_id` on `POST /query` and `GET /schema`. Every answer query
  runs as a per-workspace `NOLOGIN` role (`SET LOCAL ROLE`) that can read only its own schema;
  the demo's role can't read the account tables. The schema reader takes a schema name and is
  cached per workspace for 5 minutes (it was 13 queries, 1.2 s locally, per question). History
  and saved entries record `workspaceId`. Uploads and connections arrive in Phases 5 and 6.
- **Query safety (Phase 3).** Every read runs in a `READ ONLY` transaction, so Postgres refuses a
  write whatever the SQL says (tested with `SELECT ... INTO`, which passes the SELECT-only check).
  Every query and confirmed write has a statement timeout (`QUERY_TIMEOUT_SECONDS`, default 8); a
  timeout returns 504 with the SQL and gives the question back. Answers return at most
  `MAX_RESULT_ROWS` (default 1,000) rows: `result.truncated` plus a warning, and the results
  header reads "first 1,000 rows (capped)".
- Endpoints are plain functions, so FastAPI runs them in its thread pool: one slow model or
  database call no longer blocks other visitors. Two simultaneous 1-second questions: 2.08 s
  before, 1.06 s after.
- **History and saved queries in the account.** Signed in, they're stored in Neon
  (`querymind_meta.query_history`, `saved_queries`) and follow you to every device; signed out
  they stay in the browser. On sign-in the browser's entries are moved into the account
  (`POST /me/import`, skipping ones it already has) and cleared locally; a failed import is
  retried next time. Endpoints `GET/POST/DELETE /me/history`, `GET/PUT/DELETE /me/saved`:
  newest 50 history entries kept, up to 100 saved queries, re-saving a question replaces it,
  entries checked (question required, at most 200 rows) and bodies over 8 MB refused. Reopen,
  Re-run and the Save toggle work as before. The Privacy page says what is stored.
- **Accounts: Sign in with Google.** `POST /auth/google` takes a Google access token (checked
  with Google: issued to this app's client id, same account, verified email) or an ID token
  (signature against Google's keys, audience, issuer, expiry, `email_verified`) and returns a
  7-day session token; `GET /auth/me`, `POST /auth/logout` (revokes the session row), `GET /auth/usage`.
  Users, sessions and daily counts live in a new `querymind_meta` schema that the AI never sees.
  New dependencies: PyJWT, cryptography. New env vars: `GOOGLE_CLIENT_ID`, `SESSION_SECRET`.
- **Daily question limits.** `POST /query` and `/query/confirm` count against 20 questions per
  user per UTC day (`DAILY_QUESTION_LIMIT`) and 3 for signed-out visitors
  (`ANON_DAILY_QUESTION_LIMIT`, keyed by a hashed IP, never the raw IP). The count is atomic, is
  refunded on server errors, and is reported in `X-Usage-*` headers; over the limit returns 429.
  `/query/confirm` needs sign-in. `QUERYMIND_SERVICE_KEY` (header `X-Service-Key`) skips the
  limits; the eval harness sends it and stops with a hint on 401/429 without it.
- **A question and its clarification count once.** A counted question that needs clarifying
  returns a single-use `clarification_ticket` (15 minutes, tied to the caller, stored hashed);
  the answer sent with `X-Clarification-Ticket` is free, even after the last free question.
  Free answers get no new ticket, so tickets can't be chained.
- Frontend: `/signin` page with a "Continue with Google" button in the site's style (Google's
  token popup), an account menu with today's count and sign-out, and a `/privacy` page.
  Signed-out visitors can use `/app` and the landing console with "N free questions left
  today", then get a sign-in prompt; the app's top bar and the navbar show "Sign in".
- `CLIENT_IP_HEADER`: the visitor's IP for the free-question count comes from a header the proxy
  sets itself (`True-Client-IP` on Render). Fixes signed-out visitors sharing one counter: behind
  Render the rightmost `X-Forwarded-For` entry is a Render-internal address, not the visitor.
- `frontend/vercel.json`: Content-Security-Policy (scripts only from this site and Google's
  sign-in), `Referrer-Policy`, `X-Content-Type-Options`, `Permissions-Policy`.
- `scripts/migrate_db.py`: copy the database to another PostgreSQL server (check / copy / verify).
  The copy runs in one transaction, refuses to overwrite a non-empty target, and `verify` compares
  per-table row counts and a revenue checksum. Credentials come from a git-ignored `.env.migrate`
  and reach `pg_dump`/`psql` only through libpq environment variables.
- `DB_SSLMODE` (optional), needed for hosted Postgres such as Neon.
- **Frontend redesign: "Neural Observatory".** The landing page is one continuous, scroll-driven
  camera flight: a WebGL universe (custom star shader, nebula, the demo schema as a constellation,
  a query beam, warp streaks) behind 9 pinned, scroll-scrubbed scenes that follow the real
  pipeline with real wording, SQL and numbers (the generator's actual SQL for "Which region
  generated the most revenue?"; revenue by country from the demo database; the detector's actual
  clarification question). Lenis smooth scrolling (new dependency, MIT) on the public pages only,
  decoding headlines, magnetic CTAs, a chapter rail, film grain/scanlines/vignette, and a
  full-screen warp transition into the app. Product page: a pinned horizontal feature reel.
  How it works: a scroll-linked light beam through the 10 stages. Developers: a terminal that
  types a real `curl` call and streams the real JSON response, plus the real endpoints/options.
- App restyle to match (HUD panels, command-line input, amber clarification/confirmation panels,
  big count-up card for single-number answers, staggered table rows, gradient charts, page headers).
- `GET /schema` also returns `database`; the app's top bar, sidebar and Schema tab use it.
- Route-level code splitting: main bundle 750 KB -> 308 KB; three.js (827 KB) loads only on the
  landing page; Lenis only on the public pages.
- Frontend unit tests for the motion math, text decode, typing/highlight slicing, JSON
  highlighting and the schema adapter (`npm test`).
- **Saved queries.** Results have a Save / Saved toggle; the Saved Queries tab lists them with
  Reopen, Re-run and Remove. Stored in the browser (`localStorage`), like history.
- **Query history Reopen and Re-run.** History entries now keep a snapshot of the result (SQL,
  parameters, warnings and up to 200 rows). *Reopen* shows it without calling the backend, with a
  "stored result, not re-run" banner and a Run again button. *Re-run* (formerly Duplicate) puts
  the question in the Ask box without submitting it. Entries without a snapshot (writes, entries
  from older builds) cannot be reopened. When browser storage is full the oldest snapshots are
  dropped first. Frontend storage tests: `npm test` (Node's built-in runner, no new dependencies).
- **Settings toggles now work.** *Ask for clarification* is saved in the browser and sent as
  `strict` (off: ambiguous questions are answered with the model's guess plus a warning;
  critical ambiguities still block). *Allow write queries* is sent as the new `allow_writes`
  request field; a write needs both it and `QUERYMIND_ENABLE_WRITES`, and the toggle is greyed
  out when the server has writes disabled. *Require a WHERE clause* is shown as always on,
  which is what the backend enforces. The connection card shows live `/health` data.
- `GET /health` reports `writes_enabled`.
- `frontend/vercel.json` SPA rewrite so hard-refreshing `/app`, `/architecture` and
  `/developers` no longer 404s on Vercel.
- **Eval harness** (`python -m testing.eval_harness`): runs `testing/eval_questions.json`
  through `POST /query` against any base URL (or `--offline` with the real LLM and no
  database), checks HTTP status, response status, SQL shape, row counts and cells, repeats
  runs to expose model variance, and exits non-zero on any core failure. Questions tagged
  `known_gap` are reported but do not fail the run.
- `pytest testing/` runs every suite, including the older script-style ones
  (`testing/conftest.py`); `python -m testing.run_tests --live` adds the token-spending tests.
- HAVING support: conditions on aggregates ("more than 5 orders") become `HAVING` clauses.
- Anti-joins: "customers who never ordered" renders `LEFT JOIN ... IS NULL`.
- **Natural-language INSERT/UPDATE** with a mandatory confirmation step. `/query` never
  writes; it returns `status: "needs_confirmation"`, a preview (with the affected-row count
  for UPDATEs) and a signed, single-use, 5-minute token. `POST /query/confirm` executes
  exactly that statement and rolls back if the affected row count changed. Writes are
  disabled unless `QUERYMIND_ENABLE_WRITES=true` (see SETUP.md); `QUERYMIND_CONFIRM_SECRET`
  keeps tokens valid across restarts. NL `DELETE` is refused.
- **Period-over-period comparison** ("customers whose spending increased this quarter"):
  current vs previous month/quarter/year via two aggregated subqueries on a FULL OUTER JOIN
  (an entity with no activity in one period counts as 0). Period bounds come from today's date,
  not the LLM; an in-progress period is flagged in `warnings`.
- **Top-N per group** (`ROW_NUMBER() OVER (PARTITION BY ...)`), **nested aggregates**
  ("average order value" = AVG of per-order SUM) and **date bucketing** (`DATE_TRUNC`,
  allow-listed units, schema-validated column).
- Frontend: confirmation panel for writes (preview, Confirm/Cancel), backend `warnings` /
  assumptions shown to the user, `blocked` responses without questions shown as messages.
- **LLM provider failover chain**: Gemini 3.1 Flash-Lite, then Gemini 3.8 Flash (Google AI Studio,
  one `GEMINI_API_KEY`, per-model quotas), then Groq, tried in `LLM_PROVIDER_ORDER` (default
  `gemini-lite,gemini-flash,groq`; `gemini` = both Gemini entries); entries without a key are
  skipped. Both providers are free without a payment method (Mistral and Cerebras were dropped
  because they require one).
  A daily-quota 429 parks the provider and fails over immediately; a per-minute 429 gets one short
  retry; 5xx/timeouts/other 4xx fail over. `/query` returns 429 only when every provider is rate
  limited. Model overrides `GEMINI_LITE_MODEL` (default `gemini-3.1-flash-lite`),
  `GEMINI_FLASH_MODEL` (default `gemini-3.8-flash`), `GROQ_MODEL`.
  Each served request logs provider, model, `prompt_tokens` and `completion_tokens`.
- **Per-question schema trimming**: only the tables `EntityRecognizer` finds, plus metric tables and
  foreign-key neighbours, are sent to the LLM; full schema when nothing is recognised. Validation
  still uses the full schema. `python -m testing.measure_prompt_tokens` measures the effect.
- Extraction uses the standard `tools` API (Gemini's OpenAI-compatible layer does not document the
  legacy `functions` parameter).
- Required-column check for INSERT: missing NOT NULL values become clarification questions.
- `docs/KNOWN_ISSUES.md`: observed behaviour per question, owner actions, open gaps.

### Changed
- **Sales count completed orders only.** Revenue, sales, spending and "units sold" questions over
  order line items now add `orders.status = 'Completed'` (pending and cancelled orders are not
  sales), unless the question names a status itself. Every affected answer carries the warning
  "Sales count completed orders only; pending and cancelled orders are excluded." Landing page,
  README and Developers examples recaptured: India's revenue is 706,939 (734,561 with all statuses).
- Aggregation result columns have readable names: `sum_quantity_x_unit_price` instead of
  `sum_order_items_quantity_order_items_unit_price`; duplicates get a numeric suffix.
- **LLM chain is now `gemini-lite,groq,gemini-lite-alt,gemini-flash`.** `gemini-lite` defaults to
  `gemini-3.5-flash-lite` (41/41 offline eval, ~1-3 s per call on 2026-10-05); the previous
  `gemini-3.1-flash-lite` moves to the new `gemini-lite-alt` entry (`GEMINI_LITE_ALT_MODEL`),
  keeping its separate 500/day quota. Groq moves to second place: Render logs showed it
  answering in <1 s while 3.1 Flash-Lite returned 503s or timed out. `gemini` in
  `LLM_PROVIDER_ORDER` now expands to all three Gemini entries.
- LLM calls retry 429/5xx/connection errors with exponential backoff (honouring
  `Retry-After`); failures map to honest HTTP statuses (429 / 503 / 502) with a structured
  body instead of a traceback. `max_tokens` stays pinned at 800.
- `/query` never returns a traceback: any unexpected error is a structured 500.
- Extractor prompt is pinned in a module constant with two few-shot examples; guidance and
  function-schema slots for writes, comparisons, per-group ranking, nested aggregates, time
  grouping and HAVING are added only for questions that need them, and the schema listing is
  compact. Measured with schema trimming on: 1,028 prompt + 139 completion tokens for "What were
  our top 10 products?". Groq's free tier for this key is 8,000 tokens/minute and 200,000 tokens/day.
- Text comparisons (`=`, `!=`, `IN`, `LIKE`) on text columns are case-insensitive.
- `execute_query` debug-file write on every request replaced by `logging`.

### Removed
- OpenAI as an LLM provider: `OPENAI_API_KEY` (previously a fallback when no Groq key was set) is
  no longer read. The supported providers are Gemini and Groq.

### Fixed
- **Live outage after the workspaces deploy (2026-10-19): every answer failed** with "permission
  denied to set role querymind_demo". On PostgreSQL 16+ a non-superuser that creates a role (Neon's
  owner) gets only ADMIN on it, which counts as membership but doesn't allow `SET ROLE`; the setup
  checked membership and skipped the grant, and never tried the switch, so the fail-safe didn't
  trigger. The setup now grants the role to itself when `SET` isn't allowed and proves the switch
  works (in a rolled-back savepoint) before using the roles. Reproduced locally with a CREATEROLE
  login role standing in for Neon's owner; that is now a regression test.
- **"Which ... the most" answers one thing again.** "Which region generated the most revenue?"
  started returning all 5 countries sorted (the model dropped `LIMIT 1`; seen locally and live on
  2026-10-19, eval 40/41). The converter now sets `LIMIT 1` itself for a "which/what <singular>
  ... most/highest/least/fewest" question that is ordered and has no limit, and says so in the
  warnings. Plural subjects ("Which customers have placed the most orders?"), explicit numbers and
  each/per/every/all are left alone. Eval back to 41/41; the region question passed 5/5 runs.
- **Deleting no longer loops.** "Delete all customers" asked "Are you sure you want to delete ALL
  rows?" again after every "yes", although deletes are refused anyway. Delete requests are now
  refused at once ("Deleting data through natural language is not supported."), before the
  ambiguity check.
- **Readable charts.** Date axes read "Jun 2025" (or "2025", "3 Jun 2025") instead of raw
  timestamps like `2025-06-01T00:00:00+05:30`, taken from the date as written so no viewer's
  timezone shifts it; the y-axis uses compact numbers ("280K") and is no longer clipped; long
  series skip labels instead of overlapping; tooltips show the full value ("264,713").
- **New logo, "Q-beam":** a Q whose tail is a glowing query beam, on a nebula tile. Used for the
  favicon (replacing Vite's default), the navbar, sidebar, footer, sign-in card and loading screen;
  `apple-touch-icon.png` and a 512 px `logo-512.png` added.
- The SQL panel showed `%s` placeholders and hid the values (e.g. the dates "last month" resolved
  to). It now shows the bound values inline and copies runnable SQL; the server still sends them as
  parameters. Long first lines no longer squeeze the line-number column.
- A total over zero rows (SQL `NULL`) rendered as an empty card. It now says no rows matched and
  lists the filter values. `NULL` table cells show as a dash; column headings are humanized.
- The database connection string was built by string formatting, so a password containing a space
  or quote broke the connection. It is now built with psycopg's `make_conninfo`, which quotes every
  value.
- The Ask flow made you watch scripted progress: three "stages" ticked every 480 ms before the
  request resolved, and another 2.4 s of stages played *after* the answer arrived. Results now
  appear as soon as the backend answers (measured locally: 13 ms after the response), and the
  progress display is an honest beam with a real elapsed timer.
- Public pages claimed things that do not exist: a JavaScript SDK, scoped API keys, webhooks, a
  "full API reference", query auditing, per-workspace permissions, encrypted-at-rest credentials,
  "plain-language summaries" and "read-only by default". All removed or reworded to what the
  backend actually enforces.
- The Schema tab showed mock data with invented row counts (4,820 customers; the demo database has
  500); it now reads the live schema. "sample_ecommerce_db" and a permanently green "Operational"
  status were hard-coded in the app chrome; both now come from the backend.
- framer-motion handed scroll-linked opacity to a native ViewTimeline whose progress for pinned
  (sticky) sections differs from the configured offsets (an element meant to be fully visible sat
  at 25% opacity); pinned scenes now drive animations from a plain motion value.
- Query history Reopen and Duplicate only navigated to an empty Ask page.
- Query history showed five fake demo entries (and saved them into the browser's storage once a
  real query ran). The demo data is removed and those entries are filtered out of stored history.
- "Run again" after a clarified question asked the clarification again; it now resends the answer.
- Results said "Executed in ms" (the backend sends no timing); they now show the measured
  request time ("answered in 3.2 s"). Also "1 rows" -> "1 row".
- History and saved ids were `Date.now()` only, so two entries created in the same millisecond
  shared an id and deleting one deleted both.
- `index.html` did not link the existing `favicon.svg`, so browsers requested a missing
  `/favicon.ico` (404 in the console).
- CORS only allowed `https://query-mind-tawny.vercel.app`, so the app opened from any other
  Vercel deployment URL (or a dev server on `127.0.0.1`) was refused (`400 Disallowed CORS
  origin`), which browsers report as a network failure. These origins are now allowed by
  pattern (`BACKEND_CORS_ORIGIN_REGEX`), and the error message names the backend and the page
  origin. (A Settings page stuck on "Unreachable" in Brave was a different cause: Brave
  Shields' tracker blocking stops the cross-site `GET /health` call.)
- Offline eval (`--offline`) failed every UPDATE-preview question: its fake database returned
  no rows for the affected-row count. It now reports one matching row.
- SETUP.md documented `measure_prompt_tokens --provider gemini`, which is not an entry name
  and exits with an error; it now says `--provider gemini-lite`.
- Eval check for "Show customers from India." failed a correct answer that filtered on
  `country = 'India'` without selecting the column. A `first_row` expectation now also passes
  when the SQL's WHERE clause filters that column on the expected value.
- Slow requests (35-40 s) when gemini-lite hung: the LLM timeout was 30 s before failing over.
  It is now 12 s by default and configurable with `LLM_TIMEOUT_SECONDS`; the usage log line
  and the failover warning now include how long the call took (`seconds=`).
- App logs were silently dropped in production: nothing configured logging, so under uvicorn
  only WARNING+ lines from `app.*` were printed and the per-request
  `LLM request served provider=... prompt_tokens=...` line never reached the Render logs.
  `app/main.py` now configures logging from `LOG_LEVEL` (default `INFO`).
- Hidden retry stacking: the OpenAI SDK retried 429/5xx twice on its own (honouring Retry-After)
  underneath the app's retries, and waited up to 10 minutes per request. SDK retries are now off
  and requests time out after 30 s.
- **Silent wrong answers from case-sensitive filters**: "Show cancelled orders" returned 0
  rows because values are stored as `Cancelled`.
- **Guessed answers to vague questions**: "expensive products", "recent orders",
  "top customers" used to run with an invented threshold/window/metric. They now ask
  (`app/vague_terms.py`, applied independent of what the LLM guessed). A user's clarification
  is never re-asked.
- "How many ...?" answered with a row listing now becomes a `COUNT`.
- "top N products" with no metric no longer bounces back with "What aggregation do you
  want?"; it ranks by units sold and says so in `warnings`.
- Qualified condition columns (`customers.signup_date`) no longer trigger a false
  "which date column?" clarification for "last month".
- Pydantic validation failures in the converter are 422s, not crashes.

## [0.4.0] - 2026-09-20

### Added - Phase 4: SQL Generation ✅

#### Core Features

- **SQLGenerator** class: converts a `StructuredIntent` into parameterized SQL
- Runs the Phase 3 `AmbiguityDetector` as a gatekeeper before every generation:
  - Auto-resolves ambiguities the detector has a `suggested_resolution` for
  - Blocks generation outright on CRITICAL ambiguities (e.g. DELETE/UPDATE
    without WHERE) rather than emitting a destructive query
  - Returns clarification questions for unresolved HIGH/MEDIUM ambiguities
    in strict mode (the default); `strict=False` proceeds with warnings instead
- Hardcoded, independent safety net for unfiltered UPDATE/DELETE that holds
  even if the ambiguity gate is bypassed, unless `allow_full_table_write=True`
  is explicitly passed to `generate()`
- Supports SELECT, INSERT, UPDATE, DELETE, COUNT, and AGGREGATE query types,
  including JOINs, GROUP BY, HAVING, ORDER BY, DISTINCT, and LIMIT/OFFSET
- All values passed as `%s` query parameters, never string-interpolated

#### Models

- `GenerationStatus` enum (`success`, `success_with_warnings`,
  `needs_clarification`, `blocked`, `error`)
- `SQLGenerationResult` model carrying the SQL, params, warnings, and any
  clarification questions

#### Testing

- 14/14 tests passing in `testing/test_phase4.py`, covering clean generation,
  joins/aggregations, unfiltered DELETE/UPDATE blocking, the bypass-flag
  safety net, single- vs multi-way fuzzy table matches, a hard "table
  doesn't exist" error, non-strict mode, and IN/BETWEEN operators
- Test suite runs against an in-memory mock schema, no live database required

## [0.3.0] - 2026-08-27

### Added - Phase 3: Ambiguity Detection ✅

#### Core Features

- **AmbiguityDetector** class for comprehensive ambiguity detection
- **10 Ambiguity Types** detection:
  - Missing required filters (DELETE/UPDATE without WHERE)
  - Multiple table/column matches
  - Unclear table relationships
  - Ambiguous time references
  - Implicit aggregations
  - Unclear ordering
  - Multiple join paths
  - Ambiguous values
  - Unclear grouping
  - Multiple join paths

- **4 Severity Levels**:
  - CRITICAL: Must resolve (prevents data loss)
  - HIGH: Should resolve (prevents wrong results)
  - MEDIUM: Recommended (improves clarity)
  - LOW: Optional (nice to have)

#### Models

- `Ambiguity` model for representing individual ambiguities
- `AmbiguityDetectionResult` model for detection results
- `AmbiguityType` and `SeverityLevel` enums

#### Functionality

- Fuzzy matching for table name matching
- Foreign key relationship analysis
- Date column identification
- Automatic clarification question generation
- Multiple resolution options for each ambiguity
- `resolve_ambiguity()` function for applying user choices

#### Testing

- 9/9 comprehensive unit tests passing
- Real-world question analysis (10 business questions)
- Safety mechanism validation
- Severity classification tests

#### Documentation

- Complete Phase 3 documentation
- Real-world test results analysis
- Architecture diagrams
- Usage examples

### Changed

- Updated README.md with comprehensive project information
- Enhanced .gitignore with additional exclusions
- Reorganized documentation into docs/ directory

### Fixed

- Python cache cleanup in repository
- Project structure organization

## [0.2.0] - 2026-08-24

### Added - Phase 2: Natural Language Understanding ✅

#### Core Components

- **EntityRecognizer** class with fuzzy matching capabilities
- **IntentExtractor** for extracting structured intents from NL
- **OpenAI/Groq API Client** for LLM integration
- **QueryIntent** model for intermediate intent representation

#### Features

- Entity recognition (tables, columns, values)
- Intent classification (SELECT, COUNT, JOIN, etc.)
- Fuzzy matching for entity names
- Confidence scoring
- Schema validation

#### Testing

- 5/5 unit tests passing
- API client integration tests
- Entity recognition validation
- Full pipeline integration tests

#### Documentation

- Phase 2 setup guide
- API configuration instructions

## [0.1.0] - 2026-08-23

### Added - Phase 1: Database Schema Introspection ✅

#### Core Components

- **Database** class for MySQL connection management
- **SchemaIntrospector** for schema analysis
- **Schema** models for representing database structure

#### Features

- Automatic schema introspection
- Table detection and analysis
- Column type identification
- Foreign key relationship detection
- Primary key identification
- Constraint analysis

#### Models

- `Table` model for table information
- `Column` model for column metadata
- `ForeignKey` model for relationships
- `DatabaseSchema` model for complete schema

#### Testing

- 5/5 unit tests passing
- Database connection validation
- Schema analysis verification
- Relationship detection tests

#### Documentation

- Comprehensive setup guide
- Database configuration instructions
- Example usage

## [Unreleased]

### Planned - Phase 4: SQL Generation 🚧

#### Features

- Convert structured intents to SQL queries
- Support for multiple SQL dialects
- Query optimization
- Security validation

#### Models

- `SQLGenerationRequest`
- `SQLQuery`
- `QueryExecutionPlan`

### Planned - Phase 5: Query Optimization

#### Features

- Query plan analysis
- Index suggestions
- Performance optimization
- Execution plan visualization

### Planned - Phase 6: Result Interpretation

#### Features

- Result formatting
- Data visualization suggestions
- Natural language result summarization
- Insight extraction

### Planned - Phase 7: Web Interface

#### Features

- React-based frontend
- Real-time query building
- Result visualization
- Chat-based interface

### Planned - Enhanced Features

#### Multi-Database Support

- PostgreSQL support
- SQLite support
- Oracle support
- SQL Server support

#### Advanced NLP

- Better semantic understanding
- Business term dictionary
- Context-aware interpretation
- Multi-language support

#### ML/AI Enhancements

- Learn from user feedback
- Improve accuracy over time
- Context-aware suggestions
- Pattern recognition

#### API & Integration

- REST API endpoints
- GraphQL support
- Webhook support
- Third-party integrations

## Version History

| Version | Date       | Status      | Focus                |
| ------- | ---------- | ----------- | -------------------- |
| 0.3.0   | 2026-08-27 | ✅ Complete | Ambiguity Detection  |
| 0.2.0   | 2026-08-24 | ✅ Complete | NL Understanding     |
| 0.1.0   | 2026-08-23 | ✅ Complete | Schema Introspection |

## Statistics

### Code Metrics (as of 0.3.0)

- **Total Lines of Code**: ~3,500
- **Test Coverage**: 9/9 phases tests passing
- **Ambiguity Types**: 10 detected
- **Real-World Tests**: 10/10 successful
- **Components**: 7 main modules

### Performance

- Schema introspection: ~100ms
- Entity recognition: ~50ms per query
- Intent extraction: ~200ms per query (with LLM)
- Ambiguity detection: ~10-50ms per query

### Test Results

- Phase 1: 5/5 tests (100%) ✅
- Phase 2: 5/5 tests (100%) ✅
- Phase 3: 9/9 tests (100%) ✅
- Real-World: 10/10 questions analyzed ✅

## Deprecations

None yet.

## Security

### Version 0.3.0

- Added safety checks for dangerous queries
- Implemented query validation
- Added user confirmation for destructive operations

### Future Security

- SQL injection prevention
- Query sanitization
- Access control validation
- Audit logging

## Migration Guide

### From 0.2.0 to 0.3.0

No breaking changes. New features are backward compatible.

### From 0.1.0 to 0.2.0

No breaking changes. Only new components added.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Acknowledgments

### Libraries & Frameworks

- Pydantic for data validation
- MySQL for database support
- Groq/OpenAI for LLM capabilities

### Contributors

Thanks to all contributors who have helped with code, documentation, and testing!

## License

All code in this repository is under the MIT License. See LICENSE file for details.

---

## Versioning Notes

- **Major Version**: New phases completed (0.X.0)
- **Minor Version**: New features within phase (X.Y.0)
- **Patch Version**: Bug fixes and improvements (X.Y.Z)
- **Pre-release**: Beta/RC versions (0.3.0-beta.1)

## Release Schedule

- Phase 4 (SQL Generation): Q3 2026
- Phase 5 (Optimization): Q4 2026
- Phase 6 (Result Interpretation): Q1 2027
- Web UI: Q1 2027
