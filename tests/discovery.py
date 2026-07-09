import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

EXCLUDE_DIR_NAMES = {
    "helm", "archive", "deprecated", "node_modules", ".git",
    "python-fake-data-producer-for-apache-kafka-main",
    "streaming-pipeline-tutorial",
}


_helm_chart_dir_cache = {}


def _is_helm_chart_member(path: Path) -> bool:
    for ancestor in path.parents:
        if ancestor in _helm_chart_dir_cache:
            is_chart = _helm_chart_dir_cache[ancestor]
        else:
            abs_ancestor = REPO_ROOT / ancestor
            is_chart = (abs_ancestor / "Chart.yaml").is_file()
            _helm_chart_dir_cache[ancestor] = is_chart
        if is_chart:
            return True
        if ancestor == Path("."):
            break
    return False


def _is_excluded(path: Path) -> bool:
    parts = set(path.parts)
    if parts & EXCLUDE_DIR_NAMES:
        return True
    for part in path.parts:
        if part.endswith("-main") or part.endswith("-master"):
            return True
    if _is_helm_chart_member(path):
        return True
    return False


def find_files(patterns):
    results = []
    for pattern in patterns:
        for path in REPO_ROOT.rglob(pattern):
            if path.is_file() and not _is_excluded(path.relative_to(REPO_ROOT)):
                results.append(path)
    return sorted(set(results))


def find_dockerfiles():
    return find_files(["Dockerfile", "Dockerfile.*"])


def find_compose_files():
    import yaml

    candidates = find_files(["docker-compose*.yml", "docker-compose*.yaml", "podman*.yml", "podman*.yaml"])
    candidates = [f for f in candidates if "compose" in f.name.lower() or "podman" in f.name.lower()]
    compose_files = []
    for f in candidates:
        try:
            doc = yaml.safe_load(f.read_text(errors="ignore"))
        except yaml.YAMLError:
            compose_files.append(f)
            continue
        if isinstance(doc, dict) and "services" in doc:
            compose_files.append(f)
    return compose_files


def find_k8s_files():
    candidates = find_files(["*.yml", "*.yaml"])
    k8s_files = []
    api_version_re = re.compile(r"^apiVersion:\s*\S+", re.MULTILINE)
    kind_re = re.compile(r"^kind:\s*\S+", re.MULTILINE)
    for f in candidates:
        name_lower = f.name.lower()
        if "compose" in name_lower or "podman" in name_lower:
            continue
        try:
            text = f.read_text(errors="ignore")
        except OSError:
            continue
        if api_version_re.search(text) and kind_re.search(text):
            k8s_files.append(f)
    return sorted(set(k8s_files))


def rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))
