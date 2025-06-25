-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create highlight table
CREATE TABLE IF NOT EXISTS highlight (
    id INTEGER PRIMARY KEY,
    text VARCHAR NOT NULL,
    source_type VARCHAR NOT NULL,
    source_author VARCHAR,
    source_title VARCHAR,
    source_url VARCHAR,
    category VARCHAR,
    note VARCHAR,
    location INTEGER,
    highlighted_at VARCHAR,
    tags TEXT[],
    embedding halfvec(3072)
);

-- Create vector index for efficient similarity search
CREATE INDEX IF NOT EXISTS ix_highlight_embedding
ON highlight USING hnsw (embedding halfvec_l2_ops);

-- Create sync state table
CREATE TABLE IF NOT EXISTS syncstate (
    service VARCHAR PRIMARY KEY,
    last_synced_at TIMESTAMP
);
