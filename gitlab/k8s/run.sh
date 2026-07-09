#!/bin/bash
set -eou pipefail

if ! command -v kubectl > /dev/null; then
  echo "kubectl command not installed, please install kubectl"
  exit 1
fi

# create the services
for svc in *-svc.yml
do
  echo -n "Creating $svc... "
  kubectl -f $svc create
done

# create the replication controllers
for rc in *-rc.yml
do
  echo -n "Creating $rc... "
  kubectl -f $rc create
done

# list pod,rc,svc
echo -e "Pod:\n\n"
kubectl get pod

echo -e "RC:\n\n"
kubectl get rc

echo -e "Service:\n\n"
kubectl get svc
