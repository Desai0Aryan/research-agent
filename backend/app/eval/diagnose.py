"""Failure diagnosis, clustering and fix proposals (the feedback loop's brain). Pure functions."""
from collections import Counter

from ..services.text import coverage, keyword_terms, stem, stems
from .matching import gold_from_dict

RECOMMENDATIONS = {
    "lexical_gap": "Dense search found the passage but keyword search missed it: vocabulary mismatch. Review the proposed query expansions (synonyms) and enable them.",
    "semantic_gap": "Keyword search found the passage but dense search missed it: the embedding model is weak for this domain. Use EMBEDDING_PROVIDER=local/openai with a stronger model.",
    "fusion_gap": "Each retriever found the passage but fusion buried it. Increase CANDIDATE_POOL or enable RERANKER=llm|cross-encoder.",
    "chunk_boundary": "The answer is split across chunks. Increase CHUNK_OVERLAP_WORDS or CHUNK_TARGET_WORDS, then re-ingest.",
    "corpus_gap": "No retriever surfaced the passage. Either the evidence is not in the library, the gold label is wrong, or terms are out-of-vocabulary.",
    "ranking": "Relevant passage retrieved but ranked low. Enable RERANKER=llm|cross-encoder or raise CANDIDATE_K.",
    "wrongly_abstained": "Evidence existed but the agent produced nothing. Lower SUFFICIENCY_THRESHOLD or allow more retrieval rounds.",
    "unsupported_claims": "Writer made claims the sources do not support. Keep STRICT_CITATIONS=true and use a stronger LLM / stricter writer prompt.",
    "incorrect_answer": "Answer missed key facts. Check retrieval first (recall@k), then writer coverage.",
    "answered_unanswerable": "Agent answered a question the corpus cannot answer. Raise the relevance floor so it abstains.",
    "rating_negative": "Users rated these answers poorly; inspect the traces.",
    "low_faithfulness": "Verifier found many unsupported claims in production answers.",
    "empty_answer": "Agent returned no findings; likely corpus gap or vocabulary mismatch.",
}


def _best(ranks: list[int | None]) -> int | None:
    found = [r for r in ranks if r]
    return min(found) if found else None


def diagnose_retrieval(entry: dict, case: dict, primary: str = "hybrid", good_rank: int = 3) -> str | None:
    r = {m: _best(rs) for m, rs in entry["ranks"].items()}
    hyb = r.get(primary)
    if hyb is not None and hyb <= good_rank:
        return None
    if hyb is not None:
        return "ranking"
    vec, kw = r.get("vector"), r.get("keyword")
    if vec and kw:
        return "fusion_gap"
    if vec:
        return "lexical_gap"
    if kw:
        return "semantic_gap"
    # not found anywhere: is the answer split across neighbouring chunks?
    for g in map(gold_from_dict, case.get("gold", [])):
        if not g.passage:
            continue
        joined = " ".join(h["text"] for h in entry["top10"] if not g.filename or h["filename"].lower().endswith(g.filename.lower()))
        if joined and coverage(g.passage, joined) >= 0.6:
            return "chunk_boundary"
    return "corpus_gap"


def summarize_failures(failures: list[dict]) -> dict:
    c = Counter(f["label"] for f in failures)
    return {"total": len(failures), "by_label": dict(c),
            "recommendations": [{"label": l, "count": n, "action": RECOMMENDATIONS.get(l, "")} for l, n in c.most_common()]}


def cluster_questions(items: list[dict], threshold: float = 0.34) -> list[dict]:
    """Greedy Jaccard clustering of failed questions by shared content stems."""
    clusters: list[dict] = []
    for it in items:
        s = stems(it["question"])
        best, best_j = None, 0.0
        for cl in clusters:
            j = len(s & cl["_stems"]) / len(s | cl["_stems"]) if s | cl["_stems"] else 0
            if j > best_j:
                best, best_j = cl, j
        if best and best_j >= threshold:
            best["items"].append(it)
            best["_stems"] |= s
        else:
            clusters.append({"_stems": set(s), "items": [it]})
    out = []
    for cl in sorted(clusters, key=lambda c: -len(c["items"])):
        freq = Counter(t for it in cl["items"] for t in stems(it["question"]))
        out.append({"size": len(cl["items"]), "top_terms": [t for t, _ in freq.most_common(5)],
                    "labels": dict(Counter(i["label"] for i in cl["items"])),
                    "examples": [i["question"] for i in cl["items"][:3]]})
    return out


# question filler that carries no topical meaning: never worth expanding
FILLER = frozenset("""tell whether right happens happen answers answer works work make made makes get gets many much need needs
should way ways let give show explain mean means does done doing really actually thing things used using different
better best good bad often usually example question questions someone people person""".split())

EXPANSION_ELIGIBLE = {"ranking", "fusion_gap", "corpus_gap", "semantic_gap"}


def propose_expansions(failures: list[dict], cases: dict[str, dict], per_case_top: dict[str, list[dict]], max_per_term: int = 3) -> list[dict]:
    """For lexical_gap failures, map query words missing from the gold passage -> distinctive words in it."""
    proposals: dict[str, dict] = {}
    for f in failures:
        if f["label"] != "lexical_gap":
            # other retrieval failures qualify only when keyword search itself missed or ranked the gold poorly
            kw = (f.get("details") or {}).get("keyword", 0)
            if f["label"] not in EXPANSION_ELIGIBLE or kw == 0 or (kw is not None and kw <= 3):
                continue
        case = cases[f["case_id"]]
        for g in map(gold_from_dict, case.get("gold", [])):
            if not g.passage:
                continue
            gold_terms = [t for t in keyword_terms(g.passage, 80) if len(t) > 4]
            gold_stems = {stem(t) for t in gold_terms}
            qterms = keyword_terms(case["question"])
            missing = [t for t in qterms if stem(t) not in gold_stems and len(t) > 3 and t not in FILLER]
            novel = [t for t in dict.fromkeys(gold_terms) if t not in qterms][:max_per_term * 2]
            for t in missing[:4]:
                p = proposals.setdefault(t, {"term": t, "expansions": [], "support": 0, "examples": []})
                for e in novel[:max_per_term]:
                    if e not in p["expansions"]:
                        p["expansions"].append(e)
                p["support"] += 1
                if case["question"] not in p["examples"]:
                    p["examples"].append(case["question"])
    return sorted(proposals.values(), key=lambda p: -p["support"])
