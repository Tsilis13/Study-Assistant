from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---- Users

class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=20)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def lowercase_username(cls, value: str) -> str:
        return value.strip().lower()


class UserResponse(BaseModel):
    """Note what is NOT here: password_hash never leaves the server."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---- Documents

class NoteCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=200_000)


class DocumentResponse(BaseModel):
    """The full text is never sent in lists; only the facts about the document."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    kind: str
    word_count: int
    chunk_count: int
    indexed: bool
    created_at: datetime


# ---- Ask

class AskRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    question: str = Field(min_length=2, max_length=500)
    document_id: int | None = Field(default=None, gt=0)     # None = search all your documents
    top_k: int = Field(default=5, ge=1, le=10)


class Source(BaseModel):
    document_id: int
    title: str
    page: int | None
    text: str
    distance: float


class AskResponse(BaseModel):
    question: str
    answer: str | None          # None when the AI is unavailable (the sources are still returned)
    sources: list[Source]
    note: str | None = None


# ---- Quiz and summary

class QuizRequest(BaseModel):
    document_id: int = Field(gt=0)
    num_questions: int = Field(default=5, ge=1, le=10)


class QuizQuestion(BaseModel):
    question: str
    options: list[str]
    correct_index: int
    explanation: str


class QuizResponse(BaseModel):
    document_id: int
    title: str
    questions: list[QuizQuestion]


class SummarizeRequest(BaseModel):
    document_id: int = Field(gt=0)


class SummaryResponse(BaseModel):
    document_id: int
    title: str
    summary: str
    sections_used: int
    sections_total: int         # if used < total, the summary covers a sample of the document
