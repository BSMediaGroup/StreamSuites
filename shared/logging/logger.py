import logging
from datetime import datetime
from pathlib import Path

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

_LOGGERS = {}


def get_logger(
    name: str,
    *,
    runtime: str = "streamsuites",
) -> logging.Logger:
    """
    Create or retrieve a named logger.

    Parameters:
    - name: logger namespace (e.g. core.app, discord.client)
    - runtime: log file prefix (streamsuites | discord | future runtimes)

    Existing behavior is preserved when runtime is not specified.
    """
    cache_key = f"{runtime}:{name}"
    if cache_key in _LOGGERS:
        return _LOGGERS[cache_key]

    logger = logging.getLogger(cache_key)
    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    # ------------------------------
    # Console handler
    # ------------------------------
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    # ------------------------------
    # File handler (one per run)
    # ------------------------------
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    logfile = LOG_DIR / f"{runtime}-{timestamp}.log"

    file_handler = logging.FileHandler(logfile, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.propagate = False
    _LOGGERS[cache_key] = logger

    return logger
