"""Live integration tests against a REAL Postgres+pgvector (separate DB!).

  createdb research_test
  TEST_DATABASE_URL=postgresql+psycopg://postgres@localhost:5432/research_test pytest tests_integration -q
"""
import os
from pathlib import Path

import pytest

URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="set TEST_DATABASE_URL to run integration tests")

if URL:
    os.environ.update(DATABASE_URL=URL, DATA_DIR="/tmp/ra_test_data", CHUNK_TARGET_WORDS="45", CHUNK_OVERLAP_WORDS="10", LLM_PROVIDER="none")

SAMPLES = Path(__file__).resolve().parents[2] / "samples"


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from sqlalchemy import text

    from app.db import engine
    from app.main import app

    with engine.begin() as c:  # clean slate, including alembic_version
        c.execute(text("DROP SCHEMA public CASCADE"))
        c.execute(text("CREATE SCHEMA public"))
    with TestClient(app) as c:
        files = [("files", (p.name, p.read_bytes())) for p in sorted(SAMPLES.glob("*.md"))]
        assert c.post("/api/documents", files=files).status_code == 202
        yield c


def test_ingestion_produced_page_aware_chunks(client):
    docs = client.get("/api/documents").json()
    assert len(docs) == 6 and all(d["status"] == "ready" and d["num_chunks"] >= 4 for d in docs)
    # idempotent re-upload
    p = SAMPLES / "hybrid_search.md"
    client.post("/api/documents", files=[("files", (p.name, p.read_bytes()))])
    assert len(client.get("/api/documents").json()) == 6


def test_all_search_modes_work_and_hybrid_reports_both_ranks(client):
    for mode in ("hybrid", "vector", "keyword"):
        r = client.post("/api/search", json={"query": "reciprocal rank fusion", "mode": mode, "top_k": 3}).json()
        assert r["hits"], mode
    top = client.post("/api/search", json={"query": "reciprocal rank fusion score calibration", "top_k": 3}).json()["hits"][0]
    assert top["filename"] == "hybrid_search.md" and top["keyword_rank"] is not None and top["vector_rank"] is not None
    chunk = client.get(f"/api/chunks/{top['chunk_id']}").json()
    assert chunk["text"] == top["text"]


def test_research_report_is_verified_and_cited(client):
    r = client.post("/api/research", json={"question": "How does reciprocal rank fusion work and how is hallucination measured?"}).json()
    m = r["metrics"]
    assert m["claims_total"] >= 2 and m["unsupported"] == 0 and m["citation_coverage"] == 1.0
    assert all(c["url"].startswith("/api/documents/") and "#page=" in c["url"] for c in r["citations"])
    assert client.get(f"/api/research/{r['run_id']}").json()["markdown"] == r["markdown"]
    off = client.post("/api/research", json={"question": "What is the boiling point of tungsten hexafluoride?"}).json()
    assert not off["sections"]  # abstains instead of hallucinating


def test_feedback_and_failure_mining(client):
    off = client.post("/api/research", json={"question": "What is the boiling point of tungsten hexafluoride?"}).json()
    assert client.post(f"/api/research/{off['run_id']}/feedback", json={"rating": -1, "note": "no answer"}).status_code == 204
    f = client.get("/api/feedback/failures").json()
    assert any(x["question"].startswith("What is the boiling") for x in f["failures"])
    assert "tungsten" in dict(f["out_of_vocabulary_terms"])  # corpus has never heard of it


def test_eval_pipeline_and_expansion_lifecycle(client):
    golden = (SAMPLES / "golden_sample.jsonl").read_text()
    s = client.post("/api/eval/sets", json={"name": "golden", "jsonl": golden}).json()
    run = client.post("/api/eval/runs", json={"set_id": s["id"], "e2e": True}).json()
    assert run["summary"]["retrieval.hybrid.recall@5"] >= 0.7
    assert run["summary"]["answers.abstention_accuracy"] == 1.0 and run["summary"]["answers.unsupported_claim_rate"] == 0.0
    gen = client.post("/api/eval/sets/generate", json={"name": "syn", "n_cases": 8}).json()
    assert gen["n_answerable"] >= 6
    syn = client.post("/api/eval/runs", json={"set_id": gen["id"], "modes": ["hybrid"]}).json()
    assert syn["summary"]["retrieval.hybrid.recall@10"] >= 0.8  # leaky by construction: sanity floor only

    test_run = client.post("/api/eval/runs", json={"set_id": s["id"], "split": "test"}).json()
    assert client.post("/api/feedback/expansions/propose", json={"eval_run_id": test_run["id"]}).status_code == 422  # no peeking
    train = client.post("/api/eval/runs", json={"set_id": s["id"], "split": "train"}).json()
    props = client.post("/api/feedback/expansions/propose", json={"eval_run_id": train["id"]}).json()
    assert all(p["status"] == "proposed" for p in props)  # human approval required
    for p in props[:1]:
        client.patch(f"/api/feedback/expansions/{p['id']}", json={"status": "enabled"})
        assert client.delete(f"/api/feedback/expansions/{p['id']}").status_code == 204
    cmp = client.get("/api/eval/compare", params={"a": run["id"], "b": syn["id"]}).json()
    assert cmp["deltas"]
