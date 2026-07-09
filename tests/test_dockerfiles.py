import json
import re

import pytest

from discovery import find_dockerfiles, rel
from dockerfile_parser import join_continuations, parse_dockerfile, unresolved_vars_in_from

DOCKERFILES = find_dockerfiles()

SHELL_METACHARACTERS = {"|", "&&", "||", ";", ">", "<", ">>"}


@pytest.mark.parametrize("path", DOCKERFILES, ids=rel)
def test_dockerfile_has_from(path):
    text = path.read_text(errors="ignore")
    parsed = parse_dockerfile(text)
    assert parsed["from_lines"], f"{rel(path)} has no FROM instruction"


@pytest.mark.parametrize("path", DOCKERFILES, ids=rel)
def test_dockerfile_from_vars_are_resolvable(path):
    text = path.read_text(errors="ignore")
    parsed = parse_dockerfile(text)
    problems = []
    for from_line in parsed["from_lines"]:
        if from_line in parsed["stage_names"]:
            continue
        unresolved = unresolved_vars_in_from(
            from_line, parsed["global_args"], parsed["stage_names"]
        )
        if unresolved:
            problems.append((from_line, unresolved))
    assert not problems, (
        f"{rel(path)}: FROM line(s) reference ARG(s) not declared before the first FROM "
        f"(these resolve to empty string, breaking the build): {problems}"
    )


@pytest.mark.parametrize("path", DOCKERFILES, ids=rel)
def test_dockerfile_no_embedded_space_exec_args(path):
    text = path.read_text(errors="ignore")

    entrypoint_cmd_re = re.compile(
        r"^\s*(ENTRYPOINT|CMD)\s*(\[.*\])\s*$", re.IGNORECASE | re.MULTILINE
    )
    shells = {"sh", "/bin/sh", "bash", "/bin/bash", "/usr/bin/env"}
    problems = []
    for match in entrypoint_cmd_re.finditer(text):
        instr, array_literal = match.groups()
        try:
            normalized = array_literal.replace("'", '"')
            items = json.loads(normalized)
        except Exception:
            continue
        has_shell_c = any(
            item in shells for item in items if isinstance(item, str)
        ) and "-c" in items
        if has_shell_c:
            continue
        for item in items:
            if isinstance(item, str) and " " in item.strip() and "/" in item:
                problems.append((instr, item))
    assert not problems, (
        f"{rel(path)}: exec-form {problems[0][0]} contains an array element with embedded "
        f"spaces ({problems}) — exec-form never invokes a shell, so this string is passed "
        f"as a single argv[0] and will fail with 'no such file or directory'"
    )


@pytest.mark.parametrize("path", DOCKERFILES, ids=rel)
def test_dockerfile_healthcheck_exec_form_has_no_shell_metacharacters(path):
    text = path.read_text(errors="ignore")
    logical_lines = join_continuations(text)

    healthcheck_re = re.compile(r"^\s*HEALTHCHECK\b.*?\bCMD\s+(\[.*\])\s*$", re.IGNORECASE)
    problems = []
    for line in logical_lines:
        match = healthcheck_re.match(line)
        if not match:
            continue
        (array_literal,) = match.groups()
        try:
            items = json.loads(array_literal.replace("'", '"'))
        except Exception:
            continue
        if any(item in SHELL_METACHARACTERS for item in items if isinstance(item, str)):
            problems.append(items)
    assert not problems, (
        f"{rel(path)}: HEALTHCHECK uses exec-form CMD with shell metacharacters as separate "
        f"array elements ({problems}) — exec-form never invokes a shell, so '|'/'&&'/etc. are "
        f"passed as literal argv instead of being interpreted; wrap the check in "
        f"CMD-SHELL or invoke sh -c explicitly"
    )
