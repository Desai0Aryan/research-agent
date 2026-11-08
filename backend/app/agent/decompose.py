import re

from .llm import LLM, extract_json

SYSTEM = """You plan research. Break the user's question into the smallest set of self-contained
sub-questions that, answered together, fully answer it. Each sub-question must be understandable
without the others (resolve pronouns, repeat entity names). If the question is already simple,
return just one. Return ONLY JSON: {"sub_questions": ["..."]}"""


def heuristic_decompose(question: str, max_n: int) -> list[str]:
    q = question.strip()
    parts = re.split(r"\?|;|\bvs\.?\b|\bversus\b|,? and (?=(?:how|what|why|which|when|where)\b)", q, flags=re.I)
    parts = [p.strip(" ,.") for p in parts if p and len(p.split()) >= 3]
    out = [q.rstrip("?") + "?"]
    for p in parts:
        cand = p if p.endswith("?") else p + "?"
        if cand.lower() not in {o.lower() for o in out} and len(parts) > 1:
            out.append(cand)
    return out[:max_n]


def decompose(question: str, llm: LLM | None, max_n: int, warn=lambda m: None) -> list[str]:
    if llm:
        try:
            data = extract_json(
                llm.complete(SYSTEM, f"Question: {question}\nMax sub-questions: {max_n}", json_mode=True, max_tokens=600)
            )
            subs = [s.strip() for s in data.get("sub_questions", []) if isinstance(s, str) and s.strip()]
            if subs:
                return subs[:max_n]
        except Exception as e:  # noqa: BLE001
            warn(f"LLM decomposition failed, using heuristic: {e}")
    return heuristic_decompose(question, max_n)
