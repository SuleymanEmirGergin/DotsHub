-- Health-tourism partner clinic registry.
-- Replaces the read-only JSON file at backend/app/data/clinics.json with
-- a Supabase table so ops can:
--   - add a clinic without a code release
--   - soft-deactivate a partner instantly when the contract ends
--   - run RLS so only the admin role can mutate the catalog
--   - audit changes via Supabase's built-in audit features
--
-- The Python service `app.services.clinic_registry` reads this table
-- at runtime when SUPABASE_URL is configured AND the table exists with
-- rows; otherwise it falls back to clinics.json. This keeps local dev
-- and CI working without a database — no test fixtures needed.
--
-- Schema mirrors clinics.json field-for-field. The seed script
-- `scripts/seed_health_tourism_clinics.py` upserts every clinic from
-- the JSON file into this table — run it once on a fresh project to
-- bootstrap.
--
-- Run via Supabase SQL editor or psql.

CREATE TABLE IF NOT EXISTS health_tourism_clinics (
    id                       text PRIMARY KEY,
    name                     text NOT NULL,
    city                     text NOT NULL,
    country                  text NOT NULL DEFAULT 'TR',
    lat                      double precision,
    lon                      double precision,

    -- Arrays stored as jsonb so PostgREST surfaces them as JSON arrays
    -- without needing an explicit text[] cast on every read.
    certifications           jsonb NOT NULL DEFAULT '[]'::jsonb,
    languages                jsonb NOT NULL DEFAULT '[]'::jsonb,
    procedures_offered       jsonb NOT NULL DEFAULT '[]'::jsonb,
    package_features         jsonb NOT NULL DEFAULT '[]'::jsonb,
    specialties_strength     jsonb NOT NULL DEFAULT '[]'::jsonb,

    price_modifier           numeric(4, 2) NOT NULL DEFAULT 1.0
        CHECK (price_modifier >= 0.5 AND price_modifier <= 2.5),
    years_experience         integer NOT NULL DEFAULT 0
        CHECK (years_experience >= 0 AND years_experience <= 100),
    before_after_count       integer NOT NULL DEFAULT 0
        CHECK (before_after_count >= 0),
    average_rating_5         numeric(3, 2) NOT NULL DEFAULT 0.0
        CHECK (average_rating_5 >= 0.0 AND average_rating_5 <= 5.0),
    consult_response_hours   integer NOT NULL DEFAULT 24
        CHECK (consult_response_hours >= 0 AND consult_response_hours <= 168),

    -- Soft-delete: ops can deactivate a clinic without losing the row,
    -- so historical quotes referencing it stay traceable.
    is_active                boolean NOT NULL DEFAULT true,

    -- Catch-all for fields we add to clinics.json before allocating a
    -- column. Keeps the schema migration cadence loose.
    metadata                 jsonb NOT NULL DEFAULT '{}'::jsonb,

    created_at               timestamptz NOT NULL DEFAULT now(),
    updated_at               timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_health_tourism_clinics_active_city
    ON health_tourism_clinics (city)
    WHERE is_active = true;

-- Helps the quote engine's "clinics for procedure" query land on a
-- jsonb GIN index instead of a sequential scan once the table grows
-- past a few hundred rows.
CREATE INDEX IF NOT EXISTS idx_health_tourism_clinics_procedures
    ON health_tourism_clinics USING gin (procedures_offered);

-- Auto-bump updated_at so the registry's last-modified timestamp is
-- accurate without the seeder having to set it manually.
CREATE OR REPLACE FUNCTION health_tourism_clinics_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_health_tourism_clinics_updated_at
    ON health_tourism_clinics;
CREATE TRIGGER trg_health_tourism_clinics_updated_at
    BEFORE UPDATE ON health_tourism_clinics
    FOR EACH ROW EXECUTE FUNCTION health_tourism_clinics_set_updated_at();

COMMENT ON TABLE health_tourism_clinics IS
    'Partner clinic registry for /v1/quote and /v1/quote/itinerary. Source-of-truth at runtime when SUPABASE_URL is set; seeded from app/data/clinics.json by scripts/seed_health_tourism_clinics.py.';
COMMENT ON COLUMN health_tourism_clinics.is_active IS
    'Soft-delete flag. Set to false to remove the clinic from quotes without losing the row (so historical quote events still resolve clinic_id).';
COMMENT ON COLUMN health_tourism_clinics.price_modifier IS
    'Multiplier applied to procedures.price_band_eur.{low,mid,high}. Range 0.5-2.5 enforced at row insert.';
