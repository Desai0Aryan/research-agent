"""Pure text helpers (no DB / network) so they are trivially unit-testable."""
import re

STOPWORDS = frozenset(
    """a an and are as at be but by for from has have how i if in into is it its of on or
    that the their then there these this to was were what when where which who why will with
    about between compare comparing does do did can could should would than also over under
    using use used vs versus""".split()
)

_WORD = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return _WORD.findall(text.lower())


def keyword_terms(query: str, max_terms: int = 24) -> list[str]:
    """Content-bearing, de-duplicated terms (order preserved)."""
    seen: dict[str, None] = {}
    for t in tokenize(query):
        if t not in STOPWORDS and len(t) > 1:
            seen.setdefault(t)
    return list(seen)[:max_terms]


def to_or_tsquery(query: str) -> str | None:
    """Build a safe `a | b | c` string for to_tsquery. Tokens are [a-z0-9]+ only, so no injection."""
    terms = keyword_terms(query)
    return " | ".join(terms) if terms else None
