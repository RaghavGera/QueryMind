"""Query history and saved queries stored in the account (/me/*), through the API with a fake store."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.main as main_module
from app.accounts import HISTORY_LIMIT
from testing.test_auth import _google_token, api, auth_env, google_key  # noqa: F401  (pytest fixtures)


def _entry(i, question=None, resolved=None, rows=3, **extra):
    return {
        "id": f"q-{i}",
        "question": question or f"Question {i}",
        "resolved": resolved,
        "executedAt": f"2026-10-19T10:{i % 60:02d}:00.000Z",
        "status": "success",
        "durationMs": 1200,
        "snapshot": {"sql": "SELECT 1", "params": [], "columns": ["n"], "rows": [{"n": n} for n in range(rows)], "totalRows": rows, "warnings": []},
        **extra,
    }


def test_history_and_saved_need_a_session(api):
    for method, path in [("GET", "/me/history"), ("GET", "/me/saved"), ("DELETE", "/me/history/q-1")]:
        assert api.call(method, path).status_code == 401
    assert api.call("POST", "/me/history", json={"entry": _entry(1)}).status_code == 401
    assert api.call("POST", "/me/import", json={"history": [_entry(1)]}).status_code == 401


def test_history_is_stored_newest_first_and_can_be_deleted(api):
    headers = api.sign_in()
    for i in (1, 2):
        assert api.call("POST", "/me/history", headers=headers, json={"entry": _entry(i)}).status_code == 200
    api.call("POST", "/me/history", headers=headers, json={"entry": _entry(2)})  # the same id again: no duplicate
    entries = api.call("GET", "/me/history", headers=headers).json()["entries"]
    assert [e["id"] for e in entries] == ["q-2", "q-1"]
    assert entries[0]["snapshot"]["rows"] == [{"n": 0}, {"n": 1}, {"n": 2}], "the stored result comes back intact"
    api.call("DELETE", "/me/history/q-2", headers=headers)
    assert [e["id"] for e in api.call("GET", "/me/history", headers=headers).json()["entries"]] == ["q-1"]


def test_saving_the_same_query_again_replaces_it(api):
    headers = api.sign_in()
    api.call("PUT", "/me/saved", headers=headers, json={"entry": _entry(1, "Top products")})
    api.call("PUT", "/me/saved", headers=headers, json={"entry": _entry(2, "Top products")})
    api.call("PUT", "/me/saved", headers=headers, json={"entry": _entry(3, "Top products", resolved="by revenue")})
    saved = api.call("GET", "/me/saved", headers=headers).json()["entries"]
    assert sorted(e["id"] for e in saved) == ["q-2", "q-3"]
    api.call("DELETE", "/me/saved/q-2", headers=headers)
    assert [e["id"] for e in api.call("GET", "/me/saved", headers=headers).json()["entries"]] == ["q-3"]


def test_saved_queries_are_capped(api, monkeypatch):
    monkeypatch.setattr("testing.test_auth.SAVED_LIMIT", 2)
    monkeypatch.setattr(main_module, "SAVED_LIMIT", 2)
    headers = api.sign_in()
    for i in (1, 2):
        api.call("PUT", "/me/saved", headers=headers, json={"entry": _entry(i)})
    refused = api.call("PUT", "/me/saved", headers=headers, json={"entry": _entry(3)})
    assert refused.status_code == 409 and "2 saved queries" in refused.json()["error"]


def test_entries_without_a_question_or_with_too_many_rows_are_refused(api):
    headers = api.sign_in()
    for bad in [{"id": "q-1"}, _entry(1, question="   "), _entry(1, rows=201), {"id": 5, "question": "x"}, _entry(1, resolved=7)]:
        assert api.call("POST", "/me/history", headers=headers, json={"entry": bad}).status_code == 422
    assert api.call("GET", "/me/history", headers=headers).json()["entries"] == []


def test_oversized_requests_are_refused_before_reading(api, monkeypatch):
    monkeypatch.setattr(main_module, "MAX_ACCOUNT_BODY_BYTES", 500)
    headers = api.sign_in()
    big = _entry(1, rows=50)
    assert api.call("POST", "/me/history", headers=headers, json={"entry": big}).status_code == 413


def test_import_moves_browser_entries_in_and_skips_bad_ones(api):
    headers = api.sign_in()
    api.call("PUT", "/me/saved", headers=headers, json={"entry": _entry(9, "Already saved")})
    body = {
        "history": [_entry(2), _entry(1), {"id": "broken"}],
        "saved": [_entry(5, "Already saved"), _entry(6, "New one")],
    }
    result = api.call("POST", "/me/import", headers=headers, json=body).json()
    assert result == {"imported": {"history": 2, "saved": 1}, "skipped": 1}
    assert [e["id"] for e in api.call("GET", "/me/history", headers=headers).json()["entries"]] == ["q-2", "q-1"]
    assert sorted(e["id"] for e in api.call("GET", "/me/saved", headers=headers).json()["entries"]) == ["q-6", "q-9"]
    again = api.call("POST", "/me/import", headers=headers, json=body).json()
    assert again["imported"] == {"history": 0, "saved": 0}, "importing twice adds nothing"


def test_history_keeps_the_newest_entries_only(api):
    headers = api.sign_in()
    for i in range(HISTORY_LIMIT + 5):
        api.call("POST", "/me/history", headers=headers, json={"entry": _entry(i)})
    entries = api.call("GET", "/me/history", headers=headers).json()["entries"]
    assert len(entries) == HISTORY_LIMIT and entries[0]["id"] == f"q-{HISTORY_LIMIT + 4}"


def test_accounts_never_see_each_others_entries(api, google_key):
    ada = api.sign_in()
    api.call("POST", "/me/history", headers=ada, json={"entry": _entry(1, "Ada's question")})
    api.call("PUT", "/me/saved", headers=ada, json={"entry": _entry(2, "Ada's saved")})
    token = api.call("POST", "/auth/google", json={"credential": _google_token(google_key, sub="999", email="bob@example.com")}).json()["token"]
    bob = {"Authorization": f"Bearer {token}"}
    assert api.call("GET", "/me/history", headers=bob).json()["entries"] == []
    assert api.call("GET", "/me/saved", headers=bob).json()["entries"] == []
    api.call("DELETE", "/me/history/q-1", headers=bob)  # someone else's id: nothing happens
    assert len(api.call("GET", "/me/history", headers=ada).json()["entries"]) == 1
