import Foundation
import ApplicationServices
import AppKit

// MARK: - Data Models

/// Information about a single Dock item
struct DockItemInfo {
    let name: String
    let role: String
    let roleDescription: String
    let description: String?
    let enabled: Bool
    let hidden: Bool
}

// MARK: - Dock Helper Functions

/// Retrieves the running Dock application
func getDockApplication() -> NSRunningApplication? {
    NSRunningApplication.runningApplications(withBundleIdentifier: "com.apple.dock").first
}

/// Creates an Accessibility UI element for a given application
func getDockAXElement(_ app: NSRunningApplication) -> AXUIElement? {
    AXUIElementCreateApplication(app.processIdentifier)
}

/// Extracts all dock item elements from the Dock AX element
func getDockItems(_ dockAX: AXUIElement) -> [AXUIElement] {
    var items: [AXUIElement] = []
    
    // First level: get children of the Dock (usually an AXList)
    guard let children = extractAXChildren(dockAX, attribute: "AXChildren") else {
        print("Error: Could not get Dock children")
        return items
    }
    
    // Second level: get children of each AXList (actual dock items)
    for child in children {
        if let listItems = extractAXChildren(child, attribute: "AXChildren") {
            items.append(contentsOf: listItems)
        }
    }
    
    return items
}

/// Helper to extract AXChildren from an element
private func extractAXChildren(_ element: AXUIElement, attribute: String) -> [AXUIElement]? {
    var value: CFTypeRef?
    let status = AXUIElementCopyAttributeValue(element, attribute as CFString, &value)
    
    guard status == .success,
          let children = value as? [AXUIElement] else {
        return nil
    }
    
    return children
}

// MARK: - Item Information

/// Extracts detailed information from a dock item AX element
func getItemInfo(_ element: AXUIElement) -> DockItemInfo {
    func getStringValue(_ attribute: String) -> String? {
        var value: CFTypeRef?
        let status = AXUIElementCopyAttributeValue(element, attribute as CFString, &value)
        
        guard status == .success,
              let typedValue = value as? String else {
            return nil
        }
        
        return typedValue
    }
    
    func getBoolValue(_ attribute: String) -> Bool {
        var value: CFTypeRef?
        let status = AXUIElementCopyAttributeValue(element, attribute as CFString, &value)
        
        guard status == .success,
              let typedValue = value as? Bool else {
            return false
        }
        
        return typedValue
    }
    
    let name = getStringValue("AXTitle") ?? getStringValue("AXValue") ?? "Unknown"
    
    return DockItemInfo(
        name: name,
        role: getStringValue("AXRole") ?? "N/A",
        roleDescription: getStringValue("AXRoleDescription") ?? "N/A",
        description: getStringValue("AXDescription"),
        enabled: getBoolValue("AXEnabled"),
        hidden: getBoolValue("AXHidden")
    )
}

// MARK: - Formatting & Output

/// Centers a string within a specified width
func centerString(_ str: String, width: Int) -> String {
    let padding = max(0, width - str.count)
    let leftPadding = padding / 2
    let rightPadding = padding - leftPadding
    
    return String(repeating: " ", count: leftPadding) + str + String(repeating: " ", count: rightPadding)
}

/// Prints all dock items in a formatted list
func printDockItems(_ items: [AXUIElement]) {
    let separator = String(repeating: "=", count: 60)
    
    print("\n\(separator)")
    print(centerString("DOCK ITEMS", width: 60))
    print("\(separator)\n")
    
    for (index, item) in items.enumerated() {
        let info = getItemInfo(item)
        print("[\(index + 1)] \(info.name)")
        print("    Role: \(info.role)")
        print("    Role Description: \(info.roleDescription)")
        print("    Description: \(info.description ?? "N/A")")
        print("    Enabled: \(info.enabled)")
        print("    Hidden: \(info.hidden)")
        print()
    }
}

// MARK: - Main Execution

/// Entry point for the Dock Item Enumerator
func main() {
    print("Starting Dock Item Enumerator...\n")
    
    guard let dockApp = getDockApplication() else {
        print("Error: Could not find the Dock application.")
        return
    }
    
    print("Found Dock process: \(dockApp.localizedName ?? "Unknown") (PID: \(dockApp.processIdentifier))")
    
    guard let dockAX = getDockAXElement(dockApp) else {
        print("Error: Could not create AXUIElement for Dock.")
        return
    }
    
    let dockItems = getDockItems(dockAX)
    
    if dockItems.isEmpty {
        print("No dock items found.")
        return
    }
    
    print("Found \(dockItems.count) dock item(s)\n")
    printDockItems(dockItems)
}

// Execute main function
main()
