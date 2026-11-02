"""
rat.plugins.manifest — Specifications and contracts for dynamic domain tool packs.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class ToolPackState(str, Enum):
    UNLOADED = "unloaded"
    LOADED = "loaded"
    ERROR = "error"


@dataclass
class ToolPackManifest:
    """Metadata describing a modular domain tool pack."""

    id: str
    name: str
    description: str
    version: str = "1.0.0"
    category: str = "vertical"  # "vertical" | "domain" | "utility"
    author: str = "RAT Team"
    enabled_by_default: bool = False
    dependencies: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)


class ToolPack(ABC):
    """Abstract base class for dynamic domain plugins / tool packs."""

    manifest: ToolPackManifest

    @abstractmethod
    def create_capabilities(self, context: Optional[Dict[str, Any]] = None) -> List[Any]:
        """Return list of Capability instances to be registered into CapabilityRegistry."""
        ...

    def get_view_factories(self) -> Dict[str, Callable]:
        """Return mapping of artifact_kind -> view_factory callable for UI projections."""
        return {}

    def get_ui_cards(self) -> List[Dict[str, Any]]:
        """Return optional QtQuick desk card specifications contributed by this pack."""
        return []

    def on_loaded(self, registry: Any) -> None:
        """Lifecycle hook invoked immediately after capabilities are registered."""
        pass

    def on_unloaded(self, registry: Any) -> None:
        """Lifecycle hook invoked immediately after capabilities are unregistered."""
        pass
