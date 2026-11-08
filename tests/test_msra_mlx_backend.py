"""Unit tests for MLX generator backend."""

from unittest.mock import MagicMock, patch
import pytest
from structured_llm.msra.mlx_backend import MLXGeneratorBackend


def test_mlx_backend_init():
    backend = MLXGeneratorBackend(model_path="mlx-community/Qwen3-8B-4bit", adapter_path="adapters/test")
    assert backend.model_path == "mlx-community/Qwen3-8B-4bit"
    assert backend.adapter_path == "adapters/test"
    assert backend.model is None


class DummyTokenResponse:
    def __init__(self, text):
        self.text = text


def test_mlx_backend_early_stop_stream():
    # Mock stream_generate yielding token responses
    tokens = [
        DummyTokenResponse("<step id=\"1\">\n"),
        DummyTokenResponse("  <subgoal>Calc"),
        DummyTokenResponse("ulate sum</subgoal>\n"),
        DummyTokenResponse("  <decision>SOLVE_LOCAL"),
        DummyTokenResponse("</decision>\n"),
        DummyTokenResponse("  <execution>2+2=4</execution>\n"),
        DummyTokenResponse("</step>"),
    ]

    with patch("mlx_lm.stream_generate", return_value=tokens):
        backend = MLXGeneratorBackend(model="dummy_model", tokenizer="dummy_tok")
        # Request generation until </decision>
        result = backend.generate_until(
            prompt="Prompt",
            stop_sequences=["</decision>"],
            max_new_tokens=100,
        )

        assert "</decision>" in result
        assert "<execution>" not in result  # Stopped early!
        assert result.endswith("</decision>")
