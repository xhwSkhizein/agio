import logging
import sys
from typing import Any

def setup_logger(name: str = "agio", level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    logger.setLevel(getattr(logging, level.upper()))
    return logger

logger = setup_logger()

def log_debug(msg: str, **kwargs: Any) -> None:
    logger.debug(msg, **kwargs)

def log_info(msg: str, **kwargs: Any) -> None:
    logger.info(msg, **kwargs)

def log_warning(msg: str, **kwargs: Any) -> None:
    logger.warning(msg, **kwargs)

def log_error(msg: str, **kwargs: Any) -> None:
    logger.error(msg, **kwargs)

