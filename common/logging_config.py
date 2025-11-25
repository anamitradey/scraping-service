# logging_config.py
import logging
import json
import os
import sys
from datetime import datetime
from typing import Any

SERVICE_NAME = os.getenv("SERVICE_NAME", "yt-unknown")
ENV = os.getenv("ENV", "local")  # "local" or "prod"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base: dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "severity": record.levelname,
            "service": getattr(record, "service", SERVICE_NAME),
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key in base:
                continue
            if key.startswith("_") or key in (
                "args", "msg", "created", "msecs", "relativeCreated",
                "levelno", "levelname", "name", "pathname", "filename",
                "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "thread", "threadName",
                "processName", "process",
            ):
                continue
            base[key] = value
        return json.dumps(base)


def get_logger(name: str = "yt_scraper") -> logging.LoggerAdapter[logging.Logger]:
    """
    Returns a LoggerAdapter that always has `service` in its extra dict.
    """
    base_logger = logging.getLogger(name)
    if base_logger.handlers:
        # Already configured: just wrap again to ensure service is present
        return logging.LoggerAdapter(base_logger, {"service": SERVICE_NAME})

    base_logger.setLevel(logging.INFO)

    if ENV == "local":
        handler: logging.Handler = logging.FileHandler("yt_scraper.log")
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s [%(service)s] %(message)s"
        )
    else:
        handler = logging.StreamHandler(sys.stdout)
        formatter = JsonFormatter()

    handler.setFormatter(formatter)
    base_logger.addHandler(handler)

    return logging.LoggerAdapter(base_logger, {"service": SERVICE_NAME})
