//
// KagamiApp.swift — Kagami iOS Application
//
// Smart home control with WebSocket real-time state sync.
// Colony: Nexus (e4) — Integration
// h(x) ≥ 0. Always.
//

import SwiftUI

@main
struct KagamiApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @StateObject private var homeState = HomeState()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(homeState)
                .preferredColorScheme(.dark)
        }
    }
}

// MARK: - Circuit Breaker

enum CircuitState {
    case closed, open, halfOpen
}

class CircuitBreaker {
    private var state: CircuitState = .closed
    private var failureCount = 0
    private let failureThreshold = 5
    private var lastFailure: Date?
    private let recoveryTimeout: TimeInterval = 30

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

// MARK: - WebSocket Manager

@MainActor
class WebSocketManager: NSObject, URLSessionWebSocketDelegate, ObservableObject {
    @Published var isConnected = false
    @Published var lastMessage: String?

    private var webSocket: URLSessionWebSocketTask?
    private var session: URLSession?
    private let wsURL: URL?
    private var reconnectTask: Task<Void, Never>?

    var onStateUpdate: ((HomeStateUpdate) -> Void)?

    init(url: String) {
        self.wsURL = URL(string: url)
        super.init()
        setupSession()
    }

    private func setupSession() {
        let config = URLSessionConfiguration.default
        session = URLSession(configuration: config, delegate: self, delegateQueue: .main)
    }

    func connect() {
        guard let wsURL = wsURL else {
            print("WebSocketManager: Invalid WebSocket URL")
            return
        }
        disconnect()
        webSocket = session?.webSocketTask(with: wsURL)
        webSocket?.resume()
        isConnected = true
        receiveMessage()

        // Send registration
        let clientId = "ios-\(UIDevice.current.identifierForVendor?.uuidString ?? UUID().uuidString)"
        let registration = ["type": "register", "client_id": clientId, "platform": "ios"]
        if let data = try? JSONSerialization.data(withJSONObject: registration),
           let string = String(data: data, encoding: .utf8) {
            webSocket?.send(.string(string)) { _ in }
        }
    }

    func disconnect() {
        webSocket?.cancel(with: .normalClosure, reason: nil)
        webSocket = nil
        isConnected = false
    }

    private func receiveMessage() {
        webSocket?.receive { [weak self] result in
            switch result {
            case .success(let message):
                switch message {
                case .string(let text):
                    self?.handleMessage(text)
                case .data(let data):
                    if let text = String(data: data, encoding: .utf8) {
                        self?.handleMessage(text)
                    }
                @unknown default:
                    break
                }
                self?.receiveMessage() // Continue receiving
            case .failure:
                Task { @MainActor in
                    self?.isConnected = false
                    self?.scheduleReconnect()
                }
            }
        }
    }

    private func handleMessage(_ text: String) {
        Task { @MainActor in
            lastMessage = text
            if let data = text.data(using: .utf8),
               let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let type = json["type"] as? String {

                if type == "state_update",
                   let stateData = json["state"] as? [String: Any] {
                    let update = HomeStateUpdate(
                        lightsLevel: stateData["lights_level"] as? Int,
                        fireplaceOn: stateData["fireplace_on"] as? Bool,
                        shadesOpen: stateData["shades_open"] as? Bool,
                        movieModeActive: stateData["movie_mode"] as? Bool
                    )
                    onStateUpdate?(update)
                }
            }
        }
    }

    private func scheduleReconnect() {
        reconnectTask?.cancel()
        reconnectTask = Task {
            try? await Task.sleep(nanoseconds: 5_000_000_000) // 5 seconds
            guard !Task.isCancelled else { return }
            await MainActor.run { connect() }
        }
    }

    // URLSessionWebSocketDelegate
    nonisolated func urlSession(_ session: URLSession, webSocketTask: URLSessionWebSocketTask, didOpenWithProtocol protocol: String?) {
        Task { @MainActor in
            isConnected = true
        }
    }

    nonisolated func urlSession(_ session: URLSession, webSocketTask: URLSessionWebSocketTask, didCloseWith closeCode: URLSessionWebSocketTask.CloseCode, reason: Data?) {
        Task { @MainActor in
            isConnected = false
        }
    }
}

struct HomeStateUpdate {
    var lightsLevel: Int?
    var fireplaceOn: Bool?
    var shadesOpen: Bool?
    var movieModeActive: Bool?
}

// MARK: - Home State

@MainActor
class HomeState: ObservableObject {
    @Published var isConnected = false
    @Published var isLoading = false
    @Published var lastAction: String?
    @Published var errorMessage: String?

    // Scene states
    @Published var movieModeActive = false
    @Published var lightsLevel: Int = 0
    @Published var fireplaceOn = false
    @Published var shadesOpen = true

    // Room data
    @Published var rooms: [RoomInfo] = []

    // Security: Default to HTTPS production URL. Local dev via UserDefaults/environment.
    private var apiURL: String {
        if let saved = UserDefaults.standard.string(forKey: "kagamiServerURL") {
            return saved
        }
        if let env = ProcessInfo.processInfo.environment["KAGAMI_BASE_URL"] {
            return env
        }
        return "https://api.awkronos.com"
    }

    private var wsURL: String {
        let base = apiURL
            .replacingOccurrences(of: "https://", with: "wss://")
            .replacingOccurrences(of: "http://", with: "wss://")
        return "\(base)/ws/client/ios"
    }

    private let circuitBreaker = CircuitBreaker()
    private var webSocket: WebSocketManager?

    init() {
        setupWebSocket()
        Task {
            await checkConnection()
            if isConnected {
                await fetchRooms()
            }
        }
    }

    private func setupWebSocket() {
        webSocket = WebSocketManager(url: wsURL)
        webSocket?.onStateUpdate = { [weak self] update in
            Task { @MainActor in
                if let level = update.lightsLevel {
                    self?.lightsLevel = level
                }
                if let fireplace = update.fireplaceOn {
                    self?.fireplaceOn = fireplace
                }
                if let shades = update.shadesOpen {
                    self?.shadesOpen = shades
                }
                if let movie = update.movieModeActive {
                    self?.movieModeActive = movie
                }
            }
        }
        webSocket?.connect()
    }

    func checkConnection() async {
        guard circuitBreaker.canAttempt() else {
            isConnected = false
            errorMessage = "Circuit breaker open - retrying soon"
            return
        }

        isLoading = true
        defer { isLoading = false }

        guard let url = URL(string: "\(apiURL)/health") else {
            isConnected = false
            errorMessage = "Invalid API URL"
            circuitBreaker.recordFailure()
            return
        }

        do {
            let (_, response) = try await URLSession.shared.data(from: url)
            let success = (response as? HTTPURLResponse)?.statusCode == 200
            isConnected = success

            if success {
                circuitBreaker.recordSuccess()
            } else {
                circuitBreaker.recordFailure()
            }
        } catch {
            isConnected = false
            errorMessage = "Cannot connect to Kagami"
            circuitBreaker.recordFailure()
        }
    }

    func fetchRooms() async {
        guard let url = URL(string: "\(apiURL)/api/home/rooms") else {
            // Invalid URL - not critical
            return
        }

        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let roomsData = json["rooms"] as? [[String: Any]] {
                rooms = roomsData.compactMap { dict in
                    guard let id = dict["id"] as? Int,
                          let name = dict["name"] as? String else { return nil }
                    return RoomInfo(id: id, name: name)
                }
            }
        } catch {
            // Rooms fetch failed - not critical
        }
    }

    // MARK: - Intent Execution

    func executeScene(_ scene: String) async {
        await executeIntent(endpoint: "/api/home/\(scene)", name: scene.replacingOccurrences(of: "-", with: " ").capitalized)

        // Update local state based on scene
        if scene.contains("movie-mode") {
            movieModeActive = true
        } else if scene == "goodnight" {
            lightsLevel = 0
            fireplaceOn = false
        }
    }

    func setLights(_ level: Int, room: String? = nil) async {
        var body: [String: Any] = ["level": level]
        if let room = room {
            body["rooms"] = [room]
        }
        await executeIntent(endpoint: "/api/home/lights/set", body: body, name: "Lights \(level)%")
        lightsLevel = level
    }

    func toggleFireplace(_ on: Bool) async {
        let endpoint = on ? "/api/home/fireplace/on" : "/api/home/fireplace/off"
        await executeIntent(endpoint: endpoint, name: on ? "Fireplace On" : "Fireplace Off")
        fireplaceOn = on
    }

    func controlShades(_ action: String) async {
        await executeIntent(endpoint: "/api/home/shades/\(action)", name: "Shades \(action.capitalized)")
        shadesOpen = action == "open"
    }

    private func executeIntent(endpoint: String, body: [String: Any]? = nil, name: String) async {
        guard circuitBreaker.canAttempt() else {
            lastAction = "⏸️ \(name) (offline)"
            return
        }

        guard let url = URL(string: "\(apiURL)\(endpoint)") else {
            lastAction = "❌ \(name)"
            errorMessage = "Invalid endpoint URL"
            return
        }

        isLoading = true
        defer { isLoading = false }

        do {
            var request = URLRequest(url: url)
            request.httpMethod = "POST"
            request.addValue("application/json", forHTTPHeaderField: "Content-Type")
            request.addValue("kagami-ios", forHTTPHeaderField: "User-Agent")
            request.addValue(UUID().uuidString, forHTTPHeaderField: "Idempotency-Key")

            if let body = body {
                request.httpBody = try JSONSerialization.data(withJSONObject: body)
            }

            let (_, response) = try await URLSession.shared.data(for: request)

            if let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode >= 200 && httpResponse.statusCode < 300 {
                lastAction = "✅ \(name)"
                errorMessage = nil
                circuitBreaker.recordSuccess()
            } else {
                lastAction = "❌ \(name)"
                errorMessage = "Failed: HTTP \((response as? HTTPURLResponse)?.statusCode ?? 0)"
                circuitBreaker.recordFailure()
            }
        } catch {
            lastAction = "❌ \(name)"
            errorMessage = error.localizedDescription
            circuitBreaker.recordFailure()
        }
    }
}

// MARK: - Room Info

struct RoomInfo: Identifiable {
    let id: Int
    let name: String
}
