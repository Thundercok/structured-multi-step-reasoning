"""Native macOS status menu for a QGuiApplication; no QtWidgets dependency.

QAction remains the headless action model. AppKit owns the OS menu surface;
application windows are Qt Quick. Offscreen tests only construct the model.
"""
from __future__ import annotations

from enum import IntEnum
import logging
import sys

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QAction, QGuiApplication

logger = logging.getLogger(__name__)


class NativeMenu(QObject):
    aboutToShow = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._actions = []

    def addAction(self, action):
        self._actions.append(action)
        return action

    def addSeparator(self):
        action = QAction(self)
        action.setSeparator(True)
        return self.addAction(action)

    def actions(self):
        return list(self._actions)


class NativeStatusItem(QObject):
    activated = pyqtSignal(object)
    notification = pyqtSignal(str, str)
    menuVisibilityChanged = pyqtSignal(bool)

    class MessageIcon(IntEnum):
        Information = 1

    class ActivationReason(IntEnum):
        Trigger = 1

    def __init__(self):
        super().__init__()
        self._menu = None
        self._status = None
        self._target = None
        self._tooltip = ''
        self._native_actions = []
        self._primary_action = None
        self._native_menu = None

    def setPrimaryAction(self, callback):
        """Opt-in single left click; existing RAT status menus stay unchanged."""
        self._primary_action = callback

    def setContextMenu(self, menu):
        self._menu = menu

    def contextMenu(self):
        return self._menu

    def setToolTip(self, text):
        self._tooltip = text
        if self._status is not None:
            self._status.button().setToolTip_(text)

    def showMessage(self, title, message, icon=None, duration=0):
        # Keep a persistent fallback when the OS suppresses notifications.
        self.setToolTip(f'{title}\n{message}')
        self.notification.emit(title, message)
        logger.info('%s: %s', title, message)
        if self._status is not None:
            try:
                from Foundation import NSUserNotification, NSUserNotificationCenter
                notice = NSUserNotification.alloc().init()
                notice.setTitle_(title)
                notice.setInformativeText_(message)
                NSUserNotificationCenter.defaultUserNotificationCenter().deliverNotification_(notice)
            except Exception as exc:
                logger.debug('Native notification unavailable; retained in status tooltip: %s', exc)

    def show(self):
        app = QGuiApplication.instance()
        if app is None:
            raise RuntimeError('NativeStatusItem requires QGuiApplication')
        if app.platformName() == 'offscreen' or self._status is not None:
            return
        if sys.platform != 'darwin':
            logger.warning('Native status menu is available on macOS; use the Qt Quick Desk on this platform.')
            return
        from AppKit import NSImage, NSMenu, NSMenuItem, NSObject, NSStatusBar, NSVariableStatusItemLength
        import objc

        # One Objective-C class per process; owner is held by this item.
        global _TARGET_CLASS
        if _TARGET_CLASS is None:
            class RATStatusMenuTarget(NSObject):
                @objc.IBAction
                def statusClicked_(self, sender):
                    from AppKit import NSApplication, NSEventTypeRightMouseUp
                    owner = self.owner
                    event = NSApplication.sharedApplication().currentEvent()
                    if event is not None and event.type() == NSEventTypeRightMouseUp:
                        owner._status.popUpStatusItemMenu_(owner._native_menu)
                    elif owner._primary_action is not None:
                        owner._primary_action()

                @objc.IBAction
                def invoke_(self, sender):
                    owner = self.owner
                    index = sender.tag()
                    actions = owner._menu.actions()
                    if 0 <= index < len(actions):
                        action = actions[index]
                        if action.isEnabled() and action.isVisible():
                            action.trigger()

                def menuNeedsUpdate_(self, menu):
                    self.owner._menu.aboutToShow.emit()
                    self.owner._rebuild_menu(menu)

                def menuWillOpen_(self, menu):
                    self.owner.menuVisibilityChanged.emit(True)

                def menuDidClose_(self, menu):
                    self.owner.menuVisibilityChanged.emit(False)

            _TARGET_CLASS = RATStatusMenuTarget

        self._target = _TARGET_CLASS.alloc().init()
        self._target.owner = self
        self._status = NSStatusBar.systemStatusBar().statusItemWithLength_(NSVariableStatusItemLength)
        button = self._status.button()
        image = NSImage.imageWithSystemSymbolName_accessibilityDescription_('magnifyingglass', 'RAT Desk')
        if image is not None:
            image.setTemplate_(True)
            button.setImage_(image)
        else:
            button.setTitle_('RAT')
        button.setToolTip_(self._tooltip)
        menu = NSMenu.alloc().initWithTitle_('RAT')
        menu.setAutoenablesItems_(False)
        menu.setDelegate_(self._target)
        self._rebuild_menu(menu)
        self._native_menu = menu
        if self._primary_action is None:
            self._status.setMenu_(menu)
        else:
            from AppKit import NSEventMaskLeftMouseUp, NSEventMaskRightMouseUp
            button.setTarget_(self._target)
            button.setAction_('statusClicked:')
            button.sendActionOn_(NSEventMaskLeftMouseUp | NSEventMaskRightMouseUp)

    def _rebuild_menu(self, menu):
        from AppKit import NSMenuItem
        menu.removeAllItems()
        self._native_actions = []
        self._native_menu = menu
        for index, action in enumerate(self._menu.actions()):
            if not action.isVisible():
                continue
            if action.isSeparator():
                menu.addItem_(NSMenuItem.separatorItem())
                continue
            item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(action.text(), 'invoke:', '')
            item.setTarget_(self._target)
            item.setTag_(index)
            item.setEnabled_(action.isEnabled())
            item.setState_(1 if action.isCheckable() and action.isChecked() else 0)
            menu.addItem_(item)
            self._native_actions.append(item)

    def hide(self):
        if self._status is not None:
            from AppKit import NSStatusBar
            self._status.setMenu_(None)
            NSStatusBar.systemStatusBar().removeStatusItem_(self._status)
            self._status = None
        if self._target is not None:
            self._target.owner = None
            self._target = None
        self._native_actions = []
        self._native_menu = None


_TARGET_CLASS = None
