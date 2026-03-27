"""LLM-based knowledge graph extraction from text chunks into Neo4j."""

import asyncio
import json
import logging
import re
from datetime import datetime, timezone

import httpx
from neo4j import AsyncDriver

from config.settings import settings

logger = logging.getLogger(__name__)

VALID_LABELS = frozenset(
    {
        "Drug",
        "Enzyme",
        "Transporter",
        "Condition",
        "Patient",
        "Physician",
        "Pharmacist",
        "Hospital",
        "Manufacturer",
        "Protocol",
        "ClinicalCase",
        "Contraindication",
        "TreatmentInteraction",
    }
)

VALID_REL_TYPES = frozenset(
    {
        "INHIBITS",
        "INDUCES",
        "METABOLIZED_BY",
        "CLEARED_BY",
        "INHIBITS_TRANSPORTER",
        "TREATS",
        "CONTRAINDICATED_WITH",
        "INTERACTS_WITH",
        "CAUSES",
        "MANUFACTURED_BY",
        "ALTERNATIVE_TO",
        "HAS_CONDITION",
        "PRESCRIBED",
        "PRESCRIBED_TO",
        "TREATED_BY",
        "ADMITTED_TO",
        "WORKS_AT",
        "FOLLOWS_PROTOCOL",
        "COVERS",
        "INVOLVES_PATIENT",
        "PRECIPITATED_BY",
        "PREVENTED_BY",
        "METABOLIZES",
        "INCREASES_RISK_OF",
        "SUPPLIES",
        "SUPPLIED_BY",
        "DOCUMENTED_IN",
        "DOCUMENTS",
        "REVIEWED_BY",
        "REQUIRES",
    }
)

EXTRACTION_PROMPT = """You are a medical knowledge graph extractor.
Extract ALL entities and relationships from the text below.
Return ONLY valid JSON. No markdown. No explanation. No code blocks.

Use ONLY these node labels:
Drug, Enzyme, Transporter, Condition, Patient, Physician, Pharmacist,
Hospital, Manufacturer, Protocol, ClinicalCase, Contraindication

Use ONLY these relationship types:
INHIBITS, INDUCES, METABOLIZED_BY, CLEARED_BY, INHIBITS_TRANSPORTER,
TREATS, CONTRAINDICATED_WITH, INTERACTS_WITH, CAUSES, MANUFACTURED_BY,
ALTERNATIVE_TO, HAS_CONDITION, PRESCRIBED, TREATED_BY, ADMITTED_TO,
WORKS_AT, FOLLOWS_PROTOCOL, COVERS, INVOLVES_PATIENT, PRECIPITATED_BY,
PREVENTED_BY, METABOLIZES, INCREASES_RISK_OF, SUPPLIES, DOCUMENTED_IN

NORMALIZATION RULES — follow these exactly:

NODE LABELING:
- CYP3A4, CYP2C9, CYP2D6, CYP1A2, CYP2C19, CYP2C8, CYP3A5 \
are ALWAYS label Enzyme, never Transporter or Drug
- OCT2, MATE1, MATE2, P-glycoprotein, P-gp, OATP1B1 \
are ALWAYS label Transporter
- ACE, Xanthine Oxidase, VKORC1, Aldosterone Synthase \
are ALWAYS label Enzyme

DRUG NAME NORMALIZATION — always use the generic name:
- S-warfarin, Warfarin sodium, R-warfarin → Warfarin
- Atorvastatin calcium → Atorvastatin
- Metformin hydrochloride → Metformin
- Lisinopril hydrochloride → Lisinopril
- Fluconazole capsule → Fluconazole
- Simvastatin tablet → Simvastatin
- Glipizide tablet → Glipizide
- Clarithromycin tablet → Clarithromycin
- Tacrolimus capsule → Tacrolimus
- Cyclosporine capsule → Cyclosporine
- Insulin Glargine injection → Insulin Glargine
- Amiodarone hydrochloride → Amiodarone
- Digoxin tablet → Digoxin
- Clopidogrel bisulfate → Clopidogrel
- Spironolactone tablet → Spironolactone
- Omeprazole capsule → Omeprazole
- Phenytoin sodium → Phenytoin
- Sildenafil citrate → Sildenafil
- Warfarin sodium → Warfarin

ENZYME NAME NORMALIZATION:
- Cytochrome P450 3A4, CYP 3A4, CYP-3A4 → CYP3A4
- Cytochrome P450 2C9, CYP 2C9, CYP-2C9 → CYP2C9
- Cytochrome P450 2D6, CYP 2D6 → CYP2D6
- Cytochrome P450 1A2, CYP 1A2 → CYP1A2
- Cytochrome P450 2C19, CYP 2C19 → CYP2C19
- P-glycoprotein, P-gp, Pgp, MDR1 → P-glycoprotein

PATIENT RECORDS — this is critical:
- If the text contains "Current medications:", extract EVERY \
drug listed as a PRESCRIBED relationship from the Patient \
to each Drug node
- If the text contains "Primary diagnosis:" or "Secondary \
diagnosis:", extract EVERY condition as a HAS_CONDITION \
relationship from the Patient to each Condition node
- Patient IDs must be formatted exactly as: PT-001, PT-002, etc.
- Never skip a medication or diagnosis from patient records

Return this exact JSON structure:
{
  "nodes": [
    {
      "id": "unique_id_no_spaces",
      "label": "Drug",
      "properties": {"name": "Fluconazole", "drug_class": "Triazole antifungal"}
    }
  ],
  "relationships": [
    {
      "from_id": "fluconazole",
      "to_id": "cyp2c9",
      "type": "INHIBITS",
      "properties": {"strength": "strong", "source_doc": "doc06"}
    }
  ]
}

IMPORTANT RULES:
1. Node id must be lowercase, no spaces, no special chars (use underscores)
2. Apply ALL normalization rules above before setting node names
3. Every relationship must have source_doc property
4. Do not invent relationships not stated in the text
5. Do not create nodes for vague concepts — only named entities
6. For patient records, EVERY medication = one PRESCRIBED relationship

Text:
{chunk_text}"""

# ---------------------------------------------------------------------------
# Python-side validation constants
# ---------------------------------------------------------------------------

ENZYME_NAMES = frozenset({
    "CYP3A4", "CYP2C9", "CYP2D6", "CYP1A2", "CYP2C19", "CYP2C8",
    "CYP3A5", "ACE", "VKORC1", "Xanthine Oxidase", "Aldosterone Synthase",
})

TRANSPORTER_NAMES = frozenset({
    "P-glycoprotein", "OCT2", "MATE1", "MATE2-K", "MATE2",
    "OATP1B1", "OATP1B3",
})

DRUG_NORMALIZATIONS: dict[str, str] = {
    "s-warfarin": "Warfarin",
    "r-warfarin": "Warfarin",
    "warfarin sodium": "Warfarin",
    "atorvastatin calcium": "Atorvastatin",
    "metformin hydrochloride": "Metformin",
    "lisinopril hydrochloride": "Lisinopril",
    "fluconazole capsule": "Fluconazole",
    "simvastatin tablet": "Simvastatin",
    "glipizide tablet": "Glipizide",
    "clarithromycin tablet": "Clarithromycin",
    "tacrolimus capsule": "Tacrolimus",
    "cyclosporine capsule": "Cyclosporine",
    "insulin glargine injection": "Insulin Glargine",
    "amiodarone hydrochloride": "Amiodarone",
    "digoxin tablet": "Digoxin",
    "clopidogrel bisulfate": "Clopidogrel",
    "spironolactone tablet": "Spironolactone",
    "omeprazole capsule": "Omeprazole",
    "phenytoin sodium": "Phenytoin",
    "sildenafil citrate": "Sildenafil",
}

ENZYME_NORMALIZATIONS: dict[str, str] = {
    "cytochrome p450 3a4": "CYP3A4",
    "cyp 3a4": "CYP3A4",
    "cyp-3a4": "CYP3A4",
    "cytochrome p450 2c9": "CYP2C9",
    "cyp 2c9": "CYP2C9",
    "cyp-2c9": "CYP2C9",
    "cytochrome p450 2d6": "CYP2D6",
    "cyp 2d6": "CYP2D6",
    "cytochrome p450 1a2": "CYP1A2",
    "cyp 1a2": "CYP1A2",
    "cytochrome p450 2c19": "CYP2C19",
    "cyp 2c19": "CYP2C19",
    "p-gp": "P-glycoprotein",
    "pgp": "P-glycoprotein",
    "mdr1": "P-glycoprotein",
}

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clean_name(name: str) -> str:
    """Strip whitespace, remove Cypher-breaking chars, trailing commas."""
    name = name.strip()
    name = re.sub(r"[{}]", "", name)
    name = re.sub(r",\s*$", "", name)
    return name


def _validate_and_fix_node(node: dict) -> dict:
    """Apply normalization rules and fix mislabeled nodes."""
    props = node.get("properties", {})
    name = props.get("name", "").strip()
    name_lower = name.lower()
    label = node.get("label", "")

    if name_lower in ENZYME_NORMALIZATIONS:
        name = ENZYME_NORMALIZATIONS[name_lower]
        props["name"] = name
        name_lower = name.lower()

    if name_lower in DRUG_NORMALIZATIONS:
        name = DRUG_NORMALIZATIONS[name_lower]
        props["name"] = name
        name_lower = name.lower()

    for enzyme in ENZYME_NAMES:
        if enzyme.lower() == name_lower or enzyme.lower() in name_lower:
            if label != "Enzyme":
                logger.debug(
                    f"Correcting label for {name}: {label} -> Enzyme"
                )
                node["label"] = "Enzyme"
                props["name"] = enzyme
            break

    for transporter in TRANSPORTER_NAMES:
        if transporter.lower() == name_lower:
            if label != "Transporter":
                logger.debug(
                    f"Correcting label for {name}: {label} -> Transporter"
                )
                node["label"] = "Transporter"
            break

    node["properties"] = props
    return node


def _parse_llm_json(text: str) -> dict | None:
    """Extract JSON from LLM response, handling markdown fences."""
    text = text.strip()
    if "```" in text:
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------


async def _call_llm(
    client: httpx.AsyncClient, chunk_text: str, source_doc: str
) -> dict | None:
    """Call the ingestion LLM with retry logic."""
    prompt = EXTRACTION_PROMPT.replace("{chunk_text}", chunk_text)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
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
                timeout=60.0,
            )
            response.raise_for_status()
            data = response.json()
            raw_text = data["choices"][0]["message"]["content"]
            logger.debug(
                f"LLM raw response for {source_doc}: {raw_text[:200]}"
            )
            parsed = _parse_llm_json(raw_text)
            if parsed is not None:
                return parsed
            logger.warning(
                f"JSON parse failed for {source_doc} attempt {attempt}: "
                f"{raw_text[:200]}"
            )
        except httpx.HTTPStatusError as e:
            logger.warning(
                f"LLM HTTP {e.response.status_code} for {source_doc} "
                f"attempt {attempt}: {e.response.text[:200]}"
            )
        except httpx.TimeoutException:
            logger.warning(
                f"LLM timeout for {source_doc} attempt {attempt}"
            )
        except Exception as e:
            logger.warning(
                f"LLM call error for {source_doc} attempt {attempt}: {e}"
            )

        if attempt < MAX_RETRIES:
            await asyncio.sleep(RETRY_DELAY_SECONDS * attempt)

    return None


# ---------------------------------------------------------------------------
# Neo4j writes
# ---------------------------------------------------------------------------


async def _merge_node(
    session, label: str, name: str, properties: dict
) -> bool:
    """MERGE a single node into Neo4j. Returns True on success."""
    cypher = (
        f"MERGE (n:{label} {{name: $name}}) "
        "ON CREATE SET n += $props, n.created_at = datetime() "
        "ON MATCH SET n += $props, n.updated_at = datetime()"
    )
    try:
        await session.run(cypher, name=name, props=properties)
        return True
    except Exception as e:
        logger.error(f"Failed to merge node {label}:{name}: {e}")
        return False


async def _merge_relationship(
    session,
    from_name: str,
    to_name: str,
    rel_type: str,
    properties: dict,
) -> bool:
    """MERGE a relationship between two nodes matched by name."""
    cypher = (
        "MATCH (a {name: $from_name}) "
        "MATCH (b {name: $to_name}) "
        f"MERGE (a)-[r:{rel_type}]->(b) "
        "ON CREATE SET r += $props, r.created_at = datetime() "
        "ON MATCH SET r += $props"
    )
    try:
        await session.run(
            cypher,
            from_name=from_name,
            to_name=to_name,
            props=properties,
        )
        return True
    except Exception as e:
        logger.error(
            f"Failed to merge rel {from_name}-[{rel_type}]->{to_name}: {e}"
        )
        return False


# ---------------------------------------------------------------------------
# Main extraction entry point
# ---------------------------------------------------------------------------


async def extract_and_store(
    chunk: dict, driver: AsyncDriver
) -> dict:
    """Extract entities/relationships from a chunk and store in Neo4j.

    Returns stats dict with nodes_created, rels_created,
    nodes_skipped, parse_errors.
    """
    stats = {
        "nodes_created": 0,
        "rels_created": 0,
        "nodes_skipped": 0,
        "parse_errors": 0,
    }

    source_doc = chunk["metadata"]["filename"]
    chunk_text = chunk["content"]

    async with httpx.AsyncClient() as client:
        extracted = await _call_llm(client, chunk_text, source_doc)

    if extracted is None:
        stats["parse_errors"] = 1
        logger.warning(
            f"No extraction result for chunk "
            f"{chunk['chunk_index']} of {source_doc}"
        )
        return stats

    nodes = extracted.get("nodes", [])
    relationships = extracted.get("relationships", [])

    node_id_to_name: dict[str, str] = {}
    now_str = datetime.now(timezone.utc).isoformat()

    async with driver.session(database=settings.neo4j_database) as session:
        for node in nodes:
            label = node.get("label", "")
            props = node.get("properties", {})
            node_id = node.get("id", "")
            name = props.get("name", "")

            if label not in VALID_LABELS:
                logger.debug(
                    f"Skipping node with invalid label '{label}': {name}"
                )
                stats["nodes_skipped"] += 1
                continue

            name = _clean_name(name)
            if not name or len(name) < 2:
                stats["nodes_skipped"] += 1
                continue

            props["name"] = name
            node = _validate_and_fix_node(node)
            label = node.get("label", label)
            name = node["properties"].get("name", name)

            node_id_to_name[node_id] = name

            if await _merge_node(session, label, name, props):
                stats["nodes_created"] += 1
            else:
                stats["nodes_skipped"] += 1

        for rel in relationships:
            from_id = rel.get("from_id", "")
            to_id = rel.get("to_id", "")
            rel_type = rel.get("type", "INTERACTS_WITH")
            props = rel.get("properties", {})

            from_name = node_id_to_name.get(from_id, "")
            to_name = node_id_to_name.get(to_id, "")

            if not from_name or not to_name:
                continue

            if rel_type not in VALID_REL_TYPES:
                logger.debug(
                    f"Mapping invalid rel type '{rel_type}' to INTERACTS_WITH"
                )
                rel_type = "INTERACTS_WITH"

            props["source_doc"] = props.get("source_doc", source_doc)
            if "confidence" not in props:
                props["confidence"] = 0.8
            props["extracted_at"] = now_str

            if await _merge_relationship(
                session, from_name, to_name, rel_type, props
            ):
                stats["rels_created"] += 1

    return stats
