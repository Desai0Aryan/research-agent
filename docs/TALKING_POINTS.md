# Presenting this project

## 30-second pitch
"I built a research agent that answers questions over hundreds of PDFs and attaches a citation to every claim. The part I'm proudest of is the reliability layer: each claim is machine-verified against the exact passage it cites — the quote has to appear verbatim, numbers have to match — and unsupported claims are removed and reported. Quality is measured with an evaluation harness (retrieval and answer metrics, failure diagnosis) that gates CI, and failed queries feed a human-in-the-loop improvement loop."

## 2-minute demo script
1. **Library:** drop in the sample docs; show live ingestion.
2. **Research:** ask the two-part RRF/hallucination question; narrate the timeline (plan → retrieval → rerank → verify).
3. Click a `[n]` → exact passage, highlighted verified quote, PDF opens at the page.
4. Open the **removed claims** panel (or ask an off-topic question to show *abstention*).
5. **Evaluation:** run the golden set; point at the chart (hybrid vs keyword vs vector) and the diagnosis ("semantic_gap → use a real embedder").
6. **Feedback:** show a 👎 run clustered, and an expansion waiting for approval.

## Questions you should expect
- **How do you prevent hallucinated citations?** Claims must cite evidence IDs that exist; the verifier requires a verbatim quote in the cited passage, checks numbers, and cross-checks an LLM judge lexically so a rubber-stamp becomes "unsupported". Tested with a scripted hallucinating judge.
- **How do you know retrieval is good?** Golden set of `(file, page, passage)`; recall@k/MRR/nDCG per mode; failures labelled by root cause. Gated in CI.
- **Why hybrid, why RRF?** Dense for paraphrase, keyword for exact terms; RRF avoids score calibration. We saw the downside too: a weak ranker drags the fusion down.
- **Why Postgres instead of a vector DB?** One transactional store, SQL filters, simple ops; fine at this scale; I'd revisit at much larger scale.
- **What would you do with more time?** Real embedding model + cross-encoder benchmark on a bigger golden set; table/figure extraction; per-user ACLs; a job queue; Redis-backed rate limiting; judge calibration against human labels.
- **What are the weaknesses?** Offline engine is extractive (low correctness); LLM clients weren't exercised against live APIs in development; tiny demo golden set; expansions show no measurable gain at demo scale.

## Numbers you can quote (demo scale, be explicit about that)
42 chunks · 11-case paraphrase golden set · faithfulness 100% / unsupported 0% / abstention 100% (offline engine) · 35 unit + 9 live integration tests · 5 CI jobs (unit, integration, web, quality gate, docker build).

## Engineering stories worth telling
- Mocks passed, but running on real Postgres exposed a writer bug (false "no evidence" gap) and an over-specific test — I installed pgvector locally to test against the real thing.
- A test caught that a fabricated quote from the judge was only downgraded to "partial"; I tightened it to "unsupported".
- Learned expansions could leak the eval set into training; I added a deterministic train/test split and made the API refuse to learn from the held-out half.
- Iframes can't send auth headers → HMAC-signed, document-bound, short-lived links.
