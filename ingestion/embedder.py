"""Embed document chunks via OpenRouter and store in pgvector."""

import json
import logging

import asyncpg
import httpx

from config.settings import settings

logger = logging.getLogger(__name__)

BATCH_SIZE = 20


async def _call_embedding_api(
    client: httpx.AsyncClient, texts: list[str]
) -> list[list[float]]:
    """Call the OpenRouter embedding endpoint for a batch of texts."""
    response = await client.post(
        f"{settings.embedding_base_url}/embeddings",
        headers={
            "Authorization": f"Bearer {settings.embedding_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": settings.embedding_model,
            "input": texts,
        },
        timeout=60.0,
    )
    response.raise_for_status()
    data = response.json()
    sorted_data = sorted(data["data"], key=lambda x: x["index"])
    return [item["embedding"] for item in sorted_data]


async def _document_already_embedded(
    pool: asyncpg.Pool, document_id: int
) -> bool:
    """Check if a document already has chunks in the database."""
    async with pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM chunks WHERE document_id = $1",
            document_id,
        )
        return count > 0


async def embed_chunks(
    chunks: list[dict], document_id: int, pool: asyncpg.Pool
) -> None:
    """Embed a list of chunks and insert them into pgvector.

    Skips if the document already has chunks. Processes in batches
    of BATCH_SIZE to respect API limits.
    """
    try:
        if await _document_already_embedded(pool, document_id):
            logger.info(
                f"Document {document_id} already has chunks, skipping embed"
            )
            return
    except Exception as e:
        logger.error(
            f"Failed to check existing chunks for doc {document_id}: {e}"
        )
        raise

    total_batches = (len(chunks) + BATCH_SIZE - 1) // BATCH_SIZE
    filename = chunks[0]["metadata"]["filename"] if chunks else "unknown"

    async with httpx.AsyncClient() as client:
        for batch_idx in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[batch_idx : batch_idx + BATCH_SIZE]
            batch_num = batch_idx // BATCH_SIZE + 1
            texts = [c["content"] for c in batch]

            try:
                embeddings = await _call_embedding_api(client, texts)
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"Embedding API HTTP error for {filename} "
                    f"batch {batch_num}/{total_batches}: "
                    f"{e.response.status_code} {e.response.text}"
                )
                raise
            except Exception as e:
                logger.error(
                    f"Embedding API error for {filename} "
                    f"batch {batch_num}/{total_batches}: {e}"
                )
                raise

            try:
                async with pool.acquire() as conn:
                    for chunk, embedding in zip(batch, embeddings):
                        embedding_str = (
                            "[" + ",".join(str(v) for v in embedding) + "]"
                        )
                        await conn.execute(
                            "INSERT INTO chunks "
                            "(document_id, chunk_index, content, embedding, "
                            "token_count, metadata) "
                            "VALUES ($1, $2, $3, $4::vector, $5, $6)",
                            document_id,
                            chunk["chunk_index"],
                            chunk["content"],
                            embedding_str,
                            chunk["token_count"],
                            json.dumps(chunk["metadata"]),
                        )
            except Exception as e:
                logger.error(
                    f"DB insert error for {filename} "
                    f"batch {batch_num}/{total_batches}: {e}"
                )
                raise

            logger.info(
                f"Embedded batch {batch_num}/{total_batches} "
                f"for {filename}"
            )
