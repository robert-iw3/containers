import pytest
import yaml

from discovery import find_k8s_files, rel

K8S_FILES = find_k8s_files()

WORKLOAD_KINDS = {"Deployment", "StatefulSet", "DaemonSet", "ReplicaSet", "Job"}


def _try_load_docs(path):
    try:
        return [d for d in yaml.safe_load_all(path.read_text(errors="ignore")) if d], None
    except yaml.YAMLError as exc:
        return None, exc


VAULT_AGENT_TEMPLATE_FILES = {
    "bitbucket/bitbucket-deployment.yml",
}


@pytest.mark.parametrize("path", K8S_FILES, ids=rel)
def test_k8s_no_unrendered_template_syntax(path):
    if rel(path) in VAULT_AGENT_TEMPLATE_FILES:
        pytest.skip("contains Vault Agent template syntax rendered by the vault-agent sidecar at runtime, not kubectl")
    lines = path.read_text(errors="ignore").splitlines()
    code_lines = [line for line in lines if not line.strip().startswith("#")]
    text = "\n".join(code_lines)
    assert "{{" not in text, (
        f"{rel(path)} contains unrendered template syntax ('{{{{ ... }}}}') in a plain "
        f"k8s manifest — kubectl apply does not process this, it will be stored as a "
        f"literal string"
    )


@pytest.mark.parametrize("path", K8S_FILES, ids=rel)
def test_k8s_yaml_parses(path):
    docs, err = _try_load_docs(path)
    if err is not None:
        pytest.fail(f"{rel(path)} failed to parse as YAML: {err}")
    assert docs, f"{rel(path)} produced no YAML documents"
    for doc in docs:
        assert "apiVersion" in doc, f"{rel(path)}: document missing apiVersion"
        assert "kind" in doc, f"{rel(path)}: document missing kind"


@pytest.mark.parametrize("path", K8S_FILES, ids=rel)
def test_k8s_selector_matches_template_labels(path):
    docs, err = _try_load_docs(path)
    if err is not None:
        pytest.skip("YAML parse error already reported by test_k8s_yaml_parses")
    problems = []
    for doc in docs:
        if doc.get("kind") not in WORKLOAD_KINDS:
            continue
        spec = doc.get("spec") or {}
        selector = spec.get("selector") or {}
        match_labels = selector.get("matchLabels")
        if match_labels is None:
            continue
        template_labels = ((spec.get("template") or {}).get("metadata") or {}).get("labels") or {}
        missing = {
            k: v for k, v in match_labels.items() if template_labels.get(k) != v
        }
        if missing:
            name = (doc.get("metadata") or {}).get("name", "<unnamed>")
            problems.append((doc["kind"], name, missing))
    assert not problems, (
        f"{rel(path)}: selector.matchLabels not satisfied by template labels "
        f"(Kubernetes will reject these at apply time): {problems}"
    )


@pytest.mark.parametrize("path", K8S_FILES, ids=rel)
def test_k8s_service_selector_is_mapping(path):
    docs, err = _try_load_docs(path)
    if err is not None:
        pytest.skip("YAML parse error already reported by test_k8s_yaml_parses")
    problems = []
    for doc in docs:
        if doc.get("kind") != "Service":
            continue
        spec = doc.get("spec") or {}
        selector = spec.get("selector")
        if selector is None:
            continue
        if not isinstance(selector, dict):
            name = (doc.get("metadata") or {}).get("name", "<unnamed>")
            problems.append((name, selector))
            continue
        non_label_keys = {k for k in selector if k in ("clusterIP", "type", "ports")}
        if non_label_keys:
            name = (doc.get("metadata") or {}).get("name", "<unnamed>")
            problems.append((name, non_label_keys))
    assert not problems, (
        f"{rel(path)}: Service spec.selector contains non-label keys that belong at the "
        f"top level of spec, not nested inside selector (this makes the selector never "
        f"match any pod): {problems}"
    )
