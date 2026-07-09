#!/bin/bash

set -e

NAMESPACE="falco"

helm repo add falcosecurity https://falcosecurity.github.io/charts
helm repo add traefik https://traefik.github.io/charts
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update

# Install Traefik
helm install traefik traefik/traefik --namespace "${NAMESPACE}" --create-namespace --values traefik-values.yaml

# Install Redis
helm install redis bitnami/redis --namespace "${NAMESPACE}" --set architecture=standalone --set persistence.size=10Gi

# Install Falco
helm install falco falcosecurity/falco --namespace "${NAMESPACE}" --set tty=true --set falcosidekick.enabled=true --set falcosidekick.webui.enabled=true --values falco-values.yaml

# Deploy TinyAuth and other custom resources
kubectl apply -f tinyauth-k8s.yaml

kubectl wait --for=condition=Ready pod -l app.kubernetes.io/name=traefik -n "${NAMESPACE}" --timeout=300s
kubectl wait --for=condition=Ready pod -l app.kubernetes.io/name=redis -n "${NAMESPACE}" --timeout=300s
kubectl wait --for=condition=Ready pod -l app.kubernetes.io/name=falco -n "${NAMESPACE}" --timeout=300s

echo "Deployment complete. Access via LoadBalancer IP or port-forward."