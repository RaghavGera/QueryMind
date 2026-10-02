# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
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
- **LLM provider failover chain**: Gemini (Google AI Studio), Mistral, Groq and OpenAI, tried in
  `LLM_PROVIDER_ORDER` (default `gemini,mistral,groq,openai`); providers without a key are skipped.
  A daily-quota 429 parks the provider and fails over immediately; a per-minute 429 gets one short
  retry; 5xx/timeouts/other 4xx fail over. `/query` returns 429 only when every provider is rate
  limited. Per-provider model overrides `GEMINI_MODEL`, `MISTRAL_MODEL`, `GROQ_MODEL`, `OPENAI_MODEL`.
  Each served request logs provider, model, `prompt_tokens` and `completion_tokens`.
- **Per-question schema trimming**: only the tables `EntityRecognizer` finds, plus metric tables and
  foreign-key neighbours, are sent to the LLM; full schema when nothing is recognised. Validation
  still uses the full schema. `python -m testing.measure_prompt_tokens` measures the effect.
- Extraction uses the standard `tools` API (Mistral and Gemini do not document the legacy
  `functions` parameter).
- Required-column check for INSERT: missing NOT NULL values become clarification questions.
- `docs/KNOWN_ISSUES.md`: observed behaviour per question, owner actions, open gaps.

### Changed
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

### Fixed
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
