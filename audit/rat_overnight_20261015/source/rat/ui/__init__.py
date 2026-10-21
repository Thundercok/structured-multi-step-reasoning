"""RAT UI exports, loaded only when a widget is requested."""
from importlib import import_module

__all__ = ["OmnibarWindow", "SpotlightWindow", "PreviewPanel", "SettingsDialog"]
_MODULES = {"OmnibarWindow": "omnibar", "SpotlightWindow": "spotlight_window",
            "PreviewPanel": "preview_panel", "SettingsDialog": "settings_dialog"}


def __getattr__(name):
    if name not in _MODULES:
        raise AttributeError(name)
    value = getattr(import_module(f"rat.ui.{_MODULES[name]}"), name)
    globals()[name] = value
    return value
