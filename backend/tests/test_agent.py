"""Agent tests run without Postgres: an in-memory hybrid-ish retriever and scripted LLMs."""
import json
import uuid

from app.agent.core import AgentConfig, research
from app.agent.decompose import heuristic_decompose
from app.agent.llm import LLM, extract_json
from app.agent.verifier import lexical_verify, verify_claims
from app.schemas import SearchHit
from app.services.embeddings import HashEmbedder
from app.services.text import coverage

DOC_A, DOC_B = uuid.uuid4(), uuid.uuid4()
CORPUS = [
    (DOC_A, "Hybrid Search Guide", 1, "Reciprocal Rank Fusion merges ranked lists by summing 1/(k+rank) for each document. A common default is k=60."),
    (DOC_A, "Hybrid Search Guide", 2, "Cross-encoder rerankers re-score the top candidates by reading the query and passage together. They are slower than bi-encoders but more accurate."),
    (DOC_B, "RAG Evaluation", 4, "An unsupported claim is a statement in the answer that no retrieved passage entails. Tracking the unsupported claim rate quantifies hallucination."),
    (DOC_B, "RAG Evaluation", 5, "Retrieval quality is measured with recall at k, mean reciprocal rank and nDCG against labelled question passage pairs."),
    (DOC_B, "Cooking Notes", 1, "Banana bread needs ripe bananas, flour and a moderate oven."),
]
HITS = [SearchHit(chunk_id=uuid.uuid4(), document_id=d, document_title=t, filename=t + ".pdf", page=p, text=x, score=1.0) for d, t, p, x in CORPUS]
EMB = HashEmbedder(256)


def retriever(q, k, ids=None):
    qv = EMB.embed_one(q)
    sc = sorted(HITS, key=lambda h: -(sum(a * b for a, b in zip(qv, EMB.embed_one(h.text))) + coverage(q, h.text)))
    return sc[:k]


def run(question, llm=None, **cfg):
    events = list(research(question, retriever, llm, AgentConfig(**cfg)))
    return events, events[-1]["result"]


def test_extract_json_handles_fences_and_prose():
    assert extract_json('Sure!\n```json\n{"a": [1,2]}\n```') == {"a": [1, 2]}


def test_heuristic_decompose_splits_multi_part_questions():
    subs = heuristic_decompose("How does RRF work; and what does a reranker do?", 4)
    assert len(subs) >= 2 and subs[0].endswith("?")


def test_end_to_end_heuristic_report_has_verified_page_citations():
    events, r = run("How does reciprocal rank fusion work and what is a cross-encoder reranker?")
    assert [e["type"] for e in events][:2] == ["status", "plan"]
    assert r["engine"] == "heuristic" and r["sections"]
    assert r["metrics"]["citation_coverage"] == 1.0 and r["metrics"]["unsupported"] == 0
    cites = {(c["document_title"], c["page"]) for c in r["citations"]}
    assert ("Hybrid Search Guide", 1) in cites
    assert all(c["url"].endswith(f"#page={c['page']}") for c in r["citations"])
    assert "Banana" not in r["markdown"]
    for s in r["sections"]:
        for c in s["claims"]:
            assert c["citations"] and c["quote"]


def test_off_topic_question_yields_gaps_not_hallucinations():
    _, r = run("What is the airspeed velocity of an unladen swallow?")
    assert r["metrics"]["unsupported"] == 0
    assert r["gaps"] or not r["sections"]


class ScriptedLLM(LLM):
    """Plays a writer that hallucinates one claim and fabricates a quote for another."""
    name = "scripted"

    def complete(self, system, user, *, json_mode=False, max_tokens=3000):
        if "You plan research" in system:
            return json.dumps({"sub_questions": ["How does reciprocal rank fusion work?"]})
        if "meticulous research analyst" in system:
            return json.dumps({"title": "RRF", "sections": [{"heading": "Key findings", "claims": [
                {"text": "Reciprocal Rank Fusion sums 1/(k+rank) across ranked lists.", "evidence": ["E1"]},
                {"text": "RRF was invented at NASA in 1987 and needs 40 GPUs.", "evidence": ["E1"]},
                {"text": "A common default for k is 60.", "evidence": ["E1"]},
            ]}], "gaps": []})
        if "fact-checker" in system:
            return json.dumps({"results": [
                {"i": 0, "verdict": "supported", "quote": "merges ranked lists by summing 1/(k+rank)", "reason": "stated"},
                {"i": 1, "verdict": "supported", "quote": "invented at NASA in 1987", "reason": "rubber stamp"},
                {"i": 2, "verdict": "supported", "quote": "A common default is k=60.", "reason": "stated"},
            ]})
        if "judge whether" in system:
            return json.dumps({"sufficient": True, "queries": []})
        raise AssertionError(system[:40])


def test_llm_path_catches_hallucinated_claim_and_strict_mode_removes_it():
    _, r = run("How does reciprocal rank fusion work?", ScriptedLLM(), strict=True)
    texts = [c["text"] for s in r["sections"] for c in s["claims"]]
    assert "RRF was invented at NASA in 1987 and needs 40 GPUs." not in texts
    assert [c["text"] for c in r["removed_claims"]] == ["RRF was invented at NASA in 1987 and needs 40 GPUs."]
    assert r["metrics"]["unsupported"] == 1 and r["metrics"]["removed"] == 1
    assert r["metrics"]["unsupported_rate"] == round(1 / 3, 3)
    assert all(c["quote_verified"] for s in r["sections"] for c in s["claims"])


def test_non_strict_mode_keeps_but_flags_unsupported():
    _, r = run("How does reciprocal rank fusion work?", ScriptedLLM(), strict=False)
    claims = [c for s in r["sections"] for c in s["claims"]]
    assert len(claims) == 3 and sum(c["verdict"] == "unsupported" for c in claims) == 1


def test_uncited_claim_is_unsupported_and_numbers_must_match():
    assert lexical_verify("anything", []).verdict == "unsupported"
    assert lexical_verify("A common default is k=60.", [CORPUS[0][3]]).verdict == "supported"
    assert lexical_verify("A common default is k=99.", [CORPUS[0][3]]).verdict != "supported"
    assert verify_claims([("x y z", [])], None)[0].verdict == "unsupported"
