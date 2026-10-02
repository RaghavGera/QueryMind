"""
Intent Extractor Module

This module extracts structured intent from natural language queries using OpenAI's API.
It parses user questions and identifies query components like tables, columns, conditions,
aggregations, and other SQL-related operations.
"""

from typing import Any, Callable, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field
import json
import logging
import re
import random
import time
from app.entity_recognizer import EntityRecognizer
from app.openai_client import (
    OpenAIClientError,
    Provider,
    available_providers,
    configured_providers,
    mark_exhausted,
    seconds_until_available,
)
from datetime import date

import openai

logger = logging.getLogger(__name__)

# Free tiers throttle per minute and cap per day. Policy (per request):
#   * daily-quota 429  -> park that provider, fail over immediately (no retry)
#   * per-minute 429   -> at most ONE short retry honoring Retry-After, then fail over
#   * 5xx / connection -> fail over
#   * other 4xx (bad key, unknown model, rejected request) -> fail over, so one
#     misconfigured provider cannot take /query down while others work
# IntentExtractionError(kind="rate_limited") is raised only when every
# configured provider is rate limited or parked.
LLM_MAX_TOKENS = 800  # Same for every provider. Do not raise without re-verifying free-tier limits.
LLM_BACKOFF_BASE_SECONDS = 1.0
LLM_BACKOFF_CAP_SECONDS = 8.0  # a longer Retry-After means "fail over now", not "wait"
DAILY_QUOTA_DEFAULT_COOLDOWN_SECONDS = 15 * 60

_DAILY_QUOTA = re.compile(
    r"tokens?\s+per\s+day|requests?\s+per\s+day|\bTPD\b|\bRPD\b|per[\s_-]?day|daily",
    re.IGNORECASE,
)
_TRY_AGAIN_IN = re.compile(
    r"try again in\s+(?:(\d+(?:\.\d+)?)h)?\s*(?:(\d+(?:\.\d+)?)m(?!s))?\s*(?:(\d+(?:\.\d+)?)s)?",
    re.IGNORECASE,
)


class IntentExtractionError(Exception):
    """
    Raised when the LLM could not produce a usable intent.

    ``kind`` lets the API layer pick an honest HTTP status without parsing
    messages: ``rate_limited`` (429), ``unavailable`` (503) or
    ``invalid_response`` (502).
    """

    def __init__(self, message: str, kind: str = "invalid_response", retry_after: Optional[float] = None):
        super().__init__(message)
        self.kind = kind
        self.retry_after = retry_after


class _UnusableResponse(Exception):
    """The provider answered, but not with a usable intent."""


def _error_text(exc: Exception) -> str:
    body = getattr(exc, "body", None)
    return f"{exc} {json.dumps(body) if isinstance(body, (dict, list)) else body or ''}"


def _is_daily_quota(exc: Exception) -> bool:
    """A 429 caused by a per-day (or per-month) cap rather than a per-minute one."""
    return bool(_DAILY_QUOTA.search(_error_text(exc)))


def _retry_after_header(exc: Exception) -> Optional[float]:
    headers = getattr(getattr(exc, "response", None), "headers", None)
    if headers is None:
        return None
    try:
        return float(headers.get("retry-after"))
    except (TypeError, ValueError):
        return None


def _daily_cooldown(exc: Exception) -> float:
    """How long to park a provider: the provider's hint, else a default."""
    match = _TRY_AGAIN_IN.search(_error_text(exc))
    if match and any(match.groups()):
        hours, minutes, seconds = (float(g) if g else 0.0 for g in match.groups())
        return hours * 3600 + minutes * 60 + seconds
    header = _retry_after_header(exc)
    if header and header > LLM_BACKOFF_CAP_SECONDS:
        return header
    return DAILY_QUOTA_DEFAULT_COOLDOWN_SECONDS


def _transient_retry_delay(exc: Exception) -> Optional[float]:
    """Delay for the single per-minute retry, or None to fail over right away."""
    header = _retry_after_header(exc)
    if header is not None:
        return header if header <= LLM_BACKOFF_CAP_SECONDS else None
    return LLM_BACKOFF_BASE_SECONDS + random.uniform(0, LLM_BACKOFF_BASE_SECONDS / 4)


def _log_usage(provider: Provider, response: Any) -> None:
    usage = getattr(response, "usage", None)
    logger.info(
        "LLM request served provider=%s model=%s prompt_tokens=%s completion_tokens=%s",
        provider.name,
        provider.model,
        getattr(usage, "prompt_tokens", None),
        getattr(usage, "completion_tokens", None),
    )


def _create_completion_with_retry(
    request: Dict[str, Any],
    parse: Callable[[Any], Any],
) -> Tuple[Any, Provider, Any]:
    """
    Send ``request`` through the provider chain until one returns something
    ``parse`` accepts.

    Returns:
        (parsed result, provider that served it, raw response)

    Raises:
        IntentExtractionError: when every configured provider failed.
    """
    if not configured_providers():
        raise OpenAIClientError(
            "API key not found. Set GEMINI_API_KEY and/or GROQ_API_KEY in your .env file."
        )

    providers = available_providers()
    if not providers:
        wait = seconds_until_available()
        raise IntentExtractionError(
            "Every configured LLM provider has used up its daily quota.",
            kind="rate_limited",
            retry_after=round(wait) if wait else LLM_BACKOFF_CAP_SECONDS,
        )

    failures: List[Tuple[str, str]] = []  # (provider, kind)
    retry_hints: List[float] = []
    for provider in providers:
        retried = False
        while True:
            try:
                response = provider.client.chat.completions.create(
                    model=provider.model,
                    tool_choice=provider.tool_choice,
                    **request,
                )
                _log_usage(provider, response)
                return parse(response), provider, response
            except openai.RateLimitError as exc:
                if _is_daily_quota(exc):
                    cooldown = _daily_cooldown(exc)
                    mark_exhausted(provider.name, cooldown)
                    retry_hints.append(cooldown)
                    failures.append((provider.name, "rate_limited"))
                    break
                delay = _transient_retry_delay(exc)
                if not retried and delay is not None:
                    logger.warning("LLM provider %s rate limited; one retry in %.1fs", provider.name, delay)
                    retried = True
                    time.sleep(delay)
                    continue
                retry_hints.append(delay if delay is not None else LLM_BACKOFF_CAP_SECONDS)
                failures.append((provider.name, "rate_limited"))
                logger.warning("LLM provider %s still rate limited; failing over", provider.name)
                break
            except (openai.APIConnectionError, openai.InternalServerError) as exc:
                failures.append((provider.name, "unavailable"))
                logger.warning("LLM provider %s unavailable (%s); failing over", provider.name, type(exc).__name__)
                break
            except (openai.APIStatusError, _UnusableResponse) as exc:
                failures.append((provider.name, "invalid_response"))
                logger.warning("LLM provider %s failed (%s: %s); failing over",
                               provider.name, type(exc).__name__, str(exc)[:200])
                break

    kinds = {kind for _, kind in failures}
    tried = ", ".join(f"{name} ({kind})" for name, kind in failures)
    if kinds == {"rate_limited"}:
        raise IntentExtractionError(
            f"All LLM providers are rate limited: {tried}",
            kind="rate_limited",
            retry_after=round(min(retry_hints)) if retry_hints else LLM_BACKOFF_CAP_SECONDS,
        )
    if kinds & {"rate_limited", "unavailable"}:
        raise IntentExtractionError(
            f"No LLM provider could answer: {tried}",
            kind="unavailable",
            retry_after=LLM_BACKOFF_CAP_SECONDS,
        )
    raise IntentExtractionError(f"Error extracting intent: no provider returned a usable intent: {tried}")


class QueryIntent(BaseModel):
    """
    Structured representation of a database query intent extracted from natural language.

    Attributes:
        query_type: The type of query operation (e.g., "select", "aggregate", "count", "filter", "join")
        tables: List of table names involved in the query
        columns: List of column names to retrieve or filter on
        conditions: Optional list of WHERE clause conditions as dictionaries
        aggregations: Optional list of aggregation functions (COUNT, SUM, AVG, MAX, MIN, etc.)
        group_by: Optional list of columns to group results by
        order_by: Optional dictionary specifying column and sort direction (asc/desc)
        limit: Optional maximum number of rows to return
    """
    query_type: str = Field(..., description="Type of query: select, aggregate, count, filter, join")
    tables: List[str] = Field(default_factory=list, description="Tables involved in the query")
    columns: List[str] = Field(default_factory=list, description="Columns to retrieve or filter")
    conditions: Optional[List[Dict[str, Any]]] = Field(None, description="WHERE conditions")
    aggregations: Optional[List[str]] = Field(None, description="Aggregation functions like COUNT, SUM, AVG")
    group_by: Optional[List[str]] = Field(None, description="Columns to group by")
    order_by: Optional[Dict[str, str]] = Field(None, description="Column and direction for ordering")
    limit: Optional[int] = Field(None, description="Maximum number of rows to return")
    values: Optional[Dict[str, Any]] = Field(
        None, description="Column -> value map for INSERT (new row) or UPDATE (new values)"
    )
    comparison: Optional[Dict[str, Any]] = Field(
        None, description="Period-over-period comparison: date_column, grain, direction, period"
    )
    top_n_per_group: Optional[Dict[str, Any]] = Field(
        None, description="Top N rows within each group: partition_by, n"
    )


# The Groq free tier allows 8,000 tokens/minute, so every token in this prompt
# costs demo throughput. Keep the base prompt lean; question-specific guidance
# and function-schema slots are added only when the question needs them.
SYSTEM_PROMPT = """You extract structured query intent from a natural-language database question, using the schema provided. Use only real tables and columns, qualified as table.column.

Rules:
- Dates: resolve relative phrases ("last month", "this quarter") to ISO dates (YYYY-MM-DD) from the current date given. BETWEEN takes a list of exactly two values, e.g. ["2026-08-01", "2026-08-31"]. Never pass a relative phrase as a value.
- A concept with no matching column (e.g. "region" when the schema has "country"): use the closest real column; never invent one.
- Metrics are arithmetic over real columns, e.g. revenue = "SUM(order_items.quantity * order_items.unit_price)".
- Whenever you set group_by you MUST also set aggregations. Put only non-aggregated dimension columns in "columns".
- "top N <things>" with no metric ranks by units sold: aggregations ["SUM(order_items.quantity)"], group_by the thing's name column, order_by that aggregation desc, limit N. "top N by <metric>" ranks by that metric.

Examples (arguments only):
Q: What were our top 10 products?
{"query_type": "aggregate", "tables": ["products", "order_items"], "columns": ["products.product_name"], "aggregations": ["SUM(order_items.quantity)"], "group_by": ["products.product_name"], "order_by": {"column": "SUM(order_items.quantity)", "direction": "desc"}, "limit": 10}
Q: Which region generated the most revenue?
{"query_type": "aggregate", "tables": ["customers", "orders", "order_items"], "columns": ["customers.country"], "aggregations": ["SUM(order_items.quantity * order_items.unit_price)"], "group_by": ["customers.country"], "order_by": {"column": "SUM(order_items.quantity * order_items.unit_price)", "direction": "desc"}, "limit": 1}"""

HAVING_GUIDANCE = """
A condition on an aggregate ("more than 5 orders", "over 10,000 in revenue") goes in "conditions" with the aggregate expression as the column, plus the matching group_by:
Q: Which customers have placed more than 5 orders?
{"query_type": "aggregate", "tables": ["customers", "orders"], "columns": ["customers.first_name", "customers.last_name"], "aggregations": ["COUNT(orders.order_id)"], "group_by": ["customers.customer_id", "customers.first_name", "customers.last_name"], "conditions": [{"column": "COUNT(orders.order_id)", "operator": ">", "value": 5}]}
"""

# Sections appended only when the question needs them.
WRITE_GUIDANCE = """
Writes (insert / update):
- "add / create / insert a new <row>" -> query_type "insert", tables [the one table], values {bare column: value} using ONLY values the user stated. Never invent values; omit anything not stated.
- "change / update / set / rename ..." -> query_type "update", tables [the one table], values {column: new value}, and conditions that identify exactly which rows to change.
- "delete / remove" -> query_type "delete" with conditions identifying the rows.
Q: Add a new product called Wireless Mouse in the Accessories category priced at 19.99
{"query_type": "insert", "tables": ["products"], "values": {"product_name": "Wireless Mouse", "category": "Accessories", "price": 19.99}}
Q: Change the price of Laptop 1 to 999
{"query_type": "update", "tables": ["products"], "values": {"price": 999}, "conditions": [{"column": "product_name", "operator": "=", "value": "Laptop 1", "table": "products"}]}
"""

COMPARISON_GUIDANCE = """
Period comparison ("increased / decreased / grew / dropped this quarter|month|year", "compared to last month"):
- Set "comparison" to {"date_column": "<table.column>", "grain": "month|quarter|year", "direction": "increase|decrease|change", "period": "this|last"}. Do NOT compute dates yourself.
- Put the metric in "aggregations" (exactly one), the entities being compared in "columns" and "group_by". Do not add date conditions for the compared periods.
Q: Show customers whose spending increased this quarter
{"query_type": "aggregate", "tables": ["customers", "orders", "order_items"], "columns": ["customers.customer_id", "customers.first_name", "customers.last_name"], "aggregations": ["SUM(order_items.quantity * order_items.unit_price)"], "group_by": ["customers.customer_id", "customers.first_name", "customers.last_name"], "comparison": {"date_column": "orders.order_date", "grain": "quarter", "direction": "increase", "period": "this"}}
"""

PER_GROUP_GUIDANCE = """
Top N per group ("top 5 products by revenue in each category"):
- Set "top_n_per_group" to {"partition_by": ["<table.column of the group>"], "n": N}, with the metric in "aggregations", the entity in "columns" and "group_by", and "order_by" on the metric (descending). Do not set "limit".
Q: What were the top 5 products by revenue in each category?
{"query_type": "aggregate", "tables": ["products", "order_items"], "columns": ["products.category", "products.product_name"], "aggregations": ["SUM(order_items.quantity * order_items.unit_price)"], "group_by": ["products.category", "products.product_name"], "order_by": {"column": "SUM(order_items.quantity * order_items.unit_price)", "direction": "desc"}, "top_n_per_group": {"partition_by": ["products.category"], "n": 5}}
"""

NESTED_GUIDANCE = """
Average/maximum of a per-entity total ("average order value", "average spending per customer"):
- Nest the aggregates: aggregations ["AVG(SUM(<expr>))"] and group_by the entity the inner total is computed for (order -> orders.order_id, customer -> customers.customer_id).
Q: What is the average order value?
{"query_type": "aggregate", "tables": ["orders", "order_items"], "aggregations": ["AVG(SUM(order_items.quantity * order_items.unit_price))"], "group_by": ["orders.order_id"]}
"""

TIME_GROUPING_GUIDANCE = """
Time grouping ("monthly revenue", "orders per month"):
- Use DATE_TRUNC('<day|week|month|quarter|year>', <table.column>) as a column AND in group_by. Never use strftime, MONTH(), EXTRACT or to_char.
Q: Show monthly revenue
{"query_type": "aggregate", "tables": ["orders", "order_items"], "columns": ["DATE_TRUNC('month', orders.order_date)"], "aggregations": ["SUM(order_items.quantity * order_items.unit_price)"], "group_by": ["DATE_TRUNC('month', orders.order_date)"], "order_by": {"column": "DATE_TRUNC('month', orders.order_date)", "direction": "asc"}}
"""

_WRITE_WORDS = re.compile(r"\b(add|insert|create|update|change|set|rename|delete|remove)\b", re.IGNORECASE)
_COMPARISON_WORDS = re.compile(
    r"\b(increased?|decreased?|grew|grown|growth|dropped|declined?|rose|fell|compared|versus|vs)\b",
    re.IGNORECASE,
)
_PER_GROUP_WORDS = re.compile(r"\b(each|every|per)\b", re.IGNORECASE)
_RANKING_WORDS = re.compile(r"\b(top|best|highest)\b", re.IGNORECASE)
_NESTED_WORDS = re.compile(
    r"\baverage\s+(order\s+value|[a-z ]*\bper\b)|\baverage\s+\w+\s+(value|total)\b", re.IGNORECASE
)
_TIME_GROUP_WORDS = re.compile(
    r"\b(monthly|weekly|daily|quarterly|yearly|annual(ly)?|per\s+(day|week|month|quarter|year)|"
    r"by\s+(day|week|month|quarter|year)|each\s+(day|week|month|quarter|year))\b",
    re.IGNORECASE,
)
_HAVING_WORDS = re.compile(
    r"\b(more|less|fewer|greater)\s+than\b|\bover\b|\bat\s+least\b|\bat\s+most\b|\bexceed\w*\b",
    re.IGNORECASE,
)


def build_system_prompt(question: str) -> str:
    """The base prompt plus whichever optional guidance this question needs."""
    prompt = SYSTEM_PROMPT
    if _HAVING_WORDS.search(question):
        prompt += "\n" + HAVING_GUIDANCE
    if _WRITE_WORDS.search(question):
        prompt += "\n" + WRITE_GUIDANCE
    if _COMPARISON_WORDS.search(question):
        prompt += "\n" + COMPARISON_GUIDANCE
    if _PER_GROUP_WORDS.search(question) and _RANKING_WORDS.search(question):
        prompt += "\n" + PER_GROUP_GUIDANCE
    if _NESTED_WORDS.search(question):
        prompt += "\n" + NESTED_GUIDANCE
    if _TIME_GROUP_WORDS.search(question):
        prompt += "\n" + TIME_GROUPING_GUIDANCE
    return prompt


def build_function_schema(question: str) -> dict:
    """
    The extraction function schema. Slots for writes, comparisons and per-group
    ranking are only advertised for questions that can use them.
    """
    properties = {
        "query_type": {
            "type": "string",
            "enum": ["select", "aggregate", "count", "filter", "join", "insert", "update", "delete"],
        },
        "tables": {"type": "array", "items": {"type": "string"}},
        "columns": {"type": "array", "items": {"type": "string"}},
        "conditions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "column": {"type": "string"},
                    "operator": {"type": "string"},
                    # No "type": JSON-schema type unions are rejected by some providers.
                    "value": {"description": "A string, number, boolean or null; a list of exactly two values for BETWEEN"},
                },
            },
            "description": "WHERE conditions (or conditions on an aggregate expression)",
        },
        "aggregations": {"type": "array", "items": {"type": "string"},
                         "description": "e.g. COUNT(t.col), SUM(t.a * t.b)"},
        "group_by": {"type": "array", "items": {"type": "string"}},
        "order_by": {
            "type": "object",
            "properties": {"column": {"type": "string"}, "direction": {"type": "string", "enum": ["asc", "desc"]}},
        },
        "limit": {"type": "integer"},
    }
    if _WRITE_WORDS.search(question):
        properties["values"] = {
            "type": "object",
            "additionalProperties": True,
            "description": "insert/update only: bare column name -> value. Only values the user stated.",
        }
    if _COMPARISON_WORDS.search(question):
        properties["comparison"] = {
            "type": "object",
            "description": "Metric compared between two periods. Keys: date_column, grain (month|quarter|year), direction (increase|decrease|change), period (this|last).",
        }
    if _PER_GROUP_WORDS.search(question) and _RANKING_WORDS.search(question):
        properties["top_n_per_group"] = {
            "type": "object",
            "description": "Top N within each group. Keys: partition_by (list of table.column), n (integer).",
        }
    return {
        "name": "extract_query_intent",
        "description": "Extract structured intent from a natural language database query",
        "parameters": {"type": "object", "properties": properties, "required": ["query_type", "tables"]},
    }


def extract_intent(question: str, schema_context: dict) -> QueryIntent:
    """
    Extract structured query intent from a natural language question.

    Uses the standard ``tools`` API so the model returns arguments matching
    ``build_function_schema``; providers are tried in ``LLM_PROVIDER_ORDER``
    with the failover policy above. Only the tables relevant to the question
    are sent (see ``trim_schema_context``); validation elsewhere still uses
    the full schema.

    Args:
        question: The natural language question from the user
        schema_context: tables, columns and relationships (see ``app.main._schema_context``)

    Returns:
        QueryIntent: A structured representation of the query intent

    Raises:
        IntentExtractionError: If no provider returned a usable intent
    """
    request = build_extraction_request(question, schema_context)
    try:
        intent, _, _ = _create_completion_with_retry(request, parse=_parse_intent)
        return intent
    except IntentExtractionError:
        raise
    except Exception as e:
        raise IntentExtractionError(f"Error extracting intent: {str(e)}") from e


def build_extraction_request(question: str, schema_context: dict, trim: bool = True) -> Dict[str, Any]:
    """
    Provider-independent request body (model and tool_choice are per provider).
    ``trim=False`` sends the full schema (used to measure the trimming saving).
    """
    prompt_schema = trim_schema_context(question, schema_context) if trim else schema_context
    user_prompt = f"""Database Schema:
{_format_schema_context(prompt_schema)}
Current date: {date.today().isoformat()}
User Question: {question}"""
    return {
        "messages": [
            {"role": "system", "content": build_system_prompt(question)},
            {"role": "user", "content": user_prompt},
        ],
        "tools": [{"type": "function", "function": build_function_schema(question)}],
        "temperature": 0.1,  # Low temperature for more deterministic outputs
        "max_tokens": LLM_MAX_TOKENS,
    }


_JSON_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def _parse_intent(response: Any) -> QueryIntent:
    """
    Read the intent from the tool call. With ``tool_choice="auto"`` (Gemini)
    a model may answer with the JSON in the message body instead; accept that
    too. Anything else is unusable and the next provider is tried.
    """
    try:
        message = response.choices[0].message
    except (AttributeError, IndexError, TypeError) as exc:
        raise _UnusableResponse("response has no message") from exc

    tool_calls = getattr(message, "tool_calls", None)
    if tool_calls:
        raw = tool_calls[0].function.arguments
    else:
        content = (getattr(message, "content", None) or "").strip()
        raw = _JSON_FENCE.sub("", content)
        if not raw.startswith("{"):
            raise _UnusableResponse("No tool call in response")

    try:
        return QueryIntent(**json.loads(raw))
    except (ValueError, TypeError) as exc:  # JSONDecodeError and pydantic errors are ValueErrors
        raise _UnusableResponse(f"Failed to parse intent data: {exc}") from exc


# ---------------------------------------------------------------- schema trimming

# Metric words whose columns live in fact tables the question rarely names
# ("revenue per customer" needs order_items even though only "customer" is
# mentioned). When one appears, tables holding such columns are kept too.
_METRIC_WORDS = re.compile(
    r"\b(revenue|sales|spen[dt]\w*|sold|sell\w*|bought|purchas\w*|quantity|units?|"
    r"money|income|earn\w*|value|amount|totals?)\b",
    re.IGNORECASE,
)
_METRIC_COLUMNS = {"quantity", "unit_price", "price", "amount", "total"}


def _parse_relationship(relationship: str) -> Optional[Tuple[str, str]]:
    """'orders.customer_id -> customers.customer_id' -> ('orders', 'customers')"""
    try:
        left, right = (side.strip() for side in relationship.split("->", 1))
        return left.split(".", 1)[0], right.split(".", 1)[0]
    except ValueError:
        return None


def relevant_tables(question: str, schema_context: dict) -> List[str]:
    """
    Tables the question needs: those EntityRecognizer finds (directly or via a
    column), plus metric tables for metric words, plus every table one
    foreign key away. Empty list means "could not tell" -> use the full schema.
    """
    columns = schema_context.get("columns") or {}
    if not columns:
        return []

    entities = EntityRecognizer(columns).recognize_entities(question)
    found = {e.entity_name for e in entities if e.entity_type == "table"}
    found |= {e.table_name for e in entities if e.entity_type == "column" and e.table_name}
    found &= set(columns)
    if not found:
        return []

    if _METRIC_WORDS.search(question):
        found |= {
            table for table, table_columns in columns.items()
            if _METRIC_COLUMNS & {c.lower() for c in table_columns}
        }

    keep = set(found)
    for relationship in schema_context.get("relationships") or []:
        edge = _parse_relationship(relationship)
        if not edge:
            continue
        left, right = edge
        if left in found:
            keep.add(right)
        if right in found:
            keep.add(left)

    return [table for table in columns if table in keep]


def trim_schema_context(question: str, schema_context: dict) -> dict:
    """
    The schema context restricted to ``relevant_tables``. Falls back to the
    full context when nothing is recognised -- never fails closed.
    """
    keep = relevant_tables(question, schema_context)
    if not keep or len(keep) == len(schema_context.get("columns") or {}):
        return schema_context  # nothing recognised, or every table is relevant anyway
    kept = set(keep)
    relationships = []
    for relationship in schema_context.get("relationships") or []:
        edge = _parse_relationship(relationship)
        if edge and edge[0] in kept and edge[1] in kept:
            relationships.append(relationship)
    return {
        "tables": [t for t in schema_context.get("tables", keep) if t in kept],
        "columns": {t: c for t, c in schema_context["columns"].items() if t in kept},
        "relationships": relationships,
    }


def _format_schema_context(schema_context: dict) -> str:
    """
    Compact schema listing for the prompt: one line per table plus the foreign
    keys, e.g. ``orders(order_id, customer_id, order_date, status)``.
    """
    lines = []

    columns = schema_context.get("columns")
    if columns:
        for table, table_columns in columns.items():
            lines.append(f"{table}({', '.join(table_columns)})")
    elif "tables" in schema_context:
        lines.extend(schema_context["tables"])

    relationships = schema_context.get("relationships")
    if relationships:
        lines.append("Foreign keys: " + "; ".join(relationships))

    return "\n".join(lines)


def validate_intent_against_schema(intent: QueryIntent, schema_context: dict) -> tuple[bool, List[str]]:
    """
    Validate that the extracted intent references valid tables and columns from the schema.

    Args:
        intent: The extracted QueryIntent object
        schema_context: Dictionary containing database schema information

    Returns:
        tuple: (is_valid: bool, errors: List[str])

    Example:
        >>> intent = QueryIntent(query_type="select", tables=["users"], columns=["name"])
        >>> schema = {"tables": ["users"], "columns": {"users": ["id", "name", "email"]}}
        >>> is_valid, errors = validate_intent_against_schema(intent, schema)
        >>> print(is_valid)
        True
    """
    errors = []

    # Validate tables
    if "tables" in schema_context:
        valid_tables = set(schema_context["tables"])
        for table in intent.tables:
            if table not in valid_tables:
                errors.append(f"Invalid table: {table}")

    # Validate columns
    if "columns" in schema_context:
        for column in intent.columns:
            # Check if column exists in any of the referenced tables
            found = False
            for table in intent.tables:
                if table in schema_context["columns"]:
                    if column in schema_context["columns"][table]:
                        found = True
                        break
            if not found:
                errors.append(f"Invalid column: {column} not found in tables {intent.tables}")

    # Validate group_by columns
    if intent.group_by:
        for column in intent.group_by:
            if column not in intent.columns:
                errors.append(f"GROUP BY column '{column}' not in SELECT columns")

    is_valid = len(errors) == 0
    return is_valid, errors
