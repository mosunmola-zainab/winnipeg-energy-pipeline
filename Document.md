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
    try:
        results = client.get(dataset_id, limit=limit)
    finally:
        client.close()
    return results
```

The `limit` parameter defaults to 500,000 — large enough to capture the full dataset in a single API call. This was initially set to a lower value during development and scaled up once the pipeline was stable (commit `fc016df`).

The function returns a list of dictionaries, where each dictionary is one row from the API. Every value is a string at this point.

The `try/finally` block ensures `client.close()` is always called, even if the API request fails. Without it, a network timeout or server error would leave the HTTP connection open and leaked.

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
def load(rows: list[dict]) -> int:
    conn = get_connection()
    try:
        cur = conn.cursor()

        buf = io.StringIO()
        writer = csv.writer(buf)
        for row in rows:
            writer.writerow(row.get(col, "") for col in COLUMNS)
        buf.seek(0)

        col_names = ", ".join(COLUMNS)
        copy_sql = f"COPY utility_billing ({col_names}) FROM STDIN WITH CSV NULL ''"
        cur.copy_expert(copy_sql, buf)

        conn.commit()
        cur.close()
    finally:
        conn.close()

    return len(rows)
```

`COPY` bypasses the SQL parser entirely. PostgreSQL reads the CSV stream directly into the table's storage. This is orders of magnitude faster than `INSERT` for large datasets.

The `NULL ''` clause in the `COPY` command tells PostgreSQL to interpret empty CSV fields as SQL `NULL` rather than empty strings. This is critical — the transform module returns `None` for unparseable values, which `csv.writer` writes as empty fields. Without `NULL ''`, those empty fields would cause errors on `NUMERIC`, `BIGINT`, `INTEGER`, and `TIMESTAMP` columns because an empty string is not a valid number or timestamp.

The entire function is wrapped in `try/finally` to guarantee the database connection is closed even if `copy_expert()` or `conn.commit()` raises an exception. Without this, a failed load would leak open connections to the database.

#### Connection Configuration

```python
def get_connection():
    return psycopg2.connect(
        host=os.environ["POSTGRES_HOST"],
        port=os.environ["POSTGRES_PORT"],
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        sslmode=os.environ.get("POSTGRES_SSLMODE", "prefer"),
    )
```

The `sslmode` parameter is read from the `POSTGRES_SSLMODE` environment variable, defaulting to `"prefer"`. This was originally hardcoded to `"require"` (commit `edecaed`) when the pipeline moved to AWS RDS, but that broke local Docker usage because the PostgreSQL Alpine image does not enable SSL by default. Making it configurable allows:

- **Local Docker:** `sslmode=prefer` (or omit — the default) — connects without SSL to the local container
- **AWS RDS:** `sslmode=require` — enforces encrypted connections over the public internet

### `etl/pipeline.py` — Orchestration

The pipeline entrypoint ties extract, transform, and load together in sequence:

1. Load environment variables from `.env` (if present)
2. Extract raw records from the Socrata API
3. Transform them into typed dictionaries
4. Truncate the `utility_billing` table
5. Load the cleaned data via `COPY`

```python
def run():
    load_dotenv()

    raw = extract()
    print(f"Extracted {len(raw)} records")

    rows = transform(raw)
    print(f"Transformed {len(rows)} rows")

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("TRUNCATE TABLE utility_billing")
        conn.commit()
        cur.close()
    finally:
        conn.close()
    print("Truncated utility_billing table")

    inserted = load(rows)
    print(f"Loaded {inserted} rows into database")
```

**`load_dotenv()` placement:** This call lives inside `run()`, not at module import time. This is deliberate — when Airflow imports `etl.pipeline` to register the DAG, `load_dotenv()` should not fire as a side effect. It would silently override environment variables set by Docker/Airflow with values from a stale `.env` file (or fail silently if no `.env` exists in the Airflow container). By placing it inside `run()`, it only executes when the pipeline actually runs. When called via `python -m etl.pipeline` locally, `load_dotenv()` loads the `.env` file. When called by Airflow, the environment variables are already set by the container's `env_file` configuration, and `load_dotenv()` does not override existing values.

**Truncation:** The truncation step (commit `b681471`) makes the pipeline idempotent. Without it, re-running the pipeline would duplicate every row. `TRUNCATE TABLE` is used instead of `DELETE FROM` because it's faster — it deallocates data pages instead of scanning and marking individual rows. The truncation also uses `try/finally` to ensure the connection is always closed.

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

- `etl` — Builds from the Dockerfile. Uses `condition: service_healthy` to wait for the database healthcheck. Loads all environment variables from `.env` via `env_file`. Mounts `./etl` and `./sql` as volumes so code changes reflect without rebuilding the image.

**Airflow services (added in Phase 5):**

- `postgres-airflow` — A separate PostgreSQL instance for Airflow's metadata. Airflow needs its own database to track DAG runs, task states, and scheduler metadata. Using the same database as the pipeline data would be messy. Has its own healthcheck and named volume `pgdata-airflow`.

- `airflow-init` — A one-shot container that runs `airflow db migrate` to initialize the metadata schema, then creates an admin user (`admin`/`admin`). Uses `service_completed_successfully` as a dependency condition so downstream services wait for it to finish.

- `airflow-webserver` — The Airflow UI on port 8080.

- `airflow-scheduler` — The scheduler that triggers DAG runs based on cron expressions.

Both the webserver and scheduler share the same configuration:

- **`env_file: .env`** — Loads the pipeline's database and Socrata credentials. Without this, the DAG would crash with `KeyError` when trying to read `POSTGRES_HOST`, `SOCRATA_DOMAIN`, etc. from the environment. This was a critical fix — the original compose file only set `AIRFLOW__DATABASE__SQL_ALCHEMY_CONN` for the Airflow metadata database, not the pipeline's target database.

- **`PYTHONPATH: /opt/airflow`** — Ensures `from etl.pipeline import run` resolves correctly inside the container, since `./etl` is mounted at `/opt/airflow/etl/`.

- **`_PIP_ADDITIONAL_REQUIREMENTS`** — Tells the Airflow image to install `sodapy`, `psycopg2-binary`, and `python-dotenv` at startup. This is an Airflow-specific mechanism — the official image checks this environment variable and runs `pip install` before starting the main process.

- **Volume mounts:** `./dags` to `/opt/airflow/dags/`, `./etl` to `/opt/airflow/etl/`, and `./requirements.txt` to `/requirements.txt`.

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
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` — AWS credentials (available for future Terraform automation in CI)

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

**`terraform/main.tf`** — Configures the AWS provider, a security group, and the RDS instance.

The `terraform` block pins the AWS provider to `~> 5.0` and requires Terraform `>= 1.5`:

```hcl
terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}
```

The security group opens port 5432 for inbound PostgreSQL traffic and allows all outbound traffic:

```hcl
resource "aws_security_group" "rds" {
  name        = "${var.project_name}-rds-sg"
  description = "Allow inbound PostgreSQL traffic"

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
```

Without this security group, the RDS instance would be assigned the default VPC security group, which typically blocks all inbound traffic — making the database provisioned but unreachable. The `0.0.0.0/0` CIDR allows connections from any IP, which is necessary for GitHub Actions runners and local development. In a production setup, this would be locked down to specific IP ranges or placed behind a VPC with a bastion host.

The RDS instance itself:

```hcl
resource "aws_db_instance" "postgres" {
  identifier     = "${var.project_name}-db"
  engine         = "postgres"
  engine_version = "16"
  instance_class    = "db.t3.micro"
  allocated_storage = 20
  storage_type      = "gp2"
  db_name  = var.db_name
  username = var.db_username
  password = var.db_password
  vpc_security_group_ids = [aws_security_group.rds.id]
  skip_final_snapshot    = true
  publicly_accessible    = true
}
```

Key decisions:
- `db.t3.micro` with 20GB `gp2` storage — AWS free tier eligible, sufficient for ~450k rows
- `vpc_security_group_ids` — References the security group defined above to ensure port 5432 is open
- `publicly_accessible = true` — allows the GitHub Actions runner and local development to connect directly. In a production setup, this would be `false` with a VPC and bastion host.
- `skip_final_snapshot = true` — skips the RDS snapshot on deletion. Appropriate for a project where the data can be fully reconstructed from the API at any time.

**`terraform/outputs.tf`** — Exports `rds_endpoint` (the hostname) and `rds_port` after provisioning. These values are used to configure `POSTGRES_HOST` and `POSTGRES_PORT` in the environment and in GitHub Secrets.

### Configurable SSL

When the pipeline moved from a local Docker PostgreSQL to AWS RDS, SSL enforcement was needed. RDS instances require SSL by default, and sending credentials over an unencrypted connection to a public endpoint would be a security issue.

Rather than hardcoding `sslmode="require"` (which would break local Docker usage since the PostgreSQL Alpine image does not enable SSL), the connection reads `POSTGRES_SSLMODE` from the environment with a default of `"prefer"`:

```python
sslmode=os.environ.get("POSTGRES_SSLMODE", "prefer"),
```

This allows:
- **Local Docker:** Omit the variable or leave the default — connects without SSL
- **AWS RDS / CI:** Set `POSTGRES_SSLMODE=require` — enforces encrypted connections

### `.gitignore` Updates

Several commits (`202e5d6`, `4a744fc`, `c1a0a71`, `d8e75b3`, `7465f3d`) dealt with cleaning up accidentally committed Terraform state and provider binaries:

- `terraform/.terraform/` — provider plugin binaries (hundreds of MB), gitignored
- `terraform/terraform.tfstate` — contains the full state of provisioned resources including sensitive values, gitignored
- `terraform/terraform.tfstate.backup` — backup of the above, gitignored

The state files were removed from git history after being accidentally committed. This is a common Terraform pitfall — `terraform.tfstate` can contain plaintext database passwords and should never be in version control.

Note: `terraform/.terraform.lock.hcl` is **not** gitignored. HashiCorp recommends committing this lock file to version control to ensure reproducible provider versions across environments. It contains no sensitive data — only provider version hashes.

---

## Phase 5: Orchestration with Apache Airflow

### `dags/winnipeg_energy_dag.py`

Defines a single DAG that runs the ETL pipeline on a monthly schedule:

```python
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta

from etl.pipeline import run

with DAG(
    dag_id="winnipeg_energy_etl",
    schedule="0 0 1 * *",
    start_date=datetime(2026, 3, 1),
    catchup=False,
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
    },
) as dag:
    run_etl = PythonOperator(
        task_id="run_etl_pipeline",
        python_callable=run,
    )
```

- **`schedule="0 0 1 * *"`** — midnight on the 1st of every month.
- **`start_date=datetime(2026, 3, 1)`** — the first scheduled run will be March 1, 2026.
- **`catchup=False`** — prevents Airflow from backfilling all missed runs between `start_date` and now. Without this, Airflow would try to run the DAG for every month since the start date on first deployment.
- **`retries: 2` with `retry_delay: timedelta(minutes=5)`** — if the ETL fails (e.g., Socrata API timeout, database connection error), Airflow will retry the task up to 2 times, waiting 5 minutes between attempts. This handles transient failures without manual intervention.
- The `PythonOperator` calls `etl.pipeline.run()` directly, reusing the same code path as `python -m etl.pipeline`. No duplication.

The DAG file lives in `./dags/`, which is mounted into `/opt/airflow/dags/` in the Airflow containers. The `etl/` module is mounted alongside it at `/opt/airflow/etl/`, and `PYTHONPATH=/opt/airflow` ensures the import `from etl.pipeline import run` resolves correctly.

### Airflow Infrastructure

Airflow requires its own metadata database to track DAG definitions, task instances, run history, and scheduler state. The `postgres-airflow` service provides this as a separate PostgreSQL container, completely isolated from the pipeline's data database.

The `airflow-init` container runs once on startup to:
1. `airflow db migrate` — creates/updates the metadata schema
2. `airflow users create` — creates an admin account (`admin`/`admin`)

After init completes, the webserver and scheduler start. Both services load the pipeline's `.env` file via `env_file: .env`, which provides the `POSTGRES_*` and `SOCRATA_*` variables that the ETL code needs. They also use `_PIP_ADDITIONAL_REQUIREMENTS` to install the pipeline's Python dependencies (`sodapy`, `psycopg2-binary`, `python-dotenv`) at container startup. This is an Airflow-specific mechanism — the official image checks this environment variable and runs `pip install` before starting the main process.

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

Optional variables not in `.env.example` but used by the codebase:

| Variable | Purpose | Default |
|----------|---------|---------|
| `POSTGRES_SSLMODE` | PostgreSQL SSL mode (`prefer`, `require`, etc.) | `prefer` |

The `.env` file itself is in `.gitignore` — only the example template is committed. The `.gitignore` uses `.env.*` with an exception for `!.env.example` to catch any variant `.env` files (`.env.local`, `.env.production`, etc.) that could accidentally be committed with credentials.

---

## `.gitignore` — What's Excluded and Why

```
.env                              # Credentials
.env.*                            # Credential variants (.env.local, .env.production)
!.env.example                     # Exception: template is safe to commit
__pycache__/                      # Python bytecode cache
*.pyc                             # Compiled Python files
.venv/                            # Virtual environment
.pytest_cache/                    # Pytest cache directory
pgdata/                           # Local database data (if bind-mounted)
logs/                             # Airflow log files
terraform/.terraform/             # Terraform provider binaries (hundreds of MB)
terraform/terraform.tfstate       # Terraform state (contains sensitive values)
terraform/terraform.tfstate.backup  # Terraform state backup
```

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
        | io.StringIO → csv.writer → COPY FROM STDIN WITH CSV NULL ''
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
- **Scheduled:** Airflow DAG on the 1st of each month (with 2 retries on failure)

---

## Code Review Fixes Applied

During a final code review before release, several issues were identified and resolved:

### Critical Fixes
1. **Airflow services missing pipeline env vars** — The `airflow-webserver` and `airflow-scheduler` containers only had `AIRFLOW__DATABASE__SQL_ALCHEMY_CONN` set, not the pipeline's `POSTGRES_*` and `SOCRATA_*` variables. The DAG would crash with `KeyError` at runtime. Fixed by adding `env_file: .env` to both services.

2. **Hardcoded `sslmode="require"` breaking local Docker** — The PostgreSQL Alpine container does not enable SSL, so the ETL container could not connect locally. Fixed by reading `POSTGRES_SSLMODE` from the environment with a default of `"prefer"`.

3. **Empty strings causing `COPY` failures on typed columns** — `row.get(col, "")` wrote empty strings for `None` values. PostgreSQL's `COPY` interprets empty fields as empty strings, which fails on `NUMERIC`, `BIGINT`, `INTEGER`, and `TIMESTAMP` columns. Fixed by adding `NULL ''` to the `COPY` command, telling PostgreSQL to treat empty fields as SQL `NULL`.

4. **RDS instance unreachable without security group** — The `aws_db_instance` was `publicly_accessible = true` but had no `vpc_security_group_ids`. AWS assigns the default VPC security group, which blocks all inbound traffic. Fixed by adding an `aws_security_group` resource that opens port 5432.

### Medium Fixes
5. **`load_dotenv()` at import time** — Moved from module-level to inside `run()` to prevent side effects when Airflow imports the module.

6. **Connection leaks on exceptions** — Added `try/finally` blocks to `load()`, the truncation in `pipeline.py`, and `extract()` to ensure connections and clients are always closed.

7. **`.gitignore` gaps** — Added `.env.*` (with `!.env.example` exception), `.pytest_cache/`, and `logs/` for Airflow.

8. **No DAG retries** — Added `retries: 2` with `retry_delay: timedelta(minutes=5)` to the DAG's `default_args` for resilience against transient failures.

### Low-Priority Fixes
9. **Unused `AIRFLOW_UID`** — Removed from `.env.example` since it was never referenced in `docker-compose.yml`.

10. **README project structure** — Added missing `__init__.py` files, `Document.md`, and `.gitignore` to the tree listing.

11. **`.terraform.lock.hcl` gitignored incorrectly** — Removed from `.gitignore` since HashiCorp recommends committing it for reproducible provider versions.
