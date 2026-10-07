# QueryMind

**Ask your database a question in plain English. QueryMind writes the SQL, runs it, and when your question could mean two things, it asks before it answers.**

[Live app](https://query-mind-tawny.vercel.app) · [API](https://querymind-crln.onrender.com/health) · [Setup guide](SETUP.md) · [Changelog](CHANGELOG.md)

---

## Why QueryMind

Most text-to-SQL tools hand your question to a language model and run whatever SQL comes back. That works until a question is vague, and then you get a confident, wrong answer. QueryMind is built around three ideas.

- **Ambiguity is a feature.** "Show me the top customers" does not say *top by what*. QueryMind detects that and asks: *"What should 'top' be ranked by? For example total spending, number of orders, or units sold."* It answers only once the question is unambiguous.
- **The model never writes SQL.** The language model only extracts a structured intent (tables, columns, filters, aggregations). A deterministic generator turns that intent into SQL, checks every identifier against the live schema, and passes every value as a parameter.
- **Every answer shows its working.** Each result comes with the exact SQL that produced it, ready to copy, re-run or save.

## See it work

A real request against the demo database:

```bash
curl -X POST https://querymind-crln.onrender.com/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Which region generated the most revenue?"}'
```

The schema has no `region` column, so the extractor maps the word to the closest real one, `customers.country`. It reads "revenue" as arithmetic over real columns. The generator then produces:

```sql
SELECT "customers"."country", SUM("order_items"."quantity" * "order_items"."unit_price") AS "sum_order_items_quantity_order_items_unit_price"
FROM "orders"
INNER JOIN "customers" ON "orders"."customer_id" = "customers"."customer_id"
INNER JOIN "order_items" ON "orders"."order_id" = "order_items"."order_id"
GROUP BY "customers"."country"
ORDER BY SUM("order_items"."quantity" * "order_items"."unit_price") DESC
LIMIT 1
```

The response contains that SQL, its parameters, any warnings, and the rows: India, 734,561.

Ask something vague and the response is a clarification question instead. Answer it, and QueryMind runs exactly what you meant.

## How it works

```
  question
     │
     ▼
  Intent extraction      LLM tool call on a schema-trimmed prompt;   ─ app/intent_extractor.py
     │                   relative dates resolved to ISO ranges
     │                   (output: structured intent, never SQL)
     ▼
  Conversion             normalizes the intent, computes comparison  ─ app/intent_converter.py
     │                   periods, validates against the live schema
     ▼
  Ambiguity gate         11 ambiguity types, 4 severity levels       ─ app/ambiguity_detector.py
     │                   critical → blocked · unresolved → ask       ─ app/vague_terms.py
     │                   confident → auto-resolved, shown as a warning
     ▼
  SQL generation         join planning from foreign keys, quoted     ─ app/sql_generator.py
     │                   identifiers, parameterized values
     ▼
  Execution              PostgreSQL via psycopg 3                    ─ app/database.py
     │
     ▼
  answer: SQL + parameters + rows (+ warnings), or a clarification question
```

Design decisions that matter in production:

- **Structured output only.** The extractor uses function calling, and JSON returned in the message body is accepted as a fallback. Free-form SQL from the model is never executed.
- **Defense in depth for writes.** INSERT and UPDATE are off by default. When enabled, the backend returns a preview and a signed, single-use confirmation token, and it rolls back if the affected row count changes between preview and execution. An UPDATE without a WHERE clause is blocked. Natural-language DELETE is refused outright.
- **A resilient model chain.** Requests go through an ordered chain of OpenAI-compatible providers: Gemini 3.5 Flash-Lite → Groq (Qwen) → Gemini 3.1 Flash-Lite → Gemini 3.8 Flash.
  - Rate limits, 5xx errors and 12-second timeouts move the request to the next entry.
  - Daily-quota errors park that entry until its quota resets.
  - Every call logs the provider, model, prompt and completion tokens, and latency.
- **Lean prompts.** Each prompt includes only the tables a question mentions, plus their foreign-key neighbours. Over 100 test questions this measured a 3.2% saving in prompt tokens. The saving is modest because the demo schema is small; it grows with larger schemas.

## What it can answer

| Capability | Example |
|---|---|
| Filters, including case-insensitive text | *Show cancelled orders.* |
| Relative dates resolved to real ranges | *How many new customers signed up last month?* |
| Aggregates over arithmetic expressions | *What is the total revenue from completed orders?* |
| Grouping, ranking and limits | *Which country generates the most revenue?* |
| Conditions on aggregates (HAVING) | *Which customers have placed more than 5 orders?* |
| Anti-joins | *Find customers who have never placed an order.* |
| Time bucketing | *Show monthly revenue from orders.* |
| Nested aggregates | *What is the average order value?* |
| Top N within each group | *What were the top 5 products by revenue in each category?* |
| Period-over-period comparison | *Show customers whose spending increased this quarter.* |
| Confirmed inserts and updates (opt-in) | *Change the price of Laptop 1 to 999* |

## The web app

The frontend, in `frontend/`, has two parts.

- **The public site** is a scroll-driven experience. A WebGL starfield sits behind pinned, scroll-scrubbed scenes that walk through the pipeline: the question, the schema it maps onto, the ambiguity it catches, the SQL it generates and the answer it returns. The site also has a live console wired to the real API. Every SQL snippet, clarification and number on these pages is a real capture from the generator and the demo database. Visitors who prefer reduced motion, or whose browsers lack WebGL, get static and fully readable versions.
- **The app** (`/app`) is where you work: ask questions, answer clarifications, inspect the SQL, and switch between table and chart views. It also keeps a query history and saved queries, both of which reopen stored results without re-running them, plus a live schema browser and settings. Motion there stays out of the way: results appear as soon as the backend answers.

## Tech stack

| Layer | Technology |
|---|---|
| API | Python 3.10+, FastAPI, Pydantic 2 |
| Database | PostgreSQL, psycopg 3 |
| Language models | Google Gemini and Groq through the OpenAI-compatible SDK, with failover |
| Frontend | React 18, Vite, Tailwind CSS, Framer Motion, three.js / React Three Fiber, Lenis, Recharts |
| Hosting | Render (API and database), Vercel (frontend) |
| Testing | pytest, Node's built-in test runner, an evaluation harness against the live API |

## Getting started

**Prerequisites:**
- Python 3.10+
- PostgreSQL
- Node.js 20.19+ or 22.12+
- An API key for Gemini ([Google AI Studio](https://aistudio.google.com/apikey)), Groq ([console](https://console.groq.com/keys)), or both

```bash
git clone https://github.com/RaghavGera/Text-to-SQL.git
cd Text-to-SQL

# Backend
pip install -r requirements.txt
cp .env.example .env                 # set DB_* and GEMINI_API_KEY and/or GROQ_API_KEY
createdb text_to_sql
psql -d text_to_sql -f database/text_to_sql_database.sql   # demo data
uvicorn app.main:app --reload        # http://127.0.0.1:8000

# Frontend (second terminal)
cd frontend
# create frontend/.env.local containing: VITE_API_BASE_URL=http://127.0.0.1:8000
npm install
npm run dev                          # http://localhost:5173
```

The demo database holds 500 customers, 100 products, 2,000 orders and 5,000 order items across 5 countries. [SETUP.md](SETUP.md) covers every environment variable, the provider chain, write confirmation and troubleshooting.

## Quality

Claims about accuracy are measured, not estimated.

```bash
pytest testing/                          # backend: 294 passing (DB tests skip without PostgreSQL)
cd frontend && npm test                  # frontend: 21 passing
python -m testing.eval_harness           # 41 real questions against the live API
python -m testing.eval_harness --offline # same questions in-process, no database needed
```

The evaluation harness checks each answer, not just the status code:
- required SQL fragments;
- row counts and expected values;
- that vague questions produce a clarification rather than a guess;
- that unsafe requests are refused.

Rate limits and outages are reported separately from real failures. On the most recent live run (2026-10-05), all 41 questions passed.

Tests that spend LLM tokens are opt-in: `python -m testing.run_tests --live`.

## Project structure

```
app/                  FastAPI backend
  main.py             endpoints: /query, /query/confirm, /schema, /health
  intent_extractor.py LLM intent extraction, provider failover, prompt trimming
  openai_client.py    provider chain configuration
  intent_converter.py intent normalization and validation
  ambiguity_detector.py, vague_terms.py
  sql_generator.py    parameterized SQL generation and join planning
  schema.py           live schema introspection
  writes.py           write previews and confirmation tokens
frontend/             React app (public site + /app)
  src/components/universe/   WebGL scene
  src/components/landing/    scroll-driven chapters
  src/motion/                motion primitives (pinned chapters, smooth scroll, text effects)
testing/              pytest suites, evaluation harness and its question set
database/             demo schema and seed data
docs/                 known issues and phase documentation
```

## API at a glance

| Endpoint | Purpose |
|---|---|
| `POST /query` | Ask a question; returns SQL, parameters and rows, or clarification questions |
| `POST /query/confirm` | Execute a previewed insert or update with its confirmation token |
| `GET /schema` | The live schema: tables, columns, keys and the database name |
| `GET /health` | Database connectivity, and whether writes are enabled |

`POST /query` accepts the following options:
- `clarification_context`: your answer to a clarification question;
- `strict`: set it to `false` to let the model guess instead of asking;
- `allow_writes`: set it to `false` to keep a request read-only.

Full details are in [SETUP.md](SETUP.md#request-options-for-post-query).

## Documentation

- [SETUP.md](SETUP.md): installation, configuration, provider chain, tests
- [CHANGELOG.md](CHANGELOG.md): what changed and why
- [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md): open issues, with measured evidence
- [docs/PHASE3_README.md](docs/PHASE3_README.md): the ambiguity detector in depth
- [docs/PHASE4_README.md](docs/PHASE4_README.md): SQL generation and the safety model
- [CONTRIBUTING.md](CONTRIBUTING.md): how to contribute

## Roadmap

**Shipped:**
- schema introspection;
- LLM intent extraction with provider failover;
- the ambiguity gate and clarification loop;
- parameterized SQL generation, including comparisons, top-N per group, nested aggregates, anti-joins and time bucketing;
- confirmed writes;
- the web app.

**Next:** product hardening.
- read-only transactions, query timeouts and row caps at the database layer;
- per-client rate limiting and API keys;
- a query audit log with usage analytics;
- plain-English explanations of generated SQL;
- CSV export;
- continuous integration with a nightly live evaluation.

## Contributing

Issues and pull requests are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) first. Every change needs tests and a CHANGELOG entry, and any claim about accuracy needs a measurement behind it.

## License

Released under the [MIT License](LICENSE).

## Author

[Raghav Gera](https://github.com/RaghavGera)

Built with Google Gemini, Groq, FastAPI, PostgreSQL and React.
