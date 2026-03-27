#!/usr/bin/env python3

import sys
import objc

from Foundation import NSObject
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

        # Text in the menu bar. Replace with an image later if you want.
        self.status_item.button().setTitle_("Apps")

        self.menu = NSMenu.alloc().init()
        self.status_item.setMenu_(self.menu)

        self.rebuild_menu()

    def rebuild_menu(self):
        self.menu.removeAllItems()

        running = NSWorkspace.sharedWorkspace().runningApplications()

        apps = []
        for app in running:
            name = app.localizedName()
            # activationPolicy() == 0 means "regular" GUI app.
            # This filters out many background/UIElement processes.
            if name and app.activationPolicy() == 0:
                apps.append((str(name), app))

        apps.sort(key=lambda pair: pair[0].lower())

        if not apps:
            item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                "No running apps found", None, ""
            )
            item.setEnabled_(False)
            self.menu.addItem_(item)
        else:
            for name, app in apps:
                title = name
                bundle_id = app.bundleIdentifier()
                if bundle_id:
                    title = f"{name} ({bundle_id})"

                item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                    title, None, ""
                )
                item.setEnabled_(False)
                self.menu.addItem_(item)

        self.menu.addItem_(NSMenuItem.separatorItem())

        refresh_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Refresh", "refreshMenu:", ""
        )
        refresh_item.setTarget_(self)
        self.menu.addItem_(refresh_item)

        quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Quit", "quitApp:", "q"
        )
        quit_item.setTarget_(self)
        self.menu.addItem_(quit_item)

    @objc.IBAction
    def refreshMenu_(self, sender):
        self.rebuild_menu()

    @objc.IBAction
    def quitApp_(self, sender):
        NSApp.terminate_(None)


def main():
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

    delegate = AppDelegate.alloc().init()
    app.setDelegate_(delegate)

    AppHelper.runEventLoop()


if __name__ == "__main__":
    main()
