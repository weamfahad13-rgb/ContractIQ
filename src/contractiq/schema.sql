CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS contracts (
    id            SERIAL PRIMARY KEY,
    title         TEXT UNIQUE NOT NULL,
    source        TEXT NOT NULL,              -- 'cuad' or 'synthetic'
    contract_type TEXT NOT NULL,
    language      TEXT NOT NULL DEFAULT 'en', -- 'en' or 'ar'
    supplier      TEXT,
    start_date    DATE,
    end_date      DATE,
    full_text     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
    id          SERIAL PRIMARY KEY,
    contract_id INT NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
    ord         INT NOT NULL,
    heading     TEXT NOT NULL,
    text        TEXT NOT NULL,
    start_char  INT NOT NULL,                 -- offsets into contracts.full_text
    end_char    INT NOT NULL,
    language    TEXT NOT NULL DEFAULT 'en',
    embedding   vector(1024),
    -- Arabic has no Postgres stemmer, so it gets the language-neutral 'simple' config.
    tsv tsvector GENERATED ALWAYS AS (
        CASE WHEN language = 'ar' THEN to_tsvector('simple'::regconfig, heading || ' ' || text)
             ELSE to_tsvector('english'::regconfig, heading || ' ' || text) END
    ) STORED,
    UNIQUE (contract_id, ord)
);

CREATE INDEX IF NOT EXISTS chunks_tsv_idx ON chunks USING gin (tsv);
CREATE INDEX IF NOT EXISTS chunks_embedding_idx ON chunks USING hnsw (embedding vector_cosine_ops);

-- Procurement data for the Text-to-SQL path.
CREATE TABLE IF NOT EXISTS suppliers (
    id       SERIAL PRIMARY KEY,
    name     TEXT UNIQUE NOT NULL,
    country  TEXT NOT NULL,
    category TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS purchase_orders (
    id            SERIAL PRIMARY KEY,
    po_number     TEXT UNIQUE NOT NULL,
    supplier_id   INT NOT NULL REFERENCES suppliers(id),
    contract_id   INT REFERENCES contracts(id),
    order_date    DATE NOT NULL,
    promised_date DATE NOT NULL,
    delivered_date DATE,                      -- NULL while still open
    amount_sar    NUMERIC(12, 2) NOT NULL,
    status        TEXT NOT NULL               -- 'open', 'delivered', 'cancelled'
);
