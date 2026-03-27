"""
Module: embed_graph.py
Purpose: Pre-embed all Neo4j relationship facts and node 
         descriptions for fast vector search at query time.
Run: python -m ingestion.embed_graph
"""
from __future__ import annotations

import asyncio
import logging
import math
from typing import Any

import httpx
from neo4j import AsyncGraphDatabase

from config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BATCH_SIZE = 99  # OpenRouter max per embedding call


async def get_all_relationships(session) -> list[dict]:
    """Fetch all relationships with node names and properties."""
    result = await session.run("""
        MATCH (a)-[r]->(b)
        WHERE a.name IS NOT NULL AND b.name IS NOT NULL
        RETURN 
            elementId(r) AS rel_id,
            a.name AS from_name,
            labels(a)[0] AS from_label,
            type(r) AS rel_type,
            properties(r) AS rel_props,
            b.name AS to_name,
            labels(b)[0] AS to_label
    """)
    return await result.data()


async def get_all_nodes(session) -> list[dict]:
    """Fetch all nodes with name and label."""
    result = await session.run("""
        MATCH (n)
        WHERE n.name IS NOT NULL
        RETURN 
            elementId(n) AS node_id,
            n.name AS name,
            labels(n)[0] AS label,
            properties(n) AS props
    """)
    return await result.data()


def format_fact_string(row: dict) -> str:
    """Format a relationship row as a readable fact string."""
    skip = {"created_at", "updated_at", "extracted_at",
            "source_doc", "confidence", "fact_embedding"}
    props = row.get("rel_props") or {}
    prop_parts = [
        f"{k}: {v}" for k, v in props.items()
        if k not in skip and v is not None
    ]
    prop_str = (" {" + ", ".join(prop_parts) + "}") if prop_parts else ""
    return (
        f"{row['from_name']} "
        f"-[{row['rel_type']}{prop_str}]-> "
        f"{row['to_name']}"
    )


def format_node_description(row: dict) -> str:
    """Format a node row as a description string for embedding."""
    label = row.get("label") or "Unknown"
    name = row.get("name") or ""
    props = row.get("props") or {}
    skip = {"name", "created_at", "updated_at", "description_embedding"}
    prop_parts = [
        f"{k}: {v}" for k, v in props.items()
        if k not in skip and v is not None
        and not str(v).startswith("[")
    ]
    desc = f"{name} ({label})"
    if prop_parts:
        desc += " — " + ", ".join(prop_parts[:5])
    return desc


async def embed_batch(
    texts: list[str],
    client: httpx.AsyncClient,
) -> list[list[float]]:
    """Embed a batch of texts. Max 99 per call."""
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
    data = response.json()["data"]
    # Sort by index to ensure correct order
    data.sort(key=lambda x: x["index"])
    return [item["embedding"] for item in data]


async def store_relationship_embeddings(
    session,
    rel_ids: list[str],
    embeddings: list[list[float]],
    fact_strings: list[str],
) -> None:
    """Store embeddings on relationships using elementId."""
    for rel_id, embedding, fact in zip(
        rel_ids, embeddings, fact_strings
    ):
        await session.run(
            """
            MATCH ()-[r]->()
            WHERE elementId(r) = $rel_id
            SET r.fact_embedding = $embedding,
                r.fact_string = $fact
            """,
            rel_id=rel_id,
            embedding=embedding,
            fact=fact,
        )


async def store_node_embeddings(
    session,
    node_ids: list[str],
    embeddings: list[list[float]],
    descriptions: list[str],
) -> None:
    """Store embeddings on nodes using elementId."""
    for node_id, embedding, desc in zip(
        node_ids, embeddings, descriptions
    ):
        await session.run(
            """
            MATCH (n)
            WHERE elementId(n) = $node_id
            SET n.description_embedding = $embedding,
                n.description = $desc
            """,
            node_id=node_id,
            embedding=embedding,
            desc=desc,
        )


async def create_vector_indexes(session) -> None:
    """Create Neo4j 5.x vector indexes for relationships and nodes.
    
    Neo4j 5.x syntax for vector indexes on relationships
    requires CREATE VECTOR INDEX.
    Drop existing indexes first to avoid conflicts.
    """
    # Drop existing indexes if they exist
    for index_name in [
        "fact_embeddings_index",
        "node_description_index"
    ]:
        try:
            await session.run(
                f"DROP INDEX {index_name} IF EXISTS"
            )
            logger.info(f"Dropped existing index: {index_name}")
        except Exception as e:
            logger.debug(f"Index {index_name} drop: {e}")

    # Create relationship vector index
    # Neo4j 5.x syntax:
    # CREATE VECTOR INDEX <name> FOR ()-[r:<type>]-()
    # ON r.<property> OPTIONS {indexConfig: {...}}
    # 
    # IMPORTANT: Neo4j Aura requires index on specific 
    # relationship type. Since we have multiple types,
    # we create the index on ALL relationships using
    # a generic approach via a node property instead.
    # 
    # For relationship vector search in Neo4j 5.x Aura,
    # we use a shadow node pattern:
    # Each relationship gets a shadow FactNode with the embedding
    # This is the recommended production pattern for
    # relationship vector search in Neo4j.
    
    logger.info(
        "Creating shadow FactNode index for relationship search..."
    )
    
    # Create FactNode vector index
    await session.run("""
        CREATE VECTOR INDEX fact_embeddings_index IF NOT EXISTS
        FOR (f:FactNode)
        ON f.embedding
        OPTIONS {
            indexConfig: {
                `vector.dimensions`: $dims,
                `vector.similarity_function`: 'cosine'
            }
        }
    """, dims=settings.vector_dimension)

    # Create node description vector index
    await session.run("""
        CREATE VECTOR INDEX node_description_index IF NOT EXISTS
        FOR (n:GraphNode)
        ON n.description_embedding
        OPTIONS {
            indexConfig: {
                `vector.dimensions`: $dims,
                `vector.similarity_function`: 'cosine'
            }
        }
    """, dims=settings.vector_dimension)

    logger.info("Vector indexes created successfully")


async def create_fact_nodes(
    session,
    rows: list[dict],
    embeddings: list[list[float]],
    fact_strings: list[str],
) -> None:
    """Create FactNode shadow nodes for vector search.
    
    Each FactNode stores:
    - embedding: vector for similarity search
    - fact_string: human readable fact
    - from_name, rel_type, to_name: for graph traversal
    - from_label, to_label: node type info
    """
    for row, embedding, fact in zip(rows, embeddings, fact_strings):
        await session.run(
            """
            MERGE (f:FactNode {
                from_name: $from_name,
                rel_type: $rel_type,
                to_name: $to_name
            })
            SET f.embedding = $embedding,
                f.fact_string = $fact,
                f.from_label = $from_label,
                f.to_label = $to_label,
                f.updated_at = datetime()
            """,
            from_name=row["from_name"],
            rel_type=row["rel_type"],
            to_name=row["to_name"],
            from_label=row.get("from_label") or "Unknown",
            to_label=row.get("to_label") or "Unknown",
            embedding=embedding,
            fact=fact,
        )


async def main() -> None:
    """Main embedding pipeline."""
    driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_username, settings.neo4j_password),
    )

    try:
        async with driver.session(
            database=settings.neo4j_database
        ) as session:

            # --- RELATIONSHIPS ---
            logger.info("Fetching all relationships...")
            rel_rows = await get_all_relationships(session)
            logger.info(f"Found {len(rel_rows)} relationships")

            fact_strings = [
                format_fact_string(r) for r in rel_rows
            ]

            logger.info(
                f"Embedding {len(rel_rows)} relationship facts "
                f"in batches of {BATCH_SIZE}..."
            )

            all_rel_embeddings: list[list[float]] = []

            async with httpx.AsyncClient() as client:
                # Embed relationships
                num_batches = math.ceil(
                    len(fact_strings) / BATCH_SIZE
                )
                for i in range(0, len(fact_strings), BATCH_SIZE):
                    batch = fact_strings[i:i + BATCH_SIZE]
                    batch_num = (i // BATCH_SIZE) + 1
                    logger.info(
                        f"Embedding relationship batch "
                        f"{batch_num}/{num_batches}..."
                    )
                    embeddings = await embed_batch(batch, client)
                    all_rel_embeddings.extend(embeddings)

            logger.info(
                f"Storing {len(all_rel_embeddings)} "
                f"relationship embeddings in Neo4j..."
            )

            # Store embeddings on relationships AND
            # create FactNodes for vector index search
            async with driver.session(
                database=settings.neo4j_database
            ) as write_session:
                # Store on relationships directly
                await store_relationship_embeddings(
                    write_session,
                    [r["rel_id"] for r in rel_rows],
                    all_rel_embeddings,
                    fact_strings,
                )

                # Create FactNode shadow nodes
                logger.info("Creating FactNode shadow nodes...")
                for i in range(0, len(rel_rows), 50):
                    batch_rows = rel_rows[i:i + 50]
                    batch_embs = all_rel_embeddings[i:i + 50]
                    batch_facts = fact_strings[i:i + 50]
                    await create_fact_nodes(
                        write_session,
                        batch_rows,
                        batch_embs,
                        batch_facts,
                    )

            # --- NODES ---
            async with driver.session(
                database=settings.neo4j_database
            ) as read_session:
                logger.info("Fetching all nodes...")
                node_rows = await get_all_nodes(read_session)
                logger.info(f"Found {len(node_rows)} nodes")

            node_descriptions = [
                format_node_description(r) for r in node_rows
            ]

            logger.info(
                f"Embedding {len(node_rows)} node descriptions..."
            )

            all_node_embeddings: list[list[float]] = []

            async with httpx.AsyncClient() as client:
                num_batches = math.ceil(
                    len(node_descriptions) / BATCH_SIZE
                )
                for i in range(0, len(node_descriptions), BATCH_SIZE):
                    batch = node_descriptions[i:i + BATCH_SIZE]
                    batch_num = (i // BATCH_SIZE) + 1
                    logger.info(
                        f"Embedding node batch "
                        f"{batch_num}/{num_batches}..."
                    )
                    embeddings = await embed_batch(batch, client)
                    all_node_embeddings.extend(embeddings)

            logger.info("Storing node embeddings...")
            async with driver.session(
                database=settings.neo4j_database
            ) as write_session:
                await store_node_embeddings(
                    write_session,
                    [n["node_id"] for n in node_rows],
                    all_node_embeddings,
                    node_descriptions,
                )

            # --- VECTOR INDEXES ---
            logger.info("Creating vector indexes...")
            async with driver.session(
                database=settings.neo4j_database
            ) as idx_session:
                await create_vector_indexes(idx_session)

            # --- VERIFY ---
            async with driver.session(
                database=settings.neo4j_database
            ) as verify_session:
                result = await verify_session.run("""
                    MATCH (f:FactNode)
                    WHERE f.embedding IS NOT NULL
                    RETURN count(f) AS fact_count
                """)
                record = await result.single()
                fact_count = record["fact_count"]

                result = await verify_session.run("""
                    MATCH (n)
                    WHERE n.description_embedding IS NOT NULL
                    AND NOT n:FactNode
                    RETURN count(n) AS node_count
                """)
                record = await result.single()
                node_count = record["node_count"]

                result = await verify_session.run("""
                    SHOW INDEXES
                    YIELD name, type, state
                    WHERE name IN [
                        'fact_embeddings_index',
                        'node_description_index'
                    ]
                    RETURN name, type, state
                """)
                indexes = await result.data()

            print("\n" + "=" * 50)
            print("GRAPH EMBEDDING COMPLETE")
            print("=" * 50)
            print(f"FactNodes created:        {fact_count}")
            print(f"Nodes with embeddings:    {node_count}")
            print(f"Vector indexes created:   {len(indexes)}")
            for idx in indexes:
                print(
                    f"  - {idx['name']}: "
                    f"{idx['type']} ({idx['state']})"
                )
            print("=" * 50)

    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(main())
