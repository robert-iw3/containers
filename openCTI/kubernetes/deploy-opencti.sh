#!/bin/bash

# Script to deploy OpenCTI on Kubernetes
# Assumptions: kubectl is configured and points to the correct cluster
#             You have edited opencti-k8s.yaml with actual secret values

YAML_FILE="opencti-k8s.yaml"

# Check if file exists
if [ ! -f "$YAML_FILE" ]; then
  echo "Error: $YAML_FILE not found!"
  exit 1
fi

# Apply the YAML
kubectl apply -f "$YAML_FILE"

# Wait for namespace to be created
sleep 5

# Verify deployments
kubectl get all -n opencti

# Optional: Wait for pods to be ready
kubectl wait --for=condition=Ready pods --all -n opencti --timeout=600s

echo "Deployment completed. Access OpenCTI at the Ingress host or NodePort."