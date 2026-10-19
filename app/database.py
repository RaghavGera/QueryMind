"""
Database connection and query execution module.

This module handles:
- PostgreSQL connection pooling
- Safe query execution
- Connection lifecycle management
"""

import os
import re
from contextlib import contextmanager
from typing import Any, Generator, List, Dict

import psycopg
from psycopg import Connection, sql
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class WriteConflictError(Exception):
    """A confirmed write no longer matches what the user was shown."""


# Schema and role names the app creates itself: ws_<id>, querymind_ws_<id>, querymind_demo, public.
SAFE_IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")


class QueryTimeoutError(Exception):
    """A query ran past QUERY_TIMEOUT_SECONDS and Postgres cancelled it."""


def _positive_env(name: str, default: float) -> float:
    try:
        value = float(os.getenv(name, default))
    except ValueError:
        return default
    return value if value > 0 else default


def query_timeout_ms() -> int:
    """Statement timeout for every query and write (env QUERY_TIMEOUT_SECONDS, default 8)."""
    return int(_positive_env("QUERY_TIMEOUT_SECONDS", 8) * 1000)


def max_result_rows() -> int:
    """Rows returned for one answer (env MAX_RESULT_ROWS, default 1000); more are flagged as capped."""
    return int(_positive_env("MAX_RESULT_ROWS", 1000))


class DatabaseConfig:
    """Database configuration from environment variables."""

    def __init__(self):
        self.host = os.getenv("DB_HOST", "localhost")
        self.port = int(os.getenv("DB_PORT", "5432"))
        self.database = os.getenv("DB_NAME", "text_to_sql")
        self.user = os.getenv("DB_USER")
        self.password = os.getenv("DB_PASSWORD")

        # Optional: "require" for hosted Postgres such as Neon. Unset keeps
        # libpq's default ("prefer": SSL when the server offers it).
        self.sslmode = os.getenv("DB_SSLMODE", "").strip() or None

        if not self.user or not self.password:
            raise ValueError("DB_USER and DB_PASSWORD must be set in environment variables")

    @property
    def connection_string(self) -> str:
        """Build a libpq connection string; psycopg quotes every value safely."""
        params = {
            "host": self.host,
            "port": self.port,
            "dbname": self.database,
            "user": self.user,
            "password": self.password,
        }
        if self.sslmode:
            params["sslmode"] = self.sslmode
        return make_conninfo(**params)


class Database:
    """
    Database connection manager.

    Provides connection pooling and safe query execution.
    All queries return results as dictionaries for easier handling.
    """

    def __init__(self, config: DatabaseConfig):
        self.config = config
        self._connection_pool = None

    def test_connection(self) -> bool:
        """
        Test database connectivity.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            with psycopg.connect(self.config.connection_string) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    result = cur.fetchone()
                    return result[0] == 1
        except Exception as e:
            print(f"Connection test failed: {e}")
            return False

    @contextmanager
    def get_connection(self) -> Generator[Connection, None, None]:
        """
        Context manager for database connections.

        Yields a connection that automatically commits on success
        and rolls back on error.

        Usage:
            with db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM customers")
        """
        conn = psycopg.connect(
            self.config.connection_string,
            row_factory=dict_row  # Return rows as dictionaries
        )
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def execute_query(
        self,
        query: str,
        params: tuple = None,
        max_rows: int = None,
        search_path: str = None,
        role: str = None,
    ) -> List[Dict[str, Any]]:
        """
        Execute a SELECT query and return results as list of dictionaries.

        Every read runs in a READ ONLY transaction (Postgres refuses any write
        in it, whatever the SQL says) with a statement timeout of
        QUERY_TIMEOUT_SECONDS.

        Args:
            query: SQL query string
            params: Optional query parameters for safe parameterization
            max_rows: Fetch at most ``max_rows + 1`` rows, so the caller can
                tell a capped result (more than ``max_rows``) from a complete one
            search_path: Resolve unqualified table names in this schema only
                (a workspace's ``ws_<id>``)
            role: Run as this NOLOGIN role (``SET LOCAL ROLE``), which can read
                only its own workspace's tables

        Returns:
            List of dictionaries, one per row

        Raises:
            ValueError: if query contains non-SELECT statements
            QueryTimeoutError: if the query ran longer than the timeout
            psycopg.Error: on other database errors
        """
        # Safety check: only allow SELECT queries
        query_upper = query.strip().upper()
        if not query_upper.startswith("SELECT"):
            raise ValueError(
                "Only SELECT queries are allowed. "
                "Found: " + query_upper.split()[0]
            )

        for name in (search_path, role):
            if name is not None and not SAFE_IDENTIFIER.match(name):
                raise ValueError(f"Not a valid schema or role name: {name!r}")

        with self.get_connection() as conn:
            conn.read_only = True  # the transaction starts as BEGIN READ ONLY
            with conn.cursor() as cur:
                # A bound parameter can't be used with SET; set_config can. Local to this transaction.
                if search_path:
                    cur.execute(
                        "SELECT set_config('statement_timeout', %s, true), set_config('search_path', quote_ident(%s), true)",
                        (str(query_timeout_ms()), search_path),
                    )
                else:
                    cur.execute("SELECT set_config('statement_timeout', %s, true)", (str(query_timeout_ms()),))
                if role:
                    cur.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(role)))
                try:
                    if params:
                        cur.execute(query, params)
                    else:
                        cur.execute(query)
                except psycopg.errors.QueryCanceled as exc:
                    raise QueryTimeoutError(
                        f"The query took longer than {query_timeout_ms() / 1000:g} s and was stopped."
                    ) from exc
                return cur.fetchall() if max_rows is None else cur.fetchmany(max_rows + 1)

    def execute_write(
        self,
        query: str,
        params: tuple = None,
        expected_rows: int = None,
    ) -> int:
        """
        Execute one INSERT or UPDATE in its own transaction.

        Only reachable through a confirmed write (see app/writes.py). Guards
        enforced here as defense in depth, independent of the caller:
          * the statement must be a single INSERT or UPDATE
          * an UPDATE must have a WHERE clause
          * if ``expected_rows`` is given and the statement touches a
            different number of rows, the transaction is rolled back

        Returns:
            Number of rows affected.

        Raises:
            ValueError: if the statement is not an allowed write
            WriteConflictError: if the affected row count differs from
                ``expected_rows`` (nothing is committed)
        """
        statement = query.strip().rstrip(";").strip()
        keyword = statement.split(None, 1)[0].upper() if statement else ""
        if keyword not in ("INSERT", "UPDATE"):
            raise ValueError("Only INSERT and UPDATE statements can be executed as writes.")
        if ";" in statement:
            raise ValueError("Multiple statements are not allowed.")
        if keyword == "UPDATE" and " WHERE " not in f" {statement.upper()} ":
            raise ValueError("Refusing to run an UPDATE without a WHERE clause.")

        conn = psycopg.connect(self.config.connection_string)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT set_config('statement_timeout', %s, true)", (str(query_timeout_ms()),))
                try:
                    cur.execute(statement, params or None)
                except psycopg.errors.QueryCanceled as exc:
                    conn.rollback()
                    raise QueryTimeoutError(
                        f"The change took longer than {query_timeout_ms() / 1000:g} s and was stopped; nothing was changed."
                    ) from exc
                affected = cur.rowcount
            if expected_rows is not None and affected != expected_rows:
                conn.rollback()
                raise WriteConflictError(
                    f"The statement would now affect {affected} row(s) instead of the "
                    f"{expected_rows} previewed; nothing was changed."
                )
            conn.commit()
            return affected
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def execute_single(self, query: str, params: tuple = None) -> Dict[str, Any]:
        """
        Execute a query and return a single row.

        Args:
            query: SQL query string
            params: Optional query parameters

        Returns:
            Single row as dictionary, or None if no results
        """
        results = self.execute_query(query, params)
        return results[0] if results else None


# Global database instance (initialized in main.py)
db: Database = None


def get_db() -> Database:
    """
    Get the global database instance.

    Used as a dependency in FastAPI endpoints.
    """
    if db is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return db


def init_db() -> Database:
    """
    Initialize the global database instance.

    Should be called once at application startup.
    """
    global db
    config = DatabaseConfig()
    db = Database(config)
    return db
