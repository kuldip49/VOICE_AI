"""Knowledge base management: upload (PDF/TXT), list, delete, retrieval test."""
import re

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import serializers as ser
from ..config import get_settings
from ..database import get_db
from ..models import KnowledgeChunk, KnowledgeDocument
from ..security import require_admin
from ..services import rag
from ..services.llm import get_provider

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"], dependencies=[Depends(require_admin)])

ALLOWED = {".txt": "text/plain", ".md": "text/markdown", ".pdf": "application/pdf"}


def _doc(d: KnowledgeDocument) -> dict:
    return {"id": d.id, "filename": d.filename, "content_type": d.content_type, "size_bytes": d.size_bytes,
            "status": d.status, "chunk_count": d.chunk_count, "error": d.error, "created_at": ser.iso(d.created_at)}


@router.get("/documents")
def list_documents(db: Session = Depends(get_db)):
    return [_doc(d) for d in db.execute(select(KnowledgeDocument).order_by(KnowledgeDocument.created_at.desc())).scalars()]


@router.get("/documents/{doc_id}/chunks")
def document_chunks(doc_id: int, db: Session = Depends(get_db)):
    d = db.get(KnowledgeDocument, doc_id)
    if not d:
        raise HTTPException(404, "Document not found")
    rows = db.execute(select(KnowledgeChunk).where(KnowledgeChunk.document_id == doc_id)
                      .order_by(KnowledgeChunk.chunk_index)).scalars()
    return [{"id": c.id, "index": c.chunk_index, "title": c.title, "content": c.content,
             "has_embedding": bool(c.embedding)} for c in rows]


@router.post("/documents")
async def upload(file: UploadFile = File(...), db: Session = Depends(get_db)):
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", (file.filename or "upload").split("/")[-1].split("\\")[-1])[:200]
    ext = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in ALLOWED:
        raise HTTPException(415, "Only PDF, TXT and MD files are allowed")
    limit = get_settings().max_upload_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"File exceeds {get_settings().max_upload_mb} MB limit")
    if not data:
        raise HTTPException(422, "File is empty")
    if ext == ".pdf" and not data.startswith(b"%PDF"):
        raise HTTPException(415, "File content is not a valid PDF")
    if ext != ".pdf" and b"\x00" in data[:4096]:
        raise HTTPException(415, "Text file contains binary data")
    p = get_provider()
    doc = rag.ingest_document(db, name, ALLOWED[ext], data, embed_fn=getattr(p, "embed", None) if p else None)
    return _doc(doc)


@router.delete("/documents/{doc_id}")
def delete(doc_id: int, db: Session = Depends(get_db)):
    d = db.get(KnowledgeDocument, doc_id)
    if not d:
        raise HTTPException(404, "Document not found")
    db.delete(d)
    db.commit()
    rag.invalidate_index()
    return {"deleted": doc_id}


class SearchIn(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    top_k: int = Field(default=3, ge=1, le=10)


@router.post("/search")
def search(body: SearchIn, db: Session = Depends(get_db)):
    res = rag.retrieve(db, body.query, body.top_k)
    return {"found": res["found"], "method": res["method"], "top_score": res.get("top_score"),
            "threshold": rag.MIN_RELEVANCE, "results": [c.as_source() | {"content": c.content} for c in res["chunks"]]}
