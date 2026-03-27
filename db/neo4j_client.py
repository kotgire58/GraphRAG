"""Neo4j async driver, index creation, and health check."""

import logging

from neo4j import AsyncGraphDatabase, AsyncDriver

from config.settings import settings

logger = logging.getLogger(__name__)

_driver: AsyncDriver | None = None

NEO4J_INDEXES = [
    "CREATE INDEX drug_name IF NOT EXISTS FOR (n:Drug) ON (n.name)",
    "CREATE INDEX enzyme_name IF NOT EXISTS FOR (n:Enzyme) ON (n.name)",
    "CREATE INDEX patient_id IF NOT EXISTS FOR (n:Patient) ON (n.patient_id)",
    "CREATE INDEX condition_name IF NOT EXISTS FOR (n:Condition) ON (n.name)",
    "CREATE INDEX manufacturer_name IF NOT EXISTS FOR (n:Manufacturer) ON (n.name)",
    "CREATE INDEX hospital_id IF NOT EXISTS FOR (n:Hospital) ON (n.hospital_id)",
]


async def create_driver() -> AsyncDriver:
    """Create the Neo4j async driver and verify connectivity."""
    global _driver
    if _driver is not None:
        return _driver

    try:
        _driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_username, settings.neo4j_password),
        )
        async with _driver.session(database=settings.neo4j_database) as session:
            result = await session.run("RETURN 1 AS test")
            record = await result.single()
            if record and record["test"] == 1:
                logger.info("Neo4j connection verified successfully")
            else:
                logger.warning("Neo4j connection returned unexpected result")
        return _driver
    except Exception as e:
        logger.error(f"Failed to create Neo4j driver: {e}")
        raise


async def get_driver() -> AsyncDriver:
    """Return the existing driver or create a new one (for dependency injection)."""
    if _driver is None:
        return await create_driver()
    return _driver


async def create_indexes() -> None:
    """Create all Neo4j indexes defined in PLANNING.md."""
    driver = await get_driver()
    try:
        async with driver.session(database=settings.neo4j_database) as session:
            for index_cypher in NEO4J_INDEXES:
                await session.run(index_cypher)
                logger.info(f"Executed: {index_cypher}")
        logger.info(f"All {len(NEO4J_INDEXES)} Neo4j indexes created/verified")
    except Exception as e:
        logger.error(f"Failed to create Neo4j indexes: {e}")
        raise


async def health_check() -> str:
    """Return 'ok' if Neo4j is reachable, otherwise the error message."""
    try:
        driver = await get_driver()
        async with driver.session(database=settings.neo4j_database) as session:
            result = await session.run("RETURN 1 AS test")
            record = await result.single()
            if record and record["test"] == 1:
                return "ok"
            return f"Unexpected health check result: {record}"
    except Exception as e:
        return f"Neo4j error: {e}"


async def close_driver() -> None:
    """Gracefully close the Neo4j driver."""
    global _driver
    if _driver is not None:
        await _driver.close()
        _driver = None
        logger.info("Neo4j driver closed")
