#!/bin/bash

minikube start
helm repo add milvus https://milvus-io.github.io/milvus-helm/
helm repo update
helm install my-release milvus/milvus --set cluster.enabled=false --set etcd.replicaCount=1 --set minio.mode=standalone --set pulsar.enabled=false
kubectl get pods; sleep 10s
kubectl get pod my-release-milvus-standalone-54c4f88cb9-f84pf --template='{{(index (index .spec.containers 0).ports 0).containerPort}}{{"\n"}}'
kubectl port-forward service/my-release-milvus 27017:19530
