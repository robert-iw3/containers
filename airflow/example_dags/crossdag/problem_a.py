# -*- coding: utf-8 -*-

from datetime import timedelta

from airflow import DAG
from airflow.operators.empty import EmptyOperator
from airflow.utils.dates import days_ago

DAG_NAME = 'problem_a'
DEFAULT_ARGS = {
    'owner': 'Operations+Finance',
    'depends_on_past': False,
    'start_date': days_ago(2),
    'email': ['operations+airflow@example.com', 'finance+airflow@example.com'],
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

    calculate_revenue = EmptyOperator(task_id='operations_calculate_revenue',
                                      dag=dag)

    income_bookkeep = EmptyOperator(task_id='finances_income_bookkeep',
                                    dag=dag)

    validate_income = EmptyOperator(task_id='finances_validate_income',
                                    dag=dag)

    calculate_expenses = EmptyOperator(task_id='operations_calculate_expenses',
                                       dag=dag)

    outcome_bookkeep = EmptyOperator(task_id='finances_outcome_bookkeep',
                                     dag=dag)

    operations_a_report = EmptyOperator(task_id='operations_a_report',
                                        dag=dag)

    finance_a_report = EmptyOperator(task_id='finance_a_report',
                                     dag=dag)

    calculate_revenue >> income_bookkeep >> validate_income
    calculate_expenses >> outcome_bookkeep

    validate_income >> finance_a_report
    outcome_bookkeep >> finance_a_report

    income_bookkeep >> operations_a_report
    outcome_bookkeep >> operations_a_report
