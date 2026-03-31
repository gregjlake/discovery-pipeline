-- DiscoSights Database Schema
-- Generated from production Supabase instance
-- Run with: psql $DATABASE_URL < schema.sql
-- Or create tables manually via Supabase dashboard

-- ============================================================
-- raw_values: All ingested dataset values (primary data store)
-- One row per (fips, dataset_id, column_name) combination.
-- The gravity pipeline reads from this table.
-- ============================================================
CREATE TABLE IF NOT EXISTS raw_values (
    id BIGSERIAL PRIMARY KEY,
    fips VARCHAR(5) NOT NULL,
    dataset_id VARCHAR(50) NOT NULL,
    year INTEGER,
    value DOUBLE PRECISION,
    column_name VARCHAR(100) NOT NULL,
    ingested_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_raw_values_fips ON raw_values(fips);
CREATE INDEX IF NOT EXISTS idx_raw_values_dataset ON raw_values(dataset_id);
CREATE INDEX IF NOT EXISTS idx_raw_values_dataset_col ON raw_values(dataset_id, column_name);

COMMENT ON TABLE raw_values IS 'All ingested dataset values. Each row is one measurement for one county.';
COMMENT ON COLUMN raw_values.dataset_id IS 'Dataset identifier matching beta_calibration.json datasets_used (e.g., poverty, broadband, food_access)';
COMMENT ON COLUMN raw_values.column_name IS 'Source column name within the dataset (e.g., poverty_rate, broadband_rate)';

-- ============================================================
-- county_population: County names and populations
-- Source: Census ACS 5-Year
-- ============================================================
CREATE TABLE IF NOT EXISTS county_population (
    fips VARCHAR(5) PRIMARY KEY,
    county_name VARCHAR(100),
    population INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE county_population IS 'County names and populations from Census ACS.';

-- ============================================================
-- gravity_nodes: County positions for gravity visualization
-- Written by run_gravity_pipeline.py
-- ============================================================
CREATE TABLE IF NOT EXISTS gravity_nodes (
    fips VARCHAR(5) PRIMARY KEY,
    population INTEGER,
    initial_lat DOUBLE PRECISION,
    initial_lon DOUBLE PRECISION
);

COMMENT ON TABLE gravity_nodes IS 'County centroids and populations for gravity map. Written by run_gravity_pipeline.py.';

-- ============================================================
-- gravity_links: Pairwise gravity forces between counties
-- Top N strongest links stored per county
-- Written by run_gravity_pipeline.py
-- ============================================================
CREATE TABLE IF NOT EXISTS gravity_links (
    source_fips VARCHAR(5) NOT NULL,
    target_fips VARCHAR(5) NOT NULL,
    force_strength_normalized DOUBLE PRECISION,
    combined_dist DOUBLE PRECISION,
    PRIMARY KEY (source_fips, target_fips)
);

CREATE INDEX IF NOT EXISTS idx_gravity_links_source ON gravity_links(source_fips);
CREATE INDEX IF NOT EXISTS idx_gravity_links_target ON gravity_links(target_fips);

COMMENT ON TABLE gravity_links IS 'Pairwise gravity forces. force_strength_normalized is in [0,1] range. Written by run_gravity_pipeline.py.';

-- ============================================================
-- gravity_model_metadata: Model calibration parameters
-- One row per calibration run
-- ============================================================
CREATE TABLE IF NOT EXISTS gravity_model_metadata (
    id BIGSERIAL PRIMARY KEY,
    beta DOUBLE PRECISION,
    alpha_origin DOUBLE PRECISION,
    alpha_dest DOUBLE PRECISION,
    pseudo_r2 DOUBLE PRECISION,
    aic DOUBLE PRECISION,
    n_pairs INTEGER,
    calibration_year INTEGER,
    calibration_source VARCHAR(200),
    model_type VARCHAR(50),
    distance_type VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE gravity_model_metadata IS 'Model calibration history. Latest row is the active model.';

-- ============================================================
-- counties: Reserved for future county-level aggregated data
-- Currently empty — all data flows through raw_values
-- ============================================================
CREATE TABLE IF NOT EXISTS counties (
    fips VARCHAR(5) PRIMARY KEY,
    state VARCHAR(2),
    county_name VARCHAR(100)
);
