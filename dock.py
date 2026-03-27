#!/usr/bin/env python3

from CoreFoundation import CFPreferencesCopyAppValue
from urllib.parse import urlparse, unquote


DOCK_DOMAIN = "com.apple.dock"

def file_url_to_path(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    if parsed.scheme != "file":
        return url
    return unquote(parsed.path)


def get_persistent_dock_apps():
    items = CFPreferencesCopyAppValue("persistent-apps", DOCK_DOMAIN) or []
    result = []

    for item in items:
        tile_data = item.get("tile-data", {})
        file_data = tile_data.get("file-data", {})

        result.append({
            "label": tile_data.get("file-label"),
            "path": file_url_to_path(file_data.get("_CFURLString")),
        })

    return result

def dock_items_for_key(key: str):
    items = CFPreferencesCopyAppValue(key, DOCK_DOMAIN) or []
    out = []

    for item in items:
        tile_data = item.get("tile-data", {})

        # Human-readable label, when present
        label = tile_data.get("file-label")

        # Backing file URL/path, when present
        file_data = tile_data.get("file-data", {})
        url_string = file_data.get("_CFURLString")

        out.append({
            "label": label,
            "url": url_string,
        })

    return out


def main():

    for app in get_persistent_dock_apps():
        print(app)

    print("-----")
    apps = dock_items_for_key("persistent-apps")
    others = dock_items_for_key("persistent-others")

    print("Applications side:")
    for item in apps:
        print(f"  - {item['label']!r} -> {item['url']}")

    print("\nOther side:")
    for item in others:
        print(f"  - {item['label']!r} -> {item['url']}")


if __name__ == "__main__":
    main()
