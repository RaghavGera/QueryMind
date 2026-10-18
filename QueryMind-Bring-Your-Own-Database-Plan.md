# QueryMind: bring your own database (plan)

> **Status: proposal (2026-10-18), not started.** It starts after the Render → Neon move, which is due before 2026-10-23. Scope chosen by the owner: **both** file uploads and live PostgreSQL connections.

## Goal

Anyone can point QueryMind at their own data in two ways:
1. **Upload files** (CSV / Excel). Each file becomes a table in a private, auto-expiring workspace.
2. **Connect their own PostgreSQL** with a connection URL, ideally for a read-only user.

QueryMind then works on that data exactly as it does on the demo database: clarifications, generated SQL, results, history.

## What already works on any schema, and what doesn't

| Part | Status |
|---|---|
| Schema introspection, ambiguity detector, SQL generator, join planner | **Schema-agnostic**: they work from whatever schema they are given |
| Schema introspection | Only reads the `public` schema (`app/schema.py`); needs a schema parameter for upload workspaces |
| Extractor prompt (`app/intent_extractor.py`) | **Demo-specific**: every worked example uses `customers`/`orders`/`order_items`; the "top N means units sold" rule is shop logic |
| Prompt trimming metric words, vague-term metric words | Mostly generic (revenue, price, amount, total, quantity); review them |
| Database connection | One global connection from the `DB_*` variables; needs per-request routing to the active workspace |
| Eval set | Demo-only; needs a second, unrelated sample dataset to prove the pipeline is schema-agnostic |

## Design

**Workspaces.**
- Each browser gets an anonymous workspace token, sent as an `X-Workspace` header; the demo workspace is the default.
- A registry table in `querymind_meta` records each workspace's kind (demo / upload / connection), owner token hash, creation and expiry time. Connection credentials are stored encrypted.
- No accounts yet. A workspace belongs to the browser that created it.

**Uploads.**
- Endpoint: `POST /workspaces/upload`, multipart.
- Limits: CSV or XLSX, ≤ 10 files, ≤ 10 MB total, ≤ 200k rows per file.
- Processing:
  - infer column types (integer, numeric, date, timestamp, boolean, text);
  - sanitize identifiers;
  - create schema `ws_<id>` on Neon and load the rows with COPY;
  - detect obvious foreign keys (`<table>_id` matching another table's key) so joins work.
- The user sees the inferred tables, types and keys **before** importing.
- No `.sql` dumps: running uploaded SQL would let anyone execute arbitrary statements.
- Upload workspaces expire after 7 days. Cleanup runs at startup and on a timer. A storage quota protects Neon's free 0.5 GB.

**Connections.**
- Endpoint: `POST /workspaces/connect`, taking a PostgreSQL URL.
- SSRF protection before connecting: resolve the host and refuse private, loopback, link-local and cloud-metadata addresses.
- Connect with a short timeout and run a test query.
- The credentials are encrypted at rest (Fernet, key from a server secret) and expire after 24 hours.
- The UI shows the SQL to create a read-only user, and recommends it.

**Execution safety, required before any outside database is touched** (this is saved Track B):
- every query in a `READ ONLY` transaction;
- an 8-second statement timeout and a 1,000-row cap;
- blocking endpoints moved off the event loop;
- writes stay demo-only (or off) for uploads and connections.

**Abuse protection, required before public uploads** (saved Track C): per-IP rate limits on `/query` and on the upload and connect endpoints.

**Pipeline generalization.**
- Make the prompt schema-neutral: either describe the examples as illustrating a sample schema and tell the model to use only the provided tables, or generate examples from the active schema.
- Keep shop-specific defaults (such as "top N = units sold") for the demo workspace only. On other schemas, ask instead.
- Add a second sample dataset (for example employees / departments / projects) with its own eval questions.

**Frontend.**
- A **Connect** page (`/app/connect`) with two tabs:
  - **Upload**: drag and drop, then a preview of the inferred schema, then import;
  - **PostgreSQL**: URL field, a read-only user guide, then Test and Connect.
- A workspace switcher in the top bar.
- Schema tab, history and saved queries scoped to the active workspace.
- A clear privacy note: where uploads live and when they are deleted.

**Engines.** PostgreSQL first. MySQL and SQLite later, if wanted: they need their own introspection and SQL dialect.

**New dependencies** (approval needed): `openpyxl` (Excel files) and `cryptography` (credential encryption).

## Phases

0. **Neon migration** (in progress; owner steps).
1. **Safety foundation:** Track B (read-only, timeout, row cap, threadpool) and Track C (rate limits).
2. **Workspace core:** schema-aware introspection, the workspace registry, per-request DB routing, demo as the default.
3. **Uploads:** parsing, type inference, FK detection, preview, import, expiry and quotas.
4. **Connections:** SSRF guard, encrypted credentials, connection test, read-only enforcement.
5. **Pipeline generalization:** schema-neutral prompt, demo-only shop rules, second dataset and its eval.
6. **Frontend:** Connect page, workspace switcher, scoped history and saved queries.
7. **Docs and claims:** README, SETUP, a privacy note on the site, CHANGELOG.

## Verification

- **Unit tests:**
  - type inference (dates, numbers with commas, empty cells);
  - identifier sanitizing;
  - FK detection;
  - SSRF guard (private IPs, `localhost`, DNS rebinding, metadata IP);
  - credential encryption round trip;
  - workspace isolation (workspace A can never read workspace B).
- **End to end:**
  - upload the second sample dataset as CSVs and ask its eval questions;
  - connect a local read-only Postgres user and confirm that writes and long queries are refused.
- **Live:**
  - the demo eval stays 41/41;
  - the new dataset's eval passes;
  - expired workspaces are actually deleted.
