# Winnipeg Energy Ingestion Pipeline

## Overview
ETL pipeline that ingests municipal utility billing data from Winnipeg's Open Data portal into AWS RDS PostgreSQL, orchestrated by Apache Airflow on a monthly schedule. As of the September 17, 2026 profiling snapshot, the dataset contains 464,597 electricity and natural gas billing records.

The project is currently being modernized toward a layered data architecture — see [docs/technical_history.md](docs/technical_history.md) for current status and technical history.

## Tech Stack
- **Language:** Python 3.12
- **Libraries:** `sodapy`, `psycopg2`, `python-dotenv`, `pytest`
- **Database:** PostgreSQL 16 on AWS RDS
- **Infrastructure:** Terraform, Docker & Docker Compose
- **Orchestration:** Apache Airflow 2.9.0
- **Database GUI:** pgAdmin 4
- **CI/CD:** GitHub Actions

## Architecture

Socrata API → extract → type-cast/transform → PostgreSQL `COPY` load, scheduled monthly by Airflow. Deployed to AWS RDS via Terraform, with GitHub Actions running tests and deploying on push to `master`.

See [docs/technical_history.md](docs/technical_history.md) for the detailed technical walkthrough of each stage.

## Project Structure
```
winnipeg_energy_pipeline/
├── etl/
│   ├── __init__.py
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
│   ├── __init__.py
│   └── test_transform.py     # Unit tests for the transform layer
├── .github/workflows/
│   └── ci.yml                # GitHub Actions CI/CD pipeline
├── docker-compose.yml        # PostgreSQL + pgAdmin + ETL + Airflow services
├── Dockerfile
├── docs/
│   └── technical_history.md  # Technical documentation of the codebase
├── requirements.txt
├── .gitignore
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

## Phases
- **Phase 1** - Core ETL pipeline (extract, transform, load)
- **Phase 2** - Dockerized infrastructure with PostgreSQL and pgAdmin
- **Phase 3** - CI/CD with GitHub Actions (tests + deploy)
- **Phase 4** - Cloud migration (Terraform + AWS RDS)
- **Phase 5** - Orchestration & scheduling with Apache Airflow
