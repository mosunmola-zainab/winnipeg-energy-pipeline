DROP TABLE IF EXISTS utility_billing;
CREATE TABLE utility_billing (
    id                  SERIAL PRIMARY KEY,
    hydro_gas_id        BIGINT,
    account_number      BIGINT,
    customer_name       TEXT,
    ssc_number          TEXT,
    customer_information TEXT,
    service_address     TEXT,
    town                TEXT,
    meter_number        TEXT,
    actual_service_type TEXT,
    rate                TEXT,
    service_from_date   TIMESTAMP,
    service_to_date     TIMESTAMP,
    current_reading     NUMERIC,
    days_of_service     INTEGER,
    billing_units       NUMERIC,
    read_code           TEXT,
    basic_charge        NUMERIC,
    primary_other       NUMERIC,
    supplemental        NUMERIC,
    transportation      NUMERIC,
    distribution        NUMERIC,
    frp_refund          NUMERIC,
    city_tax            NUMERIC,
    gst_on_city_tax     NUMERIC,
    carbon_charge       NUMERIC,
    pst                 NUMERIC,
    gst                 NUMERIC,
    adjustment          NUMERIC,
    amount_due          NUMERIC,
    demand_billing      NUMERIC,
    billed_kva          NUMERIC,
    measured_demand     NUMERIC,
    high_demand         NUMERIC,
    contract_demand     NUMERIC,
    multiplier          NUMERIC,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- Bronze layer — structure per docs/data_modeling_decisions.md, "Bronze v1 Design".
-- v1 utility_billing table above is untouched; Bronze is additive, not a replacement yet.
CREATE SCHEMA IF NOT EXISTS bronze;

DROP TABLE IF EXISTS bronze.current_snapshot;
DROP TABLE IF EXISTS bronze.utility_billing_raw;
DROP TABLE IF EXISTS bronze.ingestion_runs;

-- One row per ingestion attempt. Column shape confirmed in docs/data_modeling_decisions.md.
-- retry_count is deliberately deferred until retry telemetry is implemented.
CREATE TABLE bronze.ingestion_runs (
    run_id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    status            TEXT NOT NULL DEFAULT 'running'
                      CHECK (status IN ('running', 'succeeded', 'failed')),
    started_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at      TIMESTAMPTZ,
    source_domain     TEXT NOT NULL,
    source_dataset_id TEXT NOT NULL,
    rows_fetched      INTEGER,
    rows_loaded       INTEGER,
    last_hydro_gas_id BIGINT,
    observed_fields   JSONB,
    error_message     TEXT
);

-- One row per source record per run. No surrogate id: (run_id, hydro_gas_id) is the key.
-- raw_record holds the source row as received (see decisions doc); no business transformation here.
CREATE TABLE bronze.utility_billing_raw (
    run_id       BIGINT NOT NULL REFERENCES bronze.ingestion_runs (run_id) ON DELETE RESTRICT,
    hydro_gas_id BIGINT NOT NULL,
    raw_record   JSONB NOT NULL,
    PRIMARY KEY (run_id, hydro_gas_id)
);

-- Single pointer row at the currently promoted run. The constant-checked id enforces one row.
CREATE TABLE bronze.current_snapshot (
    id     SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    run_id BIGINT NOT NULL REFERENCES bronze.ingestion_runs (run_id) ON DELETE RESTRICT
);
