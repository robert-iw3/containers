from datetime import datetime, timedelta
import pendulum

from airflow import DAG
from airflow.operators.bash import BashOperator


with DAG(
    dag_id="setup_dag",
    schedule="@once",
    start_date=pendulum.datetime(2022, 1, 1, tz="UTC"),
    catchup=False,
    dagrun_timeout=timedelta(minutes=60),
    tags=["pipeline"],
    params={"example_key": "example_value"},
) as dag:

    create_connection = BashOperator(
        task_id="create_connection",
        bash_command="""
        airflow connections add 'postgres_default' \
        --conn-json '{
            "conn_type": "postgres",
            "host": "postgres",
            "port": 5432,
            "schema": "postgres",
            "login": "airflow",
            "password": "airflow",
            "extra": { "sslmode": "disable" }
        }'
        """,
    )

    create_variable = BashOperator(
        task_id="create_variable",
        bash_command="""
        airflow variables set 'environment' 'local'
        """,
    )

    create_connection >> create_variable
