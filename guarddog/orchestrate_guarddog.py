#!/usr/bin/env python3
import os
import yaml
import subprocess
import sys
import json
import ast
import re
from pathlib import Path

EXAMPLE_YAML = """packages:
  - name: requests
    result_name: requests
  - name: express
    result_name: express
    ecosystem: npm
  - name: github.com/gin-gonic/gin
    result_name: gin
    ecosystem: go
"""

# ====================== IMPORT PARSERS (integrated from generate_packages_yaml.py) ======================

def is_stdlib_module(module_name: str) -> bool:
    return module_name in sys.stdlib_module_names

def get_python_imports(file_path: Path) -> set[str]:
    try:
        tree = ast.parse(file_path.read_bytes())
        modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    modules.add(alias.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    modules.add(node.module.split('.')[0])
        return {m for m in modules if not is_stdlib_module(m) and m}
    except Exception:
        return set()

def extract_npm_package(raw: str) -> str:
    if raw.startswith('@'):
        parts = raw.split('/')
        return '/'.join(parts[:2]) if len(parts) >= 2 else raw
    # @org/pkg
    return raw.split('/')[0]  # normal pkg

def get_js_imports(file_path: Path) -> set[str]:
    try:
        content = file_path.read_text(encoding='utf-8', errors='ignore')
        modules = set()
        patterns = [
            r"require\(['\"]([^'\"]+)['\"]\)",
            r"from ['\"]([^'\"]+)['\"]",
            r"^import ['\"]([^'\"]+)['\"]"
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, content, re.MULTILINE):
                raw = match.group(1)
                if not (raw.startswith('.') or raw.startswith('/') or raw.startswith('node:')):
                    modules.add(extract_npm_package(raw))
        return modules
    except Exception:
        return set()

def get_go_imports(file_path: Path) -> set[str]:
    try:
        lines = file_path.read_text(encoding='utf-8', errors='ignore').splitlines()
        modules = set()
        in_multi = False
        for line in lines:
            s = line.strip()
            if s.startswith('import ('):
                in_multi = True
                continue
            if in_multi and s == ')':
                in_multi = False
                continue
            if s.startswith('import "') or (in_multi and s.startswith('"') and s.endswith('"')):
                pkg = s.split('"')[1] if '"' in s else None
                if pkg and '/' in pkg and not pkg.startswith('.'):
                    modules.add(pkg)
        return modules
    except Exception:
        return set()

def generate_packages_from_source(root_dir: Path) -> list[dict]:
    ignore_dirs = {
        'node_modules', '.git', '__pycache__', '.venv', 'venv', 'env',
        'dist', 'build', '.tox', '.next', '.nuxt', '.idea', '.vscode'
    }

    packages = []
    seen = set()

    for path in root_dir.rglob('*'):
        if not path.is_file():
            continue
        if any(ig in path.parts for ig in ignore_dirs):
            continue

        imports = set()
        ecosystem = None

        if path.suffix == '.py':
            ecosystem = 'pypi'
            imports = get_python_imports(path)
        elif path.suffix in {'.js', '.ts', '.jsx', '.tsx', '.mjs', '.cjs'}:
            ecosystem = 'npm'
            imports = get_js_imports(path)
        elif path.suffix == '.go':
            ecosystem = 'go'
            imports = get_go_imports(path)

        if ecosystem and imports:
            for name in imports:
                key = (ecosystem, name)
                if key not in seen:
                    seen.add(key)
                    result_name = name.split('/')[-1].split('@')[0]  # clean name for filename
                    packages.append({
                        'name': name,
                        'result_name': result_name,
                        'ecosystem': ecosystem
                    })

    return sorted(packages, key=lambda x: (x['ecosystem'], x['name']))

# ====================== VALIDATION / FIX ======================

def validate_and_fix_config(path: str):
    while True:
        try:
            with open(path, 'r') as f:
                data = yaml.safe_load(f) or {}

            if 'packages' not in data and data['packages']:
                raise ValueError("Missing or empty 'packages' list")

            fixed = False
            for pkg in data['packages']:
                if not pkg.get('name'):
                    raise ValueError("Package missing 'name'")
                if 'ecosystem' not in pkg:
                    pkg['ecosystem'] = 'pypi'
                    fixed = True
                pkg['ecosystem'] = pkg['ecosystem'].lower()
                if pkg['ecosystem'] not in ['pypi', 'npm', 'go', 'github_action', 'extension']:
                    raise ValueError(f"Invalid ecosystem: {pkg['ecosystem']}")
                if not pkg.get('result_name'):
                    pkg['result_name'] = pkg['name'].replace('/', '_').replace(':', '_').replace('.', '_')
                    fixed = True

            if fixed:
                print("Auto-fixed missing ecosystem/result_name fields.")
                if input("Save fixed packages.yaml? (y/n): ").lower() == 'y':
                    with open(path, 'w') as f:
                        yaml.safe_dump(data, f)
                    print("Saved.")
                else:
                    print("Cannot proceed without saving fixes.")
                    sys.exit(1)

            print(f"Validation successful: {len(data['packages'])} packages ready.")
            return path

        except Exception as e:
            print(f"Error in {path}: {e}")
            sys.exit(1)  # Critical error in existing file

# ====================== MAIN ORCHESTRATOR ======================

def main():
    print("\nGuardDog Automated Orchestrator (Podman default) — November 16, 2025\n")

    deployment = input("Deployment method [podman/docker/kubernetes/ansible]: ").strip().lower() or "podman"
    while deployment not in ['docker', 'podman', 'kubernetes', 'ansible']:
        deployment = input("Invalid. Choose docker/podman/kubernetes/ansible: ").strip().lower()

    config_file = input("Path to packages.yaml [./packages.yaml]: ").strip() or "./packages.yaml"

    if os.path.exists(config_file):
        print(f"Found {config_file}")
    else:
        print(f"\nNo {config_file} found.")
        generate = input("Scan source code in current directory and auto-generate packages.yaml from imports? (highly recommended) (y/n): ").strip().lower()
        if generate == 'y':
            print("Scanning for Python, JavaScript/TypeScript, and Go files...")
            packages = generate_packages_from_source(Path('.'))
            if not packages:
                print("No third-party packages detected in source code.")
            else:
                data = {'packages': packages}
                with open(config_file, 'w') as f:
                    yaml.safe_dump(data, f, sort_keys=False)
                print(f"Successfully generated {config_file} with {len(packages)} packages!")
                print("Preview:")
                print(yaml.safe_dump(data, sort_keys=False))
        else:
            create_example = input("Create minimal example packages.yaml instead? (y/n): ").strip().lower()
            if create_example == 'y':
                with open(config_file, 'w') as f:
                    f.write(EXAMPLE_YAML)
                print(f"Created example {config_file}")
            else:
                print("Exiting. Please provide a valid packages.yaml")
                sys.exit(1)

    # Now validate (will auto-fix if needed)
    config_file = validate_and_fix_config(config_file)

    results_dir = input("Results directory [./guarddog-results]: ").strip() or "./guarddog-results"

    container_runtime = input("Container runtime for build (docker/podman) [podman]: ").strip().lower() or "podman"

    max_parallel = 4
    timeout = 300
    if deployment in ['docker', 'podman']:
        try:
            max_parallel = int(input(f"Max parallel scans [4]: ") or "4")
            timeout = int(input(f"Timeout per scan (seconds) [300]: ") or "300")
        except ValueError:
            print("Invalid number, using defaults")

    namespace = "default"
    if deployment == "kubernetes":
        namespace = input("Kubernetes namespace [default]: ").strip() or "default"

    inventory = "inventory.yml"
    if deployment == "ansible":
        inventory = input("Ansible inventory file [inventory.yml]: ").strip() or "inventory.yml"

    # Build image
    print(f"\nBuilding guarddog:latest with {container_runtime}...")
    subprocess.run(f"{container_runtime} build -t guarddog:latest .", shell=True, check=True)

    # Run deploy_guarddog.py
    cmd = [
        sys.executable, "deploy_guarddog.py",
        "--runtime", deployment,
        "--config", config_file,
        "--results-dir", results_dir,
        "--container-runtime", container_runtime,
    ]

    if deployment in ['docker', 'podman']:
        cmd += ["--max-parallel", str(max_parallel), "--timeout", str(timeout)]

    if deployment == "kubernetes":
        cmd += ["--namespace", namespace]

    if deployment == "ansible":
        cmd = ["ansible-playbook", "-i", inventory, "deploy_guarddog.yml",
               "--extra-vars", f"container_runtime={container_runtime}"]

    print(f"\nLaunching: {' '.join(cmd) if isinstance(cmd, list) else cmd}\n")
    subprocess.run(cmd, check=True)

    print(f"\nFinished! Results → {os.path.abspath(results_dir)}")

if __name__ == "__main__":
    main()