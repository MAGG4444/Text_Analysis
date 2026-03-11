import json
import logging
from pathlib import Path
from typing import Any


LOGGER_NAME = "narrative_baseline"


def configure_logging(level: str = "INFO") -> logging.Logger:
    """Configure process-wide logging and return the project logger."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(numeric_level)
    return logger


def ensure_directory(path: str | Path) -> Path:
    """Create a directory if needed and return it as a Path."""
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def save_json(data: Any, path: str | Path) -> Path:
    """Serialize JSON data to disk with stable formatting."""
    output_path = Path(path)
    ensure_directory(output_path.parent)
    with output_path.open("w", encoding="utf-8") as file_handle:
        json.dump(data, file_handle, ensure_ascii=False, indent=2)
    return output_path
