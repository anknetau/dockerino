// MARK: - Accessibility Utilities

import Foundation
import ApplicationServices
import AppKit

/// Helper struct for low-level AXUIElement operations.
struct AXHelper {
    
    /// Creates an AXUIElement for a running application.
    static func createApplicationElement(for app: NSRunningApplication) -> AXUIElement? {
        return AXUIElementCreateApplication(app.processIdentifier)
    }
    
    /// Copies an attribute value safely from an AXUIElement.
    /// - Parameters:
    ///   - element: The AXUIElement to query.
    ///   - key: The attribute key.
    ///   - defaultValue: The value to return if the query fails.
    /// - Returns: The attribute value or the default value.
    static func copyAttributeValue<T>(
        from element: AXUIElement,
        key: AccessibilityAttribute,
        defaultValue: T
    ) -> T {
        var value: CFTypeRef?
        let status = AXUIElementCopyAttributeValue(element, key.rawValue as CFString, &value)
        
        guard status == .success, let rawValue = value else {
            return defaultValue
        }
        
        // Attempt to cast to the desired type
        if let typedValue = rawValue as? T {
            return typedValue
        }
        
        return defaultValue
    }
    
    /// Copies an attribute value as a String.
    static func copyStringValue(from element: AXUIElement, key: AccessibilityAttribute, defaultValue: String = "N/A") -> String {
        return copyAttributeValue(from: element, key: key, defaultValue: defaultValue)
    }
    
    /// Copies an attribute value as a Bool.
    static func copyBoolValue(from element: AXUIElement, key: AccessibilityAttribute, defaultValue: Bool = false) -> Bool {
        return copyAttributeValue(from: element, key: key, defaultValue: defaultValue)
    }
    
    /// Copies an attribute value as an optional String.
    static func copyOptionalStringValue(from element: AXUIElement, key: AccessibilityAttribute) -> String? {
        var value: CFTypeRef?
        let status = AXUIElementCopyAttributeValue(element, key.rawValue as CFString, &value)
        
        guard status == .success, let rawValue = value, let stringValue = rawValue as? String else {
            return nil
        }
        return stringValue
    }
}
