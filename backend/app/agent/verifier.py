"""Claim-level citation verification: is each claim actually entailed by the passages it cites?"""
import re
from dataclasses import dataclass

from ..services.chunking import split_sentences
from ..services.text import coverage, numbers
from .llm import LLM, extract_json

SUPPORTED, PARTIAL = 0.6, 0.35


@dataclass
class Verdict:
    verdict: str  # supported | partial | unsupported
    score: float
    quote: str | None
    quote_verified: bool
    reason: str


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def lexical_verify(claim: str, passages: list[str]) -> Verdict:
    if not passages:
        return Verdict("unsupported", 0.0, None, False, "Claim cites no valid evidence.")
    best_s, best_cov = None, 0.0
    for p in passages:
        pcov = 0.85 * coverage(claim, p)
        for s in split_sentences(p):
            c = coverage(claim, s)
            if c > best_cov:
                best_s, best_cov = s, c
        best_cov = max(best_cov, pcov) if best_s else pcov
    cnums = numbers(claim)
    if cnums and not cnums <= set().union(*(numbers(p) for p in passages)):
        best_cov *= 0.6  # a number in the claim appears nowhere in the evidence
    verdict = "supported" if best_cov >= SUPPORTED else "partial" if best_cov >= PARTIAL else "unsupported"
    reason = {"supported": "Key terms and figures found in cited passage.", "partial": "Only part of the claim is found in the cited passage.", "unsupported": "Cited passage does not contain this claim."}[verdict]
    return Verdict(verdict, round(best_cov, 3), best_s, bool(best_s), reason)


LLM_SYSTEM = """You are a strict fact-checker. For each claim decide whether the cited passages ENTAIL it.
- supported: the passages explicitly state the claim (paraphrase OK).
- partial: only part of the claim is stated, or it needs an inference not in the text.
- unsupported: not stated, contradicted, or numbers/names differ.
Give "quote": a VERBATIM excerpt (max 40 words) copied from a passage that best supports the claim (empty if none).
Return ONLY JSON: {"results":[{"i":0,"verdict":"supported","quote":"...","reason":"<=20 words"}]}"""


def verify_claims(items: list[tuple[str, list[str]]], llm: LLM | None, warn=lambda m: None) -> list[Verdict]:
    """items: (claim_text, [cited passage texts]). Always cross-checked by the lexical verifier."""
    lex = [lexical_verify(c, ps) for c, ps in items]
    if not llm:
        return lex
    out = list(lex)
    for start in range(0, len(items), 8):
        batch = items[start : start + 8]
        block = "\n\n".join(
            f"[{i}] CLAIM: {c}\nPASSAGES:\n" + "\n---\n".join(ps) for i, (c, ps) in enumerate(batch) if ps
        )
        if not block:
            continue
        try:
            data = extract_json(llm.complete(LLM_SYSTEM, block, json_mode=True, max_tokens=2500))
            for r in data.get("results", []):
                gi = start + int(r["i"])
                claim, ps = items[gi]
                verdict = r.get("verdict", "unsupported")
                if verdict not in ("supported", "partial", "unsupported"):
                    verdict = "unsupported"
                quote = (r.get("quote") or "").strip() or None
                qv = bool(quote) and any(_norm(quote) in _norm(p) for p in ps)
                score = lex[gi].score
                # guardrails against a rubber-stamping judge
                why = str(r.get("reason", ""))[:300]
                if verdict == "supported" and (not qv or score < 0.25):
                    if lex[gi].verdict == "unsupported":
                        # fabricated/unfindable quote AND no lexical overlap: treat as hallucination
                        verdict, why = "unsupported", "Judge's quote not found in cited passage and claim terms are absent."
                    else:
                        verdict, why = "partial", "Judge said supported, but quote/term overlap could not be verified."
                out[gi] = Verdict(verdict, score, quote if qv else lex[gi].quote, qv or lex[gi].quote_verified, why)
        except Exception as e:  # noqa: BLE001
            warn(f"LLM verification failed for a batch, using lexical verifier: {e}")
    return out
