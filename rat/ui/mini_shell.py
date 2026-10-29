"""Transient presentation policy; never executes business tools or clears drafts."""
import logging
import os
import sys
from PyQt6.QtCore import QObject, QRect, QPoint, QTimer, Qt, QMetaObject, pyqtSignal
from PyQt6.QtGui import QGuiApplication, QRegion, QCursor
from rat.ui.mini_placement import Rect, place_panel, place_look, LOOK_WIDTH, LOOK_HEIGHT, MINI_PANEL_WIDTH

logger = logging.getLogger(__name__)


class MiniShell(QObject):
    nativeActivation = pyqtSignal(bool)
    outsidePointer = pyqtSignal(int, int)

    def __init__(self, view, root, controller):
        super().__init__(view)
        self.view, self.root, self.controller = view, root, controller
        area = view.screen().availableGeometry()
        self.home = (area.center().x()-290, area.bottom()-70)
        self.look_home = (area.right()-LOOK_WIDTH-16, area.bottom()-LOOK_HEIGHT-16)
        self.look_side = None
        self.side = None
        self.expanded = False
        self.expanded_top = None
        self._last_origin = (view.x(), view.y())
        self.fitting = self.animating = self.status_menu_open = False
        self.was_active = False
        self.look_keyboard_owned = False
        self.native_outside = False
        self._activation_observer = None
        self._outside_monitor = None
        self.nativeActivation.connect(self.native_activation_changed, Qt.ConnectionType.QueuedConnection)
        self.outsidePointer.connect(self.outside_pointer_pressed, Qt.ConnectionType.QueuedConnection)
        self.fit_timer = QTimer(self)
        self.fit_timer.setSingleShot(True)
        self.fit_timer.timeout.connect(self.fit)
        self.trim_timer = QTimer(self)
        self.trim_timer.setSingleShot(True)
        self.trim_timer.timeout.connect(self.finish_hop)
        self.dismiss_timer = QTimer(self)
        self.dismiss_timer.setSingleShot(True)
        self.dismiss_timer.timeout.connect(self.dismiss_if_outside)
        self.look_hide_timer = QTimer(self)
        self.look_hide_timer.setSingleShot(True)
        self.look_hide_timer.setInterval(5000)
        self.look_hide_timer.timeout.connect(self.hide_look_passively)
        self._look_hide_key = None
        root.preferredPanelHeightChanged.connect(self.schedule_fit)
        root.layoutExpandedChanged.connect(self.schedule_fit)
        root.workspaceModeChanged.connect(self.schedule_fit)
        root.lookActiveChanged.connect(self.look_policy_changed)
        root.lookBubbleWidthChanged.connect(self.schedule_fit)
        root.lookBubbleHeightChanged.connect(self.schedule_fit)
        root.cornerPanelWidthChanged.connect(self.schedule_fit)
        root.lookEngagedChanged.connect(self.update_look_timeout)
        root.panelRectChanged.connect(self.update_mask)
        root.mascotRectChanged.connect(self.update_mask)
        root.cornerInkBoundsChanged.connect(self.schedule_fit)
        root.cornerMouthChanged.connect(self.schedule_fit)
        root.focusOwnedChanged.connect(self.focus_changed)
        view.screenChanged.connect(self.schedule_fit)
        view.xChanged.connect(self.remember_home)
        view.yChanged.connect(self.remember_home)
        QGuiApplication.instance().applicationStateChanged.connect(self.focus_changed)
        view.activeChanged.connect(self.focus_changed)
        root.moveRequested.connect(view.startSystemMove)
        root.hideRequested.connect(self.dismiss)
        controller.hideRequested.connect(self.dismiss)
        controller.interactionCompleted.connect(self.complete_interaction)
        controller.presentRequested.connect(self.present)
        controller.engagementRequested.connect(self.present)
        controller.lookRequested.connect(self.present)
        controller.minimalRequested.connect(self.present)
        controller.lookFocusRequested.connect(self.focus_look)
        controller.lookResultDismissed.connect(self.dismiss_look_surface)
        controller.changed.connect(lambda: QTimer.singleShot(0, self.update_look_timeout))
        # Captures may complete after the user has moved on. Store the result;
        # only an explicit invocation is allowed to show/activate this window.
        controller.presentAtRequested.connect(lambda _point: logger.info('capture_result_retained'))
        if QGuiApplication.instance().platformName() == 'cocoa':
            from AppKit import NSWorkspace, NSWorkspaceDidActivateApplicationNotification, NSWorkspaceApplicationKey
            from Foundation import NSOperationQueue, NSBundle
            # Use this bundle's identity for same-app recall. A diagnostic or
            # future distribution identity must not be mistaken for another app.
            own_bundle_id = str(NSBundle.mainBundle().bundleIdentifier() or '') if getattr(sys, 'frozen', False) else ''
            self._workspace_center = NSWorkspace.sharedWorkspace().notificationCenter()
            def activated(notice):
                application = (notice.userInfo() or {}).get(NSWorkspaceApplicationKey)
                if application is not None:
                    # A second launch of our own bundle only recalls this
                    # instance; its short-lived PID must not count as switching
                    # to another application and immediately hide the recall.
                    own = (application.processIdentifier() == os.getpid()
                           or bool(own_bundle_id and str(application.bundleIdentifier() or '') == own_bundle_id))
                    self.nativeActivation.emit(own)
            self._activation_callback = activated
            self._activation_observer = self._workspace_center.addObserverForName_object_queue_usingBlock_(
                NSWorkspaceDidActivateApplicationNotification, None, NSOperationQueue.mainQueue(), activated)
            from AppKit import NSEvent, NSEventMaskLeftMouseDown, NSEventMaskRightMouseDown, NSEventMaskOtherMouseDown
            def outside_pressed(_event):
                if self.view.isVisible():
                    # Use Qt coordinates on every display. Do not retain the
                    # native event, input text or pointer position in diagnostics.
                    point = QCursor.pos()
                    self.outsidePointer.emit(point.x(), point.y())
            self._outside_callback = outside_pressed
            try:
                self._outside_monitor = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
                    NSEventMaskLeftMouseDown | NSEventMaskRightMouseDown | NSEventMaskOtherMouseDown,
                    outside_pressed)
            except Exception:
                logger.warning('mini_outside_click_monitor_unavailable')
            QGuiApplication.instance().aboutToQuit.connect(self.close)
        self.fit()

    def close(self):
        if self._outside_monitor is not None:
            from AppKit import NSEvent
            NSEvent.removeMonitor_(self._outside_monitor)
            self._outside_monitor = None
        if self._activation_observer is not None:
            self._workspace_center.removeObserver_(self._activation_observer)
            self._activation_observer = None

    def native_activation_changed(self, own):
        self.native_outside = not own
        if own:
            self.was_active = True
        logger.info('mini_app_activation own=%s', own)
        self.dismiss_timer.start(180)

    def schedule_fit(self, *_):
        if not self.fitting:
            self.fit_timer.start(0)

    def look_policy_changed(self, *_):
        # Passive Look can sit beside the reader. Mode changes set window level;
        # completion never calls show(), raise_() or requestActivate().
        was_active = self.view.isVisible() and self.view.isActive()
        self.view.setFlag(Qt.WindowType.WindowStaysOnTopHint, bool(self.root.property('lookActive')))
        # Some platforms hide a visible window when its flags change. Only
        # restore an already-active window during the user's navigation.
        if was_active and not self.view.isVisible():
            self.view.show()
            self.view.requestActivate()
        self.schedule_fit()

    def update_look_timeout(self, *_):
        if not self.view.isVisible() or not self.root.property('lookActive'):
            self.look_hide_timer.stop()
            return
        state = self.controller.snapshot
        if (state.get('lookSurface') != 'peek' or self.root.property('lookEngaged')
                or self.root.property('focusOwned') or self.status_menu_open):
            self.look_hide_timer.stop()
            return
        if not self.look_hide_timer.isActive():
            self.look_hide_timer.start()

    def hide_look_passively(self):
        if (not self.root.property('lookActive') or self.root.property('lookEngaged')
                or self.root.property('focusOwned') or self.status_menu_open
                or self.controller.snapshot.get('lookSurface') != 'peek'):
            return
        # Hide the entire overlay, preserving its source, result and watcher.
        self.controller.expireLookPeek()
        self.view.hide()

    def dismiss_look_surface(self):
        self.look_hide_timer.stop()
        self.view.hide()

    def complete_interaction(self):
        if self.root.property('lookActive'):
            self.controller.dismissLookResult()
        else:
            self.dismiss()

    def remember_home(self, *_):
        if not self.fitting and not self.animating and self.view.isVisible():
            origin = (self.view.x(), self.view.y())
            dx, dy = origin[0]-self._last_origin[0], origin[1]-self._last_origin[1]
            if self.corner_surface():
                self.look_home = (self.look_home[0]+dx, self.look_home[1]+dy)
            else:
                self.home = (self.home[0]+dx, self.home[1]+dy)
                if self.expanded_top is not None:
                    self.expanded_top += dy
            self._last_origin = origin

    def corner_surface(self):
        return bool(self.root.property('lookActive') or (
            self.controller.presentation.workspace_mode == 'minimal' and not self.root.property('auxiliary')))

    def fit(self):
        if self.animating:
            return
        self.fitting = True
        try:
            area = self.view.screen().availableGeometry()
            self.root.setProperty('maxPaperHeight', max(100, min(380, area.height()-240)))
            self.root.setProperty('maxCornerSpeechHeight', max(1, min(300, round(area.height()*0.38), area.height()-32)))
            self.root.setProperty('maxPanelHeight', max(160, area.height()-32))
            if self.corner_surface():
                looking = bool(self.root.property('lookActive'))
                previous_width = self.root.property('panelWidth')
                ink = self.root.property('cornerInkBounds')
                mouth = self.root.property('cornerMouth')
                placement = place_look(Rect(area.x(), area.y(), area.width(), area.height()),
                    self.look_home, self.root.property('lookBubbleWidth') if looking else self.root.property('cornerPanelWidth'),
                    self.root.property('lookBubbleHeight') if looking else self.root.property('preferredPanelHeight'), self.root.property('lookVariant'), self.look_side,
                    ink_bounds=Rect(round(ink.x()), round(ink.y()), round(ink.width()), round(ink.height())),
                    mouth=(mouth.x(), mouth.y()))
                self.look_side = placement.side
                self.root.setProperty('animatePlacement', False)
                bounds = placement.bounds
                self.view.setGeometry(bounds.x-4, bounds.y-4, bounds.width+8, bounds.height+8)
                self._last_origin = (self.view.x(), self.view.y())
                self.root.setProperty('panelX', placement.panel.x-self.view.x())
                self.root.setProperty('panelY', placement.panel.y-self.view.y())
                self.root.setProperty('panelWidth', placement.panel.width)
                self.root.setProperty('lookPlacedHeight', placement.panel.height)
                self.root.setProperty('ratX', placement.rat.x-self.view.x())
                self.root.setProperty('ratY', placement.rat.y-self.view.y())
                self.update_mask()
                # One follow-up allows text to rewrap after a width change;
                # a clamped preferred height must not create a resize loop.
                if round(previous_width) != placement.panel.width:
                    self.fit_timer.start(0)
                return
            expanded = bool(self.root.property('layoutExpanded'))
            if not expanded:
                self.expanded_top = None
            placement = place_panel(Rect(area.x(),area.y(),area.width(),area.height()), self.home,
                self.root.property('preferredPanelHeight'), expanded, self.side,
                panel_width=900 if self.controller.presentation.workspace_mode == 'full' else MINI_PANEL_WIDTH,
                paper_inset=0 if self.root.property('auxiliary') else round(self.root.property('paperOffset')),
                anchor_top=self.expanded_top if self.expanded else None)
            if expanded:
                self.expanded_top = placement.panel.y
            old = self.root.property('mascotRect')
            old_rat = Rect(self.view.x()+round(old.x()), self.view.y()+round(old.y()), round(old.width()), round(old.height()))
            hop = (self.view.isVisible() and not self.root.property('reduceMotion')
                   and (expanded != self.expanded or placement.side != self.side)
                   and area.contains(QRect(old_rat.x,old_rat.y,old_rat.width,old_rat.height)))
            bounds = placement.bounds.union(old_rat) if hop else placement.bounds
            self.side, self.expanded = placement.side, expanded
            self.root.setProperty('animatePlacement', False)
            self.view.setGeometry(bounds.x-4,bounds.y-4,bounds.width+8,bounds.height+8)
            self._last_origin = (self.view.x(), self.view.y())
            self.root.setProperty('panelX', placement.panel.x-self.view.x())
            self.root.setProperty('panelY', placement.panel.y-self.view.y())
            self.root.setProperty('panelWidth', placement.panel.width)
            self.root.setProperty('mascotOnRight', placement.side == 'right')
            target = (placement.rat.x-self.view.x(),placement.rat.y-self.view.y())
            self.root.setProperty('ratX', old_rat.x-self.view.x() if hop else target[0])
            self.root.setProperty('ratY', old_rat.y-self.view.y() if hop else target[1])
            if hop:
                self.animating = True
                def start_hop():
                    self.root.setProperty('animatePlacement', True)
                    self.root.setProperty('ratX', target[0])
                    self.root.setProperty('ratY', target[1])
                QTimer.singleShot(0, start_hop)
                self.trim_timer.start(220)
            self.update_mask()
        finally:
            self.fitting = False
        if not self.animating and round(self.root.property('preferredPanelHeight')) != placement.panel.height:
            # Width can change wrapping. Only schedule when the requested height
            # fits; a screen-height clamp must not create a resize loop.
            if self.root.property('preferredPanelHeight') < area.height()-32:
                self.fit_timer.start(0)

    def finish_hop(self):
        self.animating = False
        self.fit()

    def update_mask(self):
        if self.root.property('focusOwned'):
            region = QRegion(0,0,self.view.width(),self.view.height())
        else:
            panel, rat = self.root.property('panelRect'), self.root.property('mascotRect')
            region = QRegion(panel.toAlignedRect().adjusted(-2,-2,2,2)) | QRegion(rat.toAlignedRect())
        self.view.setMask(region)

    def focus_changed(self, *_):
        if self.view.isActive():
            self.was_active = True
        self.update_mask()
        self.dismiss_timer.start(180)
        self.update_look_timeout()

    def set_status_menu_open(self, opened):
        self.status_menu_open = opened
        self.focus_changed()

    def dismiss_if_outside(self):
        # App activation is not a pointer action: accessibility tools, Cmd+Tab
        # and system dialogs can change focus without the user dismissing RAT.
        # If a native monitor is unavailable, keep Close/Esc available rather
        # than silently falling back to the focus-loss behavior on macOS.
        if QGuiApplication.instance().platformName() == 'cocoa':
            return
        if self.root.property('lookActive') and (
                self.controller.snapshot.get('lookSurface') != 'reading' or not self.look_keyboard_owned):
            return
        if (self.view.isVisible() and not self.root.property('focusOwned')
                and not self.status_menu_open
                and (self.native_outside or (self.was_active and
                    (QGuiApplication.instance().applicationState() != Qt.ApplicationState.ApplicationActive
                     or not self.view.isActive())))):
            if self.root.property('lookActive'):
                self.controller.dismissLookResult()
            else:
                self.dismiss()

    def outside_pointer_pressed(self, x, y):
        if (not self.view.isVisible() or self.root.property('focusOwned')
                or self.status_menu_open):
            return
        point = self.view.mapFromGlobal(QPoint(x, y))
        mask = self.view.mask()
        if (mask.contains(point) if not mask.isEmpty() else
                QRect(0, 0, self.view.width(), self.view.height()).contains(point)):
            return
        if self.root.property('lookActive'):
            self.controller.dismissLookResult()
        else:
            self.dismiss()

    def dismiss(self):
        self.dismiss_timer.stop()
        self.look_hide_timer.stop()
        QMetaObject.invokeMethod(self.root, 'dismissTransient')
        self.controller.dismissLookResult()
        self.view.hide()
        logger.info('mini_dismissed; draft_and_result_retained')

    def present(self):
        self.dismiss_timer.stop()
        self.native_outside = False
        self.was_active = False
        self.look_keyboard_owned = False
        if not self.view.isVisible():
            QMetaObject.invokeMethod(self.root, 'beginCornerPresentation')
        if self.controller.presentation.workspace_mode == 'look':
            self.controller.prepareLookRecall()
        self.fit()
        QMetaObject.invokeMethod(self.root, 'restoreReader')
        self.view.show()
        self.view.raise_()
        if self.root.property('lookActive'):
            # Keep the reader active so the next Cmd+C still copies its selection.
            self.update_look_timeout()
            return
        if QGuiApplication.instance().platformName() == 'cocoa':
            # LSUIElement has no Dock activation path. Only this explicit user
            # invocation activates our app; background completion never does.
            from AppKit import NSApplication
            NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
        self.view.requestActivate()
        QMetaObject.invokeMethod(self.root, 'focusComposer')

    def focus_look(self):
        # A click on the passive mascot is an explicit request for keyboard
        # focus. Do not show a hidden window or activate on task completion.
        if not self.view.isVisible() or not self.root.property('lookActive'):
            return
        self.look_keyboard_owned = True
        if QGuiApplication.instance().platformName() == 'cocoa':
            from AppKit import NSApplication
            NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
        self.view.requestActivate()
        QMetaObject.invokeMethod(self.root, 'focusComposer')

    def toggle(self):
        if self.view.isVisible():
            self.dismiss()
        else:
            self.present()
