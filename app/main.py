"""
FastAPI application entry point for Phase 1.

This is the minimal Phase 1 app that:
1. Initializes database connection
2. Introspects schema
3. Provides health check and schema viewing endpoints
"""

from fastapi import FastAPI, Depends
from fastapi.responses import JSONResponse

from app.database import Database, init_db, get_db
from app.schema import SchemaIntrospector, DatabaseSchema

# Initialize FastAPI app
app = FastAPI(
    title="Text-to-SQL System",
    description="Phase 1: PostgreSQL Connection & Schema Introspection",
    version="0.1.0"
)


@app.on_event("startup")
async def startup_event():
    """Initialize database on application startup."""
    global db_instance
    db_instance = init_db()
    print("✓ Database initialized")
    print(f"✓ Connected to {db_instance.config.database} on {db_instance.config.host}")


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
