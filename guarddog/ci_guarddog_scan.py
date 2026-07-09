#!/usr/bin/env python3

import os
import subprocess
import sys
from pathlib import Path

def main():
    runtime = os.getenv("CONTAINER_RUNTIME", "podman")  # podman default
    image = os.getenv("GUARDDOG_IMAGE", "ghcr.io/datadog/guarddog:latest")
    output_format = "sarif"  # forced for CI – best integration
    results_dir = Path("./guarddog-results")
    results_dir.mkdir(exist_ok=True)

    uid = os.getuid()
    gid = os.getgid()

    print("GuardDog CI/CD Scanner — Official Image Edition")
    print(f"Runtime: {runtime}")
    print(f"Image: {image}")
    print(f"UID:GID override: {uid}:{gid}")

    # Pull official image (fast, always up-to-date)
    print("Pulling official GuardDog image...")
    subprocess.run(f"{runtime} pull {image}", shell=True, check=True)

    manifest_map = {
        "requirements.txt": "pypi",
        "poetry.lock": "pypi",
        "Pipfile.lock": "pypi",
        "package-lock.json": "npm",
        "yarn.lock": "npm",
        "pnpm-lock.yaml": "npm",
        "go.mod": "go",
    }

    manifests = []
    for pattern, eco in manifest_map.items():
        for path in Path(".").rglob(pattern):
            if path.is_file():
                manifests.append({"path": path, "ecosystem": eco, "relpath": path.as_posix()})

    if not manifests:
        print("No supported manifest files found. Skipping GuardDog scan.")
        sys.exit(0)

    print(f"Found {len(manifests)} manifest(s):")
    for m in manifests:
        print(f"  • {m['ecosystem']:>4} → {m['relpath']}")

    container_name = "guarddog-ci-official"
    subprocess.run(
        f"{runtime} run --rm -d --name {container_name} "
        f"--user {uid}:{gid} "
        f"-v {os.getcwd()}:/repo:Z "
        f"{image} tail -f /dev/null",
        shell=True, check=True
    )

    has_findings = False

    try:
        for m in manifests:
            repo_path = f"/repo/{m['relpath']}"
            output_file = results_dir / f"{m['path'].stem}-{m['ecosystem']}.{output_format}"

            print(f"Scanning {m['ecosystem']} ← {m['relpath']}...")
            cmd = f"{runtime} exec {container_name} guarddog {m['ecosystem']} verify {repo_path} --output-format={output_format}"

            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

            with open(output_file, "w") as f:
                f.write(result.stdout or result.stderr)

            if result.returncode != 0:
                has_findings = True
                print(f"⚠️  MALICIOUS/SUSPICIOUS packages detected in {m['relpath']} → Blocking build")

        if has_findings:
            print("\nBuild failed: Malicious dependencies found")
            sys.exit(1)
        else:
            print("\nAll dependencies clean → Build approved")
    finally:
        subprocess.run(f"{runtime} stop {container_name}", shell=True)

if __name__ == "__main__":
    main()