from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from .config import settings
from .db import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    prefs: Mapped[dict] = mapped_column(JSON, default=dict)  # default interests, theme, budget, diet
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Trip(Base):
    __tablename__ = "trips"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    destination: Mapped[str] = mapped_column(String(200))
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    days: Mapped[int] = mapped_column(Integer)
    theme: Mapped[str] = mapped_column(String(30))
    budget: Mapped[str] = mapped_column(String(20))
    diet: Mapped[str] = mapped_column(String(10))
    interests: Mapped[list] = mapped_column(JSON, default=list)
    itinerary: Mapped[dict] = mapped_column(JSON)  # full plan response
    saved: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class KBChunk(Base):
    """RAG knowledge base: destination guide passages with embeddings."""

    __tablename__ = "kb_chunks"
    id: Mapped[int] = mapped_column(primary_key=True)
    destination: Mapped[str] = mapped_column(String(200), index=True)
    source: Mapped[str] = mapped_column(String(300))
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    embedding = mapped_column(Vector(settings.embed_dim))
    __table_args__ = (
        Index(
            "ix_kb_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class ApiCache(Base):
    """Caches slow or rate-limited external API responses (geocoding, places, weather)."""

    __tablename__ = "api_cache"
    key: Mapped[str] = mapped_column(String(300), primary_key=True)
    payload: Mapped[dict | list | None] = mapped_column(JSON)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
