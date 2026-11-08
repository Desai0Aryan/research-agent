import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import ResearchRun
from ..schemas import ResearchRequest, ResearchResult, ResearchRunOut
from ..services.research import run_research_events

router = APIRouter(prefix="/api/research", tags=["research"])


@router.post("", response_model=ResearchResult)
def research_sync(req: ResearchRequest):
    for ev in run_research_events(req):
        if ev["type"] == "done":
            return ev["result"]
        if ev["type"] == "error":
            raise HTTPException(500, ev["message"])
    raise HTTPException(500, "Agent produced no result")


@router.post("/stream")
def research_stream(req: ResearchRequest):
    """Server-Sent Events: start, status, plan, retrieve, rerank, gap, evidence, done | error."""

    def gen():
        for ev in run_research_events(req):
            yield f"data: {json.dumps(ev)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("", response_model=list[ResearchRunOut])
def list_runs(limit: int = 50, db: Session = Depends(get_db)):
    return db.scalars(select(ResearchRun).order_by(ResearchRun.created_at.desc()).limit(min(limit, 200))).all()


@router.get("/{run_id}", response_model=ResearchResult)
def get_run(run_id: uuid.UUID, db: Session = Depends(get_db)):
    run = db.get(ResearchRun, run_id)
    if not run or not run.result:
        raise HTTPException(404, "Run not found or not finished")
    return run.result
