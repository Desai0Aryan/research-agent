"""Hybrid retrieval: pgvector cosine ANN + Postgres full-text (ts_rank_cd), fused with RRF."""
import time
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Chunk, Document
from ..schemas import SearchHit, SearchResponse
from .embeddings import get_embedder
from .fusion import rrf
from .text import keyword_terms, to_or_tsquery


def _vector_candidates(db: Session, qvec, pool: int, doc_ids) -> list[tuple[uuid.UUID, float]]:
    dist = Chunk.embedding.cosine_distance(qvec)
    stmt = select(Chunk.id, dist.label("d")).order_by(dist).limit(pool)
    if doc_ids:
        stmt = stmt.where(Chunk.document_id.in_(doc_ids))
    return [(r.id, 1.0 - float(r.d)) for r in db.execute(stmt)]


def _keyword_candidates(db: Session, query: str, pool: int, doc_ids) -> list[tuple[uuid.UUID, float]]:
    tsq_str = to_or_tsquery(query)
    if not tsq_str:
        return []
    tsq = func.to_tsquery("english", tsq_str)
    rank = func.ts_rank_cd(Chunk.tsv, tsq, 32)
    stmt = select(Chunk.id, rank.label("r")).where(Chunk.tsv.op("@@")(tsq)).order_by(rank.desc()).limit(pool)
    if doc_ids:
        stmt = stmt.where(Chunk.document_id.in_(doc_ids))
    return [(r.id, float(r.r)) for r in db.execute(stmt)]


def search(
    db: Session,
    query: str,
    top_k: int = 10,
    mode: str = "hybrid",
    document_ids: list[uuid.UUID] | None = None,
) -> SearchResponse:
    t0 = time.perf_counter()
    s = get_settings()
    pool = max(s.candidate_pool, top_k * 3)

    vec: list[tuple[uuid.UUID, float]] = []
    kw: list[tuple[uuid.UUID, float]] = []
    if mode in ("hybrid", "vector"):
        vec = _vector_candidates(db, get_embedder().embed_one(query), pool, document_ids)
    if mode in ("hybrid", "keyword"):
        kw = _keyword_candidates(db, query, pool, document_ids)

    v_rank = {cid: i for i, (cid, _) in enumerate(vec, 1)}
    k_rank = {cid: i for i, (cid, _) in enumerate(kw, 1)}
    v_sim, k_sc = dict(vec), dict(kw)
    fused = rrf([[c for c, _ in vec], [c for c, _ in kw]], k=s.rrf_k)
    ordered = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)[:top_k]

    ids = [cid for cid, _ in ordered]
    rows = {}
    if ids:
        q = select(Chunk, Document.title, Document.filename).join(Document).where(Chunk.id.in_(ids))
        rows = {c.id: (c, t, f) for c, t, f in db.execute(q)}

    terms = keyword_terms(query)
    hits: list[SearchHit] = []
    for cid, score in ordered:
        c, title, fname = rows[cid]
        low = c.text.lower()
        hits.append(
            SearchHit(
                chunk_id=cid,
                document_id=c.document_id,
                document_title=title,
                filename=fname,
                page=c.page,
                text=c.text,
                score=round(score, 6),
                vector_rank=v_rank.get(cid),
                keyword_rank=k_rank.get(cid),
                vector_similarity=v_sim.get(cid),
                keyword_score=k_sc.get(cid),
                matched_terms=[t for t in terms if t in low],
            )
        )
    return SearchResponse(query=query, mode=mode, took_ms=round((time.perf_counter() - t0) * 1000, 2), hits=hits)
