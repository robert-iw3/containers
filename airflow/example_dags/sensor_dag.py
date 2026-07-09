# import datetime

# import pendulum

# from airflow import DAG
# from airflow.operators.python import PythonOperator
# from airflow.sensors.external_task import ExternalTaskSensor

# def python_script() -> None:
#     print("Hello World")


# with DAG(
#     dag_id="sensor_dag",
#     schedule="0 0 * * *",
#     start_date=pendulum.datetime(2022, 1, 1, tz="UTC"),
#     catchup=False,
#     dagrun_timeout=datetime.timedelta(minutes=60),
#     tags=["pipeline"],
#     params={"example_key": "example_value"},
# ) as dag:

#     sensor_task = ExternalTaskSensor(
#         task_id="sensor_task",
#         external_dag_id="sensor_trigger_dag",
#         external_task_id="python_task",
#         allowed_states=["success"],
#         dag=dag,
#     )

#     python_task = PythonOperator(
#         task_id="python_task",
#         python_callable=lambda: python_script(),
#     )

#     sensor_task >> python_task

# if __name__ == "__main__":
#     dag.cli()
