"""Seed Patient nodes and their relationships directly into Neo4j."""

import asyncio
import logging

from config.settings import settings
from db.neo4j_client import get_driver

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

PATIENTS = [
    {
        "patient_id": "PT-001",
        "age": 58,
        "sex": "Male",
        "conditions": [
            "Type 2 Diabetes Mellitus",
            "Hypertension",
            "Dyslipidemia",
        ],
        "medications": ["Metformin", "Lisinopril", "Atorvastatin"],
        "physician_last_name": "Chen",
        "hospital_keyword": "Metro General",
    },
    {
        "patient_id": "PT-002",
        "age": 72,
        "sex": "Female",
        "conditions": [
            "Atrial Fibrillation",
            "Hypertension",
            "Coronary Artery Disease",
        ],
        "medications": ["Warfarin", "Metoprolol", "Lisinopril", "Atorvastatin"],
        "physician_last_name": "Okafor",
        "hospital_keyword": "Metro General",
    },
    {
        "patient_id": "PT-003",
        "age": 45,
        "sex": "Male",
        "conditions": ["Kidney Transplant", "Hypertension"],
        "medications": ["Tacrolimus", "Mycophenolate", "Prednisone", "Amlodipine"],
        "physician_last_name": "Patel",
        "hospital_keyword": "University Transplant",
    },
    {
        "patient_id": "PT-004",
        "age": 67,
        "sex": "Female",
        "conditions": [
            "Heart Failure",
            "Atrial Fibrillation",
            "Hypertension",
        ],
        "medications": [
            "Digoxin", "Carvedilol", "Lisinopril",
            "Spironolactone", "Warfarin",
        ],
        "physician_last_name": "Okafor",
        "hospital_keyword": "Metro General",
    },
    {
        "patient_id": "PT-005",
        "age": 52,
        "sex": "Male",
        "conditions": ["Type 2 Diabetes Mellitus", "Dyslipidemia"],
        "medications": ["Metformin", "Glipizide", "Simvastatin"],
        "physician_last_name": "Chen",
        "hospital_keyword": "Metro General",
    },
    {
        "patient_id": "PT-006",
        "age": 63,
        "sex": "Female",
        "conditions": ["Hypertension", "Dyslipidemia", "Osteoporosis"],
        "medications": ["Amlodipine", "Atorvastatin", "Alendronate"],
        "physician_last_name": "Patel",
        "hospital_keyword": "Metro General",
    },
    {
        "patient_id": "PT-007",
        "age": 55,
        "sex": "Male",
        "conditions": [
            "Coronary Artery Disease",
            "Hypertension",
            "Type 2 Diabetes Mellitus",
        ],
        "medications": [
            "Clopidogrel", "Aspirin", "Lisinopril",
            "Metformin", "Rosuvastatin",
        ],
        "physician_last_name": "Okafor",
        "hospital_keyword": "Metro General",
    },
    {
        "patient_id": "PT-008",
        "age": 70,
        "sex": "Female",
        "conditions": ["Atrial Fibrillation", "Heart Failure"],
        "medications": ["Amiodarone", "Warfarin", "Digoxin", "Furosemide"],
        "physician_last_name": "Okafor",
        "hospital_keyword": "Metro General",
    },
    {
        "patient_id": "PT-009",
        "age": 48,
        "sex": "Male",
        "conditions": ["HIV infection", "Hypertension"],
        "medications": ["Ritonavir", "Tenofovir", "Lisinopril"],
        "physician_last_name": "Patel",
        "hospital_keyword": "University Transplant",
    },
    {
        "patient_id": "PT-010",
        "age": 61,
        "sex": "Female",
        "conditions": [
            "Rheumatoid Arthritis",
            "Hypertension",
            "Type 2 Diabetes Mellitus",
        ],
        "medications": ["Methotrexate", "Prednisone", "Lisinopril", "Metformin"],
        "physician_last_name": "Chen",
        "hospital_keyword": "Metro General",
    },
]


async def seed() -> None:
    """Create all Patient nodes and link them to existing graph entities."""
    driver = await get_driver()

    async with driver.session(database=settings.neo4j_database) as session:
        patients_created = 0
        prescribed_created = 0
        conditions_linked = 0
        physicians_linked = 0
        hospitals_linked = 0

        for pt in PATIENTS:
            pid = pt["patient_id"]

            try:
                await session.run(
                    "MERGE (p:Patient {patient_id: $pid}) "
                    "ON CREATE SET p.name = $pid, p.age = $age, "
                    "  p.sex = $sex, p.created_at = datetime() "
                    "ON MATCH SET p.age = $age, p.sex = $sex, "
                    "  p.updated_at = datetime()",
                    pid=pid,
                    age=pt["age"],
                    sex=pt["sex"],
                )
                patients_created += 1
                logger.info(f"MERGE Patient {pid}")
            except Exception as e:
                logger.error(f"Failed to create Patient {pid}: {e}")
                continue

            for drug_name in pt["medications"]:
                try:
                    result = await session.run(
                        "MATCH (p:Patient {patient_id: $pid}) "
                        "MATCH (d:Drug) WHERE toLower(d.name) = toLower($drug) "
                        "MERGE (p)-[r:PRESCRIBED]->(d) "
                        "ON CREATE SET r.source = 'seed_patients', "
                        "  r.created_at = datetime() "
                        "RETURN d.name AS matched",
                        pid=pid,
                        drug=drug_name,
                    )
                    records = await result.data()
                    if records:
                        prescribed_created += 1
                        logger.info(f"  {pid} -[PRESCRIBED]-> {records[0]['matched']}")
                    else:
                        logger.warning(f"  Drug not found for {pid}: {drug_name}")
                except Exception as e:
                    logger.error(f"  PRESCRIBED failed {pid}->{drug_name}: {e}")

            for condition in pt["conditions"]:
                try:
                    result = await session.run(
                        "MATCH (p:Patient {patient_id: $pid}) "
                        "MATCH (c:Condition) "
                        "  WHERE toLower(c.name) CONTAINS toLower($cond) "
                        "MERGE (p)-[r:HAS_CONDITION]->(c) "
                        "ON CREATE SET r.source = 'seed_patients', "
                        "  r.created_at = datetime() "
                        "RETURN c.name AS matched",
                        pid=pid,
                        cond=condition,
                    )
                    records = await result.data()
                    if records:
                        conditions_linked += len(records)
                        for rec in records:
                            logger.info(
                                f"  {pid} -[HAS_CONDITION]-> {rec['matched']}"
                            )
                    else:
                        logger.warning(
                            f"  Condition not found for {pid}: {condition}"
                        )
                except Exception as e:
                    logger.error(
                        f"  HAS_CONDITION failed {pid}->{condition}: {e}"
                    )

            try:
                result = await session.run(
                    "MATCH (p:Patient {patient_id: $pid}) "
                    "MATCH (ph:Physician) "
                    "  WHERE ph.name CONTAINS $last_name "
                    "MERGE (p)-[r:TREATED_BY]->(ph) "
                    "ON CREATE SET r.source = 'seed_patients', "
                    "  r.created_at = datetime() "
                    "RETURN ph.name AS matched",
                    pid=pid,
                    last_name=pt["physician_last_name"],
                )
                records = await result.data()
                if records:
                    physicians_linked += 1
                    logger.info(
                        f"  {pid} -[TREATED_BY]-> {records[0]['matched']}"
                    )
                else:
                    logger.warning(
                        f"  Physician not found for {pid}: "
                        f"{pt['physician_last_name']}"
                    )
            except Exception as e:
                logger.error(
                    f"  TREATED_BY failed for {pid}: {e}"
                )

            try:
                result = await session.run(
                    "MATCH (p:Patient {patient_id: $pid}) "
                    "MATCH (h:Hospital) "
                    "  WHERE h.name CONTAINS $kw "
                    "MERGE (p)-[r:ADMITTED_TO]->(h) "
                    "ON CREATE SET r.source = 'seed_patients', "
                    "  r.created_at = datetime() "
                    "RETURN h.name AS matched",
                    pid=pid,
                    kw=pt["hospital_keyword"],
                )
                records = await result.data()
                if records:
                    hospitals_linked += 1
                    logger.info(
                        f"  {pid} -[ADMITTED_TO]-> {records[0]['matched']}"
                    )
                else:
                    logger.warning(
                        f"  Hospital not found for {pid}: "
                        f"{pt['hospital_keyword']}"
                    )
            except Exception as e:
                logger.error(
                    f"  ADMITTED_TO failed for {pid}: {e}"
                )

        print()
        print("=" * 60)
        print("  PATIENT SEEDING COMPLETE")
        print("=" * 60)
        print(f"  Patients created:      {patients_created}")
        print(f"  PRESCRIBED links:      {prescribed_created}")
        print(f"  HAS_CONDITION links:   {conditions_linked}")
        print(f"  TREATED_BY links:      {physicians_linked}")
        print(f"  ADMITTED_TO links:     {hospitals_linked}")
        print("=" * 60)

        print()
        print("=" * 60)
        print("  VERIFICATION: Patient PRESCRIBED medications")
        print("=" * 60)
        result = await session.run(
            "MATCH (p:Patient)-[:PRESCRIBED]->(d:Drug) "
            "RETURN p.patient_id AS patient_id, "
            "  collect(d.name) AS medications "
            "ORDER BY p.patient_id"
        )
        records = await result.data()
        if not records:
            print("  (no PRESCRIBED relationships found)")
        for rec in records:
            meds = ", ".join(sorted(rec["medications"]))
            print(f"  {rec['patient_id']}  ->  {meds}")
        print("=" * 60)

    await driver.close()


if __name__ == "__main__":
    asyncio.run(seed())
