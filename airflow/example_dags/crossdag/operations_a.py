# -*- coding: utf-8 -*-

from datetime import timedelta

from airflow import DAG
from airflow.operators.empty import EmptyOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.sensors.external_task import ExternalTaskSensor
from airflow.utils.dates import days_ago

DAG_NAME = 'operations_a'
DEFAULT_ARGS = {
    'owner': 'Operations',
    'depends_on_past': False,
    'start_date': days_ago(2),
    'email': ['operations+airflow@example.com'],
    'retries': 3,
    'retry_delay': timedelta(minutes=10),
    'email_on_failure': False,
    'email_on_retry': False
}

with DAG(dag_id=DAG_NAME,
         default_args=DEFAULT_ARGS,
         dagrun_timeout=timedelta(minutes=10),
         schedule_interval=None,
         tags=["crossdag"]) as dag:
    calculate_revenue = EmptyOperator(task_id='calculate_revenue',
                                      dag=dag)

    trigger_finances_a = TriggerDagRunOperator(task_id='trigger_finances_a',
                                               dag=dag,
                                               trigger_dag_id='finances_a',
                                               execution_date='{{ dag_run.logical_date }}')

    calculate_expenses = EmptyOperator(task_id='calculate_expenses',
                                       dag=dag)

    wait_finances_a_expenses_bookkept = ExternalTaskSensor(
        task_id='wait_finances_a_outcome_bookkeep',
        dag=dag,
        external_dag_id='finances_a',
        external_task_id='outcome_bookkeep',
        check_existence=True)

    operations_a_report = EmptyOperator(task_id='operations_a_report',
                                        dag=dag)

    calculate_revenue >> trigger_finances_a >> calculate_expenses
    calculate_expenses >> wait_finances_a_expenses_bookkept >> operations_a_report
