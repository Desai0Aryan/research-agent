"""Production feedback loop: mine bad runs, cluster them, learn expansions."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from ..eval.diagnose import RECOMMENDATIONS, cluster_questions, propose_expansions, summarize_failures
from ..services.evaluation import in_split
from ..models import EvalRun, EvalSet, QueryExpansion, ResearchRun
from ..services.text import keyword_terms
from .search import invalidate_expansions

LOW_FAITHFULNESS = 0.7


def unknown_terms(db: Session, question: str) -> list[str]:
    """Query words that match nothing in the corpus (stemmed full-text match): vocabulary gaps."""
    out = []
    for t in keyword_terms(question):
        hit = db.scalar(text("SELECT 1 FROM chunks WHERE tsv @@ to_tsquery('english', :t) LIMIT 1"), {"t": t})
        if not hit:
            out.append(t)
    return out


def production_failures(db: Session, days: int = 30) -> dict:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    runs = db.scalars(select(ResearchRun).where(ResearchRun.created_at >= since, ResearchRun.status != "running")).all()
    failures = []
    for r in runs:
        m, label = r.metrics or {}, None
        if r.rating == -1:
            label = "rating_negative"
        elif r.status == "failed" or (r.result is not None and not r.result.get("sections")):
            label = "empty_answer"
        elif m.get("claims_total") and m.get("faithfulness", 1) < LOW_FAITHFULNESS:
            label = "low_faithfulness"
        if label:
            failures.append({"case_id": str(r.id), "question": r.question, "kind": "production", "label": label,
                             "details": {"rating": r.rating, "note": r.feedback_note, "faithfulness": m.get("faithfulness"),
                                         "unknown_terms": unknown_terms(db, r.question)}})
    oov = {}
    for f in failures:
        for t in f["details"]["unknown_terms"]:
            oov[t] = oov.get(t, 0) + 1
    return {"window_days": days, "runs_considered": len(runs), "failures": failures,
            "clusters": cluster_questions(failures), "summary": summarize_failures(failures),
            "out_of_vocabulary_terms": sorted(oov.items(), key=lambda kv: -kv[1])[:20]}


def propose_from_eval(db: Session, run: EvalRun) -> list[QueryExpansion]:
    if run.config.get("split") == "test":
        raise ValueError("Learn from a run on split 'train' or 'all'; 'test' cases are held out for measuring the effect.")
    es = db.get(EvalSet, run.set_id)
    cases = {c["id"]: c for c in es.cases if in_split(c["id"], "train")}
    top = {e["id"]: e["top10"] for e in run.report["retrieval"]["per_case"]}
    out = []
    train_failures = [f for f in run.report["failures"] if f["case_id"] in cases]
    for p in propose_expansions(train_failures, cases, top):
        row = db.scalar(select(QueryExpansion).where(QueryExpansion.term == p["term"]))
        if row:
            row.expansions = list(dict.fromkeys(list(row.expansions) + p["expansions"]))
            row.support += p["support"]
        else:
            row = QueryExpansion(term=p["term"], expansions=p["expansions"], support=p["support"], examples=p["examples"][:5])
            db.add(row)
        out.append(row)
    db.commit()
    invalidate_expansions()
    return out


def feedback_stats(db: Session) -> dict:
    rows = db.execute(select(ResearchRun.rating, func.count()).group_by(ResearchRun.rating)).all()
    return {("none" if r is None else str(r)): n for r, n in rows}
