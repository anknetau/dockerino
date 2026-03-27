"""
menu_builder.py — constructs the NSMenu contents from Dock + running-app data.

This module is deliberately free of Objective-C delegate concerns: it only
knows how to turn data into NSMenuItems and assemble them into an NSMenu.
"""

from __future__ import annotations

from AppKit import NSMenuItem, NSWorkspace

from dock import (
    FINDER_PATH,
    DockEntry,
    get_persistent_dock_apps,
    get_persistent_dock_others,
    get_trash_entry,
)
from running_apps import (
    build_running_by_path,
    get_finder_app,
    get_running_regular_apps,
)
from windows import (
    AccessibilityStatus,
    MinimizedWindow,
    get_minimized_windows,
)


_ICON_SIZE = (16, 16)

# Bullet shown next to running apps; leading spaces align non-running entries.
_RUNNING_PREFIX  = "• "
_STOPPED_PREFIX  = "  "

# Indentation prefix for minimized-window child rows.
_WINDOW_PREFIX   = "      ↳ "

# Shown when Accessibility permission has not been granted.
_AX_DENIED_LABEL = "  ⚠ Enable Accessibility to show minimised windows…"


# ---------------------------------------------------------------------------
# Low-level item factories
# ---------------------------------------------------------------------------

def _make_item(title: str, action: str | None, target: object) -> NSMenuItem:
    item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        title, action, ""
    )
    item.setTarget_(target)
    return item


def _apply_icon_from_image(item: NSMenuItem, icon) -> None:
    if icon is None:
        return
    icon = icon.copy()
    icon.setSize_(_ICON_SIZE)
    item.setImage_(icon)


def _apply_icon_from_path(item: NSMenuItem, path: str) -> None:
    icon = NSWorkspace.sharedWorkspace().iconForFile_(path)
    _apply_icon_from_image(item, icon)


def _format_title(name: str, is_running: bool) -> str:
    prefix = _RUNNING_PREFIX if is_running else _STOPPED_PREFIX
    return f"{prefix}{name}"


# ---------------------------------------------------------------------------
# Higher-level item builders
# ---------------------------------------------------------------------------

def running_app_item(app, target: object) -> NSMenuItem:
    """Menu item for an already-running ``NSRunningApplication``."""
    title = _format_title(str(app.localizedName()), is_running=True)
    item = _make_item(title, "activateApp:", target)
    item.setRepresentedObject_(app)
    _apply_icon_from_image(item, app.icon())
    return item


def dock_app_item(entry: DockEntry, is_running: bool, target: object) -> NSMenuItem:
    """Menu item for a Dock-pinned app (running or not)."""
    title = _format_title(entry.label, is_running)
    item = _make_item(title, "openDockApp:", target)
    item.setRepresentedObject_(entry.path)
    _apply_icon_from_path(item, entry.path)
    return item


def trash_item(target: object) -> NSMenuItem:
    """Menu item for Trash."""
    entry = get_trash_entry()
    item = _make_item(entry.label, "openTrash:", target)
    item.setRepresentedObject_(entry.path)
    _apply_icon_from_path(item, entry.path)
    return item


def dock_other_item(entry: DockEntry, target: object) -> NSMenuItem:
    """Menu item for a right-side Dock item such as Downloads or Documents."""
    item = _make_item(entry.label, "openDockApp:", target)
    item.setRepresentedObject_(entry.path)
    _apply_icon_from_path(item, entry.path)
    return item


def minimized_window_item(window: MinimizedWindow, target: object) -> NSMenuItem:
    """Indented menu item representing one minimized window."""
    title = f"{_WINDOW_PREFIX}{window.title}"
    item = _make_item(title, "restoreWindow:", target)
    item.setRepresentedObject_(window)
    return item


def accessibility_prompt_item(target: object) -> NSMenuItem:
    """Tappable item shown when Accessibility permission is missing."""
    return _make_item(_AX_DENIED_LABEL, "openAccessibilityPreferences:", target)


def disabled_text_item(title: str) -> NSMenuItem:
    item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, None, "")
    item.setEnabled_(False)
    return item


def action_item(title: str, action: str, key: str, target: object) -> NSMenuItem:
    item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, action, key)
    item.setTarget_(target)
    return item


# ---------------------------------------------------------------------------
# Minimized-window injection
# ---------------------------------------------------------------------------

def _append_minimized_windows(
    menu, app, target: object, ax_denied_shown: list[bool]
) -> None:
    """
    Query *app* for minimized windows and append child items to *menu*.

    *ax_denied_shown* is a one-element list used as a mutable flag so the
    "enable Accessibility" prompt is only inserted once across all apps.
    """
    pid = app.processIdentifier()
    status, windows = get_minimized_windows(pid)

    if status == AccessibilityStatus.DENIED:
        if not ax_denied_shown[0]:
            menu.addItem_(accessibility_prompt_item(target))
            ax_denied_shown[0] = True
        return

    for win in windows:
        menu.addItem_(minimized_window_item(win, target))


# ---------------------------------------------------------------------------
# Full menu rebuild
# ---------------------------------------------------------------------------

def populate_menu(menu, target: object) -> None:
    """
    Clear *menu* and re-populate it with:

    1. Finder (always first)
    2. Persistent Dock apps; running ones include any minimized-window rows
    3. Separator
    4. Other running apps not in the Dock (sorted alphabetically),
       each followed by their minimized-window rows
    5. Separator
    6. "Refresh now" and "Quit" actions
    """
    menu.removeAllItems()

    running_apps    = get_running_regular_apps()
    running_by_path = build_running_by_path(running_apps)

    # Shared mutable flag — ensures the AX permission prompt appears at most once.
    ax_denied_shown: list[bool] = [False]

    # --- Section 1: Finder ---
    finder = get_finder_app()
    if finder is not None:
        menu.addItem_(running_app_item(finder, target))
        _append_minimized_windows(menu, finder, target, ax_denied_shown)
    else:
        menu.addItem_(
            dock_app_item(
                DockEntry(label="Finder", path=FINDER_PATH),
                is_running=False,
                target=target,
            )
        )

    # --- Section 2: Persistent Dock apps ---
    dock_entries = get_persistent_dock_apps()
    dock_paths: set[str] = set()

    for entry in dock_entries:
        dock_paths.add(entry.path)
        app = running_by_path.get(entry.path)

        if app is not None:
            menu.addItem_(running_app_item(app, target))
            _append_minimized_windows(menu, app, target, ax_denied_shown)
        else:
            menu.addItem_(dock_app_item(entry, is_running=False, target=target))

    # --- Separator ---
    menu.addItem_(NSMenuItem.separatorItem())

    # --- Section 3: Running apps NOT in the Dock ---
    extra = _extra_running_apps(running_apps, dock_paths)
    if extra:
        for app in extra:
            menu.addItem_(running_app_item(app, target))
            _append_minimized_windows(menu, app, target, ax_denied_shown)
    else:
        menu.addItem_(disabled_text_item("No other running apps"))

    # --- Section 4: Right-side Dock items (Downloads, folders, files, stacks) ---
    dock_others = get_persistent_dock_others()
    if dock_others:
        menu.addItem_(NSMenuItem.separatorItem())
        for entry in dock_others:
            menu.addItem_(dock_other_item(entry, target))

    # --- Separator + Trash + controls ---
    menu.addItem_(NSMenuItem.separatorItem())
    menu.addItem_(trash_item(target))
    menu.addItem_(NSMenuItem.separatorItem())
    # menu.addItem_(action_item("Refresh now", "refreshMenu:", "", target))
    menu.addItem_(action_item("Quit", "quitApp:", "q", target))


def _extra_running_apps(running_apps: list, dock_paths: set[str]) -> list:
    """Apps that are running but not pinned in the Dock, sorted by name."""
    extras = []
    for app in running_apps:
        bundle_url = app.bundleURL()
        path = bundle_url.path() if bundle_url else None
        if path and path.rstrip("/") in dock_paths:
            continue
        extras.append(app)
    extras.sort(key=lambda a: str(a.localizedName()).lower())
    return extras
