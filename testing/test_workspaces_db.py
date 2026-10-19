"""
Workspaces against a real PostgreSQL (skipped without one): each workspace's
role reads its own tables and nothing else.
"""

import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.main as main_module
from app.accounts import AccountStore
from app.auth import Principal
from app.intent_extractor import QueryIntent
from app.schema import SchemaIntrospector
from app.workspaces import DEMO, ScopedDatabase, WorkspaceError, WorkspaceStore


@pytest.fixture
def stores(db):
    accounts, workspaces = AccountStore(db), WorkspaceStore(db)
    accounts.ensure_schema()
    workspaces.ensure_schema()
    assert workspaces.roles_available, "the query roles could be set up"
    tag = f"ws-test-{uuid.uuid4().hex[:8]}"
    users = [accounts.upsert_google_user(f"{tag}-{i}", f"{tag}-{i}@example.com", None, None) for i in range(2)]
    yield accounts, workspaces, users
    for user in users:
        own = workspaces.for_user(user.id)
        if own:
            workspaces.delete(user.id, own.id)
    with db.get_connection() as conn:
        conn.execute("DELETE FROM querymind_meta.users WHERE google_sub LIKE %s", (f"{tag}%",))


def _with_table(db, workspaces, workspace, table, names):
    """What an upload will do: a table in the workspace's schema, readable by its role."""
    with db.get_connection() as conn:
        conn.execute(f'CREATE TABLE "{workspace.schema}"."{table}" (id integer PRIMARY KEY, name text)')
        for i, name in enumerate(names, 1):
            conn.execute(f'INSERT INTO "{workspace.schema}"."{table}" VALUES (%s, %s)', (i, name))
    workspaces.grant_tables(workspace)


def test_the_demo_role_reads_the_demo_but_not_the_account_tables(db, stores):
    demo = ScopedDatabase(db, DEMO)
    assert demo.execute_query("SELECT count(*) AS n FROM customers")[0]["n"] > 0
    with pytest.raises(Exception, match="permission denied"):
        demo.execute_query("SELECT * FROM querymind_meta.users")


def test_a_workspace_reads_only_its_own_tables(db, stores):
    _, workspaces, (ada, bob) = stores
    mine = workspaces.create(ada.id, "upload", "Ada's data")
    theirs = workspaces.create(bob.id, "upload", "Bob's data")
    _with_table(db, workspaces, mine, "plants", ["fern", "moss"])
    _with_table(db, workspaces, theirs, "secrets", ["bob's secret"])

    scoped = ScopedDatabase(db, mine)
    assert [r["name"] for r in scoped.execute_query("SELECT name FROM plants ORDER BY id")] == ["fern", "moss"]
    for forbidden in (
        "SELECT * FROM public.customers",               # the demo
        "SELECT * FROM querymind_meta.users",           # accounts
        f'SELECT * FROM "{theirs.schema}".secrets',     # another user's workspace
    ):
        with pytest.raises(Exception, match="permission denied"):
            scoped.execute_query(forbidden)
    with pytest.raises(Exception, match="does not exist"):
        scoped.execute_query("SELECT * FROM customers")  # unqualified names resolve in the workspace only


def test_the_schema_reader_sees_only_the_workspace(db, stores):
    _, workspaces, (ada, _) = stores
    mine = workspaces.create(ada.id, "upload", "Ada's data")
    _with_table(db, workspaces, mine, "plants", ["fern"])
    schema = SchemaIntrospector(db, mine.schema).introspect()
    assert list(schema.tables) == ["plants"]
    assert schema.tables["plants"].primary_keys == ["id"]


def test_one_workspace_per_user_and_replacing_drops_the_old_one(db, stores):
    _, workspaces, (ada, _) = stores
    first = workspaces.create(ada.id, "upload", "First")
    with pytest.raises(WorkspaceError) as info:
        workspaces.create(ada.id, "upload", "Second")
    assert info.value.status == 409
    second = workspaces.create(ada.id, "upload", "Second", replace=True)
    assert workspaces.for_user(ada.id).id == second.id
    with db.get_connection() as conn:
        assert conn.execute("SELECT 1 FROM pg_namespace WHERE nspname = %s", (first.schema,)).fetchone() is None
        assert conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (first.role,)).fetchone() is None


def test_expired_workspaces_are_removed_with_their_data(db, stores):
    _, workspaces, (ada, _) = stores
    mine = workspaces.create(ada.id, "upload", "Old")
    with db.get_connection() as conn:
        conn.execute("UPDATE querymind_meta.workspaces SET expires_at = %s WHERE id = %s",
                     (datetime.now(timezone.utc) - timedelta(seconds=1), int(mine.id)))
    assert workspaces.for_user(ada.id) is None, "an expired workspace is gone on the next look"
    with db.get_connection() as conn:
        assert conn.execute("SELECT 1 FROM pg_namespace WHERE nspname = %s", (mine.schema,)).fetchone() is None


def test_own_data_is_never_written(db, stores):
    _, workspaces, (ada, _) = stores
    mine = workspaces.create(ada.id, "upload", "Ada's data")
    _with_table(db, workspaces, mine, "plants", ["fern"])
    scoped = ScopedDatabase(db, mine)
    with pytest.raises(Exception, match="read-only transaction|permission denied"):
        scoped.execute_query("SELECT 1 AS x INTO TEMP TABLE probe")
    with pytest.raises(WorkspaceError):
        scoped.execute_write('UPDATE plants SET name = %s WHERE id = %s', ("x", 1))


def test_a_question_runs_against_the_chosen_workspace(db, stores, monkeypatch):
    _, workspaces, (ada, bob) = stores
    mine = workspaces.create(ada.id, "upload", "Ada's data")
    _with_table(db, workspaces, mine, "plants", ["fern", "moss"])
    monkeypatch.setattr(main_module, "_workspace_store", workspaces)
    main_module.schema_cache.forget()
    monkeypatch.setattr(
        main_module, "extract_intent",
        lambda q, c: QueryIntent(query_type="select", tables=["plants"], columns=["plants.name"]),
    )

    def ask(user, workspace_id):
        principal = Principal(kind="user", subject=f"user:{user.id}", user=user) if user else None
        http = SimpleNamespace(state=SimpleNamespace(principal=principal))
        request = main_module.QueryRequest(question="Show the plant names.", workspace_id=workspace_id)
        response = main_module.run_query(request, db, http)
        return getattr(response, "status_code", 200), response

    code, body = ask(ada, mine.id)
    assert code == 200 and sorted(r["name"] for r in body["result"]["rows"]) == ["fern", "moss"]
    assert ask(bob, mine.id)[0] == 404, "someone else's workspace"
    assert ask(None, mine.id)[0] == 401, "signed out"
    main_module.schema_cache.forget()
