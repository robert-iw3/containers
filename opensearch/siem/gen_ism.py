#!/usr/bin/env python3
"""
Generate OpenSearch ISM policies and data-stream index templates for the SIEM
datasets in datasets.yml. Each dataset routes to a labeled data stream
logs-<dataset>-<namespace> with a hot -> warm -> delete lifecycle.
"""
import json
import os
import sys

try:
    import yaml
except ImportError:
    yaml = None

HERE = os.path.dirname(os.path.abspath(__file__))


def ism_policy(ds):
    name = ds["name"]
    retention = f"{ds['retention_days']}d"
    warm_after = f"{ds.get('warm_after_days', 7)}d"
    return {
        "policy": {
            "description": f"SIEM lifecycle for {name}",
            "default_state": "hot",
            "states": [
                {
                    "name": "hot",
                    "actions": [{"rollover": {"min_index_age": "1d", "min_primary_shard_size": "50gb"}}],
                    "transitions": [{"state_name": "warm", "conditions": {"min_index_age": warm_after}}],
                },
                {
                    "name": "warm",
                    "actions": [
                        {"replica_count": {"number_of_replicas": 1}},
                        {"force_merge": {"max_num_segments": 1}},
                    ],
                    "transitions": [{"state_name": "delete", "conditions": {"min_index_age": retention}}],
                },
                {"name": "delete", "actions": [{"delete": {}}]},
            ],
            "ism_template": [{"index_patterns": [f"logs-{name}-*"], "priority": 100}],
        }
    }


def index_template(ds, namespace):
    name = ds["name"]
    return {
        "index_patterns": [f"logs-{name}-*"],
        "data_stream": {},
        "priority": 200,
        "template": {
            "settings": {
                "index.number_of_shards": 1,
                "index.number_of_replicas": 1,
                "index.codec": "best_compression",
                "plugins.index_state_management.rollover_alias": f"logs-{name}-{namespace}",
            },
            "mappings": {
                "properties": {
                    "@timestamp": {"type": "date"},
                    "data_stream.dataset": {"type": "keyword"},
                    "data_stream.namespace": {"type": "keyword"},
                }
            },
        },
    }


def load_datasets():
    if not yaml:
        raise SystemExit("PyYAML required")
    cfg = yaml.safe_load(open(os.path.join(HERE, "datasets.yml")).read())
    return cfg.get("namespace", "default"), cfg["datasets"]


def main():
    namespace, datasets = load_datasets()
    out = {"policies": {}, "templates": {}}
    for ds in datasets:
        out["policies"][ds["name"]] = ism_policy(ds)
        out["templates"][ds["name"]] = index_template(ds, namespace)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
