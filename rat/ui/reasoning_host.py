"""Explicit composition of an existing engine into the RAT conversation host.

No provider discovery, model loading, or policy approval occurs here.
"""
from __future__ import annotations


def install_reasoning_engine(app, engine, *, allow_synthetic_policy=False):
    from reasoning.bundle import validate_policy_bundle

    controller = getattr(engine, "_controller", None)
    if controller is None or controller.bundle is None:
        raise ValueError("reasoning_policy_unavailable")
    report = validate_policy_bundle(controller.bundle, controller.policy, controller.backend,
                                    allow_synthetic=allow_synthetic_policy)
    # Validate before publishing any property; failed configuration keeps the old host.
    app.setProperty("ratReasoningEngine", engine)
    app.setProperty("ratAllowSyntheticPolicy", allow_synthetic_policy is True)
    app.setProperty("ratReasoningConversation", True)
    return report
