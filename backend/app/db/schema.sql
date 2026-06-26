-- =============================================================================
-- RetailIQ GIS – PostGIS Schema
-- =============================================================================
-- Run order: extensions → enums → core tables → indexes
-- All geometry columns use EPSG:4326 (WGS 84)
-- =============================================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm; -- for text search on layer names

-- =============================================================================
-- ENUMS
-- =============================================================================

CREATE TYPE data_confidence AS ENUM ('high', 'medium', 'low', 'unknown');
CREATE TYPE layer_type AS ENUM ('polygon', 'point', 'linestring', 'multipolygon', 'multipoint', 'multilinestring');
CREATE TYPE import_status AS ENUM ('pending', 'validating', 'valid', 'invalid', 'imported', 'failed');
CREATE TYPE validation_severity AS ENUM ('error', 'warning', 'info');
CREATE TYPE run_status AS ENUM ('queued', 'running', 'complete', 'partial', 'failed');
CREATE TYPE override_entity AS ENUM ('site', 'factor', 'layer', 'analysis_weight');

-- =============================================================================
-- DATASETS — registered data source instances
-- =============================================================================

CREATE TABLE datasets (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id       VARCHAR(64) NOT NULL,          -- matches data-source-registry.md
    name            TEXT NOT NULL,
    description     TEXT,
    layer_type      layer_type NOT NULL,
    feature_count   INTEGER,
    vintage_year    SMALLINT,                       -- e.g. 2023 for ACS 2019-2023
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    confidence      data_confidence NOT NULL DEFAULT 'unknown',
    bbox            GEOMETRY(POLYGON, 4326),        -- spatial extent of dataset
    srs_original    VARCHAR(32),                   -- original projection, e.g. EPSG:4269
    metadata        JSONB NOT NULL DEFAULT '{}',   -- source-specific fields
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    is_archived     BOOLEAN NOT NULL DEFAULT FALSE -- archived datasets are read-only but queryable
);

CREATE INDEX idx_datasets_source_id ON datasets (source_id);
CREATE INDEX idx_datasets_ingested_at ON datasets (ingested_at DESC);
CREATE INDEX idx_datasets_vintage ON datasets (vintage_year);

-- =============================================================================
-- LAYERS — individual feature collections within a dataset
-- =============================================================================

CREATE TABLE layers (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    dataset_id      UUID NOT NULL REFERENCES datasets(id) ON DELETE RESTRICT,
    name            TEXT NOT NULL,
    layer_type      layer_type NOT NULL,
    feature_count   INTEGER,
    import_status   import_status NOT NULL DEFAULT 'pending',
    import_error    TEXT,                          -- last import error if status=failed
    confidence      data_confidence NOT NULL DEFAULT 'unknown',
    vintage_year    SMALLINT,
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata        JSONB NOT NULL DEFAULT '{}'
);

CREATE INDEX idx_layers_dataset_id ON layers (dataset_id);
CREATE INDEX idx_layers_status ON layers (import_status);

-- =============================================================================
-- LAYER FEATURES — geometry rows (one table for all layers)
-- =============================================================================

CREATE TABLE layer_features (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    layer_id        UUID NOT NULL REFERENCES layers(id) ON DELETE CASCADE,
    geom            GEOMETRY(GEOMETRY, 4326) NOT NULL,
    attributes      JSONB NOT NULL DEFAULT '{}',  -- all non-geometry fields
    source_id       VARCHAR(64),                  -- original source identifier
    confidence      data_confidence NOT NULL DEFAULT 'unknown',
    vintage_year    SMALLINT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_layer_features_layer_id ON layer_features (layer_id);
CREATE INDEX idx_layer_features_geom ON layer_features USING GIST (geom);
CREATE INDEX idx_layer_features_attributes ON layer_features USING GIN (attributes);

-- =============================================================================
-- LAYER VALIDATION RESULTS — row-level validation output
-- =============================================================================

CREATE TABLE layer_validation_results (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    layer_id        UUID NOT NULL REFERENCES layers(id) ON DELETE CASCADE,
    row_index       INTEGER,                       -- NULL means dataset-level check
    severity        validation_severity NOT NULL,
    rule_name       VARCHAR(128) NOT NULL,
    message         TEXT NOT NULL,
    raw_value       TEXT,                          -- offending value if applicable
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_validation_layer_id ON layer_validation_results (layer_id);
CREATE INDEX idx_validation_severity ON layer_validation_results (severity);

-- =============================================================================
-- ANALYSIS RUNS — reproducible analysis snapshots
-- =============================================================================

CREATE TABLE analysis_runs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    analyst_id      VARCHAR(128) NOT NULL DEFAULT 'system',
    city_name       VARCHAR(128) NOT NULL,
    study_bbox      GEOMETRY(POLYGON, 4326),
    weights         JSONB NOT NULL,               -- factor weights used
    dataset_snapshot JSONB NOT NULL,              -- {layer_id: ingested_at} map
    run_status      run_status NOT NULL DEFAULT 'queued',
    partial_reason  TEXT,                         -- set if status=partial
    error_message   TEXT,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_runs_status ON analysis_runs (run_status);
CREATE INDEX idx_runs_created_at ON analysis_runs (created_at DESC);

-- =============================================================================
-- DATASET VERSIONS — point-in-time locks of a dataset's layer state
-- Each analysis run references a specific version so results are reproducible.
-- =============================================================================

CREATE TABLE dataset_versions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    dataset_id      UUID NOT NULL REFERENCES datasets(id) ON DELETE RESTRICT,
    version_tag     VARCHAR(64) NOT NULL,              -- e.g. "v1", "2024-Q4", or analyst-supplied label
    layer_snapshot  JSONB NOT NULL,                    -- {layer_id: {ingested_at, feature_count, confidence}}
    created_by      VARCHAR(128) NOT NULL DEFAULT 'system',
    locked_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notes           TEXT
);

CREATE UNIQUE INDEX idx_dataset_versions_tag ON dataset_versions (dataset_id, version_tag);
CREATE INDEX idx_dataset_versions_dataset ON dataset_versions (dataset_id, locked_at DESC);



-- =============================================================================
-- CANDIDATE SITES — scored potential retail locations
-- =============================================================================

CREATE TABLE candidate_sites (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id              UUID NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
    rank                INTEGER,
    geom                GEOMETRY(POINT, 4326) NOT NULL,
    composite_score     NUMERIC(5,2),             -- 0-100
    pop_density_score   NUMERIC(5,2),
    income_score        NUMERIC(5,2),
    transit_score       NUMERIC(5,2),
    road_score          NUMERIC(5,2),
    competitor_gap_score NUMERIC(5,2),
    has_partial_data    BOOLEAN NOT NULL DEFAULT FALSE,
    partial_factors     TEXT[],                   -- which factors used estimated data
    data_sources        JSONB NOT NULL DEFAULT '{}', -- source per factor
    attributes          JSONB NOT NULL DEFAULT '{}'
);

CREATE INDEX idx_sites_run_id ON candidate_sites (run_id);
CREATE INDEX idx_sites_geom ON candidate_sites USING GIST (geom);
CREATE INDEX idx_sites_composite_score ON candidate_sites (composite_score DESC);

-- =============================================================================
-- ANALYST OVERRIDES — audit-logged overrides of automated recommendations
-- =============================================================================

CREATE TABLE analyst_overrides (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_type     override_entity NOT NULL,
    entity_id       UUID NOT NULL,                -- site_id, layer_id, run_id
    analyst_id      VARCHAR(128) NOT NULL,
    field_name      VARCHAR(128) NOT NULL,
    original_value  JSONB,
    override_value  JSONB NOT NULL,
    reason          TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_overrides_entity ON analyst_overrides (entity_type, entity_id);
CREATE INDEX idx_overrides_analyst ON analyst_overrides (analyst_id);
CREATE INDEX idx_overrides_created_at ON analyst_overrides (created_at DESC);

-- =============================================================================
-- AUDIT LOG — immutable event log for all state-changing operations
-- =============================================================================

CREATE TABLE audit_log (
    id              BIGSERIAL PRIMARY KEY,
    event_type      VARCHAR(128) NOT NULL,
    entity_type     VARCHAR(64),
    entity_id       UUID,
    actor_id        VARCHAR(128) NOT NULL DEFAULT 'system',
    payload         JSONB NOT NULL DEFAULT '{}',
    ip_address      INET,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_entity ON audit_log (entity_type, entity_id);
CREATE INDEX idx_audit_event_type ON audit_log (event_type);
CREATE INDEX idx_audit_created_at ON audit_log (created_at DESC);

-- =============================================================================
-- VIEWS
-- =============================================================================

-- Datasets with freshness flag
CREATE OR REPLACE VIEW v_datasets_with_freshness AS
SELECT
    d.*,
    CASE
        WHEN d.vintage_year IS NULL THEN 'unknown'
        WHEN (EXTRACT(YEAR FROM NOW()) - d.vintage_year) < 1 THEN 'current'
        WHEN (EXTRACT(YEAR FROM NOW()) - d.vintage_year) BETWEEN 1 AND 2 THEN 'aging'
        ELSE 'outdated'
    END AS freshness_status,
    (EXTRACT(YEAR FROM NOW()) - d.vintage_year)::INT AS age_years
FROM datasets d;

-- Layers with validation summary
CREATE OR REPLACE VIEW v_layers_with_validation AS
SELECT
    l.*,
    COUNT(vr.id) FILTER (WHERE vr.severity = 'error') AS error_count,
    COUNT(vr.id) FILTER (WHERE vr.severity = 'warning') AS warning_count
FROM layers l
LEFT JOIN layer_validation_results vr ON vr.layer_id = l.id
GROUP BY l.id;
