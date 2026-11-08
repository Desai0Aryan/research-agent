from dataclasses import dataclass
from functools import lru_cache

from ..schemas import SearchHit
from ..services.text import coverage, keyword_terms
from .llm import LLM, extract_json


@dataclass
class Ranked:
    hit: SearchHit
    score: float  # 0..1, higher = more relevant


def lexical_scores(query: str, hits: list[SearchHit]) -> list[float]:
    """Offline reranker: query-term coverage + bigram phrase bonus + prior from fused rank."""
    terms = keyword_terms(query)
    bigrams = list(zip(terms, terms[1:]))
    n = max(len(hits), 1)
    out = []
    for i, h in enumerate(hits):
        low = h.text.lower()
        cov = coverage(query, h.text)
        bg = sum(1 for a, b in bigrams if f"{a} {b}" in low) / len(bigrams) if bigrams else 0.0
        prior = 1.0 - i / n
        out.append(0.6 * cov + 0.15 * bg + 0.25 * prior * (1 if cov > 0 else 0.3))
    return out


@lru_cache
def _cross_encoder(name: str):
    from sentence_transformers import CrossEncoder  # optional dependency

    return CrossEncoder(name)


def _llm_scores(query: str, hits: list[SearchHit], llm: LLM) -> list[float]:
    items = "\n\n".join(f"[{i}] {h.text[:700]}" for i, h in enumerate(hits))
    data = extract_json(
        llm.complete(
            "Score each passage 0-10 for how directly it helps answer the query (10 = contains the answer). "
            'Return ONLY JSON: {"scores":[{"i":0,"score":7}]}',
            f"Query: {query}\n\nPassages:\n{items}",
            json_mode=True,
            max_tokens=1200,
        )
    )
    m = {int(x["i"]): float(x["score"]) / 10 for x in data["scores"]}
    return [m.get(i, 0.0) for i in range(len(hits))]


def rerank(query, hits, top_n, mode, llm: LLM | None, ce_model="", warn=lambda m: None) -> list[Ranked]:
    if not hits:
        return []
    hits = hits[:30]
    scores: list[float] | None = None
    try:
        if mode == "llm" and llm:
            scores = _llm_scores(query, hits, llm)
        elif mode == "cross-encoder":
            raw = _cross_encoder(ce_model).predict([(query, h.text) for h in hits])
            import math

            scores = [1 / (1 + math.exp(-float(x))) for x in raw]
    except Exception as e:  # noqa: BLE001
        warn(f"Reranker '{mode}' failed, using lexical: {e}")
    if scores is None:
        scores = lexical_scores(query, hits)
    ranked = sorted((Ranked(h, s) for h, s in zip(hits, scores)), key=lambda r: r.score, reverse=True)
    return ranked[:top_n]


FOLLOWUP_SYSTEM = """You judge whether retrieved passages can answer a sub-question. If not, propose up to 2
alternative search queries (different wording, synonyms, more specific terms). Return ONLY JSON:
{"sufficient": true|false, "queries": ["..."]}"""


def followup_queries(sub_q: str, ranked: list[Ranked], llm: LLM | None, warn=lambda m: None) -> list[str]:
    if llm:
        try:
            ctx = "\n".join(f"- {r.hit.text[:300]}" for r in ranked[:4]) or "(nothing retrieved)"
            d = extract_json(llm.complete(FOLLOWUP_SYSTEM, f"Sub-question: {sub_q}\nTop passages:\n{ctx}", json_mode=True, max_tokens=300))
            return [] if d.get("sufficient") else [q for q in d.get("queries", []) if isinstance(q, str)][:2]
        except Exception as e:  # noqa: BLE001
            warn(f"LLM follow-up failed, using heuristic: {e}")
    # heuristic: expand with the most frequent novel terms from the best passages
    base = set(keyword_terms(sub_q))
    freq: dict[str, int] = {}
    for r in ranked[:3]:
        for t in keyword_terms(r.hit.text, 200):
            if t not in base and len(t) > 4:
                freq[t] = freq.get(t, 0) + 1
    extra = [t for t, _ in sorted(freq.items(), key=lambda kv: -kv[1])[:3]]
    return [" ".join(list(base) + extra)] if extra else [" ".join(sorted(base))]
