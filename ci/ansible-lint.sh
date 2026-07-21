#!/bin/sh
# Validate the identity stacks' Ansible deploy playbooks with ansible-lint,
# run from a container (no host ansible install needed) — mirrors the
# container-first approach used for terraform.
#
#   ci/ansible-lint.sh            # lint all stack deploy playbooks
#   ci/ansible-lint.sh <files...> # lint specific playbooks
#
# Requires podman (or set RUNTIME=docker).
set -eu

RUNTIME="${RUNTIME:-podman}"
IMAGE="${ANSIBLE_LINT_IMAGE:-docker.io/pipelinecomponents/ansible-lint:latest}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Default set: every stack's deploy playbook, plus the extra k8s/cluster ones.
if [ "$#" -gt 0 ]; then
    PLAYBOOKS="$*"
else
    PLAYBOOKS="authentik/ansible/deploy.yml keycloak/ansible/deploy.yml hanko/ansible/deploy.yml hanko/ansible/deploy-k8s.yml tinyauth/ansible/deploy.yml zitadel/ansible/deploy.yml freeipa/ansible/deploy.yml freeipa/playbooks/install-cluster.yml"
fi

# The freeipa cluster playbook references roles from freeipa.ansible_freeipa;
# install that collection inside the container so lint can resolve them.
exec "$RUNTIME" run --rm -v "$REPO_ROOT":/data:z -w /data "$IMAGE" sh -c \
    "ansible-galaxy collection install -r freeipa/playbooks/requirements.yml >/dev/null 2>&1 || true
     ansible-lint $PLAYBOOKS"
