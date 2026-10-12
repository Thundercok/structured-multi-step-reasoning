"""
rat.engine.llm_client — LLM integration (Gemini, OpenAI, Ollama, and Smart Offline Reasoner).
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from rat.config import config
from rat.engine.context_parser import remove_accents

logger = logging.getLogger("rat.llm")


class LLMClient:
    """Multi-provider LLM Client with automatic offline fallback."""

    def __init__(self) -> None:
        self.provider = config.llm_provider
        self.gemini_key = config.gemini_api_key or os.getenv("GEMINI_API_KEY", "")
        self.openai_key = config.openai_api_key or os.getenv("OPENAI_API_KEY", "")
        self.ollama_url = config.ollama_url
        self.ollama_model = config.ollama_model

    def is_available(self) -> bool:
        """Check if any online LLM provider is configured."""
        if self.provider == "gemini" and self.gemini_key:
            return True
        if self.provider == "openai" and self.openai_key:
            return True
        if self.provider == "ollama":
            return True
        if self.provider == "auto" and (self.gemini_key or self.openai_key):
            return True
        return False

    def query_gemini(self, prompt: str) -> Optional[str]:
        """Query Google Gemini API via lightweight HTTP request."""
        if not self.gemini_key:
            return None

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.gemini_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1000}
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode("utf-8"))
                candidates = result.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        return parts[0].get("text", "").strip()
        except Exception as e:
            logger.warning(f"Gemini API query error: {e}")
        return None

    def query_openai(self, prompt: str) -> Optional[str]:
        """Query OpenAI API."""
        if not self.openai_key:
            return None

        url = "https://api.openai.com/v1/chat/completions"
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "You are a helpful file search assistant."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2,
            "max_tokens": 1000
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.openai_key}"
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode("utf-8"))
                choices = result.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "").strip()
        except Exception as e:
            logger.warning(f"OpenAI API query error: {e}")
        return None

    def query_ollama(self, prompt: str) -> Optional[str]:
        """Query local Ollama instance."""
        url = f"{self.ollama_url.rstrip('/')}/api/generate"
        payload = {
            "model": self.ollama_model,
            "prompt": prompt,
            "stream": False
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                result = json.loads(response.read().decode("utf-8"))
                return result.get("response", "").strip()
        except Exception as e:
            logger.warning(f"Ollama query error: {e}")
        return None

    def generate(self, prompt: str) -> Optional[str]:
        """Generate response choosing the optimal active provider."""
        return self.call_llm(prompt)

    def call_llm(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1000
    ) -> Optional[str]:
        """Generate response with optional system prompt and max tokens."""
        # Refresh keys in case config changed
        self.gemini_key = config.gemini_api_key or os.getenv("GEMINI_API_KEY", "")
        self.openai_key = config.openai_api_key or os.getenv("OPENAI_API_KEY", "")

        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

        if self.provider == "gemini" or (self.provider == "auto" and self.gemini_key):
            res = self.query_gemini(full_prompt)
            if res:
                return res

        if self.provider == "openai" or (self.provider == "auto" and self.openai_key):
            res = self.query_openai(full_prompt)
            if res:
                return res

        if self.provider == "ollama":
            res = self.query_ollama(full_prompt)
            if res:
                return res

        return None
