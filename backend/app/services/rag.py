"""RAG: destination guide text (Wikivoyage, falling back to Wikipedia) -> chunks -> embeddings in pgvector."""
import httpx
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import KBChunk
from .chunking import chunk_text

_embedder = None
UA = {"User-Agent": "AITouristGuide/1.0 (college project)"}


def _model():
    global _embedder
    if _embedder is None:
        from fastembed import TextEmbedding

        _embedder = TextEmbedding(settings.embed_model, cache_dir=settings.embed_cache)
    return _embedder


def embed_docs(texts: list[str]) -> list[list[float]]:
    return [[float(x) for x in v] for v in _model().embed(texts)]


def embed_query(text: str) -> list[float]:
    return [float(x) for x in next(iter(_model().query_embed([text])))]


def fetch_article(title: str) -> tuple[str, str] | None:
    for site in ("en.wikivoyage.org", "en.wikipedia.org"):
        r = httpx.get(f"https://{site}/w/api.php", headers=UA, timeout=25, params={
            "action": "query", "prop": "extracts", "explaintext": 1, "titles": title, "redirects": 1,
            "format": "json"})
        r.raise_for_status()
        for page in r.json().get("query", {}).get("pages", {}).values():
            text = page.get("extract") or ""
            if len(text) > 500:
                return f"https://{site}/wiki/{page['title'].replace(' ', '_')}", text
    return None


def ingest_destination(db: Session, destination: str, titles: list[str]) -> int:
    for title in titles:
        art = fetch_article(title)
        if not art:
            continue
        source, text = art
        chunks = chunk_text(text)[:120]
        if not chunks:
            continue
        vecs = embed_docs([f"{t}: {c}" for t, c in chunks])
        db.execute(delete(KBChunk).where(KBChunk.destination == destination))
        db.add_all(KBChunk(destination=destination, source=source, title=t, content=c, embedding=v)
                   for (t, c), v in zip(chunks, vecs))
        db.commit()
        return len(chunks)
    return 0


def ensure_kb(db: Session, destination: str, titles: list[str]) -> None:
    if db.scalar(select(KBChunk.id).where(KBChunk.destination == destination).limit(1)) is None:
        ingest_destination(db, destination, titles)


def retrieve(db: Session, destination: str, query: str, k: int = 5) -> list[dict]:
    qv = embed_query(query)
    rows = db.execute(
        select(KBChunk, KBChunk.embedding.cosine_distance(qv).label("dist"))
        .where(KBChunk.destination == destination).order_by("dist").limit(k)).all()
    return [{"title": r.KBChunk.title, "content": r.KBChunk.content, "source": r.KBChunk.source,
             "similarity": round(1 - float(r.dist), 3)} for r in rows]
