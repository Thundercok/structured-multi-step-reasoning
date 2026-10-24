"""On-demand cropped PDF match snapshots for the Qt Quick desk.

Renders only explicitly selected local PDFs on the GUI thread via PyQt6.QtPdf,
cropping tightly around matched text rectangles with warm under-glyph highlights.
Engine and headless research modules never import this file.
"""
from __future__ import annotations

import base64
from collections import OrderedDict
from pathlib import Path
import re
import unicodedata

from rat.engine.book_pages import normalized

try:
    from PyQt6.QtCore import QBuffer, QIODevice, QRectF, QSize, Qt
    from PyQt6.QtGui import QColor, QImage, QPainter, QPen
    from PyQt6.QtPdf import QPdfDocument, QPdfSearchModel
    _QT_PDF_AVAILABLE = True
except Exception:  # pragma: no cover - graceful fallback when QtPdf is absent
    _QT_PDF_AVAILABLE = False


def _candidate_phrases_and_words(query: str, snippet: str) -> tuple[list[str], list[str]]:
    """Build surface-form phrase and word candidates, recovering accents from snippet."""
    phrases: list[str] = []
    words: list[str] = []
    seen_phrases: set[str] = set()
    seen_words: set[str] = set()

    def add_phrase(value: str) -> None:
        cleaned = " ".join(value.split()).strip()
        key = cleaned.casefold()
        if len(cleaned) >= 2 and key not in seen_phrases:
            seen_phrases.add(key)
            phrases.append(cleaned)

    def add_word(value: str) -> None:
        cleaned = value.strip()
        key = cleaned.casefold()
        if len(cleaned) >= 2 and key not in seen_words:
            seen_words.add(key)
            words.append(cleaned)

    norm_snippet = unicodedata.normalize("NFC", snippet or "")
    snippet_tokens = [
        (m.group(), normalized(m.group()), m.start(), m.end())
        for m in re.finditer(r"[^\W_]+", norm_snippet)
    ]

    q_clean = (query or "").strip()
    if q_clean:
        q_norm_tokens = re.findall(r"[^\W_]+", normalized(q_clean))
        if q_norm_tokens and snippet_tokens:
            n_q = len(q_norm_tokens)
            for idx in range(len(snippet_tokens) - n_q + 1):
                window = snippet_tokens[idx : idx + n_q]
                if [item[1] for item in window] == q_norm_tokens:
                    span = norm_snippet[window[0][2] : window[-1][3]]
                    if "\n" not in span and len(span) <= 120:
                        # Prefer exact surface casing/accents from extracted PDF text first.
                        add_phrase(span)
            q_set = set(q_norm_tokens)
            for surface, norm_tok, _, _ in snippet_tokens:
                if norm_tok in q_set:
                    add_word(surface)
        add_phrase(q_clean)
        for raw_tok in re.findall(r"[^\W_]+", q_clean):
            add_word(raw_tok)
    elif snippet_tokens:
        # Citation preview without an explicit search query: anchor on opening snippet words.
        head = [tok[0] for tok in snippet_tokens[:5] if len(tok[0]) >= 2]
        if len(head) >= 2:
            add_phrase(" ".join(head[:4]))
        for surface, _, _, _ in sorted(snippet_tokens[:12], key=lambda item: -len(item[0]))[:3]:
            if len(surface) >= 4:
                add_word(surface)

    return phrases, words


def _select_anchor_band(rects: list[QRectF], page_height: float) -> tuple[float, float, list[QRectF]]:
    """Choose the densest vertical cluster of match boxes and return (top, bottom, visible_rects)."""
    if not rects:
        top = min(22.0, page_height * 0.03)
        bottom = min(page_height, top + min(136.0, page_height * 0.22))
        if bottom - top < 48.0:
            top, bottom = 0.0, page_height
        return top, bottom, []

    ordered = sorted(rects, key=lambda r: (r.top(), r.left()))
    best_cluster: list[QRectF] = []
    for anchor in ordered:
        band_top = anchor.top() - 8.0
        band_bottom = anchor.top() + 88.0
        cluster = [r for r in ordered if r.bottom() >= band_top and r.top() <= band_bottom]
        if len(cluster) > len(best_cluster):
            best_cluster = cluster

    min_y = min(r.top() for r in best_cluster)
    max_y = max(r.bottom() for r in best_cluster)
    pad_top = 42.0
    pad_bottom = 46.0
    crop_top = max(0.0, min_y - pad_top)
    crop_bottom = min(page_height, max_y + pad_bottom)

    # Enforce comfortable reading band [106pt, 166pt] around the matched lines.
    min_band = min(106.0, page_height)
    max_band = min(166.0, page_height)
    current_h = crop_bottom - crop_top
    if current_h < min_band:
        extra = (min_band - current_h) / 2.0
        crop_top = max(0.0, crop_top - extra)
        crop_bottom = min(page_height, crop_bottom + extra)
        if crop_bottom - crop_top < min_band:
            if crop_top == 0.0:
                crop_bottom = min(page_height, min_band)
            else:
                crop_top = max(0.0, page_height - min_band)
    elif current_h > max_band:
        center = (min_y + max_y) / 2.0
        crop_top = max(0.0, min(page_height - max_band, center - max_band / 2.0))
        crop_bottom = min(page_height, crop_top + max_band)

    visible = [
        r for r in ordered
        if r.bottom() >= crop_top + 1.0 and r.top() <= crop_bottom - 1.0
    ]
    return crop_top, crop_bottom, visible


class PdfSnapshotRenderer:
    """Bounded LRU cache of QPdfDocument handles and rendered PNG data URLs."""

    def __init__(self, *, max_docs: int = 4, max_snaps: int = 48):
        self._max_docs = max_docs
        self._max_snaps = max_snaps
        self._docs: OrderedDict[tuple[str, int], tuple[QPdfDocument, QPdfSearchModel]] = OrderedDict()
        self._snaps: OrderedDict[tuple[str, int, int, str, str, int], str] = OrderedDict()

    def close(self) -> None:
        while self._docs:
            _, (doc, _) = self._docs.popitem(last=False)
            try:
                doc.close()
                doc.deleteLater()
            except Exception:
                pass
        self._snaps.clear()

    def _evict_stale_path(self, resolved_path: str, current_mtime_ns: int) -> None:
        stale_doc_keys = [k for k in self._docs if k[0] == resolved_path and k[1] != current_mtime_ns]
        for key in stale_doc_keys:
            entry = self._docs.pop(key, None)
            if entry is not None:
                doc, _ = entry
                try:
                    doc.close()
                    doc.deleteLater()
                except Exception:
                    pass
        stale_snap_keys = [k for k in self._snaps if k[0] == resolved_path and k[1] != current_mtime_ns]
        for key in stale_snap_keys:
            self._snaps.pop(key, None)

    def _get_document(self, resolved_path: str, mtime_ns: int):
        key = (resolved_path, mtime_ns)
        if key in self._docs:
            self._docs.move_to_end(key)
            return self._docs[key]

        self._evict_stale_path(resolved_path, mtime_ns)
        doc = QPdfDocument(None)
        err = doc.load(resolved_path)
        if err != QPdfDocument.Error.None_ or doc.status() != QPdfDocument.Status.Ready or doc.pageCount() < 1:
            try:
                doc.close()
                doc.deleteLater()
            except Exception:
                pass
            return None

        search_model = QPdfSearchModel(doc)
        search_model.setDocument(doc)
        self._docs[key] = (doc, search_model)
        while len(self._docs) > self._max_docs:
            _, (oldest, _) = self._docs.popitem(last=False)
            try:
                oldest.close()
                oldest.deleteLater()
            except Exception:
                pass
        return doc, search_model

    def _locate_rects(self, model, page_index: int, query: str, snippet: str) -> list[QRectF]:
        phrases, words = _candidate_phrases_and_words(query, snippet)
        if not phrases and not words:
            return []

        collected: list[QRectF] = []
        for phrase in phrases:
            model.setSearchString(phrase)
            for link in model.resultsOnPage(page_index):
                for rect in link.rectangles():
                    if rect.width() > 0.5 and rect.height() > 0.5:
                        collected.append(QRectF(rect))
            if collected:
                return collected

        for word in words[:6]:
            model.setSearchString(word)
            for link in model.resultsOnPage(page_index):
                for rect in link.rectangles():
                    if rect.width() > 0.5 and rect.height() > 0.5:
                        collected.append(QRectF(rect))
        return collected

    def render_data_url(
        self,
        path: str | Path,
        page: int,
        query: str = "",
        snippet: str = "",
        *,
        width: int = 1040,
    ) -> str:
        if not _QT_PDF_AVAILABLE or not path or type(page) is not int or page < 1:
            return ""
        try:
            resolved = Path(path).expanduser().resolve(strict=True)
            stat = resolved.stat()
        except (OSError, RuntimeError, ValueError):
            return ""
        if resolved.suffix.casefold() != ".pdf" or not resolved.is_file():
            return ""

        resolved_str = str(resolved)
        mtime_ns = stat.st_mtime_ns
        q_key = (query or "").strip()[:120]
        s_key = (snippet or "").strip()[:180]
        snap_key = (resolved_str, mtime_ns, page, q_key, s_key, int(width))
        if snap_key in self._snaps:
            self._snaps.move_to_end(snap_key)
            return self._snaps[snap_key]

        entry = self._get_document(resolved_str, mtime_ns)
        if entry is None:
            return ""
        doc, search_model = entry
        if page > doc.pageCount():
            return ""

        page_index = page - 1
        pt_size = doc.pagePointSize(page_index)
        pt_w, pt_h = float(pt_size.width()), float(pt_size.height())
        if pt_w <= 2.0 or pt_h <= 2.0:
            return ""

        rects = self._locate_rects(search_model, page_index, query, snippet)
        crop_top, crop_bottom, visible_rects = _select_anchor_band(rects, pt_h)

        margin_x = min(24.0, pt_w * 0.04)
        crop_left = margin_x
        crop_right = max(crop_left + 40.0, pt_w - margin_x)
        if visible_rects:
            crop_left = max(0.0, min(crop_left, min(r.left() for r in visible_rects) - 10.0))
            crop_right = min(pt_w, max(crop_right, max(r.right() for r in visible_rects) + 10.0))

        crop_w = max(40.0, crop_right - crop_left)
        crop_h = max(40.0, crop_bottom - crop_top)
        scale = max(1.5, min(2.6, float(width) / crop_w))

        render_w = max(64, round(pt_w * scale))
        render_h = max(64, round(pt_h * scale))
        raw_page = doc.render(page_index, QSize(render_w, render_h))
        if raw_page.isNull():
            return ""

        px_x = max(0, min(render_w - 1, round(crop_left * scale)))
        px_y = max(0, min(render_h - 1, round(crop_top * scale)))
        px_w = max(1, min(render_w - px_x, round(crop_w * scale)))
        px_h = max(1, min(render_h - px_y, round(crop_h * scale)))
        slice_img = raw_page.copy(px_x, px_y, px_w, px_h)
        if slice_img.isNull():
            return ""

        canvas = QImage(px_w, px_h, QImage.Format.Format_RGB32)
        canvas.fill(QColor("#fdfdf9"))

        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        if visible_rects:
            fill_color = QColor(250, 216, 94, 145)
            border_pen = QPen(QColor(214, 164, 34, 155), max(1.0, 0.7 * scale))
            painter.setPen(border_pen)
            painter.setBrush(fill_color)
            min_hy = float(px_h)
            max_hy = 0.0
            for rect in visible_rects:
                hx = (rect.left() - crop_left) * scale - 2.5 * scale
                hy = (rect.top() - crop_top) * scale - 1.5 * scale
                hw = rect.width() * scale + 5.0 * scale
                hh = rect.height() * scale + 3.0 * scale
                min_hy = min(min_hy, hy)
                max_hy = max(max_hy, hy + hh)
                painter.drawRoundedRect(QRectF(hx, hy, hw, hh), 3.5 * scale / 2.0, 3.5 * scale / 2.0)

            # Left sage callout bar marking the matched vertical span
            bar_w = max(4.0, round(2.6 * scale))
            bar_top = max(6.0, min_hy - 3.0 * scale)
            bar_bottom = min(float(px_h) - 6.0, max(bar_top + 16.0 * scale, max_hy + 3.0 * scale))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#4f6740"))
            painter.drawRoundedRect(QRectF(0.0, bar_top, bar_w, max(12.0, bar_bottom - bar_top)), bar_w / 2.0, bar_w / 2.0)

        painter.drawImage(0, 0, slice_img)
        painter.end()

        buf = QBuffer()
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        if not canvas.save(buf, "PNG"):
            return ""
        encoded = base64.b64encode(bytes(buf.data())).decode("ascii")
        data_url = f"data:image/png;base64,{encoded}"

        self._snaps[snap_key] = data_url
        while len(self._snaps) > self._max_snaps:
            self._snaps.popitem(last=False)
        return data_url
