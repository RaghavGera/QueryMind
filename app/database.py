"""
Database connection and query execution module.

This module handles:
- PostgreSQL connection pooling
- Safe query execution
- Connection lifecycle management
"""

import os
from contextlib import contextmanager
from typing import Any, Generator, List, Dict

import psycopg
from psycopg import Connection
from psycopg.rows import dict_row
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class DatabaseConfig:
    """Database configuration from environment variables."""

    def __init__(self):
        self.host = os.getenv("DB_HOST", "localhost")
        self.port = int(os.getenv("DB_PORT", "5432"))
        self.database = os.getenv("DB_NAME", "text_to_sql")
        self.user = os.getenv("DB_USER")
        self.password = os.getenv("DB_PASSWORD")

        if not self.user or not self.password:
            raise ValueError("DB_USER and DB_PASSWORD must be set in environment variables")

    @property
    def connection_string(self) -> str:
        """Build PostgreSQL connection string."""
        return (
            f"host={self.host} "
            f"port={self.port} "
            f"dbname={self.database} "
            f"user={self.user} "
            f"password={self.password}"
        )


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

    def execute_query(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """
        Execute a SELECT query and return results as list of dictionaries.

        Args:
            query: SQL query string
            params: Optional query parameters for safe parameterization

        Returns:
            List of dictionaries, one per row

        Raises:
            ValueError: if query contains non-SELECT statements
            psycopg.Error: on database errors
        """
        # Safety check: only allow SELECT queries
        query_upper = query.strip().upper()
        if not query_upper.startswith("SELECT"):
            raise ValueError(
                "Only SELECT queries are allowed. "
                "Found: " + query_upper.split()[0]
            )

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                if params:
                    cur.execute(query, params)
                else:
                    cur.execute(query)
                return cur.fetchall()

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
