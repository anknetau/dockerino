from CoreFoundation import CFPreferencesCopyAppValue
from AppKit import NSWorkspace
from urllib.parse import urlparse, unquote


DOCK_DOMAIN = "com.apple.dock"


def file_url_to_path(url):
    if not url:
        return None
    parsed = urlparse(url)
    if parsed.scheme == "file":
        return unquote(parsed.path)
    return url


def read_dock_array(key):
    items = CFPreferencesCopyAppValue(key, DOCK_DOMAIN) or []
    out = []

    for item in items:
        tile_data = item.get("tile-data", {})
        file_data = tile_data.get("file-data", {})

        out.append({
            "label": tile_data.get("file-label"),
            "url": file_data.get("_CFURLString"),
            "path": file_url_to_path(file_data.get("_CFURLString")),
            "raw": item,
        })

    return out


def get_pinned_apps():
    return read_dock_array("persistent-apps")


def get_pinned_others():
    return read_dock_array("persistent-others")


def get_running_dock_apps():
    running = NSWorkspace.sharedWorkspace().runningApplications()
    out = []

    for app in running:
        # activationPolicy == 0 means "regular"
        # In PyObjC this is usually an int-like enum value.
        if app.activationPolicy() != 0:
            continue

        bundle_url = app.bundleURL()
        path = str(bundle_url.path()) if bundle_url else None

        out.append({
            "name": str(app.localizedName()) if app.localizedName() else None,
            "bundle_identifier": str(app.bundleIdentifier()) if app.bundleIdentifier() else None,
            "path": path,
            "pid": app.processIdentifier(),
        })

    return out


def main():
    pinned_apps = get_pinned_apps()
    pinned_others = get_pinned_others()
    running_apps = get_running_dock_apps()

    pinned_app_paths = {
        item["path"] for item in pinned_apps if item["path"]
    }

    running_unpinned = [
        app for app in running_apps
        if app["path"] not in pinned_app_paths
    ]

    dock_model = {
        "finder": {
            "label": "Finder",
            "special": True,
        },
        "pinned_apps": pinned_apps,
        "running_unpinned_apps": running_unpinned,
        "pinned_others": pinned_others,
        "trash": {
            "label": "Trash",
            "special": True,
        },
    }

    print("Finder")
    print()

    print("Pinned apps:")
    for item in dock_model["pinned_apps"]:
        print(f"  {item['label']!r} -> {item['path']}")

    print("\nRunning unpinned apps:")
    for app in dock_model["running_unpinned_apps"]:
        print(f"  {app['name']!r} -> {app['path']}")

    print("\nPinned others:")
    for item in dock_model["pinned_others"]:
        print(f"  {item['label']!r} -> {item['path']}")

    print("\nTrash")


if __name__ == "__main__":
    main()
