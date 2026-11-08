import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..eval.diagnose import cluster_questions
from ..eval.golden import load_jsonl
from ..models import EvalRun, EvalSet
from ..services.evaluation import compare, generate_set, run_eval

router = APIRouter(prefix="/api/eval", tags=["evaluation"])


class GenerateReq(BaseModel):
    name: str = "synthetic"
    n_cases: int = Field(default=20, ge=1, le=200)
    include_unanswerable: bool = True
    seed: int = 7
    use_llm: bool = True  # falls back to heuristic generation when no LLM is configured


class ImportReq(BaseModel):
    name: str
    jsonl: str | None = None
    cases: list[dict] | None = None


class RunReq(BaseModel):
    set_id: uuid.UUID
    name: str | None = None
    modes: list[Literal["hybrid", "vector", "keyword"]] = ["hybrid", "vector", "keyword"]
    ks: list[int] = [1, 3, 5, 10]
    e2e: bool = False
    use_expansions: bool = True
    max_cases: int | None = Field(default=None, ge=1)
    split: Literal["all", "train", "test"] = "all"  # train/test = deterministic halves (leak-free expansion learning)


def _set_out(s: EvalSet, full=False):
    d = {"id": s.id, "name": s.name, "n_cases": len(s.cases), "n_answerable": sum(1 for c in s.cases if c.get("answerable", True)), "created_at": s.created_at}
    return {**d, "cases": s.cases} if full else d


def _run_out(r: EvalRun, full=False):
    d = {"id": r.id, "set_id": r.set_id, "name": r.name, "config": r.config, "summary": r.summary, "created_at": r.created_at}
    return {**d, "report": r.report} if full else d


@router.post("/sets/generate")
def generate(req: GenerateReq, db: Session = Depends(get_db)):
    es = generate_set(db, req.name, req.n_cases, req.include_unanswerable, req.seed, req.use_llm)
    if not es.cases:
        raise HTTPException(422, "No ready documents to generate cases from")
    return _set_out(es, full=True)


@router.post("/sets")
def import_set(req: ImportReq, db: Session = Depends(get_db)):
    cases = load_jsonl(req.jsonl) if req.jsonl else req.cases
    if not cases:
        raise HTTPException(422, "Provide `jsonl` or `cases`")
    es = EvalSet(name=req.name, cases=cases)
    db.add(es)
    db.commit()
    return _set_out(es)


@router.get("/sets")
def list_sets(db: Session = Depends(get_db)):
    return [_set_out(s) for s in db.scalars(select(EvalSet).order_by(EvalSet.created_at.desc()))]


@router.get("/sets/{set_id}")
def get_set(set_id: uuid.UUID, db: Session = Depends(get_db)):
    es = db.get(EvalSet, set_id)
    if not es:
        raise HTTPException(404, "Eval set not found")
    return _set_out(es, full=True)


@router.delete("/sets/{set_id}", status_code=204)
def delete_set(set_id: uuid.UUID, db: Session = Depends(get_db)):
    es = db.get(EvalSet, set_id)
    if not es:
        raise HTTPException(404, "Eval set not found")
    db.delete(es)
    db.commit()


@router.post("/runs")
def create_run(req: RunReq, db: Session = Depends(get_db)):
    es = db.get(EvalSet, req.set_id)
    if not es:
        raise HTTPException(404, "Eval set not found")
    run = run_eval(db, es, req.name or f"run {len(es.cases)} cases", req.modes, req.ks, req.e2e, req.use_expansions, req.max_cases, req.split)
    return _run_out(run, full=True)


@router.get("/runs")
def list_runs(set_id: uuid.UUID | None = None, db: Session = Depends(get_db)):
    q = select(EvalRun).order_by(EvalRun.created_at.desc()).limit(100)
    if set_id:
        q = q.where(EvalRun.set_id == set_id)
    return [_run_out(r) for r in db.scalars(q)]


@router.get("/runs/{run_id}")
def get_run(run_id: uuid.UUID, db: Session = Depends(get_db)):
    r = db.get(EvalRun, run_id)
    if not r:
        raise HTTPException(404, "Eval run not found")
    return _run_out(r, full=True)


@router.get("/runs/{run_id}/failures")
def run_failures(run_id: uuid.UUID, db: Session = Depends(get_db)):
    r = db.get(EvalRun, run_id)
    if not r:
        raise HTTPException(404, "Eval run not found")
    f = r.report["failures"]
    return {"failures": f, "clusters": cluster_questions(f), "summary": r.report["failure_summary"]}


@router.get("/compare")
def compare_runs(a: uuid.UUID, b: uuid.UUID, db: Session = Depends(get_db)):
    ra, rb = db.get(EvalRun, a), db.get(EvalRun, b)
    if not ra or not rb:
        raise HTTPException(404, "Eval run not found")
    return {"a": _run_out(ra), "b": _run_out(rb), "deltas": compare(ra.summary, rb.summary)}
