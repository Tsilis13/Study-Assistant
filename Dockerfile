FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/opt/hf_cache \
    DATABASE_URL=sqlite:////data/app.db \
    CHROMA_PATH=/data/chroma_db

WORKDIR /code

# CPU-only PyTorch first. It is much smaller than the default (CUDA) build,
# and sentence-transformers then finds it already installed.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download the embedding model while building, so the first upload or search
# does not need internet access and is not slow.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

COPY app ./app
COPY frontend ./frontend
COPY reindex.py .

# /data holds app.db and chroma_db (mounted as a volume, see docker-compose.yml).
RUN useradd --create-home appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /data /opt/hf_cache /code
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"

# One worker on purpose: rate-limit counters live in memory and ChromaDB
# uses a local folder. No --reload in a container.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]