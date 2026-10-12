"""Structured logging configuration for NeSy-DocAI."""
import logging
from pathlib import Path
from typing import Optional

class ColoredFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': '\033[90m',
        'INFO': '\033[94m',
        'WARNING': '\033[93m',
        'ERROR': '\033[91m',
        'CRITICAL': '\033[95m'
    }
    RESET = '\033[0m'

    def format(self, record):
        levelname = record.levelname
        color = self.COLORS.get(levelname, self.RESET)
        record.levelname = f"{color}{levelname}{self.RESET}"
        return super().format(record)

def setup_logging(level: str = 'INFO', log_file: Optional[Path | str] = None, json_format: bool = False):
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    logger = logging.getLogger('nesy_docai')
    logger.setLevel(numeric_level)
    
    # Clear existing handlers
    if logger.hasHandlers():
        logger.handlers.clear()

    formatter_str = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(ColoredFormatter(formatter_str))
    logger.addHandler(console_handler)

    if log_file:
        file_path = Path(log_file)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(file_path, encoding='utf-8')
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(logging.Formatter(formatter_str))
        logger.addHandler(file_handler)

def get_logger(name: str) -> logging.Logger:
    """Get a configured logger for the given module name."""
    if not name.startswith('nesy_docai.'):
        name = f'nesy_docai.{name}'
    return logging.getLogger(name)
