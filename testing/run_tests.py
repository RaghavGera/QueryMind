"""
Run every offline test suite the way each one is meant to be run.

The suites in testing/ are a mix of pytest files and standalone scripts (which
`pytest testing/` cannot collect cleanly), so this is the single entry point:

    python -m testing.run_tests          # offline suites (no DB, no network)
    python -m testing.run_tests --live   # also the suites needing a database / LLM key

Exit code is non-zero if any suite fails.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PYTEST_SUITES = [
    "testing/test_regressions.py",
    "testing/test_stabilization.py",
    "testing/test_having.py",
    "testing/test_vague_terms.py",
    "testing/test_case_insensitive.py",
    "testing/test_converter_rules.py",
    "testing/test_writes.py",
    "testing/test_analytics.py",
    "testing/test_provider_config.py",
    "testing/test_eval_harness.py",
]
SCRIPT_SUITES = [
    "testing.test_phase3",
    "testing.test_phase4",
    "testing.test_expression_aggregations",
]
# Need a reachable PostgreSQL and/or GROQ_API_KEY (see SETUP.md).
LIVE_SCRIPT_SUITES = [
    "testing.test_phase1",
    "testing.test_phase2",
]


def run(label: str, command: list) -> bool:
    print(f"\n=== {label}", flush=True)
    result = subprocess.run(command, cwd=ROOT)
    ok = result.returncode == 0
    print(f"--- {label}: {'OK' if ok else 'FAILED'}", flush=True)
    return ok


def main() -> int:
    live = "--live" in sys.argv[1:]
    outcomes = {}

    for path in PYTEST_SUITES:
        outcomes[path] = run(path, [sys.executable, "-m", "pytest", path, "-q", "-p", "no:cacheprovider"])
    for module in SCRIPT_SUITES + (LIVE_SCRIPT_SUITES if live else []):
        outcomes[module] = run(module, [sys.executable, "-m", module])

    failed = [name for name, ok in outcomes.items() if not ok]
    print("\n" + "=" * 60)
    print(f"{len(outcomes) - len(failed)}/{len(outcomes)} suites passed")
    for name in failed:
        print(f"  FAILED: {name}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
