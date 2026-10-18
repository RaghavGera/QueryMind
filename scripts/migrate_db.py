"""
Copy the QueryMind database from one PostgreSQL server to another
(Render -> Neon), then prove the copy is complete.

Credentials are read from .env.migrate (git-ignored), never from the command
line or chat:

    SOURCE_DATABASE_URL=postgresql://...   # Render: "External Database URL"
    TARGET_DATABASE_URL=postgresql://...   # Neon: connection string (sslmode=require)

    python scripts/migrate_db.py check    # connect to both; tables and row counts
    python scripts/migrate_db.py copy     # pg_dump source -> psql target, one transaction
    python scripts/migrate_db.py verify   # row counts and a revenue checksum must match

Output never includes passwords or full URLs, only host and database names.
`copy` refuses to write into a target that already has data unless --force.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import psycopg
from dotenv import dotenv_values
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = Path(os.getenv("MIGRATE_ENV_FILE", ROOT / ".env.migrate"))  # override only for rehearsals
DEFAULT_PG_BIN = Path("C:/Program Files/PostgreSQL/18/bin")

# Same numbers the landing page shows: a strong end-to-end check of the data.
REVENUE_CHECKSUM = """
    SELECT c.country, SUM(oi.quantity * oi.unit_price) AS revenue
    FROM customers c
    JOIN orders o ON o.customer_id = c.customer_id
    JOIN order_items oi ON oi.order_id = o.order_id
    GROUP BY c.country ORDER BY c.country
"""


def load_urls():
    if not ENV_FILE.exists():
        sys.exit(f"Missing {ENV_FILE.name}. Create it with SOURCE_DATABASE_URL and TARGET_DATABASE_URL.")
    values = dotenv_values(ENV_FILE)
    urls = {name: (values.get(f"{name}_DATABASE_URL") or "").strip() for name in ("SOURCE", "TARGET")}
    missing = [name for name, url in urls.items() if not url]
    if missing:
        sys.exit(f"{ENV_FILE.name} is missing: {', '.join(m + '_DATABASE_URL' for m in missing)}")
    if urls["SOURCE"] == urls["TARGET"]:
        sys.exit("SOURCE and TARGET are the same database; refusing to continue.")
    return urls["SOURCE"], urls["TARGET"]


def describe(url):
    """Host/database only: never the user or password."""
    info = conninfo_to_dict(url)
    return f"{info.get('host', '?')}/{info.get('dbname', '?')}"


def pg_tool(name):
    found = shutil.which(name)
    if found:
        return found
    candidate = Path(os.getenv("PG_BIN", DEFAULT_PG_BIN)) / f"{name}.exe"
    if candidate.exists():
        return str(candidate)
    sys.exit(f"Could not find {name}. Install the PostgreSQL client tools or set PG_BIN.")


# libpq environment variables for each connection parameter.
_PG_ENV = {"host": "PGHOST", "port": "PGPORT", "dbname": "PGDATABASE", "user": "PGUSER",
           "password": "PGPASSWORD", "sslmode": "PGSSLMODE", "channel_binding": "PGCHANNELBINDING"}


def run_pg(tool, url, args):
    """
    Run pg_dump/psql against ``url``. Credentials go through libpq environment
    variables, never argv, so neither the process list nor an error message
    can reveal them. On failure only the tool's own error output is shown.
    """
    env = {k: v for k, v in os.environ.items() if not k.startswith("PG") or k == "PG_BIN"}
    for key, value in conninfo_to_dict(url).items():
        if key in _PG_ENV:
            env[_PG_ENV[key]] = str(value)
    result = subprocess.run([pg_tool(tool), *args], env=env, capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"{tool} failed (exit {result.returncode}):\n{result.stderr.strip()[-2000:]}")
    return result


def snapshot(url):
    """Server version, {table: row count} for the public schema, and the revenue checksum."""
    with psycopg.connect(url, connect_timeout=15) as conn, conn.cursor() as cur:
        cur.execute("SHOW server_version_num")
        version = int(cur.fetchone()[0])
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' ORDER BY table_name"
        )
        tables = [row[0] for row in cur.fetchall()]
        counts = {}
        for table in tables:
            cur.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table)))
            counts[table] = cur.fetchone()[0]
        checksum = None
        if {"customers", "orders", "order_items"} <= set(tables):
            cur.execute(REVENUE_CHECKSUM)
            checksum = [(country, float(revenue)) for country, revenue in cur.fetchall()]
    return version, counts, checksum


def print_snapshot(label, url, snap):
    version, counts, _ = snap
    print(f"\n{label}: {describe(url)}  (PostgreSQL {version // 10000})")
    if not counts:
        print("  (no tables)")
    for table, count in counts.items():
        print(f"  {table:<16} {count:>8,} rows")


def cmd_check(source, target):
    for label, url in (("SOURCE", source), ("TARGET", target)):
        try:
            print_snapshot(label, url, snapshot(url))
        except psycopg.Error as exc:
            print(f"\n{label}: {describe(url)}  could not connect: {str(exc).splitlines()[0]}")


def cmd_copy(source, target, force):
    target_version, target_counts, _ = snapshot(target)
    if any(target_counts.values()) and not force:
        sys.exit("TARGET already contains data. Refusing to overwrite it (use --force if you are sure).")
    source_snap = snapshot(source)
    print_snapshot("SOURCE", source, source_snap)

    with tempfile.TemporaryDirectory() as tmp:
        dump = Path(tmp) / "querymind.sql"
        print("\nDumping source ...")
        run_pg("pg_dump", source, ["--format=plain", "--schema=public", "--no-owner", "--no-privileges",
                                   "--file", str(dump)])
        text = dump.read_text(encoding="utf-8")
        lines = []
        for line in text.splitlines():
            if line.strip() == "CREATE SCHEMA public;":
                line = "CREATE SCHEMA IF NOT EXISTS public;"  # every database already has it
            elif line.startswith("COMMENT ON SCHEMA public"):
                continue  # needs schema ownership, which a hosted target may not grant
            elif target_version < 170000 and line.startswith("SET transaction_timeout"):
                continue  # pg_dump 17+ emits a setting that older servers reject
            lines.append(line)
        text = "\n".join(lines) + "\n"
        dump.write_text(text, encoding="utf-8")
        if force:
            for table in target_counts:
                text = f'DROP TABLE IF EXISTS "{table}" CASCADE;\n' + text
            dump.write_text(text, encoding="utf-8")
        print("Restoring into target (single transaction: all or nothing) ...")
        run_pg("psql", target, ["-v", "ON_ERROR_STOP=1", "--single-transaction", "--quiet", "--file", str(dump)])
    print("Copy finished. Now run: python scripts/migrate_db.py verify")


def cmd_verify(source, target):
    s_version, s_counts, s_sum = snapshot(source)
    t_version, t_counts, t_sum = snapshot(target)
    ok = True
    print(f"\n{'table':<16} {'source':>10} {'target':>10}")
    for table in sorted(set(s_counts) | set(t_counts)):
        a, b = s_counts.get(table), t_counts.get(table)
        mark = "" if a == b else "   <-- MISMATCH"
        ok &= a == b
        print(f"{table:<16} {a if a is not None else '-':>10} {b if b is not None else '-':>10}{mark}")
    same_sum = s_sum == t_sum
    ok &= same_sum
    print(f"\nrevenue-by-country checksum: {'match' if same_sum else 'MISMATCH'}")
    if t_sum:
        top = max(t_sum, key=lambda row: row[1])
        print(f"  target top country: {top[0]} {top[1]:,.0f}")
    print("\nRESULT:", "copy is complete and identical" if ok else "copy does NOT match")
    sys.exit(0 if ok else 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("step", choices=["check", "copy", "verify"])
    parser.add_argument("--force", action="store_true", help="copy: overwrite tables that already exist in the target")
    args = parser.parse_args()
    source, target = load_urls()
    {"check": lambda: cmd_check(source, target),
     "copy": lambda: cmd_copy(source, target, args.force),
     "verify": lambda: cmd_verify(source, target)}[args.step]()


if __name__ == "__main__":
    main()
