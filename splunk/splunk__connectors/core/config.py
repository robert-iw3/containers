"""
Environment configuration, read once and validated at startup.

Every setting is read here so a connector cannot disagree with its own
compose file about a default. Bad values fail at startup with the name of the
variable, rather than at the first event with a traceback from inside a
worker.
"""

import os


class ConfigError(Exception):
    pass


def _int(name, default, minimum=None, maximum=None):
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ConfigError(f"{name}={raw!r} is not an integer")
    if minimum is not None and value < minimum:
        raise ConfigError(f"{name}={value} is below the minimum of {minimum}")
    if maximum is not None and value > maximum:
        raise ConfigError(f"{name}={value} is above the maximum of {maximum}")
    return value


def _float(name, default, minimum=None):
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        value = float(raw)
    except ValueError:
        raise ConfigError(f"{name}={raw!r} is not a number")
    if minimum is not None and value < minimum:
        raise ConfigError(f"{name}={value} is below the minimum of {minimum}")
    return value


def _bool(name, default):
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


class Config:
    """Resolved settings for one connector process."""

    def __init__(self, fmt, log_dir_var, extension, sink="splunk"):
        self.format = fmt
        self.extension = extension
        self.sink = sink

        self.log_dir = os.getenv(log_dir_var, f"/var/log/{fmt}_data")
        self.schemas_file = os.getenv("SCHEMAS_FILE", "/app/schemas.yaml")
        self.state_path = os.getenv("STATE_PATH", "/var/lib/connector/offsets.json")

        self.hec_url = os.getenv(
            "SPLUNK_HEC_URL", "https://your-splunk-host:8088/services/collector/event"
        )
        self.hec_token = os.getenv("SPLUNK_TOKEN", "")
        self.index = os.getenv("SPLUNK_INDEX", "") or None
        self.host = os.getenv("SPLUNK_HOST", "") or None
        self.verify_tls = _bool("SPLUNK_VERIFY_TLS", True)
        self.ca_file = os.getenv("SPLUNK_CA_FILE", "") or None

        self.batch_size = _int("BATCH_SIZE", 100, minimum=1, maximum=100_000)
        self.buffer_timeout = _float("BUFFER_TIMEOUT", 2.0, minimum=0.1)
        self.read_chunk_bytes = _int("READ_CHUNK_BYTES", 1024 * 1024, minimum=4096)
        # Concurrency over files, not processes: the work is I/O bound.
        self.parse_concurrency = _int("WORKER_COUNT", 2, minimum=1, maximum=64)
        self.queue_depth = _int("QUEUE_DEPTH", 8, minimum=1, maximum=1024)

        self.max_retries = _int("MAX_RETRIES", 5, minimum=0, maximum=100)
        self.retry_base = _float("RETRY_BASE_SECONDS", 0.5, minimum=0.01)
        self.retry_cap = _float("RETRY_CAP_SECONDS", 30.0, minimum=0.1)
        self.request_timeout = _float("REQUEST_TIMEOUT", 30.0, minimum=1.0)

        self.scan_interval = _float("SCAN_INTERVAL", 5.0, minimum=0.5)
        self.delimiter = os.getenv("CSV_DELIMITER", ",")
        self.status_interval = _float("STATUS_INTERVAL", 60.0, minimum=1.0)

        # Polled sources. DB_TYPE selects the driver, imported lazily so a
        # SQLite deployment does not need Oracle's client library installed.
        self.db_type = os.getenv("DB_TYPE", "sqlite").strip().lower()
        self.db_conn_str = os.getenv("DB_CONN_STR", "")

        self.es_host = os.getenv("ES_HOST", "http://localhost:9200")
        self.es_index = os.getenv("ES_INDEX", f"{fmt}-logs")
        self.es_user = os.getenv("ES_USER", "") or None
        self.es_password = os.getenv("ES_PASSWORD", "")

        if self.sink == "splunk":
            if not self.hec_token:
                raise ConfigError("SPLUNK_TOKEN is not set")
            if "your-splunk-host" in self.hec_url:
                raise ConfigError(f"SPLUNK_HEC_URL is still the placeholder: {self.hec_url}")
        elif self.sink == "elasticsearch":
            if not self.es_host:
                raise ConfigError("ES_HOST is not set")
        else:
            raise ConfigError(f"unknown sink {self.sink!r}")

        if len(self.delimiter) != 1:
            raise ConfigError(f"CSV_DELIMITER must be one character, got {self.delimiter!r}")

        if fmt == "sql":
            valid = ("sqlite", "postgres", "mysql", "mssql", "oracle")
            if self.db_type not in valid:
                raise ConfigError(f"DB_TYPE must be one of {', '.join(valid)}, got {self.db_type!r}")
            if not self.db_conn_str:
                raise ConfigError("DB_CONN_STR is not set")

    def redacted(self):
        """Settings safe to log at startup, with credentials reduced to a length."""
        common = {
            "format": self.format,
            "sink": self.sink,
            "log_dir": self.log_dir,
            "schemas_file": self.schemas_file,
            "state_path": self.state_path,
            "batch_size": self.batch_size,
            "parse_concurrency": self.parse_concurrency,
        }
        if self.format == "sql":
            # The connection string carries a password; report the driver and
            # the host, never the string.
            common["db_type"] = self.db_type
            common["db_conn_str"] = _redact_conn_str(self.db_conn_str)
        if self.sink == "splunk":
            common.update(
                hec_url=self.hec_url,
                hec_token=f"<{len(self.hec_token)} chars>",
                index=self.index,
                verify_tls=self.verify_tls,
            )
        else:
            common.update(
                es_host=self.es_host,
                es_index=self.es_index,
                es_user=self.es_user,
                es_password=f"<{len(self.es_password)} chars>" if self.es_password else None,
            )
        return common


def _redact_conn_str(conn_str):
    """A connection string minus anything before the @, which is where every
    dialect puts the credentials."""
    if not conn_str:
        return None
    if "@" in conn_str:
        scheme, _, rest = conn_str.partition("://")
        return f"{scheme}://<redacted>@{rest.split('@', 1)[-1]}" if rest else "<redacted>"
    return conn_str
