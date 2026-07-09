import pytest
import yaml

from discovery import REPO_ROOT, find_compose_files, rel

COMPOSE_FILES = find_compose_files()


def _load(path):
    return yaml.safe_load(path.read_text(errors="ignore"))


def _project_root(path):
    rel_parts = path.relative_to(REPO_ROOT).parts
    return REPO_ROOT / rel_parts[0]


_project_keys_cache = {}


def _sibling_top_level_keys(path, key):
    project_dir = _project_root(path)
    cache_key = (project_dir, key)
    if cache_key in _project_keys_cache:
        names = _project_keys_cache[cache_key]
    else:
        names = set()
        for pattern in ("*.yml", "*.yaml"):
            for candidate in project_dir.rglob(pattern):
                if "compose" not in candidate.name.lower() and "podman" not in candidate.name.lower():
                    continue
                try:
                    doc = yaml.safe_load(candidate.read_text(errors="ignore"))
                except yaml.YAMLError:
                    continue
                if isinstance(doc, dict) and isinstance(doc.get(key), dict):
                    names.update(doc[key].keys())
        _project_keys_cache[cache_key] = names
    return names - {None}


@pytest.mark.parametrize("path", COMPOSE_FILES, ids=rel)
def test_compose_is_valid_yaml(path):
    doc = _load(path)
    assert isinstance(doc, dict), f"{rel(path)} did not parse to a mapping"
    assert "services" in doc, f"{rel(path)} has no top-level 'services' key"


@pytest.mark.parametrize("path", COMPOSE_FILES, ids=rel)
def test_compose_depends_on_resolves(path):
    doc = _load(path)
    services = doc.get("services") or {}
    if not isinstance(services, dict):
        pytest.skip("services is not a mapping (uses extension/anchor merge not resolved by safe_load)")
    service_names = set(services.keys())
    problems = []
    sibling_names = None
    for name, svc in services.items():
        if not isinstance(svc, dict):
            continue
        depends_on = svc.get("depends_on")
        if not depends_on:
            continue
        deps = depends_on if isinstance(depends_on, list) else depends_on.keys()
        for dep in deps:
            if dep in service_names:
                continue
            if sibling_names is None:
                sibling_names = _sibling_top_level_keys(path, "services")
            if dep in sibling_names:
                continue
            problems.append((name, dep))
    assert not problems, f"{rel(path)}: depends_on references undefined services: {problems}"


@pytest.mark.parametrize("path", COMPOSE_FILES, ids=rel)
def test_compose_named_volumes_resolve(path):
    doc = _load(path)
    services = doc.get("services") or {}
    if not isinstance(services, dict):
        pytest.skip("services is not a mapping")
    top_level_volumes = set((doc.get("volumes") or {}).keys())
    problems = []
    sibling_volumes = None
    for name, svc in services.items():
        if not isinstance(svc, dict):
            continue
        for vol in svc.get("volumes") or []:
            if not isinstance(vol, str):
                continue
            source = vol.split(":", 1)[0]
            if source.startswith((".", "/", "~", "$")):
                continue
            if source in top_level_volumes:
                continue
            if sibling_volumes is None:
                sibling_volumes = _sibling_top_level_keys(path, "volumes")
            if source in sibling_volumes:
                continue
            problems.append((name, source))
    assert not problems, (
        f"{rel(path)}: services reference named volumes not declared in the top-level "
        f"'volumes:' block: {problems}"
    )


@pytest.mark.parametrize("path", COMPOSE_FILES, ids=rel)
def test_compose_networks_resolve(path):
    doc = _load(path)
    services = doc.get("services") or {}
    if not isinstance(services, dict):
        pytest.skip("services is not a mapping")
    top_level_networks = set((doc.get("networks") or {}).keys())
    problems = []
    sibling_networks = None
    for name, svc in services.items():
        if not isinstance(svc, dict):
            continue
        nets = svc.get("networks")
        if not nets:
            continue
        if isinstance(nets, str):
            problems.append((name, f"networks value must be a list or mapping, not a bare string: {nets!r}"))
            continue
        net_names = nets if isinstance(nets, list) else nets.keys()
        for net in net_names:
            if net in top_level_networks:
                continue
            if sibling_networks is None:
                sibling_networks = _sibling_top_level_keys(path, "networks")
            if net in sibling_networks:
                continue
            problems.append((name, net))
    assert not problems, f"{rel(path)}: services reference undeclared networks: {problems}"


@pytest.mark.parametrize("path", COMPOSE_FILES, ids=rel)
def test_compose_no_unrendered_template_syntax(path):
    lines = path.read_text(errors="ignore").splitlines()
    code_lines = [line for line in lines if not line.strip().startswith("#")]
    text = "\n".join(code_lines)
    assert "{{" not in text or "helm" in str(path).lower(), (
        f"{rel(path)} contains unrendered template syntax ('{{{{ ... }}}}') in a plain "
        f"compose file — this is never substituted by docker compose and will be passed "
        f"through literally"
    )


SHELL_METACHARACTERS = {"|", "&&", "||", ";", ">", "<", ">>"}


@pytest.mark.parametrize("path", COMPOSE_FILES, ids=rel)
def test_compose_healthcheck_exec_form_has_no_shell_metacharacters(path):
    doc = _load(path)
    services = doc.get("services") or {}
    if not isinstance(services, dict):
        pytest.skip("services is not a mapping")
    problems = []
    for name, svc in services.items():
        if not isinstance(svc, dict):
            continue
        healthcheck = svc.get("healthcheck")
        if not isinstance(healthcheck, dict):
            continue
        test = healthcheck.get("test")
        if not isinstance(test, list) or not test:
            continue
        if test[0] not in ("CMD", "CMD-SHELL"):
            continue
        if test[0] == "CMD" and any(item in SHELL_METACHARACTERS for item in test[1:]):
            problems.append((name, test))
    assert not problems, (
        f"{rel(path)}: healthcheck uses exec-form CMD with shell metacharacters as separate "
        f"array elements ({problems}) — exec-form never invokes a shell, so '|'/'&&'/etc. are "
        f"passed as literal argv to the first command instead of being interpreted; use "
        f"CMD-SHELL for pipelines"
    )
