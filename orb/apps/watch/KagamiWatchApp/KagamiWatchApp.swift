//
// KagamiWatchApp.swift — Kagami watchOS Application
//
// Smart home control from your wrist with haptic feedback.
// Colony: Nexus (e4) — Integration
// h(x) ≥ 0. Always.
//

import SwiftUI
import WatchKit

@main
struct KagamiWatchApp: App {
    @StateObject private var homeState = WatchHomeState()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(homeState)
        }
    }
}

// MARK: - Haptics Manager

class HapticsManager {
    static let shared = HapticsManager()

    func success() {
        WKInterfaceDevice.current().play(.success)
    }

    func failure() {
        WKInterfaceDevice.current().play(.failure)
    }

    func click() {
        WKInterfaceDevice.current().play(.click)
    }

    func notification() {
        WKInterfaceDevice.current().play(.notification)
    }
}

// MARK: - Circuit Breaker

class WatchCircuitBreaker {
    private var state: CircuitState = .closed
    private var failureCount = 0
    private let failureThreshold = 3
    private var lastFailure: Date?
    private let recoveryTimeout: TimeInterval = 30

    enum CircuitState {
        case closed, open, halfOpen
    }

    var isOpen: Bool { state == .open }

    func recordSuccess() {
        failureCount = 0
        state = .closed
    }

    func recordFailure() {
        failureCount += 1
        lastFailure = Date()
        if failureCount >= failureThreshold {
            state = .open
        }
    }

    func canAttempt() -> Bool {
        switch state {
        case .closed:
            return true
        case .open:
            if let lastFailure = lastFailure,
               Date().timeIntervalSince(lastFailure) > recoveryTimeout {
                state = .halfOpen
                return true
            }
            return false
        case .halfOpen:
            return true
        }
    }
}

// MARK: - Context Engine

@MainActor
class ContextEngine: ObservableObject {
    @Published var suggestedAction: SuggestedAction?

    struct SuggestedAction {
        let title: String
        let icon: String
        let color: Color
        let scene: String
    }

    func updateContext() {
        let hour = Calendar.current.component(.hour, from: Date())

        switch hour {
        case 5..<9: // Morning
            suggestedAction = SuggestedAction(
                title: "Start Day",
                icon: "sunrise.fill",
                color: .orange,
                scene: "welcome-home"
            )
        case 9..<17: // Work hours
            suggestedAction = SuggestedAction(
                title: "Focus Mode",
                icon: "brain.head.profile",
                color: .green,
                scene: "focus"
            )
        case 17..<22: // Evening
            suggestedAction = SuggestedAction(
                title: "Movie Time",
                icon: "film.fill",
                color: .purple,
                scene: "movie-mode/enter"
            )
        default: // Night
            suggestedAction = SuggestedAction(
                title: "Goodnight",
                icon: "moon.fill",
                color: .indigo,
                scene: "goodnight"
            )
        }
    }
}

// MARK: - Home State

@MainActor
class WatchHomeState: ObservableObject {
    @Published var isConnected = false
    @Published var isLoading = false
    @Published var lastAction: String?
    @Published var offlineQueue: [QueuedAction] = []

    let context = ContextEngine()
    private let haptics = HapticsManager.shared
    private let circuitBreaker = WatchCircuitBreaker()
    private let apiURL = "http://kagami.local:8001"

    struct QueuedAction: Identifiable {
        let id = UUID()
        let endpoint: String
        let body: [String: Any]?
        let name: String
        let timestamp: Date
    }

    init() {
        context.updateContext()
        Task {
            await checkConnection()
        }
    }

    func checkConnection() async {
        guard circuitBreaker.canAttempt() else {
            isConnected = false
            return
        }

        isLoading = true
        defer { isLoading = false }

        do {
            let url = URL(string: "\(apiURL)/health")!
            let (_, response) = try await URLSession.shared.data(from: url)
            let success = (response as? HTTPURLResponse)?.statusCode == 200
            isConnected = success

            if success {
                circuitBreaker.recordSuccess()
                // Process queued actions
                await processOfflineQueue()
            } else {
                circuitBreaker.recordFailure()
            }
        } catch {
            isConnected = false
            circuitBreaker.recordFailure()
        }
    }

    private func processOfflineQueue() async {
        let queue = offlineQueue
        offlineQueue = []

        for action in queue {
            await executeIntent(endpoint: action.endpoint, body: action.body, name: action.name, isRetry: true)
        }
    }

    func executeScene(_ scene: String) async {
        haptics.click()
        await executeIntent(endpoint: "/api/home/\(scene)", name: scene.replacingOccurrences(of: "-", with: " ").capitalized)
    }

    func setLights(_ level: Int) async {
        haptics.click()
        await executeIntent(
            endpoint: "/api/home/lights/set",
            body: ["level": level],
            name: "Lights \(level)%"
        )
    }

    func toggleFireplace(_ on: Bool) async {
        haptics.click()
        let endpoint = on ? "/api/home/fireplace/on" : "/api/home/fireplace/off"
        await executeIntent(endpoint: endpoint, name: on ? "🔥 On" : "🔥 Off")
    }

    func executeSuggestedAction() async {
        guard let action = context.suggestedAction else { return }
        haptics.notification()
        await executeScene(action.scene)
    }

    private func executeIntent(endpoint: String, body: [String: Any]? = nil, name: String, isRetry: Bool = false) async {
        guard circuitBreaker.canAttempt() else {
            // Queue for later if circuit is open
            if !isRetry {
                offlineQueue.append(QueuedAction(endpoint: endpoint, body: body, name: name, timestamp: Date()))
                lastAction = "📥 Queued: \(name)"
            }
            haptics.failure()
            return
        }

        isLoading = true
        defer { isLoading = false }

        do {
            var request = URLRequest(url: URL(string: "\(apiURL)\(endpoint)")!)
            request.httpMethod = "POST"
            request.addValue("application/json", forHTTPHeaderField: "Content-Type")
            request.addValue("KagamiWatch/1.0", forHTTPHeaderField: "User-Agent")
            request.addValue(UUID().uuidString, forHTTPHeaderField: "Idempotency-Key")

            if let body = body {
                request.httpBody = try JSONSerialization.data(withJSONObject: body)
            }

            let (_, response) = try await URLSession.shared.data(for: request)

            if let httpResponse = response as? HTTPURLResponse,
               httpResponse.statusCode >= 200 && httpResponse.statusCode < 300 {
                lastAction = "✅ \(name)"
                circuitBreaker.recordSuccess()
                haptics.success()
            } else {
                lastAction = "❌ \(name)"
                circuitBreaker.recordFailure()
                haptics.failure()
            }
        } catch {
            lastAction = "❌ \(name)"
            circuitBreaker.recordFailure()
            haptics.failure()

            // Queue for later if not already a retry
            if !isRetry {
                offlineQueue.append(QueuedAction(endpoint: endpoint, body: body, name: name, timestamp: Date()))
            }
        }

        // Clear after delay
        Task {
            try? await Task.sleep(nanoseconds: 2_000_000_000)
            lastAction = nil
        }
    }
}
