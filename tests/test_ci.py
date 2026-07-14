"""Guards for the CI pipelines (.github/workflows + .gitlab). These catch the
classes of failure that only surface when the pipeline actually builds/scans an
image: unbuildable FROM args, archived Dockerfiles getting built, artifact names
that contain a '/', and the Dockerfile-selection logic (changed / paths / all).
"""

import importlib.util
import io
import os
import re
import sys
from contextlib import redirect_stdout

import yaml

from discovery import REPO_ROOT, find_dockerfiles, rel
from dockerfile_parser import join_continuations, FROM_RE, BUILTIN_ARGS

sys.path.insert(0, str(REPO_ROOT / "ci"))
import dockerfile_targets as dt  # noqa: E402

GH_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "docker-build.yml"
GH_DISCOVER = REPO_ROOT / ".github" / "discover.py"
GITLAB_CI = REPO_ROOT / ".gitlab-ci.yml"
GITLAB_GEN = REPO_ROOT / ".gitlab" / "generate-pipeline.py"

_BRACE_RE = re.compile(r"\$\{([^}]*)\}")
_BARE_RE = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")


def _from_vars_needing_default(image_ref):
    needs = set()
    for content in _BRACE_RE.findall(image_ref):
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)(.*)$", content)
        if m and m.group(2).strip() == "":
            needs.add(m.group(1))
    for name in _BARE_RE.findall(_BRACE_RE.sub("", image_ref)):
        needs.add(name)
    return needs


def _global_defaulted_args(text):
    defaulted = set()
    for line in join_continuations(text):
        code = line.split("#", 1)[0]
        if FROM_RE.match(code):
            break
        m = re.match(r"^\s*ARG\s+(.*)$", code, re.IGNORECASE)
        if m:
            for part in re.split(r"\s+(?=[A-Za-z_][A-Za-z0-9_]*=)", m.group(1)):
                if "=" in part:
                    defaulted.add(part.strip().split("=")[0].strip())
    return defaulted


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestDockerfilesBuildableInCI:
    def test_from_args_have_defaults(self):
        # both CIs run `docker build` with no --build-arg, so a FROM that
        # references an undefaulted ARG fails with InvalidDefaultArgInFrom.
        offenders = []
        for df in find_dockerfiles():
            text = df.read_text(errors="ignore")
            defaulted = _global_defaulted_args(text)
            for line in join_continuations(text):
                code = line.split("#", 1)[0]
                m = FROM_RE.match(code)
                if not m:
                    continue
                for var in _from_vars_needing_default(m.group(1)):
                    if var in BUILTIN_ARGS or var in defaulted:
                        continue
                    offenders.append(f"{rel(df)}: FROM references ${{{var}}} with no ARG default")
        assert not offenders, "docker build without --build-arg fails for:\n" + "\n".join(offenders)


class TestSelector:
    def _root(self):
        return str(REPO_ROOT)

    def test_all_excludes_archive(self):
        dfs = dt.select("all", [], root=self._root())
        assert dfs
        assert not any("/archive/" in d or d.startswith("archive/") for d in dfs)

    def test_changed_maps_to_context(self):
        # editing a file inside a Dockerfile's context rebuilds just that image
        changed = ["elastic/data-pipeline/logstash/pipeline/logstash.conf"]
        dfs = dt.select("changed", changed, root=self._root())
        assert dfs == ["elastic/data-pipeline/logstash/Dockerfile"]

    def test_changed_unrelated_builds_nothing(self):
        assert dt.select("changed", ["README.md"], root=self._root()) == []

    def test_paths_selects_subset(self):
        dfs = dt.select("paths", ["elastic/data-pipeline/fluentd"], root=self._root())
        assert set(dfs) == {
            "elastic/data-pipeline/fluentd/Dockerfile",
            "elastic/data-pipeline/fluentd/Dockerfile.quick",
        }

    def test_image_and_safe_names(self):
        [e] = dt.entries(["elastic/data-pipeline/fluentd/Dockerfile"])
        assert e["image"] == "elastic/data-pipeline/fluentd"
        assert "/" not in e["safe"]

    def test_none_builds_nothing(self):
        assert dt.select("none", [], root=self._root()) == []

    def test_manifest_default_is_present_and_parses(self):
        # the committed manifest must exist and parse (empty list is valid)
        manifest = dt.load_manifest(self._root())
        assert isinstance(manifest, list)
        # manifest mode selects exactly what the manifest lists
        assert dt.select("manifest", [], root=self._root()) == dt.select(
            "paths", manifest, root=self._root())

    def test_manifest_entries_resolve_to_dockerfiles(self):
        # every declared manifest entry must match at least one buildable Dockerfile
        manifest = dt.load_manifest(self._root())
        for entry in manifest:
            assert dt.select("paths", [entry], root=self._root()), \
                f"ci/build.yaml entry matches no Dockerfile: {entry}"

    def test_manifest_parses_entries_and_strips_comments(self, tmp_path):
        (tmp_path / "ci").mkdir()
        (tmp_path / "ci" / "build.yaml").write_text(
            "build:\n  - kafka\n  - elastic/apm-server  # a comment\n")
        assert dt.load_manifest(str(tmp_path)) == ["kafka", "elastic/apm-server"]

    def test_manifest_missing_file_is_empty(self, tmp_path):
        assert dt.load_manifest(str(tmp_path)) == []


class TestGitlabGenerator:
    def test_paths_mode_renders_slash_free_jobs(self):
        gen = _load("gitlab_gen", GITLAB_GEN)
        buf = io.StringIO()
        cwd = os.getcwd()
        os.chdir(REPO_ROOT)
        try:
            with redirect_stdout(buf):
                gen.main(["paths", "elastic/data-pipeline/fluentd"])
        finally:
            os.chdir(cwd)
        out = buf.getvalue()
        assert "build:elastic-data-pipeline-fluentd:" in out
        assert "sbom-elastic-data-pipeline-fluentd.cdx.json" in out
        assert "build:elastic/" not in out           # job names carry no '/'
        assert "apm-server" not in out               # only the selected subset

    def test_all_mode_excludes_archive(self):
        gen = _load("gitlab_gen", GITLAB_GEN)
        buf = io.StringIO()
        cwd = os.getcwd()
        os.chdir(REPO_ROOT)
        try:
            with redirect_stdout(buf):
                gen.main(["all"])
        finally:
            os.chdir(cwd)
        assert "archive" not in buf.getvalue()


class TestGithubWorkflow:
    def test_valid_yaml_and_selection(self):
        text = GH_WORKFLOW.read_text()
        doc = yaml.safe_load(text)
        assert "build-scan-publish" in doc["jobs"]
        # PyYAML parses the `on:` key as boolean True (YAML 1.1); assert on text
        assert "Build only these Dockerfiles" in text                # subset selection input
        assert "build_changed" in text                               # incremental opt-in input
        assert "MODE=manifest" in text                               # default reads ci/build.yaml
        assert ".github/discover.py" in text
        assert "sbom-${{ matrix.safe }}" in text                     # artifact name has no '/'
        assert "trivy-${{ matrix.safe }}" in text
        assert "hashFiles('trivy.sarif')" in text                    # guarded when build failed

    def test_discover_script_is_valid_python(self):
        import ast
        ast.parse(GH_DISCOVER.read_text())


class TestGitlabCiConfig:
    def test_valid_yaml_and_child_trigger(self):
        doc = yaml.safe_load(GITLAB_CI.read_text())
        assert "discover" in doc and "trigger-build" in doc
        assert doc["trigger-build"]["trigger"]["include"][0]["job"] == "discover"
