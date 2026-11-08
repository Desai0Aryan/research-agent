"""The research loop. Pure orchestration: retriever + llm are injected, so it is testable without a DB."""
import time
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass

from ..schemas import (
    CitationOut, ClaimOut, EvidenceOut, MetricsOut, ResearchResult, SearchHit, SectionOut,
)
from .decompose import decompose
from .llm import LLM
from .rerank import Ranked, followup_queries, rerank
from .verifier import verify_claims
from .writer import extractive_write, llm_write

Retriever = Callable[[str, int, "list[uuid.UUID] | None"], list[SearchHit]]


@dataclass
class AgentConfig:
    max_subquestions: int = 4
    max_rounds: int = 2
    candidate_k: int = 20
    evidence_per_subq: int = 5
    max_evidence: int = 16
    sufficiency_threshold: float = 0.35
    reranker: str = "lexical"
    cross_encoder_model: str = ""
    strict: bool = True


def _url(doc_id, page) -> str:
    return f"/api/documents/{doc_id}/file#page={page}"


def render_markdown(title, sections, gaps, citations) -> str:
    md = [f"# {title}", ""]
    for s in sections:
        md += [f"## {s.heading}", ""]
        for c in s.claims:
            mark = "".join(f"[{n}]" for n in c.citations)
            flag = " ⚠️ *partially supported*" if c.verdict == "partial" else ""
            md.append(f"- {c.text} {mark}{flag}")
        md.append("")
    if gaps:
        md += ["## Gaps in the evidence", ""] + [f"- {g}" for g in gaps] + [""]
    md += ["## References", ""]
    md += [f"[{c.n}] {c.document_title}, p. {c.page}" for c in citations]
    return "\n".join(md)


def research(
    question: str,
    retriever: Retriever,
    llm: LLM | None,
    cfg: AgentConfig,
    document_ids: list[uuid.UUID] | None = None,
    run_id: uuid.UUID | None = None,
) -> Iterator[dict]:
    t0 = time.perf_counter()
    warnings: list[str] = []
    warn = warnings.append
    engine = llm.name if llm else "heuristic"

    # 1) plan
    yield {"type": "status", "message": "Planning: decomposing the question"}
    subqs = decompose(question, llm, cfg.max_subquestions, warn)
    yield {"type": "plan", "sub_questions": subqs, "engine": engine}

    # 2) multi-step retrieval per sub-question
    per_sq: dict[int, list[Ranked]] = {}
    rounds_used = 1
    for i, sq in enumerate(subqs):
        queries, pool = [sq], {}
        ranked: list[Ranked] = []
        for rnd in range(1, cfg.max_rounds + 1):
            for q in queries:
                hits = retriever(q, cfg.candidate_k, document_ids)
                for h in hits:
                    pool.setdefault(h.chunk_id, h)
                yield {"type": "retrieve", "sub_question": i, "round": rnd, "query": q, "hits": len(hits)}
            ranked = rerank(sq, list(pool.values()), cfg.evidence_per_subq, cfg.reranker, llm, cfg.cross_encoder_model, warn)
            best = ranked[0].score if ranked else 0.0
            yield {"type": "rerank", "sub_question": i, "round": rnd, "kept": len(ranked), "best_score": round(best, 3)}
            rounds_used = max(rounds_used, rnd)
            if best >= cfg.sufficiency_threshold or rnd == cfg.max_rounds:
                break
            queries = followup_queries(sq, ranked, llm, warn)
            yield {"type": "gap", "sub_question": i, "message": "Evidence looks thin; trying reformulated queries", "queries": queries}
            if not queries:
                break
        per_sq[i] = ranked

    # 3) build a global, de-duplicated evidence set with stable IDs
    best: dict[uuid.UUID, Ranked] = {}
    for rl in per_sq.values():
        for r in rl:
            if r.hit.chunk_id not in best or r.score > best[r.hit.chunk_id].score:
                best[r.hit.chunk_id] = r
    ordered = sorted(best.values(), key=lambda r: -r.score)[: cfg.max_evidence]
    eid_of = {r.hit.chunk_id: f"E{n}" for n, r in enumerate(ordered, 1)}
    evidence = {
        eid_of[r.hit.chunk_id]: {"title": r.hit.document_title, "page": r.hit.page, "text": r.hit.text, "r": r}
        for r in ordered
    }
    per_sq_eids = {i: [eid_of[r.hit.chunk_id] for r in rl if r.hit.chunk_id in eid_of] for i, rl in per_sq.items()}
    yield {"type": "evidence", "count": len(evidence), "documents": len({r.hit.document_id for r in ordered})}

    # 4) write
    yield {"type": "status", "message": "Writing the cited report"}
    if not evidence:
        draft = {"title": question, "sections": [], "gaps": ["No relevant evidence was found in the library."]}
    else:
        draft = None
        if llm:
            try:
                draft = llm_write(question, subqs, evidence, llm)
            except Exception as e:  # noqa: BLE001
                warn(f"LLM writer failed, using extractive writer: {e}")
        if draft is None or not draft["sections"]:
            draft = extractive_write(question, subqs, evidence, per_sq_eids)

    # 5) verify every claim against the passages it cites
    yield {"type": "status", "message": "Verifying every claim against its cited passages"}
    flat = [(si, c) for si, s in enumerate(draft["sections"]) for c in s["claims"]]
    items = []
    for _, c in flat:
        valid = [e for e in dict.fromkeys(c["evidence"]) if e in evidence]
        c["evidence"] = valid
        items.append((c["text"], [evidence[e]["text"] for e in valid]))
    verdicts = verify_claims(items, llm, warn)

    strict = cfg.strict
    kept_claims: dict[int, list[ClaimOut]] = {}
    removed: list[ClaimOut] = []
    cite_no: dict[str, int] = {}
    counts = {"supported": 0, "partial": 0, "unsupported": 0}
    for n, ((si, c), v) in enumerate(zip(flat, verdicts), 1):
        counts[v.verdict] += 1
        out = ClaimOut(
            id=f"C{n}", text=c["text"], evidence_ids=c["evidence"], citations=[], verdict=v.verdict,
            support_score=v.score, quote=v.quote, quote_verified=v.quote_verified, reason=v.reason,
        )
        if strict and v.verdict == "unsupported":
            removed.append(out)
            continue
        for e in c["evidence"]:
            cite_no.setdefault(e, len(cite_no) + 1)
        out.citations = sorted(cite_no[e] for e in c["evidence"])
        kept_claims.setdefault(si, []).append(out)
    sections = [
        SectionOut(heading=s["heading"], claims=kept_claims[si])
        for si, s in enumerate(draft["sections"]) if si in kept_claims
    ]
    ev_by_id = {eid: e["r"].hit for eid, e in evidence.items()}
    citations = [
        CitationOut(n=n, evidence_id=eid, chunk_id=ev_by_id[eid].chunk_id, document_id=ev_by_id[eid].document_id,
                    document_title=ev_by_id[eid].document_title, page=ev_by_id[eid].page,
                    url=_url(ev_by_id[eid].document_id, ev_by_id[eid].page))
        for eid, n in sorted(cite_no.items(), key=lambda kv: kv[1])
    ]
    gaps = list(draft.get("gaps", []))
    if removed:
        gaps.append(f"{len(removed)} draft claim(s) were removed because the cited sources did not support them.")

    total = len(flat)
    metrics = MetricsOut(
        claims_total=total, supported=counts["supported"], partial=counts["partial"], unsupported=counts["unsupported"],
        removed=len(removed),
        citation_coverage=round(sum(1 for _, c in flat if c["evidence"]) / total, 3) if total else 0.0,
        faithfulness=round((counts["supported"] + 0.5 * counts["partial"]) / total, 3) if total else 0.0,
        unsupported_rate=round(counts["unsupported"] / total, 3) if total else 0.0,
        evidence_count=len(evidence), documents_used=len({r.hit.document_id for r in ordered}),
        retrieval_rounds=rounds_used, latency_ms=int((time.perf_counter() - t0) * 1000),
    )
    result = ResearchResult(
        run_id=run_id, question=question, title=draft["title"], sub_questions=subqs, sections=sections,
        removed_claims=removed, gaps=gaps, citations=citations,
        evidence=[
            EvidenceOut(id=eid, chunk_id=e["r"].hit.chunk_id, document_id=e["r"].hit.document_id,
                        document_title=e["title"], page=e["page"], text=e["text"],
                        relevance=round(e["r"].score, 3), url=_url(e["r"].hit.document_id, e["page"]))
            for eid, e in evidence.items()
        ],
        markdown=render_markdown(draft["title"], sections, gaps, citations),
        metrics=metrics, engine=engine, warnings=warnings,
    )
    yield {"type": "done", "result": result.model_dump(mode="json")}
