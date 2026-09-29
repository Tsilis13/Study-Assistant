from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app import llm, models, rag, schemas, text_utils
from app.database import get_db
from app.dependencies import get_current_user
from app.limiter import limiter
from app.routers.documents import get_owned_document_or_404

router = APIRouter(tags=["study"])

# Passages farther away than this (0 = identical meaning, bigger = less related) are treated
# as "not relevant". A first guess; tune it by watching the `distance` values in real answers.
MAX_DISTANCE = 0.8

QUIZ_SECTIONS = 8       # how many parts of the document the quiz is written from
SUMMARY_SECTIONS = 12

NOTHING_FOUND = "I couldn't find anything relevant in your documents."


def document_sections(doc: models.Document, wanted: int) -> tuple[list[dict], int]:
    """A sample of the document's chunks, ready for the prompt, and how many chunks it has in total."""
    chunks = text_utils.chunk_pages(doc.content, paged=(doc.kind == "pdf"))
    picked = text_utils.sample_chunks(chunks, wanted)
    return [{"title": doc.title, "page": c["page"], "text": c["text"]} for c in picked], len(chunks)


@router.post("/ask", response_model=schemas.AskResponse)
@limiter.limit("20/minute")     # every call may cost model usage
def ask(
    request: Request,
    data: schemas.AskRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if data.document_id is not None:
        get_owned_document_or_404(db, data.document_id, current_user)   # 404 for other people's documents

    # 1. Retrieval: the closest passages of THIS user, minus the ones that are too far away.
    hits = rag.search(current_user.id, data.question, top_k=data.top_k, doc_id=data.document_id)
    hits = [hit for hit in hits if hit["distance"] <= MAX_DISTANCE]

    # 2. The titles come from SQLite (the truth). A hit whose document no longer exists there
    #    is a stale vector and must not be returned.
    titles = dict(
        db.query(models.Document.id, models.Document.title)
        .filter(
            models.Document.id.in_({hit["doc_id"] for hit in hits}),
            models.Document.user_id == current_user.id,
        )
        .all()
    )
    sources = [
        {
            "document_id": hit["doc_id"],
            "title": titles[hit["doc_id"]],
            "page": hit["page"] or None,
            "text": hit["text"],
            "distance": round(hit["distance"], 3),
        }
        for hit in hits
        if hit["doc_id"] in titles
    ]

    # 3. Nothing relevant: say so without calling the model (saves cost, prevents invented answers).
    if not sources:
        return {"question": data.question, "answer": NOTHING_FOUND, "sources": []}

    # 4. Generation. If the model is down, the student still gets the passages.
    try:
        answer, note = llm.answer_question(data.question, sources), None
    except llm.LLMUnavailable:
        answer = None
        note = "The AI answer is unavailable right now. Here are the most relevant passages from your documents."
    return {"question": data.question, "answer": answer, "sources": sources, "note": note}


@router.post("/quiz", response_model=schemas.QuizResponse)
@limiter.limit("5/minute")
def make_quiz(
    request: Request,
    data: schemas.QuizRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    doc = get_owned_document_or_404(db, data.document_id, current_user)
    sections, _ = document_sections(doc, QUIZ_SECTIONS)
    try:
        questions = llm.generate_quiz(sections, data.num_questions)
    except llm.LLMUnavailable:
        raise HTTPException(status_code=503, detail="The AI service is unavailable right now. Try again in a moment.")
    if not questions:
        raise HTTPException(status_code=502, detail="The AI did not return usable questions. Try again.")
    return {"document_id": doc.id, "title": doc.title, "questions": questions[:data.num_questions]}


@router.post("/summarize", response_model=schemas.SummaryResponse)
@limiter.limit("5/minute")
def summarize(
    request: Request,
    data: schemas.SummarizeRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    doc = get_owned_document_or_404(db, data.document_id, current_user)
    sections, total = document_sections(doc, SUMMARY_SECTIONS)
    try:
        summary = llm.summarize(sections)
    except llm.LLMUnavailable:
        raise HTTPException(status_code=503, detail="The AI service is unavailable right now. Try again in a moment.")
    return {
        "document_id": doc.id,
        "title": doc.title,
        "summary": summary,
        "sections_used": len(sections),
        "sections_total": total,
    }
