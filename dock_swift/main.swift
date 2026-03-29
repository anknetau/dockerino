// MARK: - Entry Point

// To run, use 


// replace the separators with a simple function that just prints ---, remove the repetition function, it's unnecessary

import Foundation
import AppKit

struct DockInspector {
    static func main() {
        print("Starting Dock Item Enumerator...\n")
        
        guard let dockApp = DockService.findDockApplication() else {
            print("Error: Could not find the Dock application.")
            return
        }
        
        print("Found Dock process: \(dockApp.localizedName ?? "Unknown") with pid \(dockApp.processIdentifier)")
        
        let dockItems = DockService.fetchAllDockInfo()
        
        if dockItems.isEmpty {
            print("No dock items found.")
            return
        }
        
        print("Found \(dockItems.count) dock item(s)\n")
        Formatter.printDockItems(dockItems)
    }
}

DockInspector.main()