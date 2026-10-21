"""Follow-up coverage for the same parser/provenance contracts; no real model."""
from fractions import Fraction
import json
import os
from pathlib import Path

import pytest
from reasoning_strategies import extract_answer

HERE = Path(__file__).resolve().parent


@pytest.fixture
def session_artifacts_root():
    # Later repairs select fresh output while the captured failing evidence stays immutable.
    return Path(os.environ.get("RAT_REVIEW_R4_OUTPUT_DIR") or HERE)


@pytest.mark.parametrize("raw,expected", [
    ("Therefore x = 3/4", Fraction(3, 4)),
    ("x = 3.25/4", Fraction(13, 16)),
    ("Answer: x = 3/4", Fraction(3, 4)),
    ("x = 3/4", Fraction(3, 4)),
], ids=["conclusion-cue-fallback", "decimal-numerator-fallback", "answer-marker-control", "bare-equation-control"])
def test_fallback_and_marker_paths_preserve_fraction_value(raw, expected):
    parsed = extract_answer(raw)
    conclusion = parsed.rsplit("=", 1)[-1].strip()
    if "/" in conclusion:
        numerator, denominator = conclusion.split("/", 1)
        actual = Fraction(numerator.strip()) / Fraction(denominator.strip())
    else:
        actual = Fraction(conclusion)
    assert actual == expected, {"raw": raw, "parsed": parsed}


@pytest.mark.parametrize("folder,expected_new_fake", [
    ("fake_session", 1), ("locked_ledger_replay", 0),
], ids=["fresh-fake-control", "budget-halt-on-real-history"])
def test_cli_mode_does_not_relabel_historical_calls(folder, expected_new_fake, session_artifacts_root):
    perf = json.loads((session_artifacts_root / folder / "native_performance.json").read_text())
    if folder == "locked_ledger_replay":
        original = (HERE / "received_artifacts/calls.jsonl").read_bytes()
        assert (session_artifacts_root / folder / "calls.jsonl").read_bytes() == original
    assert perf["fake_model_calls_executed"] == expected_new_fake, perf["scope_classification"]


def test_same_directory_copy_labels_fit_hosted_420px_viewport():
    from PyQt6.QtWidgets import QApplication, QPushButton, QStyle, QStyleOptionButton, QVBoxLayout, QWidget
    from PyQt6.QtTest import QTest
    from rat.kernel.contracts import Artifact
    from rat.kernel.view_spec import StandardViewProvider
    from rat.ui.view_renderer import QtViewRenderer

    app = QApplication.instance() or QApplication([])
    host = QWidget()
    host.setFixedWidth(420)
    layout = QVBoxLayout(host)
    layout.setContentsMargins(0, 0, 0, 0)
    paths = ("/Applications/League of Legends.app", "/Applications/League of Legends copy.app")
    choices = [dict(name="League of Legends", path=p, bundle_id="com.fixture.league", version="1.0") for p in paths]
    art = Artifact("hosted-review", "input_request", payload=dict(operation_name="open_application",
        missing_fields=[], candidate_choices=choices, supplied_inputs={"name":"Liên Minh"}, prompt="Choose installation"))
    ren = QtViewRenderer(StandardViewProvider().provide_view(art), art, parent=host)
    layout.addWidget(ren)
    host.show()
    for _ in range(5):
        app.processEvents()
        QTest.qWait(10)
    try:
        assert host.width() == 420 and ren.width() == 420
        buttons = [b for b in ren.findChildren(QPushButton) if b.objectName() == "CandidateBtn"]
        assert len(buttons) == 2 and len({b.text() for b in buttons}) == 2
        data=[]
        for b in buttons:
            option=QStyleOptionButton(); b.initStyleOption(option)
            rect=b.style().subElementRect(QStyle.SubElement.SE_PushButtonContents,option,b)
            data.append(dict(text=b.text(),content_width=rect.width(),text_width=b.fontMetrics().horizontalAdvance(b.text())))
            assert b.isVisible() and b.fontMetrics().horizontalAdvance(b.text()) <= rect.width(), data
        (HERE / "hosted_candidate_geometry.json").write_text(json.dumps(data,indent=2)+"\n")
        host.grab().save(str(HERE / "hosted_candidate_labels_420.png"))
    finally:
        host.close();host.deleteLater();app.processEvents()
