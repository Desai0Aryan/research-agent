"""Standard IR metrics. Pure functions."""
import math
from statistics import mean


def recall_at_k(gold_ranks: list[int | None], k: int) -> float:
    """Share of gold passages found within the top k (rank is 1-based, None = not found)."""
    return sum(1 for r in gold_ranks if r is not None and r <= k) / len(gold_ranks) if gold_ranks else 0.0


def mrr(gold_ranks: list[int | None]) -> float:
    found = [r for r in gold_ranks if r is not None]
    return 1.0 / min(found) if found else 0.0


def ndcg_at_k(rels: list[bool], n_gold: int, k: int) -> float:
    """Binary-relevance nDCG. `rels` marks only the FIRST hit per gold passage (no double credit)."""
    dcg = sum(1.0 / math.log2(i + 2) for i, r in enumerate(rels[:k]) if r)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(min(n_gold, k)))
    return dcg / idcg if idcg else 0.0


def avg(xs: list[float]) -> float:
    return round(mean(xs), 4) if xs else 0.0
