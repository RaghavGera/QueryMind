"""
Quick tweaks: change an answer (MAX -> MIN, sort, limit, a filter value)
without asking the model again (owner decision, 2026-10-20).

An answer carries its checked plan as a signed token plus a list of the
changes it allows. A tweak request sends the token back with *changes only*;
the server verifies the signature, applies the allowed changes to that plan
and the normal generator builds the SQL again (identifiers checked against
the schema, values as parameters, the same read-only role and limits). Users
never send SQL or a plan of their own.
"""

import base64
import hashlib
import hmac
import json
import re
import zlib
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from app.auth import session_secret
from app.explain import words
from app.intent_converter import readable_alias
from app.models import AggregationType, ConditionOperator, OrderDirection, QueryType, StructuredIntent

TOKEN_VERSION = 1
MAX_LIMIT = 1000
_AGGREGATE = re.compile(r"^(COUNT|SUM|AVG|MIN|MAX)\s*\((.*)\)$", re.IGNORECASE)
_NUMERIC = ("integer", "bigint", "smallint", "numeric", "decimal", "real", "double precision")
_COMPARE = ["=", "!=", ">", "<", ">=", "<="]
_TEXT_OPS = ["=", "!="]
TWEAKABLE_TYPES = (QueryType.SELECT, QueryType.COUNT, QueryType.AGGREGATE)
_SORT_WORDS = {
    "number": {"desc": "highest first", "asc": "lowest first"},
    "date": {"desc": "newest first", "asc": "oldest first"},
    "text": {"desc": "Z to A", "asc": "A to Z"},
}


class TweakError(Exception):
    """A tweak that can't be applied; the message says why."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


# --------------------------------------------------------------------------- #
# Signed plan tokens
# --------------------------------------------------------------------------- #

def _key() -> Optional[bytes]:
    secret = session_secret()
    if not secret:
        return None
    return hmac.new(secret.encode(), b"querymind-intent-token-v1", hashlib.sha256).digest()


def tweaks_enabled() -> bool:
    return _key() is not None


def sign_plan(intent: StructuredIntent, workspace_id: str) -> Optional[str]:
    key = _key()
    if key is None:
        return None
    body = json.dumps({"v": TOKEN_VERSION, "ws": workspace_id, "intent": intent.to_dict()},
                      separators=(",", ":"), default=str).encode()
    packed = base64.urlsafe_b64encode(zlib.compress(body, 9)).rstrip(b"=")
    signature = base64.urlsafe_b64encode(hmac.new(key, packed, hashlib.sha256).digest()).rstrip(b"=")
    return f"{packed.decode()}.{signature.decode()}"


def read_plan(token: str) -> Tuple[StructuredIntent, str]:
    """The plan and workspace id inside a token this server signed; TweakError otherwise."""
    key = _key()
    if key is None:
        raise TweakError("Adjusting answers isn't available on this server.", status=503)
    try:
        packed, signature = str(token).split(".", 1)
        expected = base64.urlsafe_b64encode(hmac.new(key, packed.encode(), hashlib.sha256).digest()).rstrip(b"=")
        if not hmac.compare_digest(expected, signature.encode()):
            raise ValueError("signature")
        body = json.loads(zlib.decompress(base64.urlsafe_b64decode(packed + "=" * (-len(packed) % 4))))
        if body.get("v") != TOKEN_VERSION:
            raise ValueError("version")
        return StructuredIntent.from_dict(body["intent"]), str(body["ws"])
    except TweakError:
        raise
    except Exception as exc:
        raise TweakError("This answer can't be adjusted any more; ask the question again.") from exc


# --------------------------------------------------------------------------- #
# What can be changed
# --------------------------------------------------------------------------- #

def _column_type(schema, column: Optional[str], table: Optional[str], tables: List[str]) -> str:
    text = str(column or "").replace('"', "").strip()
    if _AGGREGATE.match(text) or "*" in text or "+" in text:
        return "number"
    if "." in text:
        table, text = text.split(".", 1)
    for name in [table] if table else tables:
        info = schema.tables.get(name) if schema else None
        if info and text in info.columns:
            kind = info.columns[text].data_type.lower()
            if kind.startswith(_NUMERIC):
                return "number"
            if kind.startswith(("date", "timestamp")):
                return "date"
            if kind == "boolean":
                return "boolean"
            return "text"
    return "text"


def _aggregate_options(column: Optional[str], kind: str) -> List[str]:
    if column is None:
        return []
    return ["MAX", "MIN", "AVG", "SUM", "COUNT"] if kind == "number" else ["MAX", "MIN", "COUNT"]


def _operators(kind: str, current: str) -> List[str]:
    if current == "BETWEEN":
        return ["BETWEEN"]
    if kind in ("number", "date"):
        return _COMPARE
    return _TEXT_OPS


def describe(intent: StructuredIntent, schema) -> List[Dict[str, Any]]:
    """The controls an answer offers, as the frontend renders them."""
    if intent.query_type not in TWEAKABLE_TYPES or intent.comparison is not None:
        return []
    controls: List[Dict[str, Any]] = []
    if intent.outer_aggregation is None:
        for i, agg in enumerate(intent.aggregations):
            kind = _column_type(schema, agg.column, None, intent.tables)
            options = _aggregate_options(agg.column, kind)
            if len(options) > 1 and agg.aggregation_type.value in options:
                controls.append({"id": f"agg:{i}", "kind": "aggregate", "label": words(agg.column), "type": kind,
                                 "value": agg.aggregation_type.value, "options": options})
    if intent.order_by:
        order = intent.order_by[0]
        controls.append({"id": "sort", "kind": "sort", "label": words(order.column),
                         "type": _column_type(schema, order.column, order.table, intent.tables),
                         "value": order.direction.value.lower(), "options": ["desc", "asc"]})
    if intent.top_n_per_group is not None:
        per = ", ".join(words(p) for p in intent.top_n_per_group.partition_by)
        controls.append({"id": "per_group", "kind": "limit", "label": f"per {per}",
                         "value": intent.top_n_per_group.n, "min": 1, "max": MAX_LIMIT})
    elif intent.limit is not None or intent.order_by:
        controls.append({"id": "limit", "kind": "limit", "label": "rows", "value": intent.limit,
                         "min": 1, "max": MAX_LIMIT})
    for prefix, conditions in (("where", intent.conditions), ("having", intent.having_conditions)):
        for i, cond in enumerate(conditions):
            if cond.operator in (ConditionOperator.IS_NULL, ConditionOperator.IS_NOT_NULL,
                                 ConditionOperator.IN, ConditionOperator.NOT_IN,
                                 ConditionOperator.LIKE, ConditionOperator.NOT_LIKE):
                continue
            kind = "number" if prefix == "having" else _column_type(schema, cond.column, cond.table, intent.tables)
            if kind == "boolean":
                continue
            controls.append({"id": f"{prefix}:{i}", "kind": "filter", "label": words(cond.column), "type": kind,
                             "operator": cond.operator.value, "operators": _operators(kind, cond.operator.value),
                             "value": cond.value})
    return controls


# --------------------------------------------------------------------------- #
# Applying changes
# --------------------------------------------------------------------------- #

def _coerce(value: Any, kind: str, label: str) -> Any:
    if kind == "number":
        if isinstance(value, bool):
            raise TweakError(f"{label} needs a number.")
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise TweakError(f"{label} needs a number.") from exc
        if number != number or abs(number) > 1e15:  # NaN or absurd
            raise TweakError(f"{label} needs a sensible number.")
        return int(number) if number.is_integer() else number
    if kind == "date":
        try:
            return date.fromisoformat(str(value).strip()).isoformat()
        except ValueError as exc:
            raise TweakError(f"{label} needs a date like 2025-01-31.") from exc
    text = str(value if value is not None else "").strip()
    if not text or len(text) > 200:
        raise TweakError(f"{label} needs a value (up to 200 characters).")
    return text


def apply(intent: StructuredIntent, changes: Dict[str, Any], schema) -> Tuple[StructuredIntent, List[str]]:
    """
    The plan with ``changes`` applied, and a short description of each change.
    Only what ``describe`` offers can change; anything else is a TweakError.
    """
    if not isinstance(changes, dict) or not changes:
        raise TweakError("Choose something to change first.")
    controls = {c["id"]: c for c in describe(intent, schema)}
    data = intent.to_dict()
    summary: List[str] = []
    for control_id, change in changes.items():
        control = controls.get(control_id)
        if control is None:
            raise TweakError("That part of the answer can't be changed.")
        if control["kind"] == "aggregate":
            new = str(change).upper()
            if new not in control["options"]:
                raise TweakError(f"{control['label']} can't use {new}.")
            index = int(control_id.split(":")[1])
            agg = data["aggregations"][index]
            old = agg["aggregation_type"]
            if new == old:
                continue
            agg["aggregation_type"] = new
            agg["alias"] = readable_alias(new.lower(), agg["column"])
            for order in data["order_by"]:  # sorting by that aggregate follows it
                if str(order["column"]).replace(" ", "").upper() == f"{old}({agg['column']})".replace(" ", "").upper():
                    order["column"] = f"{new}({agg['column']})"
            summary.append(f"{new} instead of {old} of {control['label']}")
        elif control["kind"] == "sort":
            new = str(change).lower()
            if new not in ("asc", "desc"):
                raise TweakError("Sort is either highest first or lowest first.")
            if new != control["value"]:
                data["order_by"][0]["direction"] = OrderDirection.DESC.value if new == "desc" else OrderDirection.ASC.value
                summary.append(_SORT_WORDS.get(control["type"], _SORT_WORDS["number"])[new])
        elif control["kind"] == "limit":
            try:
                n = int(change)
            except (TypeError, ValueError) as exc:
                raise TweakError("Show a whole number of rows.") from exc
            if not 1 <= n <= MAX_LIMIT:
                raise TweakError(f"Show between 1 and {MAX_LIMIT:,} rows.")
            if n == control["value"]:
                continue
            if control_id == "per_group":
                data["top_n_per_group"]["n"] = n
                summary.append(f"top {n} {control['label']}")
            else:
                data["limit"] = n
                summary.append(f"top {n}")
        elif control["kind"] == "filter":
            if not isinstance(change, dict):
                raise TweakError(f"Send the new operator and value for {control['label']}.")
            operator = str(change.get("operator", control["operator"])).upper()
            if operator not in control["operators"]:
                raise TweakError(f"{control['label']} can't be compared with {operator}.")
            raw = change.get("value", control["value"])
            if operator == "BETWEEN":
                if not isinstance(raw, list) or len(raw) != 2:
                    raise TweakError(f"{control['label']} needs two values for between.")
                value = [_coerce(v, control["type"], control["label"]) for v in raw]
            else:
                value = _coerce(raw, control["type"], control["label"])
            prefix, index = control_id.split(":")
            target = data["conditions" if prefix == "where" else "having_conditions"][int(index)]
            if operator == target["operator"] and value == target["value"]:
                continue
            target["operator"], target["value"] = operator, value
            shown = " and ".join(str(v) for v in value) if isinstance(value, list) else value
            summary.append(f"{control['label']} {operator} {shown}")
    if not summary:
        raise TweakError("Nothing changed: pick a different value first.")
    try:
        return StructuredIntent.from_dict(data), summary
    except Exception as exc:
        raise TweakError("That combination can't be run; ask a new question instead.") from exc
