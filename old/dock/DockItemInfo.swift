// MARK: - Models

import Foundation

/// Represents the metadata of a single item in the Dock.
public struct DockItemInfo {
    let name: String
    let role: String
    let roleDescription: String
    let description: String?
    let enabled: Bool
    let hidden: Bool
    
    /// Creates a DockItemInfo with default values for optional fields.
    init(name: String, role: String, roleDescription: String, description: String? = nil, enabled: Bool = false, hidden: Bool = false) {
        self.name = name
        self.role = role
        self.roleDescription = roleDescription
        self.description = description
        self.enabled = enabled
        self.hidden = hidden
    }
}
