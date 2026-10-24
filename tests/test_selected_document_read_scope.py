"""Exact selected-file permission; actual reads, no model or UI responses."""
import pytest

from rat.crawler.db import Database
from rat.engine.assistant_runtime import AssistantRuntime
from rat.timetable.compositor import TimetableCompositor


def test_selected_read_grant_is_exact_transient_and_does_not_index(tmp_path):
    selected = tmp_path / "selected.txt"
    other = tmp_path / "other.txt"
    selected.write_text("Read this explicitly selected document.")
    other.write_text("Another document requires its own selection.")
    db = Database(str(tmp_path / "index.db"))
    runtime = AssistantRuntime(db=db, compositor=TimetableCompositor([]), use_live_model=False)
    try:
        args = {"file_path": str(selected), "max_chars": 3000}
        with pytest.raises(ValueError, match="chỉ mục RAT"):
            runtime.execute_tool("read_document", args)
        result = runtime.execute_tool("read_document", args,
                                      selected_document_path=str(selected))
        assert result["found"] and result["content"] == selected.read_text()
        with pytest.raises(ValueError, match="chỉ mục RAT"):
            runtime.execute_tool("read_document", {"file_path": str(other)},
                                 selected_document_path=str(selected))
        with pytest.raises(ValueError, match="chỉ mục RAT"):
            runtime.execute_tool("read_document", args)
        assert db.get_document_by_path(str(selected)) is None
    finally:
        runtime.close()
