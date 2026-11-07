"""Reciprocal Rank Fusion: combine ranked lists without needing comparable scores."""
from collections.abc import Hashable, Sequence


def rrf(rankings: Sequence[Sequence[Hashable]], k: int = 60) -> dict[Hashable, float]:
    scores: dict[Hashable, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
    return scores
