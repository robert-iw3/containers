#!/usr/bin/env python3
"""
generate_packages_yaml.py

Recursively scans a project for import statements in Python, JavaScript/TypeScript, and Go files.
Extracts third-party packages and generates a packages.yaml file compatible with the GuardDog suite.

- Ignores stdlib (Python), built-in/node: (Node.js), and standard library (Go)
- Handles scoped npm packages (@org/pkg)
- Works in monorepos, skips common ignore dirs
- Deduplicates across ecosystems
- Ready for orchestrate_guarddog.py / deploy_guarddog.py / CI/CD

Usage:
    python generate_packages_yaml.py                # scans current dir → packages.yaml
    python generate_packages_yaml.py --dir ./myapp --output custom.yaml
"""

import ast
import os
import re
import sys
import yaml
from pathlib import Path
from argparse import ArgumentParser

def is_stdlib_module(module_name: str) -> bool:
    """Check if a Python module is part of the standard library."""
    return module_name in sys.stdlib_module_names

def get_python_imports(file_path: Path) -> set[str]:
    """Extract third-party imports from a Python file using AST."""
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
        return {m for m in modules if not is_stdlib_module(m)}
    except Exception:
        return set()

def extract_npm_package(raw: str) -> str:
    """Extract the package name from a require/import (handles scoped @org/pkg)."""
    if raw.startswith('@'):
        parts = raw.split('/')
        return '/'.join(parts[:2]) if len(parts) >= 2 else raw
    return raw.split('/')[0]

def get_js_imports(file_path: Path) -> set[str]:
    """Extract third-party npm packages from JS/TS files (static require/import only)."""
    try:
        content = file_path.read_text(encoding='utf-8')
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
    """Extract third-party Go imports (line-by-line parser)."""
    try:
        lines = file_path.read_text(encoding='utf-8').splitlines()
        modules = set()
        in_multi_import = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('import ('):
                in_multi_import = True
                continue
            if in_multi_import and stripped == ')':
                in_multi_import = False
                continue
            if stripped.startswith('import "'):
                pkg = stripped.split('"')[1]
                if '/' in pkg:
                    modules.add(pkg)
            elif in_multi_import and stripped.startswith('"') and stripped.endswith('"'):
                pkg = stripped.strip('"')
                if '/' in pkg:
                    modules.add(pkg)
            elif stripped.startswith('"') and stripped.endswith('"'):
                pkg = stripped.strip('"')
                if '/' in pkg:
                    modules.add(pkg)
        return modules
    except Exception:
        return set()

def main():
    parser = ArgumentParser(description="Generate packages.yaml from source code imports")
    parser.add_argument('--dir', default='.', help="Directory to scan (default: current)")
    parser.add_argument('--output', default='packages.yaml', help="Output YAML file (default: packages.yaml)")
    args = parser.parse_args()

    root = Path(args.dir).resolve()
    if not root.is_dir():
        print(f"Error: {root} is not a directory")
        sys.exit(1)

    ignore_dirs = {
        'node_modules', '.git', '__pycache__', '.venv', 'venv', 'env',
        'dist', 'build', '.tox', '.next', '.nuxt'
    }

    packages = []
    seen = set()  # (ecosystem, name)

    for path in root.rglob('*'):
        if not path.is_file():
            continue
        if any(ig in path.parts for ig in ignore_dirs):
            continue

        ecosystem = None
        imports = set()

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
                    result_name = name.split('/')[-1]
                    if ecosystem == 'npm' and name.startswith('@'):
                        # For scoped packages, use the short name without @
                        result_name = result_name.split('@')[0] if '@' in result_name else result_name
                    packages.append({
                        'name': name,
                        'result_name': result_name,
                        'ecosystem': ecosystem
                    })

    if not packages:
        print("No third-party packages found in the project.")
        return

    data = {'packages': sorted(packages, key=lambda x: (x['ecosystem'], x['name']))}
    yaml_content = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)

    Path(args.output).write_text(yaml_content)
    print(f"Generated {args.output} with {len(packages)} unique third-party packages:")
    print(yaml_content)

if __name__ == "__main__":
    main()