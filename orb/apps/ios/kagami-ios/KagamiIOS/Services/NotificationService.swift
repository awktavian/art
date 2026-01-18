//
// NotificationService.swift -- Push Notification Service for iOS
//
// Colony: Nexus (e4) -- Integration
//
// Features:
//   - APNs device token registration
//   - Background notification handling
//   - Notification categories and actions
//   - Deep link handling
//
// Created: December 31, 2025 (RALPH Week 3)
//

import Foundation
import UserNotifications
import UIKit
import Combine

// MARK: - Notification Types

enum KagamiNotificationType: String {
    case smartHomeAlert = "smart_home_alert"
    case routineReminder = "routine_reminder"
    case securityAlert = "security_alert"
    case systemUpdate = "system_update"
}

enum KagamiNotificationPriority: String {
    case critical = "critical"
    case high = "high"
    case normal = "normal"
    case low = "low"
}

// MARK: - Notification Categories

enum KagamiNotificationCategory: String {
    case homeAlert = "KAGAMI_HOME_ALERT"
    case securityAlert = "KAGAMI_SECURITY_ALERT"
    case routineReminder = "KAGAMI_ROUTINE"
    case systemUpdate = "KAGAMI_SYSTEM"

    var identifier: String { rawValue }
}

// MARK: - Notification Actions

enum KagamiNotificationAction: String {
    // Home Alert Actions
    case acknowledgeAlert = "ACKNOWLEDGE_ALERT"
    case viewDetails = "VIEW_DETAILS"
    case dismissAlert = "DISMISS_ALERT"

    // Security Alert Actions
    case viewCamera = "VIEW_CAMERA"
    case armSystem = "ARM_SYSTEM"
    case disarmSystem = "DISARM_SYSTEM"

    // Routine Actions
    case runRoutine = "RUN_ROUTINE"
    case skipRoutine = "SKIP_ROUTINE"
    case snoozeRoutine = "SNOOZE_ROUTINE"

    var identifier: String { rawValue }
}

// MARK: - Notification Service

@MainActor
class NotificationService: NSObject, ObservableObject {

    static let shared = NotificationService()

    // MARK: - Published State

    @Published var isAuthorized = false
    @Published var isRegistered = false
    @Published var deviceToken: String?
    @Published var unreadCount: Int = 0
    @Published var pendingNotifications: [UNNotification] = []

    // MARK: - Private Properties

    private var deviceTokenData: Data?
    private var notificationCenter: UNUserNotificationCenter {
        UNUserNotificationCenter.current()
    }

    // Retry logic
    private var registrationRetryCount = 0
    private let maxRetries = 3

    // Combine
    private var cancellables = Set<AnyCancellable>()

    // MARK: - Init

    private override init() {
        super.init()
    }

    // MARK: - Setup

    /// Initialize the notification service
    func setup() async {
        // Set delegate
        notificationCenter.delegate = self

        // Register notification categories
        registerNotificationCategories()

        // Check current authorization status
        await checkAuthorizationStatus()

        // Start periodic sync
        startPeriodicSync()
    }

    /// Request notification permissions
    func requestAuthorization() async -> Bool {
        do {
            let options: UNAuthorizationOptions = [.alert, .badge, .sound, .criticalAlert]
            let granted = try await notificationCenter.requestAuthorization(options: options)

            await MainActor.run {
                self.isAuthorized = granted
            }

            if granted {
                await registerForRemoteNotifications()
            }

            return granted
        } catch {
            print("Failed to request notification authorization: \(error)")
            return false
        }
    }

    /// Check current authorization status
    private func checkAuthorizationStatus() async {
        let settings = await notificationCenter.notificationSettings()

        await MainActor.run {
            self.isAuthorized = settings.authorizationStatus == .authorized
        }

        if isAuthorized && deviceToken == nil {
            await registerForRemoteNotifications()
        }
    }

    // MARK: - Remote Notification Registration

    /// Register for remote notifications (APNs)
    func registerForRemoteNotifications() async {
        await MainActor.run {
            UIApplication.shared.registerForRemoteNotifications()
        }
    }

    /// Handle successful APNs registration
    func didRegisterForRemoteNotifications(deviceToken: Data) {
        self.deviceTokenData = deviceToken

        // Convert token to string
        let tokenString = deviceToken.map { String(format: "%02.2hhx", $0) }.joined()

        Task { @MainActor in
            self.deviceToken = tokenString
            print("APNs device token: \(tokenString)")

            // Register with Kagami backend
            await registerTokenWithBackend(token: tokenString)
        }
    }

    /// Handle APNs registration failure
    func didFailToRegisterForRemoteNotifications(error: Error) {
        print("Failed to register for remote notifications: \(error)")

        // Retry if appropriate
        if registrationRetryCount < maxRetries {
            registrationRetryCount += 1
            Task {
                try? await Task.sleep(nanoseconds: UInt64(pow(2.0, Double(registrationRetryCount))) * 1_000_000_000)
                await registerForRemoteNotifications()
            }
        }
    }

    // MARK: - Backend Registration

    /// Register device token with Kagami backend
    private func registerTokenWithBackend(token: String) async {
        let api = KagamiAPIService.shared

        guard api.isConnected else {
            print("Cannot register token: not connected to server")
            return
        }

        guard let deviceId = await getDeviceId() else {
            print("Cannot register token: no device ID")
            return
        }

        let registration = KagamiAPIService.DeviceRegistrationRequest(
            deviceToken: token,
            platform: "ios",
            deviceId: deviceId,
            deviceName: UIDevice.current.name,
            appVersion: Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String
        )

        do {
            let result = try await api.registerDeviceForNotifications(registration)
            await MainActor.run {
                self.isRegistered = result.success
            }
            print("Device registered for notifications: \(result.success)")
        } catch {
            print("Failed to register device token with backend: \(error)")
        }
    }

    /// Unregister device from push notifications
    func unregisterDevice() async {
        guard let deviceId = await getDeviceId() else { return }

        let api = KagamiAPIService.shared

        do {
            _ = try await api.unregisterDeviceForNotifications(deviceId: deviceId)
            await MainActor.run {
                self.isRegistered = false
            }
            print("Device unregistered from notifications")
        } catch {
            print("Failed to unregister device: \(error)")
        }
    }

    // MARK: - Notification Categories

    /// Register notification categories with actions
    private func registerNotificationCategories() {
        // Home Alert Category
        let homeAlertCategory = UNNotificationCategory(
            identifier: KagamiNotificationCategory.homeAlert.identifier,
            actions: [
                UNNotificationAction(
                    identifier: KagamiNotificationAction.acknowledgeAlert.identifier,
                    title: "Acknowledge",
                    options: []
                ),
                UNNotificationAction(
                    identifier: KagamiNotificationAction.viewDetails.identifier,
                    title: "View Details",
                    options: [.foreground]
                ),
                UNNotificationAction(
                    identifier: KagamiNotificationAction.dismissAlert.identifier,
                    title: "Dismiss",
                    options: [.destructive]
                ),
            ],
            intentIdentifiers: [],
            options: [.customDismissAction]
        )

        // Security Alert Category
        let securityAlertCategory = UNNotificationCategory(
            identifier: KagamiNotificationCategory.securityAlert.identifier,
            actions: [
                UNNotificationAction(
                    identifier: KagamiNotificationAction.viewCamera.identifier,
                    title: "View Camera",
                    options: [.foreground]
                ),
                UNNotificationAction(
                    identifier: KagamiNotificationAction.armSystem.identifier,
                    title: "Arm System",
                    options: [.authenticationRequired]
                ),
                UNNotificationAction(
                    identifier: KagamiNotificationAction.disarmSystem.identifier,
                    title: "Disarm",
                    options: [.authenticationRequired, .destructive]
                ),
            ],
            intentIdentifiers: [],
            options: [.customDismissAction]
        )

        // Routine Reminder Category
        let routineCategory = UNNotificationCategory(
            identifier: KagamiNotificationCategory.routineReminder.identifier,
            actions: [
                UNNotificationAction(
                    identifier: KagamiNotificationAction.runRoutine.identifier,
                    title: "Run Now",
                    options: []
                ),
                UNNotificationAction(
                    identifier: KagamiNotificationAction.snoozeRoutine.identifier,
                    title: "Snooze 15m",
                    options: []
                ),
                UNNotificationAction(
                    identifier: KagamiNotificationAction.skipRoutine.identifier,
                    title: "Skip",
                    options: [.destructive]
                ),
            ],
            intentIdentifiers: [],
            options: [.customDismissAction]
        )

        // System Update Category
        let systemCategory = UNNotificationCategory(
            identifier: KagamiNotificationCategory.systemUpdate.identifier,
            actions: [
                UNNotificationAction(
                    identifier: KagamiNotificationAction.viewDetails.identifier,
                    title: "View Details",
                    options: [.foreground]
                ),
            ],
            intentIdentifiers: [],
            options: []
        )

        notificationCenter.setNotificationCategories([
            homeAlertCategory,
            securityAlertCategory,
            routineCategory,
            systemCategory,
        ])
    }

    // MARK: - Notification Handling

    /// Handle notification received while app is in foreground
    func handleForegroundNotification(_ notification: UNNotification) {
        let content = notification.request.content

        // Update unread count
        Task { @MainActor in
            self.unreadCount += 1
        }

        // Extract notification data
        let userInfo = content.userInfo
        let notificationType = userInfo["notification_type"] as? String ?? ""

        print("Foreground notification: \(content.title) (\(notificationType))")

        // Post notification for UI handling
        NotificationCenter.default.post(
            name: .kagamiNotificationReceived,
            object: nil,
            userInfo: userInfo
        )
    }

    /// Handle notification action response
    func handleNotificationResponse(_ response: UNNotificationResponse) {
        let actionIdentifier = response.actionIdentifier
        let userInfo = response.notification.request.content.userInfo

        print("Notification action: \(actionIdentifier)")

        // Mark as read
        if let notificationId = userInfo["notification_id"] as? String {
            Task {
                await markNotificationRead(notificationId: notificationId)
            }
        }

        // Handle specific actions
        switch actionIdentifier {
        case KagamiNotificationAction.viewDetails.identifier,
             UNNotificationDefaultActionIdentifier:
            handleViewDetails(userInfo: userInfo)

        case KagamiNotificationAction.viewCamera.identifier:
            handleViewCamera(userInfo: userInfo)

        case KagamiNotificationAction.acknowledgeAlert.identifier:
            handleAcknowledgeAlert(userInfo: userInfo)

        case KagamiNotificationAction.runRoutine.identifier:
            handleRunRoutine(userInfo: userInfo)

        case KagamiNotificationAction.snoozeRoutine.identifier:
            handleSnoozeRoutine(userInfo: userInfo)

        case KagamiNotificationAction.armSystem.identifier:
            handleArmSystem()

        case KagamiNotificationAction.disarmSystem.identifier:
            handleDisarmSystem()

        case KagamiNotificationAction.dismissAlert.identifier,
             KagamiNotificationAction.skipRoutine.identifier,
             UNNotificationDismissActionIdentifier:
            // Just dismiss, no action needed
            break

        default:
            break
        }
    }

    // MARK: - Action Handlers

    private func handleViewDetails(userInfo: [AnyHashable: Any]) {
        guard let actionUrl = userInfo["action_url"] as? String else { return }

        // Post deep link notification
        NotificationCenter.default.post(
            name: .kagamiDeepLink,
            object: nil,
            userInfo: ["url": actionUrl]
        )
    }

    private func handleViewCamera(userInfo: [AnyHashable: Any]) {
        let cameraId = userInfo["camera_id"] as? String ?? ""

        NotificationCenter.default.post(
            name: .kagamiDeepLink,
            object: nil,
            userInfo: ["url": "kagami://cameras/\(cameraId)"]
        )
    }

    private func handleAcknowledgeAlert(userInfo: [AnyHashable: Any]) {
        guard let alertId = userInfo["alert_id"] as? String else { return }

        Task {
            let api = KagamiAPIService.shared
            await api.acknowledgeAlert(alertId: alertId)
        }
    }

    private func handleRunRoutine(userInfo: [AnyHashable: Any]) {
        guard let routineId = userInfo["routine_id"] as? String else { return }

        Task {
            let api = KagamiAPIService.shared
            await api.executeRoutine(routineId: routineId)
        }
    }

    private func handleSnoozeRoutine(userInfo: [AnyHashable: Any]) {
        guard let routineId = userInfo["routine_id"] as? String else { return }

        Task {
            let api = KagamiAPIService.shared
            await api.snoozeRoutine(routineId: routineId, minutes: 15)
        }
    }

    private func handleArmSystem() {
        Task {
            let api = KagamiAPIService.shared
            await api.armSecuritySystem()
        }
    }

    private func handleDisarmSystem() {
        Task {
            let api = KagamiAPIService.shared
            await api.disarmSecuritySystem()
        }
    }

    // MARK: - Backend Sync

    /// Mark notification as read on backend
    private func markNotificationRead(notificationId: String) async {
        let api = KagamiAPIService.shared

        do {
            try await api.markNotificationRead(notificationId: notificationId)
            await refreshUnreadCount()
        } catch {
            print("Failed to mark notification read: \(error)")
        }
    }

    /// Refresh unread notification count
    func refreshUnreadCount() async {
        let api = KagamiAPIService.shared

        do {
            let count = try await api.getUnreadNotificationCount()
            await MainActor.run {
                self.unreadCount = count
                UIApplication.shared.applicationIconBadgeNumber = count
            }
        } catch {
            print("Failed to get unread count: \(error)")
        }
    }

    /// Start periodic sync with backend
    private func startPeriodicSync() {
        // Sync unread count every 60 seconds
        Timer.scheduledTimer(withTimeInterval: 60.0, repeats: true) { [weak self] _ in
            Task { @MainActor in
                await self?.refreshUnreadCount()
            }
        }
    }

    // MARK: - Helpers

    /// Get unique device identifier
    private func getDeviceId() async -> String? {
        // Use vendor ID for device identification
        return await UIDevice.current.identifierForVendor?.uuidString
    }

    /// Clear all notifications
    func clearAllNotifications() {
        notificationCenter.removeAllDeliveredNotifications()
        Task { @MainActor in
            self.unreadCount = 0
            UIApplication.shared.applicationIconBadgeNumber = 0
        }
    }
}

// MARK: - UNUserNotificationCenterDelegate

extension NotificationService: UNUserNotificationCenterDelegate {

    nonisolated func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification,
        withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void
    ) {
        // Show notification even when app is in foreground
        Task { @MainActor in
            self.handleForegroundNotification(notification)
        }

        // Show banner, sound, and badge
        completionHandler([.banner, .sound, .badge])
    }

    nonisolated func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        didReceive response: UNNotificationResponse,
        withCompletionHandler completionHandler: @escaping () -> Void
    ) {
        Task { @MainActor in
            self.handleNotificationResponse(response)
        }

        completionHandler()
    }
}

// MARK: - Notification Names

extension Notification.Name {
    /// Posted when a push notification is received
    static let kagamiNotificationReceived = Notification.Name("kagamiNotificationReceived")
    /// Posted when a deep link should be handled
    static let kagamiDeepLink = Notification.Name("kagamiDeepLink")
    /// Posted when the user logs out - used to reset app state
    static let kagamiDidLogout = Notification.Name("kagamiDidLogout")
    /// Posted when authentication state changes
    static let kagamiAuthStateChanged = Notification.Name("kagamiAuthStateChanged")
}

// MARK: - API Extension for Notifications

extension KagamiAPIService {

    struct DeviceRegistrationRequest {
        let deviceToken: String
        let platform: String
        let deviceId: String
        let deviceName: String?
        let appVersion: String?
    }

    struct DeviceRegistrationResponse {
        let success: Bool
        let deviceId: String
        let registeredAt: String
    }

    func registerDeviceForNotifications(_ registration: DeviceRegistrationRequest) async throws -> DeviceRegistrationResponse {
        guard let url = URL(string: "\(currentBaseURL)/api/notifications/register") else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")

        let body: [String: Any] = [
            "device_token": registration.deviceToken,
            "platform": registration.platform,
            "device_id": registration.deviceId,
            "device_name": registration.deviceName ?? "",
            "app_version": registration.appVersion ?? ""
        ]
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode.isSuccessful else {
            throw APIError.requestFailed
        }

        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any] ?? [:]

        return DeviceRegistrationResponse(
            success: json["success"] as? Bool ?? false,
            deviceId: json["device_id"] as? String ?? "",
            registeredAt: json["registered_at"] as? String ?? ""
        )
    }

    func unregisterDeviceForNotifications(deviceId: String) async throws -> Bool {
        guard let url = URL(string: "\(currentBaseURL)/api/notifications/unregister?device_id=\(deviceId)") else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "DELETE"

        let (_, response) = try await URLSession.shared.data(for: request)

        return (response as? HTTPURLResponse)?.statusCode.isSuccessful ?? false
    }

    func markNotificationRead(notificationId: String) async throws {
        guard let url = URL(string: "\(currentBaseURL)/api/notifications/mark-read/\(notificationId)") else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"

        _ = try await URLSession.shared.data(for: request)
    }

    func getUnreadNotificationCount() async throws -> Int {
        guard let url = URL(string: "\(currentBaseURL)/api/notifications/unread-count") else {
            throw APIError.invalidURL
        }

        let (data, response) = try await URLSession.shared.data(from: url)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode.isSuccessful else {
            throw APIError.requestFailed
        }

        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any] ?? [:]
        return json["unread_count"] as? Int ?? 0
    }

    // Smart Home Actions (for notification actions)

    func acknowledgeAlert(alertId: String) async {
        await postRequest(endpoint: "/api/alerts/\(alertId)/acknowledge")
    }

    func executeRoutine(routineId: String) async {
        await postRequest(endpoint: "/api/routines/\(routineId)/execute")
    }

    func snoozeRoutine(routineId: String, minutes: Int) async {
        let body: [String: Any] = ["minutes": minutes]
        await postRequest(endpoint: "/api/routines/\(routineId)/snooze", body: body)
    }

    func armSecuritySystem() async {
        await postRequest(endpoint: "/api/security/arm")
    }

    func disarmSecuritySystem() async {
        await postRequest(endpoint: "/api/security/disarm")
    }
}

/*
 * Mirror
 * h(x) >= 0. Always.
 */
