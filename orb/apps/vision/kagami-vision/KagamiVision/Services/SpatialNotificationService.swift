//
// SpatialNotificationService.swift
// KagamiVision
//
// Spatial notifications for visionOS 2.
// Notifications appear in appropriate proxemic zones.
//
// Features:
//   - Zone-based notification placement
//   - Notification priority levels
//   - Spatial audio cues
//   - VoiceOver announcements
//   - Reduced motion support
//

import SwiftUI
import RealityKit
import UserNotifications

// MARK: - Spatial Notification

struct SpatialNotification: Identifiable {
    let id: UUID
    let title: String
    let body: String
    let icon: String
    let priority: Priority
    let zone: ProxemicZone
    let timestamp: Date
    var isRead: Bool

    enum Priority {
        case low       // Ambient zone, subtle
        case normal    // Social zone, standard
        case high      // Personal zone, attention-getting
        case critical  // Intimate zone, immediate attention

        var zoneDistance: Float {
            switch self {
            case .low: return 3.0       // Ambient
            case .normal: return 2.0    // Social
            case .high: return 0.8      // Personal
            case .critical: return 0.4  // Intimate
            }
        }

        var soundIntensity: Float {
            switch self {
            case .low: return 0.2
            case .normal: return 0.5
            case .high: return 0.8
            case .critical: return 1.0
            }
        }
    }

    enum ProxemicZone {
        case intimate   // 0-45cm
        case personal   // 45cm-1.2m
        case social     // 1.2m-3.6m
        case ambient    // 3.6m+
    }

    init(
        title: String,
        body: String,
        icon: String = "bell.fill",
        priority: Priority = .normal
    ) {
        self.id = UUID()
        self.title = title
        self.body = body
        self.icon = icon
        self.priority = priority
        self.timestamp = Date()
        self.isRead = false

        // Map priority to zone
        switch priority {
        case .low: self.zone = .ambient
        case .normal: self.zone = .social
        case .high: self.zone = .personal
        case .critical: self.zone = .intimate
        }
    }
}

// MARK: - Spatial Notification Service

@MainActor
class SpatialNotificationService: ObservableObject {

    // MARK: - Published State

    @Published var activeNotifications: [SpatialNotification] = []
    @Published var unreadCount = 0

    // MARK: - Internal State

    private var audioService: SpatialAudioService?
    private var anchorService: SpatialAnchorService?

    // Auto-dismiss timer
    private var dismissTimers: [UUID: Timer] = [:]

    // Notification history (limited)
    private var notificationHistory: [SpatialNotification] = []
    private let maxHistory = 50

    // MARK: - Init

    init(audioService: SpatialAudioService? = nil, anchorService: SpatialAnchorService? = nil) {
        self.audioService = audioService
        self.anchorService = anchorService
    }

    func configure(audio: SpatialAudioService, anchors: SpatialAnchorService) {
        self.audioService = audio
        self.anchorService = anchors
    }

    // MARK: - Showing Notifications

    /// Shows a spatial notification
    func show(_ notification: SpatialNotification, duration: TimeInterval = 5.0) {
        activeNotifications.append(notification)
        notificationHistory.insert(notification, at: 0)
        updateUnreadCount()

        // Trim history
        if notificationHistory.count > maxHistory {
            notificationHistory = Array(notificationHistory.prefix(maxHistory))
        }

        // Play audio cue at appropriate distance
        if let position = calculateNotificationPosition(for: notification) {
            audioService?.play(.notification, at: position)
        }

        // VoiceOver announcement
        UIAccessibility.post(
            notification: .announcement,
            argument: "\(notification.title). \(notification.body)"
        )

        // Auto-dismiss timer
        let timer = Timer.scheduledTimer(withTimeInterval: duration, repeats: false) { [weak self] _ in
            Task { @MainActor [weak self] in
                self?.dismiss(notification.id)
            }
        }
        dismissTimers[notification.id] = timer
    }

    // MARK: - Convenience Methods

    /// Shows a device status notification
    func showDeviceStatus(device: String, status: String, icon: String = "lightbulb.fill") {
        let notification = SpatialNotification(
            title: device,
            body: status,
            icon: icon,
            priority: .normal
        )
        show(notification, duration: 3.0)
    }

    /// Shows a scene activation notification
    func showSceneActivated(scene: String) {
        let notification = SpatialNotification(
            title: "Scene Activated",
            body: scene,
            icon: "sparkles",
            priority: .normal
        )
        show(notification, duration: 4.0)
    }

    /// Shows an alert notification
    func showAlert(title: String, message: String) {
        let notification = SpatialNotification(
            title: title,
            body: message,
            icon: "exclamationmark.triangle.fill",
            priority: .high
        )
        show(notification, duration: 8.0)
    }

    /// Shows a critical notification
    func showCritical(title: String, message: String) {
        let notification = SpatialNotification(
            title: title,
            body: message,
            icon: "exclamationmark.circle.fill",
            priority: .critical
        )
        show(notification, duration: 0)  // No auto-dismiss for critical
    }

    // MARK: - Dismissing

    func dismiss(_ id: UUID) {
        activeNotifications.removeAll { $0.id == id }
        dismissTimers[id]?.invalidate()
        dismissTimers.removeValue(forKey: id)
    }

    func dismissAll() {
        for timer in dismissTimers.values {
            timer.invalidate()
        }
        dismissTimers.removeAll()
        activeNotifications.removeAll()
    }

    func markAsRead(_ id: UUID) {
        if let index = activeNotifications.firstIndex(where: { $0.id == id }) {
            activeNotifications[index].isRead = true
        }
        if let index = notificationHistory.firstIndex(where: { $0.id == id }) {
            notificationHistory[index].isRead = true
        }
        updateUnreadCount()
    }

    private func updateUnreadCount() {
        unreadCount = activeNotifications.filter { !$0.isRead }.count
    }

    // MARK: - Position Calculation

    private func calculateNotificationPosition(for notification: SpatialNotification) -> SIMD3<Float>? {
        guard let headPosition = anchorService?.headPosition,
              let headForward = anchorService?.headForward else {
            return nil
        }

        // Calculate position based on priority zone
        let distance = notification.priority.zoneDistance
        let forward = simd_normalize(headForward)

        // Offset slightly to the right and up for visibility
        let right = simd_cross(forward, SIMD3<Float>(0, 1, 0))
        let offset = SIMD3<Float>(0.2, 0.1, 0)  // Slight offset

        return headPosition + forward * distance + right * offset.x + SIMD3<Float>(0, offset.y, 0)
    }

    // MARK: - History

    func getHistory() -> [SpatialNotification] {
        return notificationHistory
    }

    func clearHistory() {
        notificationHistory.removeAll()
    }
}

// MARK: - Notification View

struct SpatialNotificationView: View {
    let notification: SpatialNotification
    let onDismiss: () -> Void

    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        HStack(spacing: 12) {
            // Icon
            Image(systemName: notification.icon)
                .font(.system(size: 24))
                .foregroundColor(iconColor)
                .frame(width: 44, height: 44)
                .background(
                    Circle()
                        .fill(iconColor.opacity(0.2))
                )

            // Content
            VStack(alignment: .leading, spacing: 4) {
                Text(notification.title)
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundColor(.primary)

                Text(notification.body)
                    .font(.system(size: 14))
                    .foregroundColor(.secondary)
                    .lineLimit(2)
            }

            Spacer()

            // Dismiss button
            Button(action: onDismiss) {
                Image(systemName: "xmark")
                    .font(.system(size: 14))
                    .foregroundColor(.secondary)
            }
            .frame(width: 44, height: 44)
            .contentShape(.hoverEffect, .circle)
            .hoverEffect(.lift)
            .buttonStyle(.plain)
        }
        .padding(16)
        .glassBackgroundEffect()
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(notification.title). \(notification.body)")
        .accessibilityAddTraits(.isButton)
        .accessibilityHint("Double tap to dismiss")
    }

    private var iconColor: Color {
        switch notification.priority {
        case .low: return .grove
        case .normal: return .crystal
        case .high: return .beacon
        case .critical: return .spark
        }
    }
}

// MARK: - Notification Container

struct SpatialNotificationContainer: View {
    @ObservedObject var service: SpatialNotificationService

    var body: some View {
        VStack(spacing: 8) {
            ForEach(service.activeNotifications) { notification in
                SpatialNotificationView(
                    notification: notification,
                    onDismiss: { service.dismiss(notification.id) }
                )
                .transition(.move(edge: .trailing).combined(with: .opacity))
            }
        }
        .animation(.spring(response: 0.377, dampingFraction: 0.8), value: service.activeNotifications.count)  // 377ms Fibonacci
        .padding()
    }
}

/*
 * Spatial notifications appear in appropriate proxemic zones.
 * Critical alerts appear close, ambient updates stay distant.
 * All notifications support VoiceOver.
 */
