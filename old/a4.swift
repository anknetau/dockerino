import Foundation
import ApplicationServices
import AppKit

// MARK: - Dock Item Info
struct DockItemInfo {
    let name: String
    let role: String
    let roleDescription: String
    let description: String?
    let enabled: Bool
    let hidden: Bool
}

// MARK: - Helpers

extension String {
    /// Centers the string within a given width using padding spaces.
    func centered(width: Int) -> String {
        let padding = max(0, width - self.count)
        let leftPadding = padding / 2
        let rightPadding = padding - leftPadding
        return String(repeating: " ", count: leftPadding) + self + String(repeating: " ", count: rightPadding)
    }
}

/// Extracts an AX attribute value safely as a String.
private func extractStringAttribute(
    from element: AXUIElement,
    key: String,
    defaultValue: String = "N/A"
) -> String {
    var value: CFTypeRef?
    let status = AXUIElementCopyAttributeValue(element, key as CFString, &value)
    
    guard status == .success, let rawValue = value, let stringValue = rawValue as? String else {
        return defaultValue
    }
    
    return stringValue
}

/// Extracts an AX attribute value safely as a Bool.
private func extractBoolAttribute(
    from element: AXUIElement,
    key: String,
    defaultValue: Bool = false
) -> Bool {
    var value: CFTypeRef?
    let status = AXUIElementCopyAttributeValue(element, key as CFString, &value)
    
    guard status == .success, let rawValue = value, let boolValue = rawValue as? Bool else {
        return defaultValue
    }
    
    return boolValue
}

/// Extracts an AX attribute value safely as an optional String.
private func extractOptionalStringAttribute(
    from element: AXUIElement,
    key: String
) -> String? {
    var value: CFTypeRef?
    let status = AXUIElementCopyAttributeValue(element, key as CFString, &value)
    
    guard status == .success, let rawValue = value, let stringValue = rawValue as? String else {
        return nil
    }
    
    return stringValue
}

// MARK: - Dock Logic

/// Finds the running Dock application.
func findDockApplication() -> NSRunningApplication? {
    return NSRunningApplication.runningApplications(withBundleIdentifier: "com.apple.dock").first
}

/// Creates an AXUIElement for a given running application.
func createDockAXElement(_ app: NSRunningApplication) -> AXUIElement? {
    return AXUIElementCreateApplication(app.processIdentifier)
}

/// Retrieves dock items by traversing the Accessibility hierarchy.
/// The Dock structure is typically: Dock -> AXList -> AXButton (Items)
func getDockItems(_ dockAX: AXUIElement) -> [AXUIElement] {
    var items: [AXUIElement] = []
    
    // Level 1: Get children of the Dock (usually an AXList)
    var children: CFTypeRef?
    var status = AXUIElementCopyAttributeValue(dockAX, "AXChildren" as CFString, &children)
    
    guard status == .success,
          let childrenRef = children,
          let childrenArray = childrenRef as? [AXUIElement] else {
        print("Error getting Dock children: \(status)")
        return items
    }
    
    // Level 2: Get children of each AXList (actual dock items)
    for child in childrenArray {
        var listItems: CFTypeRef?
        status = AXUIElementCopyAttributeValue(child, "AXChildren" as CFString, &listItems)
        
        if status == .success,
           let listItemsRef = listItems,
           let listItemsArray = listItemsRef as? [AXUIElement] {
            items.append(contentsOf: listItemsArray)
        }
    }
    
    return items
}

/// Extracts detailed information about a specific dock item.
func getItemInfo(_ element: AXUIElement) -> DockItemInfo {
    // Try to get the name from AXTitle
    var name: CFTypeRef?
    var status = AXUIElementCopyAttributeValue(element, "AXTitle" as CFString, &name)
    
    var nameString = "Unknown"
    
    if status == .success, let nameRef = name, let title = nameRef as? String {
        nameString = title
    } else {
        // Fallback to AXValue if AXTitle is not available
        status = AXUIElementCopyAttributeValue(element, "AXValue" as CFString, &name)
        if status == .success, let nameRef = name, let value = nameRef as? String {
            nameString = value
        }
    }
    
    // Get role
    let role = extractStringAttribute(from: element, key: "AXRole")
    
    // Get role description
    let roleDesc = extractStringAttribute(from: element, key: "AXRoleDescription")
    
    // Get description (optional)
    let description = extractOptionalStringAttribute(from: element, key: "AXDescription")
    
    // Get enabled
    let enabled = extractBoolAttribute(from: element, key: "AXEnabled")
    
    // Get hidden
    let hidden = extractBoolAttribute(from: element, key: "AXHidden")
    
    return DockItemInfo(
        name: nameString,
        role: role,
        roleDescription: roleDesc,
        description: description,
        enabled: enabled,
        hidden: hidden
    )
}

/// Prints the dock items to the console in a formatted table.
func printDockItems(_ items: [AXUIElement]) {
    let separator = String(repeating: "=", count: 60)
    
    print("\n\(separator)")
    print("DOCK ITEMS".centered(width: 60))
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

// MARK: - Entry Point
func main() {
    print("Starting Dock Item Enumerator...\n")
    
    guard let dockApp = findDockApplication() else {
        print("Error: Could not find the Dock application.")
        return
    }
    
    print("Found Dock process: \(dockApp.localizedName ?? "Unknown") with pid \(dockApp.processIdentifier)")
    
    guard let dockAX = createDockAXElement(dockApp) else {
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

main()