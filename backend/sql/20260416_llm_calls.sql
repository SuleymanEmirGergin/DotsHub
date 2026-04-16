-- LLM NLU call log — tracks every LLM extraction attempt for observability and cost tracking.
-- Run this migration in the Supabase SQL editor or via psql.

CREATE TABLE IF NOT EXISTS llm_calls (
    id            bigserial PRIMARY KEY,
    session_id    uuid REFERENCES triage_sessions(session_id) ON DELETE SET NULL,
    provider      text,
    model         text,
    input_tokens  integer,
    output_tokens integer,
    latency_ms    integer,
    success       boolean,
    -- "timeout" | "schema_error" | "rate_limit" | "http_error" | "error" | NULL
    error_type    text,
    -- "llm" | "hybrid" | "llm_schema_error" | "llm_timeout" | "llm_rate_limit" | "llm_http_error" | "llm_error" | "deterministic"
    nlu_source    text,
    created_at    timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_llm_calls_created_at  ON llm_calls (created_at);
CREATE INDEX IF NOT EXISTS idx_llm_calls_success      ON llm_calls (success);
CREATE INDEX IF NOT EXISTS idx_llm_calls_session_id   ON llm_calls (session_id);

COMMENT ON TABLE llm_calls IS
  'Per-call log for LLM NLU extraction. Used for cost estimation and failure rate dashboards.';
COMMENT ON COLUMN llm_calls.nlu_source IS
  'Final NLU source after fallback logic: llm, hybrid, or deterministic variant.';
COMMENT ON COLUMN llm_calls.error_type IS
  'Failure category when success=false: timeout, schema_error, rate_limit, http_error, error.';
