# Winnipeg Energy Ingestion Pipeline

## Overview
A production-grade ETL (Extract, Transform, Load) pipeline that processes municipal utility billing data for the **City of Winnipeg**. The system automates the ingestion of electricity and natural gas consumption data from Winnipeg's Open Data portal, providing a structured foundation for large-scale energy analysis and climate action benchmarking.

## Tech Stack
- **Language:** Python 3.12
- **Libraries:** `sodapy`, `psycopg2`, `python-dotenv`, `pytest`
- **Database:** PostgreSQL 16 (Alpine)
- **Infrastructure:** Docker & Docker Compose
- **Database GUI:** pgAdmin 4
- **CI/CD:** GitHub Actions

## Architecture

```
Socrata Open Data API
        |
        v
  [ Extract ]  -->  Pull 450,000+ records via sodapy
        |
        v
  [ Transform ] -->  Type-cast 35 fields (Text, Int, Float, Timestamp)
        |
        v
  [   Load   ]  -->  Bulk insert into PostgreSQL
```

| Layer         | Description                                                                 |
|---------------|-----------------------------------------------------------------------------|
| **Extract**   | Connects to the Socrata API and pulls from the Winnipeg Utility Billing dataset (`49ge-5j9g`). |
| **Transform** | Type-casts 35 raw API fields into structured SQL types (Numeric, BigInt, Timestamps) with safe handling of missing/malformed data. |
| **Load**      | Parameterized inserts into a containerized PostgreSQL instance via `psycopg2`. |
| **CI/CD**     | Pytest suite runs automatically via GitHub Actions on every push and PR to `master`. |

## Project Structure
```
winnipeg_energy_pipeline/
├── etl/
│   ├── extract.py        # Socrata API client
│   ├── transform.py      # Data cleaning & type-casting
│   ├── load.py           # PostgreSQL insertion
│   └── pipeline.py       # Orchestrates the full ETL run
├── sql/
│   └── init.sql          # Table schema (auto-runs on container start)
├── tests/
│   └── test_transform.py # Unit tests for the transform layer
├── .github/workflows/
│   └── ci.yml            # GitHub Actions CI pipeline
├── docker-compose.yml    # PostgreSQL + pgAdmin + ETL services
├── Dockerfile
├── requirements.txt
└── .env.example
```

## Getting Started

### Prerequisites
- Docker & Docker Compose
- Git

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
   This starts PostgreSQL, pgAdmin, and runs the ETL pipeline.

4. **Explore the data:**
   Open [http://localhost:5050](http://localhost:5050) to access pgAdmin and query the `utility_billing` table.

### Running Tests Locally
```bash
pip install -r requirements.txt
python -m pytest tests/ -v
```

## Data Validation Results
The pipeline successfully processed the full dataset with the following results verified via SQL:
- **Total Records Ingested:** 451,691
- **Data Integrity:** 0 NULL values in critical `amount_due` fields after transformation
