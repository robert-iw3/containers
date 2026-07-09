from datetime import datetime, timedelta
import pendulum

from airflow import DAG
from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator

# TODO: To get this dag working. You need to set up a
# postgres_default connection in the Airflow UI. Admin -> Connections -> Create

# NOTE: You can run the "setup DAG". It will setup all the connections for you.

with DAG(
    dag_id="postgres_dag",
    schedule="0 0 * * *",
    start_date=pendulum.datetime(2022, 1, 1, tz="UTC"),
    catchup=False,
    dagrun_timeout=timedelta(minutes=60),
    tags=["pipeline"],
    params={"example_key": "example_value"},
) as dag:

    create_table = SQLExecuteQueryOperator(
        conn_id="postgres_default",
        retries=2,
        retry_delay=timedelta(seconds=5),
        task_id="create_table",
        sql="""
            CREATE TABLE IF NOT EXISTS events (
                id SERIAL PRIMARY KEY,
                event_name VARCHAR(50) NOT NULL,
                event_value INTEGER NOT NULL,
                created_at TIMESTAMP NOT NULL
            );
            """,
    )

    populate_table = SQLExecuteQueryOperator(
        conn_id="postgres_default",
        retries=2,
        retry_delay=timedelta(seconds=5),
        task_id="populate_table",
        sql="""
            INSERT INTO events (event_name, event_value, created_at) VALUES ('example', 1, NOW());
            """,
    )

    get_table = SQLExecuteQueryOperator(
        conn_id="postgres_default",
        retries=2,
        retry_delay=timedelta(seconds=5),
        task_id="get_table",
        sql="""
            SELECT * FROM events;
            """,
    )

    create_table >> populate_table >> get_table

if __name__ == "__main__":
    dag.cli()
