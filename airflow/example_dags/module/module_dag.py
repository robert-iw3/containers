import datetime

import pendulum
import sys

from airflow import DAG
from airflow.operators.python import PythonOperator

sys.path.append("/opt/airflow/dags/module")

from module_tasks.core import ModuleTasks

with DAG(
    dag_id="module_dag",
    schedule="0 0 * * *",
    start_date=pendulum.datetime(2022, 1, 1, tz="UTC"),
    catchup=False,
    dagrun_timeout=datetime.timedelta(minutes=60),
    tags=["pipeline"],
    params={"example_key": "example_value"},
) as dag:

    module_tasks = ModuleTasks()

    python_task = PythonOperator(
        task_id="python_task",
        python_callable=lambda: module_tasks.python_script(),
    )

if __name__ == "__main__":
    dag.cli()
