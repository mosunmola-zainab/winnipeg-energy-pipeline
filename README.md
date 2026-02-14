# Winnipeg Energy Ingestion Pipeline

## Overview
ETL pipeline that ingests municipal utility billing data from Winnipeg's Open Data portal into AWS RDS PostgreSQL. Processes 450,000+ electricity and natural gas consumption records, orchestrated by Apache Airflow on a monthly schedule.

## Tech Stack
- **Language:** Python 3.12
- **Libraries:** `sodapy`, `psycopg2`, `python-dotenv`, `pytest`
- **Database:** PostgreSQL 16 on AWS RDS
- **Infrastructure:** Terraform, Docker & Docker Compose
- **Orchestration:** Apache Airflow 2.9.0
- **Database GUI:** pgAdmin 4
- **CI/CD:** GitHub Actions

## Architecture

### Data Flow
```
Socrata Open Data API
        |
        v
  [ Extract ]    -->  Pull 450,000+ records via sodapy
        |
        v
  [ Transform ]  -->  Type-cast 35 fields (Text, Int, Float, Timestamp)
        |
        v
  [   COPY    ]  -->  PostgreSQL COPY into AWS RDS
        |
        v
  [ Airflow ]   -->  Scheduler triggers pipeline on the 1st of each month
```

### Infrastructure
```
Terraform             GitHub Actions
    |                       |
    v                       v
AWS RDS PostgreSQL    Deploy on push to master
    ^                       |
    |                       v
    +------  ETL Pipeline --+
```

| Layer             | Description |
|-------------------|-------------|
| **Extract**       | Connects to the Socrata API and pulls from the Winnipeg Utility Billing dataset (`49ge-5j9g`). |
| **Transform**     | Type-casts 35 raw API fields into structured SQL types (Numeric, BigInt, Timestamps) with safe handling of missing/malformed data. |
| **Load**          | Bulk loads data into PostgreSQL via the `COPY` command using `psycopg2.copy_expert`. Table is truncated before each run to prevent duplicates. |
| **Orchestration** | Airflow DAG runs on a monthly cron schedule (`0 0 1 * *`), calling the ETL pipeline's `run()` function. |
| **CI/CD**         | Pytest suite runs on every push/PR to `master`. Deploy job runs the pipeline after tests pass. |
| **Infrastructure**| Terraform provisions the RDS instance with version-pinned AWS provider (`~> 5.0`). |

## Project Structure
```
winnipeg_energy_pipeline/
├── etl/
│   ├── extract.py            # Socrata API client
│   ├── transform.py          # Data cleaning & type-casting
│   ├── load.py               # PostgreSQL COPY loading
│   └── pipeline.py           # Orchestrates the full ETL run
├── dags/
│   └── winnipeg_energy_dag.py  # Airflow DAG definition
├── terraform/
│   ├── main.tf               # AWS provider & RDS instance
│   ├── variables.tf          # Input variables
│   └── outputs.tf            # RDS endpoint & port outputs
├── sql/
│   └── init.sql              # Table schema (auto-runs on container start)
├── tests/
│   └── test_transform.py     # Unit tests for the transform layer
├── .github/workflows/
│   └── ci.yml                # GitHub Actions CI/CD pipeline
├── docker-compose.yml        # PostgreSQL + pgAdmin + ETL + Airflow services
├── Dockerfile
├── requirements.txt
└── .env.example
```

## Getting Started

### Installation & Execution

1. **Clone the repository:**
   ```bash
   git clone https://github.com/mosunmola-zainab/winnipeg-energy-pipeline.git
   cd winnipeg-energy-pipeline
   ```

2. **Set up environment variables:**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` with your credentials. See `.env.example` for required variables.

3. **Run the pipeline:**
   ```bash
   docker-compose up --build
   ```
   This starts PostgreSQL, pgAdmin, Airflow, and runs the ETL pipeline.

4. **Explore the data:**
   Open [http://localhost:5050](http://localhost:5050) to access pgAdmin and query the `utility_billing` table.

5. **Access Airflow:**
   Open [http://localhost:8080](http://localhost:8080) and log in with `admin`/`admin`.

### Running Tests Locally
```bash
pip install -r requirements.txt
python -m pytest tests/ -v
```

## Data Validation Results
The pipeline successfully processed the full dataset with the **Total Records Ingested:** 451,691

## Phases
- **Phase 1** - Core ETL pipeline (extract, transform, load)
- **Phase 2** - Dockerized infrastructure with PostgreSQL and pgAdmin
- **Phase 3** - CI/CD with GitHub Actions (tests + deploy)
- **Phase 4** - Cloud migration (Terraform + AWS RDS)
- **Phase 5** - Orchestration & scheduling with Apache Airflow
