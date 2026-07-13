#!/usr/bin/env python3
"""Generate ILM policies + data-stream index templates from datasets.yml.

Each SIEM dataset becomes:
  * an ILM policy: hot (rollover on size/age) -> warm (shrink/forcemerge/fewer
    replicas) -> delete (at retention), and
  * a data-stream index template matching `logs-<dataset>-*` that binds the policy,
    so parsing streams land in the LABELED index `logs-<dataset>-<namespace>`.

    python3 gen_siem.py [datasets.yml]     # writes generated/{ilm,templates}/*.json

Only PyYAML + the stdlib are needed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml


def ilm_policy(ds: dict) -> dict:
    return {
        "policy": {
            "phases": {
                "hot": {
                    "min_age": "0ms",
                    "actions": {
                        "rollover": {
                            "max_primary_shard_size": f"{ds.get('hot_rollover_gb', 50)}gb",
                            "max_age": f"{ds.get('hot_rollover_days', 7)}d",
                        },
                        "set_priority": {"priority": 100},
                    },
                },
                "warm": {
                    "min_age": f"{ds.get('warm_after_days', 7)}d",
                    "actions": {
                        "forcemerge": {"max_num_segments": 1},
                        "shrink": {"number_of_shards": 1},
                        "allocate": {"number_of_replicas": 1},
                        "set_priority": {"priority": 50},
                    },
                },
                "delete": {
                    "min_age": f"{ds['retention_days']}d",
                    "actions": {"delete": {}},
                },
            }
        }
    }


def index_template(ds: dict, namespace: str, policy_name: str) -> dict:
    name = ds["name"]
    return {
        "index_patterns": [f"logs-{name}-*"],
        "data_stream": {},
        "priority": 200,
        "template": {
            "settings": {
                "index.lifecycle.name": policy_name,
                "index.number_of_shards": 1,
                "index.number_of_replicas": 1,
                # storage-vs-CPU: best_compression trades a little CPU for ~2x less disk.
                "index.codec": "best_compression",
                "index.refresh_interval": "5s",
            },
            "mappings": {
                "properties": {
                    "@timestamp": {"type": "date"},
                    "data_stream.dataset": {"type": "constant_keyword", "value": name},
                    "data_stream.namespace": {"type": "constant_keyword", "value": namespace},
                    "event.dataset": {"type": "keyword"},
                    "host.name": {"type": "keyword"},
                    "source.ip": {"type": "ip"},
                    "destination.ip": {"type": "ip"},
                    "user.name": {"type": "keyword"},
                    "message": {"type": "match_only_text"},
                }
            },
        },
        "_meta": {"managed_by": "arcanaeum-siem", "dataset": name},
    }


def main() -> None:
    cfg_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("datasets.yml")
    cfg = yaml.safe_load(cfg_path.read_text())
    ns = cfg.get("namespace", "default")
    out = cfg_path.parent / "generated"
    (out / "ilm").mkdir(parents=True, exist_ok=True)
    (out / "templates").mkdir(parents=True, exist_ok=True)

    for ds in cfg["datasets"]:
        pol = f"{ds['name']}-ilm"
        (out / "ilm" / f"{pol}.json").write_text(json.dumps(ilm_policy(ds), indent=2))
        (out / "templates" / f"{ds['name']}.json").write_text(
            json.dumps(index_template(ds, ns, pol), indent=2)
        )
    print(f"generated {len(cfg['datasets'])} ILM policies + templates in {out}/")


if __name__ == "__main__":
    main()
