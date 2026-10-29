"""Explicit macOS selection capture. Never reads/writes Clipboard or sends keys."""
import os
import sys


def read_selected_text(source_pid=None, should_cancel=lambda: False):
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
            return text
        element = get(element, 'AXParent')
    raise ValueError('selection_unavailable: App này chưa cung cấp chữ đang chọn. Bạn có thể dán chữ hoặc chọn vùng ảnh.')
