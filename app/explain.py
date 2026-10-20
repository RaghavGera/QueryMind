"""
A plain-English description of what a generated query does, built from the
same StructuredIntent the SQL came from (no model call, so it costs nothing
and can't describe something the SQL doesn't do).

    "Adds up quantity × unit price for each country, only where status is
     Completed, highest first, and shows the top result."

With the schema, wording follows each column's type: numbers sort "highest
first", dates "latest first" and compare "after", text sorts "A to Z".
"""

import re
from datetime import date, timedelta
from typing import Any, List, Optional

from app.models import (
    Aggregation, AggregationType, Condition, ConditionOperator, JoinType, OrderDirection, QueryType, StructuredIntent,
)

_DATE_TRUNC = re.compile(r"^DATE_TRUNC\(\s*'([a-z]+)'\s*,\s*(.+?)\s*\)$", re.IGNORECASE)
_AGGREGATE = re.compile(r"^(COUNT|SUM|AVG|MIN|MAX)\s*\((.*)\)$", re.IGNORECASE)
_NUMERIC = ("integer", "bigint", "smallint", "numeric", "decimal", "real", "double precision")
_DATES = ("date", "timestamp")


def words(column: Optional[str]) -> str:
    """'order_items.unit_price' -> 'unit price'; "DATE_TRUNC('month', orders.order_date)" -> 'month of order date'."""
    text = str(column or "").strip().replace('"', "")
    trunc = _DATE_TRUNC.match(text)
    if trunc:
        return f"{trunc.group(1).lower()} of {words(trunc.group(2))}"
    aggregate = _AGGREGATE.match(text)
    if aggregate:
        return _aggregate_phrase(aggregate.group(1).upper(), aggregate.group(2), noun=True)
    out = []
    for part in re.split(r"\s*([*+/-])\s*", text):
        if part in ("*", "+", "-", "/"):
            out.append({"*": "×", "+": "+", "-": "−", "/": "÷"}[part])
        else:
            out.append(part.split(".")[-1].replace("_", " ").strip())
    return " ".join(p for p in out if p)


def _singular(name: str) -> str:
    if name.endswith("ies"):
        return name[:-3] + "y"
    if name.endswith("s") and not name.endswith("ss"):
        return name[:-1]
    return name


def _table_noun(column: Optional[str]) -> str:
    """COUNT(customers.customer_id) counts customers."""
    text = str(column or "").replace('"', "")
    return text.split(".")[0].replace("_", " ") if "." in text else "rows"


def _aggregate_phrase(function: str, column: Optional[str], noun: bool = False) -> str:
    if function == "COUNT":
        return f"the number of {_table_noun(column)}" if noun else f"counts {_table_noun(column)}"
    what = words(column)
    as_noun, as_verb = {
        "SUM": ("the total of", "adds up"), "AVG": ("the average", "averages"),
        "MIN": ("the lowest", "finds the lowest"), "MAX": ("the highest", "finds the highest"),
    }.get(function, (function.lower(), function.lower()))
    return f"{as_noun} {what}" if noun else f"{as_verb} {what}"


def _aggregation(agg: Aggregation, noun: bool = False) -> str:
    return _aggregate_phrase(agg.aggregation_type.value, agg.column, noun=noun)


def _join(items: List[str]) -> str:
    items = [i for i in items if i]
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


class _Types:
    """Column types from the schema (when there is one)."""

    def __init__(self, intent: StructuredIntent, schema):
        self.intent, self.schema = intent, schema

    def of(self, column: Optional[str], table: Optional[str] = None) -> str:
        text = str(column or "").replace('"', "").strip()
        if _DATE_TRUNC.match(text):
            return "date"
        if _AGGREGATE.match(text):
            return "numeric"
        if self.schema is None:
            return ""
        if "." in text:
            table, text = text.split(".", 1)
        for name in [table] if table else self.intent.tables:
            info = self.schema.tables.get(name)
            if info and text in info.columns:
                kind = info.columns[text].data_type.lower()
                if kind.startswith(_NUMERIC):
                    return "numeric"
                if kind.startswith(_DATES):
                    return "date"
                return "text"
        return ""

    def key_of(self, table: str) -> str:
        info = self.schema.tables.get(table) if self.schema else None
        if info and info.primary_keys:
            return info.primary_keys[0]
        return f"{_singular(table)}_id"


def _value(value: Any) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float) and value.is_integer():
        return f"{int(value):,}"
    if isinstance(value, (int, float)):
        return f"{value:,}"
    return str(value)


def _condition(cond: Condition, types: _Types) -> str:
    column = words(cond.column)
    op, value = cond.operator, cond.value
    dated = types.of(cond.column, cond.table) == "date"
    if op == ConditionOperator.IS_NULL:
        return f"{column} is empty"
    if op == ConditionOperator.IS_NOT_NULL:
        return f"{column} is filled in"
    if op == ConditionOperator.BETWEEN and isinstance(value, list) and len(value) == 2:
        return f"{column} is between {_value(value[0])} and {_value(value[1])}"
    if op in (ConditionOperator.IN, ConditionOperator.NOT_IN):
        items = value if isinstance(value, list) else [value]
        return f"{column} is {'not ' if op == ConditionOperator.NOT_IN else ''}one of {', '.join(_value(v) for v in items)}"
    if op in (ConditionOperator.LIKE, ConditionOperator.NOT_LIKE):
        text = str(value)
        core = text.strip("%")
        kind = "contains" if text.startswith("%") and text.endswith("%") else (
            "starts with" if text.endswith("%") else "ends with" if text.startswith("%") else "matches")
        if op == ConditionOperator.NOT_LIKE:
            kind = {"contains": "does not contain", "starts with": "does not start with",
                    "ends with": "does not end with", "matches": "does not match"}[kind]
        return f"{column} {kind} {core}"
    verbs = {
        ConditionOperator.EQUALS: "is", ConditionOperator.NOT_EQUALS: "is not",
        ConditionOperator.GREATER_THAN: "is after" if dated else "is more than",
        ConditionOperator.LESS_THAN: "is before" if dated else "is less than",
        ConditionOperator.GREATER_EQUAL: "is on or after" if dated else "is at least",
        ConditionOperator.LESS_EQUAL: "is on or before" if dated else "is at most",
    }
    return f"{column} {verbs.get(op, op.value)} {_value(value)}"


def _groups(group_by: List[str], types: _Types) -> List[str]:
    """'customers.customer_id, customers.first_name' -> ['customer']: a table's key stands for the whole row."""
    def split(column):
        text = str(column).replace('"', "")
        return text.split(".", 1) if "." in text and not _DATE_TRUNC.match(text) else (None, text)

    keyed = {table for table, name in map(split, group_by) if table and name in (types.key_of(table), "id")}
    out = []
    for column in group_by:
        table, _ = split(column)
        label = _singular(table).replace("_", " ") if table in keyed else words(column)
        if label and label not in out:
            out.append(label)
    return out


def _anti_join(intent: StructuredIntent) -> Optional[str]:
    """'customers with no orders' for the LEFT JOIN ... IS NULL shape."""
    for join in intent.joins:
        if join.join_type == JoinType.LEFT:
            for cond in intent.conditions:
                if cond.operator == ConditionOperator.IS_NULL and (
                    cond.table == join.right_table or str(cond.column).startswith(f"{join.right_table}.")
                ):
                    return f"{join.left_table.replace('_', ' ')} with no {join.right_table.replace('_', ' ')}"
    return None


def _day_before(iso: str) -> str:
    """Comparison periods end exclusively (the next period's start); show the last day instead."""
    try:
        return (date.fromisoformat(iso) - timedelta(days=1)).isoformat()
    except ValueError:
        return iso


def explain_intent(intent: StructuredIntent, schema=None) -> str:
    """One plain sentence describing the SELECT that ``intent`` produces."""
    if intent.query_type not in (QueryType.SELECT, QueryType.COUNT, QueryType.AGGREGATE):
        return ""
    types = _Types(intent, schema)
    anti = _anti_join(intent)
    conditions = [c for c in intent.conditions if not (anti and c.operator == ConditionOperator.IS_NULL)]
    groups = _groups(intent.group_by, types)

    # What it computes, and for what.
    if intent.outer_aggregation is not None and intent.aggregations:
        outer = intent.outer_aggregation.aggregation_type
        verb = {AggregationType.AVG: "averages", AggregationType.MAX: "takes the highest of",
                AggregationType.MIN: "takes the lowest of", AggregationType.SUM: "adds up"}.get(outer, outer.value.lower())
        noun = "totals" if intent.aggregations[0].aggregation_type == AggregationType.SUM else "results"
        per = f" for each {_join(groups)}" if groups else ""
        action = f"Works out {_aggregation(intent.aggregations[0], noun=True)}{per}, then {verb} those {noun}"
    else:
        if intent.aggregations:
            action = _join([_aggregation(a) for a in intent.aggregations])
            action = action[0].upper() + action[1:]
            if anti:
                action += f" for {anti}"
        else:
            shown = [words(c) for c in intent.columns if words(c)]
            subject = anti or (intent.tables[0].replace("_", " ") if intent.tables else "rows")
            action = f"Lists {_join(shown)} of {subject}" if shown else f"Lists every column of {subject}"
        if groups:
            action += f" for each {_join(groups)}"

    parts = [action]
    if conditions:
        parts.append("only where " + _join([_condition(c, types) for c in conditions]))
    if intent.comparison is not None:
        c = intent.comparison
        change = {"increase": "went up", "decrease": "went down"}.get(c.direction, "changed")
        parts.append(
            f"comparing {c.current_start} to {_day_before(c.current_end)} with "
            f"{c.previous_start} to {_day_before(c.previous_end)} and keeping those where it {change}"
        )
    if intent.having_conditions:
        parts.append("keeping only results where " + _join([_condition(c, types) for c in intent.having_conditions]))

    if intent.order_by and intent.comparison is None:
        order = intent.order_by[0]
        descending = order.direction == OrderDirection.DESC
        kind = types.of(order.column)
        if _AGGREGATE.match(str(order.column).replace('"', "")):
            parts.append("highest first" if descending else "lowest first")
        elif _DATE_TRUNC.match(str(order.column).replace('"', "")):
            parts.append("newest first" if descending else "in date order")
        elif kind == "numeric":
            parts.append(f"sorted by {words(order.column)}, {'highest' if descending else 'lowest'} first")
        elif kind == "date":
            parts.append(f"{'latest' if descending else 'earliest'} {words(order.column)} first")
        else:
            parts.append(f"sorted by {words(order.column)}, {'Z to A' if descending else 'A to Z'}")
    if intent.top_n_per_group is not None:
        per = _join([words(p) for p in intent.top_n_per_group.partition_by])
        parts.append(f"keeping the top {intent.top_n_per_group.n} in each {per}")
    elif intent.limit is not None:
        if intent.limit == 1 and intent.order_by:
            parts.append("and shows the top result")
        else:
            parts.append(f"and shows {'the top' if intent.order_by else 'the first'} {intent.limit:,}")

    return ", ".join(parts) + "."
