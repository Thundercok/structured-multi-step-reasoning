"""Centralized configuration for NeSy-DocAI pipeline."""
import os
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional


@dataclass
class NeSyConfig:
    tesseract_path: str = '/opt/homebrew/bin/tesseract'
    vision_enabled: bool = True
    qwen_enabled: bool = False
    max_workers: int = 4
    z3_timeout_ms: int = 1000
    output_dir: Path = Path('./output')
    csv_encoding: str = 'utf-8-sig'
    high_value_threshold_vnd: int = 500_000_000
    duplicate_registry_path: str = 'invoice_registry.db'
    log_level: str = 'INFO'
    log_file: Optional[Path] = None

    @classmethod
    def from_env(cls) -> "NeSyConfig":
        config = cls()
        if 'NESY_TESSERACT_PATH' in os.environ:
            config.tesseract_path = os.environ['NESY_TESSERACT_PATH']
        if 'NESY_VISION_ENABLED' in os.environ:
            config.vision_enabled = os.environ['NESY_VISION_ENABLED'].lower() in ('true', '1', 't')
        if 'NESY_QWEN_ENABLED' in os.environ:
            config.qwen_enabled = os.environ['NESY_QWEN_ENABLED'].lower() in ('true', '1', 't')
        if 'NESY_MAX_WORKERS' in os.environ:
            config.max_workers = int(os.environ['NESY_MAX_WORKERS'])
        if 'NESY_Z3_TIMEOUT' in os.environ:
            config.z3_timeout_ms = int(os.environ['NESY_Z3_TIMEOUT'])
        if 'NESY_OUTPUT_DIR' in os.environ:
            config.output_dir = Path(os.environ['NESY_OUTPUT_DIR'])
        if 'NESY_CSV_ENCODING' in os.environ:
            config.csv_encoding = os.environ['NESY_CSV_ENCODING']
        if 'NESY_HIGH_VALUE_THRESHOLD_VND' in os.environ:
            config.high_value_threshold_vnd = int(os.environ['NESY_HIGH_VALUE_THRESHOLD_VND'])
        if 'NESY_DUPLICATE_REGISTRY_PATH' in os.environ:
            config.duplicate_registry_path = os.environ['NESY_DUPLICATE_REGISTRY_PATH']
        if 'NESY_LOG_LEVEL' in os.environ:
            config.log_level = os.environ['NESY_LOG_LEVEL']
        if 'NESY_LOG_FILE' in os.environ:
            config.log_file = Path(os.environ['NESY_LOG_FILE'])
        return config

    @classmethod
    def from_yaml(cls, yaml_path: str | Path) -> "NeSyConfig":
        path = Path(yaml_path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        data = {}
        try:
            import yaml
            with open(path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
        except ImportError:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)

        config = cls()
        for k, v in data.items():
            if hasattr(config, k):
                if k in ('output_dir', 'log_file') and v is not None:
                    setattr(config, k, Path(v))
                else:
                    setattr(config, k, v)
        return config

    def to_dict(self) -> dict:
        d = asdict(self)
        if d.get('output_dir'):
            d['output_dir'] = str(d['output_dir'])
        if d.get('log_file'):
            d['log_file'] = str(d['log_file'])
        return d
