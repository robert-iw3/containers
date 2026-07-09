import json
import uuid
import os
import requests
from datetime import datetime, timezone
from .config import MITRE_ATTACK_JSON, EMBEDDINGS_FILE
from .deepseek_client import DeepSeekClient

class TTPMapper:
    def __init__(self):
        self.techniques = []
        self.deepseek = DeepSeekClient()

        if os.path.exists(EMBEDDINGS_FILE):
            self.load_mappings()
        else:
            self.load_mitre_data()
            self.save_mappings()

    def load_mitre_data(self):
        """
        Load enterprise ATT&CK techniques from MITRE JSON file.
        Skips deprecated or revoked techniques.
        If file not found, download it from official MITRE repo.
        """
        if not os.path.exists(MITRE_ATTACK_JSON):
            print("[*] MITRE data not found, downloading from MITRE GitHub...")
            url = "https://raw.githubusercontent.com/mitre-attack/attack-stix-data/refs/heads/master/enterprise-attack/enterprise-attack.json"
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                os.makedirs(os.path.dirname(MITRE_ATTACK_JSON), exist_ok=True)
                with open(MITRE_ATTACK_JSON, "w", encoding="utf-8") as f:
                    f.write(response.text)
                print("[+] Download complete.")
            else:
                raise Exception(f"[!] Failed to download MITRE data: HTTP {response.status_code}")

        with open(MITRE_ATTACK_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)

        revoked_count = 0
        deprecated_count = 0
        valid_count = 0

        for item in data.get("objects", []):
            if item.get("type") != "attack-pattern":
                continue

            if item.get("revoked", True):
                revoked_count += 1
                continue

            if item.get("x_mitre_deprecated", True):
                deprecated_count += 1
                continue

            valid_count += 1
            self.techniques.append({
                "id": item.get("external_references", [{}])[0].get("external_id", ""),
                "name": item.get("name", ""),
                "description": item.get("description", ""),
                "tactic": [phase["phase_name"] for phase in item.get("kill_chain_phases", [])],
                "url": item.get("external_references", [{}])[0].get("url", ""),
                "matrix": "Enterprise"
            })

        print(f"[+] Loaded {valid_count} valid techniques (skipped {revoked_count} revoked, {deprecated_count} deprecated)")


    def save_mappings(self, path: str = EMBEDDINGS_FILE):
        """
        Save loaded ATT&CK techniques to disk for reuse, then remove MITRE JSON file.
        """
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"techniques": self.techniques}, f, ensure_ascii=False, indent=2)

        # Clean up: delete the original MITRE JSON to save space
        if os.path.exists(MITRE_ATTACK_JSON):
            os.remove(MITRE_ATTACK_JSON)
            print(f"[*] Deleted temporary file: {MITRE_ATTACK_JSON}")

    def load_mappings(self, path: str = EMBEDDINGS_FILE):
        """
        Load pre-saved ATT&CK techniques from file.
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"[!] Mapping file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.techniques = data["techniques"]

    def extract_mappings(self, api_response: dict) -> dict:
        """
        Parse DeepSeek JSON response into structured dict.
        """
        try:
            content = api_response["choices"][0]["message"]["content"]
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            data = json.loads(content)
            return {
                "techniques": data.get("techniques", []),
                "iocs": data.get("iocs", {}),
                "threat_actor": data.get("threat_actor", [])
            }
        except Exception as e:
            print(f"[!] Failed to parse DeepSeek JSON: {e}")
            return {"techniques": [], "iocs": {}, "threat_actor": []}

    def refang_ioc(self, ioc: str) -> str:
        return (
            ioc.replace("hxxps", "https")
               .replace("hxxp", "http")
               .replace("[[:]]", ":")
               .replace("[:]", ":")
               .replace("[[.]]", ".")
               .replace("[.]", ".")
        )

    def map_threat_report(self, report_text: str, verbose: bool = False) -> dict:
        api_data = self.extract_mappings(self.deepseek.query(report_text, verbose=verbose))
        mapped = []

        for mapping in api_data["techniques"]:
            technique_id = mapping.get("technique_id") or mapping.get("id")
            if not technique_id:
                continue

            technique = next((t for t in self.techniques if t["id"] == technique_id), None)
            if technique:
                mapped.append({
                    "technique_id": technique["id"],
                    "technique_name": technique["name"],
                    "tactics": technique["tactic"],
                    "procedure_description": mapping.get("procedure_description", "No detailed procedure provided."),
                    "url": technique["url"]
                })

        iocs = api_data.get("iocs", {})
        refanged_iocs = {
            "ips": [self.refang_ioc(i) for i in iocs.get("ips", [])],
            "domains": [self.refang_ioc(d) for d in iocs.get("domains", [])],
            "urls": [self.refang_ioc(u) for u in iocs.get("urls", [])],
            "hashes": iocs.get("hashes", [])  # hashes don't need refanging
        }

        return {
            "techniques": mapped,
            "iocs": refanged_iocs,
            "threat_actor": api_data.get("threat_actor", [])
        }

    def summarize_report(self, full_text: str, verbose: bool = False) -> str:
        """
        Call DeepSeek to summarize the report.
        """
        return self.deepseek.summarize(full_text, verbose=verbose)


    def generate_stix_bundle(self, parsed_data: dict) -> dict:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        bundle_id = f"bundle--{uuid.uuid4()}"
        objects = []
        id_map = {}

        # Threat Actors
        threat_actor_ids = []
        for actor in parsed_data.get("threat_actor", []):
            ta_id = f"threat-actor--{uuid.uuid4()}"
            threat_actor_ids.append(ta_id)
            id_map[actor] = ta_id
            objects.append({
                "type": "threat-actor",
                "id": ta_id,
                "created": now,
                "modified": now,
                "name": actor,
                "labels": ["threat-actor"]
            })

        # ATT&CK Techniques
        technique_ids = []
        for tech in parsed_data.get("techniques", []):
            tid = tech["technique_id"]
            ap_id = f"attack-pattern--{uuid.uuid4()}"
            technique_ids.append(ap_id)
            id_map[tid] = ap_id
            objects.append({
                "type": "attack-pattern",
                "id": ap_id,
                "created": now,
                "modified": now,
                "name": tech["technique_name"],
                "description": tech.get("procedure_description", ""),
                "external_references": [{
                    "source_name": "mitre-attack",
                    "external_id": tid,
                    "url": tech.get("url", "")
                }],
                "kill_chain_phases": [
                    {"kill_chain_name": "mitre-attack", "phase_name": tactic}
                    for tactic in tech.get("tactics", [])
                ]
            })

        # Indicators
        indicator_ids = []

        def create_indicator(indicator_type, value, pattern):
            ind_id = f"indicator--{uuid.uuid4()}"
            objects.append({
                "type": "indicator",
                "id": ind_id,
                "created": now,
                "modified": now,
                "name": f"{indicator_type}: {value}",
                "description": f"Observed {indicator_type} in threat activity",
                "pattern_type": "stix",
                "pattern": pattern,
                "valid_from": now,
                "labels": ["malicious-activity"]
            })
            return ind_id

        for ip in parsed_data.get("iocs", {}).get("ips", []):
            pattern = f"[ipv4-addr:value = '{ip}']"
            indicator_ids.append(create_indicator("IP", ip, pattern))

        for domain in parsed_data.get("iocs", {}).get("domains", []):
            pattern = f"[domain-name:value = '{domain}']"
            indicator_ids.append(create_indicator("Domain", domain, pattern))

        for url in parsed_data.get("iocs", {}).get("urls", []):
            pattern = f"[url:value = '{url}']"
            indicator_ids.append(create_indicator("URL", url, pattern))

        for hash_val in parsed_data.get("iocs", {}).get("hashes", []):
            if len(hash_val) == 32:
                pattern = f"[file:hashes.MD5 = '{hash_val}']"
            elif len(hash_val) == 40:
                pattern = f"[file:hashes.SHA1 = '{hash_val}']"
            elif len(hash_val) == 64:
                pattern = f"[file:hashes.SHA256 = '{hash_val}']"
            else:
                continue
            indicator_ids.append(create_indicator("File-Hash", hash_val, pattern))

        # Relationships
        for ta_id in threat_actor_ids:
            for ap_id in technique_ids:
                objects.append({
                    "type": "relationship",
                    "id": f"relationship--{uuid.uuid4()}",
                    "relationship_type": "uses",
                    "source_ref": ta_id,
                    "target_ref": ap_id,
                    "created": now,
                    "modified": now
                })
            for ind_id in indicator_ids:
                objects.append({
                    "type": "relationship",
                    "id": f"relationship--{uuid.uuid4()}",
                    "relationship_type": "indicates",
                    "source_ref": ind_id,
                    "target_ref": ta_id,
                    "created": now,
                    "modified": now
                })

        # Report object (only this has created_by_ref)
        summary_full = parsed_data.get("summary", "Automatically generated summary of the threat report.")
        report_title = self.deepseek.generate_title(summary_full) if summary_full else summary_full[:80]

        report_id = f"report--{uuid.uuid4()}"

        objects.append({
            "type": "report",
            "id": report_id,
            "created": now,
            "modified": now,
            "published": now,
            "name": report_title,
            "description": summary_full,
            "labels": ["threat-report"],
            "object_refs": [obj["id"] for obj in objects if obj["type"] not in ("report", "identity")],
        })

        return {
            "type": "bundle",
            "id": bundle_id,
            "spec_version": "2.1",
            "objects": objects
        }
