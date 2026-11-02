"""
rat.kernel — Shared interaction kernel for RAT.

Implements:
- Shared capability & operation contracts
- Input requests for natural language and direct user input
- Versioned, typed artifacts with revision history
- Action dispatching with stale revision and ambiguity detection
- Declarative versioned presentation system (ViewSpec, ViewProvider)
"""
from __future__ import annotations

from rat.kernel.contracts import (
    Artifact,
    ArtifactAction,
    ArtifactStore,
    DispatchResult,
    ExecutionEvent,
    ExecutionState,
    InputRequest,
)
from rat.kernel.dispatcher import (
    ActionDispatcher,
    AmbiguousArtifactError,
    StaleRevisionError,
)
from rat.kernel.registry import (
    Capability,
    CapabilityRegistry,
    OperationDefinition,
)
from rat.kernel.view_spec import (
    StandardViewProvider,
    ViewBlock,
    ViewProvider,
    ViewSpec,
    validate_view_spec,
)
def build_core_registry(*args, **kwargs):
    from rat.kernel.capabilities import build_core_registry as build
    return build(*args, **kwargs)


def build_default_registry(*args, **kwargs):
    from rat.kernel.capabilities import build_default_registry as build
    return build(*args, **kwargs)

__all__ = [
    "Artifact",
    "ArtifactAction",
    "ArtifactStore",
    "DispatchResult",
    "ExecutionEvent",
    "ExecutionState",
    "InputRequest",
    "ActionDispatcher",
    "AmbiguousArtifactError",
    "StaleRevisionError",
    "Capability",
    "CapabilityRegistry",
    "OperationDefinition",
    "ViewBlock",
    "ViewProvider",
    "ViewSpec",
    "StandardViewProvider",
    "validate_view_spec",
    "build_core_registry",
    "build_default_registry",
]
