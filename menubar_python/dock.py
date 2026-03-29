"""
dock.py — reads persistent Dock entries from macOS preferences.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse

from CoreFoundation import CFPreferencesCopyAppValue


_DOCK_DOMAIN = "com.apple.dock"
_PERSISTENT_APPS_KEY = "persistent-apps"
_PERSISTENT_OTHERS_KEY = "persistent-others"

# The Finder is always implicitly first in the Dock but is stored separately.
FINDER_BUNDLE_ID = "com.apple.finder"
FINDER_PATH = "/System/Library/CoreServices/Finder.app"
TRASH_PATH = str(Path.home() / ".Trash")


@dataclass(frozen=True)
class DockEntry:
    label: str
    path: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _cfurl_to_path(url: str | None) -> str | None:
    """Convert a ``file://`` URL string to a POSIX path, or return *url* as-is."""
    if not url:
        return None
    parsed = urlparse(url)
    if parsed.scheme == "file":
        return unquote(parsed.path)
    return url


def _normalize_path(path: str | None) -> str | None:
    """Strip a trailing slash that macOS occasionally appends to bundle paths."""
    if not path:
        return None
    path = str(path).rstrip("/")
    return path or None


def _is_finder_entry(path: str) -> bool:
    return path.endswith(FINDER_PATH.lstrip("/"))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _entries_for_key(key: str) -> list[DockEntry]:
    """Return Dock entries for a given Dock preference-array key."""
    raw_items = CFPreferencesCopyAppValue(key, _DOCK_DOMAIN) or []
    entries: list[DockEntry] = []

    for item in raw_items:
        tile_data = item.get("tile-data", {})
        file_data = tile_data.get("file-data", {})

        label: str = str(tile_data["file-label"]) if tile_data.get("file-label") else "Unknown"
        url: str | None = file_data.get("_CFURLString")
        path = _normalize_path(_cfurl_to_path(url))

        if not path or _is_finder_entry(path):
            continue

        entries.append(DockEntry(label=label, path=path))

    return entries

def get_trash_entry() -> DockEntry:
    """Return the built-in Trash item."""
    return DockEntry(label="Trash", path=TRASH_PATH)


def get_persistent_dock_apps() -> list[DockEntry]:
    """
    Return the list of apps pinned to the Dock (persistent-apps preference).

    Finder is excluded — it is handled separately by the caller because it
    is always running and needs special treatment.
    """
    return _entries_for_key(_PERSISTENT_APPS_KEY)


def get_persistent_dock_others() -> list[DockEntry]:
    """Return the list of right-side Dock items (folders, files, stacks)."""
    return _entries_for_key(_PERSISTENT_OTHERS_KEY)
