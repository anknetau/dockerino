import Foundation
import AppKit
import ApplicationServices
import CoreFoundation

// MARK: - Constants

let REFRESH_INTERVAL: TimeInterval = 5.0
let STATUS_ITEM_TITLE = "D"

let DOCK_DOMAIN = "com.apple.dock" as CFString
let PERSISTENT_APPS_KEY = "persistent-apps" as CFString
let PERSISTENT_OTHERS_KEY = "persistent-others" as CFString
let AUTOHIDE_KEY = "autohide" as CFString

let FINDER_BUNDLE_ID = "com.apple.finder"
let FINDER_PATH = "/System/Library/CoreServices/Finder.app"
let TRASH_PATH = (NSHomeDirectory() as NSString).appendingPathComponent(".Trash")

let ICON_SIZE = NSSize(width: 16, height: 16)
let RUNNING_PREFIX = "• "
let STOPPED_PREFIX = "  "
let WINDOW_PREFIX = "      ↳ "
let AX_DENIED_LABEL = "  ⚠ Enable Accessibility to show minimised windows…"

let AX_WINDOWS = kAXWindowsAttribute as String
let AX_MINIMIZED = kAXMinimizedAttribute as String
let AX_TITLE = kAXTitleAttribute as String

// MARK: - Models

struct DockEntry {
    let label: String
    let path: String
}

enum AccessibilityStatus {
    case ok
    case denied
    case unavailable
}

final class MinimizedWindow: NSObject {
    let title: String
    let pid: pid_t
    let axRef: AXUIElement

    init(title: String, pid: pid_t, axRef: AXUIElement) {
        self.title = title
        self.pid = pid
        self.axRef = axRef
    }
}

// MARK: - CF / AX helpers

func cfDictionaryToSwiftDictionary(_ value: CFPropertyList?) -> [String: Any] {
    guard let dict = value as? [String: Any] else { return [:] }
    return dict
}

func cfURLStringToPath(_ url: String?) -> String? {
    guard let url, !url.isEmpty else { return nil }
    if url.hasPrefix("file://"), let parsed = URL(string: url) {
        return parsed.path
    }
    return url
}

func normalizePath(_ path: String?) -> String? {
    guard var path, !path.isEmpty else { return nil }
    while path.hasSuffix("/") && path.count > 1 {
        path.removeLast()
    }
    return path.isEmpty ? nil : path
}

func isFinderEntry(_ path: String) -> Bool {
    path.hasSuffix(FINDER_PATH.trimmingCharacters(in: CharacterSet(charactersIn: "/")))
}

func axCopyAttributeValue(_ element: AXUIElement, _ attribute: String) -> (AXError, AnyObject?) {
    var value: CFTypeRef?
    let err = AXUIElementCopyAttributeValue(element, attribute as CFString, &value)
    return (err, value)
}

func axSetAttributeValue(_ element: AXUIElement, _ attribute: String, _ value: CFTypeRef) -> AXError {
    AXUIElementSetAttributeValue(element, attribute as CFString, value)
}

func accessibilityPermissionGranted() -> Bool {
    AXIsProcessTrustedWithOptions(nil)
}

func openAccessibilityPreferencesPane() {
    guard let url = URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility") else {
        return
    }
    NSWorkspace.shared.open(url)
}

// MARK: - Dock preferences

func entriesForDockKey(_ key: CFString) -> [DockEntry] {
    let raw = CFPreferencesCopyAppValue(key, DOCK_DOMAIN)
    guard let items = raw as? [[String: Any]] else {
        return []
    }

    var entries: [DockEntry] = []

    for item in items {
        let tileData = item["tile-data"] as? [String: Any] ?? [:]
        let fileData = tileData["file-data"] as? [String: Any] ?? [:]

        let label = (tileData["file-label"] as? String) ?? "Unknown"
        let url = fileData["_CFURLString"] as? String
        let path = normalizePath(cfURLStringToPath(url))

        guard let path else { continue }
        if isFinderEntry(path) { continue }

        entries.append(DockEntry(label: label, path: path))
    }

    return entries
}

func getPersistentDockApps() -> [DockEntry] {
    entriesForDockKey(PERSISTENT_APPS_KEY)
}

func getPersistentDockOthers() -> [DockEntry] {
    entriesForDockKey(PERSISTENT_OTHERS_KEY)
}

func getTrashEntry() -> DockEntry {
    DockEntry(label: "Trash", path: TRASH_PATH)
}

// MARK: - Dock autohide

func getDockAutohide() -> Bool {
    let value = CFPreferencesCopyAppValue(AUTOHIDE_KEY, DOCK_DOMAIN)
    if let b = value as? Bool { return b }
    if let n = value as? NSNumber { return n.boolValue }
    return false
}

func restartDock() {
    let apps = NSRunningApplication.runningApplications(withBundleIdentifier: "com.apple.dock")
    for app in apps {
        app.forceTerminate()
    }
}

func setDockAutohide(_ hidden: Bool) {
    CFPreferencesSetAppValue(AUTOHIDE_KEY, hidden as CFBoolean, DOCK_DOMAIN)
    let ok = CFPreferencesAppSynchronize(DOCK_DOMAIN)
    if !ok {
        fputs("Failed to synchronize Dock preferences\n", stderr)
        return
    }
    restartDock()
}

@discardableResult
func toggleDockAutohide() -> Bool {
    let newValue = !getDockAutohide()
    setDockAutohide(newValue)
    return newValue
}

// MARK: - Running apps

func getRunningRegularApps() -> [NSRunningApplication] {
    NSWorkspace.shared.runningApplications.filter { app in
        guard app.localizedName != nil else { return false }
        guard app.activationPolicy == .regular else { return false }
        guard app.bundleIdentifier != FINDER_BUNDLE_ID else { return false }
        return true
    }
}

func buildRunningByPath(_ apps: [NSRunningApplication]) -> [String: NSRunningApplication] {
    var mapping: [String: NSRunningApplication] = [:]
    for app in apps {
        guard let path = normalizePath(app.bundleURL?.path) else { continue }
        mapping[path] = app
    }
    return mapping
}

func getFinderApp() -> NSRunningApplication? {
    NSRunningApplication.runningApplications(withBundleIdentifier: FINDER_BUNDLE_ID).first
}

func appForPID(_ pid: pid_t) -> NSRunningApplication? {
    NSRunningApplication(processIdentifier: pid)
}

func pidToBundleID(_ pid: pid_t) -> String? {
    appForPID(pid)?.bundleIdentifier
}

// MARK: - Windows / Accessibility

func getMinimizedWindows(pid: pid_t) -> (AccessibilityStatus, [MinimizedWindow]) {
    let appRef = AXUIElementCreateApplication(pid)

    let (err, windowsValue) = axCopyAttributeValue(appRef, AX_WINDOWS)

    if err == .apiDisabled {
        return (.denied, [])
    }

    guard err == .success else {
        return (.unavailable, [])
    }

    guard let windows = windowsValue as? [Any], !windows.isEmpty else {
        return (.unavailable, [])
    }

    var minimized: [MinimizedWindow] = []

    for item in windows {
        let win = unsafeBitCast(item as AnyObject, to: AXUIElement.self)

        let (minErr, minValue) = axCopyAttributeValue(win, AX_MINIMIZED)
        if minErr != .success {
            continue
        }

        let isMinimized: Bool = {
            if let b = minValue as? Bool { return b }
            if let n = minValue as? NSNumber { return n.boolValue }
            return false
        }()

        if !isMinimized {
            continue
        }

        let (_, rawTitle) = axCopyAttributeValue(win, AX_TITLE)
        let title = (rawTitle as? String).flatMap { $0.isEmpty ? nil : $0 } ?? "(Untitled)"

        minimized.append(MinimizedWindow(title: title, pid: pid, axRef: win))
    }

    return (.ok, minimized)
}

func restoreWindow(_ window: MinimizedWindow) {
    _ = axSetAttributeValue(window.axRef, AX_MINIMIZED, kCFBooleanFalse)
    AXUIElementPerformAction(window.axRef, kAXRaiseAction as CFString)

    var app: NSRunningApplication?
    if let bundleID = pidToBundleID(window.pid) {
        app = NSRunningApplication.runningApplications(withBundleIdentifier: bundleID).first
    }
    if app == nil {
        app = appForPID(window.pid)
    }

    app?.activate(options: [.activateAllWindows])
}

// MARK: - Menu item builders

func makeItem(_ title: String, _ action: Selector?, _ target: AnyObject?) -> NSMenuItem {
    let item = NSMenuItem(title: title, action: action, keyEquivalent: "")
    item.target = target
    return item
}

func applyIcon(_ item: NSMenuItem, image: NSImage?) {
    guard let image else { return }
    guard let copy = image.copy() as? NSImage else { return }
    copy.size = ICON_SIZE
    item.image = copy
}

func applyIcon(_ item: NSMenuItem, path: String) {
    let icon = NSWorkspace.shared.icon(forFile: path)
    applyIcon(item, image: icon)
}

func formatTitle(_ name: String, isRunning: Bool) -> String {
    (isRunning ? RUNNING_PREFIX : STOPPED_PREFIX) + name
}

func runningAppItem(_ app: NSRunningApplication, _ target: AnyObject) -> NSMenuItem {
    let title = formatTitle(app.localizedName ?? "Unknown", isRunning: true)
    let item = makeItem(title, #selector(AppDelegate.activateApp(_:)), target)
    item.representedObject = app
    applyIcon(item, image: app.icon)
    return item
}

func dockAppItem(_ entry: DockEntry, isRunning: Bool, target: AnyObject) -> NSMenuItem {
    let title = formatTitle(entry.label, isRunning: isRunning)
    let item = makeItem(title, #selector(AppDelegate.openDockApp(_:)), target)
    item.representedObject = entry.path as NSString
    applyIcon(item, path: entry.path)
    return item
}

func trashItem(_ target: AnyObject) -> NSMenuItem {
    let entry = getTrashEntry()
    let item = makeItem(entry.label, #selector(AppDelegate.openTrash(_:)), target)
    item.representedObject = entry.path as NSString
    applyIcon(item, path: entry.path)
    return item
}

func dockOtherItem(_ entry: DockEntry, _ target: AnyObject) -> NSMenuItem {
    let item = makeItem(entry.label, #selector(AppDelegate.openDockApp(_:)), target)
    item.representedObject = entry.path as NSString
    applyIcon(item, path: entry.path)
    return item
}

func minimizedWindowItem(_ window: MinimizedWindow, _ target: AnyObject) -> NSMenuItem {
    let item = makeItem(WINDOW_PREFIX + window.title, #selector(AppDelegate.restoreWindowAction(_:)), target)
    item.representedObject = window
    return item
}

func accessibilityPromptItem(_ target: AnyObject) -> NSMenuItem {
    makeItem(AX_DENIED_LABEL, #selector(AppDelegate.openAccessibilityPreferences(_:)), target)
}

func disabledTextItem(_ title: String) -> NSMenuItem {
    let item = NSMenuItem(title: title, action: nil, keyEquivalent: "")
    item.isEnabled = false
    return item
}

func actionItem(_ title: String, _ action: Selector, _ key: String, _ target: AnyObject) -> NSMenuItem {
    let item = NSMenuItem(title: title, action: action, keyEquivalent: key)
    item.target = target
    return item
}

func dockVisibilityItem(_ target: AnyObject) -> NSMenuItem {
    let title = getDockAutohide() ? "Show Dock" : "Hide Dock"
    return actionItem(title, #selector(AppDelegate.toggleDockVisibility(_:)), "", target)
}

// MARK: - Menu population

func appendMinimizedWindows(
    to menu: NSMenu,
    app: NSRunningApplication,
    target: AppDelegate,
    axDeniedShown: inout Bool
) {
    let (status, windows) = getMinimizedWindows(pid: app.processIdentifier)

    if status == .denied {
        if !axDeniedShown {
            menu.addItem(accessibilityPromptItem(target))
            axDeniedShown = true
        }
        return
    }

    for win in windows {
        menu.addItem(minimizedWindowItem(win, target))
    }
}

func extraRunningApps(_ runningApps: [NSRunningApplication], dockPaths: Set<String>) -> [NSRunningApplication] {
    let extras = runningApps.filter { app in
        guard let path = app.bundleURL?.path else { return true }
        return !dockPaths.contains(path.trimmingCharacters(in: CharacterSet(charactersIn: "/")))
    }

    return extras.sorted {
        ($0.localizedName ?? "").localizedLowercase < ($1.localizedName ?? "").localizedLowercase
    }
}

func populateMenu(_ menu: NSMenu, _ target: AppDelegate) {
    menu.removeAllItems()

    let runningApps = getRunningRegularApps()
    let runningByPath = buildRunningByPath(runningApps)

    var axDeniedShown = false

    if let finder = getFinderApp() {
        menu.addItem(runningAppItem(finder, target))
        appendMinimizedWindows(to: menu, app: finder, target: target, axDeniedShown: &axDeniedShown)
    } else {
        menu.addItem(
            dockAppItem(
                DockEntry(label: "Finder", path: FINDER_PATH),
                isRunning: false,
                target: target
            )
        )
    }

    let dockEntries = getPersistentDockApps()
    var dockPaths = Set<String>()

    for entry in dockEntries {
        dockPaths.insert(entry.path)

        if let app = runningByPath[entry.path] {
            menu.addItem(runningAppItem(app, target))
            appendMinimizedWindows(to: menu, app: app, target: target, axDeniedShown: &axDeniedShown)
        } else {
            menu.addItem(dockAppItem(entry, isRunning: false, target: target))
        }
    }

    menu.addItem(.separator())

    let extra = extraRunningApps(runningApps, dockPaths: dockPaths)
    if extra.isEmpty {
        menu.addItem(disabledTextItem("No other running apps"))
    } else {
        for app in extra {
            menu.addItem(runningAppItem(app, target))
            appendMinimizedWindows(to: menu, app: app, target: target, axDeniedShown: &axDeniedShown)
        }
    }

    let dockOthers = getPersistentDockOthers()
    if !dockOthers.isEmpty {
        menu.addItem(.separator())
        for entry in dockOthers {
            menu.addItem(dockOtherItem(entry, target))
        }
    }

    menu.addItem(trashItem(target))

    menu.addItem(.separator())
    menu.addItem(dockVisibilityItem(target))
    menu.addItem(actionItem("Quit", #selector(AppDelegate.quitApp(_:)), "q", target))
}

// MARK: - App delegate

final class AppDelegate: NSObject, NSApplicationDelegate, NSMenuDelegate {
    var statusItem: NSStatusItem?
    var menu: NSMenu?
    var refreshTimer: Timer?

    func applicationDidFinishLaunching(_ notification: Notification) {
        setupStatusItem()
        setupMenu()
        setupRefreshTimer()
    }

    func setupStatusItem() {
        let item = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        item.button?.title = STATUS_ITEM_TITLE
        self.statusItem = item
    }

    func setupMenu() {
        let menu = NSMenu()
        menu.delegate = self
        statusItem?.menu = menu
        self.menu = menu
        rebuildMenu()
    }

    func setupRefreshTimer() {
        refreshTimer = Timer.scheduledTimer(
            timeInterval: REFRESH_INTERVAL,
            target: self,
            selector: #selector(timerFired(_:)),
            userInfo: nil,
            repeats: true
        )
    }

    func rebuildMenu() {
        guard let menu else { return }
        populateMenu(menu, self)
    }

    func menuWillOpen(_ menu: NSMenu) {
        rebuildMenu()
    }


    @objc func activateApp(_ sender: NSMenuItem) {
        guard let app = sender.representedObject as? NSRunningApplication else { return }
        app.activate(options: [.activateAllWindows])
    }

    @objc func openDockApp(_ sender: NSMenuItem) {
        guard let path = sender.representedObject as? String else { return }
        NSWorkspace.shared.open(URL(fileURLWithPath: path))
    }

    @objc func openTrash(_ sender: NSMenuItem) {
        guard let path = sender.representedObject as? String else { return }
        NSWorkspace.shared.open(URL(fileURLWithPath: path))
    }

    @objc func restoreWindowAction(_ sender: NSMenuItem) {
        guard let window = sender.representedObject as? MinimizedWindow else { return }
        restoreWindow(window)
    }

    @objc func openAccessibilityPreferences(_ sender: Any?) {
        openAccessibilityPreferencesPane()
    }

    @objc func toggleDockVisibility(_ sender: Any?) {
        toggleDockAutohide()
        rebuildMenu()
    }

    @objc func timerFired(_ sender: Any?) {
        rebuildMenu()
    }

    @objc func refreshMenu(_ sender: Any?) {
        rebuildMenu()
    }

    @objc func quitApp(_ sender: Any?) {
        refreshTimer?.invalidate()
        refreshTimer = nil
        NSApp.terminate(nil)
    }
}

// MARK: - Main

let app = NSApplication.shared
app.setActivationPolicy(.accessory)

let delegate = AppDelegate()
app.delegate = delegate
app.run()
