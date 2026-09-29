# Study Assistant

Upload your lecture notes, PDFs and text files, then ask questions about them. Every answer
shows the passages it came from (with page numbers for PDFs). The assistant can also write a
quiz from a document and summarize it.

It follows the design of the Smart Knowledge Hub: FastAPI, SQLite, ChromaDB, a local embedding
model, and Groq for the language model.

## Features

- Accounts: bcrypt-hashed passwords, JWT login, per-account rate limits.
- Material: upload `.pdf`, `.txt`, `.md` (up to 10 MB) or write a note. Documents are private to their owner.
- Ask: semantic search finds the most relevant passages, the model answers using only those, and the
  answer cites them as [1], [2]. Click a citation to see the passage.
- Quiz: multiple-choice questions written from a document, graded in the browser with explanations.
- Summary: key points of a document. For very long documents it uses a sample spread across the
  whole text and says so.
- Honest failures: if nothing relevant is found, the model is not called and no answer is invented.
  If the model is unavailable, `/ask` still returns the matching passages.

## Architecture

```text
Browser (frontend/index.html, served at /)
        | HTTP + Bearer token
        v
FastAPI: auth, documents, ask / quiz / summarize
   |             |                |
   v             v                v
SQLite        ChromaDB         Groq LLM
(the truth:   (search index,   (writes answers,
 users,        rebuildable)     quizzes, summaries;
 full text)                     never picks passages)
```

Two rules hold everywhere:

1. **SQLite is the source of truth.** The vector index is a copy that `python reindex.py` can rebuild at any time.
   Documents are saved to SQLite first; if indexing fails, nothing is lost and the document is marked "not searchable yet".
2. **Every query is limited to the logged-in user**, both in the vector search and again in SQL.

## Setup

Python 3.11 or newer.

```bash
python -m venv venv
venv\Scripts\activate            # Windows      (macOS/Linux: source venv/bin/activate)
pip install -r requirements.txt  # large: it downloads PyTorch (several GB)
copy .env.example .env           # macOS/Linux: cp .env.example .env
```

Edit `.env`: set `JWT_SECRET_KEY` (the file explains how) and, for written answers, `GROQ_API_KEY`.
The first search downloads the embedding model (about 90 MB) once.

## Run

```bash
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000, create an account, add some material, and ask a question.
The API documentation is at http://127.0.0.1:8000/docs.

## Test

```bash
pip install -r requirements-dev.txt
python -m pytest -v
```

The tests use a temporary database and index, a fake embedder and a fake language model, so they
need no internet, no API key, and never touch your data.

## Endpoints

| Method | Path | What it does |
|---|---|---|
| POST | `/auth/register`, `/auth/login` | create an account, get a token |
| GET | `/auth/me` | who am I |
| POST | `/documents/upload` | upload a PDF, TXT or MD file |
| POST | `/documents/note` | save a pasted note |
| GET | `/documents`, `/documents/{id}` | list / read document details |
| DELETE | `/documents/{id}` | delete a document and its search data |
| POST | `/ask` | answer a question from your material, with sources |
| POST | `/quiz` | make a multiple-choice quiz from a document |
| POST | `/summarize` | summarize a document |

## Maintenance

```bash
python reindex.py    # stop the server first
```

Rebuilds the search index from SQLite. Use it after deleting `chroma_db/`, after a "not searchable
yet" warning, or after changing the embedding model.

## Tuning

`MAX_DISTANCE` in `app/routers/study.py` decides how close a passage must be to count as relevant
(0 means identical meaning). If real questions often get "I couldn't find anything relevant", raise it a little;
if unrelated passages show up, lower it. Each source in `/ask` includes its `distance`, and the page shows it when you hover a source title.

## Limits

- Scanned PDFs (pages that are images) are not supported: there is no text to read.
- Text and notes are chunked into about 180 words, because the embedding model reads about 256 tokens.
- Summaries and quizzes of long documents use a sample of sections, not the whole text.
- The database schema is created automatically. There are no migrations yet (Alembic would be the next step).

## Troubleshooting

- `JWT_SECRET_KEY is not set`: create `.env` from `.env.example` in the project root.
- Odd ChromaDB errors when the project is inside OneDrive: sync can lock its files. Set
  `CHROMA_PATH=C:/study_chroma` in `.env` to keep the index outside the synced folder.
- Answers say the AI is unavailable: check `GROQ_API_KEY`, or your internet connection.
