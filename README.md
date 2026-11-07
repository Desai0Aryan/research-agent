# Enterprise AI Research Agent with Verifiable Citations

Research complex questions across hundreds of PDFs and docs, compare sources, and get a report where **every claim is cited to an exact passage and page**.

> **Status: Part 1 of 5 — ingestion + hybrid retrieval foundation.**

## Roadmap
- [x] **Part 1** – Docker/Postgres+pgvector, ingestion, page-aware chunking, hybrid search (vector + FTS + RRF), API
- [ ] Part 2 – Agent: query decomposition, multi-step retrieval, reranking, cited report, citation verifier
- [ ] Part 3 – Evaluation pipeline + failed-query feedback loop
- [ ] Part 4 – Next.js UI with PDF citation viewer
- [ ] Part 5 – CI, auth, observability, polish

## Quick start
```bash
make up                         # Postgres+pgvector and the API on :8000
python scripts/upload.py samples/*
python scripts/upload.py --query "How does reciprocal rank fusion work?"
open http://localhost:8000/docs # interactive OpenAPI
```
Tests (no DB needed): `make test`

## Architecture (so far)
```
upload ─▶ parse (pypdf per page) ─▶ chunk (sentence-packing, never crosses pages)
       ─▶ embed (hash | local | openai) ─▶ Postgres: chunks(embedding HNSW, tsv GIN)

query ─▶ ┌ vector top-N  (pgvector cosine, HNSW) ┐
         └ keyword top-N (to_tsquery OR, ts_rank_cd) ┴▶ Reciprocal Rank Fusion ▶ hits
                                                       (page + passage + per-retriever ranks)
```
**Design choices**
- Chunks stay within a page → every citation resolves to a real PDF page (`/api/documents/{id}/file#page=N`).
- RRF avoids calibrating cosine vs. BM25-style scores.
- Content-hash dedupe makes re-uploads idempotent.
- Embedding provider is swappable; **changing `EMBEDDING_DIM` requires recreating the DB volume** (`docker compose down -v`).

## API
| Method | Path | Purpose |
|---|---|---|
| POST | `/api/documents` | Upload PDF/MD/TXT (multi-file, async ingest) |
| GET | `/api/documents` · `/{id}` | List / status |
| GET | `/api/documents/{id}/file` | Original file (for viewer) |
| DELETE | `/api/documents/{id}` | Remove doc + chunks |
| POST | `/api/search` | `{query, top_k, mode: hybrid\|vector\|keyword, document_ids}` |
| GET | `/api/chunks/{id}` | Exact cited passage + neighbours |
| GET | `/health` | Status + counts |

Known limits (addressed later): no OCR for scanned PDFs, no auth.
