"""AccountStore SQL against a real PostgreSQL (skipped without a database)."""

import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.accounts import AccountStore


@pytest.fixture
def store(db):
    s = AccountStore(db)
    s.ensure_schema()
    s.ensure_schema()  # idempotent
    tag = f"test-{uuid.uuid4().hex[:10]}"
    yield s, tag
    with db.get_connection() as conn:
        conn.execute("DELETE FROM querymind_meta.users WHERE google_sub LIKE %s", (f"{tag}%",))
        conn.execute("DELETE FROM querymind_meta.usage WHERE subject LIKE %s", (f"{tag}%",))
        conn.execute("DELETE FROM querymind_meta.clarification_tickets WHERE subject LIKE %s", (f"{tag}%",))


def test_upsert_keeps_one_user_per_google_account(store):
    s, tag = store
    first = s.upsert_google_user(f"{tag}-sub", "old@example.com", "Ada", None)
    again = s.upsert_google_user(f"{tag}-sub", "new@example.com", "Ada L.", "https://x/p.png")
    assert again.id == first.id
    assert again.email == "new@example.com" and again.picture == "https://x/p.png"


def test_sessions_live_until_revoked(store, db):
    s, tag = store
    user = s.upsert_google_user(f"{tag}-sub", "ada@example.com", None, None)
    sid, _ = s.create_session(user.id)
    assert s.session_user(sid).id == user.id
    s.revoke_session(sid)
    assert s.session_user(sid) is None
    sid2, _ = s.create_session(user.id)
    with db.get_connection() as conn:
        conn.execute("UPDATE querymind_meta.sessions SET expires_at = now() - interval '1 second' WHERE id = %s", (sid2,))
    assert s.session_user(sid2) is None, "expired sessions are not live"
    assert s.session_user("no-such-session") is None


def test_the_limit_is_exact_and_refunds_work(store):
    s, tag = store
    subject = f"{tag}:user"
    assert [s.try_consume(subject, 3) for _ in range(4)] == [1, 2, 3, None]
    assert s.used_today(subject) == 3
    s.refund(subject)
    assert s.used_today(subject) == 2
    assert s.try_consume(subject, 3) == 3


def test_concurrent_requests_cannot_exceed_the_limit(store):
    s, tag = store
    subject = f"{tag}:race"
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: s.try_consume(subject, 5), range(20)))
    assert sorted(r for r in results if r is not None) == [1, 2, 3, 4, 5]
    assert results.count(None) == 15
    assert s.used_today(subject) == 5


def test_clarification_tickets_are_single_use_and_bound_to_their_caller(store, db):
    s, tag = store
    ticket = s.issue_ticket(f"{tag}:anon")
    assert not s.redeem_ticket(ticket, f"{tag}:someone-else")
    assert s.redeem_ticket(ticket, f"{tag}:anon")
    assert not s.redeem_ticket(ticket, f"{tag}:anon"), "single use"
    s.restore_ticket(ticket)
    assert s.redeem_ticket(ticket, f"{tag}:anon"), "usable again after a failure on our side"
    with db.get_connection() as conn:
        stored = conn.execute("SELECT token_hash FROM querymind_meta.clarification_tickets WHERE subject = %s", (f"{tag}:anon",)).fetchone()
        assert stored["token_hash"] != ticket, "only the hash is stored"
        late = s.issue_ticket(f"{tag}:anon")
        conn.execute("UPDATE querymind_meta.clarification_tickets SET expires_at = now() - interval '1 second' WHERE subject = %s AND used_at IS NULL", (f"{tag}:anon",))
    assert not s.redeem_ticket(late, f"{tag}:anon"), "expired"


def _entry(i, question=None, resolved=None, minute=None):
    return {
        "id": f"q-{i}", "question": question or f"Question {i}", "resolved": resolved,
        "executedAt": f"2026-10-19T10:{(i if minute is None else minute) % 60:02d}:00Z",
        "savedAt": f"2026-10-19T11:{i % 60:02d}:00Z",
        "snapshot": {"sql": "SELECT 1", "params": [5], "columns": ["n"], "rows": [{"n": 1.5}], "totalRows": 1, "warnings": []},
    }


def test_history_round_trips_and_keeps_the_newest(store):
    from app.accounts import HISTORY_LIMIT
    s, tag = store
    user = s.upsert_google_user(f"{tag}-sub", "ada@example.com", None, None)
    for i in range(HISTORY_LIMIT + 3):
        s.add_history(user.id, _entry(i))
    s.add_history(user.id, _entry(HISTORY_LIMIT + 2))  # same id again: no duplicate
    history = s.history(user.id)
    assert len(history) == HISTORY_LIMIT
    assert history[0]["id"] == f"q-{HISTORY_LIMIT + 2}" and history[-1]["id"] == "q-3"
    assert history[0]["snapshot"] == _entry(0)["snapshot"], "JSON comes back exactly as stored"
    s.delete_history(user.id, history[0]["id"])
    assert len(s.history(user.id)) == HISTORY_LIMIT - 1


def test_saved_queries_replace_by_question_and_clarification(store):
    s, tag = store
    user = s.upsert_google_user(f"{tag}-sub", "ada@example.com", None, None)
    other = s.upsert_google_user(f"{tag}-sub2", "bob@example.com", None, None)
    assert s.save_query(user.id, _entry(1, "Top products"))
    assert s.save_query(user.id, _entry(2, "Top products"))
    assert s.save_query(user.id, _entry(3, "Top products", resolved="by revenue"))
    assert s.save_query(other.id, _entry(1, "Top products")), "the same id in another account is separate"
    assert sorted(e["id"] for e in s.saved(user.id)) == ["q-2", "q-3"]
    assert [e["id"] for e in s.saved(other.id)] == ["q-1"]
    s.delete_saved(user.id, "q-3")
    assert [e["id"] for e in s.saved(user.id)] == ["q-2"]


def test_saved_limit_leaves_the_list_unchanged(store, monkeypatch):
    import app.accounts as accounts
    monkeypatch.setattr(accounts, "SAVED_LIMIT", 2)
    s, tag = store
    user = s.upsert_google_user(f"{tag}-sub", "ada@example.com", None, None)
    assert s.save_query(user.id, _entry(1)) and s.save_query(user.id, _entry(2))
    assert not s.save_query(user.id, _entry(3))
    assert s.save_query(user.id, _entry(4, "Question 1")), "replacing an existing one still works at the limit"
    assert sorted(e["id"] for e in s.saved(user.id)) == ["q-2", "q-4"]


def test_import_skips_what_the_account_already_has(store):
    s, tag = store
    user = s.upsert_google_user(f"{tag}-sub", "ada@example.com", None, None)
    s.add_history(user.id, _entry(1))
    s.save_query(user.id, _entry(5, "Already saved"))
    added = s.import_entries(user.id, [_entry(1), _entry(2)], [_entry(6, "Already saved"), _entry(7, "New")])
    assert added == {"history": 1, "saved": 1}
    assert [e["id"] for e in s.history(user.id)] == ["q-2", "q-1"]
    assert sorted(e["id"] for e in s.saved(user.id)) == ["q-5", "q-7"]


def test_a_tweaked_answer_is_saved_next_to_the_original(store):
    s, tag = store
    user = s.upsert_google_user(f"{tag}-sub", "ada@example.com", None, None)
    assert s.save_query(user.id, _entry(1, "Priciest category"))
    assert s.save_query(user.id, {**_entry(2, "Priciest category"), "adjusted": "MIN instead of MAX of price"})
    assert sorted(e["id"] for e in s.saved(user.id)) == ["q-1", "q-2"], "the tweak doesn't replace the original"
    assert s.save_query(user.id, {**_entry(3, "Priciest category"), "adjusted": "MIN instead of MAX of price"})
    assert sorted(e["id"] for e in s.saved(user.id)) == ["q-1", "q-3"], "the same tweak again replaces it"
