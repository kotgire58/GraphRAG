"""Vector-based retrieval using pgvector cosine similarity."""

import json
import logging
from dataclasses import dataclass

import asyncpg
import httpx

from config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class VectorResult:
    """A single chunk returned by vector similarity search."""

    chunk_id: int
    document_id: int
    content: str
    filename: str
    similarity: float


async def _embed_query(query: str) -> list[float]:
    """Embed a single query string via the embedding API."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.embedding_base_url}/embeddings",
                headers={
                    "Authorization": f"Bearer {settings.embedding_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.embedding_model,
                    "input": [query],
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["data"][0]["embedding"]
    except httpx.HTTPStatusError as e:
        logger.error(
            f"Embedding API HTTP error: {e.response.status_code} "
            f"{e.response.text[:200]}"
        )
        raise
    except Exception as e:
        logger.error(f"Embedding API error: {e}")
        raise


async def search(
    query: str, pool: asyncpg.Pool, limit: int = 5
) -> list[VectorResult]:
    """Embed the query and run cosine-similarity search over pgvector chunks."""
    embedding = await _embed_query(query)
    embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"

    results: list[VectorResult] = []
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM vector_search($1::vector, $2)",
                embedding_str,
                limit,
            )
            for row in rows:
                metadata = row["metadata"]
                if isinstance(metadata, str):
                    metadata = json.loads(metadata)
                filename = metadata.get("filename", "unknown")

                results.append(
                    VectorResult(
                        chunk_id=row["id"],
                        document_id=row["document_id"],
                        content=row["content"],
                        filename=filename,
                        similarity=float(row["similarity"]),
                    )
                )
    except Exception as e:
        logger.error(f"Vector search failed: {e}")
        raise

    logger.info(
        f"Vector search for '{query[:60]}' returned {len(results)} chunks"
    )
    return results
