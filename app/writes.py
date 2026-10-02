"""
Confirmed natural-language writes (INSERT / UPDATE).

Writes are never executed by ``POST /query``. The pipeline instead returns a
preview and a confirmation token, and the caller must explicitly
``POST /query/confirm`` with that token. The token is:

  * bound to the exact SQL and parameters the user was shown (HMAC-signed, so
    it cannot be edited or forged),
  * short-lived (``TOKEN_TTL_SECONDS``), and
  * single-use (best effort: the used-token set is in memory, so a restart
    forgets it -- the TTL bounds that window).

Execution is additionally gated by ``QUERYMIND_ENABLE_WRITES`` (default off)
so a public demo database cannot be modified by visitors unless the owner opts
in. ``QUERYMIND_CONFIRM_SECRET`` should be set in production so tokens stay
valid across restarts and instances; without it a random per-process secret is
used (tokens then only validate on the instance that issued them).
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from typing import Any, Dict, List, Optional

TOKEN_TTL_SECONDS = 300
_TOKEN_VERSION = 1

_process_secret = secrets.token_bytes(32)
_used_nonces: Dict[str, float] = {}
_lock = threading.Lock()


class ConfirmationError(Exception):
    """The confirmation token is invalid, expired, or already used."""


def writes_enabled() -> bool:
    return os.getenv("QUERYMIND_ENABLE_WRITES", "").strip().lower() in {"1", "true", "yes", "on"}


def _secret() -> bytes:
    configured = os.getenv("QUERYMIND_CONFIRM_SECRET")
    return configured.encode("utf-8") if configured else _process_secret


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(body: bytes) -> bytes:
    return hmac.new(_secret(), body, hashlib.sha256).digest()


def issue_token(
    sql: str,
    params: List[Any],
    expected_rows: Optional[int] = None,
    now: Optional[float] = None,
) -> str:
    """Create a signed token authorizing exactly this statement once."""
    issued = time.time() if now is None else now
    payload = {
        "v": _TOKEN_VERSION,
        "sql": sql,
        "params": params,
        "expected_rows": expected_rows,
        "exp": issued + TOKEN_TTL_SECONDS,
        "nonce": secrets.token_hex(8),
    }
    body = json.dumps(payload, separators=(",", ":"), default=str).encode("utf-8")
    return f"{_b64(body)}.{_b64(_sign(body))}"


def redeem_token(token: str, now: Optional[float] = None) -> Dict[str, Any]:
    """
    Verify a token and mark it used. Returns the authorized statement
    (``sql``, ``params``, ``expected_rows``) or raises ConfirmationError.
    """
    current = time.time() if now is None else now
    try:
        encoded_body, encoded_sig = token.split(".", 1)
        body = _unb64(encoded_body)
        signature = _unb64(encoded_sig)
    except (ValueError, AttributeError):
        raise ConfirmationError("Malformed confirmation token.")

    if not hmac.compare_digest(signature, _sign(body)):
        raise ConfirmationError("Invalid confirmation token.")

    try:
        payload = json.loads(body)
    except ValueError:
        raise ConfirmationError("Malformed confirmation token.")

    if payload.get("v") != _TOKEN_VERSION:
        raise ConfirmationError("Unsupported confirmation token.")
    if current > float(payload["exp"]):
        raise ConfirmationError("Confirmation expired. Please ask the question again.")

    with _lock:
        for nonce, expiry in list(_used_nonces.items()):
            if expiry < current:
                del _used_nonces[nonce]
        if payload["nonce"] in _used_nonces:
            raise ConfirmationError("This confirmation was already used.")
        _used_nonces[payload["nonce"]] = float(payload["exp"])

    return {
        "sql": payload["sql"],
        "params": payload["params"],
        "expected_rows": payload.get("expected_rows"),
    }


def describe_write(intent, affected_rows: Optional[int] = None) -> Dict[str, Any]:
    """Human-readable summary of a pending write, shown before confirmation."""
    table = intent.tables[0]
    if intent.query_type.value == "INSERT":
        return {
            "action": "insert",
            "table": table,
            "values": dict(intent.insert_values or {}),
            "summary": f"Insert 1 new row into {table}.",
        }

    where = [
        {"column": c.column, "operator": c.operator.value, "value": c.value}
        for c in intent.conditions
    ]
    summary = f"Update {table}"
    if affected_rows is not None:
        summary += f": {affected_rows} row(s) will be changed."
    return {
        "action": "update",
        "table": table,
        "set": dict(intent.update_values or {}),
        "where": where,
        "affected_rows": affected_rows,
        "summary": summary,
    }
