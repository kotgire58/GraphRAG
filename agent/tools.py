"""Async tool functions for the GraphRAG agent."""

import asyncio
import json
import logging

import asyncpg
import httpx
from neo4j import AsyncDriver

from agent.models import ComparisonResult
from agent.prompts import (
    COMPARE_SYSTEM_PROMPT,
    GRAPH_INFO_PROMPT,
    GRAPH_SYSTEM_PROMPT,
    VECTOR_SYSTEM_PROMPT,
)
from config.settings import settings
from retrieval import graph_retriever, vector_retriever

logger = logging.getLogger(__name__)


async def vector_search_tool(
    query: str, pool: asyncpg.Pool
) -> dict:
    """Run vector similarity search and format results for the LLM."""
    results = await vector_retriever.search(query, pool, limit=5)

    chunks = []
    context_parts = []
    sources = []
    for r in results:
        chunk_dict = {
            "chunk_id": r.chunk_id,
            "document_id": r.document_id,
            "content": r.content,
            "filename": r.filename,
            "similarity": round(r.similarity, 4),
        }
        chunks.append(chunk_dict)
        sources.append(r.filename)
        context_parts.append(
            f"[Source: {r.filename} | Similarity: {r.similarity:.3f}]\n"
            f"{r.content}"
        )

    context = "\n\n---\n\n".join(context_parts) if context_parts else ""

    return {
        "chunks": chunks,
        "context": context,
        "sources": list(dict.fromkeys(sources)),
        "retrieval_type": "vector",
    }


def _is_safety_query(query: str) -> bool:
    """Detect if query is a drug safety assessment vs informational."""
    query_lower = query.lower()

    SAFETY_PATTERNS = [
        "safe", "safety", "dangerous", "danger",
        "interact", "interaction", "prescribe",
        "together", "combine", "risk", "contraindic",
        "can i take", "should i take", "is it ok",
    ]

    INFO_PATTERNS = [
        "what does", "what is", "what are",
        "how does", "how do", "list", "which drugs",
        "tell me about", "describe", "explain",
        "metabolize", "metabolized by",
        "what condition", "what medication",
        "show me", "give me",
    ]

    info_hits = sum(1 for p in INFO_PATTERNS if p in query_lower)
    safety_hits = sum(1 for p in SAFETY_PATTERNS if p in query_lower)

    if info_hits >= safety_hits:
        return False
    if safety_hits > 0:
        return True
    return False


def pick_graph_prompt(query: str) -> str:
    """Return the appropriate system prompt for a graph query."""
    if _is_safety_query(query):
        return GRAPH_SYSTEM_PROMPT
    return GRAPH_INFO_PROMPT


async def graph_search_tool(
    query: str, driver: AsyncDriver
) -> dict:
    """Run graph traversal search and format results for the LLM."""
    result = await graph_retriever.search(query, driver)

    context_lines = result.facts[:25]
    context_parts = []
    if context_lines:
        context_parts.append("GRAPH FACTS:\n" + "\n".join(context_lines))
    if result.traversal_paths:
        context_parts.append(
            "TRAVERSAL PATHS:\n"
            + "\n".join(result.traversal_paths[:5])
        )

    context = "\n\n".join(context_parts) if context_parts else ""

    return {
        "facts": result.facts,
        "context": context,
        "traversal_paths": result.traversal_paths,
        "entities_found": result.entities_found,
        "retrieval_type": "graph",
        "seed_facts": result.seed_facts,
        "traversal_explanation": result.traversal_explanation,
        "traversal_graph": result.traversal_graph,
    }


async def generate_answer(
    query: str,
    context: str,
    system_prompt: str,
) -> str:
    """Call the LLM to generate an answer given context and a system prompt."""
    user_content = f"Context:\n{context}\n\nQuestion: {query}"
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{settings.llm_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.llm_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.llm_choice,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content},
                    ],
                    "temperature": 0.2,
                    "max_tokens": 700,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
    except httpx.HTTPStatusError as e:
        logger.error(
            f"LLM HTTP error: {e.response.status_code} "
            f"{e.response.text[:200]}"
        )
        return f"Error generating answer: HTTP {e.response.status_code}"
    except httpx.TimeoutException:
        logger.error("LLM call timed out")
        return "Error generating answer: request timed out"
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        return f"Error generating answer: {e}"


async def stream_generate_answer(
    query: str,
    context: str,
    system_prompt: str,
):
    """Stream LLM answer token-by-token via SSE."""
    user_content = f"Context:\n{context}\n\nQuestion: {query}"
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                f"{settings.llm_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.llm_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.llm_choice,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content},
                    ],
                    "temperature": 0.2,
                    "stream": True,
                },
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:].strip()
                    if payload == "[DONE]":
                        break
                    try:
                        chunk = json.loads(payload)
                        delta = chunk["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
    except Exception as e:
        logger.error(f"Streaming LLM call failed: {e}")
        yield f"\n[Error: {e}]"


async def compare_approaches(
    query: str,
    pool: asyncpg.Pool,
    driver: AsyncDriver,
) -> ComparisonResult:
    """Run both retrievers concurrently, generate answers, compare."""
    vector_task = vector_search_tool(query, pool)
    graph_task = graph_search_tool(query, driver)
    vector_raw, graph_raw = await asyncio.gather(vector_task, graph_task)

    vector_answer_task = generate_answer(
        query, vector_raw["context"], VECTOR_SYSTEM_PROMPT
    )
    graph_answer_task = generate_answer(
        query, graph_raw["context"], pick_graph_prompt(query)
    )
    vector_answer, graph_answer = await asyncio.gather(
        vector_answer_task, graph_answer_task
    )

    key_diff_prompt = (
        f"Vector RAG answer: {vector_answer}\n\n"
        f"Graph RAG answer: {graph_answer}\n\n"
        "Write exactly 2 sentences:\n"
        "Sentence 1: What Vector RAG found and why it may be "
        "incomplete (was it relying on a pre-written case study? "
        "did it miss patient-specific context?)\n"
        "Sentence 2: What Graph RAG found by traversing "
        "relationships that Vector RAG could not (specific "
        "enzyme pathway, specific patient medication chain, "
        "number of hops traversed)"
    )
    key_difference = await generate_answer(
        "Compare the two approaches.",
        key_diff_prompt,
        COMPARE_SYSTEM_PROMPT,
    )

    return ComparisonResult(
        query=query,
        vector_result={
            "answer": vector_answer,
            "chunks": vector_raw["chunks"],
            "sources": vector_raw["sources"],
        },
        graph_result={
            "answer": graph_answer,
            "facts": graph_raw["facts"],
            "traversal_paths": graph_raw["traversal_paths"],
        },
        key_difference=key_difference,
    )
