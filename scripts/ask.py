#!/usr/bin/env python3
"""Ask the research agent a question and watch it work (SSE stream).

  python scripts/ask.py "How does RRF work and how is hallucination measured in RAG?"
"""
import argparse
import json

import httpx

p = argparse.ArgumentParser()
p.add_argument("question")
p.add_argument("--api", default="http://localhost:8000")
p.add_argument("--lenient", action="store_true", help="keep unsupported claims (flagged)")
a = p.parse_args()

body = {"question": a.question, "strict": not a.lenient}
with httpx.stream("POST", f"{a.api}/api/research/stream", json=body, timeout=600) as r:
    for line in r.iter_lines():
        if not line.startswith("data: "):
            continue
        ev = json.loads(line[6:])
        t = ev["type"]
        if t == "status":
            print(f"• {ev['message']}")
        elif t == "plan":
            print(f"• Plan ({ev['engine']}):", *[f"\n    {i+1}. {q}" for i, q in enumerate(ev["sub_questions"])])
        elif t == "retrieve":
            print(f"    ↳ sub-q {ev['sub_question']+1} round {ev['round']}: {ev['hits']} hits for “{ev['query'][:70]}”")
        elif t == "rerank":
            print(f"    ↳ reranked, kept {ev['kept']} (best {ev['best_score']})")
        elif t == "gap":
            print(f"    ↳ {ev['message']}")
        elif t == "evidence":
            print(f"• Evidence: {ev['count']} passages from {ev['documents']} documents")
        elif t == "error":
            raise SystemExit(f"ERROR: {ev['message']}")
        elif t == "done":
            res = ev["result"]
            print("\n" + res["markdown"])
            m = res["metrics"]
            print(f"\n— faithfulness {m['faithfulness']:.0%} · citation coverage {m['citation_coverage']:.0%} · "
                  f"unsupported {m['unsupported']}/{m['claims_total']} (removed {m['removed']}) · {m['latency_ms']} ms")
            for w in res["warnings"]:
                print("  ! warning:", w)
