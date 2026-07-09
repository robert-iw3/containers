import datetime

import pendulum

from airflow import DAG
from airflow.operators.empty import EmptyOperator
from airflow.operators.datetime import BranchDateTimeOperator


def python_script() -> None:
    print("Hello World")


with DAG(
    dag_id="datetime_dag",
    schedule="0 0 * * *",
    start_date=pendulum.datetime(2022, 1, 1, tz="UTC"),
    catchup=False,
    dagrun_timeout=datetime.timedelta(minutes=60),
    tags=["pipeline"],
    params={"example_key": "example_value"},
) as dag:

    empty_task_12 = EmptyOperator(task_id="date_in_range", dag=dag)
    empty_task_22 = EmptyOperator(task_id="date_outside_range", dag=dag)

    cond = BranchDateTimeOperator(
        task_id="datetime_branch",
        follow_task_ids_if_true=["date_in_range"],
        follow_task_ids_if_false=["date_outside_range"],
        target_upper=pendulum.time(0, 0, 0),
        target_lower=pendulum.time(15, 0, 0),
        dag=dag,
    )

    cond >> [empty_task_12, empty_task_22]

if __name__ == "__main__":
    dag.cli()
