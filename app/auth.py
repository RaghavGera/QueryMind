"""
Sign in with Google, session tokens, and who is calling.

Flow: the browser gets a token from Google Identity Services and POSTs it to
/auth/google. The site's own button uses Google's token popup, which yields an
access token: we ask Google who it was issued to (must be our client id) and
whose it is (verified email). A Google ID token is also accepted, verified
against Google's published keys (signature, audience, issuer, expiry,
verified email). Either way we store the user and return our own session token (HS256, signed with
SESSION_SECRET, 7 days). Every later request sends it as
``Authorization: Bearer <token>``; the session row can be revoked (sign-out).
"""

import hashlib
import hmac
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import jwt

GOOGLE_CERTS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = ("accounts.google.com", "https://accounts.google.com")
GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
SESSION_ALGORITHM = "HS256"
SESSION_ISSUER = "querymind"


class AuthError(Exception):
    """A sign-in or session problem; ``status`` is the HTTP code to answer with."""

    def __init__(self, message: str, status: int = 401):
        super().__init__(message)
        self.status = status


def google_client_id() -> str:
    return (os.getenv("GOOGLE_CLIENT_ID") or "").strip()


def session_secret() -> str:
    return (os.getenv("SESSION_SECRET") or "").strip()


def auth_configured() -> bool:
    return bool(google_client_id() and session_secret())


_jwks_client: Optional[jwt.PyJWKClient] = None


def _google_signing_key(token: str):
    """Google's public key for this token (fetched once, cached, refreshed on rotation)."""
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = jwt.PyJWKClient(GOOGLE_CERTS_URL, cache_keys=True, lifespan=6 * 3600, timeout=10)
    return _jwks_client.get_signing_key_from_jwt(token).key


def verify_google_id_token(token: str) -> dict:
    """Return the verified claims of a Google ID token, or raise AuthError."""
    client_id = google_client_id()
    if not client_id:
        raise AuthError("Sign-in is not configured on this server.", status=503)
    try:
        claims = jwt.decode(
            token,
            _google_signing_key(token),
            algorithms=["RS256"],
            audience=client_id,
            issuer=GOOGLE_ISSUERS,
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            leeway=30,
        )
    except jwt.PyJWKClientError as exc:
        raise AuthError("Could not reach Google to verify the sign-in. Please try again.", status=503) from exc
    except jwt.InvalidTokenError as exc:
        raise AuthError(f"Google sign-in could not be verified ({type(exc).__name__}).") from exc
    if claims.get("email_verified") is not True or not claims.get("email"):
        raise AuthError("Your Google account's email address is not verified.")
    return claims


def _google_json(url: str, headers: Optional[dict] = None) -> dict:
    """GET a Google endpoint. 4xx means a bad token (401); anything else, Google is unreachable (503)."""
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers or {}), timeout=10) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        if 400 <= exc.code < 500:
            raise AuthError("Google sign-in could not be verified (invalid or expired token).") from exc
        raise AuthError("Could not reach Google to verify the sign-in. Please try again.", status=503) from exc
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise AuthError("Could not reach Google to verify the sign-in. Please try again.", status=503) from exc


def verify_google_access_token(token: str) -> dict:
    """
    Return ``{sub, email, name, picture}`` for a Google access token that was
    issued to our client id, or raise AuthError. Checking the audience matters:
    without it, a token any other app obtained for the user would sign them in.
    """
    client_id = google_client_id()
    if not client_id:
        raise AuthError("Sign-in is not configured on this server.", status=503)
    info = _google_json(f"{GOOGLE_TOKENINFO_URL}?{urllib.parse.urlencode({'access_token': token})}")
    if info.get("aud") != client_id:
        raise AuthError("Google sign-in could not be verified (token issued to another app).")
    profile = _google_json(GOOGLE_USERINFO_URL, {"Authorization": f"Bearer {token}"})
    if not profile.get("sub") or profile.get("sub") != info.get("sub"):
        raise AuthError("Google sign-in could not be verified (account mismatch).")
    if profile.get("email_verified") is not True or not profile.get("email"):
        raise AuthError("Your Google account's email address is not verified.")
    return {key: profile.get(key) for key in ("sub", "email", "name", "picture")}


def issue_session_token(session_id: str, user_id: int, expires_at: datetime) -> str:
    secret = session_secret()
    if not secret:
        raise AuthError("Sign-in is not configured on this server.", status=503)
    now = datetime.now(timezone.utc)
    payload = {"sid": session_id, "sub": str(user_id), "iss": SESSION_ISSUER, "iat": now, "exp": expires_at}
    return jwt.encode(payload, secret, algorithm=SESSION_ALGORITHM)


def read_session_token(token: str) -> str:
    """The session id inside a valid session token (the DB still decides if it's live)."""
    secret = session_secret()
    if not secret:
        raise AuthError("Sign-in is not configured on this server.", status=503)
    try:
        claims = jwt.decode(
            token, secret, algorithms=[SESSION_ALGORITHM], issuer=SESSION_ISSUER,
            options={"require": ["exp", "iat", "sub", "sid"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("Your session has expired. Please sign in again.") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthError("Your session is not valid. Please sign in again.") from exc
    return claims["sid"]


def bearer_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    scheme, _, value = authorization.partition(" ")
    return value.strip() if scheme.lower() == "bearer" and value.strip() else None


def service_key_matches(provided: Optional[str]) -> bool:
    """The eval harness's key (QUERYMIND_SERVICE_KEY): bypasses sign-in and limits."""
    expected = (os.getenv("QUERYMIND_SERVICE_KEY") or "").strip()
    return bool(expected and provided) and hmac.compare_digest(expected, provided.strip())


def client_ip(
    forwarded_for: Optional[str], peer: Optional[str], trusted_hops: int = 1, header_ip: Optional[str] = None
) -> str:
    """
    The caller's IP. ``header_ip`` is the value of CLIENT_IP_HEADER, a header
    the proxy in front sets itself (so a client can't forge it); it wins when
    present. Otherwise the client is the entry ``trusted_hops`` from the right
    of X-Forwarded-For (entries further left are client-supplied and can be
    forged).
    """
    if header_ip and header_ip.strip():
        return header_ip.strip()
    parts = [p.strip() for p in (forwarded_for or "").split(",") if p.strip()]
    if parts and trusted_hops > 0:
        return parts[-min(trusted_hops, len(parts))]
    return peer or "unknown"


def anonymous_subject(ip: str) -> str:
    """Usage key for a signed-out visitor: a keyed hash, so raw IPs are never stored."""
    key = (session_secret() or "querymind-dev").encode()
    return "anon:" + hmac.new(key, ip.encode(), hashlib.sha256).hexdigest()[:32]


@dataclass(frozen=True)
class Principal:
    """Who is calling: a signed-in user, an anonymous visitor, or the service key."""

    kind: str  # "user" | "anonymous" | "service"
    subject: str  # usage key
    user: object = None  # accounts.User for a session (kind "user", or "service" sent with one)
    session_id: Optional[str] = None
