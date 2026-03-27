"""Fuzzy-match deduplication of Neo4j nodes with similar names."""

import logging
import re
from collections import defaultdict

from neo4j import AsyncDriver
from thefuzz import fuzz

from config.settings import settings

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 85


def _names_are_safe_to_merge(name_a: str, name_b: str) -> bool:
    """Reject merges where alphanumeric identifiers differ.

    Prevents merging CYP2C9 with CYP2C19, PT-001 with PT-002,
    Teva Pharmaceuticals with Taro Pharmaceutical, etc.
    """
    codes_a = set(re.findall(r"[A-Z]*\d+[A-Z]*\d*", name_a))
    codes_b = set(re.findall(r"[A-Z]*\d+[A-Z]*\d*", name_b))
    if codes_a and codes_b and codes_a != codes_b:
        return False

    alpha_a = re.sub(r"[^a-z]", "", name_a.lower())
    alpha_b = re.sub(r"[^a-z]", "", name_b.lower())
    if alpha_a != alpha_b:
        len_diff = abs(len(alpha_a) - len(alpha_b))
        if len_diff > 3:
            return False

    return True


async def deduplicate(driver: AsyncDriver) -> dict:
    """Find and merge duplicate nodes using fuzzy name matching.

    Returns dict with duplicates_merged count.
    """
    merged_count = 0

    try:
        async with driver.session(database=settings.neo4j_database) as session:
            result = await session.run(
                "MATCH (n) WHERE n.name IS NOT NULL "
                "RETURN labels(n)[0] AS label, n.name AS name, "
                "elementId(n) AS eid "
                "ORDER BY label, name"
            )
            records = [record async for record in result]
    except Exception as e:
        logger.error(f"Failed to fetch nodes for deduplication: {e}")
        return {"duplicates_merged": 0}

    by_label: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        by_label[record["label"]].append(
            {"name": record["name"], "eid": record["eid"]}
        )

    for label, nodes in by_label.items():
        if len(nodes) < 2:
            continue

        already_merged: set[str] = set()

        for i in range(len(nodes)):
            if nodes[i]["eid"] in already_merged:
                continue

            canonical = nodes[i]

            for j in range(i + 1, len(nodes)):
                if nodes[j]["eid"] in already_merged:
                    continue

                duplicate = nodes[j]
                ratio = fuzz.ratio(
                    canonical["name"].lower(), duplicate["name"].lower()
                )

                if ratio >= SIMILARITY_THRESHOLD and _names_are_safe_to_merge(
                    canonical["name"], duplicate["name"]
                ):
                    try:
                        await _merge_nodes(
                            driver,
                            canonical_eid=canonical["eid"],
                            duplicate_eid=duplicate["eid"],
                            canonical_name=canonical["name"],
                            duplicate_name=duplicate["name"],
                        )
                        already_merged.add(duplicate["eid"])
                        merged_count += 1
                        logger.info(
                            f"Merged '{duplicate['name']}' "
                            f"-> '{canonical['name']}' "
                            f"(label={label}, similarity={ratio})"
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to merge '{duplicate['name']}' "
                            f"-> '{canonical['name']}': {e}"
                        )

    logger.info(f"Deduplication complete: {merged_count} nodes merged")
    return {"duplicates_merged": merged_count}


async def _merge_nodes(
    driver: AsyncDriver,
    canonical_eid: str,
    duplicate_eid: str,
    canonical_name: str,
    duplicate_name: str,
) -> None:
    """Move all relationships from duplicate to canonical, then delete duplicate."""
    async with driver.session(database=settings.neo4j_database) as session:
        await session.run(
            "MATCH (dup) WHERE elementId(dup) = $dup_eid "
            "MATCH (can) WHERE elementId(can) = $can_eid "
            "WITH dup, can "
            "MATCH (dup)-[r]->(target) "
            "WHERE target <> can "
            "WITH dup, can, type(r) AS rtype, properties(r) AS rprops, target "
            "CREATE (can)-[nr:INTERACTS_WITH]->(target) "
            "SET nr = rprops",
            dup_eid=duplicate_eid,
            can_eid=canonical_eid,
        )

        await session.run(
            "MATCH (dup) WHERE elementId(dup) = $dup_eid "
            "MATCH (can) WHERE elementId(can) = $can_eid "
            "MATCH (source)-[r]->(dup) "
            "WHERE source <> can "
            "WITH dup, can, type(r) AS rtype, properties(r) AS rprops, source "
            "CREATE (source)-[nr:INTERACTS_WITH]->(can) "
            "SET nr = rprops",
            dup_eid=duplicate_eid,
            can_eid=canonical_eid,
        )

        await session.run(
            "MATCH (dup) WHERE elementId(dup) = $dup_eid "
            "DETACH DELETE dup",
            dup_eid=duplicate_eid,
        )
