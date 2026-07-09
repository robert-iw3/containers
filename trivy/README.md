## Trivy:

<p align="center">
    <a href="https://github.com/robert-iw3/apps/actions/workflows/trivy-ghcr.yml" alt="Docker CI">
          <img src="https://github.com/robert-iw3/apps/actions/workflows/trivy-ghcr.yml/badge.svg" /></a>
</p>

[What is Trivy?](https://www.aquasec.com/products/trivy/)

```sh
podman build -t trivy .
podman network create trivy
mkdir -p ./scan_results/{trivy-cache,trivy-reports}

#html
podman run --rm -it -v ./scan_results/trivy-cache/:/root/.cache/:Z \
                -v ./scan_results/trivy-reports:/output:Z \
                --network trivy --security-opt=no-new-privileges trivy trivy image \
                --format template --template "@/home/trivy/html.tpl" \
                -o /output/<Report Name_Changeme>.html \
                <registry/user/image_name:tag>

#json
podman run --rm -it -v ./scan_results/trivy-cache/:/root/.cache/:Z \
                -v ./scan_results/trivy-reports:/output:Z \
                --network trivy --security-opt=no-new-privileges trivy trivy image \
                -f json -o /output/<Report Name_Changeme>.json \
                <registry/user/image_name:tag>

#xml
podman run --rm -it -v ./scan_results/trivy-cache/:/root/.cache/:Z \
                -v ./scan_results/trivy-reports:/output:Z \
                --network trivy --security-opt=no-new-privileges trivy trivy image \
                --format template --template "@/home/trivy/junit.tpl" \
                -o /output/<Report Name_Changeme>.xml \
                <registry/user/image_name:tag>
```

```console
# Trivy now supports scanning for vulnerabilities in the Kubernetes control plane and node components.
# Instead of using the Kubernetes cluster version, it leverages KBOM to identify individual component versions like kubelet for more accurate detection.

# Generate KBOM first

$ trivy k8s --format cyclonedx cluster -o kbom.json

# Then, scan KBOM for vulnerabilities
$ trivy sbom kbom.json
2023-09-28T22:52:25.707+0300    INFO    Vulnerability scanning is enabled
2023-09-28T22:52:25.707+0300    INFO    Detected SBOM format: cyclonedx-json
2023-09-28T22:52:25.717+0300    WARN    No OS package is detected. Make sure you haven't deleted any files that contain information about the installed packages.
2023-09-28T22:52:25.717+0300    WARN    e.g. files under "/lib/apk/db/", "/var/lib/dpkg/" and "/var/lib/rpm"
2023-09-28T22:52:25.717+0300    INFO    Detected OS: debian gnu/linux
2023-09-28T22:52:25.717+0300    WARN    unsupported os : debian gnu/linux
2023-09-28T22:52:25.717+0300    INFO    Number of language-specific files: 3
2023-09-28T22:52:25.717+0300    INFO    Detecting kubernetes vulnerabilities...
2023-09-28T22:52:25.718+0300    INFO    Detecting gobinary vulnerabilities...

Kubernetes (kubernetes)
=======================
Total: 2 (UNKNOWN: 0, LOW: 1, MEDIUM: 0, HIGH: 1, CRITICAL: 0)

┌────────────────┬────────────────┬──────────┬────────┬───────────────────┬─────────────────────────────────┬──────────────────────────────────────────────────┐
│    Library     │ Vulnerability  │ Severity │ Status │ Installed Version │          Fixed Version          │                      Title                       │
├────────────────┼────────────────┼──────────┼────────┼───────────────────┼─────────────────────────────────┼──────────────────────────────────────────────────┤
│ k8s.io/kubelet │ CVE-2021-25749 │ HIGH     │ fixed  │ 1.24.0            │ 1.22.14, 1.23.11, 1.24.5        │ runAsNonRoot logic bypass for Windows containers │
│                │                │          │        │                   │                                 │ https://avd.aquasec.com/nvd/cve-2021-25749       │
│                ├────────────────┼──────────┤        │                   ├─────────────────────────────────┼──────────────────────────────────────────────────┤
│                │ CVE-2023-2431  │ LOW      │        │                   │ 1.24.14, 1.25.9, 1.26.4, 1.27.1 │ Bypass of seccomp profile enforcement            │
│                │                │          │        │                   │                                 │ https://avd.aquasec.com/nvd/cve-2023-2431        │
└────────────────┴────────────────┴──────────┴────────┴───────────────────┴─────────────────────────────────┴──────────────────────────────────────────────────┘

```
