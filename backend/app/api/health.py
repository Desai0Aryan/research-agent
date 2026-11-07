from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import Chunk, Document

router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    s = get_settings()
    return {
        "status": "ok",
        "embedding_provider": s.embedding_provider,
        "embedding_dim": s.embedding_dim,
        "documents": db.scalar(select(func.count()).select_from(Document)),
        "chunks": db.scalar(select(func.count()).select_from(Chunk)),
    }
