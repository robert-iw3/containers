# CI image builds

The GitHub (`.github/workflows/docker-build.yml`) and GitLab (`.gitlab-ci.yml`)
pipelines build, Trivy-scan, and publish container images to GHCR. Selection of
which Dockerfiles to build is shared logic in `ci/dockerfile_targets.py`.

There are **~426 Dockerfiles** in this repo, so nothing is built implicitly.

## Default: the manifest

On every push/PR the pipelines build exactly what `ci/build.yaml` declares:

```yaml
build:
  - elastic/data-pipeline/logstash
  - elastic/apm-server
```

Each entry is a Dockerfile path, a directory, or a glob (matched against
Dockerfile paths). An **empty manifest builds nothing**. Add a directory when its
image is ready to publish; remove it to stop building it.

## On-demand overrides (manual run)

| Intent | GitHub input | GitLab variable |
| --- | --- | --- |
| Build a chosen subset | `paths` = `elastic/data-pipeline/*, elastic/apm-server` | `BUILD_PATHS` |
| Build everything | `build_all` = true | `BUILD_ALL=true` |
| Build changed contexts | `build_changed` = true | `BUILD_CHANGED=true` |

`build_changed` rebuilds a Dockerfile when **any file in its build context**
changed (not just the Dockerfile), so editing a config or pipeline that the image
`COPY`s triggers a rebuild.

## Rules enforced by `tests/test_ci.py`

- Archived Dockerfiles (`**/archive/**`) are never built.
- Every Dockerfile whose `FROM` references an `ARG` must default it (both CIs run
  `docker build` with no `--build-arg`).
- Image names may nest with `/` for GHCR; artifact/scan names are `/`-free.
- Every `ci/build.yaml` entry must resolve to at least one buildable Dockerfile.
