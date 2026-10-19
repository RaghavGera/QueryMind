"""
Accounts, sessions and daily usage, stored in the ``querymind_meta`` schema.

The schema introspector reads only ``public``, so none of these tables are
ever shown to the language model or the user's schema browser.
"""

import hashlib
import json
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from psycopg.types.json import Jsonb

logger = logging.getLogger(__name__)

SESSION_DAYS = 7
TICKET_MINUTES = 15
HISTORY_LIMIT = 50  # newest entries kept per account, as in the browser
SAVED_LIMIT = 100
MAX_ENTRY_BYTES = 1_000_000  # one entry with its result snapshot (200 rows at most)

DDL = """
CREATE SCHEMA IF NOT EXISTS querymind_meta;
CREATE TABLE IF NOT EXISTS querymind_meta.users (
    id            BIGSERIAL PRIMARY KEY,
    google_sub    TEXT UNIQUE NOT NULL,
    email         TEXT NOT NULL,
    name          TEXT,
    picture       TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS querymind_meta.sessions (
    id         TEXT PRIMARY KEY,
    user_id    BIGINT NOT NULL REFERENCES querymind_meta.users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS querymind_meta.usage (
    subject TEXT NOT NULL,      -- 'user:<id>' or 'anon:<keyed hash of the client IP>'
    day     DATE NOT NULL,      -- UTC
    count   INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (subject, day)
);
-- History and saved queries: the entry as the app shows it (question,
-- clarification, timing, and a snapshot of the SQL and up to 200 rows).
CREATE TABLE IF NOT EXISTS querymind_meta.query_history (
    user_id BIGINT NOT NULL REFERENCES querymind_meta.users(id) ON DELETE CASCADE,
    id      TEXT NOT NULL,
    at      TIMESTAMPTZ NOT NULL,
    entry   JSONB NOT NULL,
    PRIMARY KEY (user_id, id)
);
CREATE INDEX IF NOT EXISTS query_history_newest ON querymind_meta.query_history (user_id, at DESC);
CREATE TABLE IF NOT EXISTS querymind_meta.saved_queries (
    user_id  BIGINT NOT NULL REFERENCES querymind_meta.users(id) ON DELETE CASCADE,
    id       TEXT NOT NULL,
    question TEXT NOT NULL,
    resolved TEXT NOT NULL DEFAULT '',  -- the clarification answer; '' when there was none
    at       TIMESTAMPTZ NOT NULL,
    entry    JSONB NOT NULL,
    PRIMARY KEY (user_id, id),
    UNIQUE (user_id, question, resolved)
);
CREATE TABLE IF NOT EXISTS querymind_meta.clarification_tickets (
    token_hash TEXT PRIMARY KEY,  -- sha256 of the ticket; the ticket itself is never stored
    subject    TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at    TIMESTAMPTZ
);
"""


@dataclass(frozen=True)
class User:
    id: int
    email: str
    name: Optional[str]
    picture: Optional[str]

    def to_dict(self) -> dict:
        return {"id": self.id, "email": self.email, "name": self.name, "picture": self.picture}


def utc_today():
    return datetime.now(timezone.utc).date()


def next_reset() -> datetime:
    """Usage counters reset at 00:00 UTC."""
    now = datetime.now(timezone.utc)
    return (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)


class AccountStore:
    """All account persistence goes through here (tests use an in-memory fake)."""

    def __init__(self, db):
        self.db = db

    def ensure_schema(self) -> None:
        with self.db.get_connection() as conn:
            conn.execute(DDL)

    # Users ------------------------------------------------------------- #
    def upsert_google_user(self, sub: str, email: str, name: Optional[str], picture: Optional[str]) -> User:
        with self.db.get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO querymind_meta.users (google_sub, email, name, picture)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (google_sub) DO UPDATE
                    SET email = EXCLUDED.email, name = EXCLUDED.name,
                        picture = EXCLUDED.picture, last_login_at = now()
                RETURNING id, email, name, picture
                """,
                (sub, email, name, picture),
            )
            row = cur.fetchone()
        return User(row["id"], row["email"], row["name"], row["picture"])

    # Sessions ---------------------------------------------------------- #
    def create_session(self, user_id: int) -> tuple:
        session_id = secrets.token_urlsafe(24)
        expires = datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)
        with self.db.get_connection() as conn:
            conn.execute(
                "INSERT INTO querymind_meta.sessions (id, user_id, expires_at) VALUES (%s, %s, %s)",
                (session_id, user_id, expires),
            )
        return session_id, expires

    def session_user(self, session_id: str) -> Optional[User]:
        """The user of a live (not expired, not revoked) session, else None."""
        with self.db.get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT u.id, u.email, u.name, u.picture
                FROM querymind_meta.sessions s JOIN querymind_meta.users u ON u.id = s.user_id
                WHERE s.id = %s AND s.revoked_at IS NULL AND s.expires_at > now()
                """,
                (session_id,),
            )
            row = cur.fetchone()
        return User(row["id"], row["email"], row["name"], row["picture"]) if row else None

    def revoke_session(self, session_id: str) -> None:
        with self.db.get_connection() as conn:
            conn.execute(
                "UPDATE querymind_meta.sessions SET revoked_at = now() WHERE id = %s AND revoked_at IS NULL",
                (session_id,),
            )

    # Usage ------------------------------------------------------------- #
    def try_consume(self, subject: str, limit: int) -> Optional[int]:
        """
        Atomically count one question for today. Returns the new count, or
        None when the limit was already reached (nothing is counted then).
        """
        with self.db.get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO querymind_meta.usage (subject, day, count) VALUES (%s, %s, 1)
                ON CONFLICT (subject, day) DO UPDATE SET count = querymind_meta.usage.count + 1
                    WHERE querymind_meta.usage.count < %s
                RETURNING count
                """,
                (subject, utc_today(), limit),
            )
            row = cur.fetchone()
        return row["count"] if row else None

    def refund(self, subject: str) -> None:
        """Give back a question that failed on our side (model or server outage)."""
        with self.db.get_connection() as conn:
            conn.execute(
                "UPDATE querymind_meta.usage SET count = GREATEST(count - 1, 0) WHERE subject = %s AND day = %s",
                (subject, utc_today()),
            )

    def used_today(self, subject: str) -> int:
        with self.db.get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT count FROM querymind_meta.usage WHERE subject = %s AND day = %s",
                (subject, utc_today()),
            )
            row = cur.fetchone()
        return row["count"] if row else 0

    # Clarification tickets ---------------------------------------------- #
    # A counted question that comes back with a clarification question gets a
    # ticket; answering with it is free. Free answers never get a new ticket,
    # so one counted question costs at most two model calls.
    def issue_ticket(self, subject: str) -> str:
        ticket = secrets.token_urlsafe(24)
        expires = datetime.now(timezone.utc) + timedelta(minutes=TICKET_MINUTES)
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM querymind_meta.clarification_tickets WHERE expires_at < now() - interval '1 day'")
            conn.execute(
                "INSERT INTO querymind_meta.clarification_tickets (token_hash, subject, expires_at) VALUES (%s, %s, %s)",
                (_ticket_hash(ticket), subject, expires),
            )
        return ticket

    def redeem_ticket(self, ticket: str, subject: str) -> bool:
        """Use a ticket once. False if unknown, expired, used, or someone else's."""
        with self.db.get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE querymind_meta.clarification_tickets SET used_at = now()
                WHERE token_hash = %s AND subject = %s AND used_at IS NULL AND expires_at > now()
                RETURNING token_hash
                """,
                (_ticket_hash(ticket), subject),
            )
            return cur.fetchone() is not None

    def restore_ticket(self, ticket: str) -> None:
        """Make a ticket usable again after the free answer failed on our side."""
        with self.db.get_connection() as conn:
            conn.execute(
                "UPDATE querymind_meta.clarification_tickets SET used_at = NULL WHERE token_hash = %s",
                (_ticket_hash(ticket),),
            )

    # History and saved queries ------------------------------------------- #
    def history(self, user_id: int) -> list:
        with self.db.get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT entry FROM querymind_meta.query_history WHERE user_id = %s ORDER BY at DESC, id DESC LIMIT %s",
                (user_id, HISTORY_LIMIT),
            )
            return [row["entry"] for row in cur.fetchall()]

    def add_history(self, user_id: int, entry: dict) -> None:
        """Store one entry (the same id again is a no-op) and keep the newest HISTORY_LIMIT."""
        with self.db.get_connection() as conn, conn.cursor() as cur:
            _insert_history(cur, user_id, entry)
            _trim_history(cur, user_id)

    def delete_history(self, user_id: int, entry_id: str) -> None:
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM querymind_meta.query_history WHERE user_id = %s AND id = %s", (user_id, entry_id))

    def saved(self, user_id: int) -> list:
        with self.db.get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT entry FROM querymind_meta.saved_queries WHERE user_id = %s ORDER BY at DESC, id DESC",
                (user_id,),
            )
            return [row["entry"] for row in cur.fetchall()]

    def save_query(self, user_id: int, entry: dict) -> bool:
        """
        Save an entry. Saving the same question + clarification again replaces
        the old one. False (nothing changed) when SAVED_LIMIT others exist.
        """
        resolved = entry.get("resolved") or ""
        with self.db.get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM querymind_meta.saved_queries
                WHERE user_id = %s AND (id = %s OR (question = %s AND resolved = %s))
                """,
                (user_id, entry["id"], entry["question"], resolved),
            )
            cur.execute("SELECT count(*) AS n FROM querymind_meta.saved_queries WHERE user_id = %s", (user_id,))
            if cur.fetchone()["n"] >= SAVED_LIMIT:
                conn.rollback()
                return False
            _insert_saved(cur, user_id, entry)
        return True

    def delete_saved(self, user_id: int, entry_id: str) -> None:
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM querymind_meta.saved_queries WHERE user_id = %s AND id = %s", (user_id, entry_id))

    def import_entries(self, user_id: int, history: list, saved: list) -> dict:
        """
        Add a browser's entries to the account. Entries already there (same id,
        or for saved queries the same question + clarification) are skipped.
        """
        added = {"history": 0, "saved": 0}
        with self.db.get_connection() as conn, conn.cursor() as cur:
            for entry in history[:HISTORY_LIMIT]:
                added["history"] += _insert_history(cur, user_id, entry)
            _trim_history(cur, user_id)
            cur.execute("SELECT count(*) AS n FROM querymind_meta.saved_queries WHERE user_id = %s", (user_id,))
            room = SAVED_LIMIT - cur.fetchone()["n"]
            for entry in saved:
                if room <= 0:
                    break
                inserted = _insert_saved(cur, user_id, entry, skip_existing=True)
                added["saved"] += inserted
                room -= inserted
        return added


def _insert_history(cur, user_id: int, entry: dict) -> int:
    cur.execute(
        """
        INSERT INTO querymind_meta.query_history (user_id, id, at, entry) VALUES (%s, %s, %s, %s)
        ON CONFLICT (user_id, id) DO NOTHING
        """,
        (user_id, entry["id"], _entry_time(entry, "executedAt"), Jsonb(entry)),
    )
    return cur.rowcount


def _trim_history(cur, user_id: int) -> None:
    cur.execute(
        """
        DELETE FROM querymind_meta.query_history WHERE user_id = %s AND id NOT IN (
            SELECT id FROM querymind_meta.query_history WHERE user_id = %s ORDER BY at DESC, id DESC LIMIT %s
        )
        """,
        (user_id, user_id, HISTORY_LIMIT),
    )


def _insert_saved(cur, user_id: int, entry: dict, skip_existing: bool = False) -> int:
    cur.execute(
        """
        INSERT INTO querymind_meta.saved_queries (user_id, id, question, resolved, at, entry)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        + (" ON CONFLICT DO NOTHING" if skip_existing else ""),
        (user_id, entry["id"], entry["question"], entry.get("resolved") or "", _entry_time(entry, "savedAt"), Jsonb(entry)),
    )
    return cur.rowcount


def clean_entry(raw) -> Optional[dict]:
    """
    A history or saved entry sent by the browser, checked before it is stored:
    it needs an id and a question, a snapshot of at most 200 rows, and must
    stay under MAX_ENTRY_BYTES. Returns None for anything else.
    """
    if not isinstance(raw, dict):
        return None
    entry_id, question, resolved = raw.get("id"), raw.get("question"), raw.get("resolved")
    if not isinstance(entry_id, str) or not 0 < len(entry_id) <= 100:
        return None
    if not isinstance(question, str) or not 0 < len(question.strip()) <= 2000:
        return None
    if resolved is not None and not isinstance(resolved, str):
        return None
    snapshot = raw.get("snapshot")
    if snapshot is not None and (not isinstance(snapshot, dict) or len(snapshot.get("rows") or []) > 200):
        return None
    try:
        if len(json.dumps(raw)) > MAX_ENTRY_BYTES:
            return None
    except (TypeError, ValueError):
        return None
    return raw


def _entry_time(entry: dict, key: str) -> datetime:
    """The entry's own ISO 8601 timestamp, or now if it is missing or unreadable."""
    try:
        when = datetime.fromisoformat(str(entry.get(key)).replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(timezone.utc)
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def _ticket_hash(ticket: str) -> str:
    return hashlib.sha256(ticket.encode()).hexdigest()
