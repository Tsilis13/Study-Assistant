from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))

    documents: Mapped[list["Document"]] = relationship(back_populates="owner", cascade="all, delete-orphan")


class Document(Base):
    """
    One piece of study material: an uploaded PDF/text file or a pasted note.
    The full text is stored HERE, so the vector index
    can always be rebuilt from it. In a PDF, pages are separated by a form-feed character.
    """
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    title: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(10))          # "pdf", "text" or "note"
    content: Mapped[str] = mapped_column(Text)
    word_count: Mapped[int] = mapped_column(default=0)
    chunk_count: Mapped[int] = mapped_column(default=0)
    indexed: Mapped[bool] = mapped_column(default=False)   # False = the vector step failed; run reindex.py

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    owner: Mapped["User"] = relationship(back_populates="documents")
