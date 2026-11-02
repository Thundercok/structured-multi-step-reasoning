"""
rat.plugins.manager — Dynamic tool pack discovery, registration, and lifecycle management.
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Dict, List, Optional, Set

from rat.plugins.manifest import ToolPack, ToolPackManifest

logger = logging.getLogger("rat.plugins")


class PluginManager:
    """Central manager for discovering, registering, and dynamically toggling domain tool packs."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._packs: Dict[str, ToolPack] = {}
        # Track which pack IDs registered which capabilities: {pack_id: [capability_names]}
        self._pack_caps: Dict[str, Set[str]] = {}
        self._listeners: List[Callable[[str, str], None]] = []

    def register_pack(self, pack: ToolPack) -> None:
        """Register a tool pack with the manager."""
        with self._lock:
            self._packs[pack.manifest.id] = pack
            logger.debug(f"PluginManager: Registered tool pack '{pack.manifest.id}' ({pack.manifest.name})")

    def unregister_pack(self, pack_id: str) -> Optional[ToolPack]:
        """Unregister a tool pack from the manager."""
        with self._lock:
            pack = self._packs.pop(pack_id, None)
            self._pack_caps.pop(pack_id, None)
            return pack

    def get_pack(self, pack_id: str) -> Optional[ToolPack]:
        """Look up a tool pack by ID."""
        with self._lock:
            return self._packs.get(pack_id)

    def list_packs(self) -> List[ToolPack]:
        """Return all registered tool packs."""
        with self._lock:
            return list(self._packs.values())

    def list_manifests(self) -> List[ToolPackManifest]:
        """Return manifests of all available tool packs."""
        with self._lock:
            return [p.manifest for p in self._packs.values()]

    def is_pack_loaded(self, pack_id: str, registry: Any) -> bool:
        """Check if a tool pack's capabilities are currently loaded into a given registry."""
        with self._lock:
            caps = self._pack_caps.get(pack_id)
            if not caps or not hasattr(registry, "get_capability"):
                return False
            return any(registry.get_capability(cap_name) is not None for cap_name in caps)

    def load_pack(
        self,
        pack_id: str,
        registry: Any,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Dynamically load a tool pack into a CapabilityRegistry.
        Registers the pack's capabilities, attaches any custom view factories,
        and fires the on_loaded lifecycle hook.
        """
        with self._lock:
            pack = self._packs.get(pack_id)
            if pack is None:
                logger.warning(f"PluginManager: Tool pack '{pack_id}' not found.")
                return False

            if self.is_pack_loaded(pack_id, registry):
                logger.debug(f"PluginManager: Tool pack '{pack_id}' is already loaded in registry.")
                return True

            try:
                capabilities = pack.create_capabilities(context=context)
                registered_cap_names: Set[str] = set()
                view_factories = pack.get_view_factories()

                for cap in capabilities:
                    if hasattr(registry, "register_capability"):
                        registry.register_capability(cap)
                        registered_cap_names.add(cap.name)

                        # Wire custom view factories to registered operations
                        if view_factories:
                            for op in cap.operations.values():
                                if op.artifact_kind in view_factories:
                                    op.view_factory = view_factories[op.artifact_kind]

                self._pack_caps.setdefault(pack_id, set()).update(registered_cap_names)
                pack.on_loaded(registry)
                self._notify_listeners(pack_id, "loaded")
                logger.info(
                    f"PluginManager: Successfully loaded tool pack '{pack_id}' "
                    f"({len(capabilities)} capabilities registered)."
                )
                return True
            except Exception as e:
                logger.error(f"PluginManager: Failed to load tool pack '{pack_id}': {e}", exc_info=True)
                return False

    def unload_pack(self, pack_id: str, registry: Any) -> bool:
        """
        Dynamically unload a tool pack from a CapabilityRegistry.
        Removes the pack's capabilities and operations, then fires the on_unloaded hook.
        """
        with self._lock:
            pack = self._packs.get(pack_id)
            if pack is None:
                return False

            cap_names = self._pack_caps.pop(pack_id, set())
            unregistered_any = False

            if hasattr(registry, "unregister_capability"):
                for cap_name in cap_names:
                    removed = registry.unregister_capability(cap_name)
                    if removed is not None:
                        unregistered_any = True

            pack.on_unloaded(registry)
            self._notify_listeners(pack_id, "unloaded")
            logger.info(f"PluginManager: Unloaded tool pack '{pack_id}'.")
            return unregistered_any

    def add_listener(self, callback: Callable[[str, str], None]) -> None:
        """Register a listener for pack load/unload events: callback(pack_id, event)."""
        with self._lock:
            self._listeners.append(callback)

    def _notify_listeners(self, pack_id: str, event: str) -> None:
        for cb in list(self._listeners):
            try:
                cb(pack_id, event)
            except Exception as e:
                logger.debug(f"PluginManager listener error: {e}")

    def register_builtins(self) -> None:
        """Register all default built-in domain vertical tool packs."""
        with self._lock:
            if not self._packs:
                from rat.plugins.packs.astrology import AstrologyToolPack
                from rat.plugins.packs.divination import DivinationToolPack
                from rat.plugins.packs.timetable import TimetableToolPack

                self.register_pack(AstrologyToolPack())
                self.register_pack(DivinationToolPack())
                self.register_pack(TimetableToolPack())


_DEFAULT_PLUGIN_MANAGER: Optional[PluginManager] = None
_INIT_LOCK = threading.Lock()


def get_plugin_manager() -> PluginManager:
    """Retrieve the global PluginManager singleton with built-ins pre-registered."""
    global _DEFAULT_PLUGIN_MANAGER
    if _DEFAULT_PLUGIN_MANAGER is None:
        with _INIT_LOCK:
            if _DEFAULT_PLUGIN_MANAGER is None:
                manager = PluginManager()
                manager.register_builtins()
                _DEFAULT_PLUGIN_MANAGER = manager
    return _DEFAULT_PLUGIN_MANAGER
