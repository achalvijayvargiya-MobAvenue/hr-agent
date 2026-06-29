"""
Centralised logging configuration.

Sets up two handlers on the root logger:
  1. TimedRotatingFileHandler → logs/hr_agent.log  (rotates daily)
  2. StreamHandler            → stdout              (for dev convenience)

Call setup_logging() once in main.py before any other imports so every
module's module-level logger inherits the same configuration.
"""
import logging
import logging.handlers
import sys
from datetime import datetime
from pathlib import Path


# Log format — same for both file and console so log lines are copy-pasteable
_FMT = "%(asctime)s | %(levelname)-8s | %(name)s — %(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"


class DailyTimestampedFileHandler(logging.handlers.TimedRotatingFileHandler):
    """
    Rotates every day and names the active log file with the current date.
    e.g. logs/hr_agent.log.2026-06-29  → logs/hr_agent.log.2026-06-30

    A new log file is automatically created every day while the app is running.
    """

    def __init__(self, base_path: str, **kwargs):
        self._base_path = base_path
        timestamped = self._current_filename()
        Path(timestamped).parent.mkdir(parents=True, exist_ok=True)
        super().__init__(filename=timestamped, **kwargs)

    def _current_filename(self) -> str:
        return self._base_path + "." + datetime.now().strftime("%Y-%m-%d")

    def doRollover(self):
        """
        Close the current file, compute the next rollover time,
        and reopen a brand-new file whose name reflects the current date.
        Called automatically by the handler every day while the app runs.
        """
        # Close the current log file
        if self.stream:
            self.stream.close()
            self.stream = None

        # Update base filename to current date and open new file
        new_filename = self._current_filename()
        Path(new_filename).parent.mkdir(parents=True, exist_ok=True)
        self.baseFilename = str(Path(new_filename).resolve())
        self.stream = self._open()

        # Advance the next rollover time by one interval (1 day)
        self.rolloverAt += self.interval


def setup_logging(
    log_level: str = "INFO",
    log_file: str = "logs/hr_agent.log." + datetime.now().strftime("%Y-%m-%d"),
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

    # ── File handler (per-day rotation) ──────────────────────────────────────
    file_handler = DailyTimestampedFileHandler(
        base_path="logs/hr_agent.log",
        when="D",        # rotate every day
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
        "Logging initialised — level=%s file=%s rotation=daily backup_count=%d",
        log_level.upper(),
        log_file,
        backup_count,
    )