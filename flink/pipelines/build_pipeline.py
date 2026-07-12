#!/usr/bin/env python3
"""
Generate a Flink SQL streaming job from a declarative pipeline config.

source table -> windowed aggregation (+ optional anomaly flag) -> sink table.

The same generator handles whatever you configure: change the schema, source
connector (datagen/kafka/filesystem), window, aggregations, or sink and it emits
valid Flink SQL. Only the standard library + PyYAML are needed.

    python3 build_pipeline.py pipeline_config.yaml > pipeline.sql
"""

from __future__ import annotations

import sys

import yaml

# Aggregation function -> (SQL template, output SQL type). "{f}" is the field type.
AGG_FUNCS = {
    "avg": ("AVG({c})", "DOUBLE"),
    "min": ("MIN({c})", "{f}"),
    "max": ("MAX({c})", "{f}"),
    "sum": ("SUM({c})", "{f}"),
    "count": ("COUNT({c})", "BIGINT"),
    "stddev_pop": ("STDDEV_POP({c})", "DOUBLE"),
}

_UNITS = {
    "second": "SECOND", "seconds": "SECOND",
    "minute": "MINUTE", "minutes": "MINUTE",
    "hour": "HOUR", "hours": "HOUR", "day": "DAY", "days": "DAY",
}


def interval(spec: str) -> str:
    """'10 SECONDS' -> "INTERVAL '10' SECOND"."""
    n, unit = spec.split()
    return f"INTERVAL '{int(n)}' {_UNITS[unit.lower()]}"


def col_types(cfg: dict) -> dict[str, str]:
    return {c["name"]: c["type"] for c in cfg["schema"]["columns"]}


def source_ddl(cfg: dict) -> tuple[str, str]:
    """Return (CREATE TABLE source DDL, time descriptor column)."""
    schema = cfg["schema"]
    lines = [f"  `{c['name']}` {c['type']}" for c in schema["columns"]]

    if schema.get("time_attribute", "processing") == "event":
        tcol = schema["event_time_column"]
        delay = interval(schema.get("watermark_delay", "5 SECONDS"))
        lines.append(f"  WATERMARK FOR `{tcol}` AS `{tcol}` - {delay}")
    else:
        tcol = "proc_time"
        lines.append(f"  `{tcol}` AS PROCTIME()")

    src = cfg["source"]
    opts = {"connector": src["connector"], **src.get("options", {})}
    # datagen: expand per-column field generators.
    if src["connector"] == "datagen":
        for c in schema["columns"]:
            for k, v in (c.get("datagen") or {}).items():
                opts[f"fields.{c['name']}.{k}"] = v
    with_clause = ",\n".join(f"  '{k}' = '{v}'" for k, v in opts.items())

    ddl = (
        "CREATE TABLE source_stream (\n"
        + ",\n".join(lines)
        + "\n) WITH (\n"
        + with_clause
        + "\n);"
    )
    return ddl, tcol


def window_tvf(cfg: dict, tcol: str) -> str:
    w = cfg["window"]
    size = interval(w["size"])
    d = f"DESCRIPTOR(`{tcol}`)"
    if w["type"] == "tumble":
        return f"TABLE(TUMBLE(TABLE source_stream, {d}, {size}))"
    if w["type"] == "hop":
        return f"TABLE(HOP(TABLE source_stream, {d}, {interval(w['slide'])}, {size}))"
    if w["type"] == "cumulate":
        return f"TABLE(CUMULATE(TABLE source_stream, {d}, {interval(w['step'])}, {size}))"
    raise ValueError(f"unknown window type: {w['type']}")


def projection(cfg: dict) -> list[tuple[str, str, str]]:
    """Return the output columns as (select_expr, alias, sql_type)."""
    types = col_types(cfg)
    cols: list[tuple[str, str, str]] = [
        ("window_start", "window_start", "TIMESTAMP(3)"),
        ("window_end", "window_end", "TIMESTAMP(3)"),
    ]
    for k in cfg["key_by"]:
        cols.append((f"`{k}`", k, types[k]))

    for agg in cfg["aggregations"]:
        field = agg["field"]
        ftype = types[field]
        for fn in agg["funcs"]:
            tmpl, otype = AGG_FUNCS[fn]
            cols.append((tmpl.format(c=f"`{field}`"), f"{fn}_{field}", otype.format(f=ftype)))

    anomaly = cfg.get("anomaly")
    if anomaly:
        f = anomaly["field"]
        thr = float(anomaly["threshold"])
        expr = (
            f"CASE WHEN STDDEV_POP(`{f}`) = 0 THEN 0 "
            f"WHEN (MAX(`{f}`) - AVG(`{f}`)) > {thr} * STDDEV_POP(`{f}`) "
            f"THEN 1 ELSE 0 END"
        )
        cols.append((expr, f"{f}_anomaly", "INT"))
    return cols


def sink_ddl(cfg: dict, cols: list[tuple[str, str, str]]) -> str:
    defs = ",\n".join(f"  `{alias}` {sqltype}" for _, alias, sqltype in cols)
    sink = cfg["sink"]
    opts = {"connector": sink["connector"], **sink.get("options", {})}
    with_clause = ",\n".join(f"  '{k}' = '{v}'" for k, v in opts.items())
    return f"CREATE TABLE sink_stream (\n{defs}\n) WITH (\n{with_clause}\n);"


def insert_stmt(cfg: dict, cols: list[tuple[str, str, str]], tvf: str) -> str:
    select = ",\n  ".join(f"{expr} AS `{alias}`" for expr, alias, _ in cols)
    keys = ", ".join(["window_start", "window_end"] + [f"`{k}`" for k in cfg["key_by"]])
    return (
        "INSERT INTO sink_stream\n"
        f"SELECT\n  {select}\n"
        f"FROM {tvf}\n"
        f"GROUP BY {keys};"
    )


def build(cfg: dict) -> str:
    src, tcol = source_ddl(cfg)
    cols = projection(cfg)
    tvf = window_tvf(cfg, tcol)
    parts = [
        f"-- Generated from pipeline config: {cfg.get('name', 'pipeline')}",
        f"SET 'pipeline.name' = '{cfg.get('name', 'flink-pipeline')}';",
        "SET 'execution.runtime-mode' = 'streaming';",
        "",
        src,
        "",
        sink_ddl(cfg, cols),
        "",
        insert_stmt(cfg, cols, tvf),
        "",
    ]
    return "\n".join(parts)


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: build_pipeline.py <pipeline_config.yaml>")
    with open(sys.argv[1]) as f:
        cfg = yaml.safe_load(f)
    sys.stdout.write(build(cfg))


if __name__ == "__main__":
    main()
