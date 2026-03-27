#!/usr/bin/env python3

import objc

from Foundation import NSObject, NSTimer
from AppKit import (
    NSApp,
    NSApplication,
    NSApplicationActivationPolicyAccessory,
    NSMenu,
    NSMenuItem,
    NSStatusBar,
    NSVariableStatusItemLength,
    NSWorkspace,
)
from PyObjCTools import AppHelper


class AppDelegate(NSObject):
    def applicationDidFinishLaunching_(self, notification):
        self.status_item = NSStatusBar.systemStatusBar().statusItemWithLength_(
            NSVariableStatusItemLength
        )

        button = self.status_item.button()
        button.setTitle_("D")

        self.menu = NSMenu.alloc().init()
        self.menu.setDelegate_(self)
        self.status_item.setMenu_(self.menu)

        self.rebuild_menu()

        # Refresh every 5 seconds
        self.refresh_timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            5.0,
            self,
            "timerFired:",
            None,
            True,
        )

    def rebuild_menu(self):
        self.menu.removeAllItems()

        running = NSWorkspace.sharedWorkspace().runningApplications()

        apps = []
        for app in running:
            name = app.localizedName()
            if not name:
                continue

            # 0 = regular app; filters out many background processes
            if app.activationPolicy() != 0:
                continue

            apps.append(app)

        apps.sort(key=lambda app: str(app.localizedName()).lower())

        if not apps:
            item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                "No running apps found", None, ""
            )
            item.setEnabled_(False)
            self.menu.addItem_(item)
        else:
            for app in apps:
                self.menu.addItem_(self.menu_item_for_app(app))

        self.menu.addItem_(NSMenuItem.separatorItem())

        refresh_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Refresh now", "refreshMenu:", ""
        )
        refresh_item.setTarget_(self)
        self.menu.addItem_(refresh_item)

        quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Quit", "quitApp:", "q"
        )
        quit_item.setTarget_(self)
        self.menu.addItem_(quit_item)

    def menu_item_for_app(self, app):
        name = str(app.localizedName())
        bundle_id = app.bundleIdentifier()
        title = f"{name} ({bundle_id})" if bundle_id else name
        title = name

        item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            title, None, ""
        )
        item.setEnabled_(False)

        icon = app.icon()
        if icon is not None:
            icon = icon.copy()
            icon.setSize_((16, 16))
            item.setImage_(icon)

        return item

    @objc.IBAction
    def timerFired_(self, sender):
        self.rebuild_menu()

    def menuWillOpen_(self, menu):
        self.rebuild_menu()

    @objc.IBAction
    def refreshMenu_(self, sender):
        self.rebuild_menu()

    @objc.IBAction
    def quitApp_(self, sender):
        if getattr(self, "refresh_timer", None) is not None:
            self.refresh_timer.invalidate()
            self.refresh_timer = None
        NSApp.terminate_(None)


def main():
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

    delegate = AppDelegate.alloc().init()
    app.setDelegate_(delegate)

    AppHelper.runEventLoop()


if __name__ == "__main__":
    main()
