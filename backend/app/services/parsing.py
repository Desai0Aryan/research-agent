"""File -> list of 'pages'. PDFs use real pages; text/markdown get virtual pages."""
import re
from pathlib import Path

from pypdf import PdfReader

VIRTUAL_PAGE_CHARS = 3000


def _virtual_pages(text: str) -> list[str]:
    pages, cur = [], ""
    for para in re.split(r"\n{2,}", text):
        if cur and len(cur) + len(para) > VIRTUAL_PAGE_CHARS:
            pages.append(cur)
            cur = ""
        cur += para + "\n\n"
    if cur.strip():
        pages.append(cur)
    return pages


def parse_file(path: Path, filename: str) -> tuple[str, list[str], str]:
    """Returns (title, pages, mime)."""
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    stem = Path(filename).stem.replace("_", " ").replace("-", " ").strip() or filename

    if ext == "pdf":
        reader = PdfReader(str(path))
        pages = [(p.extract_text() or "") for p in reader.pages]
        meta_title = (reader.metadata.title if reader.metadata else None) or ""
        return (meta_title.strip() or stem), pages, "application/pdf"

    if ext in {"md", "markdown", "txt", "rst"}:
        text = path.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"^#\s+(.+)$", text, re.M)
        return (m.group(1).strip() if m else stem), _virtual_pages(text), "text/markdown" if ext != "txt" else "text/plain"

    raise ValueError(f"Unsupported file type: .{ext} (supported: pdf, md, txt, rst)")
