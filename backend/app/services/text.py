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


def to_or_tsquery(query: str, expansions: dict[str, list[str]] | None = None) -> str | None:
    """Build a safe `a | b | c` string for to_tsquery. Tokens are [a-z0-9]+ only, so no injection.

    `expansions` (term -> related terms, learned from failed queries) widen the keyword query.
    """
    terms = keyword_terms(query)
    if expansions:
        extra = [e for t in terms for e in expansions.get(t, [])]
        terms = list(dict.fromkeys(terms + [x for e in extra for x in tokenize(e) if x not in STOPWORDS]))
    return " | ".join(terms) if terms else None

def stem(t: str) -> str:
    for suf in ("ing", "ed", "es", "s", "ly"):
        if len(t) > len(suf) + 3 and t.endswith(suf):
            return t[: -len(suf)]
    return t


def stems(text: str) -> set[str]:
    return {stem(t) for t in keyword_terms(text, 64)}


def coverage(claim: str, passage: str) -> float:
    """Fraction of the claim's content stems that appear in the passage (0..1)."""
    cs = stems(claim)
    return len(cs & stems(passage)) / len(cs) if cs else 0.0


def numbers(text: str) -> set[str]:
    return set(re.findall(r"\d+(?:\.\d+)?", text))
