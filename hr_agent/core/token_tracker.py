import logging
import threading
from hr_agent.core.logging_config import DailyTimestampedFileHandler, _FMT, _DATE_FMT

# Configure a separate logger for tokens
token_logger = logging.getLogger("hr_agent.tokens")
token_logger.setLevel(logging.INFO)
token_logger.propagate = False  # Prevent propagating to the main hr_agent.log

# Set up the file handler specifically for tokens.log
_token_handler = DailyTimestampedFileHandler(
    base_path="logs/tokens.log",
    when="D",
    interval=1,
    backupCount=30,
    encoding="utf-8",
)
_token_handler.suffix = "%Y-%m-%d"
_token_handler.setFormatter(logging.Formatter(_FMT, datefmt=_DATE_FMT))
token_logger.addHandler(_token_handler)


class TokenTracker:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance.usage_stats = {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "calls": 0,
                }
        return cls._instance

    def add_usage(self, service_name: str, prompt_tokens: int, completion_tokens: int, total_tokens: int):
        with self._lock:
            self.usage_stats["prompt_tokens"] += prompt_tokens
            self.usage_stats["completion_tokens"] += completion_tokens
            self.usage_stats["total_tokens"] += total_tokens
            self.usage_stats["calls"] += 1
            
            token_logger.info(
                "[END-TO-END TOKENS] Service: %s | Cumulative - prompt: %d, completion: %d, total: %d (across %d calls)",
                service_name,
                self.usage_stats["prompt_tokens"],
                self.usage_stats["completion_tokens"],
                self.usage_stats["total_tokens"],
                self.usage_stats["calls"]
            )

token_tracker = TokenTracker()
