"""Evaluation runner. DB/LLM-free: the retriever and agent are injected callables."""
from collections import defaultdict
from collections.abc import Callable
from types import SimpleNamespace

from ..services.text import coverage
from .diagnose import diagnose_retrieval, summarize_failures
from .matching import gold_from_dict, matches, relevance
from .metrics import avg, mrr, ndcg_at_k, recall_at_k

Retriever = Callable[[str, str, int], list]  # (mode, query, k) -> hits
AgentFn = Callable[[str], dict]  # question -> ResearchResult dict

FACT_THRESHOLD = 0.6


def eval_retrieval(cases: list[dict], retriever: Retriever, modes=("hybrid", "vector", "keyword"), ks=(1, 3, 5, 10)) -> dict:
    kmax = max(ks)
    answerable = [c for c in cases if c.get("answerable", True) and c.get("gold")]
    agg: dict[str, dict[str, list[float]]] = {m: defaultdict(list) for m in modes}
    per_case = []
    primary = "hybrid" if "hybrid" in modes else modes[0]
    for c in answerable:
        golds = [gold_from_dict(g) for g in c["gold"]]
        entry = {"id": c["id"], "question": c["question"], "ranks": {}, "top10": []}
        for m in modes:
            hits = retriever(m, c["question"], kmax)
            rels, ranks = relevance(hits, golds)
            entry["ranks"][m] = ranks
            for k in ks:
                agg[m][f"recall@{k}"].append(recall_at_k(ranks, k))
                agg[m][f"ndcg@{k}"].append(ndcg_at_k(rels, len(golds), k))
            agg[m]["mrr"].append(mrr(ranks))
            if m == primary:
                entry["top10"] = [{"filename": h.filename, "page": h.page, "text": h.text[:600]} for h in hits[:10]]
        per_case.append(entry)
    return {
        "n_cases": len(answerable),
        "modes": {m: {k: avg(v) for k, v in d.items()} for m, d in agg.items()},
        "per_case": per_case,
        "primary": primary,
    }


def _answer_text(result: dict) -> str:
    return " ".join(c["text"] for s in result["sections"] for c in s["claims"])


def eval_answers(cases: list[dict], run_agent: AgentFn) -> dict:
    per_case, correct, faith = [], [], []
    unsupported = claims_total = 0
    gold_cited, n_gold_cases = 0, 0
    abstain_ok, n_unans = 0, 0
    for c in cases:
        res = run_agent(c["question"])
        text = _answer_text(res)
        n_claims = res["metrics"]["claims_total"]
        entry = {"id": c["id"], "question": c["question"], "answerable": c.get("answerable", True),
                 "claims": n_claims, "unsupported": res["metrics"]["unsupported"],
                 "faithfulness": res["metrics"]["faithfulness"], "abstained": not res["sections"]}
        unsupported += res["metrics"]["unsupported"]
        claims_total += n_claims
        if c.get("answerable", True):
            facts = c.get("key_facts") or []
            hit = [coverage(f, text) >= FACT_THRESHOLD for f in facts]
            entry["key_fact_recall"] = round(sum(hit) / len(hit), 3) if hit else None
            if hit:
                correct.append(sum(hit) / len(hit))
            if n_claims:
                faith.append(res["metrics"]["faithfulness"])
            cited = {e for s in res["sections"] for cl in s["claims"] for e in cl["evidence_ids"]}
            golds = [gold_from_dict(g) for g in c.get("gold", [])]
            if golds:
                n_gold_cases += 1
                ev = [SimpleNamespace(filename=e.get("filename", ""), page=e["page"], text=e["text"]) for e in res["evidence"] if e["id"] in cited]
                ok = any(matches(h, g) for h in ev for g in golds)
                entry["cites_gold"] = ok
                gold_cited += ok
        else:
            n_unans += 1
            abstain_ok += entry["abstained"]
        per_case.append(entry)
    return {
        "n_cases": len(cases),
        "answer_correctness": avg(correct),
        "faithfulness": avg(faith),
        "unsupported_claim_rate": round(unsupported / claims_total, 4) if claims_total else 0.0,
        "gold_citation_rate": round(gold_cited / n_gold_cases, 4) if n_gold_cases else 0.0,
        "abstention_accuracy": round(abstain_ok / n_unans, 4) if n_unans else None,
        "per_case": per_case,
    }


def label_answer_failures(answers: dict) -> list[dict]:
    out = []
    for e in answers["per_case"]:
        if e["answerable"]:
            if e["abstained"]:
                label = "wrongly_abstained"
            elif e["unsupported"] > 0:
                label = "unsupported_claims"
            elif e.get("key_fact_recall") is not None and e["key_fact_recall"] < 0.5:
                label = "incorrect_answer"
            else:
                continue
        elif not e["abstained"]:
            label = "answered_unanswerable"
        else:
            continue
        out.append({"case_id": e["id"], "question": e["question"], "kind": "answer", "label": label, "details": {k: e[k] for k in ("claims", "unsupported", "faithfulness") if k in e}})
    return out


def build_report(cases, retrieval: dict, answers: dict | None, config: dict) -> dict:
    failures = []
    gold_by_id = {c["id"]: c for c in cases}
    for e in retrieval["per_case"]:
        label = diagnose_retrieval(e, gold_by_id[e["id"]], retrieval["primary"])
        if label:
            failures.append({"case_id": e["id"], "question": e["question"], "kind": "retrieval", "label": label,
                             "details": {m: min((r for r in rs if r), default=None) for m, rs in e["ranks"].items()}})
    if answers:
        failures += label_answer_failures(answers)
    summary = {f"retrieval.{m}.{k}": v for m, d in retrieval["modes"].items() for k, v in d.items()}
    if answers:
        for k in ("answer_correctness", "faithfulness", "unsupported_claim_rate", "gold_citation_rate", "abstention_accuracy"):
            if answers.get(k) is not None:
                summary[f"answers.{k}"] = answers[k]
    return {"config": config, "retrieval": retrieval, "answers": answers, "failures": failures,
            "failure_summary": summarize_failures(failures), "summary": summary}
