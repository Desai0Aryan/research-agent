import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import EvalRun, QueryExpansion, ResearchRun
from ..services.feedback import feedback_stats, production_failures, propose_from_eval
from ..services.search import invalidate_expansions

router = APIRouter(prefix="/api", tags=["feedback"])


class FeedbackReq(BaseModel):
    rating: Literal[-1, 0, 1]
    note: str | None = Field(default=None, max_length=2000)


class ProposeReq(BaseModel):
    eval_run_id: uuid.UUID


class StatusReq(BaseModel):
    status: Literal["proposed", "enabled", "rejected"]


def _exp(e: QueryExpansion):
    return {"id": e.id, "term": e.term, "expansions": e.expansions, "status": e.status, "support": e.support, "examples": e.examples}


@router.post("/research/{run_id}/feedback", status_code=204)
def rate(run_id: uuid.UUID, req: FeedbackReq, db: Session = Depends(get_db)):
    run = db.get(ResearchRun, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    run.rating, run.feedback_note = req.rating, req.note
    db.commit()


@router.get("/feedback/failures")
def failures(days: int = 30, db: Session = Depends(get_db)):
    """Failed production queries (thumbs-down, empty, low faithfulness), clustered with fixes."""
    return {**production_failures(db, min(days, 365)), "ratings": feedback_stats(db)}


@router.post("/feedback/expansions/propose")
def propose(req: ProposeReq, db: Session = Depends(get_db)):
    run = db.get(EvalRun, req.eval_run_id)
    if not run:
        raise HTTPException(404, "Eval run not found")
    try:
        return [_exp(e) for e in propose_from_eval(db, run)]
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@router.get("/feedback/expansions")
def list_expansions(db: Session = Depends(get_db)):
    return [_exp(e) for e in db.scalars(select(QueryExpansion).order_by(QueryExpansion.support.desc()))]


@router.patch("/feedback/expansions/{exp_id}")
def set_status(exp_id: uuid.UUID, req: StatusReq, db: Session = Depends(get_db)):
    e = db.get(QueryExpansion, exp_id)
    if not e:
        raise HTTPException(404, "Expansion not found")
    e.status = req.status
    db.commit()
    invalidate_expansions()
    return _exp(e)


@router.delete("/feedback/expansions/{exp_id}", status_code=204)
def delete_expansion(exp_id: uuid.UUID, db: Session = Depends(get_db)):
    e = db.get(QueryExpansion, exp_id)
    if e:
        db.delete(e)
        db.commit()
        invalidate_expansions()
