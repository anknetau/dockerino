import Foundation
import AppKit
import ApplicationServices
import CoreFoundation

// MARK: - Constants

let REFRESH_INTERVAL = 5.0

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
let AX_DENIED_LABEL = "  Enable Accessibility to show minimised windows..."

let AX_WINDOWS = kAXWindowsAttribute as String
let AX_MINIMIZED = kAXMinimizedAttribute as String
let AX_TITLE = kAXTitleAttribute as String

// Hover-reorder test
let ENABLE_HOVER_REORDER_TEST = true
let HOVER_REORDER_INTERVAL = 0.7
let HOVER_REORDER_COUNT = 8

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

final class DebugItem: NSObject {
    let id: Int
    let title: String

    init(id: Int, title: String) {
        self.id = id
        self.title = title
    }
}

// MARK: - General helpers

func normalizePath(_ path: String?) -> String? {
    guard var path, !path.isEmpty else { return nil }
    while path.count > 1 && path.hasSuffix("/") {
        path.removeLast()
    }
    return path.isEmpty ? nil : path
}

func fileURLStringToPath(_ value: String?) -> String? {
    guard let value, !value.isEmpty else { return nil }

    if value.hasPrefix("file://"), let url = URL(string: value) {
        return normalizePath(url.path)
    }

    return normalizePath(value)
}

func isFinderPath(_ path: String) -> Bool {
    (normalizePath(path) ?? path) == FINDER_PATH
}

func openAccessibilityPreferencesPane() {
    guard let url = URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility") else {
        return
    }
    NSWorkspace.shared.open(url)
}

func openPath(_ path: String) {
    NSWorkspace.shared.open(URL(fileURLWithPath: path))
}

// MARK: - Anchor icon

func makeAnchorStatusImage() -> NSImage {
    let size = NSSize(width: 18, height: 18)
    let image = NSImage(size: size)
    image.isTemplate = true

    image.lockFocus()

    let path = NSBezierPath()
    path.lineWidth = 2.1
    NSColor.labelColor.setStroke()

    let midX = size.width / 2
    let ringCenterY: CGFloat = 12.0
    let ringRadius: CGFloat = 2.0

    path.appendArc(
        withCenter: NSPoint(x: midX, y: ringCenterY),
        radius: ringRadius,
        startAngle: 0,
        endAngle: 360
    )

    path.move(to: NSPoint(x: midX, y: 9.4))
    path.line(to: NSPoint(x: midX, y: 5.2))

    path.move(to: NSPoint(x: midX - 4.8, y: 7.6))
    path.line(to: NSPoint(x: midX + 4.8, y: 7.6))

    path.move(to: NSPoint(x: midX - 4.8, y: 7.6))
    path.curve(
        to: NSPoint(x: midX - 1.4, y: 2.8),
        controlPoint1: NSPoint(x: midX - 5.0, y: 5.5),
        controlPoint2: NSPoint(x: midX - 4.3, y: 2.9)
    )

    path.move(to: NSPoint(x: midX + 4.8, y: 7.6))
    path.curve(
        to: NSPoint(x: midX + 1.4, y: 2.8),
        controlPoint1: NSPoint(x: midX + 5.0, y: 5.5),
        controlPoint2: NSPoint(x: midX + 4.3, y: 2.9)
    )

    path.move(to: NSPoint(x: midX - 1.9, y: 3.5))
    path.line(to: NSPoint(x: midX, y: 1.8))
    path.line(to: NSPoint(x: midX + 1.9, y: 3.5))

    path.stroke()
    image.unlockFocus()

    return image
}

// MARK: - AX helpers

func axCopyAttributeValue(_ element: AXUIElement, _ attribute: String) -> (AXError, AnyObject?) {
    var value: CFTypeRef?
    let err = AXUIElementCopyAttributeValue(element, attribute as CFString, &value)
    return (err, value as AnyObject?)
}

func axSetAttributeValue(_ element: AXUIElement, _ attribute: String, _ value: CFTypeRef) -> AXError {
    AXUIElementSetAttributeValue(element, attribute as CFString, value)
}

func getAXBool(_ value: AnyObject?) -> Bool {
    if let b = value as? Bool { return b }
    if let n = value as? NSNumber { return n.boolValue }
    return false
}

func getAXString(_ value: AnyObject?) -> String? {
    value as? String
}

// MARK: - Dock preferences

func entriesForDockKey(_ key: CFString) -> [DockEntry] {
    guard let raw = CFPreferencesCopyAppValue(key, DOCK_DOMAIN) else {
        return []
    }

    guard let items = raw as? [[String: Any]] else {
        return []
    }

    var out: [DockEntry] = []

    for item in items {
        guard let tileData = item["tile-data"] as? [String: Any] else {
            continue
        }

        let fileLabel = (tileData["file-label"] as? String) ?? "Unknown"
        let fileData = tileData["file-data"] as? [String: Any]

        let urlString =
            (fileData?["_CFURLString"] as? String) ??
            (fileData?["CFURLString"] as? String)

        guard let path = fileURLStringToPath(urlString) else {
            continue
        }

        if isFinderPath(path) {
            continue
        }

        out.append(DockEntry(label: fileLabel, path: path))
    }

    return out
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
    guard let raw = CFPreferencesCopyAppValue(AUTOHIDE_KEY, DOCK_DOMAIN) else {
        return false
    }

    if let b = raw as? Bool {
        return b
    }
    if let n = raw as? NSNumber {
        return n.boolValue
    }

    return false
}

func restartDock() {
    for app in NSRunningApplication.runningApplications(withBundleIdentifier: "com.apple.dock") {
        app.forceTerminate()
    }
}

func setDockAutohide(_ hidden: Bool) {
    CFPreferencesSetAppValue(AUTOHIDE_KEY, hidden as CFPropertyList, DOCK_DOMAIN)
    _ = CFPreferencesAppSynchronize(DOCK_DOMAIN)
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
    var out: [String: NSRunningApplication] = [:]

    for app in apps {
        guard let path = normalizePath(app.bundleURL?.path) else { continue }
        out[path] = app
    }

    return out
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

    guard let windowsArray = windowsValue as? NSArray else {
        return (.unavailable, [])
    }

    var out: [MinimizedWindow] = []

    for item in windowsArray {
        let anyObject = item as AnyObject
        let win = unsafeBitCast(anyObject, to: AXUIElement.self)

        let (minErr, minValue) = axCopyAttributeValue(win, AX_MINIMIZED)
        guard minErr == .success else { continue }
        guard getAXBool(minValue) else { continue }

        let (_, titleValue) = axCopyAttributeValue(win, AX_TITLE)
        let title = getAXString(titleValue).flatMap { $0.isEmpty ? nil : $0 } ?? "(Untitled)"

        out.append(MinimizedWindow(title: title, pid: pid, axRef: win))
    }

    return (.ok, out)
}

func restoreWindow(_ window: MinimizedWindow) {
    _ = axSetAttributeValue(window.axRef, AX_MINIMIZED, kCFBooleanFalse)
    _ = AXUIElementPerformAction(window.axRef, kAXRaiseAction as CFString)

    var app: NSRunningApplication?

    if let bundleID = pidToBundleID(window.pid) {
        app = NSRunningApplication.runningApplications(withBundleIdentifier: bundleID).first
    }

    if app == nil {
        app = appForPID(window.pid)
    }

    app?.activate(options: [.activateAllWindows])
}

// MARK: - Debug reorder section

func makeInitialDebugItems() -> [DebugItem] {
    (1...HOVER_REORDER_COUNT).map { i in
        DebugItem(id: i, title: "Test Item \(i)")
    }
}

func rotateDebugItems(_ items: inout [DebugItem]) {
    guard items.count > 1 else { return }
    let first = items.removeFirst()
    items.append(first)
}

// For a harsher test, replace the function above with this:
// func rotateDebugItems(_ items: inout [DebugItem]) {
//     items.shuffle()
// }

func appendDebugTestSection(_ menu: NSMenu, _ items: [DebugItem], _ target: AnyObject) {
    menu.addItem(.separator())
    menu.addItem(disabledTextItem("Hover reorder test"))

    for itemModel in items {
        let item = makeItem(itemModel.title, #selector(AppDelegate.debugItemSelected(_:)), target)
        item.representedObject = itemModel
        menu.addItem(item)
    }
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

func dockOtherItem(_ entry: DockEntry, _ target: AnyObject) -> NSMenuItem {
    let item = makeItem(entry.label, #selector(AppDelegate.openDockApp(_:)), target)
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
        let normalized = normalizePath(path) ?? path
        return !dockPaths.contains(normalized)
    }

    return extras.sorted {
        ($0.localizedName ?? "").localizedLowercase < ($1.localizedName ?? "").localizedLowercase
    }
}

func populateMenu(_ menu: NSMenu, _ target: AppDelegate, debugItems: [DebugItem]) {
    menu.removeAllItems()

    let runningApps = getRunningRegularApps()
    let runningByPath = buildRunningByPath(runningApps)

    var axDeniedShown = false

    if let finder = getFinderApp() {
        menu.addItem(runningAppItem(finder, target))
        appendMinimizedWindows(to: menu, app: finder, target: target, axDeniedShown: &axDeniedShown)
    } else {
        menu.addItem(dockAppItem(DockEntry(label: "Finder", path: FINDER_PATH), isRunning: false, target: target))
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

    let extras = extraRunningApps(runningApps, dockPaths: dockPaths)
    if extras.isEmpty {
        menu.addItem(disabledTextItem("No other running apps"))
    } else {
        for app in extras {
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

    if ENABLE_HOVER_REORDER_TEST {
        appendDebugTestSection(menu, debugItems, target)
    }

    menu.addItem(.separator())
    menu.addItem(dockVisibilityItem(target))
    menu.addItem(actionItem("Quit", #selector(AppDelegate.quitApp(_:)), "q", target))
}

// MARK: - App delegate

final class AppDelegate: NSObject, NSApplicationDelegate, NSMenuDelegate {
    var statusItem: NSStatusItem?
    var menu: NSMenu?
    var refreshTimer: Timer?
    var hoverReorderTimer: Timer?
    var debugItems: [DebugItem] = makeInitialDebugItems()
    var isMenuOpen = false

    func applicationDidFinishLaunching(_ notification: Notification) {
        setupStatusItem()
        setupMenu()
        setupRefreshTimer()
    }

    func setupStatusItem() {
        let item = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)

        if let button = item.button {
            button.title = ""
            button.image = makeAnchorStatusImage()
            button.imagePosition = .imageOnly
        }

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
        refreshTimer = Timer(
            timeInterval: 1.0,
            target: self,
            selector: #selector(timerFired(_:)),
            userInfo: nil,
            repeats: true
        )
    }

    func rebuildMenu() {
        guard let menu else { return }
        populateMenu(menu, self, debugItems: debugItems)
    }

    func startHoverReorderTimer() {
        print("startHoverReorderTimer")
        guard ENABLE_HOVER_REORDER_TEST else { return }
        print("startHoverReorderTimer2")
        guard hoverReorderTimer == nil else { return }
        print("startHoverReorderTimer3")

        hoverReorderTimer = Timer(
            timeInterval: 0.7,
            target: self,
            selector: #selector(hoverReorderTick(_:)),
            userInfo: nil,
            repeats: true
        )
        RunLoop.main.add(hoverReorderTimer!, forMode: .common)
    }

    func stopHoverReorderTimer() {
        print("stopHoverReorderTimer")
        hoverReorderTimer?.invalidate()
        hoverReorderTimer = nil
    }

    func menuWillOpen(_ menu: NSMenu) {
        print("menuWillOpen")
        isMenuOpen = true
        rebuildMenu()
        startHoverReorderTimer()
    }

    func menuDidClose(_ menu: NSMenu) {
        print("menuDidClose")
        isMenuOpen = false
        stopHoverReorderTimer()
    }

    @objc func hoverReorderTick(_ sender: Any?) {
        print("hoverReorderTick")

        rotateDebugItems(&debugItems)

        if isMenuOpen {
            rebuildMenu()
        }
    }

    @objc func timerFired(_ sender: Any?) {
        print("timer fired")
        if !isMenuOpen {
            rebuildMenu()
        }
    }

    @objc func activateApp(_ sender: NSMenuItem) {
        guard let app = sender.representedObject as? NSRunningApplication else { return }
        app.activate(options: [.activateAllWindows])
    }

    @objc func openDockApp(_ sender: NSMenuItem) {
        guard let path = sender.representedObject as? String else { return }
        openPath(path)
    }

    @objc func openTrash(_ sender: NSMenuItem) {
        guard let path = sender.representedObject as? String else { return }
        openPath(path)
    }

    @objc func restoreWindowAction(_ sender: NSMenuItem) {
        guard let window = sender.representedObject as? MinimizedWindow else { return }
        restoreWindow(window)
    }

    @objc func openAccessibilityPreferences(_ sender: Any?) {
        openAccessibilityPreferencesPane()
    }

    @objc func toggleDockVisibility(_ sender: Any?) {
        _ = toggleDockAutohide()
        rebuildMenu()
    }

    @objc func debugItemSelected(_ sender: NSMenuItem) {
        guard let item = sender.representedObject as? DebugItem else { return }
        print("Selected debug item \(item.id): \(item.title)")
    }

    @objc func quitApp(_ sender: Any?) {
        refreshTimer?.invalidate()
        refreshTimer = nil
        stopHoverReorderTimer()
        NSApp.terminate(nil)
    }
}

// MARK: - Main

let app = NSApplication.shared
app.setActivationPolicy(.accessory)

let delegate = AppDelegate()
app.delegate = delegate
app.run()