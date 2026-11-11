import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..middleware import sign_file_token
from ..models import Document
from ..schemas import DocumentOut
from ..services.ingest import process_document, register_document, stored_path

router = APIRouter(prefix="/api/documents", tags=["documents"])
ALLOWED = {".pdf", ".md", ".markdown", ".txt", ".rst"}


@router.post("", response_model=list[DocumentOut], status_code=202)
async def upload(
    background: BackgroundTasks,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    limit = get_settings().max_upload_mb * 1024 * 1024
    out: list[Document] = []
    for f in files:
        name = Path(f.filename or "upload").name
        if Path(name).suffix.lower() not in ALLOWED:
            raise HTTPException(415, f"Unsupported file type for {name}. Allowed: {sorted(ALLOWED)}")
        with tempfile.NamedTemporaryFile(delete=False, dir=get_settings().upload_dir) as tmp:
            size = 0
            while chunk := await f.read(1 << 20):
                size += len(chunk)
                if size > limit:
                    Path(tmp.name).unlink(missing_ok=True)
                    raise HTTPException(413, f"{name} exceeds {get_settings().max_upload_mb} MB")
                tmp.write(chunk)
        doc, created = register_document(db, Path(tmp.name), name)
        if created or doc.status == "failed":
            background.add_task(process_document, doc.id)
        out.append(doc)
    return out


@router.get("", response_model=list[DocumentOut])
def list_documents(db: Session = Depends(get_db)):
    return db.scalars(select(Document).order_by(Document.created_at.desc())).all()


@router.get("/{doc_id}", response_model=DocumentOut)
def get_document(doc_id: uuid.UUID, db: Session = Depends(get_db)):
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    return doc


@router.get("/{doc_id}/signed-url")
def signed_url(doc_id: uuid.UUID, db: Session = Depends(get_db)):
    """Short-lived link for <iframe>/<a> (which cannot send an API-key header). Plain URL when auth is off."""
    if not db.get(Document, doc_id):
        raise HTTPException(404, "Document not found")
    path = f"/api/documents/{doc_id}/file"
    keys = get_settings().api_key_list
    return {"url": f"{path}?token={sign_file_token(keys[0], str(doc_id))}" if keys else path, "expires_in": 300 if keys else None}


@router.get("/{doc_id}/file")
def download(doc_id: uuid.UUID, db: Session = Depends(get_db)):
    """Serves the original file so the UI can open it at #page=N for citation viewing."""
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    p = stored_path(doc)
    if not p.exists():
        raise HTTPException(410, "File missing from storage")
    return FileResponse(p, media_type=doc.mime, filename=doc.filename, content_disposition_type="inline")


@router.delete("/{doc_id}", status_code=204)
def delete_document(doc_id: uuid.UUID, db: Session = Depends(get_db)):
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    stored_path(doc).unlink(missing_ok=True)
    db.delete(doc)
    db.commit()
