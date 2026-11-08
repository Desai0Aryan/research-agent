"""Golden-set creation: synthetic (LLM or heuristic) generation + JSONL import."""
import json
import math
import random
import re

from ..agent.llm import LLM, extract_json
from ..services.chunking import split_sentences
from ..services.text import keyword_terms, stem

OFF_TOPIC = [
    "What is the boiling point of tungsten hexafluoride?",
    "Who won the 1998 football world cup final?",
    "What is the recommended dosage of ibuprofen for adults?",
    "How do I change the oil in a 2012 Honda Civic?",
]

GEN_SYSTEM = """You write evaluation questions for a document-search system. Given ONE passage, write a natural
question that this passage answers and that a person would ask WITHOUT quoting the passage's wording (use
paraphrase / different vocabulary). Also list 1-3 short key facts a correct answer must contain.
Return ONLY JSON: {"question":"...","key_facts":["..."]}"""


def load_jsonl(text: str) -> list[dict]:
    cases = []
    for i, line in enumerate(l for l in text.splitlines() if l.strip()):
        c = json.loads(line)
        c.setdefault("id", f"case{i+1}")
        c.setdefault("answerable", bool(c.get("gold")))
        c.setdefault("gold", [])
        c.setdefault("key_facts", [])
        c.setdefault("source", "manual")
        cases.append(c)
    return cases


def _idf(chunks: list[dict]) -> dict[str, float]:
    df: dict[str, int] = {}
    for c in chunks:
        for t in {stem(t) for t in keyword_terms(c["text"], 400)}:
            df[t] = df.get(t, 0) + 1
    n = len(chunks)
    return {t: math.log((n + 1) / (d + 0.5)) + 1 for t, d in df.items()}


def _heuristic_case(chunk: dict, idf: dict[str, float]) -> dict | None:
    sents = [s for s in split_sentences(chunk["text"]) if len(s.split()) >= 8 and not s.startswith("#")]
    if not sents:
        return None
    score = lambda s: sum(idf.get(stem(t), 0) for t in set(keyword_terms(s)))  # noqa: E731
    best = max(sents, key=score)
    terms = sorted({t for t in keyword_terms(best) if len(t) > 3}, key=lambda t: -idf.get(stem(t), 0))[:3]
    if len(terms) < 2:
        return None
    q = f"What does the documentation say about {', '.join(terms[:-1])} and {terms[-1]}?"
    return {"question": q, "key_facts": [best], "passage": best}


def generate_cases(chunks: list[dict], n: int, llm: LLM | None = None, include_unanswerable: bool = True, seed: int = 7) -> list[dict]:
    """chunks: [{filename, page, text}]. Returns eval cases tagged source=synthetic."""
    rng = random.Random(seed)
    pool = [c for c in chunks if len(c["text"].split()) >= 30]
    rng.shuffle(pool)
    idf = _idf(chunks) if chunks else {}
    cases: list[dict] = []
    for c in pool:
        if len(cases) >= n:
            break
        made = None
        if llm:
            try:
                d = extract_json(llm.complete(GEN_SYSTEM, f"Passage:\n{c['text'][:1500]}", json_mode=True, max_tokens=300))
                made = {"question": d["question"], "key_facts": d.get("key_facts", []), "passage": c["text"][:400]}
            except Exception:  # noqa: BLE001
                made = None
        made = made or _heuristic_case(c, idf)
        if not made:
            continue
        cases.append({
            "id": f"syn{len(cases)+1}", "question": made["question"], "answerable": True, "source": "synthetic",
            "gold": [{"filename": c["filename"], "page": c["page"], "passage": made["passage"]}],
            "key_facts": made["key_facts"],
        })
    if include_unanswerable:
        for j, q in enumerate(OFF_TOPIC[: max(1, n // 5)]):
            cases.append({"id": f"unans{j+1}", "question": q, "answerable": False, "source": "synthetic", "gold": [], "key_facts": []})
    return cases


def dump_jsonl(cases: list[dict]) -> str:
    return "\n".join(json.dumps(c, ensure_ascii=False) for c in cases)
