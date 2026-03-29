// MARK: - Output Formatting

import Foundation

/// Utility for formatting console output.
///
/// Provides methods for printing dock items in a structured format.
struct Formatter {
    
    /// Prints the dock items in a formatted table.
    /// - Parameters:
    ///   - items: An array of `DockItemInfo` objects to display.
    static func printDockItems(_ items: [DockItemInfo]) {
        print("\n---")
        print("DOCK ITEMS")
        print("---\n")
        
        for (index, item) in items.enumerated() {
            print("[\(index + 1)] \(item.name ?? "Unknown")")
            print("    Role: \(item.role ?? "N/A")")
            print("    Role Description: \(item.roleDescription ?? "N/A")")
            print("    Description: \(item.description ?? "N/A")")
            print("    Enabled: \(item.enabled)")
            print("    Hidden: \(item.hidden)")
            print()
        }
    }
}

