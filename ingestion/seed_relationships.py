"""Seed missing transporter, QT, and enzyme relationships into Neo4j."""

import asyncio
import logging

from config.settings import settings
from db.neo4j_client import get_driver

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

RELATIONSHIP_STATEMENTS = [
    # --- P-glycoprotein relationships ---
    (
        "MERGE (d:Drug {name: 'Digoxin'}) "
        "MERGE (t:Transporter {name: 'P-glycoprotein'}) "
        "MERGE (d)-[:CLEARED_BY {source_doc: 'doc02', confidence: 1.0}]->(t)",
        "Digoxin -[CLEARED_BY]-> P-glycoprotein",
    ),
    (
        "MERGE (d:Drug {name: 'Amiodarone'}) "
        "MERGE (t:Transporter {name: 'P-glycoprotein'}) "
        "MERGE (d)-[:INHIBITS_TRANSPORTER "
        "{strength: 'strong', source_doc: 'doc02', confidence: 1.0}]->(t)",
        "Amiodarone -[INHIBITS_TRANSPORTER]-> P-glycoprotein",
    ),
    (
        "MERGE (d:Drug {name: 'Clarithromycin'}) "
        "MERGE (t:Transporter {name: 'P-glycoprotein'}) "
        "MERGE (d)-[:INHIBITS_TRANSPORTER "
        "{strength: 'strong', source_doc: 'doc02', confidence: 1.0}]->(t)",
        "Clarithromycin -[INHIBITS_TRANSPORTER]-> P-glycoprotein",
    ),
    (
        "MERGE (d:Drug {name: 'Cyclosporine'}) "
        "MERGE (t:Transporter {name: 'P-glycoprotein'}) "
        "MERGE (d)-[:INHIBITS_TRANSPORTER "
        "{strength: 'strong', source_doc: 'doc02', confidence: 1.0}]->(t)",
        "Cyclosporine -[INHIBITS_TRANSPORTER]-> P-glycoprotein",
    ),
    (
        "MERGE (d:Drug {name: 'Tacrolimus'}) "
        "MERGE (t:Transporter {name: 'P-glycoprotein'}) "
        "MERGE (d)-[:CLEARED_BY {source_doc: 'doc02', confidence: 1.0}]->(t)",
        "Tacrolimus -[CLEARED_BY]-> P-glycoprotein",
    ),
    # --- OCT2 / MATE1 (Metformin clearance) ---
    (
        "MERGE (d:Drug {name: 'Metformin'}) "
        "MERGE (t:Transporter {name: 'OCT2'}) "
        "MERGE (d)-[:CLEARED_BY {source_doc: 'doc02', confidence: 1.0}]->(t)",
        "Metformin -[CLEARED_BY]-> OCT2",
    ),
    (
        "MERGE (d:Drug {name: 'Metformin'}) "
        "MERGE (t:Transporter {name: 'MATE1'}) "
        "MERGE (d)-[:CLEARED_BY {source_doc: 'doc02', confidence: 1.0}]->(t)",
        "Metformin -[CLEARED_BY]-> MATE1",
    ),
    # --- QT prolongation ---
    (
        "MERGE (d:Drug {name: 'Fluconazole'}) "
        "MERGE (c:Condition {name: 'QT Prolongation'}) "
        "MERGE (d)-[:CAUSES "
        "{severity: 'moderate', source_doc: 'doc07', confidence: 1.0}]->(c)",
        "Fluconazole -[CAUSES]-> QT Prolongation",
    ),
    (
        "MERGE (d:Drug {name: 'Amiodarone'}) "
        "MERGE (c:Condition {name: 'QT Prolongation'}) "
        "MERGE (d)-[:CAUSES "
        "{severity: 'severe', source_doc: 'doc07', confidence: 1.0}]->(c)",
        "Amiodarone -[CAUSES]-> QT Prolongation",
    ),
    (
        "MERGE (c1:Condition {name: 'QT Prolongation'}) "
        "MERGE (c2:Condition {name: 'Torsades de Pointes'}) "
        "MERGE (c1)-[:INCREASES_RISK_OF "
        "{source_doc: 'doc07', confidence: 1.0}]->(c2)",
        "QT Prolongation -[INCREASES_RISK_OF]-> Torsades de Pointes",
    ),
    # --- Amiodarone CYP2C9 inhibition ---
    (
        "MERGE (d:Drug {name: 'Amiodarone'}) "
        "MERGE (e:Enzyme {name: 'CYP2C9'}) "
        "MERGE (d)-[:INHIBITS "
        "{strength: 'moderate', source_doc: 'doc06', confidence: 1.0}]->(e)",
        "Amiodarone -[INHIBITS]-> CYP2C9",
    ),
    # --- Simvastatin CYP3A4 ---
    (
        "MERGE (d:Drug {name: 'Simvastatin'}) "
        "MERGE (e:Enzyme {name: 'CYP3A4'}) "
        "MERGE (d)-[:METABOLIZED_BY "
        "{source_doc: 'doc06', confidence: 1.0}]->(e)",
        "Simvastatin -[METABOLIZED_BY]-> CYP3A4",
    ),
    (
        "MERGE (d:Drug {name: 'Fluconazole'}) "
        "MERGE (e:Enzyme {name: 'CYP3A4'}) "
        "MERGE (d)-[:INHIBITS "
        "{strength: 'moderate', source_doc: 'doc06', confidence: 1.0}]->(e)",
        "Fluconazole -[INHIBITS]-> CYP3A4",
    ),
    # --- Warfarin CYP2C9 (ensure exists) ---
    (
        "MERGE (d:Drug {name: 'Warfarin'}) "
        "MERGE (e:Enzyme {name: 'CYP2C9'}) "
        "MERGE (d)-[:METABOLIZED_BY "
        "{source_doc: 'doc06', confidence: 1.0}]->(e)",
        "Warfarin -[METABOLIZED_BY]-> CYP2C9",
    ),
]

VERIFICATION_QUERIES = [
    (
        "CLEARED_BY relationships",
        "MATCH (d:Drug)-[:CLEARED_BY]->(t:Transporter) "
        "RETURN d.name AS drug, t.name AS transporter "
        "ORDER BY drug",
    ),
    (
        "INHIBITS_TRANSPORTER relationships",
        "MATCH (d:Drug)-[:INHIBITS_TRANSPORTER]->(t:Transporter) "
        "RETURN d.name AS drug, t.name AS transporter "
        "ORDER BY drug",
    ),
    (
        "CAUSES relationships (Drug -> Condition)",
        "MATCH (d:Drug)-[:CAUSES]->(c:Condition) "
        "RETURN d.name AS drug, c.name AS condition "
        "ORDER BY drug",
    ),
]


async def seed() -> None:
    """Create all missing relationships and verify."""
    driver = await get_driver()

    async with driver.session(database=settings.neo4j_database) as session:
        created = 0
        for cypher, description in RELATIONSHIP_STATEMENTS:
            try:
                await session.run(cypher)
                created += 1
                logger.info(f"  MERGE {description}")
            except Exception as e:
                logger.error(f"  FAILED {description}: {e}")

        print()
        print("=" * 60)
        print(f"  SEEDED {created}/{len(RELATIONSHIP_STATEMENTS)} RELATIONSHIPS")
        print("=" * 60)

        for title, cypher in VERIFICATION_QUERIES:
            print(f"\n--- {title} ---")
            result = await session.run(cypher)
            records = await result.data()
            if not records:
                print("  (none)")
            for rec in records:
                vals = "  ->  ".join(str(v) for v in rec.values())
                print(f"  {vals}")

    print()
    print("=" * 60)
    print("  DONE")
    print("=" * 60)
    await driver.close()


if __name__ == "__main__":
    asyncio.run(seed())
