import re

ARG_NAME_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=")
FROM_RE = re.compile(r"^\s*FROM\s+(.+?)(?:\s+AS\s+(\S+))?\s*$", re.IGNORECASE)
VAR_REF_RE = re.compile(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?")

BUILTIN_ARGS = {
    "BUILDPLATFORM", "BUILDOS", "BUILDARCH", "BUILDVARIANT",
    "TARGETPLATFORM", "TARGETOS", "TARGETARCH", "TARGETVARIANT",
}


def join_continuations(text: str):
    lines = text.splitlines()
    joined = []
    buf = ""
    for line in lines:
        stripped = line.rstrip("\n")
        if stripped.rstrip().endswith("\\") and not stripped.strip().startswith("#"):
            buf += stripped.rstrip()[:-1] + " "
        else:
            buf += stripped
            joined.append(buf)
            buf = ""
    if buf:
        joined.append(buf)
    return joined


def parse_dockerfile(text: str):
    logical_lines = join_continuations(text)

    instructions = []
    for line in logical_lines:
        code = line.split("#", 1)[0] if not line.strip().startswith("#") else ""
        if not code.strip():
            continue
        instructions.append(code)

    global_args = set()
    stage_names = set()
    from_lines = []
    seen_first_from = False

    for instr in instructions:
        m = FROM_RE.match(instr)
        if m:
            seen_first_from = True
            image_ref = m.group(1).strip()
            stage_name = m.group(2)
            from_lines.append(image_ref)
            if stage_name:
                stage_names.add(stage_name)
            continue

        if not seen_first_from:
            arg_match = re.match(r"^\s*ARG\s+(.*)$", instr, re.IGNORECASE)
            if arg_match:
                for part in re.split(r"\s+(?=[A-Za-z_][A-Za-z0-9_]*=)", arg_match.group(1)):
                    name_match = ARG_NAME_RE.match(part.strip())
                    if name_match:
                        global_args.add(name_match.group(1))
                    else:
                        bare = part.strip().split("=")[0].strip()
                        if bare:
                            global_args.add(bare)

    return {
        "global_args": global_args,
        "stage_names": stage_names,
        "from_lines": from_lines,
    }


def unresolved_vars_in_from(image_ref: str, global_args: set, stage_names: set):
    unresolved = []
    for var in VAR_REF_RE.findall(image_ref):
        if var in global_args or var in BUILTIN_ARGS:
            continue
        unresolved.append(var)
    return unresolved
