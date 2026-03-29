"""
Controls the macOS Dock's autohide behavior.
"""

from CoreFoundation import (
    CFPreferencesCopyAppValue,
    CFPreferencesSetAppValue,
    CFPreferencesAppSynchronize,
)
from Foundation import CFBooleanRef
from AppKit import NSRunningApplication

DOCK_DOMAIN = "com.apple.dock"
AUTOHIDE_KEY = "autohide"


def get_dock_autohide() -> bool:
    value = CFPreferencesCopyAppValue(AUTOHIDE_KEY, DOCK_DOMAIN)
    # If unset, treat it as False.
    return bool(value) if value is not None else False


def set_dock_autohide(hidden: bool) -> None:
    CFPreferencesSetAppValue(AUTOHIDE_KEY, hidden, DOCK_DOMAIN)
    ok = CFPreferencesAppSynchronize(DOCK_DOMAIN)
    if not ok:
        raise RuntimeError("Failed to synchronize Dock preferences")
    restart_dock()


def toggle_dock_autohide() -> bool:
    new_value = not get_dock_autohide()
    set_dock_autohide(new_value)
    return new_value


def restart_dock() -> None:
    # Restart Dock without shelling out.
    for app in NSRunningApplication.runningApplicationsWithBundleIdentifier_("com.apple.dock"):
        app.forceTerminate()


if __name__ == "__main__":
    current = get_dock_autohide()
    print(f"Current autohide: {current}")

    new_value = toggle_dock_autohide()
    print(f"New autohide: {new_value}")
