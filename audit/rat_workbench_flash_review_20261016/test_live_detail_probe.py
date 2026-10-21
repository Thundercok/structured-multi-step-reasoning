"""Run the supplied detail regression with the scene turn actually active."""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location(
    "workbench_review_original", ROOT / "tests/test_workbench_scene.py"
)
original = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = original
spec.loader.exec_module(original)

app = original.app
scene_window = original.scene_window


def test_supplied_detail_regression_with_active_scene_turn(scene_window, monkeypatch):
    win = scene_window
    original_begin = win._conversation.begin_turn

    def begin_scene_turn(query, *args, **kwargs):
        turn = original_begin(query, *args, **kwargs)
        win.workbench_scene.begin_turn(
            query,
            generation=win._chat_generation,
            execution_id=turn.execution_id,
            turn_id=turn.turn_ref.turn_id,
            artifact_store=win.assistant_runtime.artifact_store,
        )
        return turn

    monkeypatch.setattr(win._conversation, "begin_turn", begin_scene_turn)
    original.test_detail_view_state_preserved_during_unrelated_progress(win)
