"""
Intent Extractor Module

This module extracts structured intent from natural language queries using OpenAI's API.
It parses user questions and identifies query components like tables, columns, conditions,
aggregations, and other SQL-related operations.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import json
from app.openai_client import get_openai_client


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
                            "value": {"type": ["string", "number", "boolean", "null"]}
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
                }
            },
            "required": ["query_type", "tables"]
        }
    }

    # Construct the prompt
    system_prompt = """You are an expert at analyzing natural language database queries and extracting structured intent.
Given a user's question and the database schema, identify:
- What type of query it is (select, aggregate, count, filter, join, etc.)
- Which tables and columns are involved
- Any filtering conditions (WHERE clauses)
- Aggregation functions needed
- Grouping and sorting requirements

Use the provided schema to ensure table and column names are valid."""

    user_prompt = f"""Database Schema:
{schema_description}

User Question: {question}

Extract the structured query intent from this question."""

    try:
        # Call API with function calling (supports both Groq and OpenAI)
        response = client.chat.completions.create(
            model="qwen/qwen3.8-27b",  # Llama 3.1 8B - current Groq model
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            functions=[function_schema],
            function_call={"name": "extract_query_intent"},
            temperature=0.1  # Low temperature for more deterministic outputs
        )

        # Extract the function call response
        message = response.choices[0].message

        if not message.function_call:
            raise Exception("No function call in response")

        # Parse the function arguments
        intent_data = json.loads(message.function_call.arguments)

        # Create and return QueryIntent object
        return QueryIntent(**intent_data)

    except json.JSONDecodeError as e:
        raise Exception(f"Failed to parse intent data: {str(e)}")
    except Exception as e:
        raise Exception(f"Error extracting intent: {str(e)}")


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
