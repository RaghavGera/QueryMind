"""Unit tests for the eval harness's pure checking logic and question file."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from testing.eval_harness import check_response, load_questions, normalize_sql, summarize, RunResult

OK_BODY = {
    "status": "success",
    "sql": 'SELECT COUNT("customers"."customer_id") AS "c"\nFROM "customers"',
    "result": {"columns": ["c"], "rows": [{"c": 500}]},
}


def test_question_file_is_valid():
    questions = load_questions()
    ids = [q["id"] for q in questions]
    assert len(ids) == len(set(ids))
    assert len(questions) >= 30
    assert {q["tier"] for q in questions} <= {"core", "known_gap"}
    assert all(q["question"].strip() for q in questions)


def test_normalize_sql_strips_quotes_and_whitespace():
    assert normalize_sql('SELECT  "a"."b"\nFROM "a"') == "select a.b from a"


def test_passing_response():
    expect = {"sql_all": ["count(", "from customers"], "rows": {"count": 1}, "first_row": {"c": 500}}
    assert check_response(expect, 200, OK_BODY) == []


def test_wrong_http_status_fails():
    failures = check_response({}, 500, {"status": "error", "error": "boom"})
    assert failures and "HTTP 200" in failures[0]


def test_unexpected_clarification_fails():
    body = {"status": "needs_clarification", "clarification_questions": ["what?"], "result": {"rows": []}}
    assert check_response({}, 200, body)


def test_expected_clarification_passes_only_with_questions():
    expect = {"status": "needs_clarification"}
    good = {"status": "needs_clarification", "clarification_questions": ["which?"], "result": {"rows": []}}
    bad = {"status": "needs_clarification", "clarification_questions": [], "result": {"rows": []}}
    assert check_response(expect, 200, good) == []
    assert check_response(expect, 200, bad)


def test_missing_sql_fragment_and_forbidden_fragment():
    assert check_response({"sql_all": ["group by"]}, 200, OK_BODY)
    assert check_response({"sql_none": ["customers"]}, 200, OK_BODY)
    assert check_response({"sql_any": ["avg(", "sum("]}, 200, OK_BODY)


def test_row_expectations():
    empty = dict(OK_BODY, result={"columns": [], "rows": []})
    assert check_response({"rows": "nonempty"}, 200, empty)
    assert check_response({"rows": "any"}, 200, empty) == []
    assert check_response({"rows": {"count": 2}}, 200, OK_BODY)
    assert check_response({"rows": {"min": 1, "max": 1}}, 200, OK_BODY) == []


def test_rows_not_checked_in_offline_mode():
    empty = dict(OK_BODY, result={"columns": [], "rows": []})
    assert check_response({"rows": "nonempty", "first_row": {"c": 1}}, 200, empty, check_rows=False) == []


def test_first_row_value_mismatch():
    assert check_response({"first_row": {"c": 499}}, 200, OK_BODY)


def test_non_select_sql_is_rejected():
    body = dict(OK_BODY, sql="DELETE FROM customers")
    assert check_response({}, 200, body)


def test_refusal_must_not_be_an_outage():
    expect = {"status": ["blocked", "needs_clarification", "error"]}
    outage = {"status": "error", "error": "rate limited", "result": {"rows": []}}
    assert check_response(expect, 429, outage)  # throttling is not a safe refusal
    blocked = {"status": "blocked", "clarification_questions": ["no"], "result": {"rows": []}}
    assert check_response(expect, 200, blocked) == []


def test_refusal_that_returns_rows_fails():
    expect = {"status": ["blocked", "error"]}
    body = {"status": "error", "result": {"rows": [{"x": 1}]}}
    assert check_response(expect, 200, body)


def test_summary_only_counts_core_failures_toward_exit_code():
    questions = [
        {"id": "a", "tier": "core"},
        {"id": "b", "tier": "known_gap"},
    ]
    results = [
        RunResult("a", 1, True),
        RunResult("b", 1, False, failures=["x"]),
    ]
    assert summarize(questions, results)["core_failed"] == 0
    results[0] = RunResult("a", 1, False, failures=["x"])
    assert summarize(questions, results)["core_failed"] == 1
