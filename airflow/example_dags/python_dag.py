import datetime

import pendulum

from airflow import DAG
from airflow.operators.python import PythonOperator


def python_script() -> None:
    print("Hello World")


with DAG(
    dag_id="python_dag",
    schedule="0 0 * * *",
    start_date=pendulum.datetime(2022, 1, 1, tz="UTC"),
    catchup=False,
    dagrun_timeout=datetime.timedelta(minutes=60),
    tags=["pipeline"],
    params={"example_key": "example_value"},
) as dag:
    python_task = PythonOperator(
        task_id="python_task",
        python_callable=lambda: python_script(),
    )

if __name__ == "__main__":
    dag.cli()
