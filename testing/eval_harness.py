"""
QueryMind eval harness.

Runs the questions in ``testing/eval_questions.json`` through ``POST /query``
and checks each response against explicit expectations (HTTP status, response
status, SQL shape, row counts, specific cells). It fails loudly: any core
question that does not meet its expectation makes the run exit non-zero.

Usage
-----
    # Against the live backend (default) or any other deployment
    python -m testing.eval_harness
    python -m testing.eval_harness --base-url http://localhost:8000

    # Repeat each question to measure LLM variance (e.g. Q2 5/5)
    python -m testing.eval_harness --only q2-top-10-products --runs 5

    # No database needed: real LLM + real converter/generator against the
    # in-memory schema. Row/cell checks are skipped (reported as such).
    python -m testing.eval_harness --offline

    # Machine-readable results
    python -m testing.eval_harness --json eval_results.json

Question tiers
--------------
``core``     questions the pipeline is expected to answer. Any failure fails
             the run.
``known_gap`` questions that exercise documented gaps (see
             docs/KNOWN_ISSUES.md). They are run and reported, but they do
             not fail the run -- they exist so progress is measured, not
             guessed. Move one to ``core`` when the gap is closed.

Only measured results are ever reported; nothing here is hard-coded.
"""

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

QUESTIONS_PATH = Path(__file__).with_name("eval_questions.json")
DEFAULT_BASE_URL = "https://querymind-crln.onrender.com"

SUCCESS_STATUSES = {"success", "success_with_warnings"}
INFRA_HTTP_STATUSES = (0, 429, 502, 503, 504)


# ---------------------------------------------------------------------- #
# Checking (pure -- unit tested in test_eval_harness.py)
# ---------------------------------------------------------------------- #

def normalize_sql(sql: Optional[str]) -> str:
    """Lower-case, strip identifier quotes and collapse whitespace."""
    if not sql:
        return ""
    return re.sub(r"\s+", " ", sql.replace('"', "")).strip().lower()


def _expected_statuses(expect: Dict[str, Any]) -> set:
    wanted = expect.get("status", "success")
    wanted = [wanted] if isinstance(wanted, str) else list(wanted)
    expanded = set()
    for status in wanted:
        if status == "success":
            expanded |= SUCCESS_STATUSES
        else:
            expanded.add(status)
    return expanded


def _values_equal(actual: Any, expected: Any) -> bool:
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        try:
            return abs(float(actual) - float(expected)) < 1e-6
        except (TypeError, ValueError):
            return False
    return str(actual).strip().lower() == str(expected).strip().lower()


def check_response(
    expect: Dict[str, Any],
    http_status: int,
    body: Optional[Dict[str, Any]],
    check_rows: bool = True,
) -> List[str]:
    """Return a list of human-readable failures (empty means the check passed)."""
    failures: List[str] = []

    if not isinstance(body, dict):
        return [f"response was not a JSON object (HTTP {http_status})"]

    wanted_statuses = _expected_statuses(expect)
    status = body.get("status")
    expecting_success = bool(wanted_statuses & SUCCESS_STATUSES)

    if expecting_success and http_status != 200:
        failures.append(f"expected HTTP 200, got {http_status}: {body.get('error') or body.get('details')}")
        return failures

    if status not in wanted_statuses:
        detail = body.get("error") or body.get("error_message") or ""
        failures.append(
            f"expected status {sorted(wanted_statuses)}, got '{status}' (HTTP {http_status}) {detail}".rstrip()
        )
        return failures

    if not expecting_success:
        if http_status in INFRA_HTTP_STATUSES:
            # An outage/throttle is not evidence the pipeline refused safely.
            failures.append(f"infrastructure error (HTTP {http_status}), not a real verdict")
            return failures
        if status == "needs_clarification" and not body.get("clarification_questions"):
            failures.append("needs_clarification returned no clarification_questions")
        # A refusal must never come with SQL that ran.
        if status != "success" and body.get("result", {}).get("rows"):
            failures.append("a non-success response still returned rows")
        wanted_action = expect.get("preview_action")
        if wanted_action and (body.get("preview") or {}).get("action") != wanted_action:
            failures.append(f"expected a {wanted_action} preview, got {body.get('preview')!r}")
        return failures

    sql = body.get("sql")
    sql_norm = normalize_sql(sql)
    if not sql_norm.startswith("select"):
        failures.append(f"expected a SELECT statement, got: {sql!r}")
        return failures

    for fragment in expect.get("sql_all", []):
        if fragment.lower() not in sql_norm:
            failures.append(f"SQL missing '{fragment}'")
    any_of = expect.get("sql_any", [])
    if any_of and not any(fragment.lower() in sql_norm for fragment in any_of):
        failures.append(f"SQL contains none of {any_of}")
    for fragment in expect.get("sql_none", []):
        if fragment.lower() in sql_norm:
            failures.append(f"SQL must not contain '{fragment}'")

    if not check_rows:
        return failures

    rows = (body.get("result") or {}).get("rows") or []
    rows_spec = expect.get("rows", "nonempty")
    if rows_spec == "nonempty" and not rows:
        failures.append("expected non-empty results, got 0 rows")
    elif isinstance(rows_spec, dict):
        if "count" in rows_spec and len(rows) != rows_spec["count"]:
            failures.append(f"expected {rows_spec['count']} rows, got {len(rows)}")
        if "min" in rows_spec and len(rows) < rows_spec["min"]:
            failures.append(f"expected at least {rows_spec['min']} rows, got {len(rows)}")
        if "max" in rows_spec and len(rows) > rows_spec["max"]:
            failures.append(f"expected at most {rows_spec['max']} rows, got {len(rows)}")
    # rows_spec == "any" -> no row constraint

    first_row_spec = expect.get("first_row")
    if first_row_spec and rows:
        first = rows[0]
        for column, expected in first_row_spec.items():
            matches = [key for key in first if column.lower() in key.lower()]
            if not matches:
                failures.append(f"first row has no column like '{column}' (columns: {list(first)})")
            elif not _values_equal(first[matches[0]], expected):
                failures.append(f"first row {matches[0]}={first[matches[0]]!r}, expected {expected!r}")
    elif first_row_spec and not rows:
        failures.append("first_row expectation but no rows returned")

    return failures


# ---------------------------------------------------------------------- #
# Runners
# ---------------------------------------------------------------------- #

@dataclass
class RunResult:
    question_id: str
    run: int
    passed: bool
    failures: List[str] = field(default_factory=list)
    infra_error: bool = False
    seconds: float = 0.0
    sql: Optional[str] = None
    status: Optional[str] = None


def post_query(base_url: str, question: str, timeout: float = 90.0, retries: int = 3):
    """POST /query, retrying throttling/cold-start responses. Returns (http_status, body)."""
    payload = json.dumps({"question": question}).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/query",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    last = (0, {"status": "error", "error": "no response"})
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            try:
                body = json.loads(exc.read().decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                body = {"status": "error", "error": f"HTTP {exc.code}"}
            last = (exc.code, body)
            if exc.code not in (429, 502, 503, 504) or attempt == retries:
                return last
            wait = float(body.get("retry_after") or 2 ** (attempt + 1))
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = (0, {"status": "error", "error": f"could not reach backend: {exc}"})
            if attempt == retries:
                return last
            wait = 2 ** (attempt + 1)
        time.sleep(min(wait, 15.0))
    return last


def build_offline_runner():
    """Run the real LLM + converter + generator against the in-memory schema."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import app.main as main_module
    from testing.test_phase4 import build_mock_schema

    class _Introspector:
        def __init__(self, db):
            pass

        def introspect(self):
            return build_mock_schema()

    class _NoRowsDB:
        def execute_query(self, query, params=None):
            return []

    main_module.SchemaIntrospector = _Introspector
    db = _NoRowsDB()

    def run(question: str):
        request = main_module.QueryRequest(question=question)
        response = main_module._run_pipeline(question, request, db)
        if hasattr(response, "status_code"):
            return response.status_code, json.loads(response.body)
        return 200, response

    return run


def is_infra_failure(http_status: int, body: Dict[str, Any]) -> bool:
    """Throttling / outage / unreachable: not a verdict on the pipeline's logic."""
    return http_status in INFRA_HTTP_STATUSES


def load_questions(path: Path = QUESTIONS_PATH) -> List[Dict[str, Any]]:
    with open(path, encoding="utf-8") as handle:
        questions = json.load(handle)
    seen = set()
    for item in questions:
        if item["id"] in seen:
            raise ValueError(f"duplicate question id: {item['id']}")
        seen.add(item["id"])
        item.setdefault("tier", "core")
        item.setdefault("expect", {})
    return questions


def evaluate(
    questions: List[Dict[str, Any]],
    send,
    runs: int = 1,
    delay: float = 1.0,
    check_rows: bool = True,
    verbose: bool = True,
) -> List[RunResult]:
    results: List[RunResult] = []
    for item in questions:
        for run in range(1, runs + 1):
            started = time.time()
            http_status, body = send(item["question"])
            elapsed = time.time() - started
            infra = is_infra_failure(http_status, body or {})
            failures = check_response(item["expect"], http_status, body, check_rows=check_rows)
            result = RunResult(
                question_id=item["id"],
                run=run,
                passed=not failures,
                failures=failures,
                infra_error=infra and bool(failures),
                seconds=elapsed,
                sql=(body or {}).get("sql") if isinstance(body, dict) else None,
                status=(body or {}).get("status") if isinstance(body, dict) else None,
            )
            results.append(result)
            if verbose:
                mark = "PASS" if result.passed else ("INFRA" if result.infra_error else "FAIL")
                label = f"[{mark}] [{item['tier']}] {item['id']}"
                if runs > 1:
                    label += f" (run {run}/{runs})"
                print(f"{label}  {elapsed:.1f}s")
                for failure in failures:
                    print(f"        - {failure}")
            time.sleep(delay)
    return results


def summarize(questions: List[Dict[str, Any]], results: List[RunResult]) -> Dict[str, Any]:
    tiers: Dict[str, Dict[str, int]] = {}
    tier_of = {q["id"]: q["tier"] for q in questions}
    for result in results:
        bucket = tiers.setdefault(tier_of[result.question_id], {"runs": 0, "passed": 0, "infra": 0})
        bucket["runs"] += 1
        bucket["passed"] += int(result.passed)
        bucket["infra"] += int(result.infra_error)
    core_failures = [r for r in results if tier_of[r.question_id] == "core" and not r.passed]
    return {"tiers": tiers, "core_failed": len(core_failures)}


def print_summary(questions, results, summary) -> None:
    print("\n" + "=" * 70)
    print("EVAL SUMMARY (measured, not estimated)")
    print("=" * 70)
    for tier, bucket in sorted(summary["tiers"].items()):
        rate = 100.0 * bucket["passed"] / bucket["runs"] if bucket["runs"] else 0.0
        infra = f", {bucket['infra']} infra" if bucket["infra"] else ""
        print(f"{tier:>10}: {bucket['passed']}/{bucket['runs']} passed ({rate:.0f}%){infra}")

    per_question: Dict[str, List[bool]] = {}
    for result in results:
        per_question.setdefault(result.question_id, []).append(result.passed)
    flaky = {qid: p for qid, p in per_question.items() if any(p) and not all(p)}
    if flaky:
        print("\nFlaky (passed some runs, failed others):")
        for qid, outcomes in flaky.items():
            print(f"  {qid}: {sum(outcomes)}/{len(outcomes)}")

    tier_of = {q["id"]: q["tier"] for q in questions}
    failing_core = sorted({r.question_id for r in results if tier_of[r.question_id] == "core" and not r.passed})
    if failing_core:
        print("\nCORE FAILURES:")
        for qid in failing_core:
            print(f"  - {qid}")
    else:
        print("\nAll core questions passed.")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="QueryMind eval harness")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--offline", action="store_true",
                        help="Run the pipeline in-process against the in-memory schema (no DB; row checks skipped)")
    parser.add_argument("--only", action="append", help="Run only these question ids (repeatable)")
    parser.add_argument("--runs", type=int, default=1, help="Repeat each question N times")
    parser.add_argument("--delay", type=float, default=1.0, help="Seconds between requests")
    parser.add_argument("--json", dest="json_out", help="Write detailed results to this file")
    args = parser.parse_args(argv)

    questions = load_questions()
    if args.only:
        wanted = set(args.only)
        unknown = wanted - {q["id"] for q in questions}
        if unknown:
            print(f"Unknown question ids: {sorted(unknown)}", file=sys.stderr)
            return 2
        questions = [q for q in questions if q["id"] in wanted]

    if args.offline:
        send = build_offline_runner()
        target = "offline (in-process, in-memory schema)"
    else:
        def send(question):
            return post_query(args.base_url, question)
        target = args.base_url
    print(f"Evaluating {len(questions)} question(s) x {args.runs} run(s) against {target}\n")

    results = evaluate(questions, send, runs=args.runs, delay=args.delay, check_rows=not args.offline)
    summary = summarize(questions, results)
    print_summary(questions, results, summary)

    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(
                {
                    "target": target,
                    "summary": summary,
                    "results": [r.__dict__ for r in results],
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    return 1 if summary["core_failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
