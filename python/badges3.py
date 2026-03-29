#!/usr/bin/env python3

from AppKit import NSRunningApplication
from ApplicationServices import (
    AXIsProcessTrusted,
    AXUIElementCreateApplication,
    AXUIElementCopyAttributeNames,
    AXUIElementCopyAttributeValue,
)
import ApplicationServices as AS

DOCK_BUNDLE_ID = "com.apple.dock"

CONTAINER_ATTRS = [
    AS.kAXChildrenAttribute,
    AS.kAXContentsAttribute,
    AS.kAXVisibleChildrenAttribute,
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


def walk_ax(elem):
    yield elem

    children = ax_value(elem, AS.kAXChildrenAttribute) or []
    for child in children:
        yield from walk_ax(child)


def nsurl_to_path(url):
    if url is None:
        return None
    try:
        return str(url.path())
    except Exception:
        return str(url)


def dock_item_record(elem):
    role = ax_value(elem, AS.kAXRoleAttribute)
    subrole = ax_value(elem, AS.kAXSubroleAttribute)

    # Collect all available AX* properties for the element
    all_attrs = ax_attr_names(elem)
    properties = {}
    for attr in all_attrs:
        value = ax_value(elem, attr)
        properties[attr] = value

    # Extract specific properties of interest
    title = ax_value(elem, AS.kAXTitleAttribute)
    url = ax_value(elem, AS.kAXURLAttribute)
    badge = ax_value(elem, "AXStatusLabel")
    running = ax_value(elem, AS.kAXIsApplicationRunningAttribute)
    pos = ax_value(elem, AS.kAXPositionAttribute)

    # Additional properties that might be useful
    description = ax_value(elem, AS.kAXDescriptionAttribute)
    help = ax_value(elem, AS.kAXHelpAttribute)
    value = ax_value(elem, AS.kAXValueAttribute)
    value_description = ax_value(elem, AS.kAXValueDescriptionAttribute)
    selected = ax_value(elem, AS.kAXSelectedAttribute)
    enabled = ax_value(elem, AS.kAXEnabledAttribute)
    editable = ax_value(elem, "AXEditable")
    orientation = ax_value(elem, AS.kAXOrientationAttribute)
    size = ax_value(elem, AS.kAXSizeAttribute)
    frame = ax_value(elem, "AXFrameAttribute")
    window = ax_value(elem, AS.kAXWindowAttribute)
    parent = ax_value(elem, AS.kAXParentAttribute)
    children = ax_value(elem, AS.kAXChildrenAttribute)
    visible_children = ax_value(elem, AS.kAXVisibleChildrenAttribute)
    contents = ax_value(elem, AS.kAXContentsAttribute)
    role_description = ax_value(elem, AS.kAXRoleDescriptionAttribute)
    subrole_description = ax_value(elem, "AXSubroleDescription")
    identifier = ax_value(elem, AS.kAXIdentifierAttribute)
    label = ax_value(elem, "AXLabel")
    localized_role_description = ax_value(elem, AS.kAXLocalizedRoleDescriptionAttribute)
    localized_subrole_description = ax_value(elem, AS.kAXLocalizedSubroleDescriptionAttribute)
    localized_description = ax_value(elem, "AXLocalizedDescription")
    localized_help = ax_value(elem, AS.kAXLocalizedHelpAttribute)
    localized_value_description = ax_value(elem, AS.kAXLocalizedValueDescriptionAttribute)
    localized_label = ax_value(elem, AS.kAXLocalizedLabelAttribute)
    localized_title = ax_value(elem, AS.kAXLocalizedTitleAttribute)
    localized_value = ax_value(elem, AS.kAXLocalizedValueAttribute)
    localized_identifier = ax_value(elem, AS.kAXLocalizedIdentifierAttribute)
    localized_role = ax_value(elem, AS.kAXLocalizedRoleAttribute)
    localized_subrole = ax_value(elem, AS.kAXLocalizedSubroleAttribute)
    localized_position = ax_value(elem, AS.kAXLocalizedPositionAttribute)
    localized_size = ax_value(elem, AS.kAXLocalizedSizeAttribute)
    localized_frame = ax_value(elem, AS.kAXLocalizedFrameAttribute)
    localized_window = ax_value(elem, AS.kAXLocalizedWindowAttribute)
    localized_parent = ax_value(elem, AS.kAXLocalizedParentAttribute)
    localized_children = ax_value(elem, AS.kAXLocalizedChildrenAttribute)
    localized_visible_children = ax_value(elem, AS.kAXLocalizedVisibleChildrenAttribute)
    localized_contents = ax_value(elem, AS.kAXLocalizedContentsAttribute)
    localized_selected = ax_value(elem, AS.kAXLocalizedSelectedAttribute)
    localized_enabled = ax_value(elem, AS.kAXLocalizedEnabledAttribute)
    localized_editable = ax_value(elem, AS.kAXLocalizedEditableAttribute)
    localized_orientation = ax_value(elem, AS.kAXLocalizedOrientationAttribute)

    return {
        "id": str(localized_identifier) if localized_identifier is not None else None,
        "role": str(role) if role is not None else None,
        "subrole": str(subrole) if subrole is not None else None,
        "title": str(title) if title is not None else None,
        "path": nsurl_to_path(url),
        "badge": str(badge) if badge not in (None, "") else None,
        "running": bool(running) if running is not None else None,
        "position": str(pos) if pos is not None else None,
    }

def main():
    if not AXIsProcessTrusted():
        print("Accessibility permission is not granted.")
        print("Enable it for Terminal / Python in System Settings -> Privacy & Security -> Accessibility.")
        return

    pid = find_pid(DOCK_BUNDLE_ID)
    app_elem = AXUIElementCreateApplication(pid)

    records = []

    for elem in walk_ax(app_elem):
        record = dock_item_record(elem)
        if record is None:
            continue
        records.append(record)

    if not records:
        print("No AXDockItem entries found.")
        return

    for item in records:
        print(
            f"id={item['id']!r} | "
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