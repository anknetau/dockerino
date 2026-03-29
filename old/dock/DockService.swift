// MARK: - Business Logic

import Foundation
import ApplicationServices
import AppKit

/// Handles all logic related to finding and inspecting the macOS Dock.
struct DockService {
    
    /// Finds the Dock application running on the system.
    static func findDockApplication() -> NSRunningApplication? {
        return NSRunningApplication.runningApplications(withBundleIdentifier: "com.apple.dock").first
    }
    
    /// Retrieves the raw AXUIElements representing Dock items.
    static func getDockItems(from dockAX: AXUIElement) -> [AXUIElement] {
        var items: [AXUIElement] = []
        
        // Level 1: Get children of the Dock (usually an AXList)
        var children: CFTypeRef?
        var status = AXUIElementCopyAttributeValue(dockAX, AccessibilityAttribute.children.rawValue as CFString, &children)
        
        guard status == .success,
              let childrenRef = children,
              let childrenArray = childrenRef as? [AXUIElement] else {
            print("Error getting Dock children: \(status)")
            return items
        }
        
        // Level 2: Get children of each AXList (actual dock items)
        for child in childrenArray {
            var listItems: CFTypeRef?
            status = AXUIElementCopyAttributeValue(child, AccessibilityAttribute.children.rawValue as CFString, &listItems)
            
            if status == .success,
               let listItemsRef = listItems,
               let listItemsArray = listItemsRef as? [AXUIElement] {
                items.append(contentsOf: listItemsArray)
            }
        }
        
        return items
    }
    
    /// Extracts detailed information from a single AXUIElement.
    static func getItemInfo(from element: AXUIElement) -> DockItemInfo {
        // 1. Extract Name (AXTitle with AXValue fallback)
        var name: CFTypeRef?
        var status = AXUIElementCopyAttributeValue(element, AccessibilityAttribute.title.rawValue as CFString, &name)
        
        var nameString = "Unknown"
        
        if status == .success, let nameRef = name, let title = nameRef as? String {
            nameString = title
        } else {
            // Fallback to AXValue if AXTitle is not available
            status = AXUIElementCopyAttributeValue(element, AccessibilityAttribute.value.rawValue as CFString, &name)
            if status == .success, let nameRef = name, let value = nameRef as? String {
                nameString = value
            }
        }
        
        // 2. Extract Role and Description
        let role = AXHelper.copyStringValue(from: element, key: .role)
        let roleDesc = AXHelper.copyStringValue(from: element, key: .roleDescription)
        let description = AXHelper.copyOptionalStringValue(from: element, key: .description)
        let enabled = AXHelper.copyBoolValue(from: element, key: .enabled)
        let hidden = AXHelper.copyBoolValue(from: element, key: .hidden)
        
        return DockItemInfo(
            name: nameString,
            role: role,
            roleDescription: roleDesc,
            description: description,
            enabled: enabled,
            hidden: hidden
        )
    }
    
    /// Fetches all Dock item information.
    static func fetchAllDockInfo() -> [DockItemInfo] {
        guard let dockApp = findDockApplication() else {
            return []
        }
        
        guard let dockAX = AXHelper.createApplicationElement(for: dockApp) else {
            return []
        }
        
        let dockItems = getDockItems(from: dockAX)
        
        if dockItems.isEmpty {
            return []
        }
        
        return dockItems.map { getItemInfo(from: $0) }
    }
}
