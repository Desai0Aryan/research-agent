"""Page-aware, sentence-packing chunker.

Chunks never cross page boundaries, so every chunk maps to exactly one PDF page.
That is what makes claim-level citations ("p. 7") verifiable later.
"""
import re
from dataclasses import dataclass

_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])|\n{2,}")


@dataclass(frozen=True)
class ChunkDraft:
    page: int
    text: str
    word_count: int


def normalize(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"-\n(?=[a-z])", "", text)  # de-hyphenate line wraps
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n(?!\n)", " ", text)  # single newlines -> spaces, keep paragraph breaks
    return text.strip()


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SPLIT.split(text) if s and s.strip()]


def _wc(s: str) -> int:
    return len(s.split())


def chunk_page(text: str, page: int, target: int = 180, overlap: int = 40) -> list[ChunkDraft]:
    text = normalize(text)
    if not text:
        return []

    units: list[str] = []
    for s in split_sentences(text):
        words = s.split()
        if len(words) > int(target * 1.5):  # pathological long "sentence" (tables, code)
            step = target
            units += [" ".join(words[i : i + step]) for i in range(0, len(words), step)]
        else:
            units.append(s)

    chunks: list[ChunkDraft] = []
    cur: list[str] = []
    cur_wc = 0
    for u in units:
        w = _wc(u)
        if cur and cur_wc + w > target:
            body = " ".join(cur)
            chunks.append(ChunkDraft(page, body, cur_wc))
            # carry tail sentences as overlap
            tail: list[str] = []
            tw = 0
            for s in reversed(cur):
                if tw >= overlap:
                    break
                tail.insert(0, s)
                tw += _wc(s)
            cur, cur_wc = tail, tw
        cur.append(u)
        cur_wc += w
    if cur:
        body = " ".join(cur)
        # avoid a tiny trailing chunk that is just overlap
        if not chunks or body != chunks[-1].text:
            if chunks and cur_wc < overlap + 5 and chunks[-1].page == page:
                pass  # fully covered by previous overlap
            else:
                chunks.append(ChunkDraft(page, body, cur_wc))
    return chunks


def chunk_document(pages: list[str], target: int = 180, overlap: int = 40) -> list[ChunkDraft]:
    out: list[ChunkDraft] = []
    for i, p in enumerate(pages, start=1):
        out.extend(chunk_page(p, i, target, overlap))
    return out
