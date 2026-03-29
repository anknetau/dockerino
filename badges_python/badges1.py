#!/usr/bin/env python3

from AppKit import NSWorkspace
from ApplicationServices import (
    AXIsProcessTrusted,
    AXUIElementCreateApplication,
    AXUIElementCopyAttributeNames,
    AXUIElementCopyAttributeValue,
)

MAX_DEPTH = 6

COMMON_ATTRIBUTES = [
    "AXRole",
    "AXSubrole",
    "AXRoleDescription",
    "AXTitle",
    "AXDescription",
    "AXValue",
    "AXHelp",
    "AXIdentifier",
    "AXLabelValue",
    "AXURL",
    "AXFilename",
    "AXSelected",
    "AXEnabled",
    "AXFocused",
    "AXPosition",
    "AXSize",
    "AXChildren",
]


def find_dock_pid():
    apps = NSWorkspace.sharedWorkspace().runningApplications()
    for app in apps:
        if str(app.bundleIdentifier() or "") == "com.apple.dock":
            return app.processIdentifier()
    raise RuntimeError("Dock process not found")


def ax_copy_attribute_names(elem):
    err, names = AXUIElementCopyAttributeNames(elem, None)
    if err != 0:
        return []
    return list(names or [])


def ax_copy_attribute_value(elem, attr):
    err, value = AXUIElementCopyAttributeValue(elem, attr, None)
    if err != 0:
        return None
    return value


def short_repr(value, max_len=140):
    try:
        if value is None:
            return "None"

        if isinstance(value, (str, int, float, bool)):
            s = repr(value)
        elif isinstance(value, (list, tuple)):
            s = f"<{type(value).__name__} len={len(value)}>"
        else:
            cls = type(value).__name__
            s = f"<{cls} {value!r}>"

        if len(s) > max_len:
            s = s[: max_len - 3] + "..."
        return s
    except Exception as e:
        return f"<unreprable: {e}>"


def print_element(elem, depth=0, seen=None, path="root"):
    if seen is None:
        seen = set()

    oid = id(elem)
    indent = "  " * depth

    if oid in seen:
        print(f"{indent}- {path} <already seen>")
        return
    # seen.add(oid)

    names = ax_copy_attribute_names(elem)
    # print(f"{indent}- {path}")
    # print(f"{indent}  attributes: {', '.join(names) if names else '(none)'}")

    for attr in COMMON_ATTRIBUTES:
        if attr not in names:
            continue
        value = ax_copy_attribute_value(elem, attr)

        if attr == "AXChildren":
            # if value is None:
            #     print(f"{indent}  {attr}: None")
            # else:
            #     print(f"{indent}  {attr}: <{type(value).__name__} len={len(value)}>")
            continue

        # AXRole: 'AXDockItem'
    #   AXSubrole: 'AXApplicationDockItem'
    #   AXRoleDescription: 'application dock item'
    #   AXTitle: 'Finder'
    #   AXURL: <NSURL file:///System/Library/CoreServices/Finder.app/>
    #   AXSelected: False
    #   AXPosition: <AXValueRef <AXValue 0x8d4ee5050> {value = x:574.049988 y:1190.000000 type = kAXValueCGPointType}>
    #   AXSize: <AXValueRef <AXValue 0x8d4ee5080> {value = w:31.000000 h:43.000000 type = kAXValueCGSizeType}>
    #   AXChildren: <__NSArray0 len=0>
    #   AXParent: <AXUIElementRef <AXUIElement 0x8d4c1de60> {pid=66791}>
    #   AXFrame: <AXValueRef <AXValue 0x8d51ea180> {value = x:574.049988 y:1190.000000 w:31.000000 h:43.000000 type = kAXValueCGRectType}>
    #   AXTopLevelUIElement: <AXUIElementRef <AXUIElement 0x8d4c1de60> {pid=66791}>
    #   AXShownMenuUIElement: None
    #   AXStatusLabel: None
    #   AXProgressValue: None
    #   AXIsApplicationRunning: True
        if attr == "AXURL" or attr == "AXRole" or attr == "AXSubRole":
            print(f"--{indent}  {attr}: {short_repr(value)}")

    extra_attrs = [a for a in names if a not in COMMON_ATTRIBUTES]
    for attr in extra_attrs:
        value = ax_copy_attribute_value(elem, attr)
        if attr == "AXStatusLabel":
            if isinstance(value, (list, tuple)):
                print(f">>>{indent}  {attr}: <{type(value).__name__} len={len(value)}>")
            else:
                print(f">>>{indent}  {attr}: {short_repr(value)}")
        # if isinstance(value, (list, tuple)):
        #     print(f">>>{indent}  {attr}: <{type(value).__name__} len={len(value)}>")
        # else:
        #     print(f">>>{indent}  {attr}: {short_repr(value)}")

    if depth >= MAX_DEPTH:
        return

    children = ax_copy_attribute_value(elem, "AXChildren") or []
    for i, child in enumerate(children):
        print_element(child, depth + 1, seen, f"{path}.children[{i}]")


def main():
    if not AXIsProcessTrusted():
        print("Accessibility permission is not granted.")
        print("Enable it in System Settings -> Privacy & Security -> Accessibility.")
        return

    pid = find_dock_pid()
    print(f"Dock pid: {pid}")

    app_elem = AXUIElementCreateApplication(pid)
    print_element(app_elem)


if __name__ == "__main__":
    main()
