//
// UniversalLinkHandler.swift — Universal Links Support
//
// Colony: Nexus (e4) — Integration
//
// Handles Universal Links for deep linking into Kagami iOS from:
//   - Web links (https://kagami.home/...)
//   - QR codes
//   - NFC tags
//   - Shared links
//
// AASA Configuration required at:
//   https://kagami.home/.well-known/apple-app-site-association
//
// See: apple-app-site-association.json for AASA stub
//
// h(x) >= 0. Always.
//

import Foundation
import OSLog

// MARK: - Universal Link Handler

/// Handles Universal Links for Kagami
@MainActor
final class UniversalLinkHandler: ObservableObject {

    // MARK: - Singleton

    static let shared = UniversalLinkHandler()

    // MARK: - Properties

    @Published var pendingLink: UniversalLink?
    @Published var lastError: UniversalLinkError?

    private let logger = Logger(subsystem: "com.kagami.ios", category: "UniversalLinks")

    // Supported domains
    private let supportedDomains: Set<String> = [
        "kagami.home",
        "www.kagami.home",
        "app.kagami.home"
    ]

    // MARK: - Init

    private init() {}

    // MARK: - URL Handling

    /// Handle an incoming URL (Universal Link or custom scheme)
    /// - Parameter url: The URL to handle
    /// - Returns: True if the URL was handled
    @discardableResult
    func handle(url: URL) -> Bool {
        // Check if it's a custom scheme URL
        if url.scheme == "kagami" {
            return handleCustomScheme(url)
        }

        // Check if it's a Universal Link
        guard let host = url.host, supportedDomains.contains(host) else {
            logger.warning("Unsupported domain: \(url.host ?? "nil")")
            lastError = .unsupportedDomain(url.host ?? "unknown")
            return false
        }

        return handleUniversalLink(url)
    }

    // MARK: - Universal Link Handling

    private func handleUniversalLink(_ url: URL) -> Bool {
        let pathComponents = url.pathComponents.filter { $0 != "/" }

        guard let firstComponent = pathComponents.first else {
            logger.info("Universal link with no path, opening home")
            pendingLink = .home
            return true
        }

        switch firstComponent {
        case "scene", "scenes":
            return handleSceneLink(pathComponents: Array(pathComponents.dropFirst()), queryItems: queryItems(from: url))

        case "room", "rooms":
            return handleRoomLink(pathComponents: Array(pathComponents.dropFirst()), queryItems: queryItems(from: url))

        case "hub":
            pendingLink = .hub
            return true

        case "settings":
            return handleSettingsLink(pathComponents: Array(pathComponents.dropFirst()))

        case "camera", "cameras":
            return handleCameraLink(pathComponents: Array(pathComponents.dropFirst()))

        case "share":
            return handleShareLink(pathComponents: Array(pathComponents.dropFirst()), queryItems: queryItems(from: url))

        case "invite":
            return handleInviteLink(queryItems: queryItems(from: url))

        default:
            logger.warning("Unknown universal link path: \(firstComponent)")
            lastError = .unknownPath(firstComponent)
            return false
        }
    }

    // MARK: - Custom Scheme Handling

    private func handleCustomScheme(_ url: URL) -> Bool {
        guard let host = url.host else {
            pendingLink = .home
            return true
        }

        let pathComponents = url.pathComponents.filter { $0 != "/" }

        switch host {
        case "scene":
            if let sceneName = pathComponents.first ?? queryItems(from: url)["name"] {
                pendingLink = .scene(name: sceneName.replacingOccurrences(of: "_", with: " "))
                return true
            }

        case "room":
            if let roomId = pathComponents.first ?? queryItems(from: url)["id"] {
                pendingLink = .room(id: roomId)
                return true
            }

        case "hub":
            pendingLink = .hub
            return true

        case "settings":
            pendingLink = .settings
            return true

        case "command":
            if let command = pathComponents.first?.removingPercentEncoding ?? queryItems(from: url)["text"] {
                pendingLink = .command(text: command)
                return true
            }

        default:
            break
        }

        logger.warning("Unhandled custom scheme URL: \(url.absoluteString)")
        return false
    }

    // MARK: - Path Handlers

    private func handleSceneLink(pathComponents: [String], queryItems: [String: String]) -> Bool {
        guard let sceneName = pathComponents.first ?? queryItems["name"] else {
            logger.warning("Scene link missing scene name")
            lastError = .missingParameter("scene name")
            return false
        }

        let normalizedName = sceneName.replacingOccurrences(of: "_", with: " ")
        pendingLink = .scene(name: normalizedName)

        logger.info("Scene link: \(normalizedName)")
        return true
    }

    private func handleRoomLink(pathComponents: [String], queryItems: [String: String]) -> Bool {
        guard let roomId = pathComponents.first ?? queryItems["id"] else {
            logger.warning("Room link missing room ID")
            lastError = .missingParameter("room ID")
            return false
        }

        pendingLink = .room(id: roomId)
        logger.info("Room link: \(roomId)")
        return true
    }

    private func handleSettingsLink(pathComponents: [String]) -> Bool {
        if let section = pathComponents.first {
            pendingLink = .settingsSection(section: section)
        } else {
            pendingLink = .settings
        }
        return true
    }

    private func handleCameraLink(pathComponents: [String]) -> Bool {
        if let cameraId = pathComponents.first {
            pendingLink = .camera(id: cameraId)
        } else {
            pendingLink = .cameras
        }
        return true
    }

    private func handleShareLink(pathComponents: [String], queryItems: [String: String]) -> Bool {
        guard let shareType = pathComponents.first else {
            lastError = .missingParameter("share type")
            return false
        }

        switch shareType {
        case "scene":
            if let sceneId = pathComponents.dropFirst().first ?? queryItems["id"] {
                pendingLink = .sharedScene(id: sceneId)
                return true
            }

        case "routine":
            if let routineId = pathComponents.dropFirst().first ?? queryItems["id"] {
                pendingLink = .sharedRoutine(id: routineId)
                return true
            }

        default:
            break
        }

        lastError = .invalidShareLink
        return false
    }

    private func handleInviteLink(queryItems: [String: String]) -> Bool {
        guard let inviteCode = queryItems["code"] else {
            lastError = .missingParameter("invite code")
            return false
        }

        pendingLink = .invite(code: inviteCode)
        logger.info("Invite link: \(inviteCode)")
        return true
    }

    // MARK: - Helpers

    private func queryItems(from url: URL) -> [String: String] {
        guard let components = URLComponents(url: url, resolvingAgainstBaseURL: false),
              let items = components.queryItems else {
            return [:]
        }

        return Dictionary(uniqueKeysWithValues: items.compactMap { item in
            guard let value = item.value else { return nil }
            return (item.name, value)
        })
    }

    // MARK: - Clear

    /// Clear the pending link
    func clearPendingLink() {
        pendingLink = nil
        lastError = nil
    }
}

// MARK: - Universal Link Types

/// Represents a parsed Universal Link
enum UniversalLink: Equatable, Hashable {
    case home
    case scene(name: String)
    case room(id: String)
    case hub
    case settings
    case settingsSection(section: String)
    case camera(id: String)
    case cameras
    case command(text: String)
    case sharedScene(id: String)
    case sharedRoutine(id: String)
    case invite(code: String)

    /// Title for display
    var title: String {
        switch self {
        case .home:
            return "Home"
        case .scene(let name):
            return name
        case .room(let id):
            return "Room \(id)"
        case .hub:
            return "Hub"
        case .settings:
            return "Settings"
        case .settingsSection(let section):
            return section.capitalized
        case .camera(let id):
            return "Camera \(id)"
        case .cameras:
            return "Cameras"
        case .command(let text):
            return text
        case .sharedScene(let id):
            return "Shared Scene"
        case .sharedRoutine(let id):
            return "Shared Routine"
        case .invite:
            return "Invite"
        }
    }
}

// MARK: - Universal Link Error

/// Errors that can occur during Universal Link handling
enum UniversalLinkError: Error, LocalizedError {
    case unsupportedDomain(String)
    case unknownPath(String)
    case missingParameter(String)
    case invalidShareLink
    case expiredLink
    case permissionDenied

    var errorDescription: String? {
        switch self {
        case .unsupportedDomain(let domain):
            return "Unsupported domain: \(domain)"
        case .unknownPath(let path):
            return "Unknown link path: \(path)"
        case .missingParameter(let param):
            return "Missing required parameter: \(param)"
        case .invalidShareLink:
            return "Invalid share link"
        case .expiredLink:
            return "This link has expired"
        case .permissionDenied:
            return "You don't have permission to access this resource"
        }
    }
}

// MARK: - AASA Configuration

/// Apple App Site Association configuration helper
/// This generates the AASA JSON that should be hosted at:
/// https://kagami.home/.well-known/apple-app-site-association
struct AASAConfiguration {

    /// Team ID for Apple Developer account
    /// NOTE: Set via build configuration or environment variable in production
    static let teamId: String = {
        // Try to get from build configuration first
        if let teamId = Bundle.main.object(forInfoDictionaryKey: "KAGAMI_TEAM_ID") as? String,
           !teamId.isEmpty, teamId != "XXXXXXXXXX" {
            return teamId
        }
        // Fallback for development - will fail AASA verification
        // Production builds MUST set KAGAMI_TEAM_ID in Info.plist
        #if DEBUG
        return "DEVELOPMENT"
        #else
        fatalError("KAGAMI_TEAM_ID must be set in Info.plist for production builds")
        #endif
    }()

    /// App Bundle ID
    static let bundleId = "com.kagami.ios"

    /// Generate AASA JSON
    static func generateJSON() -> String {
        """
        {
            "applinks": {
                "apps": [],
                "details": [
                    {
                        "appID": "\(teamId).\(bundleId)",
                        "paths": [
                            "/scene/*",
                            "/scenes/*",
                            "/room/*",
                            "/rooms/*",
                            "/hub",
                            "/hub/*",
                            "/settings",
                            "/settings/*",
                            "/camera/*",
                            "/cameras/*",
                            "/share/*",
                            "/invite"
                        ]
                    }
                ]
            },
            "webcredentials": {
                "apps": [
                    "\(teamId).\(bundleId)"
                ]
            }
        }
        """
    }
}

/*
 * Mirror
 * Universal Links bridge web and app.
 * h(x) >= 0. Always.
 */
