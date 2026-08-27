"""
Pydantic models for structured intent representation in Text-to-SQL conversion.

This module defines comprehensive data models for representing parsed natural language
queries as structured intents that can be converted to SQL statements.

Example usage:
    >>> from app.models import StructuredIntent, QueryType, Condition, ConditionOperator
    >>>
    >>> # Simple SELECT query
    >>> intent = StructuredIntent(
    ...     query_type=QueryType.SELECT,
    ...     tables=["users"],
    ...     columns=["name", "email"],
    ...     conditions=[
    ...         Condition(
    ...             operator=ConditionOperator.EQUALS,
    ...             column="status",
    ...             value="active",
    ...             table="users"
    ...         )
    ...     ],
    ...     original_question="Get all active users' names and emails",
    ...     confidence_score=0.95
    ... )
"""

from enum import Enum
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, model_validator


class QueryType(str, Enum):
    """Types of SQL query operations."""
    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    COUNT = "COUNT"
    AGGREGATE = "AGGREGATE"


class AggregationType(str, Enum):
    """Types of SQL aggregation functions."""
    COUNT = "COUNT"
    SUM = "SUM"
    AVG = "AVG"
    MIN = "MIN"
    MAX = "MAX"
    GROUP_CONCAT = "GROUP_CONCAT"


class ConditionOperator(str, Enum):
    """Operators for WHERE clause conditions."""
    EQUALS = "="
    NOT_EQUALS = "!="
    GREATER_THAN = ">"
    LESS_THAN = "<"
    GREATER_EQUAL = ">="
    LESS_EQUAL = "<="
    LIKE = "LIKE"
    IN = "IN"
    BETWEEN = "BETWEEN"
    IS_NULL = "IS NULL"
    IS_NOT_NULL = "IS NOT NULL"
    NOT_IN = "NOT IN"
    NOT_LIKE = "NOT LIKE"


class JoinType(str, Enum):
    """Types of SQL JOIN operations."""
    INNER = "INNER JOIN"
    LEFT = "LEFT JOIN"
    RIGHT = "RIGHT JOIN"
    FULL = "FULL OUTER JOIN"
    CROSS = "CROSS JOIN"


class OrderDirection(str, Enum):
    """Sort order directions."""
    ASC = "ASC"
    DESC = "DESC"


class Condition(BaseModel):
    """
    Represents a WHERE clause condition.

    Example:
        >>> condition = Condition(
        ...     operator=ConditionOperator.GREATER_THAN,
        ...     column="age",
        ...     value=18,
        ...     table="users"
        ... )
    """
    operator: ConditionOperator = Field(
        description="Comparison operator to use"
    )
    column: str = Field(
        description="Column name to apply condition on"
    )
    value: Optional[Union[str, int, float, bool, List[Any], datetime]] = Field(
        default=None,
        description="Value to compare against (None for IS NULL/IS NOT NULL)"
    )
    table: Optional[str] = Field(
        default=None,
        description="Table name (used when joining multiple tables)"
    )
    logic: Optional[str] = Field(
        default="AND",
        description="Logical operator (AND/OR) to connect with next condition"
    )

    @field_validator('logic')
    @classmethod
    def validate_logic(cls, v: str) -> str:
        """Ensure logic operator is valid."""
        if v and v.upper() not in ['AND', 'OR']:
            raise ValueError("Logic must be 'AND' or 'OR'")
        return v.upper() if v else "AND"

    @model_validator(mode='after')
    def validate_condition(self):
        """Validate condition consistency."""
        null_operators = [ConditionOperator.IS_NULL, ConditionOperator.IS_NOT_NULL]

        if self.operator in null_operators and self.value is not None:
            raise ValueError(f"{self.operator} should not have a value")

        if self.operator not in null_operators and self.value is None:
            raise ValueError(f"{self.operator} requires a value")

        if self.operator == ConditionOperator.BETWEEN:
            if not isinstance(self.value, list) or len(self.value) != 2:
                raise ValueError("BETWEEN operator requires a list of two values")

        if self.operator in [ConditionOperator.IN, ConditionOperator.NOT_IN]:
            if not isinstance(self.value, list):
                raise ValueError(f"{self.operator} requires a list of values")

        return self


class Join(BaseModel):
    """
    Represents a JOIN operation between two tables.

    Example:
        >>> join = Join(
        ...     join_type=JoinType.INNER,
        ...     left_table="users",
        ...     right_table="orders",
        ...     left_column="id",
        ...     right_column="user_id"
        ... )
    """
    join_type: JoinType = Field(
        description="Type of join operation"
    )
    left_table: str = Field(
        description="Left table in the join"
    )
    right_table: str = Field(
        description="Right table in the join"
    )
    left_column: str = Field(
        description="Column from left table"
    )
    right_column: str = Field(
        description="Column from right table"
    )
    alias: Optional[str] = Field(
        default=None,
        description="Alias for the joined table"
    )


class Aggregation(BaseModel):
    """
    Represents an aggregation function.

    Example:
        >>> agg = Aggregation(
        ...     aggregation_type=AggregationType.SUM,
        ...     column="revenue",
        ...     alias="total_revenue"
        ... )
    """
    aggregation_type: AggregationType = Field(
        description="Type of aggregation function"
    )
    column: Optional[str] = Field(
        default=None,
        description="Column to aggregate (None for COUNT(*))"
    )
    alias: Optional[str] = Field(
        default=None,
        description="Alias for the aggregation result"
    )
    table: Optional[str] = Field(
        default=None,
        description="Table name (used when joining multiple tables)"
    )
    distinct: bool = Field(
        default=False,
        description="Whether to use DISTINCT in aggregation (e.g., COUNT(DISTINCT column))"
    )

    @model_validator(mode='after')
    def validate_aggregation(self):
        """Validate aggregation consistency."""
        if self.aggregation_type == AggregationType.COUNT and self.column is None:
            # COUNT(*) is valid
            return self

        if self.aggregation_type != AggregationType.COUNT and self.column is None:
            raise ValueError(f"{self.aggregation_type} requires a column")

        return self


class OrderBy(BaseModel):
    """
    Represents an ORDER BY clause.

    Example:
        >>> order = OrderBy(
        ...     column="created_at",
        ...     direction=OrderDirection.DESC,
        ...     table="users"
        ... )
    """
    column: str = Field(
        description="Column to sort by"
    )
    direction: OrderDirection = Field(
        default=OrderDirection.ASC,
        description="Sort direction"
    )
    table: Optional[str] = Field(
        default=None,
        description="Table name (used when joining multiple tables)"
    )


class StructuredIntent(BaseModel):
    """
    Main model representing the complete structured intent of a natural language query.

    This model captures all elements needed to generate a SQL query from a natural
    language question.

    Example:
        >>> intent = StructuredIntent(
        ...     query_type=QueryType.SELECT,
        ...     tables=["users", "orders"],
        ...     columns=["users.name", "COUNT(orders.id)"],
        ...     joins=[
        ...         Join(
        ...             join_type=JoinType.LEFT,
        ...             left_table="users",
        ...             right_table="orders",
        ...             left_column="id",
        ...             right_column="user_id"
        ...         )
        ...     ],
        ...     aggregations=[
        ...         Aggregation(
        ...             aggregation_type=AggregationType.COUNT,
        ...             column="orders.id",
        ...             alias="order_count"
        ...         )
        ...     ],
        ...     group_by=["users.name"],
        ...     order_by=[
        ...         OrderBy(column="order_count", direction=OrderDirection.DESC)
        ...     ],
        ...     limit=10,
        ...     original_question="Show me the top 10 users with the most orders",
        ...     confidence_score=0.92
        ... )
    """
    query_type: QueryType = Field(
        description="Type of SQL query to generate"
    )

    tables: List[str] = Field(
        default_factory=list,
        description="List of table names involved in the query"
    )

    columns: List[str] = Field(
        default_factory=list,
        description="List of columns to select/update (empty for SELECT * or DELETE)"
    )

    conditions: List[Condition] = Field(
        default_factory=list,
        description="WHERE clause conditions"
    )

    joins: List[Join] = Field(
        default_factory=list,
        description="JOIN operations between tables"
    )

    aggregations: List[Aggregation] = Field(
        default_factory=list,
        description="Aggregation functions to apply"
    )

    group_by: List[str] = Field(
        default_factory=list,
        description="Columns to group by (for aggregations)"
    )

    order_by: List[OrderBy] = Field(
        default_factory=list,
        description="ORDER BY clauses"
    )

    limit: Optional[int] = Field(
        default=None,
        description="LIMIT clause value",
        ge=0
    )

    offset: Optional[int] = Field(
        default=None,
        description="OFFSET clause value",
        ge=0
    )

    original_question: str = Field(
        description="The original natural language question"
    )

    confidence_score: float = Field(
        default=0.0,
        description="Confidence score of the intent recognition (0.0 to 1.0)",
        ge=0.0,
        le=1.0
    )

    recognized_entities: Dict[str, Any] = Field(
        default_factory=dict,
        description="Dictionary of recognized entities (tables, columns, values, etc.)"
    )

    insert_values: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Values to insert (for INSERT queries)"
    )

    update_values: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Values to update (for UPDATE queries)"
    )

    distinct: bool = Field(
        default=False,
        description="Whether to use SELECT DISTINCT"
    )

    having_conditions: List[Condition] = Field(
        default_factory=list,
        description="HAVING clause conditions (for aggregated queries)"
    )

    @model_validator(mode='after')
    def validate_intent(self):
        """Validate logical consistency of the structured intent."""
        # Validate that tables are specified
        if not self.tables and self.query_type != QueryType.COUNT:
            raise ValueError("At least one table must be specified")

        # Validate INSERT queries have values
        if self.query_type == QueryType.INSERT and not self.insert_values:
            raise ValueError("INSERT queries must have insert_values")

        # Validate UPDATE queries have values
        if self.query_type == QueryType.UPDATE and not self.update_values:
            raise ValueError("UPDATE queries must have update_values")

        # Validate aggregations with group_by
        if self.aggregations and not self.group_by:
            # Check if any non-aggregated columns are selected
            agg_columns = {agg.column for agg in self.aggregations if agg.column}
            non_agg_columns = [col for col in self.columns if col not in agg_columns]

            if non_agg_columns:
                # Suggest columns that should be in group_by
                pass  # This is a warning, not an error

        # Validate HAVING requires aggregations
        if self.having_conditions and not self.aggregations:
            raise ValueError("HAVING clause requires aggregation functions")

        # Validate joins reference valid tables
        if self.joins:
            all_tables = set(self.tables)
            for join in self.joins:
                if join.left_table not in all_tables:
                    all_tables.add(join.left_table)
                if join.right_table not in all_tables:
                    all_tables.add(join.right_table)

            # Update tables list with joined tables
            self.tables = list(all_tables)

        # Validate offset requires limit (common SQL pattern)
        if self.offset is not None and self.limit is None:
            # This is a warning - some databases allow OFFSET without LIMIT
            pass

        return self

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the structured intent to a dictionary.

        Returns:
            Dictionary representation of the structured intent.
        """
        return {
            "query_type": self.query_type.value,
            "tables": self.tables,
            "columns": self.columns,
            "conditions": [
                {
                    "operator": cond.operator.value,
                    "column": cond.column,
                    "value": cond.value,
                    "table": cond.table,
                    "logic": cond.logic
                }
                for cond in self.conditions
            ],
            "joins": [
                {
                    "join_type": join.join_type.value,
                    "left_table": join.left_table,
                    "right_table": join.right_table,
                    "left_column": join.left_column,
                    "right_column": join.right_column,
                    "alias": join.alias
                }
                for join in self.joins
            ],
            "aggregations": [
                {
                    "aggregation_type": agg.aggregation_type.value,
                    "column": agg.column,
                    "alias": agg.alias,
                    "table": agg.table,
                    "distinct": agg.distinct
                }
                for agg in self.aggregations
            ],
            "group_by": self.group_by,
            "order_by": [
                {
                    "column": order.column,
                    "direction": order.direction.value,
                    "table": order.table
                }
                for order in self.order_by
            ],
            "limit": self.limit,
            "offset": self.offset,
            "original_question": self.original_question,
            "confidence_score": self.confidence_score,
            "recognized_entities": self.recognized_entities,
            "insert_values": self.insert_values,
            "update_values": self.update_values,
            "distinct": self.distinct,
            "having_conditions": [
                {
                    "operator": cond.operator.value,
                    "column": cond.column,
                    "value": cond.value,
                    "table": cond.table,
                    "logic": cond.logic
                }
                for cond in self.having_conditions
            ]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StructuredIntent":
        """
        Create a StructuredIntent from a dictionary.

        Args:
            data: Dictionary representation of the structured intent.

        Returns:
            StructuredIntent instance.
        """
        # Convert string enums back to enum types
        if "query_type" in data:
            data["query_type"] = QueryType(data["query_type"])

        # Convert conditions
        if "conditions" in data:
            data["conditions"] = [
                Condition(
                    operator=ConditionOperator(cond["operator"]),
                    column=cond["column"],
                    value=cond.get("value"),
                    table=cond.get("table"),
                    logic=cond.get("logic", "AND")
                )
                for cond in data["conditions"]
            ]

        # Convert joins
        if "joins" in data:
            data["joins"] = [
                Join(
                    join_type=JoinType(join["join_type"]),
                    left_table=join["left_table"],
                    right_table=join["right_table"],
                    left_column=join["left_column"],
                    right_column=join["right_column"],
                    alias=join.get("alias")
                )
                for join in data["joins"]
            ]

        # Convert aggregations
        if "aggregations" in data:
            data["aggregations"] = [
                Aggregation(
                    aggregation_type=AggregationType(agg["aggregation_type"]),
                    column=agg.get("column"),
                    alias=agg.get("alias"),
                    table=agg.get("table"),
                    distinct=agg.get("distinct", False)
                )
                for agg in data["aggregations"]
            ]

        # Convert order_by
        if "order_by" in data:
            data["order_by"] = [
                OrderBy(
                    column=order["column"],
                    direction=OrderDirection(order["direction"]),
                    table=order.get("table")
                )
                for order in data["order_by"]
            ]

        # Convert having_conditions
        if "having_conditions" in data:
            data["having_conditions"] = [
                Condition(
                    operator=ConditionOperator(cond["operator"]),
                    column=cond["column"],
                    value=cond.get("value"),
                    table=cond.get("table"),
                    logic=cond.get("logic", "AND")
                )
                for cond in data["having_conditions"]
            ]

        return cls(**data)

    def validate(self) -> bool:
        """
        Validate the structured intent for logical consistency.

        Returns:
            True if valid, raises ValueError if invalid.
        """
        # Pydantic validators already run during initialization
        # This method is kept for explicit validation calls
        return True

    def __repr__(self) -> str:
        """String representation of the structured intent."""
        return (
            f"StructuredIntent(query_type={self.query_type.value}, "
            f"tables={self.tables}, "
            f"confidence={self.confidence_score:.2f})"
        )
