-- GraphRAG PostgreSQL Schema
-- Extensions, tables, indexes, and search functions

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Documents table
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    filename TEXT UNIQUE NOT NULL,
    title TEXT,
    content TEXT NOT NULL,
    word_count INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Chunks table with vector embedding
CREATE TABLE IF NOT EXISTS chunks (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536),
    token_count INTEGER,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

-- IVFFlat index for approximate nearest-neighbor search on embeddings
CREATE INDEX IF NOT EXISTS chunks_embedding_idx
    ON chunks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- GIN trigram index for full-text / fuzzy search on chunk content
CREATE INDEX IF NOT EXISTS chunks_content_trgm_idx
    ON chunks USING gin (content gin_trgm_ops);

-- vector_search: pure cosine-similarity search
CREATE OR REPLACE FUNCTION vector_search(
    query_embedding vector(1536),
    match_count INTEGER DEFAULT 5
)
RETURNS TABLE (
    id INTEGER,
    document_id INTEGER,
    chunk_index INTEGER,
    content TEXT,
    token_count INTEGER,
    metadata JSONB,
    similarity FLOAT
)
LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id,
        c.document_id,
        c.chunk_index,
        c.content,
        c.token_count,
        c.metadata,
        1 - (c.embedding <=> query_embedding) AS similarity
    FROM chunks c
    WHERE c.embedding IS NOT NULL
    ORDER BY c.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Session and message tables for chat history
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT NOW(),
    last_active TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    session_id TEXT REFERENCES sessions(id),
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    mode TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

-- hybrid_search: combines vector similarity with trigram text matching
CREATE OR REPLACE FUNCTION hybrid_search(
    query_embedding vector(1536),
    query_text TEXT,
    match_count INTEGER DEFAULT 5,
    vector_weight FLOAT DEFAULT 0.7,
    text_weight FLOAT DEFAULT 0.3
)
RETURNS TABLE (
    id INTEGER,
    document_id INTEGER,
    chunk_index INTEGER,
    content TEXT,
    token_count INTEGER,
    metadata JSONB,
    score FLOAT
)
LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id,
        c.document_id,
        c.chunk_index,
        c.content,
        c.token_count,
        c.metadata,
        (
            vector_weight * (1 - (c.embedding <=> query_embedding))
            + text_weight * COALESCE(similarity(c.content, query_text), 0)
        ) AS score
    FROM chunks c
    WHERE c.embedding IS NOT NULL
    ORDER BY score DESC
    LIMIT match_count;
END;
$$;
