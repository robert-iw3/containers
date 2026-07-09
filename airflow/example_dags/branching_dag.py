import datetime

import pendulum
import random

from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.utils.edgemodifier import Label
from airflow.utils.trigger_rule import TriggerRule
from airflow.operators.empty import EmptyOperator


def python_script() -> None:
    print("Hello World")


with DAG(
    dag_id="branching_dag",
    schedule="0 0 * * *",
    start_date=pendulum.datetime(2022, 1, 1, tz="UTC"),
    catchup=False,
    dagrun_timeout=datetime.timedelta(minutes=60),
    tags=["pipeline"],
    params={"example_key": "example_value"},
) as dag:

    OPTIONS = ["branch_a", "branch_b", "branch_c", "branch_d"]

    python_task = PythonOperator(
        task_id="python_task",
        python_callable=lambda: python_script(),
    )

    branching_task = BranchPythonOperator(
        task_id="branching",
        python_callable=lambda: random.choice(OPTIONS),
    )

    python_task >> branching_task

    for option in OPTIONS:
        processing_task = EmptyOperator(
            task_id=f"{option}",
        )
        closing_task = EmptyOperator(
            task_id=f"closing_{option}",
        )
        branching_task >> processing_task >> closing_task


if __name__ == "__main__":
    dag.cli()
