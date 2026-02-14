from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime

from etl.pipeline import run

with DAG(
    dag_id="winnipeg_energy_etl",
    schedule="0 0 1 * *",
    start_date=datetime(2025, 1, 1),
    catchup=False,
) as dag:
    run_etl = PythonOperator(
        task_id="run_etl_pipeline",
        python_callable=run,
    )
