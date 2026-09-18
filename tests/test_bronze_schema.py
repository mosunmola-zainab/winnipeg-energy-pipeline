"""Integration tests for the Bronze schema structure.

Design reference: docs/data_modeling_decisions.md, "Bronze v1 Design".

These require a reachable PostgreSQL with sql/init.sql applied. They skip
(rather than fail) when no database connection can be made, since CI does
not currently provision a Postgres service.
"""

import psycopg2
import pytest

from etl.load import get_connection


@pytest.fixture
def conn():
    try:
        connection = get_connection()
    except (KeyError, psycopg2.OperationalError) as exc:
        pytest.skip(f"Postgres not reachable: {exc}")
    yield connection
    connection.rollback()
    connection.close()


def _insert_run(cur, status="succeeded"):
    cur.execute(
        "INSERT INTO bronze.ingestion_runs (status, source_domain, source_dataset_id) "
        "VALUES (%s, %s, %s) RETURNING run_id",
        (status, "data.winnipeg.ca", "49ge-5j9g"),
    )
    return cur.fetchone()[0]


def _bogus_run_id(cur):
    cur.execute("SELECT COALESCE(MAX(run_id), 0) + 1000 FROM bronze.ingestion_runs")
    return cur.fetchone()[0]


def test_bronze_schema_and_tables_exist(conn):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'bronze'
        ORDER BY table_name
        """
    )
    tables = {row[0] for row in cur.fetchall()}
    assert tables == {"current_snapshot", "ingestion_runs", "utility_billing_raw"}


def test_ingestion_runs_structure_matches_design(conn):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = 'bronze' AND table_name = 'ingestion_runs'
        """
    )
    columns = {row[0] for row in cur.fetchall()}
    assert columns == {
        "run_id",
        "status",
        "started_at",
        "completed_at",
        "source_domain",
        "source_dataset_id",
        "rows_fetched",
        "rows_loaded",
        "last_hydro_gas_id",
        "observed_fields",
        "error_message",
    }


def test_utility_billing_raw_structure_matches_design(conn):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT column_name, data_type FROM information_schema.columns
        WHERE table_schema = 'bronze' AND table_name = 'utility_billing_raw'
        """
    )
    columns = dict(cur.fetchall())
    # No surrogate row id: only these three columns exist.
    assert set(columns) == {"run_id", "hydro_gas_id", "raw_record"}
    assert columns["raw_record"] == "jsonb"

    cur.execute(
        """
        SELECT a.attname
        FROM pg_index i
        JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
        WHERE i.indrelid = 'bronze.utility_billing_raw'::regclass AND i.indisprimary
        """
    )
    pk_columns = {row[0] for row in cur.fetchall()}
    assert pk_columns == {"run_id", "hydro_gas_id"}


def test_duplicate_run_and_hydro_gas_id_rejected(conn):
    cur = conn.cursor()
    run_id = _insert_run(cur)
    cur.execute(
        "INSERT INTO bronze.utility_billing_raw (run_id, hydro_gas_id, raw_record) "
        "VALUES (%s, %s, %s)",
        (run_id, 1, "{}"),
    )
    with pytest.raises(psycopg2.errors.UniqueViolation):
        cur.execute(
            "INSERT INTO bronze.utility_billing_raw (run_id, hydro_gas_id, raw_record) "
            "VALUES (%s, %s, %s)",
            (run_id, 1, "{}"),
        )


def test_raw_row_cannot_reference_nonexistent_run(conn):
    cur = conn.cursor()
    bogus_run_id = _bogus_run_id(cur)
    with pytest.raises(psycopg2.errors.ForeignKeyViolation):
        cur.execute(
            "INSERT INTO bronze.utility_billing_raw (run_id, hydro_gas_id, raw_record) "
            "VALUES (%s, %s, %s)",
            (bogus_run_id, 1, "{}"),
        )


def test_current_snapshot_cannot_reference_nonexistent_run(conn):
    cur = conn.cursor()
    bogus_run_id = _bogus_run_id(cur)
    with pytest.raises(psycopg2.errors.ForeignKeyViolation):
        cur.execute(
            "INSERT INTO bronze.current_snapshot (run_id) VALUES (%s)",
            (bogus_run_id,),
        )


def test_current_snapshot_accepts_valid_run(conn):
    cur = conn.cursor()
    run_id = _insert_run(cur)
    cur.execute("INSERT INTO bronze.current_snapshot (run_id) VALUES (%s)", (run_id,))
    cur.execute("SELECT run_id FROM bronze.current_snapshot WHERE id = 1")
    assert cur.fetchone()[0] == run_id
