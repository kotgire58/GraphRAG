"""FastAPI application — all API endpoints for the GraphRAG PoC."""

import json
import logging
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import httpx
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from agent.agent import run_agent
from agent.models import (
    ChatRequest,
    ChatResponse,
    ComparisonResult,
    NodeWithRelationships,
    PathResult,
)
from agent.prompts import GRAPH_SYSTEM_PROMPT, VECTOR_SYSTEM_PROMPT
from agent.tools import (
    compare_approaches,
    graph_search_tool,
    stream_generate_answer,
    vector_search_tool,
)
from config.settings import settings
from db import neo4j_client, postgres
from retrieval import graph_retriever

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ models

class HealthResponse(BaseModel):
    """Health check response model."""

    postgres: str
    neo4j: str
    llm: str


class GraphStatsResponse(BaseModel):
    """Graph database statistics response model."""

    total_nodes: int
    total_relationships: int
    nodes_by_label: dict[str, int]


# ------------------------------------------------------------------ lifespan

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown lifecycle for the FastAPI application."""
    logger.info("Starting GraphRAG API server...")

    try:
        await postgres.create_pool()
        logger.info("PostgreSQL pool created")
    except Exception as e:
        logger.error(f"PostgreSQL pool creation failed: {e}")

    try:
        await postgres.apply_schema()
        logger.info("PostgreSQL schema applied")
    except Exception as e:
        logger.error(f"PostgreSQL schema application failed: {e}")

    try:
        await neo4j_client.create_driver()
        logger.info("Neo4j driver connected")
    except Exception as e:
        logger.error(f"Neo4j driver creation failed: {e}")

    try:
        await neo4j_client.create_indexes()
        logger.info("Neo4j indexes created")
    except Exception as e:
        logger.error(f"Neo4j index creation failed: {e}")

    logger.info("GraphRAG API startup complete")
    yield

    logger.info("Shutting down GraphRAG API server...")
    await postgres.close_pool()
    await neo4j_client.close_driver()
    logger.info("GraphRAG API shutdown complete")


# ------------------------------------------------------------------ app

app = FastAPI(
    title="GraphRAG PoC API",
    description="Drug Interaction Knowledge Graph — Vector vs Graph RAG",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------ helpers

async def _llm_health_check() -> str:
    """Check LLM availability by hitting the /models endpoint."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{settings.llm_base_url}/models",
                headers={
                    "Authorization": f"Bearer {settings.llm_api_key}"
                },
            )
            if response.status_code == 200:
                return "ok"
            return f"LLM returned status {response.status_code}"
    except httpx.TimeoutException:
        return "LLM health check timed out"
    except Exception as e:
        return f"LLM error: {e}"


async def _ensure_session(pool, session_id: str | None) -> str:
    """Create a session row if it doesn't exist; return the session id."""
    if session_id is None:
        session_id = str(uuid.uuid4())
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO sessions (id) VALUES ($1) "
                "ON CONFLICT (id) DO UPDATE SET last_active = NOW()",
                session_id,
            )
    except Exception as e:
        logger.error(f"Session upsert failed: {e}")
    return session_id


async def _store_message(
    pool, session_id: str, role: str, content: str,
    mode: str | None = None, metadata: dict | None = None,
) -> None:
    """Persist a chat message to PostgreSQL."""
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO messages "
                "(session_id, role, content, mode, metadata) "
                "VALUES ($1, $2, $3, $4, $5)",
                session_id,
                role,
                content,
                mode,
                json.dumps(metadata or {}),
            )
    except Exception as e:
        logger.error(f"Message store failed: {e}")


# ------------------------------------------------------------------ routes

@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Return health status of all backing services."""
    pg_status = await postgres.health_check()
    neo4j_status = await neo4j_client.health_check()
    llm_status = await _llm_health_check()
    return HealthResponse(
        postgres=pg_status, neo4j=neo4j_status, llm=llm_status
    )


@app.get("/graph/stats", response_model=GraphStatsResponse)
async def graph_stats() -> GraphStatsResponse:
    """Return node and relationship counts from the Neo4j graph."""
    nodes_by_label: dict[str, int] = {}
    total_nodes = 0
    total_rels = 0

    try:
        driver = await neo4j_client.get_driver()
        async with driver.session(
            database=settings.neo4j_database
        ) as session:
            result = await session.run(
                "MATCH (n) "
                "RETURN labels(n)[0] AS label, count(n) AS count"
            )
            async for record in result:
                label = record["label"] or "Unknown"
                count = record["count"]
                nodes_by_label[label] = count
                total_nodes += count

            result = await session.run(
                "MATCH ()-[r]->() RETURN count(r) AS total"
            )
            record = await result.single()
            if record:
                total_rels = record["total"]
    except Exception as e:
        logger.error(f"Failed to get graph stats: {e}")

    return GraphStatsResponse(
        total_nodes=total_nodes,
        total_relationships=total_rels,
        nodes_by_label=nodes_by_label,
    )


# ------------------------------------------------------------------ /chat

@app.post("/chat")
async def chat(body: ChatRequest, request: Request):
    """Run a chat query through the selected retrieval mode.

    Returns JSON normally, or SSE stream if Accept: text/event-stream.
    """
    pool = await postgres.get_pool()
    driver = await neo4j_client.get_driver()
    accept = request.headers.get("accept", "")

    if "text/event-stream" in accept:
        return EventSourceResponse(
            _stream_chat(body, pool, driver),
            media_type="text/event-stream",
        )

    session_id = await _ensure_session(pool, body.session_id)
    await _store_message(pool, session_id, "user", body.message, body.mode)

    response = await run_agent(body.message, body.mode, pool, driver)
    response.session_id = session_id

    await _store_message(
        pool, session_id, "assistant", response.answer, body.mode,
        {"tools_used": response.tools_used},
    )
    return response


async def _stream_chat(body: ChatRequest, pool, driver):
    """Async generator that yields SSE events for a streaming chat."""
    session_id = await _ensure_session(pool, body.session_id)
    await _store_message(pool, session_id, "user", body.message, body.mode)

    if body.mode == "vector":
        yield {"data": json.dumps({"type": "tool_start", "tool": "vector_search"})}
        result = await vector_search_tool(body.message, pool)
        yield {"data": json.dumps({
            "type": "tool_end", "tool": "vector_search",
            "result": {"chunks_count": len(result["chunks"]), "sources": result["sources"]},
        })}
        system_prompt = VECTOR_SYSTEM_PROMPT
    elif body.mode == "graph":
        yield {"data": json.dumps({"type": "tool_start", "tool": "graph_search"})}
        result = await graph_search_tool(body.message, driver)
        yield {"data": json.dumps({
            "type": "tool_end", "tool": "graph_search",
            "result": {
                "facts_count": len(result["facts"]),
                "entities_found": result["entities_found"],
                "traversal_paths": result["traversal_paths"][:5],
            },
        })}
        system_prompt = GRAPH_SYSTEM_PROMPT
    else:
        yield {"data": json.dumps({"type": "tool_start", "tool": "graph_search"})}
        result = await graph_search_tool(body.message, driver)
        yield {"data": json.dumps({
            "type": "tool_end", "tool": "graph_search",
            "result": {"facts_count": len(result["facts"])},
        })}
        if len(result["facts"]) <= 5:
            yield {"data": json.dumps({"type": "tool_start", "tool": "vector_search"})}
            v_result = await vector_search_tool(body.message, pool)
            yield {"data": json.dumps({
                "type": "tool_end", "tool": "vector_search",
                "result": {"chunks_count": len(v_result["chunks"])},
            })}
            result["context"] = result["context"] + "\n\n" + v_result["context"]
        system_prompt = GRAPH_SYSTEM_PROMPT

    full_answer = ""
    async for token in stream_generate_answer(
        body.message, result["context"], system_prompt
    ):
        full_answer += token
        yield {"data": json.dumps({"type": "text_delta", "content": token})}

    await _store_message(pool, session_id, "assistant", full_answer, body.mode)
    yield {"data": json.dumps({"type": "done", "session_id": session_id})}


# ------------------------------------------------------------------ /compare

@app.get("/compare")
async def compare(q: str = Query(..., description="The question to compare")):
    """Run the same query through both pipelines and return comparison."""
    pool = await postgres.get_pool()
    driver = await neo4j_client.get_driver()

    try:
        result = await compare_approaches(q, pool, driver)
        return result
    except Exception as e:
        logger.error(f"Compare failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Compare failed: {e}"},
        )


# ------------------------------------------------------------------ /graph

@app.get("/graph/node/{name}")
async def graph_node(name: str):
    """Look up a node by name and return its relationships and neighbors."""
    try:
        driver = await neo4j_client.get_driver()
        async with driver.session(
            database=settings.neo4j_database
        ) as session:
            result = await session.run(
                "MATCH (n) "
                "WHERE toLower(n.name) CONTAINS toLower($name) "
                "WITH n LIMIT 1 "
                "OPTIONAL MATCH (n)-[r]-(neighbor) "
                "RETURN n, "
                "  collect(DISTINCT { "
                "    type: type(r), "
                "    direction: CASE WHEN startNode(r) = n "
                "               THEN 'outgoing' ELSE 'incoming' END, "
                "    neighbor: neighbor.name, "
                "    neighbor_label: labels(neighbor)[0], "
                "    properties: properties(r) "
                "  }) AS relationships",
                name=name,
            )
            record = await result.single()
            if not record:
                return JSONResponse(
                    status_code=404,
                    content={"error": f"Node not found: {name}"},
                )

            node_data = dict(record["n"])
            rels = record["relationships"]
            neighbors = [
                {"name": r["neighbor"], "label": r["neighbor_label"]}
                for r in rels if r.get("neighbor")
            ]

            clean_rels = []
            for r in rels:
                if r.get("type") is None:
                    continue
                props = r.get("properties", {}) or {}
                props.pop("created_at", None)
                props.pop("updated_at", None)
                clean_rels.append({
                    "type": r["type"],
                    "direction": r["direction"],
                    "neighbor": r["neighbor"],
                    "neighbor_label": r["neighbor_label"],
                    "properties": props,
                })

            return NodeWithRelationships(
                node=node_data,
                relationships=clean_rels,
                neighbors=neighbors,
            )
    except Exception as e:
        logger.error(f"Graph node lookup failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Graph node lookup failed: {e}"},
        )


@app.get("/graph/path")
async def graph_path(
    from_entity: str = Query(..., alias="from"),
    to_entity: str = Query(..., alias="to"),
):
    """Find shortest path between two named entities in the graph."""
    try:
        driver = await neo4j_client.get_driver()
        result = await graph_retriever.find_path(
            from_entity, to_entity, driver
        )
        return PathResult(
            from_entity=from_entity,
            to_entity=to_entity,
            path_nodes=result.path_nodes,
            path_relationships=result.path_relationships,
            readable_path=result.readable_path,
            hops=result.hops,
        )
    except Exception as e:
        logger.error(f"Graph path failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Graph path failed: {e}"},
        )


# ------------------------------------------------------------------ sessions

@app.get("/sessions/{session_id}/messages")
async def get_session_messages(session_id: str):
    """Return all messages for a given session."""
    pool = await postgres.get_pool()
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, role, content, mode, metadata, created_at "
                "FROM messages WHERE session_id = $1 "
                "ORDER BY created_at",
                session_id,
            )
            messages = []
            for row in rows:
                meta = row["metadata"]
                if isinstance(meta, str):
                    meta = json.loads(meta)
                messages.append({
                    "id": row["id"],
                    "role": row["role"],
                    "content": row["content"],
                    "mode": row["mode"],
                    "metadata": meta,
                    "created_at": row["created_at"].isoformat()
                    if row["created_at"]
                    else None,
                })
            return {"session_id": session_id, "messages": messages}
    except Exception as e:
        logger.error(f"Failed to fetch messages: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to fetch messages: {e}"},
        )
