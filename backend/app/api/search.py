import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Chunk, Document
from ..schemas import ChunkOut, SearchRequest, SearchResponse
from ..services.search import search

router = APIRouter(prefix="/api", tags=["search"])


@router.post("/search", response_model=SearchResponse)
def run_search(req: SearchRequest, db: Session = Depends(get_db)):
    return search(db, req.query, req.top_k, req.mode, req.document_ids)


@router.get("/chunks/{chunk_id}", response_model=ChunkOut)
def get_chunk(chunk_id: uuid.UUID, db: Session = Depends(get_db)):
    """Exact passage + neighbouring context; the target of every citation link."""
    c = db.get(Chunk, chunk_id)
    if not c:
        raise HTTPException(404, "Chunk not found")
    doc = db.get(Document, c.document_id)

    def neighbour(idx: int):
        return db.scalar(select(Chunk.text).where(Chunk.document_id == c.document_id, Chunk.chunk_index == idx))

    return ChunkOut(
        chunk_id=c.id,
        document_id=c.document_id,
        document_title=doc.title,
        page=c.page,
        chunk_index=c.chunk_index,
        text=c.text,
        prev_text=neighbour(c.chunk_index - 1),
        next_text=neighbour(c.chunk_index + 1),
    )
