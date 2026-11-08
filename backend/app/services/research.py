"""Glue: wires the DB-backed retriever, LLM and persistence around the pure agent loop."""
from collections.abc import Iterator

from ..agent.core import AgentConfig, research
from ..agent.llm import get_llm
from ..config import get_settings
from ..db import SessionLocal
from ..models import ResearchRun
from ..schemas import ResearchRequest
from .search import search


def build_config(req: ResearchRequest) -> AgentConfig:
    s = get_settings()
    return AgentConfig(
        max_subquestions=s.max_subquestions, max_rounds=req.max_rounds or s.max_rounds, candidate_k=s.candidate_k,
        evidence_per_subq=s.evidence_per_subq, max_evidence=s.max_evidence,
        sufficiency_threshold=s.sufficiency_threshold, reranker=s.reranker,
        cross_encoder_model=s.cross_encoder_model,
        strict=s.strict_citations if req.strict is None else req.strict,
    )


def run_research_events(req: ResearchRequest) -> Iterator[dict]:
    with SessionLocal() as db:
        run = ResearchRun(question=req.question, status="running")
        db.add(run)
        db.commit()
        yield {"type": "start", "run_id": str(run.id)}
        retriever = lambda q, k, ids: search(db, q, k, "hybrid", ids).hits  # noqa: E731
        trace: list[dict] = []
        try:
            for ev in research(req.question, retriever, get_llm(), build_config(req), req.document_ids, run.id):
                if ev["type"] == "done":
                    res = ev["result"]
                    run.status, run.result, run.metrics = "done", res, res["metrics"]
                    run.duration_ms = res["metrics"]["latency_ms"]
                else:
                    trace.append(ev)
                run.trace = trace
                if ev["type"] == "done":
                    db.commit()
                yield ev
        except Exception as e:  # noqa: BLE001
            db.rollback()
            run = db.get(ResearchRun, run.id)
            run.status, run.error, run.trace = "failed", str(e)[:2000], trace
            db.commit()
            yield {"type": "error", "message": str(e)}
