"""Native macOS application & file icon provider for QML via QFileIconProvider."""

from __future__ import annotations

import logging
import sys
import urllib.parse
from pathlib import Path
from typing import Dict, Optional, Tuple

from PyQt6.QtCore import QFileInfo, QSize
from PyQt6.QtGui import QColor, QPainter, QPixmap
from PyQt6.QtQuick import QQuickImageProvider
from PyQt6.QtWidgets import QApplication, QFileIconProvider

logger = logging.getLogger("rat.ui.icon_provider")


class RatIconProvider(QQuickImageProvider):
    """
    Supplies native macOS application and file icons to QML via `image://icon/<file_path>`.
    Utilizes system icon services (via QFileIconProvider) with high-res Retina scaling
    and an LRU in-memory cache.
    """

    def __init__(self, max_cache_entries: int = 256) -> None:
        super().__init__(QQuickImageProvider.ImageType.Pixmap)
        self._provider: Optional[QFileIconProvider] = None
        self._cache: Dict[Tuple[str, int, int], QPixmap] = {}
        self._max_cache = max_cache_entries

    def _get_provider(self) -> Optional[QFileIconProvider]:
        if self._provider is None:
            app = QApplication.instance()
            if app is not None and isinstance(app, QApplication):
                try:
                    self._provider = QFileIconProvider()
                except Exception as e:
                    logger.debug("Could not instantiate QFileIconProvider: %s", e)
        return self._provider

    def requestPixmap(self, id_str: str, requested_size: QSize) -> Tuple[QPixmap, QSize]:
        raw_path = urllib.parse.unquote(id_str or "")
        # Normalize macOS absolute paths
        if not raw_path.startswith("/") and sys.platform == "darwin":
            raw_path = "/" + raw_path

        p = Path(raw_path)
        w = requested_size.width() if requested_size is not None and requested_size.isValid() and requested_size.width() > 0 else 64
        h = requested_size.height() if requested_size is not None and requested_size.isValid() and requested_size.height() > 0 else 64
        cache_key = (str(p), w, h)

        if cache_key in self._cache:
            pix = self._cache[cache_key]
            return pix, pix.size()

        pix = self._load_icon_pixmap(p, QSize(w, h))

        if len(self._cache) >= self._max_cache:
            # Evict first inserted entry
            first_key = next(iter(self._cache))
            del self._cache[first_key]
        self._cache[cache_key] = pix

        return pix, pix.size()

    def _load_icon_pixmap(self, path: Path, target_size: QSize) -> QPixmap:
        # On macOS, prioritize AppKit NSWorkspace to extract the genuine 1024x1024 .icns icon
        if sys.platform == "darwin" and (path.suffix == ".app" or "Applications" in str(path)):
            try:
                from AppKit import NSBitmapImageRep, NSPNGFileType, NSWorkspace
                from PyQt6.QtCore import Qt
                ws = NSWorkspace.sharedWorkspace()
                ns_img = ws.iconForFile_(str(path))
                if ns_img is not None:
                    tiff = ns_img.TIFFRepresentation()
                    if tiff is not None:
                        rep = NSBitmapImageRep.imageRepWithData_(tiff)
                        png_data = rep.representationUsingType_properties_(NSPNGFileType, None)
                        if png_data:
                            pix = QPixmap()
                            if pix.loadFromData(bytes(png_data)) and not pix.isNull():
                                return pix.scaled(
                                    target_size,
                                    Qt.AspectRatioMode.KeepAspectRatio,
                                    Qt.TransformationMode.SmoothTransformation,
                                )
            except Exception as e:
                logger.debug("AppKit native icon extraction fallback: %s", e)

        try:
            if path.exists():
                provider = self._get_provider()
                if provider is not None:
                    icon = provider.icon(QFileInfo(str(path)))
                    if not icon.isNull():
                        pix = icon.pixmap(target_size)
                        if not pix.isNull():
                            return pix
        except Exception as e:
            logger.debug("Failed loading native icon for %s: %s", path, e)

        # Fallback pixmap if file missing or icon extraction unavailable
        fallback = QPixmap(target_size)
        fallback.fill(QColor(0, 0, 0, 0))
        painter = QPainter(fallback)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(82, 121, 70, 40))  # Accent tint
        painter.setPen(QColor(82, 121, 70, 180))
        painter.drawRoundedRect(2, 2, target_size.width() - 4, target_size.height() - 4, 6, 6)
        painter.end()
        return fallback

    _registered_instances: list[RatIconProvider] = []

    @classmethod
    def register(cls, engine, name: str = "icon") -> RatIconProvider:
        """Helper to register this provider on a QQmlEngine with reference pinning."""
        provider = cls()
        cls._registered_instances.append(provider)
        if hasattr(engine, "_icon_providers"):
            engine._icon_providers.append(provider)
        else:
            try:
                engine._icon_providers = [provider]
            except Exception:
                pass
        engine.addImageProvider(name, provider)
        return provider
