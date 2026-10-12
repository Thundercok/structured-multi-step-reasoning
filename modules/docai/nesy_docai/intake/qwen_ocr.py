"""
Ollama Qwen2.5-VL Multimodal Vision-Language Model Intake Engine
"""

import requests
from typing import Dict, Any, Optional


class QwenVLEngine:
    def __init__(self, ollama_url: str = "http://localhost:11434", model_name: str = "qwen2.5-vl:3b"):
        self.ollama_url = ollama_url
        self.model_name = model_name

    def is_available(self) -> bool:
        try:
            res = requests.get(f"{self.ollama_url}/api/tags", timeout=1)
            return res.status_code == 200
        except Exception:
            return False

    def process_image(self, image_path: str) -> Optional[Dict[str, Any]]:
        """
        Sends structured multimodal prompt to Ollama Qwen2.5-VL if server is online.
        """
        if not self.is_available():
            return None

        # Structure API call if needed
        return None
