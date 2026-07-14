"""
Shared Dockerfile selection for the GitHub and GitLab pipelines.

Selection modes:
  none                   nothing
  manifest               the entries listed in ci/build.yaml (the default)
  all                    every Dockerfile in the repo
  paths  <glob|dir ...>  Dockerfiles matching a glob, an exact path, or a directory
  changed <file ...>     Dockerfiles whose build context contains a changed file

Archived Dockerfiles (any path under an ``archive/`` directory) are never built.
"""
import fnmatch
import os

MANIFEST = os.path.join("ci", "build.yaml")

# Vendored / third-party / non-buildable trees that CI must never build.
EXCLUDE_DIR_NAMES = {".git", "archive", "deprecated", "node_modules", "helm"}


def _is_excluded(rel_path):
    parts = rel_path.split("/")
    if set(parts) & EXCLUDE_DIR_NAMES:
        return True
    return any(p.endswith("-main") or p.endswith("-master") for p in parts)


def load_manifest(root="."):
    """Entries under ``build:`` in ci/build.yaml. Uses PyYAML when available and
    falls back to a minimal list parser so the CI discovery image needs no deps."""
    path = os.path.join(root, MANIFEST)
    if not os.path.isfile(path):
        return []
    text = open(path).read()
    try:
        import yaml
        data = yaml.safe_load(text) or {}
        return [str(x).strip() for x in (data.get("build") or []) if str(x).strip()]
    except ImportError:
        items, in_build = [], False
        for line in text.splitlines():
            stripped = line.split("#", 1)[0].rstrip()
            if not stripped.strip():
                continue
            if stripped.strip() == "build:":
                in_build = True
                continue
            if in_build and stripped.lstrip().startswith("- "):
                items.append(stripped.lstrip()[2:].strip().strip("'\""))
            elif in_build and not stripped.startswith((" ", "\t")):
                in_build = False
        return items


def all_dockerfiles(root="."):
    found = []
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIR_NAMES]
        for fn in files:
            if fn == "Dockerfile" or fn.startswith("Dockerfile."):
                rel = os.path.relpath(os.path.join(dirpath, fn), root).replace(os.sep, "/")
                if not _is_excluded(rel):
                    found.append(rel)
    return sorted(found)


def select(mode, items, root="."):
    if mode == "none":
        return []
    if mode == "manifest":
        return select("paths", load_manifest(root), root)
    dockerfiles = all_dockerfiles(root)
    if mode == "all":
        return dockerfiles
    if mode == "paths":
        globs = [g.strip().rstrip("/") for g in items if g.strip()]
        chosen = []
        for d in dockerfiles:
            ctx = os.path.dirname(d)
            if any(d == g or fnmatch.fnmatch(d, g) or d.startswith(g + "/") or ctx == g for g in globs):
                chosen.append(d)
        return chosen
    # changed: rebuild a Dockerfile when anything in its context directory changed
    changed = set(items)
    chosen = []
    for d in dockerfiles:
        ctx = os.path.dirname(d)
        prefix = ctx + "/" if ctx else ""
        if any(c == d or (prefix and c.startswith(prefix)) for c in changed):
            chosen.append(d)
    return chosen


def image_name(dockerfile):
    d = os.path.dirname(dockerfile) or "."
    base = os.path.basename(dockerfile)
    suffix = base[len("Dockerfile"):].lstrip(".") if base.startswith("Dockerfile") else base
    name = (d if not suffix else f"{d}-{suffix}").strip("./").lower()
    return "".join(c if (c.isalnum() or c in "-_/.") else "-" for c in name)


def entries(dockerfiles):
    out = []
    for f in dockerfiles:
        name = image_name(f)
        out.append({
            "dockerfile": f,
            "context": os.path.dirname(f) or ".",
            "image": name,
            "safe": name.replace("/", "-"),
        })
    return out
