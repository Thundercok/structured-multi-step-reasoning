"""The assistant answers with a model seen to call tools; lighter jobs keep the small one."""
from unittest.mock import patch

import pytest

from rat.config import config
from rat.engine import slm
from rat.engine.assistant_runtime import AssistantRuntime


@pytest.mark.parametrize("installed, explicit, chosen", [
    (["qwen2.5:1.5b", "qwen3:4b-instruct", "qwen3:4b"], "", "qwen3:4b-instruct"),
    (["qwen3:4b-instruct"], "", "qwen3:4b-instruct"),
    (["QWEN3:4B-INSTRUCT"], "", "qwen3:4b-instruct"),
    # Measured as worse: leaks reasoning and takes minutes, so it is not picked on its own.
    (["qwen2.5:1.5b", "qwen3:4b"], "", None),
    (["qwen2.5:1.5b"], "", None),
    ([], "", None),
    (["my-model:7b", "qwen3:4b-instruct"], "my-model:7b", "my-model:7b"),
    # An override that is not installed must not break answering.
    (["qwen3:4b-instruct"], "gone:1b", "qwen3:4b-instruct"),
    (["qwen2.5:1.5b"], "gone:1b", None),
])
def test_pick_assistant_model(installed, explicit, chosen):
    assert slm.pick_assistant_model(installed, explicit) == chosen


def test_engine_follows_what_is_installed(monkeypatch):
    monkeypatch.setattr(config, "assistant_model", "")
    monkeypatch.setattr(slm.slm_engine, "list_installed_models", lambda: ["qwen2.5:1.5b", "qwen3:4b-instruct"])
    engine = slm.assistant_engine()
    assert engine is not slm.slm_engine
    assert engine.model == "qwen3:4b-instruct"
    assert slm.assistant_engine() is engine

    monkeypatch.setattr(slm.slm_engine, "list_installed_models", lambda: ["qwen2.5:1.5b"])
    assert slm.assistant_engine() is slm.slm_engine


def test_background_jobs_keep_the_small_model():
    assert slm.slm_engine.model == config.ollama_model


@pytest.mark.parametrize("installed, ok", [
    (["qwen3:4b-instruct"], True),
    (["qwen2.5:1.5b"], False),
    # Ollama off or empty is a different problem, already reported as such.
    ([], True),
])
def test_warning_is_only_for_a_model_that_cannot_use_tools(monkeypatch, installed, ok):
    monkeypatch.setattr(config, "assistant_model", "")
    monkeypatch.setattr(slm.slm_engine, "list_installed_models", lambda: installed)
    assert slm.assistant_can_use_tools() is ok


def test_runtime_reaches_the_chosen_model(monkeypatch):
    monkeypatch.setattr(config, "assistant_model", "")
    monkeypatch.setattr(slm.slm_engine, "list_installed_models", lambda: ["qwen2.5:1.5b", "qwen3:4b-instruct"])
    used = []

    def chat(self, messages, tools, **kwargs):
        used.append(self.model)
        return {"message": {"content": "Được."}, "prompt_tokens": 1, "completion_tokens": 1}

    with patch.object(slm.SLMEngine, "chat_with_meta", chat):
        AssistantRuntime(discover_tools=True).run("xin chào", max_steps=1)
    assert used and set(used) == {"qwen3:4b-instruct"}


def test_injected_client_is_left_alone():
    class Client:
        supports_chat_callbacks = True
        calls = 0

        def chat_with_meta(self, messages, tools, **kwargs):
            Client.calls += 1
            return {"message": {"content": "Được."}, "prompt_tokens": 1, "completion_tokens": 1}

    AssistantRuntime(discover_tools=True, model_client=Client()).run("xin chào", max_steps=1)
    assert Client.calls >= 1
