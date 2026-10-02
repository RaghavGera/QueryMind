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

import re
from datetime import date
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from app.intent_extractor import QueryIntent
from app.models import (
    Aggregation,
    AggregationType,
    Condition,
    ConditionOperator,
    Join,
    JoinType,
    OrderBy,
    OrderDirection,
    PeriodComparison,
    QueryType,
    StructuredIntent,
    TopNPerGroup,
)
from app.schema import DatabaseSchema
from app.vague_terms import DEFAULTABLE_RANKING, needs_ranking_metric


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

_PLAIN_QUALIFIED = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*")

_AGGREGATION_EXPRESSION = re.compile(
    r"^(COUNT|SUM|AVG|MIN|MAX|GROUP_CONCAT)\s*\(\s*(.*?)\s*\)$",
    re.IGNORECASE,
)


def convert_condition(raw: Dict[str, Any]) -> Condition:
    """Convert one LLM-produced condition dict into a Condition."""
    op_raw = str(raw.get("operator", "=")).strip().lower()
    operator = _OPERATOR_ALIASES.get(op_raw)
    if operator is None:
        raise IntentConversionError(f"Unrecognized condition operator: '{raw.get('operator')}'")

    column = str(raw["column"]).strip()
    table = raw.get("table")
    # The model often emits "customers.signup_date" as the column. Split it so
    # downstream checks (date-column detection, validation) see a bare column.
    if "." in column and not table and _PLAIN_QUALIFIED.fullmatch(column):
        table, column = column.split(".", 1)

    return Condition(
        operator=operator,
        column=column,
        value=raw.get("value"),
        table=table,
    )


def convert_aggregations(
    agg_names: List[str],
    columns: List[str]
) -> Aggregation:
    """
    Convert aggregation specifications from Phase 2 into Aggregation objects.

    Supports both formats:

        ["SUM", "COUNT"]

    and:

        ["SUM(order_items.quantity)", "COUNT(order_items.id)"]

    The latter is useful when the LLM binds the aggregation function
    directly to a column.
    """
    aggregations = []

    expression_columns = []
    plain_columns = []
    for column_name in columns:
        expression_match = _AGGREGATION_EXPRESSION.match(str(column_name).strip())
        if expression_match:
            expression_columns.append((expression_match.group(1), expression_match.group(2)))
        else:
            plain_columns.append(column_name)

    for i, raw_name in enumerate(agg_names):
        name = str(raw_name).strip()

        column = None
        expression_match = _AGGREGATION_EXPRESSION.match(name)
        if expression_match:
            name = expression_match.group(1)
            column = expression_match.group(2)
        else:
            for expression_name, expression_column in expression_columns:
                if expression_name.lower() == name.lower():
                    column = expression_column
                    break
            if column is None and i < len(plain_columns):
                column = plain_columns[i]

        # Handle expressions such as:
        #   SUM(order_items.quantity)
        #   COUNT(order_items.id)
        if "(" in name and name.endswith(")"):
            function_name, explicit_column = name.split("(", 1)
            function_name = function_name.strip()
            explicit_column = explicit_column[:-1].strip()

            # Use the column explicitly supplied by the LLM.
            if explicit_column:
                column = explicit_column

            name = function_name

        agg_type = _AGGREGATION_MAP.get(name.lower())

        if agg_type is None:
            raise IntentConversionError(
                f"Unrecognized aggregation function: '{raw_name}'"
            )

        # COUNT can operate on *.
        if agg_type != AggregationType.COUNT and column is None:
            raise IntentConversionError(
                f"Aggregation '{raw_name}' needs a column to operate on, "
                "but none was provided."
            )

        if column:
            # Sanitize so expression columns (e.g. "order_items.quantity * order_items.unit_price")
            # produce valid aliases. Plain columns are unaffected.
            safe_column = re.sub(r"\W+", "_", column).strip("_")
            alias = f"{name.lower()}_{safe_column}"
        else:
            alias = f"{name.lower()}_all"

        aggregations.append(
            Aggregation(
                aggregation_type=agg_type,
                column=column,
                alias=alias,
            )
        )

    return aggregations


_TOP_N = re.compile(r"\btop\s+(\d+)\b", re.IGNORECASE)


def _resolve_group_table(
    group_column: str, candidate_tables: List[str], schema: DatabaseSchema
) -> Optional[str]:
    """Find the schema table a group-by column (qualified or not) belongs to."""
    if "." in group_column:
        table, column = group_column.split(".", 1)
        info = schema.tables.get(table)
        return table if info and column in info.columns else None
    for table in candidate_tables:
        info = schema.tables.get(table)
        if info and group_column in info.columns:
            return table
    return None


def _default_ranking_metric(
    query_intent: QueryIntent,
    question: str,
    schema: DatabaseSchema,
) -> Optional[Aggregation]:
    """
    Safety net for the most common LLM miss: a ranking question ("top 10
    products") returned with a GROUP BY but no aggregation, which would
    otherwise bounce back to the user with "what aggregation do you want?".

    Rank by units sold -- SUM(<child>.quantity) over the child table that
    references the grouped table -- but only when the schema makes that
    unambiguous (exactly one such child table). Returns None otherwise, so
    genuinely unclear questions still fall through to a clarification.
    """
    if not DEFAULTABLE_RANKING.search(question):
        return None

    group_tables = {
        _resolve_group_table(column, list(query_intent.tables), schema)
        for column in (query_intent.group_by or [])
    }
    if len(group_tables) != 1 or None in group_tables:
        return None
    (group_table,) = group_tables

    children = [
        name for name, info in schema.tables.items()
        if "quantity" in info.columns
        and any(fk.referenced_table == group_table for fk in info.foreign_keys)
    ]
    if len(children) != 1:
        return None

    column = f"{children[0]}.quantity"
    return Aggregation(
        aggregation_type=AggregationType.SUM,
        column=column,
        alias=f"sum_{children[0]}_quantity",
    )


# "how many customers ...", "how many orders were placed ..."
_HOW_MANY = re.compile(r"^\s*how\s+many\b", re.IGNORECASE)


def _apply_anti_join(
    joins: List[Join], conditions: List[Condition], tables: List[str], schema: Optional[DatabaseSchema]
) -> List[Join]:
    """
    "Customers who never placed an order" arrives as ``orders.order_id IS NULL``
    over an INNER JOIN, which can never match. Re-orient it as the anti-join the
    user means: start from the referenced table and LEFT JOIN the child, so the
    IS NULL test sees the unmatched rows.
    """
    if schema is None:
        return joins
    null_tables = set()
    for condition in conditions:
        if condition.operator != ConditionOperator.IS_NULL:
            continue
        if condition.table:
            null_tables.add(condition.table)
        else:
            owners = [
                t for t in tables
                if t in schema.tables and condition.column in schema.tables[t].columns
            ]
            if len(owners) == 1:
                null_tables.add(owners[0])

    rewritten = []
    for join in joins:
        # Joins are (FK holder = left) -> (referenced = right). The null-tested
        # table is the holder; it must hang off the referenced table.
        if join.left_table in null_tables and join.right_table not in null_tables:
            rewritten.append(Join(
                join_type=JoinType.LEFT,
                left_table=join.right_table,
                right_table=join.left_table,
                left_column=join.right_column,
                right_column=join.left_column,
            ))
        else:
            rewritten.append(join)
    return rewritten


# AVG(SUM(order_items.quantity * order_items.unit_price)) -> outer AVG over inner SUM
_NESTED_AGGREGATION = re.compile(
    r"^(COUNT|SUM|AVG|MIN|MAX)\s*\(\s*((?:COUNT|SUM|AVG|MIN|MAX)\s*\(.*\))\s*\)$",
    re.IGNORECASE,
)
_DATE_TRUNC_EXPRESSION = re.compile(
    r"^DATE_TRUNC\(\s*'[a-z]+'\s*,\s*([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?)\s*\)$",
    re.IGNORECASE,
)


def period_bounds(grain: str, offset: int, today: date) -> tuple:
    """
    Half-open [start, end) bounds of the calendar month/quarter/year that is
    ``offset`` periods from the one containing ``today`` (0 = this period,
    -1 = the previous one).
    """
    if grain == "month":
        index = today.year * 12 + (today.month - 1) + offset
        start = date(index // 12, index % 12 + 1, 1)
        end_index = index + 1
        end = date(end_index // 12, end_index % 12 + 1, 1)
    elif grain == "quarter":
        quarter = (today.year * 4 + (today.month - 1) // 3) + offset
        start = date(quarter // 4, (quarter % 4) * 3 + 1, 1)
        end_quarter = quarter + 1
        end = date(end_quarter // 4, (end_quarter % 4) * 3 + 1, 1)
    elif grain == "year":
        start = date(today.year + offset, 1, 1)
        end = date(today.year + offset + 1, 1, 1)
    else:
        raise IntentConversionError(f"Unsupported comparison period '{grain}' (use month, quarter or year).")
    return start, end


def _build_comparison(
    spec: Dict[str, Any], question: str, today: date, assumptions: List[str], clarifications: List[str]
) -> Optional[PeriodComparison]:
    """Turn the extractor's comparison slot into concrete period bounds."""
    date_column = str(spec.get("date_column") or "").strip()
    if not date_column:
        raise IntentConversionError("A period comparison needs a date column to cut periods on.")

    grain = str(spec.get("grain") or "").strip().lower()
    grain = {"monthly": "month", "quarterly": "quarter", "yearly": "year", "annual": "year"}.get(grain, grain)
    if grain not in ("month", "quarter", "year"):
        clarifications.append(
            "Which periods should be compared: month over month, quarter over quarter, or year over year?"
        )
        return None

    direction = str(spec.get("direction") or "change").strip().lower()
    direction = {"increased": "increase", "decreased": "decrease", "up": "increase", "down": "decrease",
                 "grew": "increase", "dropped": "decrease"}.get(direction, direction)
    if direction not in ("increase", "decrease", "change"):
        direction = "change"

    offset = -1 if str(spec.get("period") or "this").strip().lower() in ("last", "previous", "prior") else 0
    current_start, current_end = period_bounds(grain, offset, today)
    previous_start, previous_end = period_bounds(grain, offset - 1, today)

    if offset == 0 and (today - current_start).days + 1 < (current_end - current_start).days:
        assumptions.append(
            f"This {grain} is still in progress (through {today.isoformat()}), so it is compared "
            f"with the full previous {grain}."
        )

    return PeriodComparison(
        date_column=date_column,
        grain=grain,
        direction=direction,
        current_start=current_start.isoformat(),
        current_end=current_end.isoformat(),
        previous_start=previous_start.isoformat(),
        previous_end=previous_end.isoformat(),
    )


def _referenced_tables(
    intent_tables: List[str], query_intent: QueryIntent, aggregations: List[Aggregation]
) -> List[str]:
    """Collect table qualifiers from converted expressions and dimensions."""
    tables = list(intent_tables)
    values = list(query_intent.columns) + list(query_intent.group_by or [])
    if query_intent.order_by:
        values.append(query_intent.order_by.get("column", ""))
    values.extend(str(agg.column) for agg in aggregations if agg.column)
    if query_intent.comparison and query_intent.comparison.get("date_column"):
        values.append(str(query_intent.comparison["date_column"]))
    for value in values:
        expression_match = _AGGREGATION_EXPRESSION.match(str(value).strip())
        if expression_match:
            value = expression_match.group(2)
        trunc_match = _DATE_TRUNC_EXPRESSION.match(str(value).strip())
        if trunc_match:
            value = trunc_match.group(1)
        if "." in value:
            table = value.split(".", 1)[0]
            if table not in tables:
                tables.append(table)
    return tables


def _derive_fk_joins(tables: List[str], schema: Optional[DatabaseSchema]) -> List[Join]:
    """Build joins only for direct foreign-key relationships in the schema."""
    if schema is None:
        return []

    joins = []
    seen = set()
    for left_table in tables:
        table_info = schema.tables.get(left_table)
        if not table_info:
            continue
        for fk in table_info.foreign_keys:
            if fk.referenced_table not in tables:
                continue
            key = (left_table, fk.referenced_table, fk.column, fk.referenced_column)
            if key in seen:
                continue
            joins.append(Join(
                join_type=JoinType.INNER,
                left_table=left_table,
                right_table=fk.referenced_table,
                left_column=fk.column,
                right_column=fk.referenced_column,
            ))
            seen.add(key)
    return joins

_INTEGER_TYPES = {"integer", "bigint", "smallint"}
_DECIMAL_TYPES = {"numeric", "decimal", "real", "double precision"}


def _first_validation_message(exc: ValidationError) -> str:
    errors = exc.errors()
    return errors[0]["msg"].removeprefix("Value error, ") if errors else str(exc)


def _coerce_value(value: Any, table: str, column: str, schema: Optional[DatabaseSchema]) -> Any:
    """Turn a stated value into the column's type; reject what can't be."""
    info = schema.tables.get(table) if schema else None
    col = info.columns.get(column) if info else None
    if col is None or not isinstance(value, str):
        return value
    data_type = col.data_type.lower()
    text = value.strip().replace(",", "")
    try:
        if data_type in _INTEGER_TYPES:
            return int(text)
        if data_type in _DECIMAL_TYPES:
            return float(text)
    except ValueError:
        raise IntentConversionError(f"'{column}' expects a number, but got '{value}'.")
    return value


def _convert_write(
    query_type: QueryType,
    query_intent: QueryIntent,
    original_question: str,
    confidence_score: float,
    schema: Optional[DatabaseSchema],
) -> StructuredIntent:
    """Build an INSERT/UPDATE intent from the extractor's explicit ``values``."""
    verb = query_type.value
    tables = list(dict.fromkeys(query_intent.tables))
    if len(tables) != 1:
        raise IntentConversionError(f"{verb} must target exactly one table.")
    table = tables[0]

    if not query_intent.values:
        raise IntentConversionError(
            f"I couldn't tell which values to {verb.lower()}. "
            "State them explicitly, e.g. \"set the price of Laptop 1 to 999\"."
        )

    values: Dict[str, Any] = {}
    for key, raw in query_intent.values.items():
        name = str(key).strip()
        if "." in name:
            prefix, name = name.split(".", 1)
            if prefix != table:
                raise IntentConversionError(f"Column '{key}' does not belong to {table}.")
        values[name] = _coerce_value(raw, table, name, schema)

    conditions = [convert_condition(c) for c in (query_intent.conditions or [])]
    for condition in conditions:
        if condition.table not in (None, table):
            raise IntentConversionError(
                f"A {verb.lower()} can only filter on {table}, not {condition.table}."
            )
        condition.table = table

    fields = {"insert_values": values} if query_type == QueryType.INSERT else {"update_values": values}
    try:
        return StructuredIntent(
            query_type=query_type,
            tables=[table],
            conditions=conditions,
            original_question=original_question,
            confidence_score=confidence_score,
            **fields,
        )
    except ValidationError as exc:
        raise IntentConversionError(_first_validation_message(exc)) from exc


def convert_query_intent(
    query_intent: QueryIntent,
    original_question: str,
    confidence_score: float = 0.0,
    schema: Optional[DatabaseSchema] = None,
    today: Optional[date] = None,
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

    if query_type in (QueryType.INSERT, QueryType.UPDATE):
        return _convert_write(
            query_type, query_intent, original_question, confidence_score, schema
        )

    # A condition on an aggregate ("more than 5 orders" -> COUNT(...) > 5) is a
    # HAVING clause, not a WHERE clause.
    conditions = []
    having_conditions = []
    for raw_condition in (query_intent.conditions or []):
        converted = convert_condition(raw_condition)
        if _AGGREGATION_EXPRESSION.match(converted.column.strip()):
            having_conditions.append(converted)
        else:
            conditions.append(converted)

    columns = list(query_intent.columns)
    clarifications: List[str] = []
    outer_aggregation: Optional[Aggregation] = None

    agg_specs = list(query_intent.aggregations or [])
    for index, spec in enumerate(agg_specs):
        nested = _NESTED_AGGREGATION.match(str(spec).strip())
        if nested:
            # AVG(SUM(x)) -> inner SUM(x) grouped by the user's grouping, outer AVG.
            outer_function, inner_spec = nested.group(1), nested.group(2).strip()
            inner_function = inner_spec.split("(", 1)[0].strip()
            inner_column = re.sub(r"\W+", "_", inner_spec.split("(", 1)[1].rsplit(")", 1)[0]).strip("_")
            outer_aggregation = Aggregation(
                aggregation_type=_AGGREGATION_MAP[outer_function.lower()],
                column="agg_value",
                alias=f"{outer_function}_{inner_function}_{inner_column}".lower(),
            )
            agg_specs[index] = inner_spec
            columns = [c for c in columns if not _NESTED_AGGREGATION.match(str(c).strip())]
            if not query_intent.group_by:
                clarifications.append(
                    f"The {outer_function.lower()} of the {inner_function.lower()} for each what? "
                    "For example per order or per customer."
                )
            break

    aggregations = []
    if agg_specs:
        aggregations = convert_aggregations(agg_specs, columns)
        # Columns consumed by an aggregation shouldn't also appear as a
        # plain SELECT column (they're expressed via `aggregations` instead).
        # Compare unqualified names too: the model may emit "customer_id" in
        # columns while the aggregation binds "customers.customer_id".
        def _simple_name(name: str) -> str:
            return str(name).split(".")[-1].strip().lower()

        consumed = {a.column for a in aggregations if a.column}
        consumed_simple = {_simple_name(c) for c in consumed}
        columns = [
            c for c in columns
            if c not in consumed
            and _simple_name(c) not in consumed_simple
            and not _AGGREGATION_EXPRESSION.match(str(c).strip())
        ]

    order_by: List[OrderBy] = []
    if query_intent.order_by:
        direction = OrderDirection.DESC if query_intent.order_by.get("direction", "asc").lower() == "desc" else OrderDirection.ASC
        order_by = [OrderBy(column=query_intent.order_by["column"], direction=direction)]

    assumptions: List[str] = []
    limit = query_intent.limit
    if (
        schema is not None
        and query_intent.group_by
        and query_type in (QueryType.SELECT, QueryType.AGGREGATE)
        and needs_ranking_metric(original_question)
    ):
        # "top 10 products" names no metric. Where the schema makes the answer
        # unambiguous (units sold) use it -- and say so. Otherwise do nothing:
        # the AmbiguityDetector will ask which metric the user means.
        default_metric = _default_ranking_metric(query_intent, original_question, schema)
        if default_metric is not None:
            if aggregations:
                used = aggregations[0]
                metric_text = f"{used.aggregation_type.value}({used.column or '*'})"
                assumption = f"No ranking metric was given, so results are ranked by {metric_text}."
            else:
                aggregations = [default_metric]
                order_by = [OrderBy(
                    column=f"SUM({default_metric.column})", direction=OrderDirection.DESC
                )]
                columns = [
                    c for c in columns
                    if str(c).split(".")[-1].strip().lower()
                    != str(default_metric.column).split(".")[-1].strip().lower()
                ]
                metric_text = f"{default_metric.aggregation_type.value}({default_metric.column})"
                assumption = f"No ranking metric was given, so results are ranked by units sold ({metric_text})."
            top_n = _TOP_N.search(original_question)
            if limit is None and top_n:
                limit = int(top_n.group(1))
            assumptions.append(assumption)

    if (
        not aggregations
        and not having_conditions
        and query_type in (QueryType.SELECT, QueryType.COUNT, QueryType.AGGREGATE)
        and _HOW_MANY.match(original_question)
    ):
        # "How many ...?" is a count. The model occasionally returns a plain
        # row listing instead; a count is the only reading of the question.
        aggregations = [Aggregation(aggregation_type=AggregationType.COUNT, column=None, alias="count_all")]
        if not query_intent.group_by:
            columns = []
        assumptions.append("Interpreted 'how many' as a row count.")

    comparison = None
    if query_intent.comparison:
        if len(aggregations) != 1 or not (query_intent.group_by or columns):
            raise IntentConversionError(
                "A period comparison needs one aggregate (e.g. total spending) and what to compare it for."
            )
        comparison = _build_comparison(
            query_intent.comparison, original_question, today or date.today(), assumptions, clarifications
        )
        order_by = []

    group_by = list(query_intent.group_by or [])
    top_n_per_group = None
    if query_intent.top_n_per_group:
        spec = query_intent.top_n_per_group
        partition = [str(c) for c in (spec.get("partition_by") or [])]
        try:
            top_n_per_group = TopNPerGroup(partition_by=partition, n=int(spec.get("n")))
        except (TypeError, ValueError, ValidationError) as exc:
            raise IntentConversionError("Top-N per group needs the grouping column and how many to keep.") from exc
        for column in partition:
            if column not in columns:
                columns.append(column)
            if aggregations and column not in group_by:
                group_by.append(column)
        limit = None  # the per-group cut replaces any overall LIMIT
        if not order_by:
            clarifications.append("What should be ranked within each group (for example revenue or quantity sold)?")

    if outer_aggregation is not None:
        order_by, limit = [], None

    if comparison is None and query_intent.comparison:
        # Comparison period unclear: only the clarification matters.
        order_by = []

    tables = _referenced_tables(list(query_intent.tables), query_intent, aggregations)
    joins = _apply_anti_join(_derive_fk_joins(tables, schema), conditions, tables, schema)

    try:
        return StructuredIntent(
            query_type=query_type,
            tables=tables,
            columns=columns,
            conditions=conditions,
            having_conditions=having_conditions,
            joins=joins,
            aggregations=aggregations,
            group_by=group_by,
            order_by=order_by,
            limit=limit,
            original_question=original_question,
            confidence_score=confidence_score,
            recognized_entities={
                key: value for key, value in (
                    ("assumptions", assumptions), ("clarifications", clarifications)
                ) if value
            },
            comparison=comparison,
            top_n_per_group=top_n_per_group,
            outer_aggregation=outer_aggregation,
        )
    except ValidationError as exc:
        raise IntentConversionError(_first_validation_message(exc)) from exc
