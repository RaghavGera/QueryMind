# Phase 4: SQL Generation Engine

## Overview

Phase 4 turns a (clarified) structured intent into an actual, parameterized
SQL query. It sits directly downstream of Phase 3 and treats the
`AmbiguityDetector` as a hard gate rather than an optional check: nothing
gets built into SQL until the detector has either found no problems or had
its problems resolved.

The core question Phase 4 answers isn't "can I produce *some* SQL for
this?" -- it's "can I produce SQL I'm confident is *correct and safe*?" If
not, it says so instead of guessing.

## Architecture

```
Natural Language Query
    ↓
Phase 1: Database Schema Analysis (introspection)
    ↓
Phase 2: Entity Recognition & Intent Extraction (LLM) → QueryIntent
    ↓
app/intent_converter.py: QueryIntent → StructuredIntent
    ↓
Phase 3: AmbiguityDetector.detect_ambiguities(intent)
    ↓
  ┌─ CRITICAL ambiguity present? ──────────────▶ BLOCKED (no SQL, ask user)
  │
  ├─ Non-critical ambiguity, suggested_resolution
  │   present, auto_resolve=True? ─────────────▶ auto-apply resolve_ambiguity(),
  │                                              keep going, note a warning
  │
  ├─ Non-critical ambiguity, no confident
  │   resolution, strict=True (default)? ──────▶ NEEDS_CLARIFICATION (no SQL)
  │
  └─ Everything resolved or strict=False ──────▶ PHASE 4: SQL GENERATION
                                                       ↓
                                          SQLGenerator._build_sql()
                                                       ↓
                                     Parameterized SQL + params list
```

## Components

### 1. `GenerationStatus` Enum

| Status | Meaning | Is `sql` populated? |
|---|---|---|
| `SUCCESS` | Clean generation, nothing to flag | Yes |
| `SUCCESS_WITH_WARNINGS` | Generated, but one or more ambiguities were auto-resolved (or, in non-strict mode, left unresolved) along the way | Yes |
| `NEEDS_CLARIFICATION` | A non-critical ambiguity had no confident resolution (strict mode) | No |
| `BLOCKED` | A CRITICAL ambiguity was detected (e.g. unfiltered DELETE/UPDATE) | No |
| `ERROR` | The intent couldn't be turned into SQL at all (bad table, missing required data) | No |

### 2. `SQLGenerationResult` Model

```python
class SQLGenerationResult(BaseModel):
    status: GenerationStatus
    sql: Optional[str]
    params: List[Any]
    warnings: List[str]
    clarification_questions: List[str]
    error_message: Optional[str]
    ambiguity_result: Optional[AmbiguityDetectionResult]
```

### 3. `SQLGenerator`

```python
generator = SQLGenerator(
    schema,                 # DatabaseSchema
    detector=None,          # optional pre-built AmbiguityDetector
    strict=True,            # block on unresolved non-critical ambiguities
    auto_resolve=True,      # apply confident suggested_resolutions automatically
)

result = generator.generate(
    intent,
    allow_full_table_write=False,  # explicit opt-in for an unfiltered UPDATE/DELETE
)
```

Supported `QueryType`s: `SELECT`, `COUNT`, `AGGREGATE`, `INSERT`, `UPDATE`,
`DELETE` -- including `JOIN`s, `GROUP BY`/`HAVING`, `ORDER BY`, `DISTINCT`,
and `LIMIT`/`OFFSET`.

## Safety Model (defense in depth)

There are **two independent layers** that keep Phase 4 from emitting a
destructive, unfiltered query:

1. **The ambiguity gate.** `_check_missing_filters` (Phase 3) flags any
   `DELETE`/`UPDATE` with no `WHERE` conditions as `CRITICAL`. `can_proceed`
   is `False` whenever a `CRITICAL` ambiguity exists, and `SQLGenerator`
   returns `BLOCKED` before it ever calls the SQL builder.
2. **The builder's own check.** Even if something upstream were to bypass
   the ambiguity gate, `_build_update`/`_build_delete` independently refuse
   to build a `WHERE`-less statement unless `allow_full_table_write=True`
   is passed explicitly to `generate()`.

Passing `allow_full_table_write=True` only affects layer 2. It does **not**
suppress the `CRITICAL` ambiguity in layer 1 -- see `test_phase4.py`
("Bypass flag does not defeat ambiguity gate") for the test that pins this
down. To actually run an intentional full-table write, the caller has to
add a condition that's trivially always-true, or the ambiguity detector
would need a separate "user has explicitly confirmed" resolution path
(not currently implemented -- a good Phase 5 candidate).

## Auto-Resolution vs. Clarification

Not every ambiguity needs a human. `resolve_ambiguity()` (Phase 3) can
already apply a fix automatically when the detector attaches a
`suggested_resolution` -- currently that happens for `MULTIPLE_TABLE_MATCHES`
and `MULTIPLE_COLUMN_MATCHES` where exactly one plausible match was found.
`SQLGenerator` uses this so a typo like `"cusomer"` (single fuzzy match:
`customers`) generates working SQL with a warning attached, instead of
stopping to ask a question with only one sane answer.

When there's genuine ambiguity -- e.g. a table name that matches two real
tables, or a `HIGH`-severity issue with no `suggested_resolution` -- there
is no safe default to pick, so `SQLGenerator` reports
`NEEDS_CLARIFICATION` and returns the question(s) instead of a guess.

## Identifier Quoting & Injection Safety

All identifiers (table/column names) are double-quoted (`"table"."column"`)
and all values are passed as `%s` placeholders with a matching `params`
list -- never string-interpolated into the SQL text. This closes off the
most common SQL-injection vector by construction: a value like
`"'; DROP TABLE customers; --"` ends up as a single bound parameter, not as
SQL syntax.

## The `/query` Endpoint

`app/main.py` exposes `POST /query`:

```json
// Request
{ "question": "show pending orders", "strict": true, "allow_full_table_write": false }

// Response (SUCCESS)
{
  "status": "success",
  "sql": "SELECT \"order_id\", \"status\"\nFROM \"orders\"\nWHERE \"status\" = %s",
  "params": ["pending"],
  "warnings": [],
  "clarification_questions": [],
  "error_message": null,
  "has_ambiguities": false
}
```

It chains: schema introspection (Phase 1) → `extract_intent` (Phase 2,
LLM call) → `convert_query_intent` (new glue in `app/intent_converter.py`)
→ `SQLGenerator.generate` (Phases 3+4). **It returns SQL, it does not
execute it** -- running the query against the database is left to the
caller, deliberately, so nothing destructive can happen without a
separate, explicit step.

### A Known Gap: INSERT/UPDATE via Natural Language

Phase 2's `extract_intent` function schema has no slot for the actual
values of an `INSERT`/`UPDATE` (only `query_type`, `tables`, `columns`,
`conditions`, etc.) so `convert_query_intent` deliberately raises
`IntentConversionError` for those two query types rather than fabricating
`insert_values`/`update_values`. Mutating via natural language will need
either a Phase 2 schema update to capture value bindings, or a follow-up
clarification turn that collects them explicitly. Until then, `INSERT`/
`UPDATE` are only reachable by constructing a `StructuredIntent` directly
(as `test_phase4.py` does), not through `/query`.

## Testing

`testing/test_phase4.py` -- 14/14 passing, against an in-memory mock
schema (no live database required):

- Clean `SELECT`/`JOIN`/`GROUP BY`+`HAVING`/`COUNT`/`INSERT` generation
- Unfiltered `DELETE` and `UPDATE` both blocked
- `allow_full_table_write=True` does **not** defeat the ambiguity gate
- A filtered `UPDATE` succeeds once a `WHERE` is added
- A single fuzzy table match (`"cusomer"` → `customers`) auto-resolves
- A multi-way fuzzy table match (`"order"` → `orders` / `order_items`)
  asks for clarification
- A table with no plausible match at all (`"widgets"`) is a hard `ERROR`
- `strict=False` proceeds on a non-critical ambiguity instead of blocking
- `IN` and `BETWEEN` operators render with the correct number of
  placeholders and params

## Roadmap Notes for Phase 5+

- Add value-binding support to Phase 2 so `/query` can drive `INSERT`/`UPDATE`.
- A "confirmed full-table write" resolution path in the ambiguity detector,
  so a user can deliberately say "yes, delete all rows" and have that flow
  through as a real resolution rather than needing a workaround condition.
- Query plan / index-usage analysis (this is squarely Phase 5's job per the
  README roadmap).
