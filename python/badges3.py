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


def _extract_attr(elem, attr_name):
    """Helper to extract and convert an attribute value."""
    value = ax_value(elem, attr_name)
    if value is None:
        return None
    return str(value)


def dock_item_record(elem):
    # Define attribute mappings: (internal_key, AX_attribute_name)
    attribute_mappings = [
        ("id", AS.kAXIdentifierAttribute),
        ("role", AS.kAXRoleAttribute),
        ("subrole", AS.kAXSubroleAttribute),
        ("title", AS.kAXTitleAttribute),
        ("localized_title", AS.AXLocalizedTitleAttribute),
        ("url", AS.kAXURLAttribute),
        ("badge", "AXStatusLabel"),
        ("running", AS.kAXIsApplicationRunningAttribute),
        ("position", AS.kAXPositionAttribute),
        ("description", AS.kAXDescriptionAttribute),
        ("help", AS.kAXHelpAttribute),
        ("value", AS.kAXValueAttribute),
        ("value_description", AS.kAXValueDescriptionAttribute),
        ("selected", AS.kAXSelectedAttribute),
        ("enabled", AS.kAXEnabledAttribute),
        ("editable", "AXEditable"),
        ("orientation", AS.kAXOrientationAttribute),
        ("size", AS.kAXSizeAttribute),
        ("frame", "AXFrameAttribute"),
        ("window", AS.kAXWindowAttribute),
        ("parent", AS.kAXParentAttribute),
        ("children", AS.kAXChildrenAttribute),
        ("visible_children", AS.kAXVisibleChildrenAttribute),
        ("contents", AS.kAXContentsAttribute),
        ("role_description", AS.kAXRoleDescriptionAttribute),
        ("subrole_description", "AXSubroleDescription"),
        ("label", "AXLabel"),
        ("localized_role_description", AS.kAXLocalizedRoleDescriptionAttribute),
        ("localized_subrole_description", "AXLocalizedSubroleDescription"),
        ("localized_description", "AXLocalizedDescription"),
        ("localized_help", AS.kAXLocalizedHelpAttribute),
        ("localized_value_description", AS.kAXLocalizedValueDescriptionAttribute),
        ("localized_label", AS.kAXLocalizedLabelAttribute),
        ("localized_value", AS.kAXLocalizedValueAttribute),
        ("localized_role", AS.kAXLocalizedRoleAttribute),
        ("localized_subrole", AS.kAXLocalizedSubroleAttribute),
        ("localized_position", AS.kAXLocalizedPositionAttribute),
        ("localized_size", AS.kAXLocalizedSizeAttribute),
        ("localized_frame", AS.kAXLocalizedFrameAttribute),
        ("localized_window", AS.kAXLocalizedWindowAttribute),
        ("localized_parent", AS.kAXLocalizedParentAttribute),
        ("localized_children", AS.kAXLocalizedChildrenAttribute),
        ("localized_visible_children", AS.kAXLocalizedVisibleChildrenAttribute),
        ("localized_contents", AS.kAXLocalizedContentsAttribute),
        ("localized_selected", AS.kAXLocalizedSelectedAttribute),
        ("localized_enabled", AS.kAXLocalizedEnabledAttribute),
        ("localized_editable", AS.kAXLocalizedEditableAttribute),
        ("localized_orientation", AS.kAXLocalizedOrientationAttribute),
    ]

    # Extract all attributes using the mapping
    properties = {}
    for internal_key, ax_attr in attribute_mappings:
        properties[internal_key] = _extract_attr(elem, ax_attr)

    # Extract specific properties of interest
    title = properties.get("title")
    url = ax_value(elem, AS.kAXURLAttribute)
    badge = properties.get("badge")
    running = properties.get("running")
    pos = properties.get("position")
    localized_identifier = properties.get("id")

    return {
        "id": str(localized_identifier) if localized_identifier is not None else None,
        "role": properties.get("role"),
        "subrole": properties.get("subrole"),
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
