
# Migrate the metadata database. Normally handled by the airflow-init service in
# docker-compose (or the airflow-db-init Job in k8s-deployment.yaml). Kept here for
# reference / manual Kubernetes bootstraps.
# Airflow 3.x uses `db migrate` (the 2.x `db init` was removed).
# airflow db migrate;

# Then create the admin user (see users.sh).
