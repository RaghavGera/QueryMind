"""Sign in with Google, sessions, and daily usage limits (no network, no real Google)."""

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.auth as auth
import app.main as main_module
from app.accounts import User
from app.database import get_db

CLIENT_ID = "test-client.apps.googleusercontent.com"
ORIGIN = "https://query-mind-tawny.vercel.app"


@pytest.fixture(autouse=True)
def auth_env(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", CLIENT_ID)
    monkeypatch.setenv("SESSION_SECRET", "s" * 48)
    monkeypatch.delenv("QUERYMIND_SERVICE_KEY", raising=False)
    monkeypatch.delenv("DAILY_QUESTION_LIMIT", raising=False)
    monkeypatch.delenv("ANON_DAILY_QUESTION_LIMIT", raising=False)


# --------------------------------------------------------------------------- #
# Google ID tokens
# --------------------------------------------------------------------------- #

@pytest.fixture
def google_key(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(auth, "_google_signing_key", lambda token: key.public_key())
    return key


def _google_token(key, **overrides):
    now = datetime.now(timezone.utc)
    claims = {
        "iss": "https://accounts.google.com", "aud": CLIENT_ID, "sub": "1234567890",
        "email": "ada@example.com", "email_verified": True, "name": "Ada", "picture": "https://x/y.png",
        "iat": now, "exp": now + timedelta(hours=1),
    }
    claims.update(overrides)
    return jwt.encode({k: v for k, v in claims.items() if v is not None}, key, algorithm="RS256")


def test_a_valid_google_token_is_accepted(google_key):
    claims = auth.verify_google_id_token(_google_token(google_key))
    assert claims["sub"] == "1234567890" and claims["email"] == "ada@example.com"


@pytest.mark.parametrize("overrides, reason", [
    ({"aud": "someone-else.apps.googleusercontent.com"}, "another app's token"),
    ({"iss": "https://evil.example.com"}, "not issued by Google"),
    ({"exp": datetime.now(timezone.utc) - timedelta(minutes=5)}, "expired"),
    ({"email_verified": False}, "unverified email"),
    ({"email": None}, "no email"),
])
def test_bad_google_tokens_are_rejected(google_key, overrides, reason):
    with pytest.raises(auth.AuthError):
        auth.verify_google_id_token(_google_token(google_key, **overrides))


def test_a_token_signed_by_another_key_is_rejected(google_key):
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(auth.AuthError):
        auth.verify_google_id_token(_google_token(other))


def test_sign_in_is_refused_when_not_configured(google_key, monkeypatch):
    monkeypatch.delenv("GOOGLE_CLIENT_ID")
    with pytest.raises(auth.AuthError) as info:
        auth.verify_google_id_token(_google_token(google_key))
    assert info.value.status == 503


# --------------------------------------------------------------------------- #
# Session tokens, IPs, service key
# --------------------------------------------------------------------------- #

def test_session_tokens_round_trip_and_reject_tampering(monkeypatch):
    expires = datetime.now(timezone.utc) + timedelta(days=7)
    token = auth.issue_session_token("sid-1", 42, expires)
    assert auth.read_session_token(token) == "sid-1"
    with pytest.raises(auth.AuthError):
        auth.read_session_token(token[:-2] + ("AA" if token[-2:] != "AA" else "BB"))
    monkeypatch.setenv("SESSION_SECRET", "t" * 48)
    with pytest.raises(auth.AuthError):
        auth.read_session_token(token)  # signed with a different secret


def test_expired_session_tokens_are_rejected():
    token = auth.issue_session_token("sid-1", 42, datetime.now(timezone.utc) - timedelta(seconds=5))
    with pytest.raises(auth.AuthError, match="expired"):
        auth.read_session_token(token)


@pytest.mark.parametrize("header, expected", [
    ("Bearer abc.def", "abc.def"), ("bearer xyz", "xyz"), ("Basic abc", None), ("Bearer ", None), (None, None),
])
def test_bearer_token_parsing(header, expected):
    assert auth.bearer_token(header) == expected


def test_client_ip_ignores_forged_left_entries():
    # The client can send its own X-Forwarded-For; Render's proxy appends the real IP.
    assert auth.client_ip("6.6.6.6, 203.0.113.9", "10.0.0.1", trusted_hops=1) == "203.0.113.9"
    assert auth.client_ip(None, "10.0.0.1") == "10.0.0.1"


def test_anonymous_subject_never_contains_the_ip():
    subject = auth.anonymous_subject("203.0.113.9")
    assert subject.startswith("anon:") and "203.0.113.9" not in subject
    assert subject == auth.anonymous_subject("203.0.113.9")
    assert subject != auth.anonymous_subject("203.0.113.10")


def test_service_key_must_match_exactly(monkeypatch):
    assert not auth.service_key_matches("anything")  # no key configured: never matches
    monkeypatch.setenv("QUERYMIND_SERVICE_KEY", "k" * 32)
    assert auth.service_key_matches("k" * 32)
    assert not auth.service_key_matches("k" * 31)
    assert not auth.service_key_matches(None)


# --------------------------------------------------------------------------- #
# The HTTP layer: sign-in endpoints and the usage limits middleware
# --------------------------------------------------------------------------- #

class FakeStore:
    def __init__(self):
        self.users, self.sessions, self.usage, self.refunds = {}, {}, {}, 0
        self.tickets = {}

    def upsert_google_user(self, sub, email, name, picture):
        user = self.users.setdefault(sub, User(len(self.users) + 1, email, name, picture))
        return user

    def create_session(self, user_id):
        sid = f"sid-{len(self.sessions) + 1}"
        self.sessions[sid] = {"user_id": user_id, "revoked": False}
        return sid, datetime.now(timezone.utc) + timedelta(days=7)

    def session_user(self, sid):
        row = self.sessions.get(sid)
        if not row or row["revoked"]:
            return None
        return next(u for u in self.users.values() if u.id == row["user_id"])

    def revoke_session(self, sid):
        self.sessions[sid]["revoked"] = True

    def try_consume(self, subject, limit):
        if self.usage.get(subject, 0) >= limit:
            return None
        self.usage[subject] = self.usage.get(subject, 0) + 1
        return self.usage[subject]

    def refund(self, subject):
        self.refunds += 1
        self.usage[subject] = max(0, self.usage.get(subject, 0) - 1)

    def used_today(self, subject):
        return self.usage.get(subject, 0)

    def issue_ticket(self, subject):
        ticket = f"ticket-{len(self.tickets) + 1}"
        self.tickets[ticket] = {"subject": subject, "used": False}
        return ticket

    def redeem_ticket(self, ticket, subject):
        row = self.tickets.get(ticket)
        if not row or row["used"] or row["subject"] != subject:
            return False
        row["used"] = True
        return True

    def restore_ticket(self, ticket):
        self.tickets[ticket]["used"] = False


@pytest.fixture
def api(monkeypatch, google_key):
    store = FakeStore()
    monkeypatch.setattr(main_module, "_store", store)
    outcome = {"status": 200}

    def fake_pipeline(question, request, db):
        if outcome.get("clarify") and not request.clarification_context:
            return {"status": "needs_clarification", "clarification_questions": ["Ranked by what?"]}
        if outcome["status"] == 200:
            return {"status": "success", "sql": "SELECT 1", "params": [], "result": {"columns": [], "rows": []}}
        return main_module.JSONResponse(status_code=outcome["status"], content={"status": "error", "error": "model down"})

    monkeypatch.setattr(main_module, "_run_pipeline", fake_pipeline)
    main_module.app.dependency_overrides[get_db] = lambda: object()

    def call(method, path, headers=None, json=None):
        async def go():
            transport = httpx.ASGITransport(app=main_module.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://api.test") as client:
                return await client.request(method, path, headers={"Origin": ORIGIN, **(headers or {})}, json=json)
        return asyncio.run(go())

    def sign_in():
        body = call("POST", "/auth/google", json={"credential": _google_token(google_key)}).json()
        return {"Authorization": f"Bearer {body['token']}"}

    yield type("Api", (), {"call": staticmethod(call), "sign_in": staticmethod(sign_in), "store": store, "outcome": outcome})
    main_module.app.dependency_overrides.clear()


def _ask(api, headers=None):
    return api.call("POST", "/query", headers=headers, json={"question": "How many customers are there?"})


def test_sign_in_me_and_sign_out(api):
    headers = api.sign_in()
    me = api.call("GET", "/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["user"]["email"] == "ada@example.com"
    assert me.json()["usage"] == {**me.json()["usage"], "used": 0, "limit": 20, "scope": "user"}
    assert api.call("POST", "/auth/logout", headers=headers).status_code == 200
    assert api.call("GET", "/auth/me", headers=headers).status_code == 401


def test_a_half_configured_server_refuses_sign_in_without_writing(api, google_key, monkeypatch):
    monkeypatch.delenv("SESSION_SECRET")
    response = api.call("POST", "/auth/google", json={"credential": _google_token(google_key)})
    assert response.status_code == 503
    assert api.store.users == {} and api.store.sessions == {}


def test_anonymous_visitors_get_three_tries_then_a_sign_in_prompt(api):
    for n in (1, 2, 3):
        response = _ask(api)
        assert response.status_code == 200
        assert response.headers["x-usage-used"] == str(n) and response.headers["x-usage-limit"] == "3"
    blocked = _ask(api)
    assert blocked.status_code == 429
    assert blocked.json()["sign_in_required"] is True
    assert blocked.headers["access-control-allow-origin"] == ORIGIN, "the browser must be able to read the 429"


def test_signed_in_users_get_their_daily_limit(api, monkeypatch):
    monkeypatch.setenv("DAILY_QUESTION_LIMIT", "2")
    headers = api.sign_in()
    assert _ask(api, headers).status_code == 200
    assert _ask(api, headers).status_code == 200
    blocked = _ask(api, headers)
    assert blocked.status_code == 429
    assert "today's 2 questions" in blocked.json()["error"]
    assert blocked.json()["sign_in_required"] is False


def test_bad_or_revoked_sessions_are_refused(api):
    assert _ask(api, {"Authorization": "Bearer not-a-token"}).status_code == 401
    headers = api.sign_in()
    api.call("POST", "/auth/logout", headers=headers)
    refused = _ask(api, headers)
    assert refused.status_code == 401 and refused.json()["sign_in_required"] is True


def test_failures_on_our_side_give_the_question_back(api):
    headers = api.sign_in()
    api.outcome["status"] = 503
    assert _ask(api, headers).status_code == 503
    assert api.store.refunds == 1
    assert api.store.used_today("user:1") == 0


def test_the_service_key_bypasses_limits_without_counting(api, monkeypatch):
    monkeypatch.setenv("QUERYMIND_SERVICE_KEY", "k" * 32)
    monkeypatch.setenv("ANON_DAILY_QUESTION_LIMIT", "1")
    for _ in range(5):
        assert _ask(api, {"X-Service-Key": "k" * 32}).status_code == 200
    assert api.store.usage == {}


def test_confirming_a_write_requires_sign_in(api):
    refused = api.call("POST", "/query/confirm", json={"confirmation_token": "x"})
    assert refused.status_code == 401


def test_free_endpoints_stay_open(api):
    # Reading the schema or health spends no AI credits.
    assert api.call("POST", "/auth/logout").status_code == 200
    usage = api.call("GET", "/auth/usage").json()["usage"]
    assert usage["scope"] == "anonymous" and usage["limit"] == 3 and usage["used"] == 0


def _answer(api, ticket, headers=None):
    return api.call(
        "POST", "/query", headers={**(headers or {}), **({"X-Clarification-Ticket": ticket} if ticket else {})},
        json={"question": "Show me the top customers.", "clarification_context": "total spending"},
    )


def test_a_question_and_its_clarification_count_once(api, monkeypatch):
    monkeypatch.setenv("ANON_DAILY_QUESTION_LIMIT", "1")
    api.outcome["clarify"] = True
    asked = api.call("POST", "/query", json={"question": "Show me the top customers."})
    ticket = asked.json()["clarification_ticket"]
    assert asked.headers["X-Usage-Used"] == "1"
    answered = _answer(api, ticket)  # the only free question is used, yet the answer goes through
    assert answered.status_code == 200 and answered.json()["status"] == "success"
    assert answered.headers["X-Usage-Used"] == "1"
    assert _answer(api, ticket).status_code == 429  # single use


def test_tickets_do_not_chain_or_transfer(api, monkeypatch):
    monkeypatch.setenv("ANON_DAILY_QUESTION_LIMIT", "5")
    api.outcome["clarify"] = True
    ticket = api.call("POST", "/query", json={"question": "Show me the top customers."}).json()["clarification_ticket"]
    # Another caller (a signed-in user) can't spend the visitor's ticket: it's counted instead.
    headers = api.sign_in()
    assert _answer(api, ticket, headers).headers["X-Usage-Used"] == "1"
    # A free answer that needs clarifying again gets no new ticket.
    monkeypatch.setattr(api.store, "redeem_ticket", lambda t, s: True)
    again = api.call("POST", "/query", headers={"X-Clarification-Ticket": "any"}, json={"question": "Show me the top customers."})
    assert again.json()["status"] == "needs_clarification" and "clarification_ticket" not in again.json()


def test_a_failed_free_answer_keeps_its_ticket(api):
    api.outcome["clarify"] = True
    ticket = api.call("POST", "/query", json={"question": "Show me the top customers."}).json()["clarification_ticket"]
    api.outcome["status"] = 503
    assert _answer(api, ticket).status_code == 503
    api.outcome["status"] = 200
    assert _answer(api, ticket).headers["X-Usage-Used"] == "1"


# --------------------------------------------------------------------------- #
# The site's own button: Google access tokens
# --------------------------------------------------------------------------- #

@pytest.fixture
def google_api(monkeypatch):
    """Fake tokeninfo/userinfo. Edit ``replies`` to change what Google says."""
    replies = {
        "tokeninfo": {"aud": CLIENT_ID, "sub": "g-42", "expires_in": "3599"},
        "userinfo": {"sub": "g-42", "email": "grace@example.com", "email_verified": True, "name": "Grace", "picture": "https://p/g.png"},
    }
    calls = []

    def fake_google_json(url, headers=None):
        calls.append((url, headers))
        reply = replies["tokeninfo" if url.startswith(auth.GOOGLE_TOKENINFO_URL) else "userinfo"]
        if isinstance(reply, Exception):
            raise reply
        return reply

    monkeypatch.setattr(auth, "_google_json", fake_google_json)
    return replies, calls


def test_a_google_access_token_for_our_app_signs_in(google_api):
    replies, calls = google_api
    profile = auth.verify_google_access_token("ya29.token")
    assert profile == {"sub": "g-42", "email": "grace@example.com", "name": "Grace", "picture": "https://p/g.png"}
    assert calls[1][1] == {"Authorization": "Bearer ya29.token"}


@pytest.mark.parametrize("change, reason", [
    ({"tokeninfo": {"aud": "someone-elses-app", "sub": "g-42"}}, "another app"),
    ({"userinfo": {"sub": "g-other", "email": "x@example.com", "email_verified": True}}, "mismatch"),
    ({"userinfo": {"sub": "g-42", "email": "x@example.com", "email_verified": False}}, "not verified"),
])
def test_access_tokens_for_other_apps_or_unverified_emails_are_refused(google_api, change, reason):
    replies, _ = google_api
    replies.update(change)
    with pytest.raises(auth.AuthError, match=reason) as info:
        auth.verify_google_access_token("ya29.token")
    assert info.value.status == 401


def test_the_sign_in_endpoint_takes_an_access_token(api, google_api):
    body = api.call("POST", "/auth/google", json={"access_token": "ya29.token"}).json()
    assert body["user"]["email"] == "grace@example.com" and body["token"]
    assert api.call("POST", "/auth/google", json={}).status_code == 400


def test_bad_tokens_and_google_outages_get_honest_errors(monkeypatch):
    import io
    import urllib.error

    def raising(error):
        def urlopen(*args, **kwargs):
            raise error
        return urlopen

    bad = urllib.error.HTTPError(auth.GOOGLE_TOKENINFO_URL, 400, "Bad Request", {}, io.BytesIO(b"{}"))
    monkeypatch.setattr(auth.urllib.request, "urlopen", raising(bad))
    with pytest.raises(auth.AuthError) as info:
        auth.verify_google_access_token("expired")
    assert info.value.status == 401
    monkeypatch.setattr(auth.urllib.request, "urlopen", raising(urllib.error.URLError("no route")))
    with pytest.raises(auth.AuthError) as info:
        auth.verify_google_access_token("ya29.token")
    assert info.value.status == 503
