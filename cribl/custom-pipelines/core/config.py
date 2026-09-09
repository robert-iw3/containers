import configparser
import pathlib


class ConfigError(Exception):
    """Raised with the name of the setting at fault, not a traceback."""


def load(fmt_dir, section):
    """Read <fmt_dir>/config/config.ini and return (parser, section proxy).

    fmt_dir is the format's directory, e.g. .../custom-pipelines/csv.
    """
    ini = pathlib.Path(fmt_dir) / "config" / "config.ini"
    if not ini.is_file():
        example = ini.with_suffix(".ini.example")
        hint = f" Copy {example.name} to {ini.name} and edit it." if example.is_file() else ""
        raise ConfigError(f"{ini} not found.{hint}")

    parser = configparser.ConfigParser()
    parser.read(ini)

    for required in ("cribl", section):
        if required not in parser:
            raise ConfigError(f"{ini} has no [{required}] section")

    for key in ("host", "user", "pass"):
        if not parser["cribl"].get(key):
            raise ConfigError(f"{ini} [cribl] is missing '{key}'")

    return parser


def template_path(fmt_dir):
    p = pathlib.Path(fmt_dir) / "config" / "pipeline_config.json"
    if not p.is_file():
        raise ConfigError(f"{p} not found")
    return p
