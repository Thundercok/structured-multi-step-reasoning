"""Transient presentation policy; never executes business tools or clears drafts."""
import logging
import os
import sys
from PyQt6.QtCore import QObject, QRect, QPoint, QTimer, Qt, QMetaObject, pyqtSignal
from PyQt6.QtGui import QGuiApplication, QRegion, QCursor
from rat.ui.mini_placement import Rect, place_panel, place_look, LOOK_WIDTH, LOOK_HEIGHT, MINI_PANEL_WIDTH
from rat.ui.selection_placement import map_selection, choose_selection_home

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
        self.corner_home = self.look_home
        self.selection_anchored = False
        self.task_anchors = {}
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
        root.compactChanged.connect(self.schedule_fit)
        root.lookActiveChanged.connect(self.look_policy_changed)
        root.preferredPanelWidthChanged.connect(self.schedule_fit)
        root.lookEngagedChanged.connect(self.update_look_timeout)
        root.panelRectChanged.connect(self.update_mask)
        root.mascotRectChanged.connect(self.update_mask)
        root.cornerInkBoundsChanged.connect(self.schedule_fit)
        root.cornerMouthChanged.connect(self.schedule_fit)
        root.floatingHeadChanged.connect(self.schedule_fit)
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
        controller.selectionAnchorRequested.connect(self.place_selection)
        controller.restoreAnchorRequested.connect(self.restore_anchor)
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
        # One window policy across compact/expanded; no flag churn on navigation.
        self.schedule_fit()

    def update_look_timeout(self, *_):
        if not self.view.isVisible() or not self.root.property('lookActive'):
            self.look_hide_timer.stop()
            return
        state = self.controller.snapshot
        if (state.get('pinned') or state.get('lookSurface') != 'peek' or self.root.property('lookEngaged')
                or self.root.property('focusOwned') or self.status_menu_open):
            self.look_hide_timer.stop()
            return
        if not self.look_hide_timer.isActive():
            self.look_hide_timer.start()

    def hide_look_passively(self):
        if (self.controller.snapshot.get('pinned') or not self.root.property('lookActive') or self.root.property('lookEngaged')
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
            self.controller.collapseBubble()
        else:
            self.dismiss()

    def remember_home(self, *_):
        if not self.fitting and not self.animating and self.view.isVisible():
            origin = (self.view.x(), self.view.y())
            dx, dy = origin[0]-self._last_origin[0], origin[1]-self._last_origin[1]
            if self.corner_surface():
                self.look_home = (self.look_home[0]+dx, self.look_home[1]+dy)
                if not self.selection_anchored:
                    self.corner_home = self.look_home
            else:
                self.home = (self.home[0]+dx, self.home[1]+dy)
                if self.expanded_top is not None:
                    self.expanded_top += dy
            self.task_anchors[self.controller.presentation.task_id] = (self.look_home,self.look_side,self.view.screen().name())
            self._last_origin = origin

    def corner_surface(self):
        return True

    def restore_anchor(self, task_id):
        saved = self.task_anchors.get(task_id)
        if saved:
            self.look_home, self.look_side, screen_name = saved
            matches = [screen for screen in QGuiApplication.screens() if screen.name()==screen_name]
            if len(matches)==1:
                self.view.setScreen(matches[0])
            self.selection_anchored = True
        else:
            self.look_home, self.look_side = self.corner_home, None
            self.selection_anchored = False
        self.schedule_fit()

    def place_selection(self, context):
        screens=QGuiApplication.screens()
        matches=[screen for screen in screens if screen.name()==context.get('display_name')]
        if len(matches) != 1 and context.get('logical_display'):
            native = context['logical_display']
            matches = [s for s in screens if all(abs(a-b)<2 for a,b in zip(
                (s.geometry().x(),s.geometry().y(),s.geometry().width(),s.geometry().height()), native))]
        screen=matches[0] if len(matches)==1 else screens[0] if len(screens)==1 else None
        self.selection_anchored=False
        if screen is not None:
            geometry=screen.geometry()
            rect=map_selection(context,Rect(geometry.x(),geometry.y(),geometry.width(),geometry.height()))
            if rect is not None:
                area=screen.availableGeometry()
                self.look_home,self.look_side=choose_selection_home(Rect(area.x(),area.y(),area.width(),area.height()),
                    rect,self.root.property('preferredPanelWidth'),self.root.property('preferredPanelHeight'))
                self.selection_anchored=True
                self.view.setScreen(screen)
        if not self.selection_anchored:
            self.look_home=self.corner_home
        self.task_anchors[self.controller.presentation.task_id] = (self.look_home,self.look_side,self.view.screen().name())
        while len(self.task_anchors)>6:
            del self.task_anchors[next(iter(self.task_anchors))]
        self.schedule_fit()

    def fit(self):
        if self.fitting:
            return
        self.fitting = True
        try:
            area = self.view.screen().availableGeometry()
            self.root.setProperty('maxPaperHeight', max(1, min(380, area.height()-120)))
            self.root.setProperty('maxCornerSpeechHeight', max(1, min(300, round(area.height()*0.38), area.height()-32)))
            self.root.setProperty('maxPanelHeight', max(1, area.height()-32))
            previous_width = self.root.property('panelWidth')
            mouth = self.root.property('cornerMouth')
            placement = place_look(Rect(area.x(), area.y(), area.width(), area.height()),
                self.look_home, self.root.property('preferredPanelWidth'),
                self.root.property('preferredPanelHeight'), side=self.look_side,
                mouth=(mouth.x(), mouth.y()), floating_head=True)
            self.look_side = placement.side
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
            if round(previous_width) != placement.panel.width:
                self.fit_timer.start(0)
        finally:
            self.fitting = False

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
        if self.controller.snapshot.get('pinned'):
            return
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
        if self.controller.snapshot.get('pinned'):
            return
        if (not self.view.isVisible() or self.root.property('focusOwned')
                or self.status_menu_open):
            return
        point = self.view.mapFromGlobal(QPoint(x, y))
        mask = self.view.mask()
        if (mask.contains(point) if not mask.isEmpty() else
                QRect(0, 0, self.view.width(), self.view.height()).contains(point)):
            return
        if self.root.property('lookActive'):
            self.controller.collapseBubble()
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
        if self.root.property('lookActive'):
            self.controller.prepareLookRecall()
        self.fit()
        QMetaObject.invokeMethod(self.root, 'restoreReader')
        self.view.show()
        if self.view.isVisible():
            self.controller.selectionPresented()
        self.view.raise_()
        if self.root.property('lookActive') and not self.root.property('composing'):
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
