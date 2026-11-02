"""Logging setup. Call ``configure_logging()`` once, at the program's entry point.

Library modules only do ``logger = logging.getLogger(__name__)`` and never configure
logging themselves. Log paths and counts, never source code (privacy).
"""

import logging
import os
import sys

from codesense.errors import ConfigError

LOG_LEVEL_ENV_VAR = "CODESENSE_LOG_LEVEL"
_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging() -> None:
    """Send all logs to stderr: stdout is reserved for the JSON-RPC protocol.

    CodeSense logs at ``CODESENSE_LOG_LEVEL`` (default INFO); third-party libraries
    (transformers, torch, ...) stay at WARNING so DEBUG does not drown in their chatter.
    """
    level = os.environ.get(LOG_LEVEL_ENV_VAR, "INFO").upper()
    if level not in logging.getLevelNamesMapping():
        raise ConfigError(
            f"{LOG_LEVEL_ENV_VAR}={level!r} is not a valid log level; "
            "use DEBUG, INFO, WARNING, ERROR or CRITICAL"
        )

    # force=True replaces existing handlers, so calling this twice is safe.
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING, format=_FORMAT, force=True)
    logging.getLogger("codesense").setLevel(level)
