# CLAUDE.md — Cursor Agent Behavior Instructions

## Project Identity
This is a **GraphRAG Proof of Concept** system for a live demo proving that 
Knowledge Graphs (Neo4j) are technically necessary for multi-hop reasoning 
that Vector RAG (pgvector) cannot perform. The domain is pharmaceutical 
drug interactions and patient safety.

## Critical Rules — Never Violate These

### 1. Never Hallucinate Imports
Only import libraries that are in requirements.txt. If you need a new library,
add it to requirements.txt first, then import it.

### 2. Never Skip Error Handling
Every database call, LLM call, and file operation must be wrapped in try/except.
Log the error with full context. Never use bare `except:` — always catch specific
exceptions or at minimum `except Exception as e`.

### 3. Never Hardcode Credentials
All credentials come from environment variables via `.env`. Use `python-dotenv`.
Never write a connection string, API key, or password directly in code.

### 4. Always Verify Before Assuming
Before writing code that calls a function from another module, check that the
function exists and has the expected signature. Do not assume.

### 5. Never Leave TODOs in Production Code
If something is not implemented, raise `NotImplementedError` with a clear message.
Do not write `# TODO: implement this` and leave it empty.

### 6. One Responsibility Per File
Each file does one thing. `embedder.py` only embeds. `graph_extractor.py` only
extracts graph data. `api.py` only handles HTTP. Do not mix concerns.

### 7. Always Test the Connection First
At startup, every module that connects to a database must verify the connection
before proceeding. If connection fails, raise a clear error with the connection
string (masked) and the failure reason.

### 8. Async All The Way
This project uses FastAPI and async Python throughout. Never use synchronous
database calls inside async functions. Use `asyncpg` for PostgreSQL,
`neo4j` async driver for Neo4j, `httpx` or `aiohttp` for HTTP calls.

### 9. Never Truncate Code
When writing a function, write the complete function. Never write
`# ... rest of implementation` or `# similar to above`. Complete every function.

### 10. Confirm Phase Completion
After completing each phase, print a clear summary:
- What was built
- What files were created/modified
- What to run to verify it works
- What the expected output is

---

## Code Style

### Python
- Python 3.11+
- Type hints on every function signature
- Pydantic models for all data structures passed between modules
- Dataclasses for internal-only structures
- f-strings for string formatting
- Pathlib for file paths, never os.path
- Black formatting (88 char line length)
- Docstrings on every public function (one-line minimum)

### TypeScript/React
- TypeScript strict mode
- Functional components only, no class components
- Custom hooks for all API calls
- TailwindCSS for all styling, no inline styles
- No `any` types — define proper interfaces

### Naming Conventions
- Python files: snake_case
- Python functions: snake_case
- Python classes: PascalCase
- React components: PascalCase
- React hooks: camelCase starting with `use`
- Constants: UPPER_SNAKE_CASE
- Environment variables: UPPER_SNAKE_CASE

---

## Architecture Patterns to Follow

### Repository Pattern for Database Access
Never write raw SQL or Cypher inside API route handlers or agent tools.
All database operations go through repository classes:
```python
# Good
chunks = await chunk_repository.search_by_embedding(query_embedding, limit=5)

# Bad
chunks = await db.fetch("SELECT * FROM chunks ORDER BY ...")
```

### Dependency Injection for FastAPI
Use FastAPI's `Depends()` for all database connections and services.
Never instantiate database connections inside route handlers.

### Pydantic for All Inputs and Outputs
Every API endpoint input and output must be a Pydantic model.
No raw dicts passed between layers.

### Structured Logging
Use Python's `logging` module with structured format:
```python
logger = logging.getLogger(__name__)
logger.info("Graph extraction complete", extra={
    "nodes_created": 45,
    "relationships_created": 123,
    "document": "doc01_drug_registry.md"
})
```

---

## Database Patterns

### PostgreSQL (asyncpg)
- Use connection pooling (min 2, max 10 connections)
- Always use parameterized queries — never string concatenation in SQL
- Use transactions for multi-step writes
- Close connections in finally blocks or use async context managers

### Neo4j
- Use MERGE not CREATE for nodes (prevents duplicates)
- Always index node properties used in WHERE clauses
- Use parameters in Cypher — never string concatenation
- Batch relationship creation for performance
- Use async driver

### LLM Calls
- Always set a timeout (30 seconds minimum)
- Retry on rate limit errors with exponential backoff (max 3 retries)
- Parse JSON responses in try/except — LLMs sometimes return malformed JSON
- Log the raw response before parsing for debugging

---

## Graph Extraction Rules (Critical)

The graph extractor is the most important component. Follow these rules:

### Node Deduplication
When creating nodes, ALWAYS use MERGE with the `name` property as the key:
```cypher
MERGE (n:Drug {name: $name})
ON CREATE SET n += $properties
ON MATCH SET n += $properties
```

### Clean Node Names
Before creating any node, clean the name:
- Strip leading/trailing whitespace
- Remove special characters that break Cypher: `{`, `}`, `,`
- Normalize case for matching (store original, match on lowercase)
- Never create a node with an empty name

### Relationship Properties
Every relationship must have at minimum:
- `source_doc`: the filename it was extracted from
- `confidence`: float 0 to 1 from LLM extraction
- `created_at`: timestamp

### Valid Node Labels (Use ONLY these)
- Drug
- Enzyme
- Transporter
- Condition
- Patient
- Physician
- Pharmacist
- Hospital
- Manufacturer
- Protocol
- ClinicalCase
- Contraindication
- TreatmentInteraction

### Valid Relationship Types (Use ONLY these)
- PRESCRIBED_TO / PRESCRIBED (Drug-Patient)
- INHIBITS / INDUCES (Drug/Enzyme relationships)
- METABOLIZED_BY (Drug-Enzyme)
- CLEARED_BY (Drug-Transporter)
- HAS_CONDITION (Patient-Condition)
- TREATS (Drug-Condition)
- CONTRAINDICATED_WITH (Drug-Drug)
- INTERACTS_WITH (Drug-Drug, bidirectional)
- INCREASES_RISK_OF (Drug/Condition-Condition)
- CAUSES (Drug-Condition/Event)
- MANUFACTURED_BY (Drug-Manufacturer)
- TREATED_BY (Patient-Physician)
- ADMITTED_TO (Patient-Hospital)
- FOLLOWS_PROTOCOL (Hospital/Physician-Protocol)
- REQUIRES (Protocol-Action)
- DOCUMENTS (ClinicalCase-Patient)
- PREVENTED_BY (Event-Action)
- SUPPLIED_BY (Drug-Manufacturer)
- WORKS_AT (Physician/Pharmacist-Hospital)
- REVIEWED_BY (Prescription-Pharmacist)
- ALTERNATIVE_TO (Drug-Drug)

---

## What to Build — Phase Reference

See PLANNING.md for complete architecture.
See TASK.md for current phase and checklist.

## Environment Variables Reference
All defined in .env — see .env.example for all required variables.
Never access os.environ directly — always use settings object from config.py.

---

## When You Are Stuck

1. Re-read PLANNING.md for architectural context
2. Check TASK.md for what phase you are in
3. Look at existing files for patterns already established
4. Never guess at database schemas — read sql/schema.sql
5. Never guess at graph schema — read the Valid Node Labels section above
6. If an approach is not working after 2 attempts, try a fundamentally different approach
7. Always prefer simple working code over complex broken code
