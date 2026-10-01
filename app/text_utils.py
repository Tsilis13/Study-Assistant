"""Reading files and cutting text into chunks. """
import io
import random

from pypdf import PdfReader

PAGE_BREAK = "\f"       # separates the pages of a PDF inside Document.content

# The embedding model (MiniLM) only reads about 256 tokens (roughly 190 words) per text.
# Longer chunks would be silently cut off, so we stay below that.
CHUNK_WORDS = 180
CHUNK_OVERLAP = 30      # the next chunk starts 30 words before the previous one ended


class UnreadableFile(ValueError):
    """The file cannot be turned into text. The message is safe to show to the user."""


def extract_text(filename: str, data: bytes) -> tuple[str, str]:
    """Returns (content, kind) where kind is "pdf" or "text"."""
    if filename.lower().endswith(".pdf"):
        try:
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted:
                raise UnreadableFile("This PDF is password-protected. Remove the password and try again.")
            pages = [(page.extract_text() or "").replace(PAGE_BREAK, " ") for page in reader.pages]
        except UnreadableFile:
            raise
        except Exception as error:
            raise UnreadableFile("This PDF could not be read. Is the file damaged?") from error
        content, kind = PAGE_BREAK.join(pages), "pdf"
    else:
        content, kind = data.decode("utf-8", errors="replace").replace(PAGE_BREAK, " "), "text"

    if not content.replace(PAGE_BREAK, "").strip():
        raise UnreadableFile("No text was found in this file. Scanned PDFs (images of pages) are not supported.")
    return content, kind


def chunk_pages(content: str, paged: bool) -> list[dict]:
    """
    Cut the text into overlapping chunks of about CHUNK_WORDS words.
    Chunks never cross a page boundary, so a chunk from a PDF has an exact page number.
    Returns [{"text": ..., "page": ...}]; page is 0 when the material has no pages.
    """
    chunks = []
    for page_index, page_text in enumerate(content.split(PAGE_BREAK)):
        words = page_text.split()
        start = 0
        while start < len(words):
            chunks.append({
                "text": " ".join(words[start:start + CHUNK_WORDS]),
                "page": page_index + 1 if paged else 0,
            })
            if start + CHUNK_WORDS >= len(words):
                break
            start += CHUNK_WORDS - CHUNK_OVERLAP
    return chunks


def sample_chunks(chunks: list[dict], k: int) -> list[dict]:
    """At most k chunks spread evenly over the whole material (for quizzes and summaries)."""
    if len(chunks) <= k or k < 2:
        return chunks[:k]
    
    n = len(chunks)  # Select one chunk from each of k evenly spaced sections of the document.
    sampled = []
    for i in range(k):
        start = round(i * n / k)
        end = round((i + 1) * n / k)
        position = random.randrange(start, end)
        sampled.append(chunks[position])
    return sampled
