"""Seed failure contract without loading MLX native code or a model."""
import builtins
import sys
import types
from unittest.mock import Mock

import pytest

from qwen_mlx_backend import QwenMLXBackend, QwenMLXStagedRunner


def stub_mlx(monkeypatch, setter):
    parent = types.ModuleType("mlx")
    parent.__path__ = []
    core = types.ModuleType("mlx.core")
    core.random = types.SimpleNamespace(seed=setter)
    parent.core = core
    monkeypatch.setitem(sys.modules, "mlx", parent)
    monkeypatch.setitem(sys.modules, "mlx.core", core)


def test_native_seed_error_prevents_generation(monkeypatch):
    setter = Mock(side_effect=RuntimeError("authored seed failure"))
    stub_mlx(monkeypatch, setter)
    backend = QwenMLXBackend.__new__(QwenMLXBackend)
    backend._chat = Mock()
    runner = QwenMLXStagedRunner(backend)
    with pytest.raises(RuntimeError, match="authored seed failure"):
        runner.run_generation({"query": "fixture only"}, "DIRECT", 1024, 42)
    setter.assert_called_once_with(42)
    backend._chat.assert_not_called()


def test_missing_mlx_is_not_silently_seeded(monkeypatch):
    original = builtins.__import__
    def guarded(name, *args, **kwargs):
        if name == "mlx.core":
            raise ModuleNotFoundError("authored missing MLX")
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", guarded)
    backend = QwenMLXBackend.__new__(QwenMLXBackend)
    with pytest.raises(ModuleNotFoundError, match="authored missing MLX"):
        backend.set_seed(42)


def test_native_seed_success_applies_both_generators(monkeypatch):
    setter = Mock()
    stub_mlx(monkeypatch, setter)
    numpy_setter = Mock()
    monkeypatch.setattr("qwen_mlx_backend.np.random.seed", numpy_setter)
    backend = QwenMLXBackend.__new__(QwenMLXBackend)
    backend.set_seed(42)
    setter.assert_called_once_with(42)
    numpy_setter.assert_called_once_with(42)
