"""
The vector layer: makes study material searchable by meaning.

Two rules:
  1. SQLite is the source of truth. This index can always be rebuilt from it (reindex_all).
  2. Every search is limited to one user (the user_id filter).
"""
import logging
import os

import chromadb
from dotenv import load_dotenv

from app import models, text_utils

load_dotenv()

logger = logging.getLogger(__name__)

BATCH_SIZE = 64

chroma_client = chromadb.PersistentClient(path=os.getenv("CHROMA_PATH", "./chroma_db"))

# cosine distance: 0 = identical meaning, bigger = less related.
collection = chroma_client.get_or_create_collection(
    name="study_chunks", metadata={"hnsw:space": "cosine"}
)

_embedder = None


def embed(texts: list[str]) -> list[list[float]]:
    """Turn texts into vectors. The model loads on first use (this takes a few seconds once)."""
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer   # slow import, so only when needed
        _embedder = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedder.encode(texts, batch_size=32).tolist()


def index_document(doc: models.Document) -> bool:
    """
    (Re)build the vectors of one document. Returns False if it failed.
    SQLite already has the document, so a failure here never loses data: it is logged,
    the document is marked indexed=False, and reindex.py can repair it later.
    """
    try:
        chunks = text_utils.chunk_pages(doc.content, paged=(doc.kind == "pdf"))
        collection.delete(where={"doc_id": doc.id})     # drop old vectors of this document first
        for start in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[start:start + BATCH_SIZE]
            collection.upsert(
                ids=[f"doc{doc.id}-c{start + i}" for i in range(len(batch))],
                embeddings=embed([chunk["text"] for chunk in batch]),
                documents=[chunk["text"] for chunk in batch],
                metadatas=[
                    {"user_id": doc.user_id, "doc_id": doc.id, "page": chunk["page"]}
                    for chunk in batch
                ],
            )
        return True
    except Exception:
        logger.exception("Could not index document %s (SQLite is fine; run reindex.py to repair)", doc.id)
        return False


def remove_document(doc_id: int) -> None:
    try:
        collection.delete(where={"doc_id": doc_id})
    except Exception:
        logger.exception("Could not remove the vectors of document %s", doc_id)


def search(user_id: int, query: str, top_k: int = 5, doc_id: int | None = None) -> list[dict]:
    """The top_k chunks of THIS user closest in meaning to the query, closest first."""
    if collection.count() == 0:
        return []

    where = {"user_id": user_id}                                    # the privacy rule
    if doc_id is not None:
        where = {"$and": [{"user_id": user_id}, {"doc_id": doc_id}]}

    results = collection.query(query_embeddings=embed([query]), n_results=top_k, where=where)

    # Chroma returns one inner list per query. We sent one query, so we take [0] of each.
    return [
        {"doc_id": meta["doc_id"], "page": meta["page"], "distance": distance, "text": text}
        for meta, distance, text in zip(
            results["metadatas"][0], results["distances"][0], results["documents"][0]
        )
    ]


def reindex_all(db) -> tuple[int, int]:
    """Empty the index and rebuild it from SQLite. Returns (documents indexed, documents failed)."""
    existing_ids = collection.get()["ids"]
    if existing_ids:
        collection.delete(ids=existing_ids)

    ok = failed = 0
    for doc in db.query(models.Document).all():
        doc.indexed = index_document(doc)
        ok, failed = (ok + 1, failed) if doc.indexed else (ok, failed + 1)
    db.commit()
    return ok, failed
