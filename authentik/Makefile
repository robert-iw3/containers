.PHONY: all generate-env deploy-docker deploy-podman deploy-k8s clean

all: generate-env deploy-docker

generate-env: python3 deploy.py --generate-env

deploy-docker: python3 deploy.py --deploy docker --compose-file prod-docker-compose.yml

deploy-podman: python3 deploy.py --deploy podman --compose-file prod-docker-compose.yml

deploy-k8s: python3 deploy.py --deploy kubernetes --k8s-manifest authentik-k8s.yml

clean: docker-compose -f prod-docker-compose.yml down -v || podman-compose -f prod-docker-compose.yml down -v kubectl delete -f authentik-k8s.yml --ignore-not-found