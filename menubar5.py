#!/usr/bin/env python3

import objc
from urllib.parse import urlparse, unquote

from CoreFoundation import CFPreferencesCopyAppValue
from Foundation import NSObject, NSTimer
from AppKit import (
    NSApp,
    NSApplication,
    NSApplicationActivationPolicyAccessory,
    NSApplicationActivateAllWindows,
    NSApplicationActivateIgnoringOtherApps,
    NSMenu,
    NSMenuItem,
    NSStatusBar,
    NSVariableStatusItemLength,
    NSWorkspace,
    NSRunningApplication,
    NSImage,
)
from PyObjCTools import AppHelper


DOCK_DOMAIN = "com.apple.dock"
PERSISTENT_APPS_KEY = "persistent-apps"


def file_url_to_path(url):
    if not url:
        return None
    parsed = urlparse(url)
    if parsed.scheme == "file":
        return unquote(parsed.path)
    return url


def normalize_app_path(path):
    if not path:
        return None
    path = str(path)
    if path.endswith("/"):
        path = path[:-1]
    return path


def get_persistent_dock_apps():
    items = CFPreferencesCopyAppValue(PERSISTENT_APPS_KEY, DOCK_DOMAIN) or []
    out = []

    for item in items:
        tile_data = item.get("tile-data", {})
        file_data = tile_data.get("file-data", {})

        label = tile_data.get("file-label")
        url = file_data.get("_CFURLString")
        path = normalize_app_path(file_url_to_path(url))

        if not path:
            continue

        out.append(
            {
                "label": str(label) if label else None,
                "path": path,
            }
        )

    return out


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

        running_apps = []
        running_by_path = {}

        for app in running:
            name = app.localizedName()
            if not name:
                continue

            if app.activationPolicy() != 0:
                continue

            running_apps.append(app)

            bundle_url = app.bundleURL()
            if bundle_url is not None:
                path = normalize_app_path(str(bundle_url.path()))
                if path:
                    running_by_path[path] = app

        finder_app = None
        finder_list = NSRunningApplication.runningApplicationsWithBundleIdentifier_(
            "com.apple.finder"
        )
        if finder_list:
            finder_app = finder_list[0]

        if finder_app is not None:
            self.menu.addItem_(self.menu_item_for_app(finder_app, is_running=True))
        else:
            self.menu.addItem_(
                self.dock_only_item(
                    label="Finder",
                    path="/System/Library/CoreServices/Finder.app",
                    is_running=True,
                )
            )

        dock_apps = get_persistent_dock_apps()
        dock_paths_seen = set()

        for dock_entry in dock_apps:
            path = dock_entry["path"]
            label = dock_entry["label"] or "Unknown"

            if path.endswith("/System/Library/CoreServices/Finder.app"):
                continue

            dock_paths_seen.add(path)

            app = running_by_path.get(path)
            is_running = app is not None

            if app is not None:
                self.menu.addItem_(self.menu_item_for_app(app, is_running=True))
            else:
                self.menu.addItem_(
                    self.dock_only_item(label=label, path=path, is_running=is_running)
                )

        self.menu.addItem_(NSMenuItem.separatorItem())

        leftover_running = []
        for app in running_apps:
            bundle_url = app.bundleURL()
            path = normalize_app_path(str(bundle_url.path())) if bundle_url else None
            bundle_id = str(app.bundleIdentifier() or "")

            if bundle_id == "com.apple.finder":
                continue
            if path in dock_paths_seen:
                continue

            leftover_running.append(app)

        leftover_running.sort(key=lambda app: str(app.localizedName()).lower())

        if not leftover_running:
            self.menu.addItem_(self.simple_text_item("No other running apps"))
        else:
            for app in leftover_running:
                self.menu.addItem_(self.menu_item_for_app(app, is_running=True))

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

    def simple_text_item(self, title):
        item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, None, "")
        item.setEnabled_(False)
        return item

    def set_menu_item_icon_from_image(self, item, icon):
        if icon is not None:
            icon = icon.copy()
            icon.setSize_((16, 16))
            item.setImage_(icon)

    def set_menu_item_icon_from_path(self, item, path):
        if not path:
            return

        workspace = NSWorkspace.sharedWorkspace()
        icon = workspace.iconForFile_(path)
        self.set_menu_item_icon_from_image(item, icon)

    def dock_only_item(self, label, path, is_running):
        title = f"• {label}" if is_running else f"  {label}"
        item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            title, "openDockApp:", ""
        )
        item.setTarget_(self)
        item.setRepresentedObject_(path)
        self.set_menu_item_icon_from_path(item, path)
        return item

    def menu_item_for_app(self, app, is_running):
        name = str(app.localizedName())
        title = f"• {name}" if is_running else f"  {name}"

        item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            title, "activateApp:", ""
        )
        item.setTarget_(self)
        item.setRepresentedObject_(app)

        icon = app.icon()
        self.set_menu_item_icon_from_image(item, icon)

        return item

    @objc.IBAction
    def activateApp_(self, sender):
        app = sender.representedObject()
        if app is None:
            return

        app.activateWithOptions_(
            NSApplicationActivateAllWindows | NSApplicationActivateIgnoringOtherApps
        )

    @objc.IBAction
    def openDockApp_(self, sender):
        path = sender.representedObject()
        if not path:
            return

        workspace = NSWorkspace.sharedWorkspace()
        workspace.openFile_(path)

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
