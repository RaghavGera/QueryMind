"""
Intent Conversion: bridges Phase 2's LLM-produced `QueryIntent` (loose,
string-typed) into Phase 3/4's `StructuredIntent` (strict Pydantic model
used by the AmbiguityDetector and SQLGenerator).

This glue didn't exist anywhere in the codebase before Phase 4 -- every
existing test builds a StructuredIntent by hand. A real end-to-end
`/query` endpoint needs something to turn what the LLM returns into what
the rest of the pipeline expects, so that lives here.

Because the LLM's output shape is inherently looser than StructuredIntent
(e.g. aggregations are just function-name strings with no explicit
column/alias binding, and INSERT/UPDATE payload values aren't captured
by the Phase 2 function schema at all), this conversion is best-effort:
it raises `IntentConversionError` with a clear message when it can't
produce something valid, instead of silently guessing at something that
could be wrong.
"""

from typing import Any, Dict, List, Optional

from app.intent_extractor import QueryIntent
from app.models import (
    Aggregation,
    AggregationType,
    Condition,
    ConditionOperator,
    OrderBy,
    OrderDirection,
    QueryType,
    StructuredIntent,
)


class IntentConversionError(Exception):
    """Raised when a QueryIntent cannot be turned into a valid StructuredIntent."""


# Phase 2's query_type strings don't map 1:1 onto QueryType. "filter" and
# "join" are really just SELECTs qualified by conditions/joins.
_QUERY_TYPE_MAP = {
    "select": QueryType.SELECT,
    "filter": QueryType.SELECT,
    "join": QueryType.SELECT,
    "aggregate": QueryType.AGGREGATE,
    "count": QueryType.COUNT,
    "insert": QueryType.INSERT,
    "update": QueryType.UPDATE,
    "delete": QueryType.DELETE,
}

# Normalizes the various ways an LLM might spell an operator into the exact
# symbol ConditionOperator expects.
_OPERATOR_ALIASES = {
    "=": ConditionOperator.EQUALS,
    "==": ConditionOperator.EQUALS,
    "equals": ConditionOperator.EQUALS,
    "eq": ConditionOperator.EQUALS,
    "!=": ConditionOperator.NOT_EQUALS,
    "<>": ConditionOperator.NOT_EQUALS,
    "not_equals": ConditionOperator.NOT_EQUALS,
    ">": ConditionOperator.GREATER_THAN,
    "gt": ConditionOperator.GREATER_THAN,
    "<": ConditionOperator.LESS_THAN,
    "lt": ConditionOperator.LESS_THAN,
    ">=": ConditionOperator.GREATER_EQUAL,
    "gte": ConditionOperator.GREATER_EQUAL,
    "<=": ConditionOperator.LESS_EQUAL,
    "lte": ConditionOperator.LESS_EQUAL,
    "like": ConditionOperator.LIKE,
    "not_like": ConditionOperator.NOT_LIKE,
    "in": ConditionOperator.IN,
    "not_in": ConditionOperator.NOT_IN,
    "between": ConditionOperator.BETWEEN,
    "is_null": ConditionOperator.IS_NULL,
    "is null": ConditionOperator.IS_NULL,
    "is_not_null": ConditionOperator.IS_NOT_NULL,
    "is not null": ConditionOperator.IS_NOT_NULL,
}

_AGGREGATION_MAP = {
    "count": AggregationType.COUNT,
    "sum": AggregationType.SUM,
    "avg": AggregationType.AVG,
    "average": AggregationType.AVG,
    "min": AggregationType.MIN,
    "max": AggregationType.MAX,
    "group_concat": AggregationType.GROUP_CONCAT,
}


def convert_condition(raw: Dict[str, Any]) -> Condition:
    """Convert one LLM-produced condition dict into a Condition."""
    op_raw = str(raw.get("operator", "=")).strip().lower()
    operator = _OPERATOR_ALIASES.get(op_raw)
    if operator is None:
        raise IntentConversionError(f"Unrecognized condition operator: '{raw.get('operator')}'")

    return Condition(
        operator=operator,
        column=raw["column"],
        value=raw.get("value"),
        table=raw.get("table"),
    )


def convert_aggregations(agg_names: List[str], columns: List[str]) -> Aggregation:
    """
    Pair Phase 2's bare aggregation-function names with columns.

    Phase 2's schema only gives aggregation *names* (e.g. "COUNT"), not a
    column/alias binding, so this pairs each aggregation positionally with
    a column from the intent's column list, falling back to COUNT(*) when
    there's no column to pair with.
    """
    aggregations = []
    for i, name in enumerate(agg_names):
        agg_type = _AGGREGATION_MAP.get(str(name).strip().lower())
        if agg_type is None:
            raise IntentConversionError(f"Unrecognized aggregation function: '{name}'")

        column = columns[i] if i < len(columns) else None
        if agg_type != AggregationType.COUNT and column is None:
            raise IntentConversionError(
                f"Aggregation '{name}' needs a column to operate on, but none was provided."
            )

        alias = f"{str(name).lower()}_{column}" if column else f"{str(name).lower()}_all"
        aggregations.append(Aggregation(aggregation_type=agg_type, column=column, alias=alias))

    return aggregations


def convert_query_intent(
    query_intent: QueryIntent,
    original_question: str,
    confidence_score: float = 0.0,
) -> StructuredIntent:
    """
    Convert a Phase 2 QueryIntent (LLM output) into a Phase 3/4 StructuredIntent.

    Args:
        query_intent: The loosely-typed intent extracted by `extract_intent`.
        original_question: The user's original natural language question.
        confidence_score: Optional confidence score to carry over.

    Returns:
        A StructuredIntent ready for ambiguity detection / SQL generation.

    Raises:
        IntentConversionError: If the intent can't be converted (unknown
            query type/operator/aggregation, or a mutation with no values).
    """
    qtype_raw = query_intent.query_type.strip().lower()
    query_type = _QUERY_TYPE_MAP.get(qtype_raw)
    if query_type is None:
        raise IntentConversionError(f"Unrecognized query type: '{query_intent.query_type}'")

    conditions = [convert_condition(c) for c in (query_intent.conditions or [])]

    columns = list(query_intent.columns)
    aggregations = []
    if query_intent.aggregations:
        aggregations = convert_aggregations(query_intent.aggregations, columns)
        # Columns consumed by an aggregation shouldn't also appear as a
        # plain SELECT column (they're expressed via `aggregations` instead).
        consumed = {a.column for a in aggregations if a.column}
        columns = [c for c in columns if c not in consumed]

    order_by: List[OrderBy] = []
    if query_intent.order_by:
        direction = OrderDirection.DESC if query_intent.order_by.get("direction", "asc").lower() == "desc" else OrderDirection.ASC
        order_by = [OrderBy(column=query_intent.order_by["column"], direction=direction)]

    if query_type in (QueryType.INSERT, QueryType.UPDATE):
        # Phase 2's function schema has no slot for insert/update payload
        # values, so there is nothing correct to build here yet -- fail
        # loudly rather than emit a query with fabricated values.
        raise IntentConversionError(
            f"{query_type.value} queries need explicit values, which the current NLU "
            "layer (Phase 2) doesn't extract yet. Provide a StructuredIntent with "
            "insert_values/update_values directly instead of going through natural language."
        )

    return StructuredIntent(
        query_type=query_type,
        tables=list(query_intent.tables),
        columns=columns,
        conditions=conditions,
        aggregations=aggregations,
        group_by=list(query_intent.group_by or []),
        order_by=order_by,
        limit=query_intent.limit,
        original_question=original_question,
        confidence_score=confidence_score,
    )
