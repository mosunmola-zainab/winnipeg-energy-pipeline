# Winnipeg Energy Pipeline — Technical Documentation

This document walks through the entire codebase from the ground up, explaining every component, how it evolved, and the reasoning behind each decision. It follows the project's actual development timeline based on the git commit history.

---

## Phase 1: Core ETL Pipeline

### The Problem

The City of Winnipeg publishes utility billing data (electricity and natural gas consumption) through its Open Data portal, powered by the Socrata platform. The dataset contains 451,691 records across 35 columns — covering account details, meter readings, service dates, and itemized charges. The data sits behind an API as raw JSON with every value returned as a string, regardless of its actual type.

The goal: pull this data, clean it, and load it into a structured PostgreSQL database where it can be queried and analyzed.

### `etl/extract.py` — Data Extraction

The extract module connects to the Socrata API using the `sodapy` library. It reads three environment variables:

- `SOCRATA_DOMAIN` — the base domain (`data.winnipeg.ca`)
- `SOCRATA_DATASET_ID` — the dataset identifier (`49ge-5j9g`)
- `SOCRATA_APP_TOKEN` — an optional token that raises the API rate limit

```python
def extract(limit: int = 500000) -> list[dict]:
    client = Socrata(domain, app_token)
    results = client.get(dataset_id, limit=limit)
    client.close()
    return results
```

The `limit` parameter defaults to 500,000 — large enough to capture the full dataset in a single API call. This was initially set to a lower value during development and scaled up once the pipeline was stable (commit `fc016df`).

The function returns a list of dictionaries, where each dictionary is one row from the API. Every value is a string at this point.

### `etl/transform.py` — Data Cleaning and Type-Casting

The Socrata API returns all fields as strings. PostgreSQL needs proper types. The transform module handles this conversion across all 35 columns, grouped by target type:

**Text fields (9 columns):** `customer_name`, `ssc_number`, `customer_information`, `service_address`, `town`, `meter_number`, `actual_service_type`, `rate`, `read_code`. These pass through as-is since they're already strings.

**Integer fields (3 columns):** `hydro_gas_id`, `account_number`, `days_of_service`. Cast using `_safe_int()`, which converts through `float` first to handle values like `"12345.0"` that the API sometimes returns.

**Float fields (21 columns):** All monetary and measurement fields — `amount_due`, `basic_charge`, `billing_units`, `current_reading`, etc. Cast using `_safe_float()`.

**Timestamp fields (2 columns):** `service_from_date`, `service_to_date`. These are passed through as ISO-format strings because PostgreSQL's `TIMESTAMP` type handles ISO parsing natively.

Both `_safe_int()` and `_safe_float()` return `None` on failure instead of raising exceptions. This is a deliberate choice — the API contains missing and malformed data, and crashing on a single bad value in a 451,691-row dataset is not acceptable. `None` maps to SQL `NULL`, which is the correct representation of missing data.

```python
def _safe_int(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None
```

The `int(float(value))` pattern handles the edge case where Socrata returns integers as `"12345.0"`. Calling `int()` directly on that string would raise a `ValueError`.

### `etl/load.py` — Database Loading

This module went through three iterations, each a significant performance improvement:

**Version 1 — Individual inserts:** The original implementation used `cursor.execute()` in a loop. One SQL statement per row. For 451,691 rows, this meant 451,691 round trips to the database. Slow.

**Version 2 — `executemany` with batching (commit `b4891a9`, then `c9c5a5d`):** Switched to `cursor.executemany()`, which sends multiple rows per statement. Added batching in chunks of 10,000 rows with progress logging. Better, but `executemany` in psycopg2 still prepares and executes individual `INSERT` statements under the hood.

**Version 3 — PostgreSQL `COPY` (commit `e5e2ab3`):** The current implementation. Uses PostgreSQL's `COPY` protocol, which is the fastest way to bulk-load data. The approach:

1. Build an in-memory CSV using `io.StringIO` and `csv.writer`
2. Feed it to PostgreSQL via `cursor.copy_expert()`

```python
buf = io.StringIO()
writer = csv.writer(buf)
for row in rows:
    writer.writerow(row.get(col, "") for col in COLUMNS)
buf.seek(0)

copy_sql = f"COPY utility_billing ({col_names}) FROM STDIN WITH CSV"
cur.copy_expert(copy_sql, buf)
```

`COPY` bypasses the SQL parser entirely. PostgreSQL reads the CSV stream directly into the table's storage. This is orders of magnitude faster than `INSERT` for large datasets.

The connection is configured with `sslmode="require"` (commit `edecaed`) to enforce encrypted connections, which is required when connecting to AWS RDS over the public internet.

### `etl/pipeline.py` — Orchestration

The pipeline entrypoint ties extract, transform, and load together in sequence:

1. Extract raw records from the Socrata API
2. Transform them into typed dictionaries
3. Truncate the `utility_billing` table (commit `b681471`)
4. Load the cleaned data via `COPY`

The truncation step was added to make the pipeline idempotent. Without it, re-running the pipeline would duplicate every row. `TRUNCATE TABLE` is used instead of `DELETE FROM` because it's faster — it deallocates data pages instead of scanning and marking individual rows.

Environment variables are loaded from `.env` via `python-dotenv` at the top of the module, before any ETL imports. This ordering matters — the import of `load.py` doesn't read env vars at import time, but `load_dotenv()` needs to run before any code calls `os.environ`.

### `sql/init.sql` — Database Schema

Defines the `utility_billing` table with 35 data columns plus a surrogate `id` (auto-incrementing `SERIAL PRIMARY KEY`) and a `created_at` timestamp defaulting to `NOW()`.

The schema uses `DROP TABLE IF EXISTS` followed by `CREATE TABLE` to make container initialization idempotent (commit `6b73978`). When the PostgreSQL container starts, Docker mounts this file into `/docker-entrypoint-initdb.d/`, which Postgres executes automatically on first run.

Column types map directly to the transform module's type groups:
- `TEXT` for string fields
- `BIGINT` for `hydro_gas_id` and `account_number` (values exceed 32-bit int range)
- `INTEGER` for `days_of_service`
- `NUMERIC` for all monetary/measurement fields (arbitrary precision, no floating-point rounding errors)
- `TIMESTAMP` for date fields

---

## Phase 2: Dockerized Infrastructure

### `Dockerfile`

A minimal Python 3.12 image:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY etl/ etl/
CMD ["python", "-m", "etl.pipeline"]
```

Uses `python:3.12-slim` instead of the full image to reduce image size. `--no-cache-dir` prevents pip from storing downloaded packages in the image layer. The `CMD` runs the pipeline as a module (`-m`) so Python resolves the package correctly.

### `docker-compose.yml` — Service Definitions

The compose file defines the local development stack. There are two logical groups of services:

**Data services:**

- `db` — PostgreSQL 16 (Alpine) with a healthcheck (`pg_isready`). The healthcheck is critical because the ETL container depends on it — without it, the ETL would start before Postgres is ready to accept connections and crash. Data is persisted to a named volume `pgdata`. The `init.sql` schema is mounted into the entrypoint directory.

- `pgadmin` — pgAdmin 4 on port 5050 for visual database exploration. Depends on `db` being up.

- `etl` — Builds from the Dockerfile. Uses `condition: service_healthy` to wait for the database healthcheck. Mounts `./etl` and `./sql` as volumes so code changes reflect without rebuilding the image.

**Airflow services (added in Phase 5):**

- `postgres-airflow` — A separate PostgreSQL instance for Airflow's metadata. Airflow needs its own database to track DAG runs, task states, and scheduler metadata. Using the same database as the pipeline data would be messy.

- `airflow-init` — A one-shot container that runs `airflow db migrate` to initialize the metadata schema, then creates an admin user. Uses `service_completed_successfully` as a dependency condition so downstream services wait for it to finish.

- `airflow-webserver` — The Airflow UI on port 8080.

- `airflow-scheduler` — The scheduler that triggers DAG runs based on cron expressions.

Both the webserver and scheduler mount `./dags` and `./etl` into `/opt/airflow/`, with `PYTHONPATH` set to `/opt/airflow` so that `from etl.pipeline import run` resolves correctly inside the container. The `_PIP_ADDITIONAL_REQUIREMENTS` environment variable tells the Airflow image to install `sodapy`, `psycopg2-binary`, and `python-dotenv` at startup — these are the pipeline's dependencies that aren't included in the base Airflow image.

### `requirements.txt`

```
requests==2.32.*
sodapy==2.2.*
psycopg2-binary==2.9.*
python-dotenv==1.1.*
pytest
```

Pin major.minor versions with wildcard patches for reproducibility without being overly rigid. `psycopg2-binary` is used instead of `psycopg2` to avoid needing `libpq-dev` and a C compiler in the Docker image.

---

## Phase 3: CI/CD with GitHub Actions

### `.github/workflows/ci.yml`

The CI pipeline has two jobs:

**`test` job:** Runs on every push and PR to `master`. Checks out the code, sets up Python 3.12, installs dependencies, and runs `pytest tests/ -v`. This catches transform logic regressions before they reach the database.

**`deploy` job:** Runs after `test` passes (`needs: test`). Executes the full ETL pipeline (`python -m etl.pipeline`) with all connection credentials injected from GitHub Secrets:

- `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` — RDS connection details
- `SOCRATA_DOMAIN`, `SOCRATA_DATASET_ID` — API targeting
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` — AWS credentials (available for future Terraform automation)

This means every push to `master` that passes tests automatically refreshes the production database with the latest data from the Socrata API.

### `tests/test_transform.py`

Three unit tests covering the transform module's core behaviors:

1. **Row count preservation** — Input and output lengths must match. The transform should never drop or duplicate rows.
2. **Type casting** — Verifies that string values from the API are converted to `int` and `float`.
3. **Missing field handling** — An empty dictionary should produce `None` values, not exceptions.

These tests run without a database, network, or environment variables. They test pure data transformation logic in isolation.

---

## Phase 4: Cloud Migration

### Terraform Configuration

Three files provision the AWS infrastructure:

**`terraform/variables.tf`** — Defines five input variables:
- `aws_region` (default: `us-east-1`)
- `project_name` (default: `winnipeg-energy`)
- `db_name` (default: `energy`)
- `db_username` (sensitive — no default, must be provided)
- `db_password` (sensitive — no default, must be provided)

The `sensitive = true` flag on credentials prevents Terraform from displaying them in plan output or state logs.

**`terraform/main.tf`** — Configures the AWS provider and provisions a single `aws_db_instance`:

```hcl
resource "aws_db_instance" "postgres" {
  identifier     = "${var.project_name}-db"
  engine         = "postgres"
  engine_version = "16"
  instance_class    = "db.t3.micro"
  allocated_storage = 20
  storage_type      = "gp2"
  ...
}
```

Key decisions:
- `db.t3.micro` with 20GB `gp2` storage — AWS free tier eligible, sufficient for ~450k rows
- `publicly_accessible = true` — allows the GitHub Actions runner and local development to connect directly. In a production setup, this would be `false` with a VPC and bastion host.
- `skip_final_snapshot = true` — skips the RDS snapshot on deletion. Appropriate for a project where the data can be fully reconstructed from the API at any time.
- The `terraform` block pins the AWS provider to `~> 5.0` and requires Terraform `>= 1.5`

**`terraform/outputs.tf`** — Exports `rds_endpoint` (the hostname) and `rds_port` after provisioning. These values are used to configure `POSTGRES_HOST` and `POSTGRES_PORT` in the environment.

### SSL Enforcement

When the pipeline moved from a local Docker PostgreSQL to AWS RDS, `sslmode="require"` was added to the `psycopg2.connect()` call. RDS instances enforce SSL by default, and connecting without it would fail. Even if it didn't fail, sending credentials and data over an unencrypted connection to a public endpoint would be a security issue.

### `.gitignore` Updates

Several commits (`202e5d6`, `4a744fc`, `c1a0a71`, `d8e75b3`, `7465f3d`) dealt with cleaning up accidentally committed Terraform state and provider binaries:

- `terraform/.terraform/` — provider plugin binaries (hundreds of MB)
- `terraform/.terraform.lock.hcl` — dependency lock file
- `terraform/terraform.tfstate` — contains the full state of provisioned resources, including sensitive values
- `terraform/terraform.tfstate.backup` — backup of the above

The state files were removed from git history after being accidentally committed. This is a common Terraform pitfall — `terraform.tfstate` can contain plaintext database passwords and should never be in version control.

---

## Phase 5: Orchestration with Apache Airflow

### `dags/winnipeg_energy_dag.py`

Defines a single DAG that runs the ETL pipeline on a monthly schedule:

```python
with DAG(
    dag_id="winnipeg_energy_etl",
    schedule="0 0 1 * *",
    start_date=datetime(2026, 3, 1),
    catchup=False,
) as dag:
    run_etl = PythonOperator(
        task_id="run_etl_pipeline",
        python_callable=run,
    )
```

- `schedule="0 0 1 * *"` — midnight on the 1st of every month
- `catchup=False` — prevents Airflow from backfilling all missed runs between `start_date` and now. Without this, Airflow would try to run the DAG for every month since March 2026 on first deployment.
- The `PythonOperator` calls `etl.pipeline.run()` directly, reusing the same code path as `python -m etl.pipeline`. No duplication.

The DAG file lives in `./dags/`, which is mounted into `/opt/airflow/dags/` in the Airflow containers. The `etl/` module is mounted alongside it at `/opt/airflow/etl/`, and `PYTHONPATH=/opt/airflow` ensures the import `from etl.pipeline import run` resolves correctly.

### Airflow Infrastructure

Airflow requires its own metadata database to track DAG definitions, task instances, run history, and scheduler state. The `postgres-airflow` service provides this as a separate PostgreSQL container, completely isolated from the pipeline's data database.

The `airflow-init` container runs once on startup to:
1. `airflow db migrate` — creates/updates the metadata schema
2. `airflow users create` — creates an admin account (`admin`/`admin`)

After init completes, the webserver and scheduler start. Both use `_PIP_ADDITIONAL_REQUIREMENTS` to install the pipeline's Python dependencies (`sodapy`, `psycopg2-binary`, `python-dotenv`) at container startup. This is an Airflow-specific mechanism — the official image checks this environment variable and runs `pip install` before starting the main process.

---

## Environment Configuration

The `.env.example` file documents all required environment variables:

| Variable | Purpose |
|----------|---------|
| `POSTGRES_USER` | Database username |
| `POSTGRES_PASSWORD` | Database password |
| `POSTGRES_DB` | Database name |
| `POSTGRES_HOST` | Hostname (`db` for local Docker, RDS endpoint for cloud) |
| `POSTGRES_PORT` | Port (default `5432`) |
| `SOCRATA_DOMAIN` | API domain (`data.winnipeg.ca`) |
| `SOCRATA_DATASET_ID` | Dataset identifier |
| `SOCRATA_APP_TOKEN` | Optional API token for higher rate limits |
| `PGADMIN_EMAIL` | pgAdmin login email |
| `PGADMIN_PASSWORD` | pgAdmin login password |
| `AIRFLOW_UID` | Linux user ID for Airflow containers (default `50000`) |

The `.env` file itself is in `.gitignore` — only the example template is committed.

---

## Data Flow Summary

```
data.winnipeg.ca (Socrata API)
        |
        | sodapy.Socrata.get() — 451,691 JSON records
        v
   extract.py
        |
        | list[dict] — all values as strings
        v
  transform.py
        |
        | list[dict] — typed values (int, float, None, str)
        v
    load.py
        |
        | io.StringIO → csv.writer → COPY FROM STDIN
        v
  PostgreSQL (AWS RDS)
        |
        | TRUNCATE before each load (idempotent)
        |
   utility_billing table (35 columns + id + created_at)
```

Triggered by:
- **Locally:** `docker-compose up --build` (one-shot ETL container)
- **CI/CD:** GitHub Actions deploy job on push to `master`
- **Scheduled:** Airflow DAG on the 1st of each month
