"""OCR on a genuinely image-only PDF. Skipped automatically when tesseract isn't installed."""
import os
from pathlib import Path

import pytest

from app.services.parsing import ocr_available, parse_file

pytestmark = pytest.mark.skipif(not ocr_available(), reason="tesseract/pytesseract/pypdfium2 not installed")

FONTS = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans.ttf", "/Library/Fonts/Arial.ttf", "C:/Windows/Fonts/arial.ttf"]


def _scanned_pdf(path: Path, lines: list[str]) -> None:
    from PIL import Image, ImageDraw, ImageFont

    font_path = next((f for f in FONTS if os.path.exists(f)), None)
    if not font_path:
        pytest.skip("no TrueType font available to render test page")
    img = Image.new("RGB", (1240, 800), "white")
    d, f = ImageDraw.Draw(img), ImageFont.truetype(font_path, 44)
    for i, line in enumerate(lines):
        d.text((60, 60 + i * 80), line, fill="black", font=f)
    img.save(path, "PDF", resolution=150)  # image only: there is NO text layer


def test_scanned_pdf_is_ocrd_and_text_pdfs_are_not(tmp_path, monkeypatch):
    from app.config import get_settings

    pdf = tmp_path / "scan.pdf"
    _scanned_pdf(pdf, ["Reciprocal rank fusion merges", "ranked lists from several retrievers"])

    monkeypatch.setenv("OCR_ENABLED", "false")
    get_settings.cache_clear()
    _, pages, _, n = parse_file(pdf, "scan.pdf")
    assert n == 0 and "".join(pages).strip() == ""  # without OCR a scan yields nothing

    monkeypatch.setenv("OCR_ENABLED", "true")
    get_settings.cache_clear()
    _, pages, mime, n = parse_file(pdf, "scan.pdf")
    text = pages[0].lower()
    assert n == 1 and mime == "application/pdf"
    assert "reciprocal" in text and "fusion" in text and "retrievers" in text
    get_settings.cache_clear()
