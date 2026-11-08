import re

from ..services.chunking import split_sentences
from ..services.text import coverage
from .llm import LLM, extract_json

SYSTEM = """You are a meticulous research analyst. Write a report using ONLY the numbered evidence passages.
Rules:
1. Each claim is ONE atomic, self-contained factual statement (no pronouns that need context).
2. Each claim cites 1-3 evidence IDs that DIRECTLY support it. Never cite a passage that doesn't say it.
3. Never add facts that are not in the evidence, even if you know them to be true.
4. Compare sources: if several passages agree, cite them together; if they conflict, add a section
   titled "Where sources disagree" stating each side with its citations.
5. If the evidence cannot answer part of the question, put that in "gaps" instead of guessing.
6. Organise into 2-5 sections with short headings. Start with a "Key findings" section.
Return ONLY JSON:
{"title":"...","sections":[{"heading":"...","claims":[{"text":"...","evidence":["E1","E3"]}]}],"gaps":["..."]}"""


def _evidence_block(evidence: dict[str, dict]) -> str:
    return "\n\n".join(f"[{eid}] ({e['title']}, p.{e['page']})\n{e['text']}" for eid, e in evidence.items())


def llm_write(question, sub_questions, evidence, llm: LLM) -> dict:
    user = (
        f"Question: {question}\nSub-questions covered: {sub_questions}\n\nEvidence:\n{_evidence_block(evidence)}"
    )
    d = extract_json(llm.complete(SYSTEM, user, json_mode=True, max_tokens=4000))
    sections = []
    for s in d.get("sections", []):
        claims = [
            {"text": c["text"].strip(), "evidence": [e for e in c.get("evidence", []) if isinstance(e, str)]}
            for c in s.get("claims", [])
            if isinstance(c, dict) and c.get("text")
        ]
        if claims:
            sections.append({"heading": str(s.get("heading", "Findings")), "claims": claims})
    return {"title": str(d.get("title") or question)[:200], "sections": sections, "gaps": [str(g) for g in d.get("gaps", [])]}


def extractive_write(question, sub_questions, evidence, per_sq: dict[int, list[str]]) -> dict:
    """Offline writer: picks the best sentences per sub-question. Every claim is quotable by construction."""
    sections, used = [], set()
    gaps = []
    for i, sq in enumerate(sub_questions):
        cands = []
        for eid in per_sq.get(i, []):
            for s in split_sentences(evidence[eid]["text"]):
                if len(s.split()) >= 6 and not s.startswith("#"):
                    cands.append((coverage(sq, s), eid, s))
        cands.sort(key=lambda x: -x[0])
        claims, seen_e = [], set()
        for cov, eid, s in cands:
            if cov < 0.2 or (eid, s) in used or len(claims) >= 3:
                continue
            if eid in seen_e and len(claims) >= 2:
                continue
            claims.append({"text": re.sub(r"^#+\s*", "", s), "evidence": [eid]})
            used.add((eid, s))
            seen_e.add(eid)
        if claims:
            sections.append({"heading": sq.rstrip("?"), "claims": claims})
        else:
            gaps.append(f"No sufficiently relevant evidence found for: {sq}")
    return {"title": question.rstrip("?"), "sections": sections, "gaps": gaps}
