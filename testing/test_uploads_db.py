"""
Uploads end to end against a real PostgreSQL (skipped without one): preview,
import, the tables Postgres ends up with, questions about them, replacement,
rollback, and the same flow as a non-superuser owner (as on Neon).
"""

import asyncio
import io
import json
import secrets
import sys
import uuid
from pathlib import Path

import httpx
import pytest
from psycopg import sql as psql

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.main as main_module
from app.accounts import AccountStore
from app.auth import issue_session_token
from app.database import Database, DatabaseConfig, get_db
from app.intent_extractor import QueryIntent
from app.uploads import analyse, import_tables, parse_files
from app.workspaces import ScopedDatabase, WorkspaceStore

DEPARTMENTS = b"department_id,name,budget\n1,Sales,1500000.50\n2,Research,\n3,Support,900000\n"
EMPLOYEES = (
    b"employee_id,full name,department_id,hired,active\n"
    b"10,Ada Lovelace,1,03/04/2024,yes\n11,Grace Hopper,2,05/06/2024,no\n12,Linus T,3,25/12/2023,yes\n"
)


@pytest.fixture
def api(db, monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", "s" * 48)
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client.apps.googleusercontent.com")
    accounts, workspaces = AccountStore(db), WorkspaceStore(db)
    accounts.ensure_schema()
    workspaces.ensure_schema()
    monkeypatch.setattr(main_module, "_store", accounts)
    monkeypatch.setattr(main_module, "_workspace_store", workspaces)
    main_module.schema_cache.forget()
    main_module.app.dependency_overrides[get_db] = lambda: db
    tag = f"up-test-{uuid.uuid4().hex[:8]}"
    users = []

    def sign_in(n=0):
        while len(users) <= n:
            users.append(accounts.upsert_google_user(f"{tag}-{len(users)}", f"{tag}-{len(users)}@example.com", None, None))
        sid, expires = accounts.create_session(users[n].id)
        return {"Authorization": f"Bearer {issue_session_token(sid, users[n].id, expires)}"}

    def call(method, path, headers=None, **kwargs):
        async def go():
            transport = httpx.ASGITransport(app=main_module.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://api.test") as client:
                return await client.request(method, path, headers=headers, **kwargs)
        return asyncio.run(go())

    def upload(path, headers, files, **form):
        payload = {k: (json.dumps(v) if k == "plan" else str(v).lower() if isinstance(v, bool) else v) for k, v in form.items()}
        return call("POST", path, headers, files=[("files", (n, d)) for n, d in files], data=payload)

    yield type("Api", (), {"call": staticmethod(call), "upload": staticmethod(upload), "sign_in": staticmethod(sign_in),
                           "workspaces": workspaces, "users": users, "db": db})
    main_module.app.dependency_overrides.clear()
    main_module.schema_cache.forget()
    for user in users:
        own = workspaces.for_user(user.id)
        if own:
            workspaces.delete(user.id, own.id)
    with db.get_connection() as conn:
        conn.execute("DELETE FROM querymind_meta.users WHERE google_sub LIKE %s", (f"{tag}%",))


FILES = [("departments.csv", DEPARTMENTS), ("employees.csv", EMPLOYEES)]


def test_uploads_need_a_session(api):
    assert api.upload("/workspaces/uploads/preview", None, FILES).status_code == 401
    assert api.upload("/workspaces/uploads", None, FILES).status_code == 401


def test_preview_then_import_with_edits(api, monkeypatch):
    me = api.sign_in()
    preview = api.upload("/workspaces/uploads/preview", me, FILES).json()
    employees = next(t for t in preview["tables"] if t["name"] == "employees")
    hired = next(c for c in employees["columns"] if c["name"] == "hired")
    assert (hired["type"], hired["date_order"], hired["ambiguous_dates"]) == ("date", "dmy", False), "25/12 proves day first"
    assert preview["links"] == [{"table": "employees", "column": "department_id", "ref_table": "departments", "ref_column": "department_id"}]
    assert preview["replaces"] is None

    full_name = next(c for c in employees["columns"] if c["name"] == "full_name")
    plan = {"tables": [{"key": employees["key"], "name": "staff", "columns": [{"key": full_name["key"], "name": "name"}]}]}
    done = api.upload("/workspaces/uploads", me, FILES, plan=plan, name="HR data")
    assert done.status_code == 200, done.text
    body = done.json()
    assert body["workspace"]["name"] == "HR data" and body["workspace"]["kind"] == "upload"
    assert {t["name"]: t["rows"] for t in body["tables"]} == {"departments": 3, "staff": 3}
    assert body["links"] == [{"table": "staff", "column": "department_id", "ref_table": "departments", "ref_column": "department_id"}]

    workspace = api.workspaces.for_user(api.users[0].id)
    with api.db.get_connection() as conn:
        types = {r["column_name"]: r["data_type"] for r in conn.execute(
            "SELECT column_name, data_type FROM information_schema.columns WHERE table_schema = %s AND table_name = 'staff'",
            (workspace.schema,)).fetchall()}
        fks = conn.execute(
            "SELECT count(*) AS n FROM information_schema.table_constraints WHERE table_schema = %s AND constraint_type = 'FOREIGN KEY'",
            (workspace.schema,)).fetchone()["n"]
    assert types == {"employee_id": "bigint", "name": "text", "department_id": "bigint", "hired": "date", "active": "boolean"}
    assert fks == 1

    rows = ScopedDatabase(api.db, workspace).execute_query("SELECT name, hired FROM staff ORDER BY employee_id")
    assert [(r["name"], r["hired"].isoformat()) for r in rows][0] == ("Ada Lovelace", "2024-04-03")

    monkeypatch.setattr(main_module, "extract_intent",
                        lambda q, c: QueryIntent(query_type="select", tables=["staff"], columns=["staff.name"]))
    answer = api.call("POST", "/query", {**me}, json={"question": "List the staff names.", "workspace_id": workspace.id}).json()
    assert answer["status"] == "success" and len(answer["result"]["rows"]) == 3
    schema = api.call("GET", f"/schema?workspace_id={workspace.id}", me).json()
    assert set(schema["tables"]) == {"departments", "staff"} and schema["database"] == "HR data"


def test_a_second_upload_needs_replace_and_a_failed_import_keeps_the_old_one(api, monkeypatch):
    me = api.sign_in()
    assert api.upload("/workspaces/uploads", me, FILES, name="First").status_code == 200
    first = api.workspaces.for_user(api.users[0].id)

    again = api.upload("/workspaces/uploads", me, [("t.csv", b"a\n1\n")], name="Second")
    assert again.status_code == 409 and "Replace it" in again.json()["error"]

    # Over the storage quota: the import fails inside the transaction, so nothing changes.
    monkeypatch.setenv("UPLOAD_QUOTA_MB", "1")
    big = b"n,payload\n" + b"".join(b"%d,%s\n" % (i, b"x" * 200) for i in range(8000))
    failed = api.upload("/workspaces/uploads", me, [("big.csv", big)], name="Too big", replace=True)
    assert failed.status_code == 422 and "the limit is 1 MB" in failed.json()["error"]
    still = api.workspaces.for_user(api.users[0].id)
    assert still.id == first.id, "the old workspace survived the failed replacement"
    assert ScopedDatabase(api.db, still).execute_query("SELECT count(*) AS n FROM departments")[0]["n"] == 3

    monkeypatch.delenv("UPLOAD_QUOTA_MB")
    replaced = api.upload("/workspaces/uploads", me, [("t.csv", b"a\n1\n")], name="Second", replace=True)
    assert replaced.status_code == 200
    with api.db.get_connection() as conn:
        assert conn.execute("SELECT 1 FROM pg_namespace WHERE nspname = %s", (first.schema,)).fetchone() is None


def test_edits_that_dont_fit_are_refused_with_every_problem(api):
    me = api.sign_in()
    preview = api.upload("/workspaces/uploads/preview", me, FILES).json()
    employees = next(t for t in preview["tables"] if t["name"] == "employees")
    name_col = next(c for c in employees["columns"] if c["name"] == "full_name")
    plan = {"tables": [{"key": employees["key"], "columns": [{"key": name_col["key"], "type": "integer"}]}]}
    refused = api.upload("/workspaces/uploads/preview", me, FILES, plan=plan)
    assert refused.status_code == 422 and "employees.full_name: 3 values don't fit the type integer" in refused.json()["error"]


def test_an_excel_workbook_imports(api):
    import openpyxl
    from datetime import datetime
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.title = "Sales"
    sheet.append(["Sale ID", "Region", "Amount", "Sold at"])
    sheet.append([1, "North", 120.5, datetime(2025, 3, 1, 9, 30)])
    sheet.append([2, "South", 80, datetime(2025, 3, 2, 14, 0)])
    buffer = io.BytesIO()
    book.save(buffer)
    me = api.sign_in()
    done = api.upload("/workspaces/uploads", me, [("sales.xlsx", buffer.getvalue())])
    assert done.status_code == 200, done.text
    workspace = api.workspaces.for_user(api.users[0].id)
    rows = ScopedDatabase(api.db, workspace).execute_query("SELECT region, amount, sold_at FROM sales ORDER BY sale_id")
    assert [(r["region"], float(r["amount"]), r["sold_at"].hour) for r in rows] == [("North", 120.5, 9), ("South", 80.0, 14)]


def test_oversized_uploads_are_refused_before_reading(api, monkeypatch):
    monkeypatch.setattr(main_module, "MAX_UPLOAD_BODY_BYTES", 100)
    refused = api.upload("/workspaces/uploads/preview", api.sign_in(), FILES)
    assert refused.status_code == 413 and "too large" in refused.json()["error"]


def test_the_import_works_for_a_non_superuser_owner_like_neon(db):
    """The whole creation + import + query path with Neon-like privileges (see the role outage of 2026-10-19)."""
    with db.get_connection() as conn:
        if not conn.execute("SELECT rolsuper FROM pg_roles WHERE rolname = current_user").fetchone()["rolsuper"]:
            pytest.skip("needs a superuser to create the stand-in owner role")
        database = conn.execute("SELECT current_database() AS d").fetchone()["d"]
    owner, password = f"qm_owner_{uuid.uuid4().hex[:8]}", secrets.token_urlsafe(16)
    accounts = AccountStore(db)
    accounts.ensure_schema()
    WorkspaceStore(db).ensure_schema()
    user = accounts.upsert_google_user(f"neonlike-{uuid.uuid4().hex[:8]}", "n@example.com", None, None)
    with db.get_connection() as conn:
        ident = psql.Identifier(owner)
        conn.execute(psql.SQL("CREATE ROLE {} LOGIN CREATEROLE PASSWORD {}").format(ident, psql.Literal(password)))
        conn.execute(psql.SQL("GRANT CREATE ON DATABASE {} TO {}").format(psql.Identifier(database), ident))
        conn.execute(psql.SQL("GRANT USAGE ON SCHEMA querymind_meta TO {}").format(ident))
        conn.execute(psql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON querymind_meta.workspaces TO {}").format(ident))
        conn.execute(psql.SQL("GRANT USAGE ON ALL SEQUENCES IN SCHEMA querymind_meta TO {}").format(ident))
    workspace = None
    config = DatabaseConfig()
    config.user, config.password = owner, password
    as_owner = Database(config)
    store = WorkspaceStore(as_owner)
    store.roles_available = True  # the demo role belongs to the real owner; this test is about workspaces
    try:
        raws = parse_files(FILES)
        plan = analyse(raws)
        workspace = store.create(user.id, "upload", "Neon-like", fill=lambda conn, ws: import_tables(conn, ws.schema, plan, raws))
        rows = ScopedDatabase(as_owner, workspace).execute_query(
            "SELECT e.full_name FROM employees e JOIN departments d USING (department_id) WHERE d.name = %s", ("Research",))
        assert rows == [{"full_name": "Grace Hopper"}]
    finally:
        if workspace is not None:
            store.delete(user.id, workspace.id)
        as_owner.close()  # its pooled sessions end before the role is dropped
        with db.get_connection() as conn:
            conn.execute("DELETE FROM querymind_meta.users WHERE id = %s", (user.id,))
            conn.execute(psql.SQL("DROP OWNED BY {} CASCADE").format(psql.Identifier(owner)))
            conn.execute(psql.SQL("DROP ROLE {}").format(psql.Identifier(owner)))
