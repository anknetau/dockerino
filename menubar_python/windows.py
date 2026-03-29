"""
windows.py — minimized-window discovery and restoration via the Accessibility API.

Requires the user to grant Accessibility permission to this app under:
    System Settings → Privacy & Security → Accessibility

All public functions degrade gracefully when permission is absent: they return
an empty list or a sentinel rather than raising.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto

import ApplicationServices as AS


# ---------------------------------------------------------------------------
# Accessibility attribute name constants
# (The framework exports these as plain strings; aliases improve readability.)
# ---------------------------------------------------------------------------
_AX_WINDOWS      = "AXWindows"
_AX_MINIMIZED    = "AXMinimized"
_AX_TITLE        = "AXTitle"

# kAXErrorAPIDisabled  — Accessibility permission not granted
# kAXErrorSuccess      — no error
_AX_ERR_API_DISABLED = -25211
_AX_ERR_SUCCESS      = 0


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

class AccessibilityStatus(Enum):
    OK          = auto()   # permission granted, query succeeded
    DENIED      = auto()   # Accessibility permission not granted
    UNAVAILABLE = auto()   # app has no AX windows (e.g. background-only process)


@dataclass(frozen=True)
class MinimizedWindow:
    """A single minimized window belonging to one running application."""
    title:      str
    pid:        int
    _ax_ref:    object = field(repr=False, compare=False)   # AXUIElementRef


# ---------------------------------------------------------------------------
# Low-level AX helpers
# ---------------------------------------------------------------------------

def _ax_get(element, attribute: str) -> tuple[int, object]:
    """
    Thin wrapper around ``AXUIElementCopyAttributeValue``.

    Returns ``(error_code, value)``.  *value* is ``None`` on error.
    """
    err, value = AS.AXUIElementCopyAttributeValue(element, attribute, None)
    return err, value


def _ax_set(element, attribute: str, value: object) -> int:
    """Thin wrapper around ``AXUIElementSetAttributeValue``. Returns error code."""
    return AS.AXUIElementSetAttributeValue(element, attribute, value)


# ---------------------------------------------------------------------------
# Permission check
# ---------------------------------------------------------------------------

def accessibility_permission_granted() -> bool:
    """
    Return *True* if this process currently has Accessibility permission.

    Passing ``False`` to ``AXIsProcessTrustedWithOptions`` means "don't show
    the system prompt" — we handle prompting ourselves via the menu item.
    """
    return bool(AS.AXIsProcessTrustedWithOptions(None))


def open_accessibility_preferences() -> None:
    """Open the Accessibility pane in System Settings."""
    from AppKit import NSWorkspace
    NSWorkspace.sharedWorkspace().openURL_(
        AS.NSURL.URLWithString_(
            "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
        )
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_minimized_windows(pid: int) -> tuple[AccessibilityStatus, list[MinimizedWindow]]:
    """
    Return all minimized windows for the process with *pid*.

    Returns a ``(status, windows)`` pair so callers can distinguish between
    "permission denied", "app has no windows", and "app has windows, none minimized".
    """
    app_ref = AS.AXUIElementCreateApplication(pid)

    err, windows = _ax_get(app_ref, _AX_WINDOWS)

    if err == _AX_ERR_API_DISABLED:
        return AccessibilityStatus.DENIED, []

    if err != _AX_ERR_SUCCESS or not windows:
        return AccessibilityStatus.UNAVAILABLE, []

    minimized: list[MinimizedWindow] = []
    for win in windows:
        min_err, is_minimized = _ax_get(win, _AX_MINIMIZED)
        if min_err != _AX_ERR_SUCCESS or not is_minimized:
            continue

        _title_err, raw_title = _ax_get(win, _AX_TITLE)
        title = str(raw_title) if raw_title else "(Untitled)"

        minimized.append(MinimizedWindow(title=title, pid=pid, _ax_ref=win))

    return AccessibilityStatus.OK, minimized


def restore_window(window: MinimizedWindow) -> None:
    """
    Deminimize *window* and bring it to the front.

    1. Clear the minimized flag — this animates the window out of the Dock.
    2. Raise the window within its application.
    3. Activate the owning application so it comes to the foreground.
    """
    # Un-minimise
    _ax_set(window._ax_ref, _AX_MINIMIZED, False)

    # Raise the specific window
    AS.AXRaise(window._ax_ref)

    # Bring the owning application to the front
    from AppKit import (
        NSRunningApplication,
        NSApplicationActivateAllWindows,
        NSApplicationActivateIgnoringOtherApps,
    )
    apps = NSRunningApplication.runningApplicationsWithBundleIdentifier_(
        _pid_to_bundle_id(window.pid)
    )
    # Fall back to activating by PID if bundle ID lookup fails
    app = apps[0] if apps else _app_for_pid(window.pid)
    if app:
        app.activateWithOptions_(
            NSApplicationActivateAllWindows | NSApplicationActivateIgnoringOtherApps
        )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _app_for_pid(pid: int):
    """Return the ``NSRunningApplication`` for *pid*, or *None*."""
    from AppKit import NSRunningApplication
    return NSRunningApplication.runningApplicationWithProcessIdentifier_(pid)


def _pid_to_bundle_id(pid: int) -> str | None:
    app = _app_for_pid(pid)
    return str(app.bundleIdentifier()) if app and app.bundleIdentifier() else None
