#!/bin/bash

HELM_VER=3.13.1

wget --progress=bar:force -O helm.tar.gz \
https://get.helm.sh/helm-v${HELM_VER}-linux-amd64.tar.gz

tar zxvf helm.tar.gz
mv helm/linux-amd64/helm /usr/local/bin/helm

helm repo add grafana https://grafana.github.io/helm-charts

helm repo update

helm install --values values.yaml loki grafana/loki

