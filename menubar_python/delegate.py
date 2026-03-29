"""
delegate.py — NSApplication delegate.

Owns the status-bar item and the refresh timer; delegates all menu content
decisions to ``menu_builder``.
"""

from __future__ import annotations

import objc
from AppKit import (
    NSApp,
    NSApplicationActivateAllWindows,
    NSApplicationActivateIgnoringOtherApps,
    NSMenu,
    NSStatusBar,
    NSVariableStatusItemLength,
    NSWorkspace,
)
from Foundation import NSObject, NSTimer

from dock_visibility import toggle_dock_autohide
from menu_builder import populate_menu
from windows import open_accessibility_preferences, restore_window


_REFRESH_INTERVAL: float = 5.0   # seconds between automatic refreshes
_STATUS_ITEM_TITLE: str  = "D"


class AppDelegate(NSObject):

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def applicationDidFinishLaunching_(self, notification) -> None:
        self._setup_status_item()
        self._setup_menu()
        self._setup_refresh_timer()

    # ------------------------------------------------------------------
    # Setup helpers
    # ------------------------------------------------------------------

    def _setup_status_item(self) -> None:
        self.status_item = NSStatusBar.systemStatusBar().statusItemWithLength_(
            NSVariableStatusItemLength
        )
        self.status_item.button().setTitle_(_STATUS_ITEM_TITLE)

    def _setup_menu(self) -> None:
        self.menu = NSMenu.alloc().init()
        self.menu.setDelegate_(self)
        self.status_item.setMenu_(self.menu)
        self._rebuild_menu()

    def _setup_refresh_timer(self) -> None:
        self.refresh_timer = (
            NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                _REFRESH_INTERVAL, self, "timerFired:", None, True
            )
        )

    # ------------------------------------------------------------------
    # Menu management
    # ------------------------------------------------------------------

    def _rebuild_menu(self) -> None:
        populate_menu(self.menu, self)

    # NSMenuDelegate — called just before the menu becomes visible.
    def menuWillOpen_(self, menu) -> None:
        self._rebuild_menu()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    @objc.IBAction
    def activateApp_(self, sender) -> None:
        """Bring a running app to the foreground."""
        app = sender.representedObject()
        if app is None:
            return
        app.activateWithOptions_(
            NSApplicationActivateAllWindows | NSApplicationActivateIgnoringOtherApps
        )

    @objc.IBAction
    def openDockApp_(self, sender) -> None:
        """Launch (or focus) an app by its bundle path."""
        path = sender.representedObject()
        if path:
            NSWorkspace.sharedWorkspace().openFile_(path)

    @objc.IBAction
    def openTrash_(self, sender) -> None:
        """Open the user's Trash in Finder."""
        path = sender.representedObject()
        if path:
            NSWorkspace.sharedWorkspace().openFile_(path)

    @objc.IBAction
    def restoreWindow_(self, sender) -> None:
        """Deminimize a window and bring it to the front."""
        window = sender.representedObject()
        if window is not None:
            restore_window(window)

    @objc.IBAction
    def openAccessibilityPreferences_(self, sender) -> None:
        """Open the Accessibility pane in System Settings."""
        open_accessibility_preferences()

    @objc.IBAction
    def toggleDockVisibility_(self, sender) -> None:
        """Toggle Dock autohide and rebuild the menu label."""
        toggle_dock_autohide()
        self._rebuild_menu()

    @objc.IBAction
    def timerFired_(self, sender) -> None:
        self._rebuild_menu()

    @objc.IBAction
    def refreshMenu_(self, sender) -> None:
        self._rebuild_menu()

    @objc.IBAction
    def quitApp_(self, sender) -> None:
        self._invalidate_timer()
        NSApp.terminate_(None)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _invalidate_timer(self) -> None:
        timer = getattr(self, "refresh_timer", None)
        if timer is not None:
            timer.invalidate()
            self.refresh_timer = None
