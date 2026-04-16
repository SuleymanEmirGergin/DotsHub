-- Synonym suggestions: unrecognized symptoms captured by LLM NLU
-- Phrases that patients used but LLM couldn't map to a canonical.
-- Admins review these to grow synonyms_tr.json.

CREATE TABLE IF NOT EXISTS synonym_suggestions (
    id              bigserial PRIMARY KEY,
    phrase          text UNIQUE NOT NULL,
    count           integer NOT NULL DEFAULT 1,
    status          text NOT NULL DEFAULT 'pending',   -- pending | accepted | rejected
    suggested_canonical text,                          -- admin can fill in the canonical to add
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

-- For admin dashboard (most frequent first)
CREATE INDEX IF NOT EXISTS idx_synonym_suggestions_count ON synonym_suggestions (count DESC);
-- For filtering by review status
CREATE INDEX IF NOT EXISTS idx_synonym_suggestions_status ON synonym_suggestions (status);

-- Auto-update updated_at on row change (PostgreSQL only)
CREATE OR REPLACE FUNCTION update_synonym_suggestions_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_synonym_suggestions_updated_at ON synonym_suggestions;
CREATE TRIGGER trg_synonym_suggestions_updated_at
    BEFORE UPDATE ON synonym_suggestions
    FOR EACH ROW EXECUTE FUNCTION update_synonym_suggestions_updated_at();
