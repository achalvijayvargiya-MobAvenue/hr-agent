"""
Centralised logging configuration.

Sets up two handlers on the root logger:
  1. TimedRotatingFileHandler → logs/hr_agent.log  (rotates daily at midnight)
  2. StreamHandler            → stdout              (for dev convenience)

Call setup_logging() once in main.py before any other imports so every
module's module-level logger inherits the same configuration.
"""
import logging
import logging.handlers
import sys
from pathlib import Path


# Log format — same for both file and console so log lines are copy-pasteable
_FMT = "%(asctime)s | %(levelname)-8s | %(name)s — %(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"


def setup_logging(
    log_level: str = "INFO",
    log_file: str = "logs/hr_agent.log",
    backup_count: int = 30,
) -> None:
    """
    Configure the root logger with file + console handlers.

    Args:
        log_level:    Logging level string ("DEBUG", "INFO", "WARNING", …).
        log_file:     Path to the active log file (directories are created automatically).
        backup_count: Number of daily rotated log files to retain.
    """
    level = getattr(logging, log_level.upper(), logging.INFO)
    formatter = logging.Formatter(_FMT, datefmt=_DATE_FMT)

    # ── File handler (daily rotation at local midnight) ───────────────────────
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    file_handler = logging.handlers.TimedRotatingFileHandler(
        filename=log_path,
        when="midnight",
        interval=1,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.suffix = "%Y-%m-%d"
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)

    # ── Console handler ───────────────────────────────────────────────────────
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)

    # ── Root logger ───────────────────────────────────────────────────────────
    root = logging.getLogger()
    root.setLevel(level)

    # Avoid duplicate handlers if setup_logging is called more than once
    root.handlers.clear()
    root.addHandler(file_handler)
    root.addHandler(console_handler)

    # Silence noisy third-party loggers unless we're in DEBUG mode
    if level > logging.DEBUG:
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("openai").setLevel(logging.WARNING)
        logging.getLogger("pdfminer").setLevel(logging.WARNING)
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        "Logging initialised — level=%s file=%s rotation=daily backup_days=%d",
        log_level.upper(),
        log_path.resolve(),
        backup_count,
    )
