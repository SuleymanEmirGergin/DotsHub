-- Health-tourism lead persistence.
--
-- Why this exists
--   Without persistence, /v1/quote/lead is fire-and-forget: the webhook
--   payload goes out (or fails), and we have no record. If the receiving
--   CRM is down or returns 5xx through retries, the lead is lost — the
--   patient submitted, the operator never sees it. This table is the
--   durable buffer between the patient action and the CRM.
--
-- Lifecycle
--   1. POST /v1/quote/lead → row inserted with webhook_status='pending'
--      BEFORE the webhook attempt. So even if the webhook layer crashes,
--      the lead is captured.
--   2. lead_dispatcher.dispatch() returns → row updated with
--      webhook_status (one of: delivered / failed_4xx /
--      failed_exhausted / not_configured) + webhook_delivered_at.
--   3. Patient triggers KVKK silme via DELETE /v1/me/leads/{id} →
--      is_deleted=true (soft-delete; we keep the row for audit but
--      contact + notes are nulled out).
--
-- Why soft-delete
--   Sağlık Turizmi Yönetmeliği Madde 10 requires 5-year retention of
--   lead records. KVKK silme hakkı means we erase contact PII; the row
--   itself stays so the operator can prove "we received this lead and
--   handled it" if questioned by the regulator.
--
-- Run via Supabase SQL editor or psql.

CREATE TABLE IF NOT EXISTS health_tourism_leads (
    id                       text PRIMARY KEY,
    session_id               text NOT NULL,

    -- The QUOTE envelope this lead accepts. NULL is allowed for
    -- now (legacy clients may not send it) but new clients should
    -- always populate it so the operator can trace which exact
    -- price/clinic combination was on offer.
    quote_id                 text,

    procedure_id             text NOT NULL,
    clinic_id                text NOT NULL,

    -- KVKK consent gate. When false, contact is NULL — we never
    -- store identifying info without explicit consent.
    consent_to_share         boolean NOT NULL DEFAULT false,
    contact                  jsonb,
    notes                    text NOT NULL DEFAULT '',
    locale                   text NOT NULL DEFAULT 'tr-TR',
    quoted_price_eur         integer,

    -- Webhook delivery state machine.
    webhook_status           text NOT NULL DEFAULT 'pending'
        CHECK (webhook_status IN (
            'pending',
            'delivered',
            'failed_4xx',
            'failed_exhausted',
            'not_configured',
            'errored'
        )),
    webhook_attempted_at     timestamptz,
    webhook_delivered_at     timestamptz,
    webhook_response_snippet text,

    -- KVKK silme hakkı: soft-delete keeps the row for the regulator's
    -- 5-year retention requirement while erasing PII.
    is_deleted               boolean NOT NULL DEFAULT false,
    deleted_at               timestamptz,

    created_at               timestamptz NOT NULL DEFAULT now(),
    updated_at               timestamptz NOT NULL DEFAULT now()
);

-- Time-series query patterns: "leads created in the last N days",
-- "leads still pending", "leads accepted by clinic X".
CREATE INDEX IF NOT EXISTS idx_health_tourism_leads_created
    ON health_tourism_leads (created_at DESC)
    WHERE is_deleted = false;
CREATE INDEX IF NOT EXISTS idx_health_tourism_leads_pending
    ON health_tourism_leads (created_at)
    WHERE webhook_status = 'pending' AND is_deleted = false;
CREATE INDEX IF NOT EXISTS idx_health_tourism_leads_clinic
    ON health_tourism_leads (clinic_id, created_at DESC)
    WHERE is_deleted = false;

CREATE OR REPLACE FUNCTION health_tourism_leads_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_health_tourism_leads_updated_at
    ON health_tourism_leads;
CREATE TRIGGER trg_health_tourism_leads_updated_at
    BEFORE UPDATE ON health_tourism_leads
    FOR EACH ROW EXECUTE FUNCTION health_tourism_leads_set_updated_at();

COMMENT ON TABLE health_tourism_leads IS
    'Durable lead record for /v1/quote/lead. Persisted before webhook dispatch so a failed CRM never loses a lead. is_deleted=true means KVKK silme exercised; contact/notes nulled but row kept 5 years per Sağlık Turizmi Yönetmeliği Madde 10.';
COMMENT ON COLUMN health_tourism_leads.consent_to_share IS
    'KVKK Madde 6/2 açık rıza. False ise contact JSONB NULL kalır — operatör sadece session_id ile takip edebilir.';
COMMENT ON COLUMN health_tourism_leads.webhook_status IS
    'Webhook delivery state machine. pending → delivered | failed_4xx | failed_exhausted | not_configured | errored.';
