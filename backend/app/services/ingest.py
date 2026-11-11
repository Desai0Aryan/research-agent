import hashlib
import logging
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import SessionLocal
from ..models import Chunk, Document
from .chunking import chunk_document
from .embeddings import get_embedder
from .parsing import parse_file

log = logging.getLogger(__name__)
EMBED_BATCH = 64


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def register_document(db: Session, path: Path, filename: str) -> tuple[Document, bool]:
    """Create a pending Document row (dedupe by content hash). Returns (doc, created)."""
    digest = sha256_file(path)
    existing = db.scalar(select(Document).where(Document.sha256 == digest))
    if existing:
        path.unlink(missing_ok=True)
        return existing, False
    final = get_settings().upload_dir / f"{digest}{Path(filename).suffix.lower()}"
    path.replace(final)
    doc = Document(filename=filename, title=filename, sha256=digest, status="pending")
    db.add(doc)
    db.commit()
    return doc, True


def stored_path(doc: Document) -> Path:
    return get_settings().upload_dir / f"{doc.sha256}{Path(doc.filename).suffix.lower()}"


def process_document(doc_id: uuid.UUID) -> None:
    """Parse -> chunk -> embed -> persist. Runs in a background task with its own session."""
    s = get_settings()
    with SessionLocal() as db:
        doc = db.get(Document, doc_id)
        if not doc:
            return
        try:
            doc.status = "processing"
            db.commit()

            title, pages, mime, ocr_pages = parse_file(stored_path(doc), doc.filename)
            drafts = chunk_document(pages, s.chunk_target_words, s.chunk_overlap_words)
            if not drafts:
                raise ValueError("No extractable text. If this is a scanned PDF, set OCR_ENABLED=true (see requirements-ocr.txt).")

            embedder = get_embedder()
            rows: list[Chunk] = []
            for i in range(0, len(drafts), EMBED_BATCH):
                batch = drafts[i : i + EMBED_BATCH]
                vecs = embedder.embed([d.text for d in batch])
                for j, (d, v) in enumerate(zip(batch, vecs)):
                    rows.append(
                        Chunk(
                            document_id=doc.id,
                            page=d.page,
                            chunk_index=i + j,
                            text=d.text,
                            word_count=d.word_count,
                            embedding=v,
                        )
                    )
            db.add_all(rows)
            doc.title, doc.mime, doc.ocr_pages = title[:1000], mime, ocr_pages
            doc.num_pages, doc.num_chunks, doc.status, doc.error = len(pages), len(rows), "ready", None
            db.commit()
            log.info("Ingested %s: %d pages, %d chunks", doc.filename, len(pages), len(rows))
        except Exception as e:  # noqa: BLE001
            db.rollback()
            doc = db.get(Document, doc_id)
            doc.status, doc.error = "failed", str(e)[:2000]
            db.commit()
            log.exception("Ingestion failed for %s", doc_id)
