"""This modules contain method to setup logging."""
import os
import logging
import logging.handlers
from splunk.clilib import cli_common as cli
from splunk.clilib.bundle_paths import make_splunkhome_path


DEFAULT_LOG_LEVEL = "INFO"


def setup_logging(log_name):
    """Set logger for the given log_name."""
    # Make path till log file
    log_file = make_splunkhome_path(
        ["var", "log", "splunk", "%s.log" % log_name])
    # Get directory in which log file is present
    log_dir = os.path.dirname(log_file)
    # Create directory at the required path to store log file, if not found
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Read log level from conf file
    cfg = cli.getConfStanza('ta_tenable_settings', 'logging')
    log_level = str(cfg.get('loglevel'))

    logger = logging.getLogger(log_name)
    logger.propagate = False

    # Set log level
    try:
        logger.setLevel(log_level)
    except Exception:
        logger.setLevel(DEFAULT_LOG_LEVEL)

    handler_exists = any(
        [True for h in logger.handlers if h.baseFilename == log_file])

    if not handler_exists:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, mode="a", maxBytes=10485760, backupCount=10)
        # Format logs
        fmt_str = "%(asctime)s %(levelname)s pid=%(process)d tid=%(threadName)s file=%(filename)s:%(funcName)s:%(lineno)d | %(message)s"  # noqa
        formatter = logging.Formatter(fmt_str)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        if log_level:
            try:
                file_handler.setLevel(log_level)
            except Exception:
                file_handler.setLevel(DEFAULT_LOG_LEVEL)

    return logger
