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

from app.ambiguity_detector import AmbiguityDetector
from app.database import Database, get_db, init_db
from app.intent_converter import IntentConversionError, convert_query_intent
from app.intent_extractor import extract_intent
from app.schema import DatabaseSchema, SchemaIntrospector
from app.sql_generator import SQLGenerator

# Initialize FastAPI app
app = FastAPI(
    title="Text-to-SQL System",
    description="Natural language to SQL, with ambiguity detection and clarification",
    version="0.4.0"
)


@app.on_event("startup")
async def startup_event():
    """Initialize database on application startup."""
    global db_instance
    db_instance = init_db()
    print("✓ Database initialized")
    print(f"✓ Connected to {db_instance.config.database} on {db_instance.config.host}")


def _schema_context(schema: DatabaseSchema) -> dict:
    """Build the {table: [columns]} shape Phase 2's NLU modules expect."""
    return {name: list(table.columns.keys()) for name, table in schema.tables.items()}


class QueryRequest(BaseModel):
    question: str
    strict: bool = True
    allow_full_table_write: bool = False


@app.post("/query")
async def run_query(request: QueryRequest, db: Database = Depends(get_db)) -> dict:
    """
    Convert a natural language question into SQL.

    Chains schema introspection -> intent extraction -> ambiguity
    detection -> SQL generation. Returns the generated SQL and params on
    success, or clarification questions / an error message when the
    pipeline can't safely proceed. The SQL is returned, not executed.
    """
    try:
        schema = SchemaIntrospector(db).introspect()
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Schema introspection failed: {str(e)}"})

    try:
        query_intent = extract_intent(request.question, _schema_context(schema))
    except Exception as e:
        return JSONResponse(status_code=502, content={"error": f"Intent extraction failed: {str(e)}"})

    try:
        structured_intent = convert_query_intent(query_intent, request.question)
    except IntentConversionError as e:
        return JSONResponse(status_code=422, content={"error": str(e)})

    generator = SQLGenerator(schema, AmbiguityDetector(schema), strict=request.strict)
    result = generator.generate(structured_intent, allow_full_table_write=request.allow_full_table_write)

    return result.to_dict()


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
