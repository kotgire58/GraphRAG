"""Pydantic models for the GraphRAG API."""

from typing import Literal

from pydantic import BaseModel


class ChatRequest(BaseModel):
    """Incoming chat request from the client."""

    message: str
    session_id: str | None = None
    mode: Literal["vector", "graph", "agentic", "compare"] = "agentic"


class ChatResponse(BaseModel):
    """Chat response returned to the client."""

    answer: str
    mode: str
    session_id: str
    sources: list[dict]
    traversal_path: list[str] | None = None
    tools_used: list[str]
    traversal_explanation: dict | None = None
    seed_facts: list[dict] | None = None
    traversal_graph: dict | None = None


class ComparisonResult(BaseModel):
    """Side-by-side result from running both retrieval pipelines."""

    query: str
    vector_result: dict
    graph_result: dict
    key_difference: str


class NodeWithRelationships(BaseModel):
    """A single graph node with its relationships and neighbors."""

    node: dict
    relationships: list[dict]
    neighbors: list[dict]


class PathResult(BaseModel):
    """Shortest-path result between two entities."""

    from_entity: str
    to_entity: str
    path_nodes: list[str]
    path_relationships: list[str]
    readable_path: str
    hops: int


class GraphStats(BaseModel):
    """Graph database statistics."""

    total_nodes: int
    total_relationships: int
    nodes_by_label: dict[str, int]
