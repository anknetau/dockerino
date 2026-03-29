// MARK: - Constants

import Foundation

/// Enumerates the Accessibility attribute keys used to query Dock items.
enum AccessibilityAttribute: String {
    case children = "AXChildren"
    case title = "AXTitle"
    case value = "AXValue"
    case role = "AXRole"
    case roleDescription = "AXRoleDescription"
    case description = "AXDescription"
    case enabled = "AXEnabled"
    case hidden = "AXHidden"
}
