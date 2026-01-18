//
// HandoffManager.swift -- Cross-Device Handoff & Continuity
//
// Colony: Nexus (e4) -- Integration
//
// Features:
//   - NSUserActivity for cross-device handoff (iPhone -> iPad -> Mac)
//   - iPad Sidecar support detection
//   - Universal Links deep linking coordination
//   - Continuity Camera integration
//   - Spotlight indexing for scenes and rooms
//
// Architecture:
//   HandoffManager -> NSUserActivity -> Handoff/Continuity Framework
//
// h(x) >= 0. Always.
//

import Foundation
import SwiftUI
import CoreSpotlight
import MobileCoreServices
import UIKit
import OSLog
import Combine

// MARK: - Handoff Activity Types

/// Activity types for NSUserActivity handoff
enum HandoffActivityType: String {
    case viewRoom = "com.kagami.ios.viewRoom"
    case viewScene = "com.kagami.ios.viewScene"
    case controlDevice = "com.kagami.ios.controlDevice"
    case hubChat = "com.kagami.ios.hubChat"
    case settings = "com.kagami.ios.settings"

    /// User-visible title for the activity
    var title: String {
        switch self {
        case .viewRoom: return "View Room"
        case .viewScene: return "View Scene"
        case .controlDevice: return "Control Device"
        case .hubChat: return "Kagami Hub"
        case .settings: return "Settings"
        }
    }

    /// Whether this activity supports handoff
    var supportsHandoff: Bool {
        true
    }

    /// Whether this activity should be indexed in Spotlight
    var isSearchable: Bool {
        switch self {
        case .viewRoom, .viewScene: return true
        default: return false
        }
    }
}

// MARK: - Sidecar Support

/// Detects and manages iPad Sidecar functionality
struct SidecarSupport {

    /// Check if device supports Sidecar (iPad only)
    static var isSupported: Bool {
        #if targetEnvironment(macCatalyst)
        return false
        #else
        return UIDevice.current.userInterfaceIdiom == .pad
        #endif
    }

    /// Check if currently connected as Sidecar display
    static var isConnectedAsSidecar: Bool {
        guard isSupported else { return false }

        // Detect Sidecar by checking for external display with specific characteristics
        let screens = UIScreen.screens
        guard screens.count > 1 else { return false }

        // Sidecar appears as external display
        for screen in screens where screen != UIScreen.main {
            // Sidecar displays have specific DPI and mode characteristics
            let scale = screen.scale
            let nativeScale = screen.nativeScale

            // Sidecar typically has matching scales (not scaled)
            if scale == nativeScale && scale >= 2.0 {
                return true
            }
        }

        return false
    }

    /// Screen info for Sidecar optimization
    struct ScreenInfo {
        let screenCount: Int
        let isPrimarySidecar: Bool
        let externalResolution: CGSize?
    }

    /// Get current screen configuration
    static var screenInfo: ScreenInfo {
        let screens = UIScreen.screens
        var externalRes: CGSize? = nil

        if screens.count > 1, let external = screens.first(where: { $0 != UIScreen.main }) {
            externalRes = external.bounds.size
        }

        return ScreenInfo(
            screenCount: screens.count,
            isPrimarySidecar: isConnectedAsSidecar,
            externalResolution: externalRes
        )
    }
}

// MARK: - Continuity Camera

/// Manages Continuity Camera features
@MainActor
final class ContinuityCameraManager: NSObject, ObservableObject {

    // MARK: - Published State

    @Published private(set) var isAvailable: Bool = false
    @Published private(set) var connectedCameras: [String] = []

    // MARK: - Private

    private let logger = Logger(subsystem: "com.kagami.ios", category: "ContinuityCamera")

    // MARK: - Init

    override init() {
        super.init()
        checkAvailability()
    }

    // MARK: - Availability

    private func checkAvailability() {
        // Continuity Camera requires iOS 16+ and compatible devices
        if #available(iOS 16.0, *) {
            isAvailable = true
        } else {
            isAvailable = false
        }
    }

    // MARK: - Camera Discovery

    /// Start discovering Continuity Camera devices
    func startDiscovery() {
        guard isAvailable else { return }
        logger.info("Starting Continuity Camera discovery")

        // In a real implementation, this would use AVCaptureDevice.DiscoverySession
        // to find external cameras connected via Continuity Camera
    }

    /// Stop discovering cameras
    func stopDiscovery() {
        logger.info("Stopping Continuity Camera discovery")
        connectedCameras = []
    }
}

// MARK: - Handoff Manager

/// Manages cross-device handoff and continuity features
@MainActor
final class HandoffManager: ObservableObject {

    // MARK: - Singleton

    static let shared = HandoffManager()

    // MARK: - Published State

    @Published private(set) var currentActivity: NSUserActivity?
    @Published private(set) var receivedActivity: NSUserActivity?
    @Published private(set) var sidecarInfo: SidecarSupport.ScreenInfo

    // MARK: - Services

    let continuityCamera = ContinuityCameraManager()

    // MARK: - Private

    private let logger = Logger(subsystem: "com.kagami.ios", category: "Handoff")
    private var cancellables = Set<AnyCancellable>()

    // Activity persistence
    private let activityQueue = DispatchQueue(label: "com.kagami.handoff", qos: .userInitiated)

    // MARK: - Init

    private init() {
        self.sidecarInfo = SidecarSupport.screenInfo
        setupScreenNotifications()
    }

    // MARK: - Screen Monitoring

    private func setupScreenNotifications() {
        NotificationCenter.default.publisher(for: UIScreen.didConnectNotification)
            .receive(on: DispatchQueue.main)
            .sink { [weak self] _ in
                self?.updateSidecarInfo()
            }
            .store(in: &cancellables)

        NotificationCenter.default.publisher(for: UIScreen.didDisconnectNotification)
            .receive(on: DispatchQueue.main)
            .sink { [weak self] _ in
                self?.updateSidecarInfo()
            }
            .store(in: &cancellables)
    }

    private func updateSidecarInfo() {
        sidecarInfo = SidecarSupport.screenInfo

        if sidecarInfo.isPrimarySidecar {
            logger.info("Sidecar connection detected")
            // Could optimize UI layout for Sidecar use
        }
    }

    // MARK: - Activity Creation

    /// Create a handoff activity for viewing a room
    /// - Parameters:
    ///   - roomId: The room identifier
    ///   - roomName: Human-readable room name
    /// - Returns: Configured NSUserActivity
    func createRoomActivity(roomId: String, roomName: String) -> NSUserActivity {
        let activity = NSUserActivity(activityType: HandoffActivityType.viewRoom.rawValue)
        activity.title = roomName
        activity.isEligibleForHandoff = true
        activity.isEligibleForSearch = true
        activity.isEligibleForPrediction = true

        // User info for handoff
        activity.userInfo = [
            "roomId": roomId,
            "roomName": roomName,
            "timestamp": Date().timeIntervalSince1970
        ]

        // Keywords for Spotlight search
        activity.keywords = Set([roomName, "room", "kagami", "smart home"])

        // Content attribute set for richer search results
        let attributes = CSSearchableItemAttributeSet(contentType: .content)
        attributes.title = roomName
        attributes.contentDescription = "Control \(roomName) with Kagami"
        attributes.keywords = [roomName, "room", "kagami"]
        activity.contentAttributeSet = attributes

        // Web URL for Universal Links fallback
        if let webURL = URL(string: "https://kagami.home/room/\(roomId)") {
            activity.webpageURL = webURL
        }

        // Required user activities
        activity.requiredUserInfoKeys = ["roomId"]

        logger.debug("Created room activity: \(roomName)")

        return activity
    }

    /// Create a handoff activity for a scene
    /// - Parameters:
    ///   - sceneId: The scene identifier
    ///   - sceneName: Human-readable scene name
    /// - Returns: Configured NSUserActivity
    func createSceneActivity(sceneId: String, sceneName: String) -> NSUserActivity {
        let activity = NSUserActivity(activityType: HandoffActivityType.viewScene.rawValue)
        activity.title = sceneName
        activity.isEligibleForHandoff = true
        activity.isEligibleForSearch = true
        activity.isEligibleForPrediction = true

        activity.userInfo = [
            "sceneId": sceneId,
            "sceneName": sceneName,
            "timestamp": Date().timeIntervalSince1970
        ]

        activity.keywords = Set([sceneName, "scene", "kagami", "smart home", "automation"])

        let attributes = CSSearchableItemAttributeSet(contentType: .content)
        attributes.title = sceneName
        attributes.contentDescription = "Activate \(sceneName) scene"
        attributes.keywords = [sceneName, "scene", "automation"]
        activity.contentAttributeSet = attributes

        if let webURL = URL(string: "https://kagami.home/scene/\(sceneId)") {
            activity.webpageURL = webURL
        }

        activity.requiredUserInfoKeys = ["sceneId"]

        logger.debug("Created scene activity: \(sceneName)")

        return activity
    }

    /// Create a handoff activity for Hub chat
    /// - Parameters:
    ///   - conversationContext: Optional conversation context
    /// - Returns: Configured NSUserActivity
    func createHubActivity(conversationContext: String? = nil) -> NSUserActivity {
        let activity = NSUserActivity(activityType: HandoffActivityType.hubChat.rawValue)
        activity.title = "Kagami Hub"
        activity.isEligibleForHandoff = true
        activity.isEligibleForSearch = false // Don't index chat
        activity.isEligibleForPrediction = true

        var userInfo: [String: Any] = [
            "timestamp": Date().timeIntervalSince1970
        ]

        if let context = conversationContext {
            userInfo["conversationContext"] = context
        }

        activity.userInfo = userInfo

        if let webURL = URL(string: "https://kagami.home/hub") {
            activity.webpageURL = webURL
        }

        logger.debug("Created Hub activity")

        return activity
    }

    /// Create a handoff activity for device control
    /// - Parameters:
    ///   - deviceId: Device identifier
    ///   - deviceName: Device name
    ///   - deviceType: Type of device
    /// - Returns: Configured NSUserActivity
    func createDeviceActivity(deviceId: String, deviceName: String, deviceType: String) -> NSUserActivity {
        let activity = NSUserActivity(activityType: HandoffActivityType.controlDevice.rawValue)
        activity.title = deviceName
        activity.isEligibleForHandoff = true
        activity.isEligibleForSearch = true
        activity.isEligibleForPrediction = true

        activity.userInfo = [
            "deviceId": deviceId,
            "deviceName": deviceName,
            "deviceType": deviceType,
            "timestamp": Date().timeIntervalSince1970
        ]

        activity.keywords = Set([deviceName, deviceType, "control", "kagami"])

        let attributes = CSSearchableItemAttributeSet(contentType: .content)
        attributes.title = deviceName
        attributes.contentDescription = "Control \(deviceName)"
        activity.contentAttributeSet = attributes

        activity.requiredUserInfoKeys = ["deviceId"]

        return activity
    }

    // MARK: - Activity Management

    /// Set the current user activity (makes it available for handoff)
    /// - Parameter activity: The activity to advertise
    func setCurrent(_ activity: NSUserActivity) {
        currentActivity?.invalidate()
        currentActivity = activity
        activity.becomeCurrent()

        logger.info("Activity became current: \(activity.activityType)")
    }

    /// Clear the current activity
    func clearCurrentActivity() {
        currentActivity?.invalidate()
        currentActivity = nil

        logger.debug("Current activity cleared")
    }

    /// Handle an incoming handoff activity
    /// - Parameter activity: The received activity
    /// - Returns: True if handled successfully
    @discardableResult
    func handleIncoming(_ activity: NSUserActivity) -> Bool {
        receivedActivity = activity

        guard let activityType = HandoffActivityType(rawValue: activity.activityType) else {
            logger.warning("Unknown activity type: \(activity.activityType)")
            return false
        }

        logger.info("Received handoff activity: \(activityType.rawValue)")

        switch activityType {
        case .viewRoom:
            if let roomId = activity.userInfo?["roomId"] as? String {
                return handleRoomHandoff(roomId: roomId)
            }

        case .viewScene:
            if let sceneId = activity.userInfo?["sceneId"] as? String {
                return handleSceneHandoff(sceneId: sceneId)
            }

        case .controlDevice:
            if let deviceId = activity.userInfo?["deviceId"] as? String {
                return handleDeviceHandoff(deviceId: deviceId)
            }

        case .hubChat:
            let context = activity.userInfo?["conversationContext"] as? String
            return handleHubHandoff(context: context)

        case .settings:
            return handleSettingsHandoff()
        }

        return false
    }

    // MARK: - Handoff Handlers

    private func handleRoomHandoff(roomId: String) -> Bool {
        // Navigate to room via UniversalLinkHandler
        let link = UniversalLink.room(id: roomId)
        UniversalLinkHandler.shared.pendingLink = link

        logger.info("Handoff: Navigating to room \(roomId)")
        return true
    }

    private func handleSceneHandoff(sceneId: String) -> Bool {
        let link = UniversalLink.scene(name: sceneId)
        UniversalLinkHandler.shared.pendingLink = link

        logger.info("Handoff: Navigating to scene \(sceneId)")
        return true
    }

    private func handleDeviceHandoff(deviceId: String) -> Bool {
        // Device control would navigate to specific device
        logger.info("Handoff: Opening device \(deviceId)")
        return true
    }

    private func handleHubHandoff(context: String?) -> Bool {
        UniversalLinkHandler.shared.pendingLink = .hub

        logger.info("Handoff: Opening Hub")
        return true
    }

    private func handleSettingsHandoff() -> Bool {
        UniversalLinkHandler.shared.pendingLink = .settings

        logger.info("Handoff: Opening Settings")
        return true
    }

    // MARK: - Spotlight Indexing

    /// Index a room for Spotlight search
    /// - Parameters:
    ///   - roomId: Room identifier
    ///   - roomName: Room name
    ///   - deviceCount: Number of devices in room
    func indexRoom(roomId: String, roomName: String, deviceCount: Int) {
        activityQueue.async {
            let attributeSet = CSSearchableItemAttributeSet(contentType: .content)
            attributeSet.title = roomName
            attributeSet.contentDescription = "\(deviceCount) devices in \(roomName)"
            attributeSet.keywords = [roomName, "room", "kagami", "smart home"]

            let item = CSSearchableItem(
                uniqueIdentifier: "room-\(roomId)",
                domainIdentifier: "com.kagami.rooms",
                attributeSet: attributeSet
            )

            item.expirationDate = Date().addingTimeInterval(60 * 60 * 24 * 30) // 30 days

            CSSearchableIndex.default().indexSearchableItems([item]) { error in
                if let error = error {
                    #if DEBUG
                    print("[Spotlight] Indexing error: \(error)")
                    #endif
                }
            }
        }
    }

    /// Index a scene for Spotlight search
    /// - Parameters:
    ///   - sceneId: Scene identifier
    ///   - sceneName: Scene name
    ///   - description: Scene description
    func indexScene(sceneId: String, sceneName: String, description: String) {
        activityQueue.async {
            let attributeSet = CSSearchableItemAttributeSet(contentType: .content)
            attributeSet.title = sceneName
            attributeSet.contentDescription = description
            attributeSet.keywords = [sceneName, "scene", "kagami", "automation"]

            let item = CSSearchableItem(
                uniqueIdentifier: "scene-\(sceneId)",
                domainIdentifier: "com.kagami.scenes",
                attributeSet: attributeSet
            )

            item.expirationDate = Date().addingTimeInterval(60 * 60 * 24 * 30)

            CSSearchableIndex.default().indexSearchableItems([item]) { error in
                if let error = error {
                    #if DEBUG
                    print("[Spotlight] Indexing error: \(error)")
                    #endif
                }
            }
        }
    }

    /// Remove all Spotlight index entries
    func clearSpotlightIndex() {
        CSSearchableIndex.default().deleteAllSearchableItems { error in
            if let error = error {
                #if DEBUG
                print("[Spotlight] Clear error: \(error)")
                #endif
            }
        }
    }

    // MARK: - Universal Links Coordination

    /// Handle Universal Link in coordination with handoff
    /// - Parameter url: The URL to handle
    /// - Returns: True if handled
    func handleUniversalLink(_ url: URL) -> Bool {
        // Coordinate with UniversalLinkHandler
        let handled = UniversalLinkHandler.shared.handle(url: url)

        if handled {
            logger.info("Universal link handled: \(url.absoluteString)")
        }

        return handled
    }
}

// MARK: - SwiftUI Integration

/// View modifier to advertise handoff activity
struct HandoffActivityModifier: ViewModifier {
    let activity: NSUserActivity

    func body(content: Content) -> some View {
        content
            .onAppear {
                HandoffManager.shared.setCurrent(activity)
            }
            .onDisappear {
                HandoffManager.shared.clearCurrentActivity()
            }
    }
}

/// View modifier for room handoff
struct RoomHandoffModifier: ViewModifier {
    let roomId: String
    let roomName: String

    func body(content: Content) -> some View {
        content
            .onAppear {
                let activity = HandoffManager.shared.createRoomActivity(
                    roomId: roomId,
                    roomName: roomName
                )
                HandoffManager.shared.setCurrent(activity)
            }
            .onDisappear {
                HandoffManager.shared.clearCurrentActivity()
            }
    }
}

/// View modifier for scene handoff
struct SceneHandoffModifier: ViewModifier {
    let sceneId: String
    let sceneName: String

    func body(content: Content) -> some View {
        content
            .onAppear {
                let activity = HandoffManager.shared.createSceneActivity(
                    sceneId: sceneId,
                    sceneName: sceneName
                )
                HandoffManager.shared.setCurrent(activity)
            }
            .onDisappear {
                HandoffManager.shared.clearCurrentActivity()
            }
    }
}

extension View {
    /// Advertise a room for handoff
    func handoffRoom(id: String, name: String) -> some View {
        modifier(RoomHandoffModifier(roomId: id, roomName: name))
    }

    /// Advertise a scene for handoff
    func handoffScene(id: String, name: String) -> some View {
        modifier(SceneHandoffModifier(sceneId: id, sceneName: name))
    }

    /// Advertise a custom activity for handoff
    func handoffActivity(_ activity: NSUserActivity) -> some View {
        modifier(HandoffActivityModifier(activity: activity))
    }
}

/*
 * Mirror
 * Continuity bridges devices seamlessly.
 * h(x) >= 0. Always.
 */
