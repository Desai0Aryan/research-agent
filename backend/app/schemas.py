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
    ocr_pages: int = 0
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


# ---------------- Research agent ----------------
class ResearchRequest(BaseModel):
    question: str = Field(min_length=5, max_length=3000)
    document_ids: list[uuid.UUID] | None = None
    strict: bool | None = None  # drop unsupported claims from the report (default: server setting)
    max_rounds: int | None = Field(default=None, ge=1, le=4)


class EvidenceOut(BaseModel):
    id: str  # E1, E2, ...
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    filename: str = ""
    page: int
    text: str
    relevance: float
    url: str  # /api/documents/{id}/file#page=N


class ClaimOut(BaseModel):
    id: str
    text: str
    evidence_ids: list[str]
    citations: list[int]  # footnote numbers in the rendered report
    verdict: Literal["supported", "partial", "unsupported"]
    support_score: float
    quote: str | None = None  # verbatim supporting sentence from the cited passage
    quote_verified: bool = False
    reason: str | None = None


class SectionOut(BaseModel):
    heading: str
    claims: list[ClaimOut]


class CitationOut(BaseModel):
    n: int
    evidence_id: str
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    page: int
    url: str


class MetricsOut(BaseModel):
    claims_total: int
    supported: int
    partial: int
    unsupported: int
    removed: int
    citation_coverage: float  # share of claims with >=1 citation
    faithfulness: float  # (supported + 0.5*partial) / total
    unsupported_rate: float
    evidence_count: int
    documents_used: int
    retrieval_rounds: int
    latency_ms: int


class ResearchResult(BaseModel):
    run_id: uuid.UUID | None = None
    question: str
    title: str
    sub_questions: list[str]
    sections: list[SectionOut]
    removed_claims: list[ClaimOut] = []
    gaps: list[str] = []
    citations: list[CitationOut]
    evidence: list[EvidenceOut]
    markdown: str
    metrics: MetricsOut
    engine: str  # e.g. "anthropic:claude-sonnet-5-5" or "heuristic"
    warnings: list[str] = []


class ResearchRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    question: str
    status: str
    duration_ms: int | None = None
    metrics: dict | None = None
    created_at: datetime
