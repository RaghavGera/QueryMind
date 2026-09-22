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
import os

from app.ambiguity_detector import AmbiguityDetector
from app.database import Database, get_db, init_db
from app.intent_converter import IntentConversionError, convert_query_intent
from app.intent_extractor import extract_intent
from app.schema import DatabaseSchema, SchemaIntrospector
from app.sql_generator import SQLGenerator

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
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
    strict: bool = True
    allow_full_table_write: bool = False


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
        schema = SchemaIntrospector(db).introspect()
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": "Database schema could not be inspected.",
                "details": str(exc),
                "result": {"columns": [], "rows": []},
            },
        )

    try:
        query_intent = extract_intent(
            question,
            _schema_context(schema)
        )
    except Exception as exc:
        return JSONResponse(
            status_code=502,
            content={
                "status": "error",
                "error": "Natural-language intent could not be extracted.",
                "details": str(exc),
                "result": {"columns": [], "rows": []},
            },
        )

    try:
        structured_intent = convert_query_intent(
            query_intent,
            question,
            schema=schema,
        )
    except IntentConversionError as exc:
        return JSONResponse(
            status_code=422,
            content={
                "status": "error",
                "error": "The extracted intent could not be converted into a safe SQL plan.",
                "details": str(exc),
                "result": {"columns": [], "rows": []},
            },
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

    if (
        generated.status.value in {
            "success",
            "success_with_warnings"
        }
        and generated.sql
    ):
        with open("generated_sql_debug.txt", "w", encoding="utf-8") as f:
            f.write("SQL:\n")
            f.write(generated.sql)
            f.write("\n\nPARAMS:\n")
            f.write(repr(generated.params))
        try:
            rows = db.execute_query(
                generated.sql,
                tuple(generated.params)
            )
        except Exception as exc:
            payload = {
                "status": "error",
                "error": "Generated SQL could not be executed.",
                "details": str(exc),
                "sql": generated.sql,
                "params": generated.params,
                "result": {"columns": [], "rows": []},
            }
            return payload

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
        }
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
