# PLANNING.md — Full System Architecture

## Project Overview

**Name:** GraphRAG PoC — Drug Interaction Knowledge Graph  
**Purpose:** Live demo proving Knowledge Graphs are technically necessary for 
multi-hop reasoning that Vector RAG cannot perform.  
**Domain:** Pharmaceutical drug interactions, patient safety, enzyme pathways  
**Demo:** Ask the same patient safety question in Vector mode and Graph mode; 
show Vector giving an incomplete/wrong answer and Graph traversing the full 
chain to give the correct answer.

---

## The Core Demo (Never Lose Sight of This)

**Question:** "Patient PT-001 has Type 2 Diabetes and Hypertension and is 
currently taking Metformin and Lisinopril. Their doctor wants to prescribe 
Fluconazole for oral thrush. Is this safe?"

**Vector RAG fails because:**
- Retrieves chunks about Metformin, Fluconazole, and Lisinopril separately
- Cannot traverse: Fluconazole → inhibits → CYP2C9 → metabolizes → Warfarin
- Cannot check: Does PT-001 have Warfarin? No. Does PT-001 have Glipizide? No.
- Cannot traverse: Metformin → cleared by → OCT2/MATE (not CYP enzymes)
- Gives a vague answer about "potential interactions to discuss with doctor"

**Graph RAG succeeds because:**
- Traverses PT-001's full medication list
- Checks each drug against Fluconazole's inhibition profile
- Confirms Metformin uses OCT2/MATE pathway (not affected by Fluconazole)
- Confirms Lisinopril has no hepatic metabolism (not affected)
- Confirms Atorvastatin is CYP3A4 substrate but single dose Fluconazole is low risk
- Returns: SAFE with explicit reasoning chain

**Contrast case:** PT-005 has Glipizide (CYP2C9 substrate) — Fluconazole is DANGEROUS.
Same vector question, similar-sounding answer. Graph gives opposite verdict.

---

## Technology Stack

### Backend
- **Python:** 3.11
- **Web Framework:** FastAPI 0.111+
- **ASGI Server:** Uvicorn
- **AI Agent:** Pydantic AI
- **LLM:** OpenRouter (openai/gpt-4.1-mini for chat, openai/gpt-4.1-nano for ingestion)
- **Embeddings:** OpenRouter (openai/text-embedding-3-small, 1536 dimensions)
- **Vector Database:** PostgreSQL + pgvector (hosted on Neon)
- **Graph Database:** Neo4j (local, neo4j://127.0.0.1:7687)
- **HTTP Client:** httpx (async)

### Frontend
- **Framework:** React 18 + TypeScript
- **Build Tool:** Vite
- **Styling:** TailwindCSS
- **Graph Visualization:** react-force-graph-2d
- **State Management:** Zustand
- **HTTP Client:** Axios
- **Streaming:** EventSource (SSE)
- **Icons:** Lucide React

### Infrastructure
- **PostgreSQL:** Neon (serverless Postgres, connection pooling enabled)
- **Neo4j:** Local instance (neo4j://127.0.0.1:7687)
- **Package Management:** pip + requirements.txt / npm + package.json

---

## Project Structure

```
graphrag-poc/
│
├── CLAUDE.md                    # Cursor behavior instructions
├── PLANNING.md                  # This file — full architecture
├── TASK.md                      # Phase checklist
├── .cursorrules                 # Low-level Cursor coding rules
├── .env                         # Environment variables (gitignored)
├── .env.example                 # Environment variable template
├── requirements.txt             # Python dependencies
├── README.md                    # Setup and usage guide
│
├── documents/                   # Source documents for ingestion
│   ├── doc01_drug_registry.md
│   ├── doc02_enzyme_registry.md
│   ├── doc03_conditions_registry.md
│   ├── doc04_patient_records.md
│   ├── doc05_treatment_protocols.md
│   ├── doc06_drug_enzyme_interactions.md
│   ├── doc07_contraindications.md
│   ├── doc08_hospital_physician_registry.md
│   ├── doc09_manufacturer_supply_chain.md
│   ├── doc10_clinical_case_studies.md
│   ├── doc11_condition_drug_compatibility.md
│   └── doc12_demo_queries.md
│
├── config/
│   └── settings.py              # Pydantic Settings — all env vars
│
├── sql/
│   └── schema.sql               # PostgreSQL schema + functions
│
├── ingestion/
│   ├── __init__.py
│   ├── chunker.py               # Split documents into chunks
│   ├── embedder.py              # Embed chunks into pgvector
│   ├── graph_extractor.py       # LLM → JSON → Neo4j Cypher
│   ├── deduplicator.py          # Merge duplicate nodes in Neo4j
│   └── ingest.py                # Main pipeline runner (CLI)
│
├── db/
│   ├── __init__.py
│   ├── postgres.py              # asyncpg pool + repository
│   └── neo4j_client.py          # Neo4j async driver + repository
│
├── retrieval/
│   ├── __init__.py
│   ├── vector_retriever.py      # pgvector semantic search
│   └── graph_retriever.py       # Neo4j multi-hop traversal
│
├── agent/
│   ├── __init__.py
│   ├── models.py                # Pydantic models for API
│   ├── prompts.py               # System prompts
│   ├── tools.py                 # Pydantic AI tools
│   ├── agent.py                 # Pydantic AI agent definition
│   └── api.py                   # FastAPI application
│
├── ui/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── types/
│       │   └── index.ts         # TypeScript interfaces
│       ├── hooks/
│       │   ├── useChat.ts       # Chat streaming hook
│       │   └── useGraph.ts      # Graph data hook
│       ├── components/
│       │   ├── Sidebar.tsx      # Left sidebar
│       │   ├── ToolsPanel.tsx   # Right tools panel
│       │   ├── GraphViz.tsx     # Force graph visualization
│       │   ├── TraversalPath.tsx # Hop-by-hop path display
│       │   └── CompareView.tsx  # Side-by-side comparison
│       └── pages/
│           └── ChatPage.tsx     # Main chat interface
│
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_ingestion.py
    ├── test_vector_retriever.py
    ├── test_graph_retriever.py
    └── test_api.py
```

---

## Database Schemas

### PostgreSQL (pgvector)

```sql
-- Documents table
documents (
    id SERIAL PRIMARY KEY,
    filename TEXT UNIQUE NOT NULL,
    title TEXT,
    content TEXT NOT NULL,
    word_count INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
)

-- Chunks table with vector embedding
chunks (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id),
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536),
    token_count INTEGER,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
)

-- Indexes
chunks_embedding_idx: ivfflat on embedding (vector_cosine_ops)
chunks_content_trgm_idx: gin on content (gin_trgm_ops)

-- Functions
vector_search(query_embedding, match_count) → chunks with similarity
hybrid_search(query_embedding, query_text, match_count) → chunks with score
```

### Neo4j Graph Schema

#### Node Labels and Properties
```
(:Drug {name, brand_names, drug_class, fda_approval_year, 
        half_life_hours, protein_binding_pct, route})

(:Enzyme {name, full_name, family, location, 
          pct_drugs_metabolized, clinical_significance})

(:Transporter {name, full_name, classification, location, function})

(:Condition {name, icd10_code, classification, prevalence, 
             key_biomarker, complications})

(:Patient {patient_id, age, sex, weight_kg, gfr, hospital_id})

(:Physician {physician_id, name, specialty, hospital_id})

(:Pharmacist {pharmacist_id, name, role, hospital_id})

(:Hospital {hospital_id, name, type, location, bed_count})

(:Manufacturer {name, headquarters, type, revenue_2023_usd})

(:Protocol {protocol_id, name, issuing_body, version})

(:ClinicalCase {case_id, case_type, outcome, preventable})

(:Contraindication {interaction_id, severity, mechanism})
```

#### Relationship Types and Properties
```
(Drug)-[:INHIBITS {strength: "strong|moderate|weak"}]->(Enzyme)
(Drug)-[:INDUCES {strength}]->(Enzyme)
(Drug)-[:METABOLIZED_BY {percentage}]->(Enzyme)
(Drug)-[:CLEARED_BY]->(Transporter)
(Drug)-[:INHIBITS_TRANSPORTER]->(Transporter)
(Drug)-[:TREATS]->(Condition)
(Drug)-[:CONTRAINDICATED_WITH {severity, mechanism, interaction_id}]->(Drug)
(Drug)-[:INTERACTS_WITH {severity, mechanism, effect}]->(Drug)
(Drug)-[:CAUSES]->(Condition)
(Drug)-[:MANUFACTURED_BY]->(Manufacturer)
(Drug)-[:ALTERNATIVE_TO]->(Drug)
(Patient)-[:HAS_CONDITION]->(Condition)
(Patient)-[:PRESCRIBED {dose, frequency, start_date}]->(Drug)
(Patient)-[:TREATED_BY]->(Physician)
(Patient)-[:ADMITTED_TO]->(Hospital)
(Patient)-[:DOCUMENTED_IN]->(ClinicalCase)
(Physician)-[:WORKS_AT]->(Hospital)
(Pharmacist)-[:WORKS_AT]->(Hospital)
(Hospital)-[:FOLLOWS_PROTOCOL]->(Protocol)
(Protocol)-[:COVERS]->(Drug)
(ClinicalCase)-[:INVOLVES_PATIENT]->(Patient)
(ClinicalCase)-[:PRECIPITATED_BY]->(Drug)
(ClinicalCase)-[:PREVENTED_BY]->(Action)
(Enzyme)-[:METABOLIZES]->(Drug)  -- inverse of METABOLIZED_BY
(Condition)-[:INCREASES_RISK_OF]->(Condition)
(Manufacturer)-[:SUPPLIES]->(Drug)
```

#### Neo4j Indexes (create at startup)
```cypher
CREATE INDEX drug_name IF NOT EXISTS FOR (n:Drug) ON (n.name)
CREATE INDEX enzyme_name IF NOT EXISTS FOR (n:Enzyme) ON (n.name)
CREATE INDEX patient_id IF NOT EXISTS FOR (n:Patient) ON (n.patient_id)
CREATE INDEX condition_name IF NOT EXISTS FOR (n:Condition) ON (n.name)
CREATE INDEX manufacturer_name IF NOT EXISTS FOR (n:Manufacturer) ON (n.name)
CREATE INDEX hospital_id IF NOT EXISTS FOR (n:Hospital) ON (n.hospital_id)
```

---

## Graph Extraction Pipeline (Critical Detail)

### Step 1 — Chunking
- Chunk size: 800 tokens, overlap 150 tokens
- Preserve document title in each chunk's metadata
- Preserve chunk position (first/middle/last) in metadata

### Step 2 — LLM Extraction Prompt
Send each chunk to INGESTION_LLM_CHOICE (gpt-4.1-nano) with this prompt:

```
You are a medical knowledge graph extractor.
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
2. Node name property must match exactly as written in the text
3. Every relationship must have source_doc property
4. Do not invent relationships not stated in the text
5. Do not create nodes for vague concepts — only named entities

Text:
{chunk_text}
```

### Step 3 — Cypher Writing
For each extracted node and relationship:

```python
# Node creation (MERGE prevents duplicates)
MERGE (n:{label} {{name: $name}})
ON CREATE SET n += $properties, n.created_at = datetime()
ON MATCH SET n += $properties, n.updated_at = datetime()

# Relationship creation
MATCH (a {{name: $from_name}})
MATCH (b {{name: $to_name}})
MERGE (a)-[r:{rel_type}]->(b)
ON CREATE SET r += $properties, r.created_at = datetime()
ON MATCH SET r += $properties
```

### Step 4 — Deduplication Pass
After all documents ingested, run deduplication:
- Find nodes with similar names (fuzzy match, threshold 0.85)
- Examples: "CYP3A4" and "CYP 3A4" and "Cytochrome P450 3A4" → merge to "CYP3A4"
- Merge all relationships from duplicate onto canonical node
- Delete duplicate nodes
- Log all merges performed

---

## Retrieval Architecture

### Vector Retriever
```python
async def search(query: str, limit: int = 5) -> list[VectorResult]:
    1. Embed query using embedding API
    2. Call vector_search SQL function
    3. Return list of VectorResult(content, filename, similarity, chunk_id)
    
# Does NOT do relationship traversal
# Returns raw document chunks only
# Explicit in response metadata: "source: vector_search"
```

### Graph Retriever
```python
async def search(query: str, limit: int = 10) -> GraphResult:
    1. Extract entity names from query using LLM
    2. Find matching nodes in Neo4j (fuzzy name match)
    3. Run subgraph traversal up to 4 hops:
    
    MATCH (start)
    WHERE toLower(start.name) CONTAINS toLower($entity)
    CALL apoc.path.subgraphAll(start, {
        maxLevel: 4,
        relationshipFilter: "INHIBITS|METABOLIZED_BY|CLEARED_BY|
                            INTERACTS_WITH|CONTRAINDICATED_WITH|
                            HAS_CONDITION|PRESCRIBED|TREATS|CAUSES"
    })
    YIELD nodes, relationships
    RETURN nodes, relationships
    
    4. Format as readable fact strings:
       "Fluconazole -[INHIBITS]-> CYP2C9 -[METABOLIZES]-> Warfarin"
    5. Return GraphResult(facts, nodes, relationships, traversal_paths)

async def find_path(entity1: str, entity2: str) -> PathResult:
    MATCH path = shortestPath((a)-[*1..6]-(b))
    WHERE toLower(a.name) CONTAINS toLower($e1)
    AND toLower(b.name) CONTAINS toLower($e2)
    RETURN path,
           [n in nodes(path) | n.name] as names,
           [r in relationships(path) | type(r)] as rels
    LIMIT 3
```

---

## Agent Architecture

### Pydantic AI Agent
- Model: openai/gpt-4.1-mini via OpenRouter
- System prompt: In agent/prompts.py
- Tools: vector_search, graph_search, compare_approaches, find_path
- Mode gating: AgentDependencies.mode controls which tools are available
  - "vector" mode: only vector_search tool active
  - "graph" mode: only graph_search and find_path tools active
  - "agentic" mode: all tools active, agent decides
  - "compare" mode: runs both pipelines, returns structured comparison

### API Endpoints
```
POST /chat
  Body: {message, session_id, mode}
  Response: SSE stream of text deltas + tool usage events

GET /compare?q={query}
  Response: ComparisonResult {
    query, vector_result, graph_result, key_difference
  }

GET /graph/node/{name}
  Response: NodeWithRelationships {node, relationships, neighbors}

GET /graph/path?from={e1}&to={e2}
  Response: PathResult {path_nodes, path_rels, readable_path}

GET /graph/stats
  Response: GraphStats {node_count, rel_count, breakdown_by_label}

GET /health
  Response: {postgres: ok/error, neo4j: ok/error, llm: ok/error}
```

---

## Frontend Architecture

### Layout
```
┌─────────────────────────────────────────────────────────────┐
│ SIDEBAR (240px)  │  CHAT (flex)           │ TOOLS (320px)   │
│                  │                        │                  │
│ - Health check   │ [VECTOR] [GRAPH]       │ Tools used:      │
│ - Session        │ [COMPARE] tabs         │ > vector_search  │
│ - Mode selector  │                        │   {query: ...}   │
│ - Graph stats    │ Messages stream here   │ > graph_search   │
│ - Demo queries   │                        │   {facts: ...}   │
│   (clickable)    │ COMPARE MODE:          │                  │
│                  │ ┌──────────┬─────────┐ │ Graph viz:       │
│                  │ │ VECTOR   │ GRAPH   │ │ [force graph]    │
│                  │ │ (red)    │ (green) │ │                  │
│                  │ │ chunks   │ facts   │ │ Traversal path:  │
│                  │ │ answer   │ path    │ │ A→[REL]→B→[REL]→C│
│                  │ └──────────┴─────────┘ │                  │
└─────────────────────────────────────────────────────────────┘
```

### Compare Mode (Demo Centerpiece)
Left column (Vector):
- Header: "Vector RAG" in amber/red
- "Chunks retrieved: N"
- Chunk preview cards (doc name + first 100 chars)
- LLM answer
- "What it missed:" callout box

Right column (Graph):
- Header: "Graph RAG" in green
- "Facts retrieved: N"
- Traversal path: visual chain
  `[Fluconazole] →INHIBITS→ [CYP2C9] →METABOLIZES→ [Warfarin]`
- LLM answer
- "Why graph wins:" callout box

### Graph Visualization
- Library: react-force-graph-2d
- Node colors by type:
  - Drug: #6366f1 (indigo)
  - Enzyme: #f59e0b (amber)
  - Patient: #10b981 (emerald)
  - Condition: #ef4444 (red)
  - Physician: #3b82f6 (blue)
  - Hospital: #8b5cf6 (purple)
  - Manufacturer: #06b6d4 (cyan)
  - Protocol: #84cc16 (lime)
- Edge labels: relationship type
- Click node: expand/highlight its connections
- Highlight: traversal path from last graph query

---

## Environment Variables

```env
# PostgreSQL (Neon)
DATABASE_URL=postgresql://...

# Neo4j (local)
NEO4J_URI=neo4j://127.0.0.1:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=...

# LLM (OpenRouter)
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_API_KEY=sk-or-v1-...
LLM_CHOICE=openai/gpt-4.1-mini
INGESTION_LLM_CHOICE=openai/gpt-4.1-nano

# Embeddings (OpenRouter)
EMBEDDING_BASE_URL=https://openrouter.ai/api/v1
EMBEDDING_API_KEY=sk-or-v1-...
EMBEDDING_MODEL=openai/text-embedding-3-small
VECTOR_DIMENSION=1536

# App
APP_HOST=0.0.0.0
APP_PORT=8058
LOG_LEVEL=INFO

# Chunking
CHUNK_SIZE=800
CHUNK_OVERLAP=150
```

---

## Phase Completion Criteria

### Phase 1 Complete When:
- [ ] Both database connections verified healthy
- [ ] `python -c "from config.settings import settings; print(settings.model_dump())"` works
- [ ] `GET /health` returns `{postgres: "ok", neo4j: "ok"}`
- [ ] SQL schema applied, tables exist

### Phase 2 Complete When:
- [ ] `python ingestion/ingest.py --docs documents/ --clean` runs without errors
- [ ] PostgreSQL has 12 documents and 100+ chunks
- [ ] Neo4j has 400+ nodes and 600+ relationships
- [ ] `GET /graph/stats` returns node breakdown by label
- [ ] No node names contain `},{` or similar artifacts

### Phase 3 Complete When:
- [ ] `vector_retriever.search("fluconazole drug interaction")` returns 5 chunks
- [ ] `graph_retriever.search("fluconazole")` returns facts with traversal paths
- [ ] `graph_retriever.find_path("Fluconazole", "Warfarin")` returns path via CYP2C9

### Phase 4 Complete When:
- [ ] `POST /chat` with mode=vector returns answer using only vector_search
- [ ] `POST /chat` with mode=graph returns answer with traversal path
- [ ] `GET /compare?q=...` returns side-by-side results
- [ ] SSE streaming works for chat endpoint

### Phase 5 Complete When:
- [ ] UI loads at localhost:5173
- [ ] Vector mode shows chunks in tools panel
- [ ] Graph mode shows traversal path in tools panel
- [ ] Compare mode shows side-by-side columns
- [ ] Graph visualization renders nodes and edges
- [ ] Demo Query 1 (PT-001 safe) shows correct difference between modes
