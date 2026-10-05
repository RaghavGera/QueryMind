"""
FastAPI application entry point.

Phase 1 provided schema introspection endpoints. This adds a Phase 2-4
`/query` endpoint that chains the whole pipeline together:

    question -> extract_intent (Phase 2, LLM) -> convert to StructuredIntent
             -> AmbiguityDetector (Phase 3) -> SQLGenerator (Phase 4)

The endpoint never executes the generated SQL -- it returns it (with its
parameters) for the caller to run, along with whatever clarification is
needed if the pipeline couldn't safely produce a query.
"""

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import logging
import os

from app.ambiguity_detector import AmbiguityDetector
from app import writes
from app.database import Database, WriteConflictError, get_db, init_db
from app.intent_converter import IntentConversionError, convert_query_intent
from app.intent_extractor import IntentExtractionError, extract_intent
from app.models import QueryType
from app.schema import DatabaseSchema, SchemaIntrospector
from app.sql_generator import SQLGenerator

logger = logging.getLogger(__name__)

# Uvicorn only configures its own loggers; without this the app's INFO lines
# (e.g. "LLM request served provider=...") never reach the Render logs.
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").strip().upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

# Initialize FastAPI app
app = FastAPI(
    title="QueryMind API",
    description="Natural language to SQL",
    version="0.5.0"
)

cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "BACKEND_CORS_ORIGINS",
        "http://localhost:5173,http://localhost:4173,https://query-mind-tawny.vercel.app",
    ).split(",")
    if origin.strip()
]

# Vercel also serves every deployment at its own URL (query-mind-<hash>-....vercel.app,
# query-mind-git-<branch>-....vercel.app). A browser on one of those, or on a local dev
# server at 127.0.0.1, was refused by CORS and showed "Could not reach the backend".
cors_origin_regex = os.getenv(
    "BACKEND_CORS_ORIGIN_REGEX",
    r"https://query-mind(-[a-z0-9-]+)?\.vercel\.app|http://(localhost|127\.0\.0\.1):\d+",
) or None

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=cors_origin_regex,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Initialize database on application startup."""
    global db_instance
    db_instance = init_db()
    print("✓ Database initialized")
    print(f"✓ Connected to {db_instance.config.database} on {db_instance.config.host}")


def _schema_context(schema: DatabaseSchema) -> dict:
    relationships = []

    for table_name, table in schema.tables.items():
        for fk in table.foreign_keys:
            relationships.append(
                f"{table_name}.{fk.column} -> "
                f"{fk.referenced_table}.{fk.referenced_column}"
            )

    return {
        "tables": list(schema.tables.keys()),

        "columns": {
            name: list(table.columns.keys())
            for name, table in schema.tables.items()
        },

        "relationships": relationships,
    }


class QueryRequest(BaseModel):
    question: str
    clarification_context: str | None = None
    # False: answer ambiguous questions with the best interpretation and report
    # it as a warning instead of asking (critical ambiguities still block).
    strict: bool = True
    allow_full_table_write: bool = False
    # The caller's opt-in to writes; a write also needs QUERYMIND_ENABLE_WRITES.
    allow_writes: bool = True


def _error_response(
    status_code: int,
    message: str,
    details: str | None = None,
    **extra,
) -> JSONResponse:
    """
    Structured error body. ``error`` is the human-readable message the
    frontend shows; the empty ``result`` keeps the response shape stable.
    """
    content = {
        "status": "error",
        "error": message,
        "result": {"columns": [], "rows": []},
        **extra,
    }
    if details:
        content["details"] = details
    return JSONResponse(status_code=status_code, content=content)


# How an LLM failure kind maps onto an honest HTTP status.
_EXTRACTION_ERROR_STATUS = {
    "rate_limited": (429, "The language model is rate limited right now. Please retry in a few seconds."),
    "unavailable": (503, "The language model is temporarily unavailable. Please retry shortly."),
    "invalid_response": (502, "Natural-language intent could not be extracted."),
}


@app.post("/query")
async def run_query(
    request: QueryRequest,
    db: Database = Depends(get_db)
):
    question = request.question.strip()

    if not question:
        return JSONResponse(
            status_code=400,
            content={"error": "Question cannot be empty."}
        )

    if request.clarification_context:
        question = (
            f"{question}\n\n"
            f"User clarification: "
            f"{request.clarification_context.strip()}"
        )

    try:
        return _run_pipeline(question, request, db)
    except Exception as exc:  # Last-resort guard: never leak a traceback.
        logger.exception("Unhandled error while answering %r", question)
        return _error_response(
            500,
            "Something went wrong while processing the question.",
            details=type(exc).__name__,
        )


def _run_pipeline(question: str, request: QueryRequest, db: Database):
    try:
        schema = SchemaIntrospector(db).introspect()
    except Exception as exc:
        return _error_response(
            500, "Database schema could not be inspected.", details=str(exc)
        )

    try:
        query_intent = extract_intent(
            question,
            _schema_context(schema)
        )
    except IntentExtractionError as exc:
        status_code, message = _EXTRACTION_ERROR_STATUS.get(
            exc.kind, _EXTRACTION_ERROR_STATUS["invalid_response"]
        )
        extra = {"retry_after": exc.retry_after} if exc.retry_after else {}
        return _error_response(status_code, message, details=str(exc), **extra)
    except Exception as exc:
        return _error_response(
            502, "Natural-language intent could not be extracted.", details=str(exc)
        )

    try:
        structured_intent = convert_query_intent(
            query_intent,
            question,
            schema=schema,
        )
    except IntentConversionError as exc:
        return _error_response(
            422,
            "The extracted intent could not be converted into a safe SQL plan.",
            details=str(exc),
        )

    generator = SQLGenerator(
        schema,
        AmbiguityDetector(schema),
        strict=request.strict,
    )

    generated = generator.generate(
        structured_intent,
        allow_full_table_write=request.allow_full_table_write,
    )

    payload = generated.to_dict()

    # Assumptions the converter made on the user's behalf (e.g. what "top
    # products" was ranked by) are surfaced, never applied silently.
    assumptions = structured_intent.recognized_entities.get("assumptions", [])
    if assumptions:
        payload["warnings"] = list(payload.get("warnings", [])) + list(assumptions)

    succeeded = generated.status.value in {"success", "success_with_warnings"} and generated.sql

    if succeeded and structured_intent.query_type in (QueryType.INSERT, QueryType.UPDATE):
        return _prepare_write(structured_intent, generated, generator, payload, db, request.allow_writes)

    if succeeded and structured_intent.query_type == QueryType.DELETE:
        return {
            **payload,
            "status": "blocked",
            "sql": None,
            "params": [],
            "error_message": "Deleting data through natural language is not supported.",
            "result": {"columns": [], "rows": []},
        }

    if succeeded:
        logger.debug("Generated SQL: %s | params: %r", generated.sql, generated.params)
        try:
            rows = db.execute_query(
                generated.sql,
                tuple(generated.params)
            )
        except Exception as exc:
            return {
                "status": "error",
                "error": "Generated SQL could not be executed.",
                "details": str(exc),
                "sql": generated.sql,
                "params": generated.params,
                "result": {"columns": [], "rows": []},
            }

        columns = (
            list(rows[0].keys())
            if rows
            else []
        )

        payload["result"] = {
            "columns": columns,
            "rows": rows,
        }

    else:
        payload["result"] = {
            "columns": [],
            "rows": [],
        }

    return payload


def _prepare_write(intent, generated, generator, payload: dict, db: Database, allow_writes: bool = True) -> dict:
    """
    Turn a generated INSERT/UPDATE into a confirmation request. Nothing is
    executed here: the caller must POST the token to /query/confirm.
    """
    affected = None
    if intent.query_type == QueryType.UPDATE:
        count_sql, count_params = generator.build_affected_rows_sql(intent)
        try:
            affected = db.execute_query(count_sql, tuple(count_params))[0]["affected_rows"]
        except Exception as exc:
            return {
                "status": "error",
                "error": "Could not preview which rows would change.",
                "details": str(exc),
                "result": {"columns": [], "rows": []},
            }
        if affected == 0:
            return {
                "status": "error",
                "error": "No rows match that description, so there is nothing to update.",
                "sql": generated.sql,
                "params": generated.params,
                "result": {"columns": [], "rows": []},
            }

    payload["preview"] = writes.describe_write(intent, affected)
    payload["result"] = {"columns": [], "rows": []}

    if not writes.writes_enabled():
        payload["status"] = "blocked"
        payload["error_message"] = (
            "Write queries are disabled on this deployment. This is the change that "
            "would have been proposed; nothing was executed."
        )
        payload["writes_enabled"] = False
        return payload

    if not allow_writes:
        payload["status"] = "blocked"
        payload["error_message"] = (
            "Write queries are turned off in Settings. This is the change that would "
            "have been proposed; nothing was executed."
        )
        payload["writes_enabled"] = True
        return payload

    payload["status"] = "needs_confirmation"
    payload["writes_enabled"] = True
    payload["confirmation_token"] = writes.issue_token(
        generated.sql,
        generated.params,
        expected_rows=1 if intent.query_type == QueryType.INSERT else affected,
    )
    payload["expires_in"] = writes.TOKEN_TTL_SECONDS
    return payload


class ConfirmRequest(BaseModel):
    confirmation_token: str


@app.post("/query/confirm")
async def confirm_write(request: ConfirmRequest, db: Database = Depends(get_db)):
    """Execute a previously previewed INSERT/UPDATE, exactly as shown."""
    if not writes.writes_enabled():
        return _error_response(403, "Write queries are disabled on this deployment.")

    try:
        authorized = writes.redeem_token(request.confirmation_token)
    except writes.ConfirmationError as exc:
        return _error_response(400, str(exc))

    try:
        affected = db.execute_write(
            authorized["sql"],
            tuple(authorized["params"]),
            expected_rows=authorized["expected_rows"],
        )
    except WriteConflictError as exc:
        return _error_response(409, str(exc))
    except ValueError as exc:
        return _error_response(400, str(exc))
    except Exception as exc:
        logger.exception("Confirmed write failed")
        return _error_response(
            500, "The database rejected the change.", details=str(exc).splitlines()[0][:300]
        )

    return {"status": "executed", "rows_affected": affected}


@app.get("/health")
async def health_check(db: Database = Depends(get_db)) -> dict:
    """
    Health check endpoint.

    Tests database connectivity and returns status.
    """
    is_healthy = db.test_connection()
    status = "healthy" if is_healthy else "unhealthy"

    return {
        "status": status,
        "database": {
            "host": db.config.host,
            "port": db.config.port,
            "database": db.config.database,
            "connected": is_healthy
        },
        # Lets the UI show whether its "Allow write queries" setting can take effect.
        "writes_enabled": writes.writes_enabled(),
    }


@app.get("/schema")
async def get_schema(db: Database = Depends(get_db)) -> dict:
    """
    Retrieve the introspected database schema.

    Returns schema in a structured format:
    - Tables with column names and types
    - Primary keys
    - Foreign key relationships
    """
    try:
        introspector = SchemaIntrospector(db)
        schema = introspector.introspect()
        return schema.to_dict()
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Schema introspection failed: {str(e)}"}
        )


@app.get("/schema/tables")
async def list_tables(db: Database = Depends(get_db)) -> dict:
    """
    List all available tables in the database.

    Returns:
        Dictionary with table names as keys
    """
    try:
        introspector = SchemaIntrospector(db)
        schema = introspector.introspect()
        return {
            "tables": list(schema.tables.keys()),
            "count": len(schema.tables)
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


@app.get("/schema/tables/{table_name}")
async def get_table_schema(table_name: str, db: Database = Depends(get_db)) -> dict:
    """
    Get schema for a specific table.

    Args:
        table_name: Name of the table to inspect

    Returns:
        Table schema with columns, keys, and relationships
    """
    try:
        introspector = SchemaIntrospector(db)
        schema = introspector.introspect()
        table = schema.get_table(table_name)

        if not table:
            return JSONResponse(
                status_code=404,
                content={"error": f"Table '{table_name}' not found"}
            )

        return {
            "name": table.name,
            "columns": {
                name: {
                    "type": col.data_type,
                    "nullable": col.is_nullable,
                    "primary_key": col.is_primary_key
                }
                for name, col in table.columns.items()
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
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
