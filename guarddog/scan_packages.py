#!/usr/bin/env python3
import argparse
import subprocess
import os
import yaml
import logging
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    parser = argparse.ArgumentParser(description="GuardDog parallel scanner (pypi/npm/go)")
    parser.add_argument("--runtime", choices=["docker", "podman"], default="podman")
    parser.add_argument("--config", default="packages.yaml")
    parser.add_argument("--results-dir", default="./guarddog-results")
    parser.add_argument("--max-parallel", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()

    runtime = args.runtime
    results_dir = os.path.abspath(args.results_dir)
    os.makedirs(results_dir, exist_ok=True)

    with open(args.config) as f:
        config = yaml.safe_load(f)

    packages = config.get("packages", [])
    if not packages:
        logging.error("No packages found")
        return

    pkgs = []
    for p in packages:
        pkgs.append({
            "name": p["name"],
            "ecosystem": p.get("ecosystem", "pypi").lower(),
            "result_name": p.get("result_name", p["name"].replace("/", "_").replace(":", "_"))
        })

    # Build image
    logging.info("Building guarddog image...")
    subprocess.run(f"{runtime} build -t guarddog .", shell=True, check=True)

    # Start container
    subprocess.run(
        f"{runtime} run --rm -d --name guarddog "
        f"--user $(id -u):$(id -g) "
        f"-v {results_dir}:/guarddog-results:Z guarddog tail -f /dev/null",
        shell=True, check=True
    )

    def scan(pkg):
        output_file = os.path.join(results_dir, f"{pkg['result_name']}.json")
        cmd = [
            runtime, "exec", "guarddog", "timeout", str(args.timeout),
            "guarddog", pkg["ecosystem"], "scan", pkg["name"],
            "--output-format=json"
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=args.timeout + 60)
            with open(output_file, "w") as f:
                f.write(result.stdout)
            logging.info(f"Success: {pkg['ecosystem']} {pkg['name']}")
        except Exception as e:
            logging.error(f"Failed: {pkg['ecosystem']} {pkg['name']} → {e}")
            with open(output_file, "w") as f:
                f.write(json.dumps({"error": str(e), "package": pkg["name"]}))

    try:
        with ThreadPoolExecutor(max_workers=args.max_parallel) as exec:
            futures = [exec.submit(scan, pkg) for pkg in pkgs]
            for f in as_completed(futures):
                f.result()
    finally:
        subprocess.run(f"{runtime} stop guarddog", shell=True)

    logging.info(f"All done. Results in {results_dir}")

if __name__ == "__main__":
    main()