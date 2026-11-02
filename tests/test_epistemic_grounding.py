"""Tests for Epistemic Grounding & Source Binding (Turn 1).

Validates:
- SourceEvidence contract and immutable serialization.
- ExecutionRequest context snapshot pinning with SHA256.
- Backend input rendering with authoritative grounding evidence.
- Validation gate: rejection of missing grounding when requires_grounding is set.
- QuickPDFController activeContext chip and automated source evidence extraction.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import pytest

from rat.kernel.contracts import SourceEvidence
from rat.engine.execution import (
    ExecutionRequest,
    build_execution_context_snapshot,
    render_backend_input,
    validate_referenced_context,
)
from rat.ui.quick_pdf_controller import QuickPDFController
from rat.engine.selected_pdf import SelectedPDF


def test_source_evidence_contract():
    """Verify SourceEvidence dataclass serialization and integrity."""
    ev = SourceEvidence(
        source_id="src-101",
        kind="pdf_page",
        path="/docs/quyche.pdf",
        page_num=3,
        char_span=(120, 350),
        excerpt="Điều 14. Cảnh báo học vụ mức 2...",
        sha256="abc12345def67890",
        provenance={"title": "Quy chế Đào tạo 2026", "author": "TDTU"},
    )

    data = ev.to_dict()
    assert data["source_id"] == "src-101"
    assert data["kind"] == "pdf_page"
    assert data["page_num"] == 3
    assert data["char_span"] == [120, 350]
    assert data["sha256"] == "abc12345def67890"
    assert data["provenance"]["title"] == "Quy chế Đào tạo 2026"

    restored = SourceEvidence.from_dict(data)
    assert restored.source_id == ev.source_id
    assert restored.kind == ev.kind
    assert restored.page_num == ev.page_num
    assert restored.char_span == ev.char_span
    assert restored.excerpt == ev.excerpt
    assert restored.sha256 == ev.sha256
    assert restored.provenance == ev.provenance


def test_execution_snapshot_source_evidence_grounding():
    """Verify context snapshot includes source_evidence and hash pinning."""
    ev1 = {
        "source_id": "src-pdf-1",
        "kind": "pdf_page",
        "path": "/docs/test.pdf",
        "page_num": 5,
        "excerpt": "Binary search has O(log n) complexity.",
        "sha256": "4a5b6c7d8e9f",
    }
    context = {
        "source_evidence": [ev1],
        "requires_grounding": True,
    }

    snap = build_execution_context_snapshot(
        "Vì sao độ phức tạp là log n?",
        execution_id="exec-grounding-1",
        generation=1,
        context=context,
    )

    assert "snapshot_hash" in snap
    assert len(snap["source_evidence"]) == 1
    assert snap["source_evidence"][0]["source_id"] == "src-pdf-1"
    assert snap["requires_grounding"] is True

    # Validate that render_backend_input displays grounding section cleanly
    rendered = render_backend_input("Vì sao độ phức tạp là log n?", snap)
    assert "Authoritative Source Evidence (Grounding):" in rendered
    assert "[src-pdf-1]" in rendered
    assert "Page 5" in rendered
    assert "Binary search has O(log n) complexity." in rendered

    # Validate referenced context passes when grounding is supplied
    validate_referenced_context(snap)

    # Validate rejection when requires_grounding is True but evidence is missing
    empty_snap = build_execution_context_snapshot(
        "Query",
        context={"requires_grounding": True, "source_evidence": []},
    )
    with pytest.raises(ValueError, match="missing_grounding_evidence"):
        validate_referenced_context(empty_snap)


def test_controller_active_context_and_jump():
    """Verify QuickPDFController activeContext, clearActiveContext, and jumpToPdfPage."""
    from PyQt6.QtGui import QGuiApplication
    app = QGuiApplication.instance() or QGuiApplication([])

    controller = QuickPDFController(auto_init_finder=False)
    controller.ready()

    # Initially no active context
    assert controller.snapshot["activeContext"] is None

    # Simulate selecting a PDF
    fake_path = Path("/tmp/fake_document.pdf")
    controller._selection = SelectedPDF(fake_path, 15, (0, 0, 0, 0))
    controller._page = {"page": 3, "content": "Sample page 3 text"}

    snap = controller.snapshot
    assert snap["activeContext"] is not None
    assert snap["activeContext"]["type"] == "pdf"
    assert snap["activeContext"]["title"] == "fake_document.pdf"
    assert "Trang 3/15" in snap["activeContext"]["subtitle"]

    # Jump to page invokes readPage worker
    jumped = controller.jumpToPdfPage(7)
    assert jumped is True
    assert controller._request is not None
    assert controller._request.kind == "page"
    assert controller._request.args == (controller._selection, 7)

    # Clear active context
    controller.clearActiveContext()
    assert controller.snapshot["activeContext"] is None
    assert controller._selection is None

    controller.close()
