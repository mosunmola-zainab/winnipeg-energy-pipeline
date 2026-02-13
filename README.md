# Winnipeg Energy Ingestion Pipeline

## Overview
This project is a production-grade ETL (Extract, Transform, Load) pipeline designed to process municipal utility billing data for the **City of Winnipeg**. The system automates the ingestion of electricity and natural gas consumption data, providing a structured foundation for large-scale energy analysis and climate action benchmarking.



## Tech Stack
- **Language:** Python 3.12 (using `sodapy`, `psycopg2`, and `pandas`)
- **Infrastructure:** Docker & Docker Compose for containerized microservices
- **Database:** PostgreSQL 16 (optimized for analytical queries)
- **CI/CD:** GitHub Actions for automated unit testing and quality assurance

## System Architecture
1. **Extraction Layer**: Interface with the Socrata Open Data API to pull over **450,000+ records** from the Winnipeg Utility Billing dataset (`49ge-5j9g`).
2. **Transformation Layer**: A robust Python cleaning module that type-casts 35 raw API fields into structured SQL types (Numeric, BigInt, Timestamps) while handling missing data gracefully.
3. **Loading Layer**: High-volume ingestion into a containerized PostgreSQL instance.
4. **DevOps/CI**: Automated Pytest suite triggered via GitHub Actions on every push to ensure code stability and transformation accuracy.

## Data Validation Results
The pipeline successfully processed the full dataset with the following results verified via SQL:
- **Total Records Ingested:** 451,691
- **Data Integrity:** 0 NULL values found in critical `amount_due` fields after transformation

## Getting Started

### Prerequisites
- Docker & Docker Compose
- Git

### Installation & Execution
1. **Clone the repository:**
   ```bash
   git clone [https://github.com/mosunmola-zainab/winnipeg-energy-pipeline.git](https://github.com/mosunmola-zainab/winnipeg-energy-pipeline.git)
   cd winnipeg-energy-pipeline

2. **Setup Environment:**
Create a `.env` file in the root directory based on the provided `.env.example` template and populate it with your local PostgreSQL credentials.

3. **Run the Pipeline:**
Execute the following command to build the images and start the containerized services:
    ```bash
    docker-compose up --build