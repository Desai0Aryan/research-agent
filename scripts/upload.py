#!/usr/bin/env python3
"""Upload files, wait for ingestion, optionally run a query.

  python scripts/upload.py samples/*            # ingest
  python scripts/upload.py --query "what is RRF?"
"""
import argparse
import sys
import time

import httpx

p = argparse.ArgumentParser()
p.add_argument("files", nargs="*")
p.add_argument("--api", default="http://localhost:8000")
p.add_argument("--query")
p.add_argument("--mode", default="hybrid", choices=["hybrid", "vector", "keyword"])
a = p.parse_args()
SUPPORTED = (".pdf", ".md", ".markdown", ".txt", ".rst")
skipped = [f for f in a.files if not f.lower().endswith(SUPPORTED)]
a.files = [f for f in a.files if f.lower().endswith(SUPPORTED)]
for f in skipped:
    print(f"skipping unsupported file: {f}")

import os

HEADERS = {"X-API-Key": os.environ["API_KEY"]} if os.environ.get("API_KEY") else {}
with httpx.Client(base_url=a.api, timeout=120, headers=HEADERS) as c:
    if a.files:
        handles = [("files", (f.split("/")[-1], open(f, "rb"))) for f in a.files]
        docs = c.post("/api/documents", files=handles).json()
        ids = {d["id"] for d in docs}
        while True:
            cur = [d for d in c.get("/api/documents").json() if d["id"] in ids]
            if all(d["status"] in ("ready", "failed") for d in cur):
                break
            time.sleep(1)
        for d in cur:
            print(f"{d['status']:8} {d['num_pages']:>4}p {d['num_chunks']:>5} chunks  {d['title']}  {d['error'] or ''}")
    if a.query:
        r = c.post("/api/search", json={"query": a.query, "mode": a.mode, "top_k": 5}).json()
        print(f"\n{len(r['hits'])} hits in {r['took_ms']} ms")
        for h in r["hits"]:
            print(f"- [{h['score']:.4f}] {h['document_title']} p.{h['page']}  (vec#{h['vector_rank']} kw#{h['keyword_rank']})")
            print("   ", h["text"][:160].replace("\n", " "), "…")
    if not a.files and not a.query:
        sys.exit(p.print_help())
