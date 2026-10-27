"""Transient presentation policy; never executes business tools or clears drafts."""
import logging
import os
from PyQt6.QtCore import QObject, QRect, QTimer, Qt, QMetaObject, pyqtSignal
from PyQt6.QtGui import QGuiApplication, QRegion
from rat.ui.mini_placement import Rect, place_panel, place_look

logger = logging.getLogger(__name__)


class MiniShell(QObject):
    nativeActivation = pyqtSignal(bool)

    def __init__(self, view, root, controller):
        super().__init__(view)
        self.view, self.root, self.controller = view, root, controller
        area = view.screen().availableGeometry()
        self.home = (area.center().x()-290, area.bottom()-70)
        self.look_home = (area.right()-122-16, area.center().y()-64)
        self.side = None
        self.expanded = False
        self.expanded_top = None
        self._last_origin = (view.x(), view.y())
        self.fitting = self.animating = self.status_menu_open = False
        self.was_active = False
        self.native_outside = False
        self._activation_observer = None
        self.nativeActivation.connect(self.native_activation_changed, Qt.ConnectionType.QueuedConnection)
        self.fit_timer = QTimer(self)
        self.fit_timer.setSingleShot(True)
        self.fit_timer.timeout.connect(self.fit)
        self.trim_timer = QTimer(self)
        self.trim_timer.setSingleShot(True)
        self.trim_timer.timeout.connect(self.finish_hop)
        self.dismiss_timer = QTimer(self)
        self.dismiss_timer.setSingleShot(True)
        self.dismiss_timer.timeout.connect(self.dismiss_if_outside)
        root.preferredPanelHeightChanged.connect(self.schedule_fit)
        root.layoutExpandedChanged.connect(self.schedule_fit)
        root.workspaceModeChanged.connect(self.schedule_fit)
        root.lookActiveChanged.connect(self.look_policy_changed)
        root.lookBubbleWidthChanged.connect(self.schedule_fit)
        root.panelRectChanged.connect(self.update_mask)
        root.mascotRectChanged.connect(self.update_mask)
        root.focusOwnedChanged.connect(self.focus_changed)
        view.screenChanged.connect(self.schedule_fit)
        view.xChanged.connect(self.remember_home)
        view.yChanged.connect(self.remember_home)
        QGuiApplication.instance().applicationStateChanged.connect(self.focus_changed)
        view.activeChanged.connect(self.focus_changed)
        root.moveRequested.connect(view.startSystemMove)
        root.hideRequested.connect(self.dismiss)
        controller.hideRequested.connect(self.dismiss)
        controller.interactionCompleted.connect(self.dismiss)
        controller.presentRequested.connect(self.present)
        controller.engagementRequested.connect(self.present)
        controller.lookRequested.connect(self.present)
        controller.minimalRequested.connect(self.present)
        controller.lookFocusRequested.connect(self.focus_look)
        # Captures may complete after the user has moved on. Store the result;
        # only an explicit invocation is allowed to show/activate this window.
        controller.presentAtRequested.connect(lambda _point: logger.info('capture_result_retained'))
        if QGuiApplication.instance().platformName() == 'cocoa':
            from AppKit import NSWorkspace, NSWorkspaceDidActivateApplicationNotification, NSWorkspaceApplicationKey
            from Foundation import NSOperationQueue
            self._workspace_center = NSWorkspace.sharedWorkspace().notificationCenter()
            def activated(notice):
                application = (notice.userInfo() or {}).get(NSWorkspaceApplicationKey)
                if application is not None:
                    # A second launch of our own bundle only recalls this
                    # instance; its short-lived PID must not count as switching
                    # to another application and immediately hide the recall.
                    own = (application.processIdentifier() == os.getpid()
                           or str(application.bundleIdentifier() or '') == 'vn.rat.mini')
                    self.nativeActivation.emit(own)
            self._activation_callback = activated
            self._activation_observer = self._workspace_center.addObserverForName_object_queue_usingBlock_(
                NSWorkspaceDidActivateApplicationNotification, None, NSOperationQueue.mainQueue(), activated)
            QGuiApplication.instance().aboutToQuit.connect(self.close)
        self.fit()

    def close(self):
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

    def remember_home(self, *_):
        if not self.fitting and not self.animating and self.view.isVisible():
            origin = (self.view.x(), self.view.y())
            dx, dy = origin[0]-self._last_origin[0], origin[1]-self._last_origin[1]
            if self.root.property('lookActive'):
                self.look_home = (self.look_home[0]+dx, self.look_home[1]+dy)
            else:
                self.home = (self.home[0]+dx, self.home[1]+dy)
                if self.expanded_top is not None:
                    self.expanded_top += dy
            self._last_origin = origin

    def fit(self):
        if self.animating:
            return
        self.fitting = True
        try:
            area = self.view.screen().availableGeometry()
            self.root.setProperty('maxPaperHeight', max(100, min(380, area.height()-240)))
            self.root.setProperty('maxPanelHeight', max(160, area.height()-32))
            if self.root.property('lookActive'):
                placement = place_look(Rect(area.x(), area.y(), area.width(), area.height()),
                    self.look_home, self.root.property('lookBubbleWidth'),
                    self.root.property('lookBubbleHeight'), self.root.property('lookVariant'))
                self.root.setProperty('animatePlacement', False)
                bounds = placement.bounds
                self.view.setGeometry(bounds.x-4, bounds.y-4, bounds.width+8, bounds.height+8)
                self._last_origin = (self.view.x(), self.view.y())
                self.root.setProperty('panelX', placement.panel.x-self.view.x())
                self.root.setProperty('panelY', placement.panel.y-self.view.y())
                self.root.setProperty('panelWidth', placement.panel.width)
                self.root.setProperty('ratX', placement.rat.x-self.view.x())
                self.root.setProperty('ratY', placement.rat.y-self.view.y())
                self.update_mask()
                if (self.root.property('lookVariant') != 'standby' and
                        round(self.root.property('lookBubbleHeight')) != placement.panel.height):
                    self.fit_timer.start(0)
                return
            expanded = bool(self.root.property('layoutExpanded'))
            if not expanded:
                self.expanded_top = None
            placement = place_panel(Rect(area.x(),area.y(),area.width(),area.height()), self.home,
                self.root.property('preferredPanelHeight'), expanded, self.side,
                panel_width=900 if self.controller.presentation.workspace_mode == 'full' else 580,
                paper_inset=0 if self.root.property('auxiliary') else round(self.root.property('paperOffset')),
                anchor_top=self.expanded_top if self.expanded else None)
            if expanded:
                self.expanded_top = placement.panel.y
            old = self.root.property('mascotRect')
            old_rat = Rect(self.view.x()+round(old.x()), self.view.y()+round(old.y()), 122, 128)
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

    def set_status_menu_open(self, opened):
        self.status_menu_open = opened
        self.focus_changed()

    def dismiss_if_outside(self):
        if self.root.property('lookActive'):
            return
        if (self.view.isVisible() and not self.root.property('focusOwned')
                and not self.status_menu_open
                and (self.native_outside or (self.was_active and
                    (QGuiApplication.instance().applicationState() != Qt.ApplicationState.ApplicationActive
                     or not self.view.isActive())))):
            self.dismiss()

    def dismiss(self):
        self.dismiss_timer.stop()
        QMetaObject.invokeMethod(self.root, 'dismissTransient')
        self.view.hide()
        logger.info('mini_dismissed; draft_and_result_retained')

    def present(self):
        self.dismiss_timer.stop()
        self.native_outside = False
        self.was_active = False
        self.fit()
        self.view.show()
        self.view.raise_()
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
