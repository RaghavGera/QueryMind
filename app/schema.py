"""
Database schema introspection module.

This module reads the PostgreSQL database schema and builds
a structured representation using Pydantic models.

The schema includes:
- Tables and their columns
- Data types
- Primary keys
- Foreign keys
- Table relationships
"""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from app.database import Database


class ColumnInfo(BaseModel):
    """Information about a database column."""

    name: str
    data_type: str
    is_nullable: bool
    is_primary_key: bool = False
    default_value: Optional[str] = None
    max_length: Optional[int] = None


class ForeignKey(BaseModel):
    """Foreign key relationship."""

    column: str
    referenced_table: str
    referenced_column: str


class TableInfo(BaseModel):
    """Information about a database table."""

    name: str
    columns: Dict[str, ColumnInfo] = Field(default_factory=dict)
    primary_keys: List[str] = Field(default_factory=list)
    foreign_keys: List[ForeignKey] = Field(default_factory=list)


class DatabaseSchema(BaseModel):
    """Complete database schema representation."""

    tables: Dict[str, TableInfo] = Field(default_factory=dict)

    def get_table(self, table_name: str) -> Optional[TableInfo]:
        """Get table info by name."""
        return self.tables.get(table_name)

    def get_relationships(self, table_name: str) -> List[ForeignKey]:
        """Get all foreign keys for a table."""
        table = self.get_table(table_name)
        return table.foreign_keys if table else []

    def to_dict(self) -> dict:
        """Convert schema to dictionary format."""
        return {
            "tables": {
                table_name: {
                    "columns": {
                        col_name: {
                            "data_type": col.data_type,
                            "is_nullable": col.is_nullable,
                            "is_primary_key": col.is_primary_key,
                        }
                        for col_name, col in table.columns.items()
                    },
                    "primary_keys": table.primary_keys,
                    "foreign_keys": [
                        {
                            "column": fk.column,
                            "references": f"{fk.referenced_table}.{fk.referenced_column}"
                        }
                        for fk in table.foreign_keys
                    ]
                }
                for table_name, table in self.tables.items()
            }
        }


class SchemaIntrospector:
    """
    Introspects PostgreSQL database schema.

    Reads table structure, columns, data types, keys, and relationships
    directly from PostgreSQL system catalogs.
    """

    def __init__(self, db: Database):
        self.db = db

    def introspect(self) -> DatabaseSchema:
        """
        Introspect the entire database schema.

        Returns:
            DatabaseSchema with complete table and relationship information
        """
        schema = DatabaseSchema()

        # Get all user tables (exclude system tables)
        tables = self._get_tables()

        for table_name in tables:
            table_info = TableInfo(name=table_name)

            # Get columns
            table_info.columns = self._get_columns(table_name)

            # Get primary keys
            table_info.primary_keys = self._get_primary_keys(table_name)

            # Mark primary key columns
            for pk in table_info.primary_keys:
                if pk in table_info.columns:
                    table_info.columns[pk].is_primary_key = True

            # Get foreign keys
            table_info.foreign_keys = self._get_foreign_keys(table_name)

            schema.tables[table_name] = table_info

        return schema

    def _get_tables(self) -> List[str]:
        """
        Get all user-defined tables in the public schema.

        Returns:
            List of table names
        """
        query = """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """
        results = self.db.execute_query(query)
        return [row["table_name"] for row in results]

    def _get_columns(self, table_name: str) -> Dict[str, ColumnInfo]:
        """
        Get all columns for a table.

        Args:
            table_name: Name of the table

        Returns:
            Dictionary mapping column name to ColumnInfo
        """
        query = """
            SELECT
                column_name,
                data_type,
                is_nullable,
                column_default,
                character_maximum_length
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
            ORDER BY ordinal_position
        """
        results = self.db.execute_query(query, (table_name,))

        columns = {}
        for row in results:
            col_name = row["column_name"]
            columns[col_name] = ColumnInfo(
                name=col_name,
                data_type=row["data_type"],
                is_nullable=row["is_nullable"] == "YES",
                default_value=row["column_default"],
                max_length=row["character_maximum_length"]
            )

        return columns

    def _get_primary_keys(self, table_name: str) -> List[str]:
        """
        Get primary key columns for a table.

        Args:
            table_name: Name of the table

        Returns:
            List of primary key column names
        """
        query = """
            SELECT a.attname AS column_name
            FROM pg_index i
            JOIN pg_attribute a ON a.attrelid = i.indrelid
                AND a.attnum = ANY(i.indkey)
            WHERE i.indrelid = %s::regclass
              AND i.indisprimary
            ORDER BY a.attnum
        """
        results = self.db.execute_query(query, (table_name,))
        return [row["column_name"] for row in results]

    def _get_foreign_keys(self, table_name: str) -> List[ForeignKey]:
        """
        Get foreign key relationships for a table.

        Args:
            table_name: Name of the table

        Returns:
            List of ForeignKey objects
        """
        query = """
            SELECT
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_schema = 'public'
              AND tc.table_name = %s
            ORDER BY kcu.ordinal_position
        """
        results = self.db.execute_query(query, (table_name,))

        foreign_keys = []
        for row in results:
            foreign_keys.append(ForeignKey(
                column=row["column_name"],
                referenced_table=row["foreign_table_name"],
                referenced_column=row["foreign_column_name"]
            ))

        return foreign_keys
