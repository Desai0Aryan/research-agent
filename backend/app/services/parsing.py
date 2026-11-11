"""File -> list of 'pages'. PDFs use real pages; text/markdown get virtual pages."""
import re
from pathlib import Path

from pypdf import PdfReader

from ..config import get_settings

VIRTUAL_PAGE_CHARS = 3000


def ocr_available() -> bool:
    try:
        import pypdfium2  # noqa: F401
        import pytesseract

        pytesseract.get_tesseract_version()
        return True
    except Exception:  # noqa: BLE001
        return False


def ocr_pdf_page(path: Path, index: int, lang: str = "eng", scale: float = 2.5) -> str:
    """Render one PDF page and OCR it. 2.5x scale (~180 DPI) is a good accuracy/speed trade-off."""
    import pypdfium2 as pdfium
    import pytesseract

    pdf = pdfium.PdfDocument(str(path))
    try:
        image = pdf[index].render(scale=scale).to_pil().convert("L")
        return pytesseract.image_to_string(image, lang=lang)
    finally:
        pdf.close()


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


def parse_file(path: Path, filename: str) -> tuple[str, list[str], str, int]:
    """Returns (title, pages, mime, ocr_pages). Scanned PDF pages are OCR'd when OCR_ENABLED=true."""
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    stem = Path(filename).stem.replace("_", " ").replace("-", " ").strip() or filename

    if ext == "pdf":
        s = get_settings()
        reader = PdfReader(str(path))
        pages = [(p.extract_text() or "") for p in reader.pages]
        ocr_pages = 0
        if s.ocr_enabled:
            if not ocr_available():
                raise RuntimeError("OCR_ENABLED=true but tesseract/pytesseract/pypdfium2 are not installed (see requirements-ocr.txt).")
            for i, text in enumerate(pages):
                if len(text.strip()) < s.ocr_min_chars:
                    pages[i] = ocr_pdf_page(path, i, s.ocr_lang)
                    ocr_pages += 1
        meta_title = (reader.metadata.title if reader.metadata else None) or ""
        return (meta_title.strip() or stem), pages, "application/pdf", ocr_pages

    if ext in {"md", "markdown", "txt", "rst"}:
        text = path.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"^#\s+(.+)$", text, re.M)
        return (m.group(1).strip() if m else stem), _virtual_pages(text), "text/markdown" if ext != "txt" else "text/plain", 0

    raise ValueError(f"Unsupported file type: .{ext} (supported: pdf, md, txt, rst)")
