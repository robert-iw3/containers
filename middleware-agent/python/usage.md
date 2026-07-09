## python apm

```sh
pip install middleware-apm
```

```py
# add to top of main
import logging

from middleware import MwTracker
tracker=MwTracker()
```

```sh
# Applications running in a container require an additional environment variable.

# docker
MW_AGENT_SERVICE=<DOCKER_BRIDGE_GATEWAY_ADDRESS>

# k8s
kubectl get service --all-namespaces | grep mw-service

MW_AGENT_SERVICE=mw-service.mw-agent-ns.svc.cluster.local
```

## agent install

```sh
# docker

# Copy and run the installation command.
# Copy the command directly from the Installation page to ensure your API key and UID are correct
MW_API_KEY=<xxxxxxxxxx> MW_TARGET=https://<uid>.middleware.io:443 \
    bash -c "$(curl -L https://install.middleware.io/scripts/docker-install.sh)"
# verify
docker ps -a --filter ancestor=ghcr.io/middleware-labs/mw-host-agent:master


# k8s

# Get the current Kubernetes context and ensure that the cluster belonging
# to this context is where you want to install MW Agent.
kubectl config get-contexts `kubectl config current-context`

MW_API_KEY=<xxxxxxxxxx> MW_TARGET=https://<uid>.middleware.io:443 \
    bash -c "$(curl -L https://install.middleware.io/scripts/mw-kube-agent-install.sh)"

# verify
kubectl get daemonset/mw-kube-agent -n mw-agent-ns
```

```yaml
# configure ini file
#
[middleware.common]

# The name of your application as service-name, as it will appear in the UI to filter out your data.
service_name = {APM-SERVICE-NAME}

# This Token binds the Python Agent's data and profiling data to your account.
access_token = {YOUR-ACCESS-TOKEN}

# The service name, where Middleware Agent is running, in case of K8s.
mw_agent_service = mw-service.mw-agent-ns.svc.cluster.local

# Distributed traces for your application (false = disabled).
collect_traces = true

# Collection of metrics for your application (false = disabled).
collect_metrics = true

# Collection of logs for your application (false = disabled).
collect_logs = true

# Collection of profiling data for your application (false = disabled).
collect_profiling = true

```

```sh
MIDDLEWARE_CONFIG_FILE=./middleware.ini middleware-apm run python app.py
```