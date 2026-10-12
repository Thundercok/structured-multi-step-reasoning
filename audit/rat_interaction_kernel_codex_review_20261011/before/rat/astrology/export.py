"""Headless chart export utilities for SVG, PNG, and PDF.

Factored out from NatalChartWindow so exports work from headless contracts,
actions, and CLI without instantiating a feature QMainWindow.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

from rat.astrology.chart import NatalChart
from rat.astrology.svg import render_poster


def export_chart(
    chart: NatalChart,
    target_path: Union[str, Path],
    format: Optional[str] = None,
    *,
    show_aspects: bool = True,
    major_only: bool = True,
) -> Path:
    """Export calculated NatalChart to SVG, PNG, or PDF."""
    path = Path(target_path)
    fmt = (format or path.suffix.lstrip(".").lower()).lower()
    if fmt not in ("svg", "png", "pdf"):
        raise ValueError(f"Định dạng xuất không được hỗ trợ: {fmt}. Chọn svg, png hoặc pdf.")

    if not path.suffix or path.suffix.lower() != f".{fmt}":
        path = path.with_suffix(f".{fmt}")

    svg_content = render_poster(chart, show_aspects=show_aspects, major_only=major_only)

    if fmt == "svg":
        path.write_text(svg_content, encoding="utf-8")
        return path

    # PNG and PDF rasterization/vector printing via Qt SVG renderer
    try:
        from PyQt6.QtCore import QByteArray, QRectF, QSizeF
        from PyQt6.QtGui import QColor, QImage, QPainter, QPdfWriter, QPageSize
        from PyQt6.QtSvg import QSvgRenderer
    except ImportError as exc:
        raise RuntimeError(f"Xuất sang {fmt.upper()} yêu cầu PyQt6 và QtSvg: {exc}")

    renderer = QSvgRenderer(QByteArray(svg_content.encode("utf-8")))
    if not renderer.isValid():
        raise RuntimeError("Nội dung SVG không hợp lệ để kết xuất.")

    path.parent.mkdir(parents=True, exist_ok=True)

    if fmt == "png":
        image = QImage(2000, 2660, QImage.Format.Format_ARGB32)
        image.fill(QColor("#fcfaf6"))
        painter = QPainter(image)
        try:
            renderer.render(painter, QRectF(0, 0, 2000, 2660))
        finally:
            painter.end()
        if not image.save(str(path)):
            raise OSError(f"Không thể lưu tệp hình ảnh tại {path}")
        return path

    if fmt == "pdf":
        writer = QPdfWriter(str(path))
        writer.setPageSize(QPageSize(QSizeF(200, 266), QPageSize.Unit.Millimeter))
        title = f"{chart.birth.name} · Lá số" if hasattr(chart, "birth") else "Lá số chiêm tinh"
        writer.setTitle(title)
        painter = QPainter(writer)
        if not painter.isActive():
            raise OSError(f"Không thể khởi tạo PDF writer cho {path}")
        try:
            renderer.render(painter, QRectF(0, 0, writer.width(), writer.height()))
        finally:
            painter.end()
        return path

    return path
