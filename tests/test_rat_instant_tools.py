"""Test suite for RAT instant tools: Kinh Dịch, Lenormand, Web Reader, and Timetable."""

import pytest
from unittest.mock import patch, MagicMock
from rat.engine.divination import cast_iching, draw_lenormand, HEXAGRAMS_64
from rat.engine.web_reader import extract_url, fetch_web_summary


def test_cast_iching():
    res = cast_iching("Hỏi về công việc sắp tới")
    assert res["visual_type"] == "iching"
    assert "hexagram_name" in res
    assert len(res["lines"]) == 6
    assert all(b in (0, 1) for b in res["lines"])
    assert res["meaning"] != ""
    assert res["advice"] != ""
    assert "Thượng:" in res["upper_trigram"] or "Càn" in res["upper_trigram"] or "(" in res["upper_trigram"]


def test_draw_lenormand():
    res = draw_lenormand("Hỏi về tình hình dự án", count=3)
    assert res["visual_type"] == "lenormand"
    assert len(res["cards"]) == 3
    for c in res["cards"]:
        assert "slot" in c
        assert "icon" in c
        assert "name" in c
        assert "meaning" in c
    assert "summary" in res


def test_extract_url():
    assert extract_url("xem https://vnexpress.net/thoi-su ngay") == "https://vnexpress.net/thoi-su"
    assert extract_url("khong co link") is None
    assert extract_url("http://example.org/test?a=1&b=2") == "http://example.org/test?a=1&b=2"


def test_fetch_web_summary_mocked():
    sample_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Tin Tức Công Nghệ 2026</title>
        <meta name="description" content="Khám phá các tiến bộ đột phá trong trí tuệ nhân tạo và mô hình ngôn ngữ nhỏ.">
    </head>
    <body>
        <h1>Tiêu đề chính</h1>
        <p>Các nhà nghiên cứu vừa công bố kỹ thuật can thiệp mô hình giúp suy luận từng bước rõ ràng hơn.</p>
        <p>Hệ thống hoạt động trực tiếp trên thiết bị cá nhân mà không phụ thuộc vào máy chủ đám mây.</p>
    </body>
    </html>
    """
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.read.return_value = sample_html.encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        res = fetch_web_summary("https://tech-news.vn/article/123")
        assert res["visual_type"] == "web"
        assert res["title"] == "Tin Tức Công Nghệ 2026"
        assert res["domain"] == "tech-news.vn"
        assert len(res["bullets"]) >= 1
        assert "tiến bộ đột phá" in res["summary"]


def test_controller_instant_dispatch():
    from PyQt6.QtGui import QGuiApplication
    _app = QGuiApplication.instance() or QGuiApplication([])
    from rat.ui.quick_pdf_controller import QuickPDFController
    from rat.engine.assistant_runtime import AssistantRuntime

    runtime = AssistantRuntime()
    ctrl = QuickPDFController(assistant_runtime=runtime)
    ctrl.ready()

    # 1. Kinh Dịch
    handled = ctrl.submit("gieo quẻ kinh dịch hôm nay")
    assert handled is True
    snap = ctrl.snapshot
    assert snap["view"] == "answer"
    assert snap["artifactCard"] is not None
    assert snap["artifactCard"]["visual_type"] == "iching"
    assert "Kinh Dịch" in snap["answerText"]

    # 2. Lenormand
    handled = ctrl.submit("rút 3 lá bài lenormand")
    assert handled is True
    snap = ctrl.snapshot
    assert snap["artifactCard"]["visual_type"] == "lenormand"
    assert "Lenormand" in snap["answerText"]

    # 3. Timetable
    handled = ctrl.submit("thời khóa biểu thứ hai")
    assert handled is True
    snap = ctrl.snapshot
    assert snap["artifactCard"]["visual_type"] == "timetable"
    assert "Thời khóa biểu" in snap["answerText"]

    # 4. Web Reader (mocked)
    with patch("rat.engine.web_reader.fetch_web_summary") as mock_fetch:
        mock_fetch.return_value = {
            "visual_type": "web",
            "url": "https://example.com/demo",
            "domain": "example.com",
            "title": "Trang Mẫu",
            "summary": "• Nội dung mẫu",
            "bullets": ["Nội dung mẫu"],
            "status": "success",
            "error_message": "",
        }
        handled = ctrl.submit("xem https://example.com/demo")
        assert handled is True
        snap = ctrl.snapshot
        assert snap["artifactCard"]["visual_type"] == "web"
        assert "example.com" in snap["answerText"]

    ctrl.close()
