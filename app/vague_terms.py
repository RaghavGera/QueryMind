"""
Deterministic detection of vague wording in a user's question.

The LLM tends to "helpfully" guess what a vague term means ("expensive" ->
price > 500, "top customers" -> ranked by spend). Ambiguity is a feature of
QueryMind, so these checks look at the *question text itself*, independent
of whatever the model decided, and let the AmbiguityDetector ask instead.

Once the user has answered a clarification (the API appends
"User clarification: ..." to the question) these checks are skipped, so a
clarified question can never loop back into another clarification.
"""

import re
from typing import Optional

CLARIFICATION_MARKER = "user clarification:"

# Adjectives that imply a threshold the user never stated.
_THRESHOLD_TERM = re.compile(
    r"\b(expensive|inexpensive|cheap|high|low|large|big|small|premium|budget|affordable)\b",
    re.IGNORECASE,
)
# Signals that the user *did* say how much: a number, a comparison, or a
# superlative ("most expensive" is a ranking, not a threshold).
_THRESHOLD_GIVEN = re.compile(
    r"\d|\b(more|less|greater|fewer|over|under|above|below|between|exceed\w*|"
    r"at\s+least|at\s+most|most|least|top|bottom|best|worst|highest|lowest|"
    r"cheapest|biggest|largest|smallest|priciest)\b",
    re.IGNORECASE,
)

# "recent orders" has no window; "last 7 days" / "latest order" do.
_RECENCY_TERM = re.compile(r"\b(recent|recently|lately)\b", re.IGNORECASE)
_RECENCY_GIVEN = re.compile(r"\d|\b(last|past|since|before|after|within|today|yesterday)\b", re.IGNORECASE)

# Words that rank things ("top customers", "best products", "popular items").
RANKING_TERM = re.compile(
    r"\b(top|best|biggest|leading|popular|most\s+popular)\b", re.IGNORECASE
)
# Words that name the metric being ranked: spend, orders, units, price ...
_METRIC_TERM = re.compile(
    r"\b(by|revenue|sales|spen\w*|orders?|quantit\w*|units?|sold|sell\w*|"
    r"price\w*|cost\w*|expensive|cheap\w*|frequent\w*|ordered|purchas\w*|"
    r"bought|buy\w*|money|profit\w*|income|total|average|count|number|"
    r"amount|value|rated|rating|signed|joined)\b",
    re.IGNORECASE,
)
# Only an explicit "top N" gets a default metric (units sold) when the schema
# makes it unambiguous; "best"/"popular" stay questions.
DEFAULTABLE_RANKING = re.compile(r"\btop\b", re.IGNORECASE)


def already_clarified(question: str) -> bool:
    return CLARIFICATION_MARKER in (question or "").lower()


def vague_threshold_term(question: str) -> Optional[str]:
    """Return the vague adjective (e.g. 'expensive') if no threshold was given."""
    if already_clarified(question):
        return None
    match = _THRESHOLD_TERM.search(question or "")
    if match and not _THRESHOLD_GIVEN.search(question):
        return match.group(1).lower()
    return None


def vague_recency_term(question: str) -> Optional[str]:
    """Return 'recent'/'recently' if no time window was given."""
    if already_clarified(question):
        return None
    match = _RECENCY_TERM.search(question or "")
    if match and not _RECENCY_GIVEN.search(question):
        return match.group(1).lower()
    return None


def needs_ranking_metric(question: str) -> Optional[str]:
    """Return the ranking word ('top', 'best', ...) if no metric was named."""
    if already_clarified(question):
        return None
    match = RANKING_TERM.search(question or "")
    if match and not _METRIC_TERM.search(question):
        return match.group(1).lower()
    return None
