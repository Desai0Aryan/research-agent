"""Decide whether a retrieved chunk satisfies a gold passage.

Gold labels reference (filename, page, passage text) rather than chunk ids, so a golden set
survives re-ingestion with different chunk sizes or embedding models.
"""
from dataclasses import dataclass
from pathlib import PurePath

from ..services.text import coverage


@dataclass(frozen=True)
class Gold:
    filename: str | None = None
    page: int | None = None
    passage: str | None = None


def gold_from_dict(d: dict) -> Gold:
    return Gold(d.get("filename"), d.get("page"), d.get("passage"))


def matches(hit, gold: Gold, min_cov: float = 0.6) -> bool:
    if not (gold.filename or gold.passage):
        return False
    if gold.filename and PurePath(hit.filename).name.lower() != PurePath(gold.filename).name.lower():
        return False
    if gold.page and hit.page != gold.page:
        return False
    if gold.passage and coverage(gold.passage, hit.text) < min_cov:
        return False
    return True


def relevance(hits: list, golds: list[Gold]) -> tuple[list[bool], list[int | None]]:
    """(rels, gold_ranks): rels[i] is True only for the first hit satisfying each gold."""
    rels = [False] * len(hits)
    ranks: list[int | None] = [None] * len(golds)
    for gi, g in enumerate(golds):
        for i, h in enumerate(hits):
            if matches(h, g):
                ranks[gi] = i + 1
                rels[i] = True
                break
    return rels, ranks
