"""
rat.config — Configuration management for rat assistant.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

# Default Paths
HOME_DIR = Path.home()
RAT_DIR = HOME_DIR / ".rat"
RAT_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_FILE = RAT_DIR / "config.json"
DEFAULT_DB_PATH = RAT_DIR / "rat_index.db"

# Default directories to watch & index
DEFAULT_WATCH_DIRS = [
    str(HOME_DIR / "Downloads"),
    str(HOME_DIR / "Documents"),
    str(HOME_DIR / "Desktop"),
]

# Supported Extensions
SUPPORTED_EXTENSIONS = {
    # Documents
    ".pdf", ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls", ".csv", ".rtf",
    # Plain text & Notes
    ".txt", ".md", ".markdown", ".rst",
    # Code & Configs
    ".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".css", ".json", ".yaml", ".yml",
    ".toml", ".sh", ".sql", ".xml", ".log",
    # Images (Metadata & OCR)
    ".jpg", ".jpeg", ".png", ".webp"
}

# Directories to always ignore (system, hidden, build, and sensitive credentials)
IGNORE_DIRS = {
    ".git", ".svn", ".hg", "node_modules", ".venv", "venv", "env",
    "__pycache__", ".pytest_cache", ".cargo", "target", "build", "dist", "dmg_temp",
    "Library", "Applications", ".Trash", ".cache", ".local", "RAWs",
    "Photos", "Photos Library.photoslibrary", "Movies", "Music", "Podcasts",
    ".npm", ".cargo", ".rustup", "Pods",
    # Sensitive credentials & vaults
    ".ssh", ".gnupg", "Keychain", "Keychains", ".aws", ".azure", ".docker",
    ".config", ".kube", ".terraform"
}

# Ignore file patterns (temporary, system, and sensitive credentials/keys)
IGNORE_PATTERNS = {
    ".DS_Store", "Thumbs.db", "desktop.ini", "*.tmp", "*.swp", "~$*", "*.pyc",
    # Sensitive secrets, tokens, private keys, and credential vaults
    ".env", ".env.*", "*.pem", "*.key", "*.p12", "*.pfx", "*.cer", "*.crt",
    "*.kdbx", "id_rsa*", "id_ed25519*", "credentials.json", "service-account*.json",
    "*.wallet", "*seed_phrase*", "*recovery_phrase*", "master.key"
}

MAX_FILE_SIZE_BYTES = 30 * 1024 * 1024  # 30 MB limit for deep text extraction


def is_on_battery() -> bool:
    """Check if macOS machine is running on battery power."""
    import platform
    import subprocess
    if platform.system() == "Darwin":
        try:
            res = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True, timeout=1)
            return "Battery Power" in res.stdout
        except Exception:
            return False
    return False


def set_thread_qos_background() -> bool:
    """Set current thread QoS to QOS_CLASS_BACKGROUND on macOS (Apple Silicon E-cores)."""
    import ctypes
    import platform
    if platform.system() == "Darwin":
        try:
            lib = ctypes.CDLL("libSystem.dylib")
            # 0x09 is QOS_CLASS_BACKGROUND in macOS pthread
            res = lib.pthread_set_qos_class_self_np(0x09, 0)
            return res == 0
        except Exception:
            pass
    return False



class Config:
    def __init__(self) -> None:
        self.db_path: str = str(DEFAULT_DB_PATH)
        self.indexed_directories: List[str] = [
            d for d in DEFAULT_WATCH_DIRS if os.path.exists(d)
        ]

        self.llm_provider: str = "auto"  # "auto", "slm", "gemini", "openai", "ollama", "offline"
        self.gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
        self.openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
        self.ollama_url: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.ollama_model: str = "qwen2.5:1.5b"
        self.use_slm: bool = True
        self.auto_watch: bool = True
        self.max_results: int = 15
        self.global_hotkey: str = os.getenv("RAT_HOTKEY", "<cmd>+<shift>+<space>")
        self.first_run_completed: bool = False
        self.launch_at_login: bool = False
        self.memory_sentinel_enabled: bool = True
        self.deep_idle_timeout_seconds: float = 2700.0  # 45 minutes
        self.memory_pressure_eviction_enabled: bool = True
        self.load()

    def get_hotkey_display(self) -> str:
        """Return native macOS symbols representation for global_hotkey."""
        key = self.global_hotkey
        key = key.replace("<alt>", "⌥").replace("<option>", "⌥")
        key = key.replace("<shift>", "⇧")
        key = key.replace("<cmd>", "⌘").replace("<super>", "⌘")
        key = key.replace("<ctrl>", "⌃")
        key = key.replace("<space>", "Space")
        key = key.replace("<", "").replace(">", "")
        parts = [p.strip().capitalize() if p.strip() not in ["⌥", "⇧", "⌘", "⌃"] else p.strip() for p in key.split("+")]
        return " + ".join(parts)

    def load(self) -> None:
        """Load settings from config.json if exists."""
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data: Dict[str, Any] = json.load(f)
                    if "indexed_directories" in data:
                        self.indexed_directories = data["indexed_directories"]
                    if "llm_provider" in data:
                        self.llm_provider = data["llm_provider"]
                    if "gemini_api_key" in data and data["gemini_api_key"]:
                        self.gemini_api_key = data["gemini_api_key"]
                    if "openai_api_key" in data and data["openai_api_key"]:
                        self.openai_api_key = data["openai_api_key"]
                    if "ollama_url" in data:
                        self.ollama_url = data["ollama_url"]
                    if "ollama_model" in data:
                        self.ollama_model = data["ollama_model"]
                    if "auto_watch" in data:
                        self.auto_watch = data["auto_watch"]
                    if "max_results" in data:
                        self.max_results = data["max_results"]
                    if "global_hotkey" in data:
                        self.global_hotkey = data["global_hotkey"]
                    if "first_run_completed" in data:
                        self.first_run_completed = data["first_run_completed"]
                    if "launch_at_login" in data:
                        self.launch_at_login = data["launch_at_login"]
                    if "memory_sentinel_enabled" in data:
                        self.memory_sentinel_enabled = data["memory_sentinel_enabled"]
                    if "deep_idle_timeout_seconds" in data:
                        self.deep_idle_timeout_seconds = float(data["deep_idle_timeout_seconds"])
                    if "memory_pressure_eviction_enabled" in data:
                        self.memory_pressure_eviction_enabled = data["memory_pressure_eviction_enabled"]
            except Exception:
                pass

    def save(self) -> None:
        """Save settings to config.json."""
        data = {
            "first_run_completed": self.first_run_completed,
            "launch_at_login": self.launch_at_login,
            "indexed_directories": self.indexed_directories,
            "llm_provider": self.llm_provider,
            "gemini_api_key": self.gemini_api_key,
            "openai_api_key": self.openai_api_key,
            "ollama_url": self.ollama_url,
            "ollama_model": self.ollama_model,
            "auto_watch": self.auto_watch,
            "max_results": self.max_results,
            "global_hotkey": self.global_hotkey,
            "memory_sentinel_enabled": self.memory_sentinel_enabled,
            "deep_idle_timeout_seconds": self.deep_idle_timeout_seconds,
            "memory_pressure_eviction_enabled": self.memory_pressure_eviction_enabled,
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


# Global singleton instance
config = Config()
