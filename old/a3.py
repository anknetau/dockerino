#!/usr/bin/env python3
"""
Dock Item Enumerator using PyObjC and macOS Accessibility API
"""

from AppKit import NSRunningApplication
import ApplicationServices as AS

def get_dock_application():
    """Find the Dock process by its bundle identifier."""
    for app in NSRunningApplication.runningApplicationsWithBundleIdentifier_('com.apple.dock'):
        return app
    return None

def get_dock_ax_element(dock_app):
    """Get the AXUIElement for the Dock application."""
    try:
        pid = dock_app.processIdentifier()
        return AS.AXUIElementCreateApplication(pid)
    except Exception as e:
        print(f"Error creating AXUIElement: {e}")
        return None

def get_dock_items(dock_ax):
    """Retrieve all dock item elements from the Dock."""
    items = []
    try:
        # First level: get children of the Dock (usually an AXList)
        result, children = AS.AXUIElementCopyAttributeValue(dock_ax, 'AXChildren', None)
        if result == 0 and children:
            for child in children:
                # Second level: get children of the AXList (actual dock items)
                result, list_items = AS.AXUIElementCopyAttributeValue(child, 'AXChildren', None)
                if result == 0 and list_items:
                    for item in list_items:
                        items.append(item)
    except Exception as e:
        print(f"Error getting children: {e}")
    return items

def get_item_info(ax_element):
    """Extract detailed information about a dock item."""
    info = {}
    try:
        # Try to get the name using AXValue or AXTitle
        result, name = AS.AXUIElementCopyAttributeValue(ax_element, 'AXValue', None)
        if result == 0 and name:
            info['name'] = str(name)
        else:
            result, title = AS.AXUIElementCopyAttributeValue(ax_element, 'AXTitle', None)
            if result == 0 and title:
                info['name'] = str(title)
            else:
                info['name'] = 'Unknown'

        result, role = AS.AXUIElementCopyAttributeValue(ax_element, 'AXRole', None)
        info['role'] = str(role) if result == 0 and role else 'N/A'

        result, role_desc = AS.AXUIElementCopyAttributeValue(ax_element, 'AXRoleDescription', None)
        info['role_description'] = str(role_desc) if result == 0 and role_desc else 'N/A'

        result, description = AS.AXUIElementCopyAttributeValue(ax_element, 'AXDescription', None)
        info['description'] = str(description) if result == 0 and description else 'N/A'

        result, enabled = AS.AXUIElementCopyAttributeValue(ax_element, 'AXEnabled', None)
        info['enabled'] = bool(enabled) if result == 0 and enabled is not None else 'N/A'

        result, hidden = AS.AXUIElementCopyAttributeValue(ax_element, 'AXHidden', None)
        info['hidden'] = bool(hidden) if result == 0 and hidden is not None else 'N/A'
    except Exception as e:
        info['error'] = str(e)
    return info

def print_dock_items(dock_items):
    """Display dock items with their details."""
    print(f"\n{'='*60}")
    print(f"{'DOCK ITEMS':^60}")
    print(f"{'='*60}\n")

    for i, item in enumerate(dock_items, 1):
        info = get_item_info(item)
        print(f"[{i}] {info.get('name', 'Unknown')}")
        print(f"    Role: {info.get('role', 'N/A')}")
        print(f"    Role Description: {info.get('role_description', 'N/A')}")
        print(f"    Description: {info.get('description', 'N/A')}")
        print(f"    Enabled: {info.get('enabled', 'N/A')}")
        print(f"    Hidden: {info.get('hidden', 'N/A')}")
        print()

def main():
    print("Starting Dock Item Enumerator...\n")

    dock_app = get_dock_application()
    if not dock_app:
        print("Error: Could not find the Dock application.")
        return

    print(f"Found Dock process: {dock_app.localizedName()} with pid {dock_app.processIdentifier()}")

    dock_ax = get_dock_ax_element(dock_app)
    if not dock_ax:
        print("Error: Could not create AXUIElement for Dock.")
        return

    dock_items = get_dock_items(dock_ax)
    if not dock_items:
        print("No dock items found.")
        return

    print(f"Found {len(dock_items)} dock item(s)\n")
    print_dock_items(dock_items)

if __name__ == '__main__':
    main()
