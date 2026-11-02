"""
rat.plugins — Dynamic tool pack and domain vertical plugin architecture.
"""
from rat.plugins.manifest import ToolPack, ToolPackManifest, ToolPackState
from rat.plugins.manager import PluginManager, get_plugin_manager

__all__ = [
    "ToolPack",
    "ToolPackManifest",
    "ToolPackState",
    "PluginManager",
    "get_plugin_manager",
]
