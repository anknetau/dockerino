"""
dock_visibility.py — read and toggle the Dock autohide preference.
"""

from __future__ import annotations

from CoreFoundation import (
    CFPreferencesAppSynchronize,
    CFPreferencesCopyAppValue,
    CFPreferencesSetAppValue,
)
from AppKit import NSRunningApplication


DOCK_DOMAIN = "com.apple.dock"
AUTOHIDE_KEY = "autohide"


def get_dock_autohide() -> bool:
    """Return whether Dock autohide is currently enabled."""
    value = CFPreferencesCopyAppValue(AUTOHIDE_KEY, DOCK_DOMAIN)
    return bool(value) if value is not None else False


def set_dock_autohide(hidden: bool) -> None:
    """Set Dock autohide and restart the Dock so the change applies."""
    CFPreferencesSetAppValue(AUTOHIDE_KEY, hidden, DOCK_DOMAIN)
    ok = CFPreferencesAppSynchronize(DOCK_DOMAIN)
    if not ok:
        raise RuntimeError("Failed to synchronize Dock preferences")
    restart_dock()


def toggle_dock_autohide() -> bool:
    """Toggle Dock autohide, returning the new state."""
    new_value = not get_dock_autohide()
    set_dock_autohide(new_value)
    return new_value


def restart_dock() -> None:
    """Restart Dock without shelling out."""
    for app in NSRunningApplication.runningApplicationsWithBundleIdentifier_("com.apple.dock"):
        app.forceTerminate()
