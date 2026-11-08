# Enterprise AI Research Agent with Verifiable Citations

Research complex questions across hundreds of PDFs and docs, compare sources, and get a report where **every claim is cited to an exact passage and page**.

> **Status: Part 2 of 5 — research agent with verified, claim-level citations.**

## Roadmap
- [x] **Part 1** – Docker/Postgres+pgvector, ingestion, page-aware chunking, hybrid search (vector + FTS + RRF), API
- [x] **Part 2** – Agent: query decomposition, multi-step retrieval, reranking, cited report, citation verifier
- [ ] Part 3 – Evaluation pipeline + failed-query feedback loop
- [ ] Part 4 – Next.js UI with PDF citation viewer
- [ ] Part 5 – CI, auth, observability, polish

## Quick start
```bash
make up                         # Postgres+pgvector and the API on :8000
python scripts/upload.py samples/*
python scripts/upload.py --query "How does reciprocal rank fusion work?"
python scripts/ask.py "How does RRF work, and how do we measure hallucination in RAG?"
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

## The research agent (Part 2)
```
question ─▶ decompose ─▶ sub-questions
   for each: hybrid search ─▶ rerank ─▶ best score < threshold? ─▶ reformulate & retry (multi-step)
   ─▶ de-duplicated evidence set (E1…En, each = exact chunk + page)
   ─▶ writer: atomic claims, each citing evidence IDs     (LLM, or offline extractive writer)
   ─▶ verifier: does the cited text entail the claim?     (LLM judge ⊕ lexical check)
        • supporting quote must appear VERBATIM in the passage
        • numbers in a claim must exist in the evidence
        • a judge's "supported" is downgraded if quote/overlap can't be verified
   ─▶ strict mode drops unsupported claims; partial ones are flagged
   ─▶ markdown report + [n] footnotes → /api/documents/{id}/file#page=N, plus metrics
```
Every run is persisted (result + event trace) in `research_runs`, which Part 3's evaluation and feedback loop consume.

**Engines.** `LLM_PROVIDER=none` runs a fully offline heuristic engine (extractive, still verified) so the whole pipeline works without keys. Set `LLM_PROVIDER=anthropic|openai` for fluent comparative reports; the verifier still cross-checks the LLM judge lexically so it cannot simply rubber-stamp hallucinations. Reranker options: `lexical`, `llm`, `cross-encoder`.

## API
| Method | Path | Purpose |
|---|---|---|
| POST | `/api/documents` | Upload PDF/MD/TXT (multi-file, async ingest) |
| GET | `/api/documents` · `/{id}` | List / status |
| GET | `/api/documents/{id}/file` | Original file (for viewer) |
| DELETE | `/api/documents/{id}` | Remove doc + chunks |
| POST | `/api/search` | `{query, top_k, mode: hybrid\|vector\|keyword, document_ids}` |
| GET | `/api/chunks/{id}` | Exact cited passage + neighbours |
| POST | `/api/research` | Run the agent, return the cited report + metrics |
| POST | `/api/research/stream` | Same, as Server-Sent Events (live progress) |
| GET | `/api/research` · `/{id}` | Past runs / a stored report |
| GET | `/health` | Status + counts |

Known limits (addressed later): no OCR for scanned PDFs, no auth.
