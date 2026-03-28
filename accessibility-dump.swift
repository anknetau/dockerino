import Foundation
import AppKit
import ApplicationServices

func cfTypeName(_ value: CFTypeRef) -> String {
    CFCopyTypeIDDescription(CFGetTypeID(value)) as String
}

func axErrorName(_ err: AXError) -> String {
    switch err {
    case .success: return "success"
    case .failure: return "failure"
    case .illegalArgument: return "illegalArgument"
    case .invalidUIElement: return "invalidUIElement"
    case .invalidUIElementObserver: return "invalidUIElementObserver"
    case .cannotComplete: return "cannotComplete"
    case .attributeUnsupported: return "attributeUnsupported"
    case .actionUnsupported: return "actionUnsupported"
    case .notificationUnsupported: return "notificationUnsupported"
    case .notImplemented: return "notImplemented"
    case .notificationAlreadyRegistered: return "notificationAlreadyRegistered"
    case .notificationNotRegistered: return "notificationNotRegistered"
    case .apiDisabled: return "apiDisabled"
    case .noValue: return "noValue"
    case .parameterizedAttributeUnsupported: return "parameterizedAttributeUnsupported"
    case .notEnoughPrecision: return "notEnoughPrecision"
    @unknown default: return "unknown(\(err.rawValue))"
    }
}

func requestAccessibilityIfNeeded() -> Bool {
    let opts = [kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: true] as CFDictionary
    return AXIsProcessTrustedWithOptions(opts)
}

func attributeNames(of element: AXUIElement) -> [String] {
    var namesCF: CFArray?
    let err = AXUIElementCopyAttributeNames(element, &namesCF)
    guard err == .success, let arr = namesCF as? [String] else {
        return []
    }
    return arr
}

func copyAttribute(_ name: String, from element: AXUIElement) -> (value: Any?, error: AXError?) {
    var value: CFTypeRef?
    let err = AXUIElementCopyAttributeValue(element, name as CFString, &value)
    if err == .success {
        return (value, nil)
    } else {
        return (nil, err)
    }
}

func isAXUIElementValue(_ value: Any) -> Bool {
    let cf = value as CFTypeRef
    return CFGetTypeID(cf) == AXUIElementGetTypeID()
}

func asAXUIElement(_ value: Any) -> AXUIElement {
    unsafeBitCast(value as CFTypeRef, to: AXUIElement.self)
}

func stringifyScalar(_ value: Any) -> String {
    switch value {
    case let s as String:
        return "\"\(s)\""

    case let n as NSNumber:
        return "\(n)"

    case let p as AXValue:
        let type = AXValueGetType(p)
        switch type {
        case .cgPoint:
            var point = CGPoint.zero
            if AXValueGetValue(p, .cgPoint, &point) {
                return "CGPoint(x: \(point.x), y: \(point.y))"
            }

        case .cgSize:
            var size = CGSize.zero
            if AXValueGetValue(p, .cgSize, &size) {
                return "CGSize(width: \(size.width), height: \(size.height))"
            }

        case .cgRect:
            var rect = CGRect.zero
            if AXValueGetValue(p, .cgRect, &rect) {
                return "CGRect(x: \(rect.origin.x), y: \(rect.origin.y), width: \(rect.size.width), height: \(rect.size.height))"
            }

        case .cfRange:
            var range = CFRange()
            if AXValueGetValue(p, .cfRange, &range) {
                return "CFRange(location: \(range.location), length: \(range.length))"
            }

        case .axError:
            var err = AXError.success
            if AXValueGetValue(p, .axError, &err) {
                return "AXError(\(axErrorName(err)))"
            }

        default:
            break
        }
        return "AXValue(type: \(type.rawValue))"

    case let arr as [Any]:
        return "[\(arr.map { stringifyScalar($0) }.joined(separator: ", "))]"

    default:
        let cf = value as CFTypeRef
        return "<\(cfTypeName(cf))> \(value)"
    }
}

func briefElementDescription(_ element: AXUIElement) -> String {
    let names = attributeNames(of: element)
    var parts: [String] = []

    if names.contains(kAXRoleAttribute as String) {
        let result = copyAttribute(kAXRoleAttribute as String, from: element)
        if let role = result.value as? String {
            parts.append("role=\(role)")
        }
    }

    if names.contains(kAXSubroleAttribute as String) {
        let result = copyAttribute(kAXSubroleAttribute as String, from: element)
        if let subrole = result.value as? String {
            parts.append("subrole=\(subrole)")
        }
    }

    if names.contains(kAXTitleAttribute as String) {
        let result = copyAttribute(kAXTitleAttribute as String, from: element)
        if let title = result.value as? String, !title.isEmpty {
            parts.append("title=\(title)")
        }
    }

    if names.contains(kAXDescriptionAttribute as String) {
        let result = copyAttribute(kAXDescriptionAttribute as String, from: element)
        if let desc = result.value as? String, !desc.isEmpty {
            parts.append("description=\(desc)")
        }
    }

    return parts.isEmpty ? "AXUIElement" : parts.joined(separator: ", ")
}

func recurse(
    _ element: AXUIElement,
    indent: String = "",
    path: String = "root",
    visited: inout Set<UInt>
) {
    let oid: UInt = CFHash(element)
    if visited.contains(oid) {
        print("\(indent)\(path): <already visited>")
        return
    }
    visited.insert(oid)

    print("\(indent)\(path): \(briefElementDescription(element))")

    let names = attributeNames(of: element).sorted()

    for name in names {
        let childIndent = indent + "  "
        let result = copyAttribute(name, from: element)

        if let err = result.error {
            print("\(childIndent)@\(name): <error \(axErrorName(err))>")
            continue
        }

        guard let raw = result.value else {
            print("\(childIndent)@\(name): <nil>")
            continue
        }

        if isAXUIElementValue(raw) {
            let child = asAXUIElement(raw)
            print("\(childIndent)@\(name):")
            recurse(child, indent: childIndent + "  ", path: name, visited: &visited)
        } else if let arr = raw as? [Any] {
            var axChildren: [(Int, AXUIElement)] = []

            for (i, item) in arr.enumerated() {
                if isAXUIElementValue(item) {
                    axChildren.append((i, asAXUIElement(item)))
                }
            }

            if !axChildren.isEmpty {
                print("\(childIndent)@\(name): [\(arr.count) items]")
                for (i, child) in axChildren {
                    recurse(child, indent: childIndent + "  ", path: "\(name)[\(i)]", visited: &visited)
                }
            } else {
                print("\(childIndent)@\(name): \(stringifyScalar(arr))")
            }
        } else {
            print("\(childIndent)@\(name): \(stringifyScalar(raw))")
        }
    }
}

func main() {
    guard requestAccessibilityIfNeeded() else {
        fputs("""
        Accessibility permission is required.
        Add this executable or your terminal app in:
        System Settings -> Privacy & Security -> Accessibility

        """, stderr)
        exit(1)
    }

    guard let dockApp = NSRunningApplication.runningApplications(withBundleIdentifier: "com.apple.dock").first else {
        fputs("Could not find the Dock process.\n", stderr)
        exit(2)
    }

    let dockAX = AXUIElementCreateApplication(dockApp.processIdentifier)
    var visited = Set<UInt>()
    recurse(dockAX, visited: &visited)
}

main()