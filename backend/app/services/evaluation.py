"""DB/LLM glue for the evaluation pipeline."""
import hashlib
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..agent.core import research
from ..agent.llm import get_llm
from ..config import get_settings
from ..eval.golden import generate_cases
from ..eval.runner import build_report, eval_answers, eval_retrieval
from ..models import Chunk, Document, EvalRun, EvalSet
from ..schemas import ResearchRequest
from .research import build_config
from .search import search


def in_split(case_id: str, split: str) -> bool:
    """Deterministic 50/50 train/test split by case id, so learning never sees the cases it is scored on."""
    if split == "all":
        return True
    is_train = int(hashlib.md5(case_id.encode()).hexdigest(), 16) % 2 == 0
    return is_train if split == "train" else not is_train


def sample_chunks(db: Session) -> list[dict]:
    q = select(Document.filename, Chunk.page, Chunk.text).join(Chunk).where(Document.status == "ready")
    return [{"filename": f, "page": p, "text": t} for f, p, t in db.execute(q)]


def generate_set(db: Session, name: str, n: int, include_unanswerable: bool, seed: int, use_llm: bool) -> EvalSet:
    cases = generate_cases(sample_chunks(db), n, get_llm() if use_llm else None, include_unanswerable, seed)
    es = EvalSet(name=name, cases=cases)
    db.add(es)
    db.commit()
    return es


def run_eval(db: Session, es: EvalSet, name: str, modes, ks, e2e: bool, use_expansions: bool, max_cases: int | None, split: str = "all") -> EvalRun:
    s = get_settings()
    cases = [c for c in es.cases if in_split(c["id"], split)]
    cases = cases[:max_cases] if max_cases else cases
    retr = lambda mode, q, k: search(db, q, k, mode, None, use_expansions=use_expansions).hits  # noqa: E731
    retrieval = eval_retrieval(cases, retr, tuple(modes), tuple(ks))
    answers = None
    if e2e:
        llm = get_llm()

        def run_agent(q: str) -> dict:
            cfg = build_config(ResearchRequest(question=q))
            r = lambda qq, k, ids: search(db, qq, k, "hybrid", ids, use_expansions=use_expansions).hits  # noqa: E731
            for ev in research(q, r, llm, cfg):
                if ev["type"] == "done":
                    return ev["result"]
            raise RuntimeError("agent returned nothing")

        answers = eval_answers(cases, run_agent)
    config = {"modes": list(modes), "ks": list(ks), "e2e": e2e, "use_expansions": use_expansions, "split": split,
              "embedding": f"{s.embedding_provider}:{s.embedding_model}:{s.embedding_dim}",
              "chunk": f"{s.chunk_target_words}/{s.chunk_overlap_words}", "reranker": s.reranker,
              "engine": llm.name if (llm := get_llm()) else "heuristic", "n_cases": len(cases)}
    report = build_report(cases, retrieval, answers, config)
    run = EvalRun(set_id=es.id, name=name, config=config, report=report, summary=report["summary"])
    db.add(run)
    db.commit()
    return run


def compare(a: dict, b: dict) -> list[dict]:
    keys = sorted(set(a) | set(b))
    rows = []
    for k in keys:
        x, y = a.get(k), b.get(k)
        rows.append({"metric": k, "a": x, "b": y, "delta": round(y - x, 4) if isinstance(x, (int, float)) and isinstance(y, (int, float)) else None})
    return rows
