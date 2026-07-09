# This is a example of how to push and pull values from XCOM

from datetime import datetime, timedelta
import pendulum

from airflow import DAG
from airflow.operators.python import PythonOperator


def send_context(**context) -> None:

    # We send the task context into the function. So we can
    # retrieve the task instance and push the value into XCOM.

    for key, value in context.items():
        print(f"{key}: {value}")

    task_instance = context["task_instance"]
    task_instance.xcom_push(key="message", value="Hello World")


def retrieve_context(**context) -> None:

    # This is how you retrieve the value from XCOM. In this case the string
    # value is returned. I recommend using a dictionary to store multiple values
    # in XCOM in production code.

    task_instance = context["task_instance"]
    xcom_value = task_instance.xcom_pull(task_ids="context_task", key="message")
    print("xcom_value: ", xcom_value)


with DAG(
    dag_id="xcom_dag",
    schedule="0 0 * * *",
    start_date=pendulum.datetime(2022, 1, 1, tz="UTC"),
    catchup=False,
    dagrun_timeout=timedelta(minutes=60),
    tags=["pipeline"],
    params={"example_key": "example_value"},
) as dag:

    context_task = PythonOperator(
        task_id="context_task",
        python_callable=send_context,
    )

    retrieve_task = PythonOperator(
        task_id="retrieve_task",
        python_callable=retrieve_context,
    )

    context_task >> retrieve_task


if __name__ == "__main__":
    dag.cli()
