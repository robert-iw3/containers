#!/usr/bin/env python3
"""Generate a GitLab child pipeline with one build/scan/push job per Dockerfile."""
import os
import sys

TEMPLATE = """
build:{job_name}:
  stage: build
  image: docker:27-cli
  services:
    - docker:27-dind
  variables:
    DOCKER_TLS_CERTDIR: "/certs"
    IMAGE: "$GHCR_REGISTRY/$GHCR_NAMESPACE/{image}"
    DOCKERFILE: "{dockerfile}"
    CONTEXT: "{context}"
  before_script:
    - apk add --no-cache curl >/dev/null
    - curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin
    - echo "$GHCR_TOKEN" | docker login "$GHCR_REGISTRY" -u "$GHCR_USERNAME" --password-stdin
  script:
    - docker build -f "$DOCKERFILE" -t "$IMAGE:$CI_COMMIT_SHORT_SHA" "$CONTEXT"
    - trivy image --format cyclonedx --output sbom-{job_name}.cdx.json "$IMAGE:$CI_COMMIT_SHORT_SHA"
    - trivy image --format table --severity CRITICAL,HIGH --ignore-unfixed --exit-code 1 "$IMAGE:$CI_COMMIT_SHORT_SHA"
  after_script:
    - |
      if [ "$CI_PIPELINE_SOURCE" != "merge_request_event" ]; then
        docker tag "$IMAGE:$CI_COMMIT_SHORT_SHA" "$IMAGE:latest"
        docker push "$IMAGE:$CI_COMMIT_SHORT_SHA"
        docker push "$IMAGE:latest"
      fi
  artifacts:
    when: always
    paths:
      - sbom-{job_name}.cdx.json
"""

NOOP = """
no-op:
  stage: build
  image: alpine:3.24
  script:
    - echo "No Dockerfiles to build for this pipeline."
"""


def sanitize(name: str) -> str:
    name = name.strip("./").lower()
    return "".join(c if (c.isalnum() or c in "-_/.") else "-" for c in name)


def main(files: list[str]) -> None:
    jobs = []
    for f in files:
        if not f or not os.path.isfile(f):
            continue
        d = os.path.dirname(f) or "."
        base = os.path.basename(f)
        suffix = base[len("Dockerfile"):].lstrip(".") if base.startswith("Dockerfile") else base
        image = sanitize(d if not suffix else f"{d}-{suffix}")
        job_name = image.replace("/", "-")
        jobs.append(TEMPLATE.format(job_name=job_name, image=image, dockerfile=f, context=d))

    print("\n".join(jobs) if jobs else NOOP)


if __name__ == "__main__":
    main(sys.argv[1:])
