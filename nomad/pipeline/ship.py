#!/usr/bin/env python3
"""Build a container anywhere (CI or locally), ship it to a registry, and
initialize the workload on a Nomad cluster.

  ship.py build  <context-dir> --image ghcr.io/org/app:sha    # podman/docker build
  ship.py push   --image ghcr.io/org/app:sha                  # push to registry
  ship.py deploy --image ghcr.io/org/app:sha --name app \
                 --port 8080 [--count 2] [--job custom.nomad.hcl]

Cluster connection comes from the standard Nomad environment variables:
  NOMAD_ADDR   e.g. https://nomad.example.com:4646
  NOMAD_TOKEN  an ACL token allowed to submit jobs
  NOMAD_CACERT path to the cluster CA (required for the self-signed cluster CA)

deploy registers the job through the HTTP API (/v1/jobs/parse then /v1/jobs)
and polls the deployment until it is healthy, failing loudly otherwise.
"""

import argparse
import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

JOB_TEMPLATE = """
job "__NAME__" {
  datacenters = ["__DATACENTER__"]
  type        = "service"

  group "__NAME__" {
    count = __COUNT__

    update {
      max_parallel     = 1
      min_healthy_time = "10s"
      healthy_deadline = "3m"
      auto_revert      = true
    }

    network {
      port "http" {
        to = __PORT__
      }
    }

    task "__NAME__" {
      driver = "__DRIVER__"

      config {
        image = "__IMAGE__"
        ports = ["http"]
      }

      resources {
        cpu    = __CPU__
        memory = __MEMORY__
      }

      shutdown_delay = "5s"

      service {
        name     = "__NAME__"
        port     = "http"
        provider = "nomad"

        check {
          type     = "tcp"
          interval = "10s"
          timeout  = "3s"
        }
      }
    }
  }
}
"""


class ShipError(Exception):
    pass


def container_runtime():
    for runtime in ("podman", "docker"):
        if shutil.which(runtime):
            return runtime
    raise ShipError("neither podman nor docker found on PATH")


def validate_image(image):
    if not re.match(r"^[a-z0-9][a-z0-9._/-]*(:[A-Za-z0-9._-]+)?(@sha256:[0-9a-f]{64})?$", image):
        raise ShipError(f"invalid image reference: {image}")


def validate_name(name):
    if not re.match(r"^[a-z0-9][a-z0-9-]{0,62}$", name):
        raise ShipError(f"invalid job name '{name}': lowercase alphanumerics and hyphens only")


def build(args):
    validate_image(args.image)
    context = Path(args.context)
    if not (context / "Dockerfile").exists() and not args.file:
        raise ShipError(f"no Dockerfile in {context}; pass --file to point at one")
    runtime = container_runtime()
    cmd = [runtime, "build", "-t", args.image]
    if args.file:
        cmd += ["-f", args.file]
    cmd.append(str(context))
    print(f"$ {' '.join(cmd)}")
    if subprocess.run(cmd).returncode != 0:
        raise ShipError("build failed")
    print(f"built {args.image}")


def push(args):
    validate_image(args.image)
    runtime = container_runtime()
    cmd = [runtime, "push", args.image]
    print(f"$ {' '.join(cmd)}")
    if subprocess.run(cmd).returncode != 0:
        raise ShipError("push failed")
    print(f"pushed {args.image}")


def render_job(args):
    if args.job:
        hcl = Path(args.job).read_text()
        return hcl.replace("__IMAGE__", args.image)
    validate_name(args.name)
    substitutions = {
        "__NAME__": args.name,
        "__IMAGE__": args.image,
        "__DATACENTER__": args.datacenter,
        "__DRIVER__": args.driver,
        "__COUNT__": str(args.count),
        "__PORT__": str(args.port),
        "__CPU__": str(args.cpu),
        "__MEMORY__": str(args.memory),
    }
    hcl = JOB_TEMPLATE
    for key, value in substitutions.items():
        hcl = hcl.replace(key, value)
    return hcl


class NomadClient:
    def __init__(self):
        self.addr = os.environ.get("NOMAD_ADDR", "").rstrip("/")
        if not self.addr:
            raise ShipError("NOMAD_ADDR is not set")
        self.token = os.environ.get("NOMAD_TOKEN", "")
        cacert = os.environ.get("NOMAD_CACERT", "")
        if self.addr.startswith("https"):
            self.ctx = ssl.create_default_context(cafile=cacert or None)
            if not cacert:
                self.ctx.check_hostname = False
                self.ctx.verify_mode = ssl.CERT_NONE
                print("warning: NOMAD_CACERT not set, TLS verification disabled", file=sys.stderr)
        else:
            self.ctx = None

    def request(self, method, path, body=None):
        req = urllib.request.Request(
            f"{self.addr}{path}",
            data=json.dumps(body).encode() if body is not None else None,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        if self.token:
            req.add_header("X-Nomad-Token", self.token)
        try:
            with urllib.request.urlopen(req, context=self.ctx, timeout=30) as resp:
                return json.loads(resp.read() or "null")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            raise ShipError(f"{method} {path} -> {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise ShipError(f"{method} {path} -> {exc.reason}") from exc


def deploy(args):
    validate_image(args.image)
    hcl = render_job(args)
    client = NomadClient()

    job = client.request("POST", "/v1/jobs/parse", {"JobHCL": hcl, "Canonicalize": True})
    job_id = job["ID"]

    plan = client.request("POST", f"/v1/job/{job_id}/plan", {"Job": job, "Diff": False})
    warnings = plan.get("Warnings", "")
    if warnings:
        print(f"plan warnings: {warnings}", file=sys.stderr)

    result = client.request("POST", "/v1/jobs", {"Job": job})
    eval_id = result.get("EvalID", "")
    print(f"registered job {job_id} (eval {eval_id})")

    deadline = time.time() + args.timeout
    while time.time() < deadline:
        deployment = client.request("GET", f"/v1/job/{job_id}/deployment")
        if deployment:
            status = deployment.get("Status")
            if status == "successful":
                print(f"deployment {deployment['ID']} successful")
                return
            if status in ("failed", "cancelled"):
                raise ShipError(
                    f"deployment {status}: {deployment.get('StatusDescription', '')}"
                )
        time.sleep(5)
    raise ShipError(f"deployment did not become healthy within {args.timeout}s")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build", help="build a container image")
    p_build.add_argument("context", help="build context directory")
    p_build.add_argument("--image", required=True)
    p_build.add_argument("--file", help="Dockerfile path if not <context>/Dockerfile")

    p_push = sub.add_parser("push", help="push the image to its registry")
    p_push.add_argument("--image", required=True)

    p_deploy = sub.add_parser("deploy", help="register the workload on Nomad and wait for health")
    p_deploy.add_argument("--image", required=True)
    p_deploy.add_argument("--name", help="job name (required unless --job)")
    p_deploy.add_argument("--job", help="custom jobspec (HCL); __IMAGE__ is substituted")
    p_deploy.add_argument("--port", type=int, default=8080)
    p_deploy.add_argument("--count", type=int, default=1)
    p_deploy.add_argument("--cpu", type=int, default=200)
    p_deploy.add_argument("--memory", type=int, default=256)
    p_deploy.add_argument("--datacenter", default="dc1")
    p_deploy.add_argument("--driver", default="podman", choices=["podman", "docker"])
    p_deploy.add_argument("--timeout", type=int, default=300)

    args = parser.parse_args(argv)
    if args.command == "deploy" and not args.job and not args.name:
        parser.error("deploy requires --name (or --job with a custom jobspec)")

    try:
        {"build": build, "push": push, "deploy": deploy}[args.command](args)
    except ShipError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
