"""Explicit macOS selection capture. Never reads/writes Clipboard or sends keys."""
import os
import sys
import math


def read_selected_text(source_pid=None, should_cancel=lambda: False, on_geometry=None):
    if sys.platform != 'darwin':
        raise ValueError('selection_unavailable: Chức năng này cần macOS.')
    from AppKit import NSWorkspace
    from ApplicationServices import (AXIsProcessTrusted, AXUIElementCreateApplication,
        AXUIElementCopyAttributeValue, AXUIElementSetMessagingTimeout)
    if not AXIsProcessTrusted():
        raise ValueError('selection_accessibility_required: Cấp quyền Trợ năng cho RAT rồi bấm lại phím tắt.')

    def front_pid():
        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        return int(app.processIdentifier()) if app else None

    pid = front_pid() if source_pid is None else source_pid
    if type(pid) is not int or pid <= 0 or pid == os.getpid() or front_pid() != pid:
        raise ValueError('selection_source_changed: Bôi đen chữ trong app nguồn rồi bấm lại phím tắt.')

    def get(element, name):
        if should_cancel():
            raise ValueError('cancelled:selection')
        AXUIElementSetMessagingTimeout(element, 0.3)
        code, value = AXUIElementCopyAttributeValue(element, name, None)
        return value if code == 0 else None

    application = AXUIElementCreateApplication(pid)
    element = get(application, 'AXFocusedUIElement')
    # Some browsers expose selected text on the focused element's web-area
    # ancestor. Keep traversal bounded and read no whole-field AXValue.
    for _ in range(4):
        if element is None:
            break
        role = get(element, 'AXRole')
        subrole = get(element, 'AXSubrole')
        if 'AXSecureTextField' in (role, subrole):
            raise ValueError('selection_unavailable: Không đọc trường mật khẩu.')
        text = get(element, 'AXSelectedText')
        if isinstance(text, str) and text.strip():
            if should_cancel():
                raise ValueError('cancelled:selection')
            if front_pid() != pid:
                raise ValueError('selection_source_changed: App nguồn đã đổi. Bôi đen và gọi lại RAT.')
            if len(text) > 8000:
                raise ValueError('snippet_too_long: Hãy chọn đoạn dưới 8.000 ký tự.')
            if callable(on_geometry):
                # Optional, transient view context. Never read a whole-field
                # value or pretend its frame is the selected text's bounds.
                try:
                    from ApplicationServices import AXUIElementCopyParameterizedAttributeValue, AXValueGetValue, kAXValueCGRectType
                    from AppKit import NSScreen
                    import Quartz
                    selected_range = get(element, 'AXSelectedTextRange')
                    code, bounds = AXUIElementCopyParameterizedAttributeValue(element, 'AXBoundsForRange', selected_range, None) if selected_range else (-1, None)
                    okay, rect = AXValueGetValue(bounds, kAXValueCGRectType, None) if code == 0 else (False, None)
                    if okay and front_pid() == pid and not should_cancel():
                        values = (float(rect.origin.x), float(rect.origin.y), float(rect.size.width), float(rect.size.height))
                        if all(math.isfinite(v) for v in values) and values[2] > 0 and values[3] > 0:
                            cx, cy = values[0]+values[2]/2, values[1]+values[3]/2
                            for screen in NSScreen.screens():
                                display = Quartz.CGDisplayBounds(int(screen.deviceDescription()['NSScreenNumber']))
                                if display.origin.x <= cx < display.origin.x+display.size.width and display.origin.y <= cy < display.origin.y+display.size.height:
                                    on_geometry(dict(rect=values, display=(display.origin.x, display.origin.y, display.size.width, display.size.height), display_name=str(screen.localizedName()),
                                        logical_display=(screen.frame().origin.x, NSScreen.screens()[0].frame().size.height-screen.frame().origin.y-screen.frame().size.height, screen.frame().size.width, screen.frame().size.height)))
                                    break
                except Exception:
                    pass  # Geometry failure never loses a valid text capture.
            return text
        element = get(element, 'AXParent')
    raise ValueError('selection_unavailable: App này chưa cung cấp chữ đang chọn. Bạn có thể dán chữ hoặc chọn vùng ảnh.')
