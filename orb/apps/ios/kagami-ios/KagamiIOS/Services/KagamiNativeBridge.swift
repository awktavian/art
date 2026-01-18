//
// KagamiNativeBridge.swift — Native Bridge for HTML Agents
//
// Provides native iOS capabilities to HTML agents via WKScriptMessageHandler.
// Enables agents to use haptics, notifications, device control, etc.
//
// Colony: Nexus (e4) — Integration
// h(x) >= 0. Always.

import Foundation
import WebKit
import UIKit

// MARK: - Bridge Message Types

/// Messages sent from JavaScript to native
struct BridgeRequest: Decodable {
    let id: Int
    let action: String
    let params: [String: AnyCodable]?
}

/// Response sent back to JavaScript
struct BridgeResponse: Encodable {
    let id: Int
    let success: Bool
    let result: AnyCodable?
    let error: String?
}

// MARK: - Kagami Native Bridge

/// Native bridge handler for WKWebView.
/// Receives messages from JavaScript and executes native actions.
///
/// Usage in JavaScript:
/// ```javascript
/// window.webkit.messageHandlers.kagamiBridge.postMessage({
///     id: 1,
///     action: 'haptic',
///     params: { style: 'medium' }
/// });
/// ```
class KagamiNativeBridge: NSObject, WKScriptMessageHandler {

    // MARK: - Properties

    weak var webView: WKWebView?
    private let haptics = KagamiHaptics.shared
    private let deviceControl = DeviceControlService.shared
    private let sceneService = SceneService.shared

    // MARK: - Platform Information

    var platformInfo: [String: Any] {
        return [
            "platform": "ios",
            "version": UIDevice.current.systemVersion,
            "model": UIDevice.current.model,
            "capabilities": [
                "haptic",
                "notification",
                "healthkit",
                "siri",
                "share",
                "device_control",
                "scenes"
            ]
        ]
    }

    // MARK: - WKScriptMessageHandler

    func userContentController(
        _ userContentController: WKUserContentController,
        didReceive message: WKScriptMessage
    ) {
        guard message.name == "kagamiBridge" else { return }

        // Parse the message
        guard let body = message.body as? [String: Any],
              let id = body["id"] as? Int,
              let action = body["action"] as? String else {
            print("⚠️ [NativeBridge] Invalid message format")
            return
        }

        let params = body["params"] as? [String: Any] ?? [:]

        // Execute action
        Task {
            do {
                let result = try await executeAction(action, params: params)
                sendResponse(id: id, success: true, result: result)
            } catch {
                sendResponse(id: id, success: false, error: error.localizedDescription)
            }
        }
    }

    // MARK: - Action Execution

    private func executeAction(_ action: String, params: [String: Any]) async throws -> Any? {
        switch action {
        // Haptics
        case "haptic":
            let style = params["style"] as? String ?? "medium"
            triggerHaptic(style: style)
            return ["triggered": true]

        // Notifications
        case "notification":
            guard let title = params["title"] as? String else {
                throw BridgeError.missingParameter("title")
            }
            let body = params["body"] as? String
            await showNotification(title: title, body: body)
            return ["shown": true]

        // Share
        case "share":
            let text = params["text"] as? String
            let url = params["url"] as? String
            await share(text: text, url: url)
            return ["shared": true]

        // Device Control - Lights
        case "setLights":
            guard let level = params["level"] as? Int else {
                throw BridgeError.missingParameter("level")
            }
            let rooms = params["rooms"] as? [String]
            _ = await deviceControl.setLights(level, rooms: rooms)
            return ["success": true]

        // Device Control - Shades
        case "setShades":
            guard let action = params["action"] as? String else {
                throw BridgeError.missingParameter("action")
            }
            let rooms = params["rooms"] as? [String]
            if action == "open" {
                try await deviceControl.openShades(rooms: rooms)
            } else {
                try await deviceControl.closeShades(rooms: rooms)
            }
            return ["success": true]

        // Scenes
        case "executeScene":
            guard let scene = params["scene"] as? String else {
                throw BridgeError.missingParameter("scene")
            }
            _ = await sceneService.execute(scene)
            return ["success": true]

        // Get platform info
        case "getPlatformInfo":
            return platformInfo

        // Clipboard
        case "clipboard":
            guard let text = params["text"] as? String else {
                throw BridgeError.missingParameter("text")
            }
            UIPasteboard.general.string = text
            return ["copied": true]

        // Unknown action
        default:
            throw BridgeError.unknownAction(action)
        }
    }

    // MARK: - Haptics

    private func triggerHaptic(style: String) {
        switch style {
        case "light":
            haptics.play(.lightImpact)
        case "medium":
            haptics.play(.mediumImpact)
        case "heavy":
            haptics.play(.heavyImpact)
        case "success":
            haptics.play(.success)
        case "error":
            haptics.play(.error)
        case "warning":
            haptics.play(.warning)
        default:
            haptics.play(.mediumImpact)
        }
    }

    // MARK: - Notifications

    @MainActor
    private func showNotification(title: String, body: String?) async {
        // For now, we'll use a simple banner. In production, use UNUserNotificationCenter.
        // This is a placeholder that just logs the notification.
        print("📢 Notification: \(title) - \(body ?? "")")

        // TODO: Implement proper notification using NotificationService
        // NotificationService.shared.showBanner(title: title, body: body)
    }

    // MARK: - Share Sheet

    @MainActor
    private func share(text: String?, url: String?) async {
        var items: [Any] = []

        if let text = text {
            items.append(text)
        }

        if let urlString = url, let url = URL(string: urlString) {
            items.append(url)
        }

        guard !items.isEmpty else { return }

        let activityVC = UIActivityViewController(
            activityItems: items,
            applicationActivities: nil
        )

        // Get the top-most view controller
        if let windowScene = UIApplication.shared.connectedScenes.first as? UIWindowScene,
           let rootVC = windowScene.windows.first?.rootViewController {
            var topVC = rootVC
            while let presentedVC = topVC.presentedViewController {
                topVC = presentedVC
            }
            topVC.present(activityVC, animated: true)
        }
    }

    // MARK: - Response Handling

    private func sendResponse(id: Int, success: Bool, result: Any? = nil, error: String? = nil) {
        guard let webView = webView else { return }

        var response: [String: Any] = [
            "id": id,
            "success": success
        ]

        if let result = result {
            response["result"] = result
        }

        if let error = error {
            response["error"] = error
        }

        // Convert to JSON and call JavaScript callback
        if let jsonData = try? JSONSerialization.data(withJSONObject: response),
           let jsonString = String(data: jsonData, encoding: .utf8) {
            let js = "window.kagamiBridgeCallback(\(id), \(jsonString))"
            DispatchQueue.main.async {
                webView.evaluateJavaScript(js) { _, error in
                    if let error = error {
                        print("⚠️ [NativeBridge] JS callback error: \(error)")
                    }
                }
            }
        }
    }
}

// MARK: - Bridge Errors

enum BridgeError: LocalizedError {
    case unknownAction(String)
    case missingParameter(String)
    case executionFailed(String)

    var errorDescription: String? {
        switch self {
        case .unknownAction(let action):
            return "Unknown action: \(action)"
        case .missingParameter(let param):
            return "Missing required parameter: \(param)"
        case .executionFailed(let reason):
            return "Execution failed: \(reason)"
        }
    }
}

// MARK: - AnyCodable
// Note: AnyCodable is defined in HubManager.swift
// Do not duplicate here to avoid redeclaration errors

/*
 * 鏡
 * h(x) >= 0. Always.
 */
