#!/bin/bash

# Apply the YAML (assumes cribl-k8s.yaml in current dir)
kubectl apply -f cribl-k8s.yaml

# Wait for master and workers to be ready
echo "Waiting for Cribl master to be ready..."
kubectl wait --for=condition=Ready pods -l app=cribl-master --timeout=300s

echo "Waiting for Cribl workers to be ready..."
kubectl wait --for=condition=Ready pods -l app=cribl-workers --timeout=300s

# Verify master status
echo "Checking master health..."
kubectl exec -it $(kubectl get pods -l app=cribl-master -o jsonpath='{.items[0].metadata.name}') -- curl -s http://localhost:9000/api/v1/health

# Provide access instructions
echo "Deployment complete. Access Cribl UI via port-forward: kubectl port-forward svc/cribl-master 19000:9000"
echo "Worker data endpoints available at svc/cribl-workers (e.g., 10200 for Elastic, 10088 for HEC)."