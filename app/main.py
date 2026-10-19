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

from typing import Optional

from fastapi import Depends, FastAPI, Header, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import logging
import os

from app.accounts import SAVED_LIMIT, AccountStore, clean_entry, next_reset
from app.ambiguity_detector import AmbiguityDetector
from app.auth import (
    AuthError,
    Principal,
    anonymous_subject,
    auth_configured,
    bearer_token,
    client_ip,
    issue_session_token,
    read_session_token,
    service_key_matches,
    verify_google_access_token,
    verify_google_id_token,
)
from app import writes
from app.database import Database, QueryTimeoutError, WriteConflictError, get_db, init_db, max_result_rows
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

# --------------------------------------------------------------------------- #
# Sign-in and daily usage limits for the endpoints that spend AI credits.
# Added *before* CORS so CORS stays outermost and 401/429 bodies are readable
# by the browser.
# --------------------------------------------------------------------------- #

def _int_env(name: str, default: int) -> int:
    try:
        return max(0, int(os.getenv(name, default)))
    except ValueError:
        return default


def user_daily_limit() -> int:
    return _int_env("DAILY_QUESTION_LIMIT", 20)


def anonymous_daily_limit() -> int:
    return _int_env("ANON_DAILY_QUESTION_LIMIT", 3)


_LIMITED_PATHS = {"/query", "/query/confirm"}
_store: Optional[AccountStore] = None


def get_account_store() -> AccountStore:
    global _store
    if _store is None:
        _store = AccountStore(get_db())
    return _store


def resolve_principal(request: Request, store: AccountStore) -> Principal:
    """Service key > valid session > anonymous visitor. Raises AuthError for bad tokens."""
    if service_key_matches(request.headers.get("x-service-key")):
        return Principal(kind="service", subject="service")
    token = bearer_token(request.headers.get("authorization"))
    if token:
        session_id = read_session_token(token)
        user = store.session_user(session_id)
        if user is None:
            raise AuthError("Your session has ended. Please sign in again.")
        return Principal(kind="user", subject=f"user:{user.id}", user=user, session_id=session_id)
    return Principal(kind="anonymous", subject=anonymous_subject(_request_ip(request)))


def _request_ip(request: Request) -> str:
    header = (os.getenv("CLIENT_IP_HEADER") or "").strip()
    return client_ip(
        request.headers.get("x-forwarded-for"),
        request.client.host if request.client else None,
        _int_env("TRUSTED_PROXY_HOPS", 1),
        request.headers.get(header) if header else None,
    )


def _usage_payload(principal: Principal, used: int, limit: Optional[int]) -> dict:
    return {
        "scope": principal.kind,
        "used": used,
        "limit": limit,
        "resets_at": next_reset().isoformat(),
    }


def _usage_headers(usage: dict) -> dict:
    headers = {"X-Usage-Scope": usage["scope"], "X-Usage-Used": str(usage["used"])}
    if usage["limit"] is not None:
        headers["X-Usage-Limit"] = str(usage["limit"])
    return headers


@app.middleware("http")
async def usage_limits(request: Request, call_next):
    if request.method != "POST" or request.url.path not in _LIMITED_PATHS:
        return await call_next(request)

    try:
        store = get_account_store()
        principal = await run_in_threadpool(resolve_principal, request, store)
    except AuthError as exc:
        return JSONResponse(
            status_code=exc.status,
            content={"status": "error", "error": str(exc), "sign_in_required": exc.status == 401},
        )
    except Exception:
        logger.exception("Could not check sign-in")
        return JSONResponse(status_code=503, content={"status": "error", "error": "Sign-in check failed. Please retry."})

    if request.url.path == "/query/confirm" and principal.kind == "anonymous":
        return JSONResponse(
            status_code=401,
            content={"status": "error", "error": "Sign in to make changes.", "sign_in_required": True},
        )

    if principal.kind == "service" or request.url.path != "/query":
        return await call_next(request)

    limit = user_daily_limit() if principal.kind == "user" else anonymous_daily_limit()
    ticket = (request.headers.get("x-clarification-ticket") or "").strip()
    if ticket and await run_in_threadpool(store.redeem_ticket, ticket, principal.subject):
        # Answering a clarification of a question already counted: free.
        response = await call_next(request)
        if response.status_code >= 500 or response.status_code == 429:
            await run_in_threadpool(store.restore_ticket, ticket)
        used = await run_in_threadpool(store.used_today, principal.subject)
        for key, value in _usage_headers(_usage_payload(principal, used, limit)).items():
            response.headers[key] = value
        return response

    used = await run_in_threadpool(store.try_consume, principal.subject, limit)
    if used is None:
        usage = _usage_payload(principal, limit, limit)
        message = (
            f"You've used today's {limit} questions. They reset at 00:00 UTC."
            if principal.kind == "user"
            else f"That's all {limit} free questions for today. Sign in with Google to keep going."
        )
        return JSONResponse(
            status_code=429,
            content={"status": "error", "error": message, "usage": usage,
                     "sign_in_required": principal.kind == "anonymous", "quota_exceeded": True},
            headers=_usage_headers(usage),
        )

    request.state.charged_subject = principal.subject  # lets /query issue a clarification ticket
    response = await call_next(request)
    if response.status_code >= 500 or response.status_code == 429:
        # The model or server failed, not the user: give the question back.
        await run_in_threadpool(store.refund, principal.subject)
        used -= 1
    for key, value in _usage_headers(_usage_payload(principal, used, limit)).items():
        response.headers[key] = value
    return response


MAX_ACCOUNT_BODY_BYTES = 8_000_000  # an import of 50 + 100 entries with results is far smaller


@app.middleware("http")
async def account_body_limit(request: Request, call_next):
    """History and saved queries are stored as sent, so refuse oversized bodies before reading them."""
    if request.url.path.startswith("/me/") and request.method in ("POST", "PUT"):
        length = request.headers.get("content-length")
        if length is None or not length.isdigit() or int(length) > MAX_ACCOUNT_BODY_BYTES:
            return JSONResponse(status_code=413, content={"status": "error", "error": "That request is too large to store."})
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=cors_origin_regex,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Usage-Scope", "X-Usage-Used", "X-Usage-Limit", "Retry-After"],
)


@app.on_event("startup")
async def startup_event():
    """Initialize database on application startup."""
    global db_instance
    db_instance = init_db()
    print("✓ Database initialized")
    print(f"✓ Connected to {db_instance.config.database} on {db_instance.config.host}")
    try:
        AccountStore(db_instance).ensure_schema()
    except Exception:
        # Without these tables sign-in fails loudly per request; the demo still runs.
        logger.exception("Could not create the account tables (querymind_meta)")
    if not auth_configured():
        logger.warning("Sign-in is not configured: set GOOGLE_CLIENT_ID and SESSION_SECRET.")


# --------------------------------------------------------------------------- #
# Account endpoints
# --------------------------------------------------------------------------- #

class GoogleSignIn(BaseModel):
    access_token: Optional[str] = None  # from the site's button (Google's token popup)
    credential: Optional[str] = None    # a Google ID token


def _auth_error(exc: AuthError) -> JSONResponse:
    return JSONResponse(status_code=exc.status, content={"status": "error", "error": str(exc)})


def _session_principal(authorization: Optional[str]) -> Principal:
    token = bearer_token(authorization)
    if not token:
        raise AuthError("Not signed in.")
    session_id = read_session_token(token)
    user = get_account_store().session_user(session_id)
    if user is None:
        raise AuthError("Your session has ended. Please sign in again.")
    return Principal(kind="user", subject=f"user:{user.id}", user=user, session_id=session_id)


@app.post("/auth/google")
def sign_in_with_google(body: GoogleSignIn):
    """Exchange a Google ID token for a QueryMind session."""
    try:
        if not auth_configured():  # before any DB write, so a half-set server leaves no rows
            raise AuthError("Sign-in is not configured on this server.", status=503)
        if body.access_token:
            claims = verify_google_access_token(body.access_token)
        elif body.credential:
            claims = verify_google_id_token(body.credential)
        else:
            raise AuthError("Send a Google access_token or credential.", status=400)
        store = get_account_store()
        user = store.upsert_google_user(claims["sub"], claims["email"], claims.get("name"), claims.get("picture"))
        session_id, expires_at = store.create_session(user.id)
        token = issue_session_token(session_id, user.id, expires_at)
    except AuthError as exc:
        return _auth_error(exc)
    limit = user_daily_limit()
    used = store.used_today(f"user:{user.id}")
    return {
        "token": token,
        "expires_at": expires_at.isoformat(),
        "user": user.to_dict(),
        "usage": {"scope": "user", "used": used, "limit": limit, "resets_at": next_reset().isoformat()},
    }


@app.get("/auth/me")
def who_am_i(authorization: Optional[str] = Header(default=None)):
    try:
        principal = _session_principal(authorization)
    except AuthError as exc:
        return _auth_error(exc)
    used = get_account_store().used_today(principal.subject)
    return {
        "user": principal.user.to_dict(),
        "usage": {"scope": "user", "used": used, "limit": user_daily_limit(), "resets_at": next_reset().isoformat()},
    }


@app.get("/auth/usage")
def anonymous_usage(request: Request):
    """Today's usage for whoever is calling (the landing console shows tries left)."""
    store = get_account_store()
    try:
        principal = resolve_principal(request, store)
    except AuthError as exc:
        return _auth_error(exc)
    if principal.kind == "service":
        return {"usage": {"scope": "service", "used": 0, "limit": None, "resets_at": next_reset().isoformat()}}
    limit = user_daily_limit() if principal.kind == "user" else anonymous_daily_limit()
    usage = _usage_payload(principal, store.used_today(principal.subject), limit)
    usage["user_limit"] = user_daily_limit()  # what signing in would give
    return {"usage": usage}


@app.post("/auth/logout")
def sign_out(authorization: Optional[str] = Header(default=None)):
    try:
        principal = _session_principal(authorization)
    except AuthError:
        return {"status": "signed_out"}  # already signed out: nothing to do
    get_account_store().revoke_session(principal.session_id)
    return {"status": "signed_out"}


# --------------------------------------------------------------------------- #
# Query history and saved queries of the signed-in user
# --------------------------------------------------------------------------- #

class EntryBody(BaseModel):
    entry: dict


class ImportBody(BaseModel):
    history: list = []
    saved: list = []


def _signed_in_user_id(authorization: Optional[str]) -> int:
    return _session_principal(authorization).user.id


def _bad_entry() -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"status": "error", "error": "That entry can't be stored (missing question, or result too large)."},
    )


@app.get("/me/history")
def list_history(authorization: Optional[str] = Header(default=None)):
    try:
        user_id = _signed_in_user_id(authorization)
    except AuthError as exc:
        return _auth_error(exc)
    return {"entries": get_account_store().history(user_id)}


@app.post("/me/history")
def add_history(body: EntryBody, authorization: Optional[str] = Header(default=None)):
    try:
        user_id = _signed_in_user_id(authorization)
    except AuthError as exc:
        return _auth_error(exc)
    entry = clean_entry(body.entry)
    if entry is None:
        return _bad_entry()
    get_account_store().add_history(user_id, entry)
    return {"status": "stored"}


@app.delete("/me/history/{entry_id}")
def remove_history(entry_id: str, authorization: Optional[str] = Header(default=None)):
    try:
        user_id = _signed_in_user_id(authorization)
    except AuthError as exc:
        return _auth_error(exc)
    get_account_store().delete_history(user_id, entry_id)
    return {"status": "deleted"}


@app.get("/me/saved")
def list_saved(authorization: Optional[str] = Header(default=None)):
    try:
        user_id = _signed_in_user_id(authorization)
    except AuthError as exc:
        return _auth_error(exc)
    return {"entries": get_account_store().saved(user_id)}


@app.put("/me/saved")
def save_entry(body: EntryBody, authorization: Optional[str] = Header(default=None)):
    try:
        user_id = _signed_in_user_id(authorization)
    except AuthError as exc:
        return _auth_error(exc)
    entry = clean_entry(body.entry)
    if entry is None:
        return _bad_entry()
    if not get_account_store().save_query(user_id, entry):
        return JSONResponse(
            status_code=409,
            content={"status": "error", "error": f"You have {SAVED_LIMIT} saved queries. Delete one to save another."},
        )
    return {"status": "saved"}


@app.delete("/me/saved/{entry_id}")
def remove_saved(entry_id: str, authorization: Optional[str] = Header(default=None)):
    try:
        user_id = _signed_in_user_id(authorization)
    except AuthError as exc:
        return _auth_error(exc)
    get_account_store().delete_saved(user_id, entry_id)
    return {"status": "deleted"}


@app.post("/me/import")
def import_browser_entries(body: ImportBody, authorization: Optional[str] = Header(default=None)):
    """Move a browser's history and saved queries into the account (invalid entries are skipped)."""
    try:
        user_id = _signed_in_user_id(authorization)
    except AuthError as exc:
        return _auth_error(exc)
    history = [e for e in map(clean_entry, body.history) if e is not None]
    saved = [e for e in map(clean_entry, body.saved) if e is not None]
    added = get_account_store().import_entries(user_id, history, saved)
    skipped = len(body.history) + len(body.saved) - len(history) - len(saved)
    return {"imported": added, "skipped": skipped}


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
def run_query(
    request: QueryRequest,
    db: Database = Depends(get_db),
    http_request: Request = None,
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
        result = _run_pipeline(question, request, db)
    except Exception as exc:  # Last-resort guard: never leak a traceback.
        logger.exception("Unhandled error while answering %r", question)
        return _error_response(
            500,
            "Something went wrong while processing the question.",
            details=type(exc).__name__,
        )

    # A clarification question costs nothing extra: the answer, sent with this
    # ticket, is free. Only counted questions get one, so tickets don't chain.
    subject = getattr(getattr(http_request, "state", None), "charged_subject", None)
    if subject and isinstance(result, dict) and result.get("clarification_questions"):
        try:
            result["clarification_ticket"] = get_account_store().issue_ticket(subject)
        except Exception:
            logger.exception("Could not issue a clarification ticket")
    return result


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

    # Deleting is refused outright. Checked before the ambiguity gate: asking
    # "delete ALL rows?" about a request that is refused anyway only loops.
    if structured_intent.query_type == QueryType.DELETE:
        return {
            "status": "blocked",
            "sql": None,
            "params": [],
            "warnings": [],
            "clarification_questions": [],
            "error_message": "Deleting data through natural language is not supported.",
            "has_ambiguities": False,
            "result": {"columns": [], "rows": []},
        }

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

    if succeeded:
        logger.debug("Generated SQL: %s | params: %r", generated.sql, generated.params)
        cap = max_result_rows()
        try:
            rows = db.execute_query(
                generated.sql,
                tuple(generated.params),
                max_rows=cap,
            )
        except QueryTimeoutError as exc:
            # 504, so the question is given back (the usage middleware refunds 5xx).
            return _error_response(
                504,
                f"{exc} Try a narrower question, for example with a filter or a smaller time range.",
                sql=generated.sql,
                params=generated.params,
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

        truncated = len(rows) > cap
        payload["result"] = {
            "columns": columns,
            "rows": rows[:cap],
            "truncated": truncated,
        }
        if truncated:
            payload["warnings"] = list(payload.get("warnings", [])) + [
                f"Showing the first {cap:,} rows; the full result has more. Add a filter or a limit to see the rest."
            ]

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
def confirm_write(request: ConfirmRequest, db: Database = Depends(get_db)):
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
    except QueryTimeoutError as exc:
        return _error_response(504, str(exc))
    except ValueError as exc:
        return _error_response(400, str(exc))
    except Exception as exc:
        logger.exception("Confirmed write failed")
        return _error_response(
            500, "The database rejected the change.", details=str(exc).splitlines()[0][:300]
        )

    return {"status": "executed", "rows_affected": affected}


@app.get("/health")
def health_check(db: Database = Depends(get_db)) -> dict:
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
def get_schema(db: Database = Depends(get_db)) -> dict:
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
        # The database name lets the UI show the real workspace (and doubles
        # as its connection check: /health is blocked by some ad blockers).
        return {"database": db.config.database, **schema.to_dict()}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Schema introspection failed: {str(e)}"}
        )


@app.get("/schema/tables")
def list_tables(db: Database = Depends(get_db)) -> dict:
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
def get_table_schema(table_name: str, db: Database = Depends(get_db)) -> dict:
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
