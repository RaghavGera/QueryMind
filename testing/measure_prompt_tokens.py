"""
Measure extraction prompt tokens with and without schema trimming.

For every question in testing/test_questions.txt this sends the production
extraction request twice to ONE provider -- once with the full schema
("before") and once with the trimmed schema ("after") -- and records
``usage.prompt_tokens`` from the API response. When trimming falls back to the
full schema the two requests are identical, so a single call is made and its
count is used for both columns.

    python -m testing.measure_prompt_tokens --dry-run          # no API calls
    python -m testing.measure_prompt_tokens --provider groq    # real measurement
    python -m testing.measure_prompt_tokens --limit 10 --json tokens.json

Cost: every call is a real request (prompt + up to LLM_MAX_TOKENS completion),
so a full run spends roughly 2 x 1.1K tokens per trimmed question. On Groq's
free tier (200K tokens/day) that is a large share of the daily quota -- check
before running against a key that also serves the live demo. The run stops
cleanly (keeping partial results) when the provider's daily quota is hit.
"""

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

QUESTIONS_FILE = Path(__file__).with_name("test_questions.txt")
_COMMENTARY_PREFIXES = ("These ", "For revenue", "rather than", "quantity ")


def parse_questions(path: Path = QUESTIONS_FILE) -> List[str]:
    """
    Questions from the free-form file: skips "Level" headers, commentary,
    relationship notes ("orders -> customers") and the option lines listed
    under "Potential ambiguity:".
    """
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    questions: List[str] = []
    in_options = False
    for index, line in enumerate(lines):
        if not line:
            continue
        if line.startswith("Level "):
            in_options = False
            continue
        if line == "Potential ambiguity:":
            in_options = True
            continue
        following = [l for l in lines[index + 1:index + 3]]
        starts_new_question = following == ["", "Potential ambiguity:"]
        if in_options and not starts_new_question:
            continue
        in_options = False
        if line.startswith(_COMMENTARY_PREFIXES) or "→" in line or line.endswith(":"):
            continue
        questions.append(line)
    return questions


def _schema_context():
    from app.database import init_db
    from app.main import _schema_context as build
    from app.schema import SchemaIntrospector
    try:
        db = init_db()
        if db.test_connection():
            return build(SchemaIntrospector(db).introspect()), "live database"
    except Exception:
        pass
    from testing.test_phase4 import build_mock_schema
    return build(build_mock_schema()), "in-memory schema (same tables as the seed SQL)"


def dry_run(questions: List[str], context: dict) -> None:
    from app.intent_extractor import _format_schema_context, trim_schema_context
    full = len(_format_schema_context(context))
    trimmed_count = 0
    for question in questions:
        trimmed = trim_schema_context(question, context)
        if trimmed is not context:
            trimmed_count += 1
        label = ",".join(trimmed["columns"]) if trimmed is not context else "FULL"
        print(f"{label:45} | {len(_format_schema_context(trimmed)):4d} chars | {question}")
    print(f"\n{len(questions)} questions; {trimmed_count} trimmed, {len(questions) - trimmed_count} use the full schema "
          f"(full schema listing = {full} characters)")
    print(f"A measurement run needs {len(questions) + trimmed_count} API calls "
          f"({len(questions)} full-schema + {trimmed_count} trimmed).")


def _provider(name: Optional[str]):
    from app.openai_client import configured_providers
    providers = configured_providers()
    if name:
        providers = [p for p in providers if p.name == name]
    if not providers:
        raise SystemExit(f"No configured provider{' named ' + name if name else ''} (set its API key).")
    return providers[0]


class _DailyQuotaReached(Exception):
    pass


def _prompt_tokens(provider, request: Dict, attempts: int = 5) -> int:
    """usage.prompt_tokens for one real request; retries per-minute 429s and 5xx."""
    import openai
    import app.intent_extractor as extractor

    for attempt in range(1, attempts + 1):
        try:
            response = provider.client.chat.completions.create(
                model=provider.model, tool_choice=provider.tool_choice, **request
            )
            return int(response.usage.prompt_tokens)
        except openai.RateLimitError as exc:
            if extractor._is_daily_quota(exc):
                raise _DailyQuotaReached(str(exc)) from exc
            if attempt == attempts:
                raise
            wait = extractor._retry_after_header(exc) or 15.0 * attempt
            print(f"  per-minute limit; waiting {wait:.0f}s")
            time.sleep(wait)
        except (openai.InternalServerError, openai.APIConnectionError) as exc:
            if attempt == attempts:
                raise
            print(f"  {type(exc).__name__}; retrying in {10 * attempt}s")
            time.sleep(10 * attempt)
    raise RuntimeError("unreachable")


def measure(questions: List[str], context: dict, provider_name: Optional[str], delay: float) -> List[Dict]:
    import app.intent_extractor as extractor

    provider = _provider(provider_name)
    print(f"Measuring with provider={provider.name} model={provider.model}\n")
    rows: List[Dict] = []
    for number, question in enumerate(questions, 1):
        trimmed = extractor.trim_schema_context(question, context) is not context
        try:
            before = _prompt_tokens(provider, extractor.build_extraction_request(question, context, trim=False))
            if trimmed:
                time.sleep(delay)
                after = _prompt_tokens(provider, extractor.build_extraction_request(question, context, trim=True))
            else:
                after = before
        except _DailyQuotaReached:
            print(f"\nStopped at question {number}: daily quota reached ({len(rows)} measured).")
            break
        rows.append({"question": question, "trimmed": trimmed, "before": before, "after": after})
        print(f"{before:5d} -> {after:5d}  {'trimmed ' if trimmed else 'fallback'}  {question}")
        time.sleep(delay)
    return rows


def summarize(rows: List[Dict]) -> None:
    if not rows:
        print("No measurements.")
        return

    def line(label, subset):
        if not subset:
            return
        before = [r["before"] for r in subset]
        after = [r["after"] for r in subset]
        saved = sum(before) - sum(after)
        print(f"{label:22} n={len(subset):3d}  mean before={statistics.mean(before):7.1f}  "
              f"mean after={statistics.mean(after):7.1f}  total before={sum(before):7d}  "
              f"total after={sum(after):7d}  saved={saved:6d} ({100 * saved / sum(before):.1f}%)")

    print("\nprompt_tokens (from API usage)")
    line("all measured", rows)
    line("trimmed questions", [r for r in rows if r["trimmed"]])
    line("full-schema fallback", [r for r in rows if not r["trimmed"]])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dry-run", action="store_true", help="Show trimming decisions only; no API calls")
    parser.add_argument("--provider", help="Provider to measure with (default: first configured)")
    parser.add_argument("--limit", type=int, help="Only the first N questions")
    parser.add_argument("--delay", type=float, default=8.0, help="Seconds between calls (per-minute limits)")
    parser.add_argument("--json", dest="json_out", help="Write per-question results to this file")
    args = parser.parse_args(argv)

    questions = parse_questions()
    if args.limit:
        questions = questions[: args.limit]
    context, source = _schema_context()
    print(f"{len(questions)} questions from {QUESTIONS_FILE.name}; schema from {source}\n")

    if args.dry_run:
        dry_run(questions, context)
        return 0

    rows = measure(questions, context, args.provider, args.delay)
    summarize(rows)
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
