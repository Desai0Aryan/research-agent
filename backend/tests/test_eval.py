import math
import uuid

from app.eval.diagnose import cluster_questions, diagnose_retrieval, propose_expansions, summarize_failures
from app.eval.golden import generate_cases, load_jsonl
from app.eval.matching import Gold, matches, relevance
from app.eval.metrics import mrr, ndcg_at_k, recall_at_k
from app.eval.runner import build_report, eval_answers, eval_retrieval
from app.schemas import SearchHit
from app.services.text import to_or_tsquery


def hit(fn, page, text):
    return SearchHit(chunk_id=uuid.uuid4(), document_id=uuid.uuid4(), document_title=fn, filename=fn, page=page, text=text, score=1.0)


# ---------- metrics ----------
def test_recall_mrr_ndcg_known_values():
    assert recall_at_k([1, 5, None], 3) == 1 / 3
    assert recall_at_k([1, 5, None], 5) == 2 / 3
    assert mrr([4, 2]) == 0.5 and mrr([None]) == 0.0
    assert math.isclose(ndcg_at_k([False, True, False], 1, 3), 1 / math.log2(3))
    assert ndcg_at_k([True, False, False], 1, 3) == 1.0
    assert ndcg_at_k([False] * 3, 1, 3) == 0.0


# ---------- matching ----------
def test_gold_matching_by_file_page_and_passage():
    g = Gold("a.pdf", 2, "RRF sums reciprocal ranks across retrievers")
    assert matches(hit("a.pdf", 2, "Notes: RRF sums reciprocal ranks across all retrievers."), g)
    assert not matches(hit("a.pdf", 3, "RRF sums reciprocal ranks across retrievers"), g)  # wrong page
    assert not matches(hit("b.pdf", 2, "RRF sums reciprocal ranks across retrievers"), g)  # wrong file
    assert not matches(hit("a.pdf", 2, "banana bread recipe"), g)  # wrong content
    assert not matches(hit("a.pdf", 2, "x"), Gold())  # unanchored gold never matches


def test_relevance_gives_credit_once_per_gold():
    g = [Gold("a.md", None, "alpha beta gamma delta")]
    hits = [hit("z.md", 1, "nothing"), hit("a.md", 1, "alpha beta gamma delta one"), hit("a.md", 1, "alpha beta gamma delta two")]
    rels, ranks = relevance(hits, g)
    assert rels == [False, True, False] and ranks == [2]


# ---------- golden generation ----------
CHUNKS = [
    {"filename": "x.md", "page": 1, "text": "Hierarchical navigable small world graphs accelerate approximate nearest neighbour queries dramatically. " * 4 + "The ef_search parameter controls exploration breadth at query time for recall."},
    {"filename": "y.md", "page": 1, "text": "Sourdough fermentation relies on wild yeast and lactobacilli producing acids slowly overnight. " * 4 + "Hydration percentage strongly influences crumb openness in baked loaves."},
]


def test_generate_cases_is_deterministic_and_adds_unanswerable():
    a = generate_cases(CHUNKS, 2, None, True, seed=1)
    b = generate_cases(CHUNKS, 2, None, True, seed=1)
    assert a == b
    ans = [c for c in a if c["answerable"]]
    assert len(ans) == 2 and all(c["gold"][0]["passage"] for c in ans)
    assert any(not c["answerable"] and not c["gold"] for c in a)


def test_load_jsonl_fills_defaults():
    cs = load_jsonl('{"question":"q?","gold":[{"filename":"a.md"}]}\n\n{"question":"off topic"}')
    assert cs[0]["answerable"] is True and cs[1]["answerable"] is False and cs[0]["id"] == "case1"


# ---------- runner with a fake retriever ----------
GOOD = hit("a.md", 1, "Reciprocal rank fusion merges ranked lists by summing reciprocal ranks for each document")
NOISE = [hit("n.md", 1, f"unrelated filler passage number {i}") for i in range(10)]
CASES = [
    {"id": "c1", "question": "How are ranked lists merged?", "answerable": True,
     "gold": [{"filename": "a.md", "passage": "merges ranked lists by summing reciprocal ranks"}], "key_facts": ["summing reciprocal ranks"]},
    {"id": "c2", "question": "boiling point of tungsten?", "answerable": False, "gold": [], "key_facts": []},
]


def fake_retriever(mode, q, k):
    if mode == "keyword":
        return NOISE[:k]  # keyword misses
    return ([NOISE[0], GOOD] + NOISE[1:])[:k]  # vector/hybrid: gold at rank 2


def test_eval_retrieval_metrics_per_mode_and_failure_labels():
    r = eval_retrieval(CASES, fake_retriever)
    assert r["n_cases"] == 1  # unanswerable excluded from retrieval metrics
    m = r["modes"]
    assert m["hybrid"]["recall@1"] == 0 and m["hybrid"]["recall@3"] == 1 and m["hybrid"]["mrr"] == 0.5
    assert m["keyword"]["recall@10"] == 0
    rep = build_report(CASES, r, None, {})
    assert rep["failures"] == []  # gold at rank 2 is inside the top-3: not a failure


# ---------- diagnosis ----------
def entry(vec, kw, hyb, top10=()):
    return {"ranks": {"vector": [vec], "keyword": [kw], "hybrid": [hyb]}, "top10": list(top10)}


CASE = {"gold": [{"filename": "a.md", "passage": "alpha beta gamma delta epsilon zeta eta theta"}]}


def test_diagnosis_covers_every_root_cause():
    assert diagnose_retrieval(entry(1, 1, 1), CASE) is None
    assert diagnose_retrieval(entry(None, None, 7), CASE) == "ranking"
    assert diagnose_retrieval(entry(2, None, None), CASE) == "lexical_gap"
    assert diagnose_retrieval(entry(None, 2, None), CASE) == "semantic_gap"
    assert diagnose_retrieval(entry(4, 5, None), CASE) == "fusion_gap"
    assert diagnose_retrieval(entry(None, None, None), CASE) == "corpus_gap"
    split = [{"filename": "a.md", "page": 1, "text": "alpha beta gamma delta"}, {"filename": "a.md", "page": 1, "text": "epsilon zeta eta theta"}]
    assert diagnose_retrieval(entry(None, None, None, split), CASE) == "chunk_boundary"


def test_clustering_groups_similar_failed_questions():
    items = [{"question": q, "label": "lexical_gap"} for q in [
        "How do I merge ranked search results?", "How can ranked search results be merged?",
        "What is the best sourdough hydration?"]]
    cl = cluster_questions(items)
    assert [c["size"] for c in cl] == [2, 1] and "merg" in " ".join(cl[0]["top_terms"]) or "result" in " ".join(cl[0]["top_terms"])


def test_expansions_are_learned_from_lexical_gaps_only():
    cases = {"c1": {"question": "How do I combine ranked lists?", "gold": [{"filename": "a.md", "passage": "Reciprocal rank fusion merges ranked lists by summing scores"}]}}
    fails = [{"case_id": "c1", "label": "lexical_gap", "question": cases["c1"]["question"]},
             {"case_id": "c1", "label": "ranking", "question": "ignored"}]
    props = propose_expansions(fails, cases, {})
    assert props and props[0]["term"] == "combine" and "reciprocal" in props[0]["expansions"] or "fusion" in props[0]["expansions"]
    assert all(p["term"] != "ranked" for p in props)  # words already in the passage are not "missing"


def test_expansions_widen_keyword_query_safely():
    q = to_or_tsquery("combine lists", {"combine": ["fusion", "Reciprocal Rank'); DROP"]})
    assert "fusion" in q and "reciprocal" in q and all(c.isalnum() or c in " |" for c in q)


def test_summary_lists_actions_by_frequency():
    s = summarize_failures([{"label": "lexical_gap"}, {"label": "lexical_gap"}, {"label": "ranking"}])
    assert s["recommendations"][0]["label"] == "lexical_gap" and s["recommendations"][0]["count"] == 2 and s["recommendations"][0]["action"]


# ---------- answer evaluation ----------
def fake_result(claims, evidence, sections=True, unsupported=0, faith=1.0):
    return {"sections": [{"heading": "h", "claims": claims}] if sections else [],
            "evidence": evidence, "metrics": {"claims_total": len(claims), "unsupported": unsupported, "faithfulness": faith}}


def test_eval_answers_scores_facts_citations_and_abstention():
    ev = [{"id": "E1", "filename": "a.md", "page": 1, "text": "Reciprocal rank fusion merges ranked lists by summing reciprocal ranks"}]
    good = fake_result([{"text": "Fusion works by summing reciprocal ranks.", "evidence_ids": ["E1"]}], ev)
    silent = fake_result([], [], sections=False)
    answers = {"How are ranked lists merged?": good, "boiling point of tungsten?": silent}
    out = eval_answers(CASES, lambda q: answers[q])
    assert out["answer_correctness"] == 1.0 and out["gold_citation_rate"] == 1.0 and out["abstention_accuracy"] == 1.0
    chatty = fake_result([{"text": "Tungsten boils somewhere hot.", "evidence_ids": ["E1"]}], ev, unsupported=1, faith=0.0)
    out2 = eval_answers(CASES, lambda q: answers[q] if "merged" in q else chatty)
    assert out2["abstention_accuracy"] == 0.0
    labels = build_report(CASES, eval_retrieval(CASES, fake_retriever), out2, {})["failures"]
    assert {f["label"] for f in labels} == {"answered_unanswerable"}
