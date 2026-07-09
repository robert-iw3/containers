## middleware.io

[![middleware.io](https://img.youtube.com/vi/SXWescUAiUg/0.jpg)](https://www.youtube.com/watch?v=SXWescUAiUg)

### usage
---

Install dependencies: `pip install docker podman kubernetes ansible-runner`

Ensure Docker, Podman, kubectl, or Ansible is installed on the target system.

Save all artifacts (Dockerfile, YAMLs) in the same directory.

```bash
python deploy_mw_agent.py --method docker --api-key your-key --target https://ingest.middleware.io --tags "env:prod,team:ops"
```

Replace --method with podman, kubernetes, or ansible as needed. For Kubernetes, ensure manifests are in the directory. For Ansible, ensure the playbook is present.

### verify
---

Docker/Podman: `docker logs mw-agent` or `podman logs mw-agent`.

Kubernetes: `kubectl get pods -n monitoring`.

Ansible: Check playbook output or `docker ps` on target hosts.

Data should appear in Middleware dashboard within minutes.