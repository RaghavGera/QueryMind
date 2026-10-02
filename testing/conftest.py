"""
pytest wiring so ``pytest testing/`` runs every suite, including the older
script-style ones (test_phase1-4, test_ambiguity_realworld), with the same
inputs their ``main()`` functions pass by hand:

* ``schema``      the in-memory schema matching database/text_to_sql_database.sql
                  (test_phase1 gets the live, introspected schema instead)
* ``detector``    an AmbiguityDetector over ``schema``
* ``db``          a live database connection (skipped when PostgreSQL is unreachable)
* ``has_api_key`` whether any LLM provider key is configured (skipped otherwise)

Script-style tests report failure by *returning* False; that fails the test
here instead of being silently ignored.

Tests that spend real LLM tokens (test_phase2 extraction/pipeline) are skipped
unless QUERYMIND_LIVE_LLM_TESTS=1, so a routine test run never eats into the
provider's daily quota.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

LIVE_DB_MODULES = {"test_phase1"}
LIVE_LLM_TESTS = {"test_intent_extraction", "test_full_pipeline"}

_db_probe = {}


def _module_name(item_or_request) -> str:
    return item_or_request.module.__name__.rsplit(".", 1)[-1]


def _live_db():
    """Connect once per session; returns (db, None) or (None, reason)."""
    if "result" not in _db_probe:
        try:
            from app.database import init_db
            db = init_db()
            if db.test_connection():
                _db_probe["result"] = (db, None)
            else:
                _db_probe["result"] = (None, f"PostgreSQL not reachable at {db.config.host}:{db.config.port}")
        except Exception as exc:  # missing credentials, driver errors...
            _db_probe["result"] = (None, f"database not configured: {exc}")
    return _db_probe["result"]


def pytest_collection_modifyitems(config, items):
    live_llm = os.getenv("QUERYMIND_LIVE_LLM_TESTS") == "1"
    for item in items:
        module = _module_name(item)
        if module in LIVE_DB_MODULES:
            db, reason = _live_db()
            if db is None:
                item.add_marker(pytest.mark.skip(reason=f"needs a live database ({reason})"))
        if item.originalname in LIVE_LLM_TESTS and module == "test_phase2" and not live_llm:
            item.add_marker(pytest.mark.skip(
                reason="spends real LLM tokens; set QUERYMIND_LIVE_LLM_TESTS=1 to run"
            ))


def pytest_generate_tests(metafunc):
    # test_ambiguity_realworld.test_question(detector, question, schema, question_num)
    if _module_name(metafunc) == "test_ambiguity_realworld" and metafunc.function.__name__ == "test_question":
        questions = metafunc.module.QUESTIONS
        metafunc.parametrize(
            "question,question_num",
            [(question, number) for number, question in enumerate(questions, 1)],
            ids=[f"q{number}" for number in range(1, len(questions) + 1)],
        )


@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem):
    """Run the test; a script-style ``return False`` is a failure."""
    arguments = {name: pyfuncitem.funcargs[name] for name in pyfuncitem._fixtureinfo.argnames}
    result = pyfuncitem.obj(**arguments)
    assert result is not False, f"{pyfuncitem.name} reported failure (returned False)"
    return True


@pytest.fixture
def db():
    database, reason = _live_db()
    if database is None:
        pytest.skip(f"needs a live database ({reason})")
    return database


@pytest.fixture
def schema(request):
    if _module_name(request) in LIVE_DB_MODULES:
        from app.schema import SchemaIntrospector
        return SchemaIntrospector(request.getfixturevalue("db")).introspect()
    from testing.test_phase4 import build_mock_schema
    return build_mock_schema()


@pytest.fixture
def detector(schema):
    from app.ambiguity_detector import AmbiguityDetector
    return AmbiguityDetector(schema)


@pytest.fixture
def has_api_key():
    from app.openai_client import configured_providers
    if not configured_providers():
        pytest.skip("no LLM provider key configured")
    return True
