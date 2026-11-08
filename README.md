# Enterprise AI Research Agent with Verifiable Citations

Research complex questions across hundreds of PDFs and docs, compare sources, and get a report where **every claim is cited to an exact passage and page**.

> **Status: Part 3 of 5 — evaluation pipeline + feedback loop.**

## Roadmap
- [x] **Part 1** – Docker/Postgres+pgvector, ingestion, page-aware chunking, hybrid search (vector + FTS + RRF), API
- [x] **Part 2** – Agent: query decomposition, multi-step retrieval, reranking, cited report, citation verifier
- [x] **Part 3** – Evaluation pipeline + failed-query feedback loop
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

## Evaluation & feedback loop (Part 3)
```
golden set (manual JSONL or synthetic) ─▶ retrieval eval  : recall@k · MRR · nDCG@k, per mode (hybrid / vector / keyword)
                                       ─▶ answer eval     : key-fact correctness · faithfulness · unsupported-claim rate
                                                            · gold-citation rate · abstention accuracy on unanswerable Qs
                                       ─▶ failure diagnosis: ranking | lexical_gap | semantic_gap | fusion_gap | chunk_boundary
                                                            | corpus_gap | wrongly_abstained | unsupported_claims | answered_unanswerable
                                       ─▶ clusters + concrete config fixes ─▶ CI quality gate (eval/thresholds.json)
production runs ─▶ 👎 ratings, empty answers, low faithfulness ─▶ clustered; out-of-vocabulary terms surfaced
eval failures   ─▶ proposed query expansions ─▶ HUMAN approves ─▶ applied to keyword search ─▶ re-measure
```
- **Gold labels are (file, page, passage)**, not chunk IDs, so golden sets survive re-chunking and model swaps.
- **Leak-free learning:** `split=train|test` is a deterministic halving by case id. Expansions are learned only from train failures and the API refuses to learn from a `test` run, so the before/after number is honest.
- **Human in the loop:** learned expansions start as `proposed`; only `enabled` ones touch search.
- **Synthetic cases are leaky by construction** (questions built from the passage's own words). Use them as a smoke test and rely on hand-written paraphrase cases (`samples/golden_sample.jsonl`) for real signal.

```bash
make eval                                   # run the golden set + gate; exit 1 on regression
python scripts/eval.py --generate 30 --e2e  # synthetic set from your corpus
make test-integration TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/research_test
```
Reading the first real numbers (tiny 42-chunk demo corpus, offline hash embedder): keyword retrieval (recall@5 0.89) beats dense (0.44), and hybrid RRF sits in between: a weak ranker drags a strong one down. That is the evidence-based case for a real embedding model (`EMBEDDING_PROVIDER=local|openai`) — exactly what the harness is for.

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
| POST | `/api/eval/sets` · `/sets/generate` | Import JSONL / synthesise a golden set |
| POST | `/api/eval/runs` | Run retrieval (+ `e2e` answer) evaluation, optional `split` |
| GET | `/api/eval/runs/{id}` · `/failures` · `/compare?a=&b=` | Report · clustered failures + fixes · metric deltas |
| POST | `/api/research/{id}/feedback` | 👍/👎 + note on a run |
| GET | `/api/feedback/failures` | Mined production failures, clusters, out-of-vocabulary terms |
| POST/GET/PATCH/DELETE | `/api/feedback/expansions…` | Propose → review → enable query expansions |
| GET | `/health` | Status + counts |

Known limits (addressed later): no OCR for scanned PDFs, no auth.
