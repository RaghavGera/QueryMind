"""
Accounts, sessions and daily usage, stored in the ``querymind_meta`` schema.

The schema introspector reads only ``public``, so none of these tables are
ever shown to the language model or the user's schema browser.
"""

import hashlib
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

SESSION_DAYS = 7
TICKET_MINUTES = 15

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


def _ticket_hash(ticket: str) -> str:
    return hashlib.sha256(ticket.encode()).hexdigest()
