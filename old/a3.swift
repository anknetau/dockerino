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

// MARK: - Main Functions
func getDockApplication() -> NSRunningApplication? {
    return NSRunningApplication.runningApplications(withBundleIdentifier: "com.apple.dock").first
}

func getDockAXElement(_ app: NSRunningApplication) -> AXUIElement? {
    let pid = app.processIdentifier
    // AXUIElementCreateApplication returns optional directly in Swift
    return AXUIElementCreateApplication(pid)
}

func getDockItems(_ dockAX: AXUIElement) -> [AXUIElement] {
    var items: [AXUIElement] = []
    
    // First level: get children of the Dock (usually an AXList)
    var children: CFTypeRef?
    var status = AXUIElementCopyAttributeValue(dockAX, "AXChildren" as CFString, &children)
    
    guard status == .success, let children = children,
          let childrenArray = children as? [AXUIElement] else {
        print("Error getting Dock children: \(status)")
        return items
    }
    
    // Second level: get children of each AXList (actual dock items)
    for child in childrenArray {
        var listItems: CFTypeRef?
        status = AXUIElementCopyAttributeValue(child, "AXChildren" as CFString, &listItems)
        
        if status == .success, let listItems = listItems,
           let listItemsArray = listItems as? [AXUIElement] {
            items.append(contentsOf: listItemsArray)
        }
    }
    
    return items
}

func getItemInfo(_ element: AXUIElement) -> DockItemInfo {
    // Try to get the name
    var name: CFTypeRef?
    var status = AXUIElementCopyAttributeValue(element, "AXTitle" as CFString, &name)
    var nameString = "Unknown"
    
    if status == .success, let name = name, let title = name as? String {
        nameString = title
    } else {
        // Fallback to AXValue
        status = AXUIElementCopyAttributeValue(element, "AXValue" as CFString, &name)
        if status == .success, let name = name, let value = name as? String {
            nameString = value
        }
    }
    
    // Get role
    var role: CFTypeRef?
    status = AXUIElementCopyAttributeValue(element, "AXRole" as CFString, &role)
    let roleString = (status == .success && role != nil) ? (role as! String) : "N/A"
    
    // Get role description
    var roleDesc: CFTypeRef?
    status = AXUIElementCopyAttributeValue(element, "AXRoleDescription" as CFString, &roleDesc)
    let roleDescString = (status == .success && roleDesc != nil) ? (roleDesc as! String) : "N/A"
    
    // Get description
    var description: CFTypeRef?
    status = AXUIElementCopyAttributeValue(element, "AXDescription" as CFString, &description)
    let descriptionString = (status == .success && description != nil) ? (description as! String) : nil
    
    // Get enabled
    var enabled: CFTypeRef?
    status = AXUIElementCopyAttributeValue(element, "AXEnabled" as CFString, &enabled)
    let enabledValue = (status == .success && enabled != nil) ? (enabled as! Bool) : false
    
    // Get hidden
    var hidden: CFTypeRef?
    status = AXUIElementCopyAttributeValue(element, "AXHidden" as CFString, &hidden)
    let hiddenValue = (status == .success && hidden != nil) ? (hidden as! Bool) : false
    
    return DockItemInfo(
        name: nameString,
        role: roleString,
        roleDescription: roleDescString,
        description: descriptionString,
        enabled: enabledValue,
        hidden: hiddenValue
    )
}

func centerString(_ str: String, width: Int) -> String {
    let padding = max(0, width - str.count)
    let leftPadding = padding / 2
    let rightPadding = padding - leftPadding
    return String(repeating: " ", count: leftPadding) + str + String(repeating: " ", count: rightPadding)
}

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

// MARK: - Main
func main() {
    print("Starting Dock Item Enumerator...\n")
    
    guard let dockApp = getDockApplication() else {
        print("Error: Could not find the Dock application.")
        return
    }
    
    // Use String(describing:) to handle optional explicitly
    print("Found Dock process: \(String(describing: dockApp.localizedName)) with pid \(dockApp.processIdentifier)")
    
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

main()
