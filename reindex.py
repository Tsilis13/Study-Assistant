"""
Rebuilds the vector index from SQLite.

    python reindex.py

Run it from the project root. SQLite is the source of truth and the index is only a searchable
copy, so this is always safe. Run it after deleting chroma_db/, after a logged indexing error,
or after changing the embedding model. Stop the server first: a running server keeps its own
copy of the index in memory.
"""
from app import models, rag
from app.database import SessionLocal


def main() -> None:
    db = SessionLocal()
    try:
        ok, failed = rag.reindex_all(db)
        total = db.query(models.Document).count()
        print(f"Documents in SQLite:  {total}")
        print(f"Indexed:              {ok}")
        print(f"Failed:               {failed}")
        print(f"Chunks in the index:  {rag.collection.count()}")
        print("OK: the index matches the database." if failed == 0 else "Some documents failed; see the log above.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
