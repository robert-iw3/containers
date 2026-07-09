import datetime

import pendulum

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator


def paths(**context) -> None:
    import sys
    import pprint

    pprint.pprint(sys.path)


def paths2(**context) -> None:
    import sys
    import pprint

    sys.path.append("/opt/airflow/dags/module")
    pprint.pprint(sys.path)


with DAG(
    dag_id="pip_dag",
    schedule="0 0 * * *",
    start_date=pendulum.datetime(2022, 1, 1, tz="UTC"),
    catchup=False,
    dagrun_timeout=datetime.timedelta(minutes=60),
    tags=["pipeline"],
    params={"example_key": "example_value"},
) as dag:

    # [START howto_operator_bash]
    requirements = BashOperator(
        task_id="running_pip_requirements",
        bash_command="pip3 list",
    )

    sys_path = PythonOperator(
        task_id="sys_path",
        python_callable=paths,
    )

    sys_path2 = PythonOperator(
        task_id="sys_path2",
        python_callable=paths2,
    )


if __name__ == "__main__":
    dag.cli()
