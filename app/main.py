from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app import models  # noqa: F401  (the import registers the tables with Base)
from app.database import Base, engine
from app.limiter import limiter
from app.routers import auth, documents, study

# Create the tables if they do not exist yet.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Study Assistant", version="1.0.0")

# The web page is served by this same app, so it needs no CORS. These origins are only for
# a frontend you might run separately during development. The token travels in the
# Authorization header, so no cookies/credentials are used.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000",
                   "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(study.router)

FRONTEND_FILE = Path(__file__).resolve().parent.parent / "frontend" / "index.html"


@app.get("/", include_in_schema=False)
def web_page():
    return FileResponse(FRONTEND_FILE)


@app.get("/health")
def health_check():
    return {"status": "online"}
