#!/usr/bin/env python3
"""Run the evaluation pipeline and (optionally) gate CI on quality thresholds.

  python scripts/eval.py --golden samples/golden_sample.jsonl --e2e --gate eval/thresholds.json
  python scripts/eval.py --generate 20            # synthetic golden set from the ingested corpus

Exit code 1 if any threshold is violated.
"""
import argparse
import json
import sys

import httpx

p = argparse.ArgumentParser()
p.add_argument("--api", default="http://localhost:8000")
p.add_argument("--golden", help="JSONL golden set to import")
p.add_argument("--generate", type=int, help="generate N synthetic cases from the corpus")
p.add_argument("--e2e", action="store_true", help="also run the full agent (answer metrics)")
p.add_argument("--gate", help="thresholds JSON; fail (exit 1) on regression")
p.add_argument("--no-expansions", action="store_true")
a = p.parse_args()

with httpx.Client(base_url=a.api, timeout=1800) as c:
    if a.golden:
        s = c.post("/api/eval/sets", json={"name": a.golden, "jsonl": open(a.golden).read()}).json()
    elif a.generate:
        s = c.post("/api/eval/sets/generate", json={"name": f"synthetic-{a.generate}", "n_cases": a.generate}).json()
    else:
        sets = c.get("/api/eval/sets").json()
        sys.exit("no eval set: pass --golden or --generate") if not sets else None
        s = sets[0]
    run = c.post("/api/eval/runs", json={"set_id": s["id"], "e2e": a.e2e, "use_expansions": not a.no_expansions}).json()

print(f"Eval run {run['id']}  ({run['config']['n_cases']} cases, engine={run['config']['engine']}, embedding={run['config']['embedding']})\n")
print(f"{'mode':10}{'recall@1':>10}{'recall@5':>10}{'mrr':>8}{'ndcg@10':>9}")
for m, d in run["report"]["retrieval"]["modes"].items():
    print(f"{m:10}{d['recall@1']:>10.3f}{d['recall@5']:>10.3f}{d['mrr']:>8.3f}{d['ndcg@10']:>9.3f}")
if run["report"]["answers"]:
    an = run["report"]["answers"]
    print(f"\nanswers: correctness={an['answer_correctness']}  faithfulness={an['faithfulness']}  "
          f"unsupported_rate={an['unsupported_claim_rate']}  gold_cited={an['gold_citation_rate']}  abstention={an['abstention_accuracy']}")
fs = run["report"]["failure_summary"]
print(f"\nfailures: {fs['total']}")
for r in fs["recommendations"]:
    print(f"  [{r['count']}x] {r['label']}: {r['action']}")

if a.gate:
    th = {k: v for k, v in json.load(open(a.gate)).items() if not k.startswith("_")}
    bad = []
    for key, bound in th.items():
        is_max = key.endswith("_max")
        name = key[:-4] if is_max else key
        val = run["summary"].get(name)
        if val is None:
            continue
        if (val > bound) if is_max else (val < bound):
            bad.append(f"{name} = {val} ({'>' if is_max else '<'} {bound})")
    print("\nQUALITY GATE:", "FAILED\n  " + "\n  ".join(bad) if bad else "passed ✔")
    sys.exit(1 if bad else 0)
