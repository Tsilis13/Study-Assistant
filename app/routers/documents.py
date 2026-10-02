import os

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app import models, rag, schemas, text_utils
from app.database import get_db
from app.dependencies import get_current_user
from app.limiter import limiter

router = APIRouter(prefix="/documents", tags=["documents"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024         # 10 MB per file
MAX_CONTENT_CHARS = 1_000_000               # about 170,000 words of text per document
ALLOWED_EXTENSIONS = (".pdf", ".txt", ".md")


def get_owned_document_or_404(db: Session, doc_id: int, user: models.User) -> models.Document:
    """
    Find a document ONLY among this user's documents. "Does not exist" and "not yours"
    both give 404, so nobody can discover which ids exist.
    """
    doc = (
        db.query(models.Document)
        .filter(models.Document.id == doc_id, models.Document.user_id == user.id)
        .first()
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return doc


def save_document(db: Session, user: models.User, title: str, content: str, kind: str) -> models.Document:
    """Save to SQLite FIRST, then build the vectors. A vector failure loses nothing."""
    doc = models.Document(
        user_id=user.id,
        title=title,
        kind=kind,
        content=content,
        word_count=len(content.split()),
        chunk_count=len(text_utils.chunk_pages(content, paged=(kind == "pdf"))),
        indexed=False,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    if rag.index_document(doc):
        doc.indexed = True
        db.commit()
        db.refresh(doc)
    return doc


@router.post("/upload", response_model=schemas.DocumentResponse, status_code=201)
@limiter.limit("10/minute")
def upload_document(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Keep only the file name (no folders) and cap its length.
    filename = os.path.basename((file.filename or "").replace("\\", "/")).strip()[:200]
    if not filename.lower().endswith(ALLOWED_EXTENSIONS):
        raise HTTPException(status_code=415, detail="Only .pdf, .txt and .md files are supported.")

    data = file.file.read(MAX_UPLOAD_BYTES + 1)      # never read more than the limit
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="The file is larger than 10 MB.")

    try:
        content, kind = text_utils.extract_text(filename, data)
    except text_utils.UnreadableFile as error:
        raise HTTPException(status_code=422, detail=str(error))
    if len(content) > MAX_CONTENT_CHARS:
        raise HTTPException(status_code=413, detail="The file contains too much text (limit: about 170,000 words).")

    return save_document(db, current_user, filename, content, kind)


@router.post("/note", response_model=schemas.DocumentResponse, status_code=201)
@limiter.limit("30/minute")
def create_note(
    request: Request,
    data: schemas.NoteCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return save_document(db, current_user, data.title, data.text, "note")


@router.get("", response_model=list[schemas.DocumentResponse])
def list_documents(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return (
        db.query(models.Document)
        .filter(models.Document.user_id == current_user.id)
        .order_by(models.Document.created_at.desc(), models.Document.id.desc())
        .all()
    )


@router.get("/{doc_id}", response_model=schemas.DocumentResponse)
def get_document(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return get_owned_document_or_404(db, doc_id, current_user)


@router.delete("/{doc_id}", status_code=204)
def delete_document(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    doc = get_owned_document_or_404(db, doc_id, current_user)
    db.delete(doc)
    db.commit()
    rag.remove_document(doc_id)     # after the commit: the index never gets ahead of SQLite
