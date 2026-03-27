"""Agent orchestrator — routes queries to the right retrieval tools."""

import uuid
import logging

import asyncpg
from neo4j import AsyncDriver

from agent.models import ChatResponse
from agent.prompts import VECTOR_SYSTEM_PROMPT
from agent.tools import (
    compare_approaches,
    generate_answer,
    graph_search_tool,
    pick_graph_prompt,
    vector_search_tool,
)

logger = logging.getLogger(__name__)


async def run_agent(
    message: str,
    mode: str,
    pool: asyncpg.Pool,
    driver: AsyncDriver,
) -> ChatResponse:
    """Execute a single query through the appropriate retrieval pipeline."""
    session_id = str(uuid.uuid4())

    if mode == "vector":
        result = await vector_search_tool(message, pool)
        answer = await generate_answer(
            message, result["context"], VECTOR_SYSTEM_PROMPT
        )
        return ChatResponse(
            answer=answer,
            mode=mode,
            session_id=session_id,
            sources=result["chunks"],
            traversal_path=None,
            tools_used=["vector_search"],
        )

    if mode == "graph":
        result = await graph_search_tool(message, driver)
        answer = await generate_answer(
            message, result["context"], pick_graph_prompt(message)
        )
        return ChatResponse(
            answer=answer,
            mode=mode,
            session_id=session_id,
            sources=[{"fact": f} for f in result["facts"]],
            traversal_path=result["traversal_paths"],
            tools_used=["graph_search"],
            traversal_explanation=result.get("traversal_explanation"),
            seed_facts=result.get("seed_facts"),
            traversal_graph=result.get("traversal_graph"),
        )

    if mode == "compare":
        comparison = await compare_approaches(message, pool, driver)
        return ChatResponse(
            answer=comparison.vector_result["answer"],
            mode=mode,
            session_id=session_id,
            sources=[],
            traversal_path=None,
            tools_used=["vector_search", "graph_search"],
        )

    # mode == "agentic": graph first, vector fallback
    graph_result = await graph_search_tool(message, driver)
    graph_facts = graph_result.get("facts", [])
    has_patient_context = any(
        "PRESCRIBED" in f or "HAS_CONDITION" in f
        for f in graph_facts
    )
    has_sufficient_facts = len(graph_facts) > 10
    use_graph = has_patient_context and has_sufficient_facts

    if use_graph:
        answer = await generate_answer(
            message, graph_result["context"], pick_graph_prompt(message)
        )
        return ChatResponse(
            answer=answer,
            mode=mode,
            session_id=session_id,
            sources=[{"fact": f} for f in graph_result["facts"]],
            traversal_path=graph_result["traversal_paths"],
            tools_used=["graph_search"],
            traversal_explanation=graph_result.get("traversal_explanation"),
            seed_facts=graph_result.get("seed_facts"),
            traversal_graph=graph_result.get("traversal_graph"),
        )

    logger.info(
        f"Agentic fallback to vector: "
        f"{len(graph_facts)} facts, "
        f"patient_context={has_patient_context}"
    )
    vector_result = await vector_search_tool(message, pool)
    combined_context = (
        graph_result["context"] + "\n\n" + vector_result["context"]
    )
    answer = await generate_answer(
        message, combined_context, pick_graph_prompt(message)
    )
    return ChatResponse(
        answer=answer,
        mode=mode,
        session_id=session_id,
        sources=vector_result["chunks"],
        traversal_path=graph_result["traversal_paths"],
        tools_used=["graph_search", "vector_search"],
        traversal_graph=graph_result.get("traversal_graph"),
    )
