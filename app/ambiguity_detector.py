"""
Phase 3: Ambiguity Detection and Clarification Engine

This module detects ambiguities in natural language queries and generates
clarification questions to resolve them before SQL generation.

Ambiguity Types:
1. Multiple table matches (e.g., "employee" could match employees, employee_details)
2. Multiple column matches (e.g., "name" in multiple tables)
3. Unclear relationships (which join path to use)
4. Ambiguous values (e.g., "last month" - which month?)
5. Missing required filters (e.g., DELETE without WHERE)
6. Implicit aggregations (e.g., "revenue by country" - SUM? AVG?)
7. Unclear ordering (e.g., "top customers" - by what metric?)
"""

from enum import Enum
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from pydantic import BaseModel, Field
from datetime import datetime

from app.models import StructuredIntent, QueryType
from app.schema import DatabaseSchema


class AmbiguityType(str, Enum):
    """Types of ambiguities that can be detected."""
    MULTIPLE_TABLE_MATCHES = "multiple_table_matches"
    MULTIPLE_COLUMN_MATCHES = "multiple_column_matches"
    UNCLEAR_RELATIONSHIP = "unclear_relationship"
    AMBIGUOUS_TIME_REFERENCE = "ambiguous_time_reference"
    MISSING_REQUIRED_FILTER = "missing_required_filter"
    IMPLICIT_AGGREGATION = "implicit_aggregation"
    UNCLEAR_ORDERING = "unclear_ordering"
    AMBIGUOUS_VALUE = "ambiguous_value"
    MULTIPLE_JOIN_PATHS = "multiple_join_paths"
    UNCLEAR_GROUPING = "unclear_grouping"


class SeverityLevel(str, Enum):
    """Severity levels for ambiguities."""
    CRITICAL = "critical"  # Must be resolved (e.g., missing WHERE in DELETE)
    HIGH = "high"  # Should be resolved (e.g., multiple table matches)
    MEDIUM = "medium"  # Recommended to resolve (e.g., implicit aggregation)
    LOW = "low"  # Nice to resolve (e.g., unclear ordering)


class Ambiguity(BaseModel):
    """Represents a detected ambiguity in a query."""
    ambiguity_type: AmbiguityType = Field(
        description="Type of ambiguity detected"
    )
    severity: SeverityLevel = Field(
        description="Severity level of the ambiguity"
    )
    description: str = Field(
        description="Human-readable description of the ambiguity"
    )
    clarification_question: str = Field(
        description="Question to ask the user to resolve the ambiguity"
    )
    options: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Possible options/choices to resolve the ambiguity"
    )
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context about the ambiguity"
    )
    suggested_resolution: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Suggested resolution based on heuristics"
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "ambiguity_type": self.ambiguity_type.value,
            "severity": self.severity.value,
            "description": self.description,
            "clarification_question": self.clarification_question,
            "options": self.options,
            "context": self.context,
            "suggested_resolution": self.suggested_resolution
        }


class AmbiguityDetectionResult(BaseModel):
    """Result of ambiguity detection."""
    has_ambiguities: bool = Field(
        description="Whether any ambiguities were detected"
    )
    ambiguities: List[Ambiguity] = Field(
        default_factory=list,
        description="List of detected ambiguities"
    )
    critical_count: int = Field(
        default=0,
        description="Number of critical ambiguities"
    )
    high_count: int = Field(
        default=0,
        description="Number of high severity ambiguities"
    )
    can_proceed: bool = Field(
        default=True,
        description="Whether SQL generation can proceed (no critical ambiguities)"
    )
    original_intent: StructuredIntent = Field(
        description="Original structured intent that was analyzed"
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "has_ambiguities": self.has_ambiguities,
            "ambiguities": [amb.to_dict() for amb in self.ambiguities],
            "critical_count": self.critical_count,
            "high_count": self.high_count,
            "can_proceed": self.can_proceed,
            "original_intent": self.original_intent.to_dict()
        }


class AmbiguityDetector:
    """
    Detects ambiguities in structured intents before SQL generation.

    Example usage:
        >>> detector = AmbiguityDetector(schema)
        >>> result = detector.detect_ambiguities(intent)
        >>> if result.has_ambiguities:
        ...     for ambiguity in result.ambiguities:
        ...         print(ambiguity.clarification_question)
    """

    def __init__(self, schema: DatabaseSchema):
        """
        Initialize the ambiguity detector.

        Args:
            schema: Database schema for validation
        """
        self.schema = schema

    def detect_ambiguities(self, intent: StructuredIntent) -> AmbiguityDetectionResult:
        """
        Detect all ambiguities in a structured intent.

        Args:
            intent: Structured intent to analyze

        Returns:
            AmbiguityDetectionResult with all detected ambiguities
        """
        ambiguities: List[Ambiguity] = []

        # Run all detection checks
        ambiguities.extend(self._check_table_ambiguities(intent))
        ambiguities.extend(self._check_column_ambiguities(intent))
        ambiguities.extend(self._check_relationship_ambiguities(intent))
        ambiguities.extend(self._check_missing_filters(intent))
        ambiguities.extend(self._check_implicit_aggregations(intent))
        ambiguities.extend(self._check_unclear_ordering(intent))
        ambiguities.extend(self._check_time_references(intent))
        ambiguities.extend(self._check_join_paths(intent))

        # Count severity levels
        critical_count = sum(1 for a in ambiguities if a.severity == SeverityLevel.CRITICAL)
        high_count = sum(1 for a in ambiguities if a.severity == SeverityLevel.HIGH)

        # Determine if we can proceed
        can_proceed = critical_count == 0

        return AmbiguityDetectionResult(
            has_ambiguities=len(ambiguities) > 0,
            ambiguities=ambiguities,
            critical_count=critical_count,
            high_count=high_count,
            can_proceed=can_proceed,
            original_intent=intent
        )

    def _check_table_ambiguities(self, intent: StructuredIntent) -> List[Ambiguity]:
        """Check for ambiguous table references."""
        ambiguities = []

        for table in intent.tables:
            # Check if table exists
            if table not in self.schema.tables:
                # Look for similar table names
                similar_tables = self._find_similar_tables(table)

                if len(similar_tables) > 1:
                    ambiguities.append(Ambiguity(
                        ambiguity_type=AmbiguityType.MULTIPLE_TABLE_MATCHES,
                        severity=SeverityLevel.HIGH,
                        description=f"Table '{table}' not found, but multiple similar tables exist",
                        clarification_question=f"Which table did you mean by '{table}'?",
                        options=[
                            {"table_name": t, "description": self._get_table_description(t)}
                            for t in similar_tables
                        ],
                        context={"original_table": table, "matches": similar_tables}
                    ))
                elif len(similar_tables) == 1:
                    # Single match - suggest it
                    ambiguities.append(Ambiguity(
                        ambiguity_type=AmbiguityType.MULTIPLE_TABLE_MATCHES,
                        severity=SeverityLevel.MEDIUM,
                        description=f"Table '{table}' not found",
                        clarification_question=f"Did you mean '{similar_tables[0]}'?",
                        options=[
                            {"table_name": similar_tables[0], "description": self._get_table_description(similar_tables[0])}
                        ],
                        context={"original_table": table},
                        suggested_resolution={"table_name": similar_tables[0]}
                    ))

        return ambiguities

    def _check_column_ambiguities(self, intent: StructuredIntent) -> List[Ambiguity]:
        """Check for ambiguous column references."""
        ambiguities = []

        # Check columns without table qualification
        for column in intent.columns:
            if '.' not in column:
                # Find which tables have this column
                tables_with_column = []
                for table in intent.tables:
                    if table in self.schema.tables:
                        if column in self.schema.tables[table].columns:
                            tables_with_column.append(table)

                if len(tables_with_column) > 1:
                    ambiguities.append(Ambiguity(
                        ambiguity_type=AmbiguityType.MULTIPLE_COLUMN_MATCHES,
                        severity=SeverityLevel.HIGH,
                        description=f"Column '{column}' exists in multiple tables",
                        clarification_question=f"Which table's '{column}' column do you want?",
                        options=[
                            {
                                "qualified_name": f"{table}.{column}",
                                "table": table,
                                "column_type": str(self.schema.tables[table].columns[column].data_type)
                            }
                            for table in tables_with_column
                        ],
                        context={"column": column, "tables": tables_with_column}
                    ))

        return ambiguities

    def _check_relationship_ambiguities(self, intent: StructuredIntent) -> List[Ambiguity]:
        """Check for unclear table relationships."""
        ambiguities = []

        # If multiple tables but no joins specified
        if len(intent.tables) > 1 and not intent.joins:
            # Check if relationships exist
            possible_joins = self._find_possible_joins(intent.tables)

            if len(possible_joins) > 1:
                ambiguities.append(Ambiguity(
                    ambiguity_type=AmbiguityType.UNCLEAR_RELATIONSHIP,
                    severity=SeverityLevel.HIGH,
                    description="Multiple tables involved but relationship is unclear",
                    clarification_question="How should these tables be joined?",
                    options=[
                        {
                            "join": f"{j['left_table']}.{j['left_column']} = {j['right_table']}.{j['right_column']}",
                            "relationship": j.get('relationship_name', 'N/A')
                        }
                        for j in possible_joins
                    ],
                    context={"tables": intent.tables, "possible_joins": possible_joins}
                ))
            elif len(possible_joins) == 0:
                ambiguities.append(Ambiguity(
                    ambiguity_type=AmbiguityType.UNCLEAR_RELATIONSHIP,
                    severity=SeverityLevel.CRITICAL,
                    description="No known relationship found between the tables",
                    clarification_question=f"How are {' and '.join(intent.tables)} related?",
                    options=[],
                    context={"tables": intent.tables}
                ))

        return ambiguities

    def _check_missing_filters(self, intent: StructuredIntent) -> List[Ambiguity]:
        """Check for potentially dangerous queries without filters."""
        ambiguities = []

        # DELETE without WHERE is dangerous
        if intent.query_type == QueryType.DELETE and not intent.conditions:
            ambiguities.append(Ambiguity(
                ambiguity_type=AmbiguityType.MISSING_REQUIRED_FILTER,
                severity=SeverityLevel.CRITICAL,
                description="DELETE query without WHERE clause will remove all rows",
                clarification_question="Are you sure you want to delete ALL rows?",
                options=[
                    {"action": "add_filter", "description": "Add a WHERE condition"},
                    {"action": "confirm_delete_all", "description": "Yes, delete all rows"}
                ],
                context={"query_type": "DELETE", "tables": intent.tables}
            ))

        # UPDATE without WHERE is also dangerous
        if intent.query_type == QueryType.UPDATE and not intent.conditions:
            ambiguities.append(Ambiguity(
                ambiguity_type=AmbiguityType.MISSING_REQUIRED_FILTER,
                severity=SeverityLevel.CRITICAL,
                description="UPDATE query without WHERE clause will update all rows",
                clarification_question="Are you sure you want to update ALL rows?",
                options=[
                    {"action": "add_filter", "description": "Add a WHERE condition"},
                    {"action": "confirm_update_all", "description": "Yes, update all rows"}
                ],
                context={"query_type": "UPDATE", "tables": intent.tables}
            ))

        return ambiguities

    def _check_implicit_aggregations(self, intent: StructuredIntent) -> List[Ambiguity]:
        """Check for implicit or unclear aggregations."""
        ambiguities = []

        # If GROUP BY exists but aggregation type is unclear
        if intent.group_by and not intent.aggregations:
            ambiguities.append(Ambiguity(
                ambiguity_type=AmbiguityType.IMPLICIT_AGGREGATION,
                severity=SeverityLevel.MEDIUM,
                description="Grouping specified but aggregation function unclear",
                clarification_question="What aggregation do you want to perform?",
                options=[
                    {"function": "COUNT", "description": "Count the number of records"},
                    {"function": "SUM", "description": "Sum the values"},
                    {"function": "AVG", "description": "Average the values"},
                    {"function": "MAX", "description": "Maximum value"},
                    {"function": "MIN", "description": "Minimum value"}
                ],
                context={"group_by": intent.group_by}
            ))

        return ambiguities

    def _check_unclear_ordering(self, intent: StructuredIntent) -> List[Ambiguity]:
        """Check for unclear ordering requirements."""
        ambiguities = []

        # If limit is specified but no order_by
        if intent.limit and not intent.order_by:
            # Check if query mentions "top", "best", "highest", etc.
            keywords = ["top", "best", "highest", "lowest", "first", "last"]
            if any(keyword in intent.original_question.lower() for keyword in keywords):
                ambiguities.append(Ambiguity(
                    ambiguity_type=AmbiguityType.UNCLEAR_ORDERING,
                    severity=SeverityLevel.MEDIUM,
                    description="Query requests 'top' results but ordering is unclear",
                    clarification_question="What should the results be ordered by?",
                    options=[
                        {"column": col, "direction": "DESC"}
                        for col in intent.columns[:5]  # Suggest first few columns
                    ],
                    context={"limit": intent.limit, "columns": intent.columns}
                ))

        return ambiguities

    def _check_time_references(self, intent: StructuredIntent) -> List[Ambiguity]:
        """Check for ambiguous time references."""
        ambiguities = []

        # Look for relative time references in conditions
        time_keywords = ["last month", "this month", "last year", "this year", "yesterday", "today"]
        question_lower = intent.original_question.lower()

        for keyword in time_keywords:
            if keyword in question_lower:
                # Check if there's a date condition
                has_date_condition = any(
                    cond.column in self._find_date_columns(intent.tables)
                    for cond in intent.conditions
                )

                if not has_date_condition:
                    ambiguities.append(Ambiguity(
                        ambiguity_type=AmbiguityType.AMBIGUOUS_TIME_REFERENCE,
                        severity=SeverityLevel.HIGH,
                        description=f"Time reference '{keyword}' found but date filter unclear",
                        clarification_question=f"Which date column should '{keyword}' apply to?",
                        options=[
                            {"column": col, "table": table}
                            for table in intent.tables
                            for col in self._find_date_columns([table])
                        ],
                        context={"time_reference": keyword}
                    ))

        return ambiguities

    def _check_join_paths(self, intent: StructuredIntent) -> List[Ambiguity]:
        """Check for multiple possible join paths."""
        ambiguities = []

        if len(intent.tables) > 2:
            # Check if there are multiple ways to join these tables
            join_paths = self._find_all_join_paths(intent.tables)

            if len(join_paths) > 1:
                ambiguities.append(Ambiguity(
                    ambiguity_type=AmbiguityType.MULTIPLE_JOIN_PATHS,
                    severity=SeverityLevel.MEDIUM,
                    description="Multiple ways to join these tables exist",
                    clarification_question="Which join path should be used?",
                    options=[
                        {"path": path["description"], "tables": path["tables"]}
                        for path in join_paths
                    ],
                    context={"tables": intent.tables, "paths": join_paths}
                ))

        return ambiguities

    # Helper methods

    def _find_similar_tables(self, table_name: str) -> List[str]:
        """Find tables with similar names."""
        similar = []
        table_lower = table_name.lower()

        for schema_table in self.schema.tables.keys():
            schema_table_lower = schema_table.lower()

            # Exact match (case-insensitive)
            if table_lower == schema_table_lower:
                return [schema_table]

            # Contains or is contained
            if table_lower in schema_table_lower or schema_table_lower in table_lower:
                similar.append(schema_table)

            # Fuzzy matching (simple Levenshtein-like)
            if self._similarity_score(table_lower, schema_table_lower) > 0.7:
                similar.append(schema_table)

        return similar[:5]  # Return top 5 matches

    def _similarity_score(self, s1: str, s2: str) -> float:
        """Calculate simple similarity score between two strings."""
        if not s1 or not s2:
            return 0.0

        # Simple character overlap ratio
        set1 = set(s1)
        set2 = set(s2)
        overlap = len(set1 & set2)
        total = len(set1 | set2)

        return overlap / total if total > 0 else 0.0

    def _get_table_description(self, table_name: str) -> str:
        """Get a brief description of a table."""
        if table_name in self.schema.tables:
            table_info = self.schema.tables[table_name]
            return f"{len(table_info.columns)} columns, {len(table_info.foreign_keys)} foreign keys"
        return "Unknown table"

    def _find_possible_joins(self, tables: List[str]) -> List[Dict[str, Any]]:
        """Find possible join relationships between tables."""
        joins = []

        for i, table1 in enumerate(tables):
            if table1 not in self.schema.tables:
                continue

            for table2 in tables[i + 1:]:
                if table2 not in self.schema.tables:
                    continue

                # Check foreign keys from table1 to table2
                for fk in self.schema.tables[table1].foreign_keys:
                    if fk.referenced_table == table2:
                        joins.append({
                            "left_table": table1,
                            "left_column": fk.column,
                            "right_table": table2,
                            "right_column": fk.referenced_column,
                            "relationship_name": f"{table1} -> {table2}"
                        })

                # Check foreign keys from table2 to table1
                for fk in self.schema.tables[table2].foreign_keys:
                    if fk.referenced_table == table1:
                        joins.append({
                            "left_table": table2,
                            "left_column": fk.column,
                            "right_table": table1,
                            "right_column": fk.referenced_column,
                            "relationship_name": f"{table2} -> {table1}"
                        })

        return joins

    def _find_date_columns(self, tables: List[str]) -> List[str]:
        """Find date/datetime columns in tables."""
        date_columns = []
        date_types = ["date", "datetime", "timestamp", "time"]

        for table in tables:
            if table in self.schema.tables:
                for col_name, col_info in self.schema.tables[table].columns.items():
                    if any(dt in str(col_info.data_type).lower() for dt in date_types):
                        date_columns.append(col_name)

        return date_columns

    def _find_all_join_paths(self, tables: List[str]) -> List[Dict[str, Any]]:
        """Find all possible join paths for multiple tables."""
        # This is a simplified version - real implementation would use graph traversal
        paths = []

        if len(tables) <= 1:
            return paths

        # For now, just check direct relationships
        possible_joins = self._find_possible_joins(tables)

        if possible_joins:
            paths.append({
                "description": " -> ".join(tables),
                "tables": tables,
                "joins": possible_joins
            })

        return paths


def resolve_ambiguity(
    ambiguity: Ambiguity,
    resolution: Dict[str, Any],
    intent: StructuredIntent
) -> StructuredIntent:
    """
    Resolve an ambiguity by applying the user's choice to the intent.

    Args:
        ambiguity: The ambiguity to resolve
        resolution: User's resolution choice
        intent: Original structured intent

    Returns:
        Updated structured intent with ambiguity resolved
    """
    # Clone the intent
    updated_intent = StructuredIntent.from_dict(intent.to_dict())

    if ambiguity.ambiguity_type == AmbiguityType.MULTIPLE_TABLE_MATCHES:
        # Replace the ambiguous table name
        old_table = ambiguity.context["original_table"]
        new_table = resolution["table_name"]

        updated_intent.tables = [
            new_table if t == old_table else t
            for t in updated_intent.tables
        ]

    elif ambiguity.ambiguity_type == AmbiguityType.MULTIPLE_COLUMN_MATCHES:
        # Replace unqualified column with qualified one
        old_column = ambiguity.context["column"]
        new_column = resolution["qualified_name"]

        updated_intent.columns = [
            new_column if c == old_column else c
            for c in updated_intent.columns
        ]

    # Add more resolution logic for other ambiguity types as needed

    return updated_intent
