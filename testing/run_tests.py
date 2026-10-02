"""
Run the whole test suite.

    python -m testing.run_tests          # == pytest testing/ (no LLM tokens spent)
    python -m testing.run_tests --live   # also the tests that call a real LLM provider

Every suite in testing/ (pytest files and the older script-style ones) is
collected by ``pytest testing/`` via testing/conftest.py. Tests needing a
database are skipped when PostgreSQL is unreachable; tests that spend LLM
tokens are skipped unless --live (QUERYMIND_LIVE_LLM_TESTS=1).

Exit code is pytest's: non-zero if anything fails.
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    env = dict(os.environ)
    if "--live" in sys.argv[1:]:
        env["QUERYMIND_LIVE_LLM_TESTS"] = "1"
    command = [sys.executable, "-m", "pytest", "testing", "-q", "-rs", "-p", "no:cacheprovider"]
    return subprocess.run(command, cwd=ROOT, env=env).returncode


if __name__ == "__main__":
    sys.exit(main())
