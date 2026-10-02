"""
Intent Extractor Module

This module extracts structured intent from natural language queries using OpenAI's API.
It parses user questions and identifies query components like tables, columns, conditions,
aggregations, and other SQL-related operations.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import json
import logging
import re
import random
import time
from app.openai_client import get_openai_client
from datetime import date

import openai

logger = logging.getLogger(__name__)

# Groq's free tier throttles aggressively (429) and occasionally 5xx's. Retry
# transient failures a few times with exponential backoff before giving up.
LLM_MODEL = "qwen/qwen3.8-27b"
LLM_MAX_TOKENS = 800  # Do not raise without re-verifying against Groq limits (429/502).
LLM_MAX_RETRIES = 3
LLM_BACKOFF_BASE_SECONDS = 1.0
LLM_BACKOFF_CAP_SECONDS = 8.0

_TRANSIENT_ERRORS = (
    openai.RateLimitError,
    openai.APIConnectionError,  # also covers APITimeoutError
    openai.InternalServerError,
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


def _retry_delay(attempt: int, exc: Exception) -> float:
    """Backoff for retry ``attempt`` (0-based), honoring a Retry-After header."""
    response = getattr(exc, "response", None)
    header = getattr(response, "headers", None)
    if header is not None:
        try:
            return min(float(header.get("retry-after")), LLM_BACKOFF_CAP_SECONDS)
        except (TypeError, ValueError):
            pass
    delay = min(LLM_BACKOFF_BASE_SECONDS * (2 ** attempt), LLM_BACKOFF_CAP_SECONDS)
    return delay + random.uniform(0, delay / 4)


def _create_completion_with_retry(client, **kwargs):
    """Call the chat completion API, retrying transient failures with backoff."""
    for attempt in range(LLM_MAX_RETRIES + 1):
        try:
            return client.chat.completions.create(**kwargs)
        except _TRANSIENT_ERRORS as exc:
            if attempt >= LLM_MAX_RETRIES:
                kind = "rate_limited" if isinstance(exc, openai.RateLimitError) else "unavailable"
                raise IntentExtractionError(
                    f"LLM provider is {'rate limiting requests' if kind == 'rate_limited' else 'unavailable'} "
                    f"after {LLM_MAX_RETRIES + 1} attempts: {exc}",
                    kind=kind,
                    retry_after=LLM_BACKOFF_CAP_SECONDS,
                ) from exc
            delay = _retry_delay(attempt, exc)
            logger.warning("LLM call failed (%s); retry %d/%d in %.1fs",
                           type(exc).__name__, attempt + 1, LLM_MAX_RETRIES, delay)
            time.sleep(delay)

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


SYSTEM_PROMPT = """You are an expert at analyzing natural language database queries and extracting structured intent.
Given a user's question and the database schema, identify:
- What type of query it is (select, aggregate, count, filter, join, etc.)
- Which tables and columns are involved
- Any filtering conditions (WHERE clauses)
- Aggregation functions needed
- Grouping and sorting requirements
- Date handling: resolve relative phrases ("last month", "this quarter", "yesterday") into concrete ISO dates (YYYY-MM-DD) using the current date below. BETWEEN requires a list of exactly two values, e.g. ["2026-08-01", "2026-08-31"]. Never pass a relative phrase as a condition value.
- Concept mapping: if the question uses a concept with no matching column (e.g. "region" when the schema only has "country"), map it to the closest available column. If no close match exists, do not invent a column.
- Computed metrics: express metrics like revenue as arithmetic over real columns (e.g. quantity * unit_price). The engine supports arithmetic expressions inside aggregations, so emit them directly, e.g. "SUM(order_items.quantity * order_items.unit_price)".

Aggregation rules (follow strictly):
- Whenever you set group_by you MUST also set aggregations. Never return group_by with an empty aggregations list.
- "top N <things>" / "best-selling <things>" / "most popular <things>" with no metric stated is a ranking by units sold: aggregations ["SUM(order_items.quantity)"], group_by the thing's name column, order_by that aggregation in descending order, and limit N.
- "top N <things> by <metric>" ranks by that metric (revenue = SUM(order_items.quantity * order_items.unit_price)).
- Always qualify columns as table.column when more than one table is involved. For a single-table query, qualified names are still preferred.
- When aggregations are used, put only the non-aggregated dimension columns in "columns"; do not repeat the aggregated column there.
- A condition on an aggregate ("more than 5 orders", "over 10,000 in revenue") goes in "conditions" with the aggregate expression as the column, e.g. {"column": "COUNT(orders.order_id)", "operator": ">", "value": 5}, together with the matching group_by.

Examples (query intent arguments only):
Q: What were our top 10 products?
{"query_type": "aggregate", "tables": ["products", "order_items"], "columns": ["products.product_name"], "aggregations": ["SUM(order_items.quantity)"], "group_by": ["products.product_name"], "order_by": {"column": "SUM(order_items.quantity)", "direction": "desc"}, "limit": 10}
Q: Which region generated the most revenue?
{"query_type": "aggregate", "tables": ["customers", "orders", "order_items"], "columns": ["customers.country"], "aggregations": ["SUM(order_items.quantity * order_items.unit_price)"], "group_by": ["customers.country"], "order_by": {"column": "SUM(order_items.quantity * order_items.unit_price)", "direction": "desc"}, "limit": 1}
Q: How many customers are from each country?
{"query_type": "aggregate", "tables": ["customers"], "columns": ["customers.country"], "aggregations": ["COUNT(customers.customer_id)"], "group_by": ["customers.country"]}
Q: Which customers have placed more than 5 orders?
{"query_type": "aggregate", "tables": ["customers", "orders"], "columns": ["customers.first_name", "customers.last_name"], "aggregations": ["COUNT(orders.order_id)"], "group_by": ["customers.customer_id", "customers.first_name", "customers.last_name"], "conditions": [{"column": "COUNT(orders.order_id)", "operator": ">", "value": 5}]}
Q: Show customers from India.
{"query_type": "select", "tables": ["customers"], "columns": ["customers.first_name", "customers.last_name", "customers.country"], "conditions": [{"column": "country", "operator": "=", "value": "India", "table": "customers"}]}

Use the provided schema to ensure table and column names are valid."""


# Sections appended only when the question needs them: every extra token is
# paid on every request, and the Groq free tier throttles on tokens.
WRITE_GUIDANCE = """
Writes (insert / update):
- "add / create / insert a new <row>" -> query_type "insert", tables [the one table], values {bare column: value} using ONLY values the user stated. Never invent values; omit anything not stated.
- "change / update / set / rename / increase ..." -> query_type "update", tables [the one table], values {column: new value}, and conditions that identify exactly which rows to change.
- "delete / remove" -> query_type "delete" with conditions identifying the rows.
Examples:
Q: Add a new product called Wireless Mouse in the Accessories category priced at 19.99
{"query_type": "insert", "tables": ["products"], "values": {"product_name": "Wireless Mouse", "category": "Accessories", "price": 19.99}}
Q: Change the price of Laptop 1 to 999
{"query_type": "update", "tables": ["products"], "values": {"price": 999}, "conditions": [{"column": "product_name", "operator": "=", "value": "Laptop 1", "table": "products"}]}
"""

_WRITE_WORDS = re.compile(
    r"\b(add|insert|create|update|change|set|rename|delete|remove)\b",
    re.IGNORECASE,
)


def build_system_prompt(question: str) -> str:
    """The base prompt plus whichever optional guidance this question needs."""
    prompt = SYSTEM_PROMPT
    if _WRITE_WORDS.search(question):
        prompt += "\n" + WRITE_GUIDANCE
    return prompt


def extract_intent(question: str, schema_context: dict) -> QueryIntent:
    """
    Extract structured query intent from a natural language question.

    This function uses OpenAI's API with function calling to analyze a user's question
    and extract structured information about what database query they want to perform.
    The schema context helps the model identify valid tables and columns.

    Args:
        question: The natural language question from the user
        schema_context: Dictionary containing database schema information including
                       tables, columns, and relationships

    Returns:
        QueryIntent: A structured representation of the query intent

    Raises:
        Exception: If the OpenAI API call fails or returns invalid data

    Example:
        >>> schema = {
        ...     "tables": ["customers", "orders"],
        ...     "columns": {"customers": ["id", "name", "email"], "orders": ["id", "customer_id", "total"]}
        ... }
        >>> intent = extract_intent("Show me all customers who ordered more than $100", schema)
        >>> print(intent.query_type)
        'filter'
    """
    client = get_openai_client()

    # Prepare the schema information for the prompt
    schema_description = _format_schema_context(schema_context)

    # Define the function schema for structured output
    function_schema = {
        "name": "extract_query_intent",
        "description": "Extract structured intent from a natural language database query",
        "parameters": {
            "type": "object",
            "properties": {
                "query_type": {
                    "type": "string",
                    "enum": ["select", "aggregate", "count", "filter", "join", "insert", "update", "delete"],
                    "description": "The primary type of database operation"
                },
                "tables": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of table names involved in the query"
                },
                "columns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of columns to retrieve or filter on"
                },
                "conditions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "column": {"type": "string"},
                            "operator": {"type": "string"},
                            "value": {"type": ["string", "number", "boolean", "null", "array"],
                                      "description": "Single value, or a list of exactly two values when operator is BETWEEN"}
                        }
                    },
                    "description": "WHERE clause conditions"
                },
                "aggregations": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Aggregation functions like COUNT, SUM, AVG, MAX, MIN"
                },
                "group_by": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Columns to group results by"
                },
                "order_by": {
                    "type": "object",
                    "properties": {
                        "column": {"type": "string"},
                        "direction": {"type": "string", "enum": ["asc", "desc"]}
                    },
                    "description": "Sorting specification"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of rows to return"
                },
                "values": {
                    "type": "object",
                    "additionalProperties": True,
                    "description": "For insert/update only: map of bare column name -> value to write. Only values the user actually stated."
                }
            },
            "required": ["query_type", "tables"]
        }
    }

    user_prompt = f"""Database Schema:
{schema_description}
Current date: {date.today().isoformat()}
User Question: {question}

Extract the structured query intent from this question."""

    try:
        # Call API with function calling (supports both Groq and OpenAI)
        response = _create_completion_with_retry(
            client,
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": build_system_prompt(question)},
                {"role": "user", "content": user_prompt}
            ],
            functions=[function_schema],
            function_call={"name": "extract_query_intent"},
            temperature=0.1,  # Low temperature for more deterministic outputs
            max_tokens=LLM_MAX_TOKENS
        )

        # Extract the function call response
        message = response.choices[0].message

        if not message.function_call:
            raise IntentExtractionError("Error extracting intent: No function call in response")

        # Parse the function arguments
        intent_data = json.loads(message.function_call.arguments)

        # Create and return QueryIntent object
        return QueryIntent(**intent_data)

    except IntentExtractionError:
        raise
    except json.JSONDecodeError as e:
        raise IntentExtractionError(f"Failed to parse intent data: {str(e)}") from e
    except Exception as e:
        raise IntentExtractionError(f"Error extracting intent: {str(e)}") from e


def _format_schema_context(schema_context: dict) -> str:
    """
    Format the schema context into a readable string for the prompt.

    Args:
        schema_context: Dictionary containing schema information

    Returns:
        str: Formatted schema description
    """
    formatted = []

    if "tables" in schema_context:
        formatted.append("Tables:")
        for table in schema_context["tables"]:
            formatted.append(f"  - {table}")

    if "columns" in schema_context:
        formatted.append("\nColumns by Table:")
        for table, columns in schema_context["columns"].items():
            formatted.append(f"  {table}:")
            for column in columns:
                formatted.append(f"    - {column}")

    if "relationships" in schema_context:
        formatted.append("\nRelationships:")
        for rel in schema_context["relationships"]:
            formatted.append(f"  - {rel}")

    return "\n".join(formatted)


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
