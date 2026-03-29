"""
running_apps.py — queries NSWorkspace for currently running GUI applications.
"""

from __future__ import annotations

from AppKit import NSRunningApplication, NSWorkspace

from dock import FINDER_BUNDLE_ID, FINDER_PATH, _normalize_path


# NSApplicationActivationPolicy.regular == 0
_REGULAR_ACTIVATION_POLICY = 0


def get_running_regular_apps() -> list:
    """
    Return all *regular* (Dock-visible) running ``NSRunningApplication`` objects,
    excluding Finder (which is handled separately).
    """
    apps = []
    for app in NSWorkspace.sharedWorkspace().runningApplications():
        if not app.localizedName():
            continue
        if app.activationPolicy() != _REGULAR_ACTIVATION_POLICY:
            continue
        if str(app.bundleIdentifier() or "") == FINDER_BUNDLE_ID:
            continue
        apps.append(app)
    return apps


def build_running_by_path(apps: list) -> dict[str, object]:
    """
    Build a ``{normalized_bundle_path: NSRunningApplication}`` lookup dict
    from *apps*.
    """
    mapping: dict[str, object] = {}
    for app in apps:
        bundle_url = app.bundleURL()
        if bundle_url is None:
            continue
        path = _normalize_path(str(bundle_url.path()))
        if path:
            mapping[path] = app
    return mapping


def get_finder_app() -> object | None:
    """Return the running Finder ``NSRunningApplication``, or *None*."""
    finder_list = NSRunningApplication.runningApplicationsWithBundleIdentifier_(
        FINDER_BUNDLE_ID
    )
    return finder_list[0] if finder_list else None
