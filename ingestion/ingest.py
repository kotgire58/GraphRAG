"""CLI runner for the full ingestion pipeline."""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from tqdm import tqdm

from config.settings import settings
from db import postgres, neo4j_client
from ingestion.chunker import chunk_document
from ingestion.embedder import embed_chunks
from ingestion.graph_extractor import extract_and_store
from ingestion.deduplicator import deduplicate

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


async def _clean_databases(pool, driver) -> None:
    """Wipe both databases and recreate schema/indexes."""
    logger.info("Cleaning databases...")

    try:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM chunks")
            await conn.execute("DELETE FROM documents")
        logger.info("PostgreSQL tables cleared")
    except Exception as e:
        logger.error(f"Failed to clean PostgreSQL: {e}")
        raise

    try:
        async with driver.session(database=settings.neo4j_database) as session:
            await session.run("MATCH (n) DETACH DELETE n")
        logger.info("Neo4j graph cleared")
    except Exception as e:
        logger.error(f"Failed to clean Neo4j: {e}")
        raise

    await postgres.apply_schema()
    await neo4j_client.create_indexes()
    logger.info("Schema and indexes recreated")


async def _insert_document(pool, filepath: Path, content: str) -> int:
    """Insert a document record and return its id."""
    word_count = len(content.split())
    title_line = ""
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("##"):
            title_line = stripped[2:].strip()
            break

    async with pool.acquire() as conn:
        doc_id = await conn.fetchval(
            "INSERT INTO documents (filename, title, content, word_count) "
            "VALUES ($1, $2, $3, $4) "
            "ON CONFLICT (filename) DO UPDATE "
            "SET content = EXCLUDED.content, "
            "    word_count = EXCLUDED.word_count, "
            "    title = EXCLUDED.title "
            "RETURNING id",
            filepath.name,
            title_line or filepath.stem,
            content,
            word_count,
        )
    return doc_id


async def run_ingestion(
    docs_path: Path,
    clean: bool = False,
    skip_embed: bool = False,
    skip_graph: bool = False,
) -> dict:
    """Run the full ingestion pipeline."""
    pool = await postgres.create_pool()
    driver = await neo4j_client.create_driver()

    if clean:
        await _clean_databases(pool, driver)

    md_files = sorted(docs_path.glob("*.md"))
    if not md_files:
        logger.error(f"No .md files found in {docs_path}")
        return {"error": "No documents found"}

    total_stats = {
        "documents_processed": 0,
        "chunks_created": 0,
        "nodes_created": 0,
        "rels_created": 0,
        "nodes_skipped": 0,
        "parse_errors": 0,
        "duplicates_merged": 0,
    }

    for filepath in tqdm(md_files, desc="Processing documents"):
        logger.info(f"Processing {filepath.name}...")

        try:
            chunks = chunk_document(filepath)
        except Exception as e:
            logger.error(f"Chunking failed for {filepath.name}: {e}")
            continue

        try:
            content = filepath.read_text(encoding="utf-8")
            doc_id = await _insert_document(pool, filepath, content)
        except Exception as e:
            logger.error(f"DB insert failed for {filepath.name}: {e}")
            continue

        if not skip_embed:
            try:
                await embed_chunks(chunks, doc_id, pool)
                total_stats["chunks_created"] += len(chunks)
            except Exception as e:
                logger.error(f"Embedding failed for {filepath.name}: {e}")

        if not skip_graph:
            for chunk in chunks:
                try:
                    chunk_stats = await extract_and_store(chunk, driver)
                    total_stats["nodes_created"] += chunk_stats["nodes_created"]
                    total_stats["rels_created"] += chunk_stats["rels_created"]
                    total_stats["nodes_skipped"] += chunk_stats["nodes_skipped"]
                    total_stats["parse_errors"] += chunk_stats["parse_errors"]
                except Exception as e:
                    logger.error(
                        f"Graph extraction failed for {filepath.name} "
                        f"chunk {chunk['chunk_index']}: {e}"
                    )
                await asyncio.sleep(0.5)

        total_stats["documents_processed"] += 1

    if not skip_graph:
        try:
            dedup_result = await deduplicate(driver)
            total_stats["duplicates_merged"] = dedup_result["duplicates_merged"]
        except Exception as e:
            logger.error(f"Deduplication failed: {e}")

    return total_stats


def _print_report(stats: dict) -> None:
    """Print the final ingestion summary."""
    print("\n" + "=" * 50)
    print("  INGESTION COMPLETE")
    print("=" * 50)
    print(f"  Documents processed:  {stats.get('documents_processed', 0)}")
    print(f"  Chunks created:       {stats.get('chunks_created', 0)}")
    print(f"  Nodes created:        {stats.get('nodes_created', 0)}")
    print(f"  Relationships created:{stats.get('rels_created', 0)}")
    print(f"  Nodes skipped:        {stats.get('nodes_skipped', 0)}")
    print(f"  Parse errors:         {stats.get('parse_errors', 0)}")
    print(f"  Duplicates merged:    {stats.get('duplicates_merged', 0)}")
    print("=" * 50)


def main() -> None:
    """Entry point for CLI invocation."""
    parser = argparse.ArgumentParser(
        description="GraphRAG ingestion pipeline"
    )
    parser.add_argument(
        "--docs",
        type=str,
        required=True,
        help="Path to documents folder",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Wipe both databases before ingesting",
    )
    parser.add_argument(
        "--skip-embed",
        action="store_true",
        help="Skip pgvector embedding",
    )
    parser.add_argument(
        "--skip-graph",
        action="store_true",
        help="Skip Neo4j graph extraction",
    )

    args = parser.parse_args()
    docs_path = Path(args.docs).resolve()

    if not docs_path.is_dir():
        print(f"Error: {docs_path} is not a directory")
        sys.exit(1)

    stats = asyncio.run(
        run_ingestion(
            docs_path=docs_path,
            clean=args.clean,
            skip_embed=args.skip_embed,
            skip_graph=args.skip_graph,
        )
    )

    _print_report(stats)


if __name__ == "__main__":
    main()
