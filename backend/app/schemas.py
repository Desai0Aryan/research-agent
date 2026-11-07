import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    filename: str
    title: str
    mime: str
    num_pages: int
    num_chunks: int
    status: str
    error: str | None = None
    created_at: datetime


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=2000)
    top_k: int = Field(default=10, ge=1, le=50)
    mode: Literal["hybrid", "vector", "keyword"] = "hybrid"
    document_ids: list[uuid.UUID] | None = None


class SearchHit(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    filename: str
    page: int
    text: str
    score: float
    vector_rank: int | None = None
    keyword_rank: int | None = None
    vector_similarity: float | None = None
    keyword_score: float | None = None
    matched_terms: list[str] = []


class SearchResponse(BaseModel):
    query: str
    mode: str
    took_ms: float
    hits: list[SearchHit]


class ChunkOut(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    page: int
    chunk_index: int
    text: str
    prev_text: str | None = None
    next_text: str | None = None
