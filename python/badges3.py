#!/usr/bin/env python3

from AppKit import NSWorkspace, NSRunningApplication
from ApplicationServices import (
    AXIsProcessTrusted,
    AXUIElementCreateApplication,
    AXUIElementCopyAttributeNames,
    AXUIElementCopyAttributeValue,
)

DOCK_BUNDLE_ID = "com.apple.dock"

CONTAINER_ATTRS = [
    "AXChildren",
    "AXContents",
    "AXVisibleChildren",
]


def find_pid(bundle_id):
    try:
        return NSRunningApplication.runningApplicationsWithBundleIdentifier_(bundle_id)[0].processIdentifier()
    except Exception:
        raise RuntimeError("Dock process not found")


def ax_attr_names(elem):
    err, names = AXUIElementCopyAttributeNames(elem, None)
    if err != 0 or names is None:
        return []
    return list(names)


def ax_value(elem, attr):
    err, value = AXUIElementCopyAttributeValue(elem, attr, None)
    if err != 0:
        return None
    return value


def is_ax_element(value):
    return value is not None and type(value).__name__ == "AXUIElementRef"


def iter_child_elements(elem):
    names = set(ax_attr_names(elem))
    for attr in CONTAINER_ATTRS:
        if attr not in names:
            continue
        value = ax_value(elem, attr)
        if value is None:
            continue

        if is_ax_element(value):
            yield attr, value
        elif isinstance(value, (list, tuple)):
            for child in value:
                if is_ax_element(child):
                    yield attr, child


def walk_ax(elem, seen=None):
    if seen is None:
        seen = set()

    oid = id(elem)
    # if oid in seen:
    #     return
    seen.add(oid)

    yield elem

    # Get all children recursively like badges1.py
    children = ax_value(elem, "AXChildren") or []
    for child in children:
        yield from walk_ax(child, seen)

    # Also check AXVisibleChildren for elements that might not have AXChildren
    visible = ax_value(elem, "AXVisibleChildren") or []
    for child in visible:
        if id(child) not in seen:
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


    # if role != "AXDockItem" or subrole != "AXApplicationDockItem":
    #     return None

    title = ax_value(elem, "AXTitle")
    url = ax_value(elem, "AXURL")
    badge = ax_value(elem, "AXStatusLabel")
    running = ax_value(elem, "AXIsApplicationRunning")
    pos = ax_value(elem, "AXPosition")

    return {
        "role": str(role) if role is not None else None,
        "subrole": str(subrole) if subrole is not None else None,
        "title": str(title) if title is not None else None,
        "path": nsurl_to_path(url),
        "badge": str(badge) if badge not in (None, "") else None,
        "running": bool(running) if running is not None else None,
        "position": str(pos) if pos is not None else None,
    }


def sort_key(item):
    title = item["title"] or ""
    return title.lower(), item["path"] or ""


def main():
    if not AXIsProcessTrusted():
        print("Accessibility permission is not granted.")
        print("Enable it for Terminal / Python in System Settings -> Privacy & Security -> Accessibility.")
        return

    pid = find_pid(DOCK_BUNDLE_ID)
    app_elem = AXUIElementCreateApplication(pid)

    records = []
    seen_records = set()

    for elem in walk_ax(app_elem):
        record = dock_item_record(elem)
        if record is None:
            continue

        key = (
            record["title"],
            record["path"],
            record["role"],
            record["subrole"],
        )
        # if record["path"] in seen_records:
        #     continue
        seen_records.add(record["path"])
        records.append(record)

    if not records:
        print("No AXDockItem entries found.")
        return

    for item in sorted(records, key=sort_key):
        print(
            f"title={item['title']!r} | "
            f"role={item['role']!r} | "
            f"subrole={item['subrole']!r} | "
            f"running={item['running']!r} | "
            f"badge={item['badge']!r} | "
            f"path={item['path']!r} | "
            f"position={item['position']}"
        )


if __name__ == "__main__":
    main()