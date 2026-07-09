import datetime

import pendulum

from airflow import DAG
from airflow.operators.python import PythonOperator

# This dag will template over a set of offices locations.
# This is how your can do basic iteration over pipelines.


def python_script() -> None:
    print("Hello World")


with DAG(
    dag_id="template_dag",
    schedule="0 0 * * *",
    start_date=pendulum.datetime(2022, 1, 1, tz="UTC"),
    catchup=False,
    dagrun_timeout=datetime.timedelta(minutes=60),
    tags=["pipeline"],
    params={"example_key": "example_value"},
) as dag:

    COUNTRIES = ["usa", "uk", "canada", "australia", "new_zealand"]

    initial_task = PythonOperator(
        task_id=f"initial_task",
        python_callable=lambda: python_script(),
    )

    closing_task = PythonOperator(
        task_id=f"closing_task",
        python_callable=lambda: python_script(),
    )

    for country in COUNTRIES:
        cleaning_task = PythonOperator(
            task_id=f"cleaning_metrics_{country}",
            python_callable=lambda: python_script(),
        )

        processing_task = PythonOperator(
            task_id=f"processing_metrics_{country}",
            python_callable=lambda: python_script(),
        )

        initial_task >> cleaning_task
        cleaning_task >> processing_task
        processing_task >> closing_task

if __name__ == "__main__":
    dag.cli()
