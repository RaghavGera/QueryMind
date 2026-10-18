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
