# GraphRAG PoC — Drug Interaction Knowledge Graph

Proof of Concept demonstrating that Knowledge Graphs (Neo4j) are technically
necessary for multi-hop reasoning that Vector RAG (pgvector) cannot perform.

**Domain:** Pharmaceutical drug interactions and patient safety.

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and fill in your database credentials and API keys
```

### 3. Run the API server

```bash
uvicorn agent.api:app --port 8058 --reload
```

### 4. Verify health

```bash
curl http://localhost:8058/health
```

**Expected response:**

```json
{"postgres": "ok", "neo4j": "ok", "llm": "ok"}
```

## Architecture

- **PostgreSQL + pgvector** (Neon) — document chunks and vector embeddings
- **Neo4j** (Aura Cloud) — knowledge graph of drug interactions
- **FastAPI** — async API server
- **Pydantic AI** — LLM agent with tool-gated retrieval modes
- **React + TypeScript** — frontend with graph visualization

See `PLANNING.md` for full architecture details and `TASK.md` for build phases.
