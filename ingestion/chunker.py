"""Split markdown documents into token-counted chunks with metadata."""

import logging
from pathlib import Path

import tiktoken

from config.settings import settings

logger = logging.getLogger(__name__)

ENCODING = tiktoken.get_encoding("cl100k_base")


def _extract_title(text: str) -> str:
    """Extract the first H1 heading from markdown text."""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("##"):
            return stripped[2:].strip()
    return "Untitled"


def _token_len(text: str) -> int:
    """Return the number of tokens in text using cl100k_base."""
    return len(ENCODING.encode(text))


def chunk_document(filepath: Path) -> list[dict]:
    """Split a markdown file into overlapping token-counted chunks.

    Each chunk is a dict with content, chunk_index, token_count,
    and metadata (filename, title, position).
    """
    try:
        text = filepath.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.error(f"Document not found: {filepath}")
        raise
    except Exception as e:
        logger.error(f"Failed to read document {filepath}: {e}")
        raise

    title = _extract_title(text)
    filename = filepath.name
    chunk_size = settings.chunk_size
    chunk_overlap = settings.chunk_overlap

    tokens = ENCODING.encode(text)
    total_tokens = len(tokens)

    if total_tokens == 0:
        logger.warning(f"Empty document: {filepath}")
        return []

    chunks: list[dict] = []
    start = 0
    chunk_index = 0

    while start < total_tokens:
        end = min(start + chunk_size, total_tokens)
        chunk_tokens = tokens[start:end]
        content = ENCODING.decode(chunk_tokens)
        token_count = len(chunk_tokens)

        if start == 0:
            position = "first"
        elif end >= total_tokens:
            position = "last"
        else:
            position = "middle"

        chunks.append(
            {
                "content": content,
                "chunk_index": chunk_index,
                "token_count": token_count,
                "metadata": {
                    "filename": filename,
                    "title": title,
                    "position": position,
                },
            }
        )

        chunk_index += 1
        start = end - chunk_overlap

        if end >= total_tokens:
            break

    if len(chunks) == 1:
        chunks[0]["metadata"]["position"] = "first"

    logger.info(
        f"Chunked {filename}: {total_tokens} tokens -> {len(chunks)} chunks"
    )
    return chunks
