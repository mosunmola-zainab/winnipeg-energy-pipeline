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
