"""Native document settings; isolated config file, no models or personal writes."""
import importlib
import json

import pytest


@pytest.fixture
def settings_env(tmp_path, monkeypatch):
    module = importlib.import_module('rat.config')
    path = tmp_path / 'rat' / 'config.json'
    monkeypatch.setattr(module, 'CONFIG_FILE', path)
    monkeypatch.delenv('RAT_DOCUMENT_MODEL_PATH', raising=False)
    monkeypatch.delenv('RAT_DOCUMENT_MODEL_PRELOAD', raising=False)
    monkeypatch.setenv('GEMINI_API_KEY', '')
    monkeypatch.setenv('OPENAI_API_KEY', '')
    return module, path


def test_native_settings_are_optional_and_saved_without_changing_general_model(settings_env):
    module, path = settings_env
    settings = module.Config()
    assert settings.document_model_path == '' and settings.document_model_preload is False
    original_model = settings.assistant_model, settings.ollama_model, settings.llm_provider
    settings.document_model_path = '/local model/snapshot'
    settings.document_model_preload = True
    settings.save()
    restored = module.Config()
    assert restored.document_model_path == '/local model/snapshot'
    assert restored.document_model_preload is True
    assert (restored.assistant_model, restored.ollama_model, restored.llm_provider) == original_model
    assert path.is_file()


def test_native_launch_overrides_win_over_saved_settings(settings_env, monkeypatch):
    module, path = settings_env
    path.parent.mkdir()
    path.write_text(json.dumps(dict(document_model_path='/saved', document_model_preload=True)))
    monkeypatch.setenv('RAT_DOCUMENT_MODEL_PATH', ' /explicit launch/model ')
    monkeypatch.setenv('RAT_DOCUMENT_MODEL_PRELOAD', 'false')
    settings = module.Config()
    assert settings.document_model_path == '/explicit launch/model'
    assert settings.document_model_preload is False
    monkeypatch.setenv('RAT_DOCUMENT_MODEL_PATH', '')
    assert module.Config().document_model_path == ''


@pytest.mark.parametrize('value,expected', [('1', True), ('TRUE', True), ('yes', True),
                                          ('0', False), ('no', False), ('invalid', False)])
def test_startup_preload_env_is_explicit(settings_env, monkeypatch, value, expected):
    module, _ = settings_env
    monkeypatch.setenv('RAT_DOCUMENT_MODEL_PRELOAD', value)
    assert module.Config().document_model_preload is expected


def test_invalid_json_setting_types_do_not_enable_native_loading(settings_env):
    module, path = settings_env
    path.parent.mkdir()
    path.write_text(json.dumps(dict(document_model_path=['not a path'], document_model_preload='true')))
    settings = module.Config()
    assert settings.document_model_path == '' and settings.document_model_preload is False
