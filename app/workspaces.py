"""
Workspaces: which data a question runs against.

    demo        the shared sample database (schema ``public``), read-only for
                everyone, signed in or not. Not stored: it always exists.
    upload      a signed-in user's files, imported into a private schema
                ``ws_<id>`` (Phase 5).
    connection  a signed-in user's own PostgreSQL (Phase 6).

Owner decisions (2026-10-19): only signed-in users create workspaces; one
active workspace per user (a new one replaces the old); uploaded data expires
after 7 days, connections after 24 hours; history and saved queries outlive
their workspace and are shown as "workspace expired".

Isolation: every answer query runs as a NOLOGIN role that can read only its
own schema (``SET LOCAL ROLE`` inside the read-only transaction). The demo's
role, ``querymind_demo``, can read the demo tables and nothing else, so even a
generator bug can't reach the account tables or another user's workspace.
If roles can't be set up, demo questions run as before and creating
workspaces is refused (``roles_available`` is False).
"""

import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, Optional

import psycopg
from psycopg import sql

logger = logging.getLogger(__name__)

DEMO_ID = "demo"
DEMO_ROLE = "querymind_demo"
EXPIRY = {"upload": timedelta(days=7), "connection": timedelta(hours=24)}
SCHEMA_CACHE_SECONDS = 300

DDL = """
CREATE TABLE IF NOT EXISTS querymind_meta.workspaces (
    id         BIGSERIAL PRIMARY KEY,
    user_id    BIGINT NOT NULL UNIQUE REFERENCES querymind_meta.users(id) ON DELETE CASCADE,  -- one per user
    kind       TEXT NOT NULL CHECK (kind IN ('upload', 'connection')),
    name       TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL
);
"""


class WorkspaceError(Exception):
    """A workspace problem; ``status`` is the HTTP code to answer with."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class Workspace:
    id: str
    kind: str
    name: str
    schema: str  # the Postgres schema its tables live in
    role: str  # the role its answer queries run as
    expires_at: Optional[datetime] = None

    @property
    def is_demo(self) -> bool:
        return self.id == DEMO_ID

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "name": self.name,
            "read_only": True,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }


DEMO = Workspace(id=DEMO_ID, kind="demo", name="Demo store", schema="public", role=DEMO_ROLE)


def _from_row(row: dict) -> Workspace:
    ws_id = row["id"]
    return Workspace(
        id=str(ws_id), kind=row["kind"], name=row["name"],
        schema=f"ws_{ws_id}", role=f"querymind_ws_{ws_id}", expires_at=row["expires_at"],
    )


class ScopedDatabase:
    """
    The database as one workspace sees it. Answer queries run with the
    workspace's ``search_path`` and as its role; the schema reader uses the
    owner connection (information_schema hides constraints from non-owners)
    but only ever reads this workspace's schema.
    """

    def __init__(self, db, workspace: Workspace, use_role: bool = True):
        self.db = db
        self.workspace = workspace
        self.use_role = use_role
        self.config = db.config

    @property
    def read_only_workspace(self) -> bool:
        """Writes (even confirmed ones) are for the demo only."""
        return not self.workspace.is_demo

    def execute_query(self, query, params=None, max_rows=None):
        return self.db.execute_query(
            query, params, max_rows=max_rows,
            search_path=None if self.workspace.is_demo else self.workspace.schema,
            role=self.workspace.role if self.use_role else None,
        )

    def execute_write(self, *args, **kwargs):
        if self.read_only_workspace:
            raise WorkspaceError("Your own data is read-only.", status=403)
        return self.db.execute_write(*args, **kwargs)


class SchemaCache:
    """Introspected schemas per workspace, for SCHEMA_CACHE_SECONDS (an upload never changes)."""

    def __init__(self, ttl: float = SCHEMA_CACHE_SECONDS, clock: Callable[[], float] = time.monotonic):
        self.ttl, self.clock = ttl, clock
        self._entries: Dict[str, tuple] = {}
        self._lock = threading.Lock()

    def get(self, key: str, load: Callable):
        with self._lock:
            hit = self._entries.get(key)
            if hit and self.clock() - hit[0] < self.ttl:
                return hit[1]
        value = load()  # outside the lock: introspection takes a few queries
        with self._lock:
            self._entries[key] = (self.clock(), value)
        return value

    def forget(self, key: Optional[str] = None) -> None:
        with self._lock:
            if key is None:
                self._entries.clear()
            else:
                self._entries.pop(key, None)


class WorkspaceStore:
    """Workspace rows plus their schemas and roles."""

    def __init__(self, db):
        self.db = db
        self.roles_available = False

    def ensure_schema(self) -> None:
        """Create the table and the demo's read role. Never raises for the role part."""
        with self.db.get_connection() as conn:
            conn.execute(DDL)
        try:
            with self.db.get_connection() as conn:
                _ensure_role(conn, DEMO_ROLE)
                conn.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(DEMO_ROLE)))
                conn.execute(sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA public TO {}").format(sql.Identifier(DEMO_ROLE)))
            self.roles_available = True
        except Exception:
            logger.exception(
                "Could not set up the read-only query roles; demo questions run as the owner "
                "and creating workspaces is disabled."
            )

    def for_user(self, user_id: int) -> Optional[Workspace]:
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT id, kind, name, expires_at FROM querymind_meta.workspaces WHERE user_id = %s", (user_id,)
            ).fetchone()
        if row is None:
            return None
        workspace = _from_row(row)
        if workspace.expires_at <= datetime.now(timezone.utc):
            self.delete(user_id, workspace.id)
            return None
        return workspace

    def create(self, user_id: int, kind: str, name: str, replace: bool = False) -> Workspace:
        """
        Create the user's workspace: a row, an empty schema ``ws_<id>`` and its
        read role. With ``replace`` an existing workspace is deleted first;
        without it, having one is a 409.
        """
        if kind not in EXPIRY:
            raise WorkspaceError(f"Unknown workspace kind {kind!r}.")
        if not self.roles_available:
            raise WorkspaceError("Your own data can't be added on this server right now.", status=503)
        existing = self.for_user(user_id)
        if existing is not None:
            if not replace:
                raise WorkspaceError(
                    f"You already have a workspace ({existing.name}). Replace it to add another.", status=409
                )
            self.delete(user_id, existing.id)
        expires = datetime.now(timezone.utc) + EXPIRY[kind]
        with self.db.get_connection() as conn:
            row = conn.execute(
                """
                INSERT INTO querymind_meta.workspaces (user_id, kind, name, expires_at)
                VALUES (%s, %s, %s, %s) RETURNING id, kind, name, expires_at
                """,
                (user_id, kind, name.strip()[:100] or "My data", expires),
            ).fetchone()
            workspace = _from_row(row)
            conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(workspace.schema)))
            _ensure_role(conn, workspace.role)
            conn.execute(
                sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(sql.Identifier(workspace.schema), sql.Identifier(workspace.role))
            )
        return workspace

    def grant_tables(self, workspace: Workspace) -> None:
        """After tables are imported into the workspace's schema, let its role read them."""
        with self.db.get_connection() as conn:
            conn.execute(
                sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA {} TO {}").format(
                    sql.Identifier(workspace.schema), sql.Identifier(workspace.role)
                )
            )

    def delete(self, user_id: int, workspace_id: str) -> bool:
        """Drop the workspace's data, role and row. False if the user has no such workspace."""
        if not str(workspace_id).isdigit():
            return False
        with self.db.get_connection() as conn:
            row = conn.execute(
                "DELETE FROM querymind_meta.workspaces WHERE id = %s AND user_id = %s RETURNING id, kind, name, expires_at",
                (int(workspace_id), user_id),
            ).fetchone()
            if row is None:
                return False
            _drop_storage(conn, _from_row(row))
        return True

    def delete_expired(self) -> int:
        """Remove every workspace past its expiry (run at startup and when workspaces are listed)."""
        with self.db.get_connection() as conn:
            rows = conn.execute(
                "DELETE FROM querymind_meta.workspaces WHERE expires_at <= now() RETURNING id, kind, name, expires_at"
            ).fetchall()
            for row in rows:
                _drop_storage(conn, _from_row(row))
        return len(rows)


def _ensure_role(conn, role: str) -> None:
    """
    A NOLOGIN role the owner can switch to with SET ROLE, proven by switching
    to it (raises if that is refused).

    On PostgreSQL 16+ a non-superuser that creates a role is only given ADMIN
    on it (createrole_self_grant is empty by default), which counts as
    membership but does not allow SET ROLE. Granting the role to ourselves adds
    the SET option. Neon's owner role is such a non-superuser.
    """
    exists = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,)).fetchone()
    if not exists:
        conn.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(role)))
    if not _can_set_role(conn, role):
        conn.execute(sql.SQL("GRANT {} TO CURRENT_USER").format(sql.Identifier(role)))
    with conn.transaction(force_rollback=True):  # a savepoint: the switch is undone right away
        conn.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(role)))


def _can_set_role(conn, role: str) -> bool:
    try:
        with conn.transaction():  # savepoint: the 'SET' privilege type is unknown before PostgreSQL 16
            return conn.execute("SELECT pg_has_role(current_user, %s, 'SET') AS ok", (role,)).fetchone()["ok"]
    except psycopg.Error:
        return conn.execute("SELECT pg_has_role(current_user, %s, 'MEMBER') AS ok", (role,)).fetchone()["ok"]


def _drop_storage(conn, workspace: Workspace) -> None:
    conn.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(workspace.schema)))
    conn.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(workspace.role)))
