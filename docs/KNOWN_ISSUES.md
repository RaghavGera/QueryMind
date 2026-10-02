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
| Show customers whose spending increased this quarter | `needs_clarification` ("What aggregation do you want to perform?"). Re-run live later on 2026-10-02 (still `4b50c56`): `error`, "Invalid aggregation expression 'CASE WHEN orders.order_date BETWEEN '2026-07-01' AND '2026-09-30' THEN … ELSE 0 END'" — the old build has no comparison slot, so the model hand-writes a CASE | Fixed in code (`af68250`, `comparison` slot → generated current-vs-previous query). Local run 2026-10-02 on gemini-3.1-flash-lite: `success`, 3/3 extractions correct; 0 rows because the local data has no orders after 2026-08-25 ("last quarter" variant: 95 rows). **Needs a live re-check after deploy** |

## Found while building the Phase 1 eval harness (2026-10-02)

| Issue | Evidence | State |
|---|---|---|
| **Case-sensitive text filters returned nothing.** Stored values are capitalised (`Cancelled`, `Completed`) but the model emits lowercase. | Live: "Show cancelled orders." → `WHERE status = 'cancelled'` → 0 rows; "total revenue from completed orders" → `NULL` | Fixed in code (text columns now compared with `LOWER()` / `ILIKE`); **needs a live re-check after deploy** |
| **Vague terms were answered by guessing**, contradicting "ambiguity is a feature". | Offline run with the real LLM: "Show me expensive products." generated `price > %s` with an invented threshold; "Show me the top customers." silently ranked by spend; "Show me customers with high spending." did the same | Fixed in code (`app/vague_terms.py` + `AmbiguityDetector._check_vague_terms`); **needs a live re-check after deploy** |
| Qualified condition columns (`customers.signup_date`) made the detector ask "which date column?" for "last month". | Offline run, 3/3 reproductions | Fixed in code (converter splits `table.column` in conditions) |
| Aggregate conditions ("more than 5 orders") failed with `Invalid condition expression 'COUNT(orders.order_id)'`. | Offline eval, `gap-having-orders-over-5` | Fixed in code (HAVING support); **needs a live re-check after deploy** |

## Still open

| Issue | Notes |
|---|---|
| Date bucketing ("monthly revenue") | Generator has no `date_trunc`; question `gap-monthly-revenue` tracked as a `known_gap` in the eval set |
| Nested aggregates ("average order value") | Needs AVG over a per-order SUM (subquery); `gap-average-order-value` |
| Anti-joins ("customers who never ordered") | Needs `NOT EXISTS` / `LEFT JOIN … IS NULL`; `gap-never-ordered` |
| Period-over-period comparisons | Phase 2 |
| Natural-language INSERT/UPDATE | Phase 2 |

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
