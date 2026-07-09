#!/bin/bash

# Apply the YAML (assumes cassandra-k8s.yaml in current dir)
kubectl apply -f cassandra-k8s.yaml

# Wait for StatefulSet to be ready
echo "Waiting for Cassandra pods to be ready..."
kubectl wait --for=condition=Ready pods -l app=cassandra --timeout=600s

# Verify cluster status (from first pod)
echo "Checking cluster status..."
kubectl exec -it cassandra-0 -- nodetool status

echo "Deployment complete. Connect to CQL via port-forward: kubectl port-forward svc/cassandra 9042:9042"