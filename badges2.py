#!/usr/bin/env python3

from AppKit import NSWorkspace
from ApplicationServices import (
    AXIsProcessTrusted,
    AXUIElementCreateApplication,
    AXUIElementCopyAttributeValue,
)

DOCK_BUNDLE_ID = "com.apple.dock"


def find_dock_pid():
    for app in NSWorkspace.sharedWorkspace().runningApplications():
        if str(app.bundleIdentifier() or "") == DOCK_BUNDLE_ID:
            return app.processIdentifier()
    raise RuntimeError("Dock process not found")


def ax_value(elem, attr):
    err, value = AXUIElementCopyAttributeValue(elem, attr, None)
    if err != 0:
        return None
    return value


def walk_ax(elem, seen=None):
    if seen is None:
        seen = set()

    oid = id(elem)
    if oid in seen:
        return
    seen.add(oid)

    yield elem

    children = ax_value(elem, "AXChildren") or []
    for child in children:
        yield from walk_ax(child, seen)


def nsurl_to_path(url):
    if url is None:
        return None
    try:
        return str(url.path())
    except Exception:
        return str(url)


def dock_item_record(elem):
    role = ax_value(elem, "AXRole")
    subrole = ax_value(elem, "AXSubrole")

    if role != "AXDockItem" or subrole != "AXApplicationDockItem":
        return None

    title = ax_value(elem, "AXTitle")
    url = ax_value(elem, "AXURL")
    badge = ax_value(elem, "AXStatusLabel")
    running = ax_value(elem, "AXIsApplicationRunning")
    position = ax_value(elem, "AXPosition")

    # AXPosition is an AXValue wrapper; stringify it for now.
    position_text = str(position) if position is not None else None

    return {
        "title": str(title) if title is not None else None,
        "path": nsurl_to_path(url),
        "badge": str(badge) if badge not in (None, "") else None,
        "running": bool(running) if running is not None else None,
        "position": position_text,
    }


def main():
    if not AXIsProcessTrusted():
        print("Accessibility permission is not granted.")
        print("Enable it for Terminal / Python in System Settings -> Privacy & Security -> Accessibility.")
        return

    pid = find_dock_pid()
    app_elem = AXUIElementCreateApplication(pid)

    items = []
    for elem in walk_ax(app_elem):
        record = dock_item_record(elem)
        if record is not None:
            items.append(record)

    if not items:
        print("No AXApplicationDockItem entries found.")
        return

    for item in items:
        print(
            f"title={item['title']!r} | "
            f"running={item['running']!r} | "
            f"badge={item['badge']!r} | "
            f"path={item['path']!r} | "
            f"position={item['position']}"
        )


if __name__ == "__main__":
    main()