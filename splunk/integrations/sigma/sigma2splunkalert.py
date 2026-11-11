#!/usr/bin/env python3

# Sigma to Splunk Alert Converter
# original author: (@bareiss_patrick)
#
# Conversion runs on pySigma. The retired sigmac binary is no longer
# available from any package index, so it cannot be used offline.
# Local directories are the default rule source; network sources require
# --allow-network, because the target environment has no internet access.

import sys
import argparse
import hashlib
import os
import re
import yaml
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from urllib.parse import urlparse

from jinja2 import Environment, FileSystemLoader

from sigma.collection import SigmaCollection
from sigma.backends.splunk import SplunkBackend
from sigma.processing.pipeline import ProcessingPipeline
from sigma.pipelines.splunk import (
    splunk_cim_data_model,
    splunk_windows_pipeline,
    splunk_windows_sysmon_acceleration_keywords,
)

HERE = Path(__file__).resolve().parent

logger = logging.getLogger("sigma2splunkalert")

# Sigma severity words mapped onto the Splunk alert.severity scale.
SEVERITY_MAP = {"informational": 1, "low": 2, "medium": 3, "high": 4, "critical": 5}

BUILTIN_PIPELINES = {
    "none": None,
    "cim": splunk_cim_data_model,
    "windows": splunk_windows_pipeline,
    "sysmon_acceleration": splunk_windows_sysmon_acceleration_keywords,
}


def configure_logging(logfile: Optional[str]) -> None:
    handlers: List[logging.Handler] = [logging.StreamHandler()]
    if logfile:
        handlers.append(logging.FileHandler(logfile))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=handlers,
    )


# How far a rule can be trusted on a single match, scored from what the rule
# itself declares. Criticality alone is a blunt instrument: a critical rule
# whose author has written down that it fires on legitimate work should not
# page anyone on one event, and a specific rule for a named tool should.
#
# Every signal below is read from the rule, not guessed at:
#
#   falsepositives   the strongest signal there is. The author is stating
#                    that legitimate activity matches this. 652 of SigmaHQ's
#                    1377 core rules declare at least one.
#   a NOT filter     the author found those false positives and excluded
#                    them, which earns some of the confidence back.
#   status           stable has survived review; test has not.
#   constraint count more fields ANDed together is a narrower claim.
#   match breadth    "contains" on a short string matches a great deal;
#                    endswith on a full path matches one thing.
CONFIDENCE_HIGH = 60
CONFIDENCE_MEDIUM = 35


def score_confidence(rule: Dict) -> Tuple[int, List[str]]:
    """Return a 0-100 confidence score and the reasons for it."""
    score = 50
    why = []

    status = str(rule.get("status", "")).lower()
    if status == "stable":
        score += 15; why.append("status stable (+15)")
    elif status in ("deprecated", "unsupported"):
        score -= 25; why.append(f"status {status} (-25)")
    elif status:
        score -= 5; why.append(f"status {status} (-5)")

    fps = rule.get("falsepositives")
    if isinstance(fps, list):
        real = [f for f in fps
                if str(f).strip().lower() not in ("unknown", "none", "")]
        if real:
            penalty = min(24, 8 * len(real))
            score -= penalty
            why.append(f"author declares {len(real)} known false positive(s) (-{penalty})")

    det = rule.get("detection", {}) or {}
    condition = str(det.get("condition", "")).lower()
    if " not " in condition:
        score += 10; why.append("condition excludes known false positives (+10)")

    # Count the field constraints the rule actually requires, and judge how
    # broad each match is.
    constraints = 0
    broad = 0
    narrow = 0

    def walk(node):
        nonlocal constraints, broad, narrow
        if isinstance(node, dict):
            for key, val in node.items():
                if key == "condition":
                    continue
                if "|" in key or not isinstance(val, (dict, list)):
                    constraints += 1
                    mods = key.split("|")[1:]
                    values = val if isinstance(val, list) else [val]
                    for v in values:
                        text = str(v)
                        if "contains" in mods and len(text) < 6:
                            broad += 1
                        elif ("endswith" in mods or not mods) and len(text) >= 12:
                            narrow += 1
                walk(val)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(det)
    if constraints >= 3:
        bump = min(20, 5 * constraints)
        score += bump; why.append(f"{constraints} field constraints (+{bump})")
    elif constraints == 1:
        score -= 10; why.append("a single field constraint (-10)")
    if broad:
        pen = min(15, 5 * broad)
        score -= pen; why.append(f"{broad} very broad substring match(es) (-{pen})")
    if narrow:
        score += min(10, 3 * narrow); why.append(f"{narrow} specific value match(es)")

    return max(0, min(100, score)), why


def _flat(value) -> str:
    """One line, safe for a conf value. A newline inside a conf value ends
    it, and the remainder is parsed as a malformed key."""
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        parts = [str(v) for v in value if str(v).strip()]
        text = " | ".join(parts)
    else:
        text = str(value)
    return " ".join(text.split())


class SigmaRuleValidator:
    @staticmethod
    def validate_rule(rule_data: Dict) -> bool:
        """Validate Sigma rule structure."""
        required_fields = ["title", "detection"]
        return isinstance(rule_data, dict) and all(f in rule_data for f in required_fields)


class UseCase:
    def __init__(self, sigma_rule: Dict, config: Dict, splunk_search: str,
                 datamodel: Optional[str] = None):
        self.sigma_rule = sigma_rule
        self.config = config
        # pySigma emits multi-line SPL for rules that need rex or regex
        # stages. A conf value must be one line, so fold the newlines:
        # SPL is whitespace-insensitive between pipeline stages.
        self.splunk_search = re.sub(r"\s*\n\s*", " ", splunk_search).strip()
        self.title = sigma_rule.get("title", "Untitled")
        self.rule_id = sigma_rule.get("id", "")
        self.description = " ".join(str(sigma_rule.get("description", "")).split())
        self.tags = sigma_rule.get("tags", []) or []
        self.level = sigma_rule.get("level", "medium")
        self.fields = sigma_rule.get("fields", []) or []
        self.datamodel = datamodel
        self.mitre_techniques = [t for t in self.tags if t.startswith("attack.t")]
        self.mitre_tactics = [
            t for t in self.tags if t.startswith("attack.") and not t.startswith("attack.t")
        ]
        self.severity = SEVERITY_MAP.get(str(self.level).lower(), 3)
        self._stagger_slots = 0
        # Everything else the rule declares about itself. A detection is far
        # easier to act on when the author's own references and stated false
        # positives travel with it, instead of living in a file nobody opens.
        ls = sigma_rule.get("logsource", {}) or {}
        self.product = ls.get("product") or "unspecified"
        self.category = ls.get("category") or ""
        self.service = ls.get("service") or ""
        self.platform = {"windows": "Windows", "linux": "Linux",
                         "macos": "macOS"}.get(self.product, self.product.title())
        self.log_source = " / ".join(x for x in (self.category, self.service) if x) or "any"
        self.author = _flat(sigma_rule.get("author"))
        self.status = str(sigma_rule.get("status", "") or "")
        self.rule_date = str(sigma_rule.get("date", "") or "")
        self.modified = str(sigma_rule.get("modified", "") or "")
        refs = sigma_rule.get("references") or []
        self.references = _flat(refs if isinstance(refs, list) else [refs])
        fps = sigma_rule.get("falsepositives") or []
        self.falsepositives = _flat(fps if isinstance(fps, list) else [fps])
        self.confidence_score, self.confidence_why = score_confidence(sigma_rule)
        self.confidence = ("high" if self.confidence_score >= CONFIDENCE_HIGH
                           else "medium" if self.confidence_score >= CONFIDENCE_MEDIUM
                           else "low")

    @property
    def confidence_comment(self):
        """The scoring, as conf comment lines, so a stanza carries its own
        justification and can be audited without re-running the converter."""
        head = (f"# confidence {self.confidence} "
                f"({self.confidence_score}/100) -> {self.disposition}")
        return "\n".join([head] + [f"#   {r}" for r in self.confidence_why])

    @property
    def disposition(self):
        """Alert now, or aggregate and watch the trend.

        Immediate is reserved for a severe rule that is also specific. A
        severe rule the author has flagged as noisy is exactly the one that
        should not wake anyone on a single event; it still records a
        detection, and the trend is what makes it meaningful.
        """
        severe = str(self.level).lower() in ("critical", "high")
        return "immediate" if (severe and self.confidence == "high") else "trend"

    @property
    def cron_schedule(self):
        """The rule's own slot in the schedule.

        Derived from the rule id so it is stable across regenerations: a
        rule keeps its slot, and re-converting does not reshuffle the whole
        deployment into a different pattern.
        """
        base = (self.config.get("cron_schedule") or "*/10 * * * *").strip()
        slots = int(self._stagger_slots or 0)
        if slots < 2:
            return base
        key = self.rule_id or self.title
        offset = int(hashlib.sha1(str(key).encode()).hexdigest(), 16) % slots
        parts = base.split()
        if len(parts) != 5 or not parts[0].startswith("*/"):
            return base
        try:
            step = int(parts[0][2:])
        except ValueError:
            return base
        # Keep the interval, move the phase: */10 becomes 3,13,23,33,43,53.
        minutes = sorted(set((offset + m) % 60 for m in range(0, 60, step)))
        return ",".join(str(m) for m in minutes) + " " + " ".join(parts[1:])

    @property
    def stanza(self) -> str:
        """Stanza name. The Sigma id is the stable key, so it carries the
        uniqueness; the title is kept for readability only."""
        title = re.sub(r"[\[\]\r\n]", " ", self.title).strip()
        title = re.sub(r"\s+", " ", title)
        suffix = f" [{self.rule_id[:8]}]" if self.rule_id else ""
        return f"Sigma - {title}{suffix}".replace("[", "(").replace("]", ")")


class DetectionRuleConverter:
    @staticmethod
    def build_backend(pipeline_spec: Optional[str]) -> SplunkBackend:
        """Resolve a pipeline name or YAML path into a configured backend."""
        if not pipeline_spec or pipeline_spec == "none":
            return SplunkBackend()
        if pipeline_spec in BUILTIN_PIPELINES:
            return SplunkBackend(processing_pipeline=BUILTIN_PIPELINES[pipeline_spec]())
        path = Path(pipeline_spec)
        if not path.is_absolute():
            candidate = HERE / pipeline_spec
            if candidate.exists():
                path = candidate
        if not path.exists():
            raise FileNotFoundError(
                f"pipeline '{pipeline_spec}' is neither a built-in "
                f"({', '.join(BUILTIN_PIPELINES)}) nor an existing file"
            )
        return SplunkBackend(
            processing_pipeline=ProcessingPipeline.from_yaml(path.read_text(encoding="utf-8"))
        )

    @staticmethod
    def convertSigmaRule(rule_file: str, pipeline_spec: Optional[str],
                         output_format: str = "default") -> Tuple[str, str]:
        """Convert one Sigma rule to SPL. Returns (search, error)."""
        try:
            collection = SigmaCollection.load_ruleset([rule_file])
            backend = DetectionRuleConverter.build_backend(pipeline_spec)
            queries = backend.convert(collection, output_format=output_format)
            if not queries:
                return "", "backend produced no query"
            return str(queries[0]).strip(), ""
        except Exception as e:
            return "", f"{type(e).__name__}: {e}"

    @staticmethod
    def performSearchTransformation(transformations: List[Dict], search: str,
                                    sigma_rule: Dict) -> str:
        """Apply the enabled search transformations to the Splunk search."""
        for transform in transformations or []:
            if not transform.get("enabled", True):
                continue
            kind = transform.get("type")
            if kind == "whitelist":
                lookup = transform.get("lookup")
                if lookup:
                    search += f" | search NOT [| inputlookup {lookup}]"
            elif kind == "custom_command":
                command = transform.get("command")
                if command:
                    search += f" | {command}"
            elif kind == "cim_tags":
                tags = ",".join(sigma_rule.get("tags", []) or [])
                search += f' | eval mitre_tags="{tags}"'
        return search

    @staticmethod
    def addToSummaryIndex(search: str, config: Dict, sigma_rule: Dict) -> str:
        """Append a summary-index collect when summary indexing is enabled."""
        summary = config.get("summary_index", {}) or {}
        if not summary.get("enabled", False):
            return search
        index = summary.get("index", "threat-hunting")
        tags = ",".join(f"sigma_tag={t}" for t in sigma_rule.get("tags", []) or [])
        marker = f"{tags},level={sigma_rule.get('level', 'medium')}"
        return search + f' | collect index={index} marker="{marker}"'

    @staticmethod
    def mapToCIMDatamodel(sigma_rule: Dict, sigma_config: Dict) -> Optional[str]:
        """Map a Sigma rule to a CIM data model.

        Matches on the rule's log source, not on its tags: Sigma tags are
        ATT&CK identifiers such as attack.t1059, so a tag intersection never
        fires for real rules.
        """
        datamodels = sigma_config.get("datamodels", {}) or {}
        logsource = sigma_rule.get("logsource", {}) or {}
        product = logsource.get("product")
        service = logsource.get("service")
        category = logsource.get("category")
        # Matched on product-service / product-category only. A bare
        # product fallback matches several data models at once, so it
        # would pick whichever is first in the file.
        candidates = {
            f"{product}-{service}" if service else None,
            f"{product}-{category}" if category else None,
        }
        candidates.discard(None)
        for dm_name, dm_config in datamodels.items():
            sources = set(dm_config.get("logsources", []) or [])
            if sources & candidates:
                return dm_name
        return None


def openSigma2SplunkConfiguration(config_path: str) -> Dict:
    """Load Sigma2SplunkAlert configuration."""
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.error(f"Failed to load configuration {config_path}: {e}")
        return {}


def openSigmaConfiguration(sigma_config_path: str) -> Dict:
    """Load the Sigma log source / data model reference."""
    try:
        with open(sigma_config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.error(f"Failed to load Sigma configuration {sigma_config_path}: {e}")
        return {}


def loadSigmaRules(input_path: str) -> List[str]:
    """Recursively load Sigma rule files from a directory or file."""
    sigma_files: List[str] = []
    path = Path(input_path)
    if path.is_file() and path.suffix in (".yml", ".yaml"):
        sigma_files.append(str(path))
    elif path.is_dir():
        for pattern in ("*.yml", "*.yaml"):
            sigma_files.extend(str(p) for p in path.rglob(pattern))
    else:
        logger.warning(f"Source is neither a file nor a directory: {input_path}")
    return sorted(sigma_files)


def fetchRemoteSigmaRules(url: str, temp_dir: str) -> str:
    """Fetch Sigma rules from a Git repository or a single URL.

    Imports are local because the offline path must work without GitPython
    or requests installed.
    """
    parsed_url = urlparse(url)
    if parsed_url.scheme in ("http", "https") and url.endswith(".git"):
        try:
            import git
        except ImportError:
            logger.error("GitPython is not installed; cannot clone %s", url)
            return ""
        try:
            logger.info(f"Cloning repository {url} to {temp_dir}")
            git.Repo.clone_from(url, temp_dir, depth=1)
            # Rules live wherever the repository puts them, so hand back the
            # clone root and let loadSigmaRules walk it.
            return temp_dir
        except Exception as e:
            logger.error(f"Failed to clone repository {url}: {e}")
            return ""
    elif parsed_url.scheme in ("http", "https"):
        try:
            import requests
        except ImportError:
            logger.error("requests is not installed; cannot download %s", url)
            return ""
        try:
            logger.info(f"Downloading Sigma rule from {url}")
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            temp_file = os.path.join(temp_dir, os.path.basename(parsed_url.path) or "rule.yml")
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(response.text)
            return temp_file
        except Exception as e:
            logger.error(f"Failed to download {url}: {e}")
            return ""
    return ""


def generate_savedsearches_conf(detection_rules: List[UseCase], config: Dict) -> str:
    """Render savedsearches.conf from the template beside this script."""
    env = Environment(
        loader=FileSystemLoader(str(HERE)),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    template = env.get_template("savedsearches.conf.j2")
    return template.render(detection_rules=detection_rules, config=config)


def process_rule(file: str, pipeline_spec: Optional[str], config: Dict,
                 sigma_config: Dict, output_format: str) -> Tuple[Optional[UseCase], str]:
    """Process a single Sigma rule. Returns (use_case, error)."""
    try:
        with open(file, "r", encoding="utf-8") as f:
            sigma_rule = yaml.safe_load(f)
    except Exception as e:
        return None, f"unreadable: {type(e).__name__}: {e}"
    if not SigmaRuleValidator.validate_rule(sigma_rule):
        return None, "invalid Sigma rule format"
    splunk_search, err = DetectionRuleConverter.convertSigmaRule(
        file, pipeline_spec, output_format
    )
    if err:
        return None, err
    splunk_search = DetectionRuleConverter.performSearchTransformation(
        config.get("search_transformations", []), splunk_search, sigma_rule
    )
    splunk_search = DetectionRuleConverter.addToSummaryIndex(
        splunk_search, config, sigma_rule
    )
    datamodel = DetectionRuleConverter.mapToCIMDatamodel(sigma_rule, sigma_config)
    uc = UseCase(sigma_rule, config, splunk_search, datamodel)
    uc._stagger_slots = int(config.get("cron_stagger_slots", 0) or 0)
    return uc, ""


def main(argv):
    parser = argparse.ArgumentParser(
        description="Convert Sigma rules to a Splunk savedsearches.conf."
    )
    parser.add_argument("sources", nargs="+",
                        help="Folders, files, or URLs containing Sigma rules")
    parser.add_argument("--config", "-c", default=str(HERE / "config.yaml"),
                        help="Sigma2SplunkAlert configuration file")
    parser.add_argument("--sigma-config", "-sc", default=str(HERE / "splunk-all.yml"),
                        help="Log source / data model reference file")
    parser.add_argument("--pipeline", "-p", default="none",
                        help="pySigma pipeline: a built-in name "
                             f"({', '.join(BUILTIN_PIPELINES)}) or a YAML file path")
    parser.add_argument("--output-format", default="default",
                        choices=("default", "data_model", "savedsearches"),
                        help="pySigma Splunk backend output format")
    parser.add_argument("--output", "-o", default="savedsearches.conf",
                        help="Output file for savedsearches.conf")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview output without writing to file")
    parser.add_argument("--allow-network", action="store_true",
                        help="Permit http(s) sources. Off by default: the target "
                             "environment has no internet access.")
    parser.add_argument("--logfile", default=None,
                        help="Write a log file in addition to stderr")
    parser.add_argument("--workers", type=int, default=4, help="Conversion workers")
    args = parser.parse_args(argv[1:])

    configure_logging(args.logfile)

    config = openSigma2SplunkConfiguration(args.config)
    sigma_config = openSigmaConfiguration(args.sigma_config)
    if not config:
        logger.error("No usable configuration; aborting")
        return 1

    # Fail fast on a bad pipeline rather than once per rule.
    try:
        DetectionRuleConverter.build_backend(args.pipeline)
    except Exception as e:
        logger.error(f"{e}")
        return 1

    all_files: List[str] = []
    temp_dirs: List[str] = []
    for source in args.sources:
        if source.startswith(("http://", "https://")):
            if not args.allow_network:
                logger.error(
                    "Refusing network source %s without --allow-network", source
                )
                return 1
            import tempfile
            temp_dir = tempfile.mkdtemp()
            temp_dirs.append(temp_dir)
            source_path = fetchRemoteSigmaRules(source, temp_dir)
            if source_path:
                all_files.extend(loadSigmaRules(source_path))
        else:
            all_files.extend(loadSigmaRules(source))

    if not all_files:
        logger.error("No Sigma rules found in: %s", ", ".join(args.sources))
        return 1
    logger.info("Found %d Sigma rule files", len(all_files))

    detection_rules: List[UseCase] = []
    failures: List[Tuple[str, str]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        results = executor.map(
            lambda f: (f, process_rule(f, args.pipeline, config, sigma_config,
                                       args.output_format)),
            all_files,
        )
        for file, (use_case, err) in results:
            if use_case is not None:
                detection_rules.append(use_case)
            else:
                failures.append((file, err))

    detection_rules.sort(key=lambda r: r.stanza)
    logger.info("Converted %d of %d rules (%d failed)",
                len(detection_rules), len(all_files), len(failures))
    if failures:
        from collections import Counter
        reasons = Counter(err.split(" in ")[0][:120] for _, err in failures)
        for reason, count in reasons.most_common(10):
            logger.warning("  %4d x %s", count, reason)

    savedsearches_conf = generate_savedsearches_conf(detection_rules, config)
    if args.dry_run:
        print(savedsearches_conf)
    else:
        Path(args.output).write_text(savedsearches_conf, encoding="utf-8")
        logger.info("Saved searches written to %s", args.output)

    for temp_dir in temp_dirs:
        try:
            import shutil
            shutil.rmtree(temp_dir)
        except Exception as e:
            logger.warning(f"Failed to clean up {temp_dir}: {e}")

    return 0 if detection_rules else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
