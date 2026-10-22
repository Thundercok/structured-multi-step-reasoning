#!/usr/bin/env python3
"""Capture high-resolution screenshots and video of RAT's unified Qt Quick Desk."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

from PIL import Image
from PyQt6.QtCore import QCoreApplication, QEvent, QPoint, QPointF, QTimer, QUrl, Qt
from PyQt6.QtGui import QFont, QGuiApplication
from PyQt6.QtQuick import QQuickItem, QQuickView
from PyQt6.QtTest import QTest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from rat.ui.chat_session import ConversationHistory
from rat.engine.assistant_runtime import AssistantRuntime
from rat.engine.app_resolver import Application, ApplicationCatalog
from rat.engine.progressive_search import ProgressiveSearch
from rat.kernel.contracts import Artifact
from rat.ui.quick_pdf_controller import QuickPDFController
from rat.ui.quick_app import bind_desk_window
from reasoning.bundle import create_synthetic_specimen_bundle
from rat.engine.meta_reasoner import build_composed_meta_reasoner
from tests.test_selected_pdf import write_pdf


import numpy as np


class ShowcaseBackend:
    hidden_size = 2

    def __init__(self):
        self.run_calls = []
        self.answer_text = ""

    def embed(self, query: str):
        return np.zeros(self.hidden_size, dtype=np.float32)

    def run(self, strategy, query: str, should_cancel=None, deadline_monotonic=None, max_tokens=None):
        self.run_calls.append(query)
        return self.answer_text, 0.95, 12


def wait_until(predicate, timeout=5):
    end = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= end:
            raise TimeoutError("Timed out waiting for predicate in showcase")
        QTest.qWait(15)
    QTest.qWait(25)


def click_quick_item(view, root, object_name):
    item = root.findChild(QQuickItem, object_name)
    if item is None:
        pending = list(root.childItems())
        while pending:
            candidate = pending.pop()
            if candidate.objectName() == object_name:
                item = candidate
                break
            pending.extend(candidate.childItems())
    if item is None or not item.isVisible():
        raise RuntimeError(f"Item {object_name} not found or hidden")
    point = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
    QTest.mouseClick(view, Qt.MouseButton.LeftButton, pos=QPoint(round(point.x()), round(point.y())))
    QTest.qWait(30)


def build_showcase(output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    tmp_scratch = output_dir / "tmp_data"
    tmp_scratch.mkdir(parents=True, exist_ok=True)

    app = QGuiApplication.instance() or QGuiApplication([sys.argv[0]])
    app.setApplicationName("RAT Showcase")
    if sys.platform == "darwin":
        app.setFont(QFont("Helvetica Neue", 13))

    backend = ShowcaseBackend()
    bundle, policy = create_synthetic_specimen_bundle(hidden_size=2)
    engine = build_composed_meta_reasoner(bundle, backend, policy, allow_synthetic=True)

    runtime = AssistantRuntime()
    conversation = ConversationHistory()

    # Pre-populate catalog with realistic macOS apps for display
    catalog = ApplicationCatalog([
        Application("app-terminal", "/System/Applications/Utilities/Terminal.app", "Terminal", "com.apple.Terminal", "2.14", names=("terminal", "shell", "bash", "zsh")),
        Application("app-safari", "/Applications/Safari.app", "Safari", "com.apple.Safari", "17.4", names=("safari", "browser", "web")),
        Application("app-code", "/Applications/Visual Studio Code.app", "Visual Studio Code", "com.microsoft.VSCode", "1.95", names=("code", "vscode", "editor")),
    ])

    controller = QuickPDFController(
        assistant_runtime=runtime,
        conversation=conversation,
        reasoning_engine=engine,
        allow_synthetic_policy=True,
        finder_catalog=catalog,
    )
    controller.ready()

    view = QQuickView()
    view.setColor(Qt.GlobalColor.transparent)
    view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
    view.setInitialProperties({
        "liveController": controller,
        "reduceMotion": True,
        "mascotSource": QUrl.fromLocalFile(str(PROJECT / "rat/assets/rat_mascot_cutout.png")),
    })
    view.setSource(QUrl.fromLocalFile(str(PROJECT / "rat/ui/quick/PDFDesk.qml")))
    root = view.rootObject()
    view.resize(700, 680)
    resize_timer = bind_desk_window(view)
    view.show()
    QTest.qWait(100)

    frames = []

    def save_frame(filename: str, label: str):
        path = output_dir / filename
        QCoreApplication.processEvents()
        QTest.qWait(50)
        img = view.grabWindow()
        img.save(str(path))
        print(f"✓ Saved {filename}: {label} ({img.width()}x{img.height()})")
        frames.append(path)
        return path

    editor = root.findChild(QQuickItem, "draftEditor")

    # --- Scene 1: Idle Desk ---
    save_frame("01_idle_desk.png", "Giao diện bàn làm việc ban đầu (sẵn sàng tìm kiếm & hỏi đáp)")

    # --- Scene 2: Progressive Finder - App Search ---
    editor.setProperty("text", "Terminal")
    wait_until(lambda: controller.snapshot["view"] == "finder" and len(controller.snapshot["finderHits"]) > 0)
    root.setProperty("selectedFinderIndex", 0)
    QTest.qWait(60)
    save_frame("02_finder_apps.png", "Progressive Finder - Gõ 'Terminal', phân nhóm ỨNG DỤNG và Thanh hành động đáy")

    # --- Scene 3: Progressive Finder - File & PDF ---
    pdf_sample = tmp_scratch / "Quy_che_hoc_vu_2026.pdf"
    write_pdf(pdf_sample, ["Quy che hoc vu Ton Duc Thang 2026. Toi da 24 tin chi hoc ky chinh. Binary search uses log n comparisons."])
    # Inject a simulated hit into finder with section headers
    controller._finder_hits = [
        {"resource_id": "pdf-1", "kind": "file", "title": "Quy_che_hoc_vu_2026.pdf", "path": str(pdf_sample), "origin": "lexical_index", "snippet": "...Tối đa 24 tín chỉ học kỳ chính...", "is_pdf": True, "bundle_id": "", "is_first_of_section": True, "section_title": "TÀI LIỆU & TỆP"},
        {"resource_id": "doc-2", "kind": "file", "title": "Bao_cao_NCKH_2026.docx", "path": "/Users/thundercock2/Documents/Bao_cao_NCKH_2026.docx", "origin": "lexical_index", "snippet": "...Nghiên cứu suy luận đa bước CoT...", "is_pdf": False, "bundle_id": "", "is_first_of_section": False, "section_title": "TÀI LIỆU & TỆP"},
    ]
    controller._view = "finder"
    controller._status = "Tìm thấy 2 kết quả cho 'Quy chế'"
    controller.changed.emit()
    editor.setProperty("text", "Quy chế")
    root.setProperty("selectedFinderIndex", 0)
    QTest.qWait(60)
    save_frame("03_finder_files.png", "Progressive Finder - Gõ 'Quy chế', phân nhóm TÀI LIỆU & TỆP và Bottom Action Bar")

    # --- Scene 3b: Smart AI Query Card ---
    controller._finder_hits = []
    controller._view = "finder"
    controller._status = "Sẵn sàng gửi câu hỏi suy luận"
    controller.changed.emit()
    editor.setProperty("text", "Sao phải dùng mid + 1 trong Binary Search?")
    QTest.qWait(60)
    save_frame("03b_smart_ai_card.png", "Spotlight AI Card - Tự động phát hiện câu hỏi tự nhiên và gợi ý suy luận CoT")

    # --- Scene 3c: Active Context Chip ---
    from rat.engine.selected_pdf import SelectedPDF
    controller._selection = SelectedPDF(pdf_sample, 15, (0, 0, 0, 0))
    controller._page = {"page": 1, "content": "Quy che hoc vu"}
    controller._view = "none"
    controller._finder_hits = []
    controller.changed.emit()
    editor.setProperty("text", "Quy định cảnh báo học vụ thế nào?")
    root.setProperty("selectedFinderIndex", -1)
    QTest.qWait(60)
    save_frame("03c_context_chip.png", "Composer Context Chip - Neo ngữ cảnh tài liệu Quy_che_hoc_vu_2026.pdf")
    controller.clearActiveContext()

    # --- Scene 4: Multi-Turn Reasoning - Turn 1 (DSA Concept) ---
    q1 = "Giải thích binary search bằng ví dụ nhỏ, chưa đưa code vội."
    backend.answer_text = (
        "Binary Search (Tìm kiếm nhị phân) hoạt động bằng cách chia đôi không gian tìm kiếm trên mảng đã sắp xếp:\n\n"
        "1. Xác định hai biên: left = 0, right = n - 1.\n"
        "2. Tính chỉ số chính giữa: mid = left + (right - left) // 2.\n"
        "3. So sánh phần tử tại mid với mục tiêu: nếu bằng thì dừng, nếu nhỏ hơn thì thu hẹp sang nửa phải (mid + 1), nếu lớn hơn thì thu sang nửa trái (mid - 1).\n\n"
        "Độ phức tạp thời gian đạt O(log n), tối ưu vượt trội so với tìm kiếm tuần tự O(n)."
    )
    editor.setProperty("text", q1)
    controller.submit(q1)
    wait_until(lambda: not controller.snapshot["busy"])
    save_frame("04_reasoning_step1.png", "Lượt 1 - Trợ lý giải thích khái niệm Binary Search trên thẻ làm việc")

    # --- Scene 5: Multi-Turn Context Retention - Turn 2 & 3 ---
    art_store = controller.assistant_runtime.artifact_store
    art_v1 = Artifact(
        id="art-dsa-search",
        kind="dsa_search",
        revision=1,
        payload={"array": [2, 4, 6, 8, 10], "target": 8, "result_index": 3},
        inputs={"array": [2, 4, 6, 8, 10], "target": 8},
        provenance={"owner_turn_id": "turn-2"},
        title="Mảng [2, 4, 6, 8, 10] tìm 8",
    )
    art_store.put(art_v1)
    q2 = "Dùng mảng [2, 4, 6, 8, 10], tìm 8."
    backend.answer_text = (
        "Thực hiện tìm kiếm 8 trên mảng [2, 4, 6, 8, 10]:\n"
        "• Bước 1: left=0, right=4 => mid=2. Giá trị a[2]=6 < 8 => loại bỏ nửa trái, đặt left = mid + 1 = 3.\n"
        "• Bước 2: left=3, right=4 => mid=3. Giá trị a[3]=8 == 8 => Tìm thấy tại chỉ số 3!\n"
        "Số bước so sánh: 2 lần."
    )
    editor.setProperty("text", q2)
    controller.submit(q2)
    wait_until(lambda: not controller.snapshot["busy"])

    turn_2_snap = controller.conversation.get_turn("turn-2")
    if turn_2_snap:
        turn_2_snap.artifact_refs = [art_v1.to_dict()]
        controller.conversation._turn_snapshots["turn-2"] = turn_2_snap

    q3 = "Sao phải dùng mid + 1?"
    backend.answer_text = (
        "Ta phải dùng `mid + 1` vì hai lý do cốt lõi trong ví dụ tìm 8 vừa rồi:\n\n"
        "1. Loại trừ chắc chắn: Ta đã kiểm tra phần tử `a[mid]` (tại mid=2, giá trị là 6) và biết rõ 6 < 8. Vì mảng đã sắp xếp tăng dần, mọi phần tử từ index 0 đến mid đều nhỏ hơn 8, không cần xét lại.\n"
        "2. Đảm bảo tiến trình & chống lặp vô tận: Nếu chỉ gán `left = mid`, khi khoảng thu hẹp còn 2 phần tử (ví dụ left=3, right=4, phép chia nguyên cho mid=3), vòng lặp sẽ bị kẹt mãi mãi tại left=3 mà không thể tiến lên."
    )
    editor.setProperty("text", q3)
    controller.submit(q3)
    wait_until(lambda: not controller.snapshot["busy"])
    save_frame("05_reasoning_turn3_midplus1.png", "Lượt 3 - Tham chiếu ngữ cảnh lượt 2 giải thích 'Sao phải dùng mid + 1?'")

    # --- Scene 6: Optimistic Revisioning - Turn 4 ---
    q4 = "Đổi sang tìm 6 nhé."
    backend.answer_text = (
        "Đã cập nhật mục tiêu mới: tìm 6 trên cùng mảng [2, 4, 6, 8, 10]:\n"
        "• Bước 1: left=0, right=4 => mid=2. Phần tử a[2]=6 == 6 => Trùng khớp ngay bước đầu tiên tại index 2!\n"
        "• Tạo bản sửa đổi mới Revision v2 trong ArtifactStore, không ghi đè dữ kiện lịch sử của Turn 2."
    )
    editor.setProperty("text", q4)
    controller.submit(q4, target_turn_id="turn-2", target_artifact_id="art-dsa-search", target_revision=1)
    wait_until(lambda: not controller.snapshot["busy"])
    art_v2 = Artifact(
        id="art-dsa-search",
        kind="dsa_search",
        revision=2,
        payload={"array": [2, 4, 6, 8, 10], "target": 6, "result_index": 2},
        inputs={"array": [2, 4, 6, 8, 10], "target": 6},
        provenance={"owner_turn_id": "turn-4"},
        title="Mảng [2, 4, 6, 8, 10] tìm 6",
    )
    controller.commit_artifact(art_v2, expected_revision=1)
    save_frame("06_artifact_revision_turn4.png", "Lượt 4 - Đổi sang tìm 6, cam kết Revision v2 bằng Optimistic Locking")

    # --- Scene 7: History Lookback without Dispatch ---
    editor.setProperty("text", "Soạn câu hỏi dở dang...")
    controller.navigateToTurn("turn-3")
    QTest.qWait(50)
    save_frame("07_history_lookback.png", "Điều hướng xem lại Turn 3 trong lịch sử: bảo toàn câu hỏi đang soạn dở")

    # --- Scene 8: PDF Document Desk Mode ---
    controller.selectFile(str(pdf_sample))
    wait_until(lambda: not controller.snapshot["busy"])
    controller.search("tin chi")
    wait_until(lambda: not controller.snapshot["busy"])
    controller.readPage(1)
    wait_until(lambda: controller.snapshot["view"] == "page")
    save_frame("08_pdf_reader_mode.png", "Chế độ đọc PDF: tìm kiếm từ khóa, trích dẫn số trang và điều khiển phân trang")

    resize_timer.stop()
    controller.close()
    view.close()

    # --- Assemble Animated GIF ---
    print("\n⏳ Assembling animated GIF...")
    pil_images = [Image.open(f) for f in frames]
    gif_path = output_dir / "rat_quick_showcase.gif"
    pil_images[0].save(
        gif_path,
        save_all=True,
        append_images=pil_images[1:],
        duration=2500,  # 2.5s per scene
        loop=0,
    )
    print(f"✓ Saved Animated GIF: {gif_path} ({gif_path.stat().st_size // 1024} KB)")

    # --- Assemble MP4 Video via ffmpeg ---
    mp4_path = output_dir / "rat_quick_showcase.mp4"
    ffmpeg_bin = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
    if Path(ffmpeg_bin).exists():
        print("⏳ Encoding MP4 video via ffmpeg...")
        # Create a concat list for ffmpeg with 2.5s duration each
        concat_txt = output_dir / "concat_list.txt"
        with open(concat_txt, "w") as f:
            for fpath in frames:
                f.write(f"file '{fpath.resolve()}'\nduration 2.5\n")
            f.write(f"file '{frames[-1].resolve()}'\n")

        cmd = [
            ffmpeg_bin,
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_txt),
            "-vf", "fps=25,format=yuv420p,scale=trunc(iw/2)*2:trunc(ih/2)*2",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            str(mp4_path),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            print(f"✓ Saved MP4 Video: {mp4_path} ({mp4_path.stat().st_size // 1024} KB)")
        else:
            print(f"⚠️ ffmpeg encoding warning: {res.stderr}")
        if concat_txt.exists():
            concat_txt.unlink()

    return frames, gif_path, mp4_path


if __name__ == "__main__":
    dest = PROJECT / "docs/screencaps"
    if len(sys.argv) > 1:
        dest = Path(sys.argv[1])
    build_showcase(dest)
