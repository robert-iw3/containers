## GuardDog

https://github.com/DataDog/guarddog

GuardDog is a CLI tool that allows to identify malicious PyPI and npm packages, Go modules, GitHub actions, or VSCode extensions. It runs a set of heuristics on the package source code (through Semgrep rules) and on the package metadata.

GuardDog can be used to scan local or remote PyPI and npm packages, Go modules, GitHub actions, or VSCode extensions using any of the available [heuristics](#heuristics).

It downloads and scans code from:

* NPM: Packages hosted in [npmjs.org](https://www.npmjs.com/)
* PyPI: Source files (tar.gz) packages hosted in [PyPI.org](https://pypi.org/)
* Go: GoLang source files of repositories hosted in [GitHub.com](https://github.com)
* GitHub Actions: Javascript source files of repositories hosted in [GitHub.com](https://github.com)
* VSCode Extensions: Extensions (.vsix) packages hosted in [marketplace.visualstudio.com](https://marketplace.visualstudio.com/)

### GuardDog Automated Deployment, Scanning & CI/CD Pipeline
---

Interactive orchestration (`orchestrate_guarddog.py`) – wizard for podman/docker/kubernetes/ansible

Parallel, timeout-protected scans with Podman (default) or Docker

Kubernetes Job & Ansible deployment support

Zero-config CI/CD pipeline (`ci_guarddog_scan.py`) – auto-detects manifests and fails the build on malicious/suspicious packages

SARIF output → native integration with GitHub Code Scanning, GitLab SAST, etc.

Full multi-ecosystem support: pypi, npm, go, github_action, extension

### Quick Start – CI/CD Pipeline (Recommended for Every Repo)
---

Just drop these files into your repo root:

Dockerfile (official GuardDog image)

ci_guarddog_scan.py

Supported manifest files (auto-detected recursively):

Python: `requirements.txt`, `poetry.lock`, `Pipfile.lock`

npm: `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`

Go: `go.mod`

### Local / Interactive Orchestration
---

```bash
python3 orchestrate_guarddog.py
```

Interactive wizard:

    Chooses deployment method (podman default)

    Validates & auto-fixes packages.yaml

    Builds image

    Runs scans (parallel, timeout-protected)

Standalone Scripts

`deploy_guarddog.py` – core engine (used by orchestrator)

`scan_packages.sh` / `scan_packages.py` – fast parallel local scans

`ci_guarddog_scan.py` – CI/CD pipeline script (above)

    All scripts use Podman by default (rootless & secure).

    Override with environment variable: CONTAINER_RUNTIME=docker

### Create a packages.yaml manifest
---

```yaml
packages:
  - name: requests
    result_name: requests
  - name: express
    result_name: express
    ecosystem: npm
  - name: github.com/gin-gonic/gin
    result_name: gin
    ecosystem: go
```

The orchestrator will auto-add missing ecosystem (defaults to pypi) and result_name.

### Generate a packages.yaml manifest
---

Alternatively, you can run `generate_packages_yaml.py` to generate a packages.yaml file scanning the current directory for all scripts to see what packages are being imported.

```bash
python generate_packages_yaml.py # scans current dir → packages.yaml
python generate_packages_yaml.py --dir ./myapp --output custom.yaml
```