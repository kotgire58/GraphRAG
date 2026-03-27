"""
Module: graph_retriever.py
Purpose: Production GraphRAG retrieval using pre-embedded 
         FactNodes for fast vector search, BFS expansion
         for context, and explicit traversal path 
         construction for explainability.
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import re
from dataclasses import dataclass, field

import httpx
from neo4j import AsyncDriver

from config.settings import settings
from agent.prompts import ENTITY_EXTRACTION_PROMPT

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

# Relationships to follow during BFS expansion
TRAVERSAL_RELS = [
    "INHIBITS", "INDUCES", "METABOLIZED_BY", "METABOLIZES",
    "CLEARED_BY", "INHIBITS_TRANSPORTER", "CAUSES",
    "INCREASES_RISK_OF", "INTERACTS_WITH", "CONTRAINDICATED_WITH",
    "PRESCRIBED", "HAS_CONDITION", "TREATS", "ALTERNATIVE_TO",
    "DOCUMENTED_IN", "PRECIPITATED_BY", "TREATED_BY",
    "ADMITTED_TO", "MANUFACTURED_BY",
]

# Always include these in final context regardless of score
MANDATORY_REL_TYPES = {
    "HAS_CONDITION", "PRESCRIBED", "CLEARED_BY",
    "INHIBITS_TRANSPORTER", "CAUSES", "CONTRAINDICATED_WITH",
    "INCREASES_RISK_OF",
}

# Vector search score threshold — facts below this are noise
SIMILARITY_THRESHOLD = 0.70

# How many seed facts to retrieve via vector search
VECTOR_SEED_COUNT = 40

# BFS hops from seed nodes
BFS_HOPS = 2

# Max facts in final LLM context
MAX_CONTEXT_FACTS = 35


DRUG_SYNONYMS: dict[str, str] = {
    'prinivil': 'Lisinopril',
    'zestril': 'Lisinopril',
    'glucophage': 'Metformin',
    'fortamet': 'Metformin',
    'glumetza': 'Metformin',
    'lipitor': 'Atorvastatin',
    'norvasc': 'Amlodipine',
    'zocor': 'Simvastatin',
    'coumadin': 'Warfarin',
    'jantoven': 'Warfarin',
    'diflucan': 'Fluconazole',
    'plavix': 'Clopidogrel',
    'prilosec': 'Omeprazole',
    'cordarone': 'Amiodarone',
    'pacerone': 'Amiodarone',
    'lanoxin': 'Digoxin',
    'aldactone': 'Spironolactone',
    'prograf': 'Tacrolimus',
    'sandimmune': 'Cyclosporine',
    'neoral': 'Cyclosporine',
    'biaxin': 'Clarithromycin',
    'nizoral': 'Ketoconazole',
    'rifadin': 'Rifampin',
    'dilantin': 'Phenytoin',
    'viagra': 'Sildenafil',
    'revatio': 'Sildenafil',
    'lantus': 'Insulin Glargine',
    'basaglar': 'Insulin Glargine',
}


def _extract_patient_id(text: str) -> str | None:
    """Extract and normalize patient id from user text (e.g. PT-002, pt002, patient 002)."""
    match = re.search(r"\bpt[\s\-_]?(\d{1,3})\b", text, flags=re.IGNORECASE)
    if match:
        return f"PT-{int(match.group(1)):03d}"

    match = re.search(
        r"\bpatient(?:\s+id)?\s*[:#-]?\s*(\d{1,3})\b",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        return f"PT-{int(match.group(1)):03d}"

    return None


def _is_patient_demographics_query(query_lower: str) -> bool:
    """True when query asks for direct patient demographics."""
    demographic_terms = (
        "age",
        "sex",
        "gender",
        "weight",
        "height",
        "demographic",
    )
    return (
        any(term in query_lower for term in demographic_terms)
        and ("patient" in query_lower or "pt" in query_lower)
    )


def _resolve_drug_synonyms(entities: list[str]) -> list[str]:
    """Replace brand names with generic names.

    Also keeps the original name in case it exists
    directly in the graph.
    """
    resolved = []
    for entity in entities:
        generic = DRUG_SYNONYMS.get(entity.lower())
        if generic:
            logger.info(
                f"Resolved brand name '{entity}' "
                f"to generic '{generic}'"
            )
            resolved.append(generic)
            resolved.append(entity)
        else:
            resolved.append(entity)
    seen: set[str] = set()
    unique: list[str] = []
    for e in resolved:
        if e not in seen:
            seen.add(e)
            unique.append(e)
    return unique


@dataclass(frozen=True)
class AggregateQueryResult:
    """Structured result when aggregate Cypher shortcut runs."""

    text: str
    traversal_graph: dict


def _build_aggregate_patients_traversal_graph(rows: list[dict]) -> dict:
    """Build Traversal Graph nodes/links from patient list Cypher rows."""
    node_map: dict[str, dict[str, str]] = {}
    links: list[dict[str, str]] = []
    seen_link: set[tuple[str, str, str]] = set()

    def add_node(node_id: str, label: str) -> None:
        if node_id not in node_map:
            node_map[node_id] = {
                "id": node_id,
                "name": node_id,
                "label": label,
            }

    for row in rows:
        pid = row.get("patient_id") or "Unknown"
        add_node(pid, "Patient")
        for med in row.get("medications") or []:
            if not med:
                continue
            add_node(med, "Drug")
            key = (pid, "PRESCRIBED", med)
            if key not in seen_link:
                seen_link.add(key)
                links.append(
                    {
                        "source": pid,
                        "target": med,
                        "type": "PRESCRIBED",
                    }
                )
        for cond in row.get("conditions") or []:
            if not cond:
                continue
            add_node(cond, "Condition")
            key = (pid, "HAS_CONDITION", cond)
            if key not in seen_link:
                seen_link.add(key)
                links.append(
                    {
                        "source": pid,
                        "target": cond,
                        "type": "HAS_CONDITION",
                    }
                )

    nodes = sorted(node_map.values(), key=lambda n: n["id"])
    return {"nodes": nodes, "links": links}


def _build_aggregate_drugs_traversal_graph(rows: list[dict]) -> dict:
    """One Drug node per row for aggregate drug listing."""
    node_map: dict[str, dict[str, str]] = {}
    for row in rows:
        name = row.get("name")
        if not name:
            continue
        if name not in node_map:
            node_map[name] = {
                "id": name,
                "name": name,
                "label": "Drug",
            }
    nodes = sorted(node_map.values(), key=lambda n: n["id"])
    return {"nodes": nodes, "links": []}


def _build_aggregate_conditions_traversal_graph(rows: list[dict]) -> dict:
    """One Condition node per row for aggregate condition listing."""
    node_map: dict[str, dict[str, str]] = {}
    for row in rows:
        name = row.get("name")
        if not name:
            continue
        if name not in node_map:
            node_map[name] = {
                "id": name,
                "name": name,
                "label": "Condition",
            }
    nodes = sorted(node_map.values(), key=lambda n: n["id"])
    return {"nodes": nodes, "links": []}


async def run_aggregate_query(
    query: str,
    driver: AsyncDriver,
) -> AggregateQueryResult | None:
    """Detect and execute aggregate Cypher queries directly.

    For queries asking for lists of all entities
    (all patients, all drugs, all conditions etc.)
    vector search fails because it can't retrieve
    all matching nodes equally.

    Returns formatted text plus a traversal graph for the UI, or None if not
    an aggregate query.
    """
    query_lower = query.lower()
    patient_id = _extract_patient_id(query)

    is_list_all_patients = any(p in query_lower for p in [
        'all patients', 'list patients', 'how many patients',
        'every patient', 'each patient', 'list out',
        'all pt-', 'patients and their',
    ])
    is_patient_demographics = (
        patient_id is not None
        and _is_patient_demographics_query(query_lower)
    )

    is_list_all_drugs = any(p in query_lower for p in [
        'all drugs', 'list drugs', 'all medications',
        'list medications', 'every drug', 'each drug',
    ])

    is_list_all_conditions = any(p in query_lower for p in [
        'all conditions', 'list conditions',
        'every condition', 'each condition',
    ])

    if not any([
        is_patient_demographics,
        is_list_all_patients,
        is_list_all_drugs,
        is_list_all_conditions,
    ]):
        return None

    logger.info(
        f"Aggregate query detected: "
        f"patient_demographics={is_patient_demographics}, "
        f"patients={is_list_all_patients}, "
        f"drugs={is_list_all_drugs}, "
        f"conditions={is_list_all_conditions}"
    )

    try:
        async with driver.session(
            database=settings.neo4j_database
        ) as session:

            if is_patient_demographics and patient_id:
                result = await session.run(
                    """
                    MATCH (p:Patient {patient_id: $pid})
                    RETURN p.patient_id AS patient_id,
                           p.age AS age,
                           p.sex AS sex,
                           p.weight_kg AS weight_kg,
                           p.height_cm AS height_cm
                    LIMIT 1
                    """,
                    pid=patient_id,
                )
                row = await result.single()
                if not row:
                    return AggregateQueryResult(
                        text=f"No patient found for ID {patient_id}.",
                        traversal_graph={"nodes": [], "links": []},
                    )

                pid = row.get("patient_id") or patient_id
                age = row.get("age")
                sex = row.get("sex")
                weight = row.get("weight_kg")
                height = row.get("height_cm")

                fields = []
                if age is not None:
                    fields.append(f"age {age}")
                if sex:
                    fields.append(f"sex {sex}")
                if weight is not None:
                    fields.append(f"weight {weight} kg")
                if height is not None:
                    fields.append(f"height {height} cm")

                details = ", ".join(fields) if fields else "no demographic fields recorded"
                return AggregateQueryResult(
                    text=f"{pid}: {details}.",
                    traversal_graph={
                        "nodes": [{"id": pid, "name": pid, "label": "Patient"}],
                        "links": [],
                    },
                )

            if is_list_all_patients:
                result = await session.run("""
                    MATCH (p:Patient)
                    OPTIONAL MATCH (p)-[:PRESCRIBED]->(d:Drug)
                    OPTIONAL MATCH (p)-[:HAS_CONDITION]->(c:Condition)
                    RETURN p.patient_id AS patient_id,
                           p.age AS age,
                           p.sex AS sex,
                           collect(DISTINCT d.name) AS medications,
                           collect(DISTINCT c.name) AS conditions
                    ORDER BY p.patient_id
                """)
                rows = await result.data()

                if not rows:
                    return AggregateQueryResult(
                        text="No patients found in the graph.",
                        traversal_graph={"nodes": [], "links": []},
                    )

                lines = [
                    f"There are {len(rows)} patients "
                    f"in the graph:\n"
                ]
                for row in rows:
                    pid = row['patient_id'] or 'Unknown'
                    age = row.get('age', '?')
                    sex = row.get('sex', '?')
                    meds = row['medications'] or []
                    conds = row['conditions'] or []

                    lines.append(f"**{pid}** ({age}y, {sex})")
                    if meds:
                        lines.append(
                            "  Medications: "
                            + ", ".join(sorted(meds))
                        )
                    if conds:
                        lines.append(
                            "  Conditions: "
                            + ", ".join(sorted(conds))
                        )
                    lines.append("")

                patient_graph = _build_aggregate_patients_traversal_graph(
                    rows
                )
                return AggregateQueryResult(
                    text="\n".join(lines),
                    traversal_graph=patient_graph,
                )

            elif is_list_all_drugs:
                result = await session.run("""
                    MATCH (d:Drug)
                    RETURN d.name AS name,
                           d.drug_class AS drug_class
                    ORDER BY d.name
                """)
                rows = await result.data()
                lines = [f"{len(rows)} drugs in the graph:\n"]
                for row in rows:
                    drug_class = row.get('drug_class', '')
                    if drug_class:
                        lines.append(
                            f"- {row['name']} ({drug_class})"
                        )
                    else:
                        lines.append(f"- {row['name']}")
                drug_graph = _build_aggregate_drugs_traversal_graph(rows)
                return AggregateQueryResult(
                    text="\n".join(lines),
                    traversal_graph=drug_graph,
                )

            elif is_list_all_conditions:
                result = await session.run("""
                    MATCH (c:Condition)
                    RETURN c.name AS name
                    ORDER BY c.name
                """)
                rows = await result.data()
                lines = [
                    f"{len(rows)} conditions in the graph:\n"
                ]
                for row in rows:
                    lines.append(f"- {row['name']}")
                cond_graph = _build_aggregate_conditions_traversal_graph(
                    rows
                )
                return AggregateQueryResult(
                    text="\n".join(lines),
                    traversal_graph=cond_graph,
                )

    except Exception as e:
        logger.error(f"Aggregate query failed: {e}")
        return None

    return None


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class SeedFact:
    """A fact retrieved via vector similarity search."""
    fact_string: str
    from_name: str
    rel_type: str
    to_name: str
    from_label: str
    to_label: str
    score: float


@dataclass
class GraphResult:
    facts: list[str] = field(default_factory=list)
    nodes: list[str] = field(default_factory=list)
    traversal_paths: list[str] = field(default_factory=list)
    entities_found: list[str] = field(default_factory=list)
    query: str = ""
    seed_facts: list[dict] = field(default_factory=list)
    traversal_explanation: dict = field(default_factory=dict)
    traversal_graph: dict = field(default_factory=dict)


@dataclass
class PathResult:
    path_nodes: list[str] = field(default_factory=list)
    path_relationships: list[str] = field(default_factory=list)
    readable_path: str = ""
    hops: int = 0


# =============================================================================
# STAGE 1 — ENTITY EXTRACTION
# =============================================================================

async def extract_entities(query: str) -> list[str]:
    """Extract named medical entities from query using LLM."""
    prompt = ENTITY_EXTRACTION_PROMPT.replace("{query}", query)
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.llm_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.llm_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.ingestion_llm_choice,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.0,
                },
            )
            response.raise_for_status()
            raw = response.json()["choices"][0]["message"]["content"].strip()
            if "```" in raw:
                raw = raw.split("```")[1].strip()
                if raw.startswith("json"):
                    raw = raw[4:].strip()
            entities = json.loads(raw)
            if isinstance(entities, list):
                logger.info(f"Extracted entities: {entities}")
                return [str(e) for e in entities]
            return []
    except json.JSONDecodeError:
        logger.warning(f"Entity extraction parse failed: {query[:80]}")
        return []
    except Exception as e:
        logger.error(f"Entity extraction failed: {e}")
        return []


# =============================================================================
# STAGE 2 — EMBED QUERY
# =============================================================================

async def embed_query(query: str) -> list[float] | None:
    """Embed the query string for vector similarity search."""
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
            return response.json()["data"][0]["embedding"]
    except Exception as e:
        logger.error(f"Query embedding failed: {e}")
        return None


# =============================================================================
# STAGE 3 — VECTOR SEARCH ON FACTNODES
# =============================================================================

async def vector_search_facts(
    query_embedding: list[float],
    session,
    top_k: int = VECTOR_SEED_COUNT,
) -> list[SeedFact]:
    """Search pre-embedded FactNodes by vector similarity.
    
    Uses Neo4j native vector index for instant retrieval.
    No live traversal or scoring needed.
    """
    try:
        result = await session.run(
            """
            CALL db.index.vector.queryNodes(
                'fact_embeddings_index',
                $top_k,
                $embedding
            )
            YIELD node AS f, score
            WHERE score >= $threshold
            RETURN f.fact_string AS fact_string,
                   f.from_name AS from_name,
                   f.rel_type AS rel_type,
                   f.to_name AS to_name,
                   f.from_label AS from_label,
                   f.to_label AS to_label,
                   score
            ORDER BY score DESC
            """,
            embedding=query_embedding,
            top_k=top_k,
            threshold=SIMILARITY_THRESHOLD,
        )
        rows = await result.data()
        seeds = [
            SeedFact(
                fact_string=r["fact_string"],
                from_name=r["from_name"],
                rel_type=r["rel_type"],
                to_name=r["to_name"],
                from_label=r.get("from_label") or "Unknown",
                to_label=r.get("to_label") or "Unknown",
                score=r["score"],
            )
            for r in rows
        ]
        logger.info(
            f"Vector search returned {len(seeds)} seed facts "
            f"(threshold={SIMILARITY_THRESHOLD})"
        )
        return seeds
    except Exception as e:
        logger.error(f"Vector search failed: {e}")
        return []


# =============================================================================
# STAGE 4 — BFS EXPANSION FROM SEED NODES
# =============================================================================

async def bfs_expand(
    seed_node_names: list[str],
    session,
    hops: int = BFS_HOPS,
) -> list[tuple[str, str, str]]:
    """BFS expansion from seed nodes.
    
    Returns list of (from_name, rel_type, to_name) tuples.
    Guarantees all hop-1 facts before hop-2 facts.
    Uses batch node expansion for efficiency.
    """
    all_edges: list[tuple[str, str, str]] = []
    visited: set[str] = set(seed_node_names)
    frontier: list[str] = seed_node_names

    for hop in range(hops):
        if not frontier:
            break

        # Batch expand all frontier nodes in one query
        try:
            # Outbound
            result = await session.run(
                """
                MATCH (n)-[r]->(m)
                WHERE n.name IN $frontier
                  AND type(r) IN $rel_types
                  AND m.name IS NOT NULL
                RETURN n.name AS from_name,
                       type(r) AS rel_type,
                       m.name AS to_name
                LIMIT 300
                """,
                frontier=frontier,
                rel_types=TRAVERSAL_RELS,
            )
            outbound = await result.data()

            # Inbound
            result = await session.run(
                """
                MATCH (m)-[r]->(n)
                WHERE n.name IN $frontier
                  AND type(r) IN $rel_types
                  AND m.name IS NOT NULL
                RETURN m.name AS from_name,
                       type(r) AS rel_type,
                       n.name AS to_name
                LIMIT 300
                """,
                frontier=frontier,
                rel_types=TRAVERSAL_RELS,
            )
            inbound = await result.data()

        except Exception as e:
            logger.error(f"BFS hop {hop + 1} failed: {e}")
            break

        next_frontier: list[str] = []

        for row in outbound + inbound:
            from_name = row.get("from_name") or ""
            to_name = row.get("to_name") or ""
            rel_type = row.get("rel_type") or ""
            if not from_name or not to_name:
                continue
            all_edges.append((from_name, rel_type, to_name))
            neighbor = (
                to_name if from_name in set(frontier)
                else from_name
            )
            if neighbor not in visited:
                visited.add(neighbor)
                next_frontier.append(neighbor)

        logger.debug(
            f"BFS hop {hop + 1}: {len(all_edges)} edges, "
            f"{len(next_frontier)} new nodes"
        )
        frontier = next_frontier

    return all_edges


# =============================================================================
# STAGE 5 — MANDATORY FACTS FROM RESOLVED ENTITIES
# =============================================================================

async def get_mandatory_facts(
    entity_names: list[str],
    session,
) -> list[str]:
    """Get all mandatory relationship facts for query entities.
    
    These are always included regardless of vector score.
    Fetches directly from Neo4j, not from FactNodes.
    """
    try:
        result = await session.run(
            """
            MATCH (n)-[r]->(m)
            WHERE (n.name IN $names OR m.name IN $names
                   OR n.patient_id IN $names)
              AND type(r) IN $mandatory_rels
              AND m.name IS NOT NULL
            RETURN n.name AS from_name,
                   type(r) AS rel_type,
                   properties(r) AS props,
                   m.name AS to_name
            """,
            names=entity_names,
            mandatory_rels=list(MANDATORY_REL_TYPES),
        )
        rows = await result.data()
        facts = []
        skip = {"created_at", "updated_at", "extracted_at",
                "source_doc", "confidence", "fact_embedding",
                "source", "fact_string"}
        for row in rows:
            props = row.get("props") or {}
            prop_parts = [
                f"{k}: {v}" for k, v in props.items()
                if k not in skip and v is not None
            ]
            prop_str = (
                " {" + ", ".join(prop_parts) + "}"
                if prop_parts else ""
            )
            fact = (
                f"{row['from_name']} "
                f"-[{row['rel_type']}{prop_str}]-> "
                f"{row['to_name']}"
            )
            facts.append(fact)
        logger.info(
            f"Mandatory facts for {entity_names}: {len(facts)}"
        )
        return facts
    except Exception as e:
        logger.error(f"Mandatory facts query failed: {e}")
        return []


# =============================================================================
# STAGE 6 — CONTEXT ASSEMBLY
# =============================================================================

def assemble_context(
    seed_facts: list[SeedFact],
    bfs_edges: list[tuple[str, str, str]],
    mandatory_facts: list[str],
    max_facts: int = MAX_CONTEXT_FACTS,
) -> tuple[list[str], list[str]]:
    """Assemble final context from all sources.
    
    Priority order:
    1. Mandatory facts (PRESCRIBED, HAS_CONDITION, etc.) — always included
    2. High-score seed facts (vector similarity >= threshold)
    3. BFS expansion facts (contextual neighbors)
    
    Returns (context_lines, traversal_paths)
    """
    seen: set[str] = set()
    
    # Start with mandatory facts
    selected: list[str] = []
    for fact in mandatory_facts:
        if fact not in seen:
            seen.add(fact)
            selected.append(fact)
    
    # Add high-score seed facts
    # Filter out MANUFACTURED_BY noise from top results
    NOISE_REL_TYPES = {"MANUFACTURED_BY", "SUPPLIES", 
                       "WORKS_AT", "ADMITTED_TO"}
    
    for seed in seed_facts:
        if len(selected) >= max_facts:
            break
        if seed.rel_type in NOISE_REL_TYPES:
            continue
        fact = seed.fact_string
        if fact not in seen:
            seen.add(fact)
            selected.append(fact)
    
    # Fill remaining slots with BFS expansion facts
    for from_name, rel_type, to_name in bfs_edges:
        if len(selected) >= max_facts:
            break
        if rel_type in NOISE_REL_TYPES:
            continue
        fact = f"{from_name} -[{rel_type}]-> {to_name}"
        if fact not in seen:
            seen.add(fact)
            selected.append(fact)
    
    # Organize into structured sections for LLM
    patient_facts = [
        f for f in selected
        if any(rel in f for rel in [
            "PRESCRIBED", "HAS_CONDITION",
            "TREATED_BY", "ADMITTED_TO"
        ])
    ]
    enzyme_facts = [
        f for f in selected
        if any(rel in f for rel in [
            "INHIBITS", "INDUCES", "METABOLIZED_BY",
            "METABOLIZES", "CLEARED_BY", "INHIBITS_TRANSPORTER"
        ])
    ]
    safety_facts = [
        f for f in selected
        if any(rel in f for rel in [
            "CONTRAINDICATED_WITH", "CAUSES",
            "INCREASES_RISK_OF", "INTERACTS_WITH"
        ])
    ]
    other_facts = [
        f for f in selected
        if f not in patient_facts
        and f not in enzyme_facts
        and f not in safety_facts
    ]
    
    context_lines: list[str] = []
    if patient_facts:
        context_lines.append("=== PATIENT CONTEXT ===")
        context_lines.extend(patient_facts)
    if enzyme_facts:
        context_lines.append("=== DRUG-ENZYME PATHWAYS ===")
        context_lines.extend(enzyme_facts)
    if safety_facts:
        context_lines.append("=== SAFETY ALERTS ===")
        context_lines.extend(safety_facts)
    if other_facts:
        context_lines.append("=== ADDITIONAL CONTEXT ===")
        context_lines.extend(other_facts)
    
    # Build traversal paths from seed facts
    traversal_paths = _build_traversal_paths(
        seed_facts, bfs_edges
    )
    
    return context_lines, traversal_paths


def _build_traversal_paths(
    seed_facts: list[SeedFact],
    bfs_edges: list[tuple[str, str, str]],
) -> list[str]:
    """Build human-readable traversal chains.
    
    Finds chains where end of one fact is start of next.
    Example: A->B, B->C becomes "A -[R1]-> B -[R2]-> C"
    """
    # Build adjacency from all facts
    adj: dict[str, list[tuple[str, str]]] = {}
    
    for seed in seed_facts:
        adj.setdefault(seed.from_name, []).append(
            (seed.rel_type, seed.to_name)
        )
    
    for from_name, rel_type, to_name in bfs_edges:
        adj.setdefault(from_name, []).append(
            (rel_type, to_name)
        )
    
    paths: list[str] = []
    
    # Start paths from seed fact nodes
    seed_starts = list({s.from_name for s in seed_facts})
    
    def dfs(
        node: str,
        path_parts: list[str],
        visited: set[str],
        depth: int,
    ) -> None:
        if depth > 4:
            return
        if depth >= 2:
            paths.append(" ".join(path_parts))
        for rel_type, neighbor in adj.get(node, []):
            if neighbor not in visited:
                visited.add(neighbor)
                path_parts.extend(
                    [f"-[{rel_type}]->", neighbor]
                )
                dfs(neighbor, path_parts, visited, depth + 1)
                path_parts.pop()
                path_parts.pop()
                visited.discard(neighbor)
    
    for start in seed_starts[:5]:  # limit starting points
        dfs(start, [start], {start}, 0)
    
    # Deduplicate and sort by length (longer = more informative)
    unique_paths = list(dict.fromkeys(paths))
    unique_paths.sort(key=len, reverse=True)
    return unique_paths[:15]


# =============================================================================
# STAGE 7 — TRAVERSAL EXPLANATION & VIZ SUBGRAPH
# =============================================================================

LABEL_FROM_REL: dict[str, tuple[str, str]] = {
    "PRESCRIBED": ("Patient", "Drug"),
    "HAS_CONDITION": ("Patient", "Condition"),
    "INHIBITS": ("Drug", "Enzyme"),
    "INDUCES": ("Drug", "Enzyme"),
    "METABOLIZED_BY": ("Drug", "Enzyme"),
    "METABOLIZES": ("Enzyme", "Drug"),
    "CLEARED_BY": ("Drug", "Transporter"),
    "INHIBITS_TRANSPORTER": ("Drug", "Transporter"),
    "TREATS": ("Drug", "Condition"),
    "CONTRAINDICATED_WITH": ("Drug", "Drug"),
    "INTERACTS_WITH": ("Drug", "Drug"),
    "INCREASES_RISK_OF": ("Drug", "Condition"),
    "CAUSES": ("Drug", "Condition"),
    "ALTERNATIVE_TO": ("Drug", "Drug"),
    "TREATED_BY": ("Patient", "Physician"),
    "ADMITTED_TO": ("Patient", "Hospital"),
    "MANUFACTURED_BY": ("Drug", "Manufacturer"),
    "DOCUMENTED_IN": ("ClinicalCase", "Patient"),
    "COVERS": ("Protocol", "Drug"),
    "REQUIRES": ("Protocol", "Protocol"),
}


def _pick_critical_path(
    entities: list[str],
    traversal_paths: list[str],
) -> str:
    """Prefer paths that mention more query entities (e.g. patient + drug)."""
    if not traversal_paths:
        return ""
    entity_lower = [e.lower() for e in entities if e]
    best_path = traversal_paths[0]
    best_score = -1
    for path in traversal_paths:
        pl = path.lower()
        score = sum(1 for e in entity_lower if e in pl)
        if score > best_score:
            best_score = score
            best_path = path
        elif score == best_score and len(path) > len(best_path):
            best_path = path
    return best_path


def _parse_chain_edges(path: str) -> list[tuple[str, str, str]]:
    """Parse 'A -[R1]-> B -[R2]-> C' into (from, rel, to) triples."""
    edges: list[tuple[str, str, str]] = []
    s = path.strip()
    while True:
        sep = " -["
        i = s.find(sep)
        if i == -1:
            break
        from_n = s[:i].strip()
        j = s.find("]", i + len(sep))
        if j == -1:
            break
        rel_raw = s[i + len(sep) : j]
        rel = rel_raw.split("{")[0].strip()
        arrow = "]-> "
        k = s.find(arrow, j)
        if k == -1:
            break
        rest = s[k + len(arrow) :]
        next_sep = rest.find(" -[")
        if next_sep == -1:
            to_n = rest.strip()
            if from_n and rel and to_n:
                edges.append((from_n, rel, to_n))
            break
        to_n = rest[:next_sep].strip()
        if from_n and rel and to_n:
            edges.append((from_n, rel, to_n))
        s = to_n + rest[next_sep:]
    return edges


def _build_traversal_graph(
    seed_facts: list[SeedFact],
    bfs_edges: list[tuple[str, str, str]],
    mandatory_facts: list[str],
    context_lines: list[str],
    entities: list[str] | None,
    traversal_paths: list[str] | None,
) -> dict:
    """Build {nodes, links} for the Traversal Graph UI from context facts."""
    node_labels: dict[str, str] = {}
    edges: list[tuple[str, str, str]] = []

    for sf in seed_facts:
        node_labels[sf.from_name] = sf.from_label
        node_labels[sf.to_name] = sf.to_label

    context_facts: set[str] = set()
    for line in context_lines:
        if "-[" in line and "]->" in line:
            context_facts.add(line.strip())

    def _infer_label(name: str, rel_type: str, position: str) -> str:
        if name in node_labels:
            return node_labels[name]
        if name.startswith("PT-"):
            return "Patient"
        if name.startswith("CYP") or name.startswith("UGT"):
            return "Enzyme"
        if name in ("P-glycoprotein", "OCT2", "MATE1", "MATE2"):
            return "Transporter"
        pair = LABEL_FROM_REL.get(rel_type)
        if pair:
            return pair[0] if position == "from" else pair[1]
        return "Drug"

    def _parse_fact_line(line: str) -> tuple[str, str, str] | None:
        try:
            left, rest = line.split(" -[", 1)
            rel_part, right = rest.split("]-> ", 1)
            rel_type = rel_part.split("{")[0].strip()
            from_name = left.strip()
            to_name = right.strip()
            if from_name and rel_type and to_name:
                return (from_name, rel_type, to_name)
        except (ValueError, IndexError):
            pass
        return None

    for mf in mandatory_facts:
        parsed = _parse_fact_line(mf)
        if parsed:
            from_n, rel, to_n = parsed
            fact_key = f"{from_n} -[{rel}]-> {to_n}"
            if fact_key in context_facts or any(
                from_n in cf and to_n in cf for cf in context_facts
            ):
                edges.append(parsed)
                if from_n not in node_labels:
                    node_labels[from_n] = _infer_label(
                        from_n, rel, "from"
                    )
                if to_n not in node_labels:
                    node_labels[to_n] = _infer_label(
                        to_n, rel, "to"
                    )

    for sf in seed_facts:
        fact_key = f"{sf.from_name} -[{sf.rel_type}]-> {sf.to_name}"
        if fact_key in context_facts:
            edges.append((sf.from_name, sf.rel_type, sf.to_name))

    for from_n, rel, to_n in bfs_edges:
        fact_key = f"{from_n} -[{rel}]-> {to_n}"
        if fact_key in context_facts:
            edges.append((from_n, rel, to_n))
            if from_n not in node_labels:
                node_labels[from_n] = _infer_label(
                    from_n, rel, "from"
                )
            if to_n not in node_labels:
                node_labels[to_n] = _infer_label(
                    to_n, rel, "to"
                )

    if entities and traversal_paths:
        crit = _pick_critical_path(entities, traversal_paths)
        for from_n, rel, to_n in _parse_chain_edges(crit):
            edges.append((from_n, rel, to_n))
            if from_n not in node_labels:
                node_labels[from_n] = _infer_label(
                    from_n, rel, "from"
                )
            if to_n not in node_labels:
                node_labels[to_n] = _infer_label(
                    to_n, rel, "to"
                )

    seen_edges: set[str] = set()
    unique_edges: list[tuple[str, str, str]] = []
    for from_n, rel, to_n in edges:
        key = f"{from_n}|{rel}|{to_n}"
        if key not in seen_edges:
            seen_edges.add(key)
            unique_edges.append((from_n, rel, to_n))

    used_names: set[str] = set()
    for from_n, _, to_n in unique_edges:
        used_names.add(from_n)
        used_names.add(to_n)

    nodes = [
        {
            "id": name,
            "name": name,
            "label": node_labels.get(name, "Drug"),
        }
        for name in sorted(used_names)
    ]
    links = [
        {"source": from_n, "target": to_n, "type": rel}
        for from_n, rel, to_n in unique_edges
    ]

    return {"nodes": nodes, "links": links}


def build_traversal_explanation(
    query: str,
    entities: list[str],
    seed_facts: list[SeedFact],
    mandatory_facts: list[str],
    final_facts: list[str],
    traversal_paths: list[str],
) -> dict:
    """Build the traversal explanation for UI display.
    
    Shows exactly how the system found its answer:
    - Which entities were identified
    - Which seed facts were found via vector search (with scores)
    - Which mandatory facts were always included
    - The critical traversal path
    """
    critical_path = _pick_critical_path(entities, traversal_paths)
    
    return {
        "query": query,
        "entities_identified": entities,
        "seed_facts_via_vector_search": [
            {
                "fact": s.fact_string,
                "similarity_score": round(s.score, 4),
                "why_relevant": (
                    f"Score {s.score:.2f} — semantically "
                    f"similar to query"
                ),
            }
            for s in seed_facts[:10]
        ],
        "mandatory_facts_always_included": mandatory_facts[:10],
        "critical_path": critical_path,
        "total_facts_in_context": len(final_facts),
        "how_it_works": (
            "1. Query embedded → vector search on pre-embedded "
            "facts → top similar facts retrieved instantly. "
            "2. BFS expansion 2 hops from relevant nodes. "
            "3. Mandatory patient/condition facts always included. "
            "4. Structured context assembled and sent to LLM."
        ),
    }


# =============================================================================
# MAIN SEARCH FUNCTION
# =============================================================================

async def search(query: str, driver: AsyncDriver) -> GraphResult:
    """Production GraphRAG search pipeline.
    
    Stage 0: Aggregate query shortcut (direct Cypher)
    Stage 1: Extract entities from query (LLM)
    Stage 1b: Resolve brand names to generic names
    Stage 2: Embed query (single API call)
    Stage 3: Vector search on FactNodes (instant, pre-embedded)
    Stage 4: BFS expansion 2 hops from seed nodes
    Stage 5: Get mandatory facts for query entities
    Stage 6: Assemble structured context
    Stage 7: Build traversal explanation for UI
    """
    # Stage 0 — aggregate queries bypass vector search
    aggregate_result = await run_aggregate_query(query, driver)
    if aggregate_result is not None:
        logger.info("Aggregate query handled via direct Cypher")
        tg = aggregate_result.traversal_graph
        logger.info(
            f"Aggregate traversal graph: "
            f"{len(tg.get('nodes', []))} nodes / "
            f"{len(tg.get('links', []))} edges"
        )
        return GraphResult(
            facts=[aggregate_result.text],
            nodes=[],
            traversal_paths=[],
            entities_found=[],
            query=query,
            seed_facts=[],
            traversal_explanation={
                "query": query,
                "entities_identified": [],
                "seed_facts_via_vector_search": [],
                "mandatory_facts_always_included": [],
                "critical_path": "",
                "total_facts_in_context": 1,
                "how_it_works": (
                    "Direct Cypher query — aggregate "
                    "queries bypass vector search and "
                    "query Neo4j directly for complete "
                    "results. Traversal Graph shows all "
                    "listed entities and their relationships."
                ),
            },
            traversal_graph=aggregate_result.traversal_graph,
        )

    # Stage 1+2 — Entity extraction and query embedding run
    # concurrently (both only need the raw query string)
    entities_task = extract_entities(query)
    embedding_task = embed_query(query)
    entities, query_embedding = await asyncio.gather(
        entities_task, embedding_task
    )

    if not entities:
        logger.warning(f"No entities extracted from: {query[:80]}")
        return GraphResult(query=query, traversal_graph={"nodes": [], "links": []})

    # Stage 1b — resolve brand names to generic names
    entities = _resolve_drug_synonyms(entities)
    logger.info(f"Entities after synonym resolution: {entities}")

    if not query_embedding:
        logger.error("Query embedding failed — cannot search")
        return GraphResult(
            query=query,
            entities_found=entities,
            traversal_graph={"nodes": [], "links": []},
        )

    # Session 1 — vector search
    async with driver.session(
        database=settings.neo4j_database
    ) as session:
        seed_facts = await vector_search_facts(
            query_embedding, session, top_k=80
        )

    # Session 2 — mandatory facts
    async with driver.session(
        database=settings.neo4j_database
    ) as session:
        mandatory_facts = await get_mandatory_facts(
            entities, session
        )

    # Build seed node names from results
    seed_node_names = list(set(
        [name for seed in seed_facts
         for name in [seed.from_name, seed.to_name] if name]
        + entities
    ))

    # Session 3 — BFS expansion
    async with driver.session(
        database=settings.neo4j_database
    ) as session:
        bfs_edges = await bfs_expand(
            seed_node_names, session, hops=BFS_HOPS
        )

    logger.info(
        f"Search stages complete: "
        f"{len(seed_facts)} seed facts, "
        f"{len(mandatory_facts)} mandatory facts, "
        f"{len(bfs_edges)} BFS edges"
    )

    # Stage 6 — Context assembly
    context_lines, traversal_paths = assemble_context(
        seed_facts, bfs_edges, mandatory_facts, MAX_CONTEXT_FACTS
    )

    # Stage 7 — Traversal explanation
    traversal_explanation = build_traversal_explanation(
        query=query,
        entities=entities,
        seed_facts=seed_facts,
        mandatory_facts=mandatory_facts,
        final_facts=context_lines,
        traversal_paths=traversal_paths,
    )

    traversal_graph = _build_traversal_graph(
        seed_facts,
        bfs_edges,
        mandatory_facts,
        context_lines,
        entities,
        traversal_paths,
    )

    # Collect all node names
    all_nodes = set()
    for seed in seed_facts:
        all_nodes.add(seed.from_name)
        all_nodes.add(seed.to_name)
    for from_name, _, to_name in bfs_edges:
        all_nodes.add(from_name)
        all_nodes.add(to_name)

    logger.info(
        f"Graph search complete: "
        f"{len(context_lines)} context lines, "
        f"{len(traversal_paths)} paths, "
        f"{len(all_nodes)} unique nodes, "
        f"viz: {len(traversal_graph.get('nodes', []))} nodes / "
        f"{len(traversal_graph.get('links', []))} edges"
    )

    return GraphResult(
        facts=context_lines,
        nodes=sorted(all_nodes),
        traversal_paths=traversal_paths,
        entities_found=entities,
        query=query,
        seed_facts=[
            {
                "fact": s.fact_string,
                "score": round(s.score, 4),
                "from_name": s.from_name,
                "rel_type": s.rel_type,
                "to_name": s.to_name,
            }
            for s in seed_facts
        ],
        traversal_explanation=traversal_explanation,
        traversal_graph=traversal_graph,
    )


# =============================================================================
# SHORTEST PATH
# =============================================================================

async def find_path(
    entity1: str,
    entity2: str,
    driver: AsyncDriver,
) -> PathResult:
    """Find the shortest path between two named entities."""
    try:
        async with driver.session(
            database=settings.neo4j_database
        ) as session:
            result = await session.run(
                """
                MATCH (a), (b)
                WHERE (toLower(a.name) CONTAINS toLower($e1)
                       OR a.patient_id = $e1)
                  AND (toLower(b.name) CONTAINS toLower($e2)
                       OR b.patient_id = $e2)
                WITH a, b LIMIT 1
                MATCH path = shortestPath((a)-[*1..6]-(b))
                RETURN [n IN nodes(path) | n.name] AS path_nodes,
                       [r IN relationships(path) | type(r)] 
                       AS path_rels
                LIMIT 3
                """,
                e1=entity1,
                e2=entity2,
            )
            record = await result.single()

            if not record:
                return PathResult(
                    readable_path=(
                        f"No path found between "
                        f"{entity1} and {entity2}"
                    )
                )

            path_nodes = [str(n) for n in record["path_nodes"]]
            path_rels = [str(r) for r in record["path_rels"]]

            parts: list[str] = []
            for i, name in enumerate(path_nodes):
                parts.append(name)
                if i < len(path_rels):
                    parts.append(f"-[{path_rels[i]}]->")

            return PathResult(
                path_nodes=path_nodes,
                path_relationships=path_rels,
                readable_path=" ".join(parts),
                hops=len(path_rels),
            )

    except Exception as e:
        logger.error(
            f"find_path failed ({entity1} -> {entity2}): {e}"
        )
        return PathResult(readable_path=f"Path search error: {e}")
