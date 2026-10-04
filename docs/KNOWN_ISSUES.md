# Known issues log

Source of truth for open problems and what was actually observed. Only
measured results are recorded here; update the **Observed** column whenever a
question is re-tested, and say which build (commit) it was tested against.

## Sample questions (Build Plan §7)

Retested live against `https://querymind-crln.onrender.com` on 2026-10-02,
against the build deployed at commit `3eec66d` (before the Phase 1 changes).

| Question | Observed (live, 2026-10-02) | State |
|---|---|---|
| How many new customers signed up last month? | `success`; `signup_date BETWEEN '2026-09-01' AND '2026-09-30'`; count `0` (data-dependent: the seed script dates customers relative to when it was run) | Fixed |
| What were our top 10 products? | `success`; ranked by `SUM(order_items.quantity)`, 10 rows | Passed this run, but flaky before: the model sometimes returned `group_by` with no aggregation → `needs_clarification`. Phase 1 adds prompt rules + a deterministic fallback; see *Q2 variance* below |
| Which region generated the most revenue? | `success`; India, `734561.0` | Fixed and verified |
| Show customers whose spending increased this quarter | `needs_clarification` ("What aggregation do you want to perform?"). Re-run live later on 2026-10-02 (still `4b50c56`): `error`, "Invalid aggregation expression 'CASE WHEN orders.order_date BETWEEN '2026-07-01' AND '2026-09-30' THEN … ELSE 0 END'" — the old build has no comparison slot, so the model hand-writes a CASE | Fixed in code (`af68250`, `comparison` slot → generated current-vs-previous query). Local run 2026-10-02 on gemini-3.1-flash-lite: `success`, 3/3 extractions correct; 0 rows because the local data has no orders after 2026-08-25 ("last quarter" variant: 95 rows). **Verified live 2026-10-02 after deploying `c42a257`:** `success`, periods 2026-10-01..2027-01-01 vs 2026-07-01..2026-10-01, 0 rows (no orders yet this quarter); "…increased last quarter" → `success`, 95 rows |

## Found while building the Phase 1 eval harness (2026-10-02)

| Issue | Evidence | State |
|---|---|---|
| **Case-sensitive text filters returned nothing.** Stored values are capitalised (`Cancelled`, `Completed`) but the model emits lowercase. | Live: "Show cancelled orders." → `WHERE status = 'cancelled'` → 0 rows; "total revenue from completed orders" → `NULL` | Fixed in code (text columns now compared with `LOWER()` / `ILIKE`); **needs a live re-check after deploy** |
| **Vague terms were answered by guessing**, contradicting "ambiguity is a feature". | Offline run with the real LLM: "Show me expensive products." generated `price > %s` with an invented threshold; "Show me the top customers." silently ranked by spend; "Show me customers with high spending." did the same | Fixed in code (`app/vague_terms.py` + `AmbiguityDetector._check_vague_terms`); **needs a live re-check after deploy** |
| Qualified condition columns (`customers.signup_date`) made the detector ask "which date column?" for "last month". | Offline run, 3/3 reproductions | Fixed in code (converter splits `table.column` in conditions) |
| Aggregate conditions ("more than 5 orders") failed with `Invalid condition expression 'COUNT(orders.order_id)'`. | Offline eval, `gap-having-orders-over-5` | Fixed in code (HAVING support); **needs a live re-check after deploy** |

## Still open

Live eval on 2026-10-04 (`python -m testing.eval_harness` against the build at
`ee88c74`): **41/41 core questions passed**, including date bucketing, nested
aggregates, anti-joins, period comparison, top-N per group and insert/update
previews (all previously listed here as open).

| Issue | Notes |
|---|---|
| Latency outliers | Same run: median 3.8 s, p90 9.7 s, but 5/41 requests took 35–40 s. **Cause confirmed** in the Render logs (2026-10-04): `LLM provider gemini-lite unavailable (APITimeoutError); failing over` — gemini-lite hung until the 30 s timeout. Fixed in code: timeout now 12 s (`LLM_TIMEOUT_SECONDS`), log lines include `seconds=`; **needs a live re-check after deploy** |
| No auth / rate limiting | Anyone can call `/query` and spend the LLM quota (Phase 3) |
| History and saved queries are browser-only | Stored in `localStorage`, not per user (Phase 3) |
| No usage analytics | Clarification rate, latency, success rate are not recorded server-side (Phase 3) |

## Owner actions the code cannot do (need your Render/Vercel access)

1. **Rotate the Render PostgreSQL password.** It was pasted into a chat on
   2026-09-29 and must be treated as compromised. In the Render dashboard:
   rotate the DB credentials → update `DB_PASSWORD` on the backend service
   (and `DB_USER` if it changed) → redeploy → confirm
   `GET /health` returns `"status": "healthy"`. Do not paste the new value
   anywhere except the Render env-var screen.
2. **Confirm Render auto-deploys from `main`** (Service → Settings → Build &
   Deploy → Auto-Deploy = *Yes*). If it is off, deploy manually after each push.
3. **Confirm the Vercel project's Root Directory is `frontend/`.**
   `frontend/vercel.json` (SPA rewrite) only takes effect if that is the root.
   After deploy, hard-refresh `/app`, `/architecture` and `/developers` — each
   should render instead of returning Vercel's 404.
4. Optionally restrict the Render database's allowed inbound sources to the
   backend service.
5. **Failover LLM key on Render** (`GEMINI_API_KEY`) - owner reports it is set
   (2026-10-02). The chain skips an entry without a key *silently*; after the
   deploy, check the logs for `LLM request served provider=gemini-lite` to
   confirm Gemini is actually serving. Remove any `GEMINI_MODEL` /
   `LLM_PROVIDER_ORDER` values copied from earlier docs.
6. **Check `GROQ_MODEL` on Render.** The code now honours it. Old copies of
   `.env.example` suggested `llama-3.1-70b-versatile`; if that stale value is
   set, Groq requests will use (or fail on) that model. Unset it to use the
   default `qwen/qwen3.8-27b`.

Status of these as of 2026-10-02: `/health` is currently green on the old
credentials; items 1–4 are **not yet done** (they require dashboard access).

Update 2026-10-04: item 2 confirmed in effect (pushes to `main` reached the live
backend without a manual deploy — the period-comparison fix went live after the
push). Item 3 confirmed in effect: `/`, `/app`, `/app/settings`,
`/architecture`, `/developers` on `https://query-mind-tawny.vercel.app` all
return 200 with the app shell. Items 1, 4, 5, 6 still open.

Update 2026-10-04 (owner): item 5 confirmed — Render logs show `LLM request served provider=gemini-lite`. Item 6: `GROQ_MODEL` is not set on Render (default used). `DATABASE_URL` is set on Render but unused by the code; delete it after the password rotation.

7. **The Render PostgreSQL database expires on 2026-10-23** (free plan). Before then: upgrade the plan, or migrate (`pg_dump` → restore on the new host → update the five `DB_*` vars → `/health`). A migration also replaces the leaked credentials from item 1.
