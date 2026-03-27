# TASK.md — Phase Checklist

## How to Use This File
- Before starting any work, read the current phase
- Check off tasks as you complete them using [x]
- Do not start Phase N+1 until Phase N is fully checked off
- After completing a phase, update "Current Phase" below
- If you encounter a blocking issue, document it under "Blockers"

---

## Current Phase: 1 — Foundation

---

## Phase 1 — Foundation and Database Setup
**Goal:** Both databases connected, schemas applied, health check passing

### Tasks
- [x] Create project folder structure exactly as defined in PLANNING.md
- [x] Create requirements.txt with all dependencies
- [x] Create .env.example with all required variables
- [x] Create config/settings.py using Pydantic Settings
- [x] Create sql/schema.sql with all tables, indexes, and functions
- [x] Create db/postgres.py with asyncpg pool and basic repository
- [x] Create db/neo4j_client.py with async driver and index creation
- [x] Create agent/api.py with just the /health endpoint
- [x] Verify PostgreSQL connection works (asyncpg connects to Neon)
- [x] Verify Neo4j connection works (driver connects to Aura Cloud)
- [x] Apply SQL schema to PostgreSQL
- [x] Create Neo4j indexes
- [x] Run health check: GET /health returns {postgres: "ok", neo4j: "ok", llm: "ok"}

### Verification Command
```bash
uvicorn agent.api:app --port 8058 --reload
curl http://localhost:8058/health
# Expected: {"postgres": "ok", "neo4j": "ok", "llm": "ok"}
```

### Files to Create
- requirements.txt
- .env.example
- config/__init__.py
- config/settings.py
- sql/schema.sql
- db/__init__.py
- db/postgres.py
- db/neo4j_client.py
- agent/__init__.py
- agent/api.py (health endpoint only)

---

## Phase 2 — Ingestion Pipeline
**Goal:** All 12 documents ingested into both pgvector and Neo4j with 400+ nodes

### Prerequisites
- Phase 1 fully complete
- 12 documents present in documents/ folder

### Tasks
- [ ] Create ingestion/__init__.py
- [ ] Create ingestion/chunker.py
  - [ ] Load markdown files from documents/
  - [ ] Split by token count (800 tokens, 150 overlap)
  - [ ] Preserve filename and title in chunk metadata
  - [ ] Test: python -c "from ingestion.chunker import chunk_document; ..."
- [ ] Create ingestion/embedder.py
  - [ ] Connect to OpenRouter embedding API
  - [ ] Batch embed chunks (batch size 20)
  - [ ] Write chunks + embeddings to PostgreSQL
  - [ ] Skip already-embedded documents (check by filename)
  - [ ] Test embedding API call works
- [ ] Create ingestion/graph_extractor.py
  - [ ] LLM extraction prompt (exactly as in PLANNING.md)
  - [ ] JSON parsing with error handling
  - [ ] Node name cleaning (remove special chars)
  - [ ] MERGE nodes into Neo4j (no duplicates)
  - [ ] CREATE relationships with properties
  - [ ] Retry on LLM failure (3 attempts, exponential backoff)
  - [ ] Log extraction stats per document
- [ ] Create ingestion/deduplicator.py
  - [ ] Find nodes with similar names (fuzzy match)
  - [ ] Merge duplicate nodes
  - [ ] Report merges performed
- [ ] Create ingestion/ingest.py (CLI runner)
  - [ ] --docs flag for documents folder
  - [ ] --clean flag to wipe both databases
  - [ ] --skip-embed flag
  - [ ] --skip-graph flag
  - [ ] Progress bar for document processing
  - [ ] Final stats report
- [ ] Run full ingestion: python ingestion/ingest.py --docs documents/ --clean
- [ ] Verify: 12 documents in PostgreSQL
- [ ] Verify: 100+ chunks in PostgreSQL
- [ ] Verify: 400+ nodes in Neo4j
- [ ] Verify: 600+ relationships in Neo4j
- [ ] Verify: No malformed node names (no `},{` artifacts)
- [ ] Verify: GET /graph/stats returns correct counts

### Verification Commands
```bash
python ingestion/ingest.py --docs documents/ --clean
# Expected output:
# Documents processed: 12
# Chunks created: ~150
# Nodes created: ~450
# Relationships created: ~700
# Duplicates merged: ~30

curl http://localhost:8058/graph/stats
# Expected: breakdown of nodes by label
```

### Files to Create
- ingestion/__init__.py
- ingestion/chunker.py
- ingestion/embedder.py
- ingestion/graph_extractor.py
- ingestion/deduplicator.py
- ingestion/ingest.py

---

## Phase 3 — Retrieval Layer
**Goal:** Both retrievers working and returning meaningfully different results

### Prerequisites
- Phase 2 fully complete
- Data verified in both databases

### Tasks
- [ ] Create retrieval/__init__.py
- [ ] Create retrieval/vector_retriever.py
  - [ ] Embed query
  - [ ] Call vector_search SQL function
  - [ ] Return VectorResult list with similarity scores
  - [ ] Test: search("fluconazole drug interaction") returns 5 chunks
- [ ] Create retrieval/graph_retriever.py
  - [ ] Extract entities from query using LLM
  - [ ] Find matching Neo4j nodes
  - [ ] Run subgraph traversal (4 hops)
  - [ ] Format traversal paths as readable strings
  - [ ] Return GraphResult with facts and paths
  - [ ] Implement find_path for entity-to-entity shortest path
  - [ ] Test: search("fluconazole") returns facts including CYP2C9 relationship
  - [ ] Test: find_path("Fluconazole", "Warfarin") returns path via CYP2C9
- [ ] Write test script retrieval/test_retrievers.py
  - [ ] Run Demo Query 1 through both retrievers
  - [ ] Print side-by-side comparison to console
  - [ ] Confirm vector returns chunks, graph returns traversal path

### Verification Commands
```bash
python retrieval/test_retrievers.py
# Expected: vector returns 5 chunks, graph returns fact chain including
# "Fluconazole -[INHIBITS]-> CYP2C9 -[METABOLIZES]-> Warfarin"
```

### Files to Create
- retrieval/__init__.py
- retrieval/vector_retriever.py
- retrieval/graph_retriever.py
- retrieval/test_retrievers.py

---

## Phase 4 — Agent and API
**Goal:** Full API working with all endpoints, streaming chat, compare mode

### Prerequisites
- Phase 3 fully complete
- Both retrievers tested and working

### Tasks
- [ ] Create agent/models.py (all Pydantic models)
- [ ] Create agent/prompts.py (system prompt)
- [ ] Create agent/tools.py
  - [ ] vector_search tool
  - [ ] graph_search tool
  - [ ] compare_approaches tool
  - [ ] find_path tool
- [ ] Create agent/agent.py
  - [ ] Pydantic AI agent definition
  - [ ] Mode-based tool gating
  - [ ] AgentDependencies dataclass
- [ ] Expand agent/api.py
  - [ ] POST /chat with SSE streaming
  - [ ] GET /compare endpoint
  - [ ] GET /graph/node/{name}
  - [ ] GET /graph/path
  - [ ] GET /graph/stats (already in Phase 1 stub)
  - [ ] Session management
  - [ ] CORS configuration for UI
- [ ] Test POST /chat with mode=vector
- [ ] Test POST /chat with mode=graph (must show traversal in response)
- [ ] Test GET /compare with Demo Query 1
- [ ] Verify compare shows different answers for vector vs graph

### Verification Commands
```bash
curl -X POST http://localhost:8058/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Is Fluconazole safe for PT-001?", "mode": "vector"}'

curl "http://localhost:8058/compare?q=Is+Fluconazole+safe+for+PT-001"
# Vector answer should be vague; Graph answer should cite specific pathway
```

### Files to Create/Expand
- agent/models.py
- agent/prompts.py
- agent/tools.py
- agent/agent.py
- agent/api.py (expand from Phase 1)

---

## Phase 5 — Frontend
**Goal:** React UI with all 3 modes working, graph visualization, demo-ready

### Prerequisites
- Phase 4 fully complete
- API tested and stable

### Tasks
- [ ] Initialize Vite + React + TypeScript project in ui/
- [ ] Install dependencies: tailwindcss, react-force-graph-2d, zustand, axios, lucide-react
- [ ] Configure TailwindCSS
- [ ] Configure Vite proxy to API (port 8058)
- [ ] Create ui/src/types/index.ts (all TypeScript interfaces)
- [ ] Create ui/src/hooks/useChat.ts (SSE streaming hook)
- [ ] Create ui/src/hooks/useGraph.ts (graph data fetching)
- [ ] Create ui/src/components/Sidebar.tsx
  - [ ] Health indicator
  - [ ] Session info
  - [ ] Mode selector (Vector / Graph / Compare / Agentic)
  - [ ] Graph stats
  - [ ] Demo queries (5 clickable preset queries)
- [ ] Create ui/src/components/ToolsPanel.tsx
  - [ ] Tool calls list (name + JSON)
  - [ ] Graph visualization (react-force-graph-2d)
  - [ ] Traversal path display
- [ ] Create ui/src/components/GraphViz.tsx
  - [ ] Force-directed graph
  - [ ] Node colors by type
  - [ ] Edge labels
  - [ ] Click to expand
- [ ] Create ui/src/components/TraversalPath.tsx
  - [ ] Visual hop chain: [Node] →REL→ [Node] →REL→ [Node]
- [ ] Create ui/src/components/CompareView.tsx
  - [ ] Two-column layout
  - [ ] Left: Vector (amber theme)
  - [ ] Right: Graph (green theme)
  - [ ] Loading states
  - [ ] Diff highlighting
- [ ] Create ui/src/pages/ChatPage.tsx
  - [ ] Tab switcher
  - [ ] Chat input + send
  - [ ] Message list with streaming
  - [ ] Compare mode renders CompareView
- [ ] Create ui/src/App.tsx
- [ ] Test: UI loads at localhost:5173
- [ ] Test: Vector mode sends message, receives streaming response
- [ ] Test: Graph mode shows traversal path in right panel
- [ ] Test: Compare mode shows two columns with different answers
- [ ] Test: Click Demo Query 1 (PT-001 safe) fills input and submits
- [ ] Test: Graph visualization renders after graph query

### Verification
- Open http://localhost:5173
- Click "Demo Query 1" in sidebar
- Switch to Compare mode
- Submit query
- Left column shows chunks + vague answer
- Right column shows traversal chain + specific answer

---

## Blockers
_Document any blocking issues here during development_

---

## Completed Phases
_Move phases here when complete_
