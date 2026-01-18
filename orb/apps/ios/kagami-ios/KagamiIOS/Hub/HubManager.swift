//
// HubManager.swift — Hub Discovery and Control
//
// Colony: Nexus (e4) — Integration
//
// Discovers and manages Kagami Hub devices on the local network
// via Bonjour/mDNS and provides configuration and control.
//
// ## NWBrowser Memory Lifecycle
//
// The NWBrowser instance (`browser`) follows a strict lifecycle to prevent memory leaks:
//
// 1. **Creation**: Created in `startDiscovery()` with `NWBrowser(for:using:)`
// 2. **Start**: Started with `browser?.start(queue: .main)`
// 3. **Active**: Receives results via `browseResultsChangedHandler`
// 4. **Stop**: Must be cancelled with `browser?.cancel()` in `stopDiscovery()`
// 5. **Release**: Set to nil after cancellation to release memory
//
// ### Critical Rules:
// - ALWAYS call `browser?.cancel()` before setting browser to nil
// - ALWAYS call `stopDiscovery()` when:
//   - View disappears (e.g., in `.onDisappear`)
//   - Discovery timeout is reached
//   - User navigates away from Hub view
//   - App enters background
// - NEVER create a new browser without cancelling the old one first
//
// ### Memory Safety Pattern:
// ```swift
// func stopDiscovery() {
//     browser?.cancel()     // 1. Cancel first
//     browser = nil         // 2. Then release
//     isDiscovering = false
// }
// ```
//
// ### Connection Resolution:
// NWConnection instances created for service resolution are short-lived:
// - Created in `resolveService(result:name:)`
// - Cancelled immediately after endpoint extraction
// - Pattern: Create -> Start -> Extract -> Cancel
//
// h(x) >= 0. Always.
//

import Foundation
import Network
import Combine

// MARK: - Hub Models

struct HubDevice: Identifiable, Codable {
    let id: String
    var name: String
    var location: String
    var host: String
    var port: Int
    var isConnected: Bool
    var lastSeen: Date

    // Security: Hub communication uses HTTPS (self-signed certs on local network)
    var baseURL: String {
        "https://\(host):\(port)"
    }
}

struct HubStatus: Codable {
    let name: String
    let location: String
    let apiUrl: String
    let apiConnected: Bool
    let safetyScore: Double?
    let ledRingEnabled: Bool
    let ledBrightness: Float
    let wakeWord: String
    var isListening: Bool
    let currentColony: String?
    let uptimeSeconds: Int
    let version: String

    enum CodingKeys: String, CodingKey {
        case name, location, version
        case apiUrl = "api_url"
        case apiConnected = "api_connected"
        case safetyScore = "safety_score"
        case ledRingEnabled = "led_ring_enabled"
        case ledBrightness = "led_brightness"
        case wakeWord = "wake_word"
        case isListening = "is_listening"
        case currentColony = "current_colony"
        case uptimeSeconds = "uptime_seconds"
    }
}

struct HubConfig: Codable {
    var name: String
    var location: String
    var apiUrl: String
    var wakeWord: String
    var wakeSensitivity: Float
    var ledEnabled: Bool
    var ledBrightness: Float
    var ledCount: Int
    var ttsVolume: Float
    var ttsColony: String

    enum CodingKeys: String, CodingKey {
        case name, location
        case apiUrl = "api_url"
        case wakeWord = "wake_word"
        case wakeSensitivity = "wake_sensitivity"
        case ledEnabled = "led_enabled"
        case ledBrightness = "led_brightness"
        case ledCount = "led_count"
        case ttsVolume = "tts_volume"
        case ttsColony = "tts_colony"
    }
}

// MARK: - Hub Events (WebSocket)

struct HubEvent: Codable {
    let eventType: String
    let data: [String: AnyCodable]
    let timestamp: Int

    enum CodingKeys: String, CodingKey {
        case eventType = "event_type"
        case data, timestamp
    }
}

// Simple wrapper for heterogeneous JSON
public struct AnyCodable: Codable, @unchecked Sendable {
    public let value: Any

    public init(_ value: Any) {
        self.value = value
    }

    public init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let bool = try? container.decode(Bool.self) {
            value = bool
        } else if let int = try? container.decode(Int.self) {
            value = int
        } else if let double = try? container.decode(Double.self) {
            value = double
        } else if let string = try? container.decode(String.self) {
            value = string
        } else if let array = try? container.decode([AnyCodable].self) {
            value = array.map { $0.value }
        } else if let dict = try? container.decode([String: AnyCodable].self) {
            value = dict.mapValues { $0.value }
        } else {
            value = NSNull()
        }
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        if let bool = value as? Bool {
            try container.encode(bool)
        } else if let int = value as? Int {
            try container.encode(int)
        } else if let double = value as? Double {
            try container.encode(double)
        } else if let string = value as? String {
            try container.encode(string)
        } else {
            try container.encodeNil()
        }
    }
}

// MARK: - Hub Manager

@MainActor
class HubManager: NSObject, ObservableObject {

    static let shared = HubManager()

    // MARK: - Published State

    @Published var discoveredHubs: [HubDevice] = []
    @Published var connectedHub: HubDevice?
    @Published var hubStatus: HubStatus?
    @Published var hubConfig: HubConfig?
    @Published var isDiscovering = false
    @Published var isConnecting = false
    @Published var lastError: String?

    // MARK: - Private

    private var browser: NWBrowser?
    private var webSocketTask: URLSessionWebSocketTask?
    private var session: URLSession

    // MARK: - Init

    override init() {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 10
        self.session = URLSession(configuration: config)
        super.init()
    }

    // MARK: - Discovery via Bonjour

    func startDiscovery() {
        isDiscovering = true
        discoveredHubs.removeAll()

        // Create browser for _kagami-hub._tcp service
        let parameters = NWParameters()
        parameters.includePeerToPeer = true

        browser = NWBrowser(for: .bonjour(type: "_kagami-hub._tcp", domain: "local."), using: parameters)

        browser?.stateUpdateHandler = { [weak self] state in
            Task { @MainActor in
                switch state {
                case .ready:
                    print("🔍 Hub discovery ready")
                case .failed(let error):
                    self?.lastError = "Discovery failed: \(error)"
                    self?.isDiscovering = false
                default:
                    break
                }
            }
        }

        browser?.browseResultsChangedHandler = { [weak self] results, changes in
            Task { @MainActor in
                self?.handleDiscoveryResults(results)
            }
        }

        browser?.start(queue: .main)

        // Also try direct connection to common addresses
        Task {
            await tryDirectDiscovery()
        }

        // Stop discovery after 10 seconds
        Task {
            try? await Task.sleep(nanoseconds: 10_000_000_000)
            await MainActor.run {
                self.stopDiscovery()
            }
        }
    }

    func stopDiscovery() {
        browser?.cancel()
        browser = nil
        isDiscovering = false
    }

    private func handleDiscoveryResults(_ results: Set<NWBrowser.Result>) {
        for result in results {
            if case .service(let name, _, _, _) = result.endpoint {
                // Resolve the service to get host/port
                resolveService(result: result, name: name)
            }
        }
    }

    private func resolveService(result: NWBrowser.Result, name: String) {
        let connection = NWConnection(to: result.endpoint, using: .tcp)

        connection.stateUpdateHandler = { [weak self] state in
            if case .ready = state {
                if let endpoint = connection.currentPath?.remoteEndpoint,
                   case .hostPort(let host, let port) = endpoint {
                    let hostString = "\(host)"
                    let portInt = Int(port.rawValue)

                    Task { @MainActor [weak self] in
                        guard let self = self else { return }
                        let hub = HubDevice(
                            id: "\(hostString):\(portInt)",
                            name: name,
                            location: "Discovered",
                            host: hostString,
                            port: portInt,
                            isConnected: false,
                            lastSeen: Date()
                        )

                        if !self.discoveredHubs.contains(where: { $0.id == hub.id }) {
                            self.discoveredHubs.append(hub)
                        }
                    }
                }
                connection.cancel()
            }
        }

        connection.start(queue: .global())
    }

    private func tryDirectDiscovery() async {
        // Try common Hub addresses
        let candidates = [
            ("kagami-hub.local", 8080),
            ("raspberrypi.local", 8080),
            ("192.168.1.100", 8080),
            ("192.168.1.50", 8080),
        ]

        for (host, port) in candidates {
            if await testHubConnection(host: host, port: port) {
                let hub = HubDevice(
                    id: "\(host):\(port)",
                    name: "Kagami Hub",
                    location: "Direct",
                    host: host,
                    port: port,
                    isConnected: false,
                    lastSeen: Date()
                )

                await MainActor.run {
                    if !discoveredHubs.contains(where: { $0.id == hub.id }) {
                        discoveredHubs.append(hub)
                    }
                }
            }
        }
    }

    private func testHubConnection(host: String, port: Int) async -> Bool {
        // Security: Use HTTPS for hub health checks
        guard let url = URL(string: "https://\(host):\(port)/health") else { return false }

        do {
            let (_, response) = try await session.data(from: url)
            return (response as? HTTPURLResponse)?.statusCode == 200
        } catch {
            return false
        }
    }

    // MARK: - Connection

    func connect(to hub: HubDevice) async {
        isConnecting = true
        lastError = nil

        do {
            // Fetch status
            let status = try await fetchStatus(from: hub)
            let config = try await fetchConfig(from: hub)

            var connectedHub = hub
            connectedHub.isConnected = true
            connectedHub.name = status.name
            connectedHub.location = status.location

            self.connectedHub = connectedHub
            self.hubStatus = status
            self.hubConfig = config

            // Connect WebSocket for real-time updates
            connectWebSocket(to: hub)

            // Save as last connected hub
            saveLastHub(hub)

        } catch {
            lastError = "Connection failed: \(error.localizedDescription)"
        }

        isConnecting = false
    }

    func disconnect() {
        webSocketTask?.cancel(with: .goingAway, reason: nil)
        webSocketTask = nil
        connectedHub = nil
        hubStatus = nil
        hubConfig = nil
    }

    // MARK: - API Calls

    private func fetchStatus(from hub: HubDevice) async throws -> HubStatus {
        guard let url = URL(string: "\(hub.baseURL)/status") else {
            throw URLError(.badURL)
        }

        let (data, _) = try await session.data(from: url)
        return try JSONDecoder().decode(HubStatus.self, from: data)
    }

    private func fetchConfig(from hub: HubDevice) async throws -> HubConfig {
        guard let url = URL(string: "\(hub.baseURL)/config") else {
            throw URLError(.badURL)
        }

        let (data, _) = try await session.data(from: url)
        return try JSONDecoder().decode(HubConfig.self, from: data)
    }

    func updateConfig(_ config: HubConfig) async throws {
        guard let hub = connectedHub,
              let url = URL(string: "\(hub.baseURL)/config") else {
            throw URLError(.badURL)
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(config)

        let (data, _) = try await session.data(for: request)
        self.hubConfig = try JSONDecoder().decode(HubConfig.self, from: data)
    }

    func controlLED(pattern: String, colony: Int? = nil, brightness: Float? = nil) async throws {
        guard let hub = connectedHub,
              let url = URL(string: "\(hub.baseURL)/led") else {
            throw URLError(.badURL)
        }

        var body: [String: Any] = ["pattern": pattern]
        if let colony = colony { body["colony"] = colony }
        if let brightness = brightness { body["brightness"] = brightness }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let _ = try await session.data(for: request)
    }

    func testLED() async throws {
        guard let hub = connectedHub,
              let url = URL(string: "\(hub.baseURL)/led/test") else {
            throw URLError(.badURL)
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"

        let _ = try await session.data(for: request)
    }

    func triggerListen() async throws {
        guard let hub = connectedHub,
              let url = URL(string: "\(hub.baseURL)/voice/listen") else {
            throw URLError(.badURL)
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"

        let _ = try await session.data(for: request)
    }

    func executeCommand(_ command: String) async throws {
        guard let hub = connectedHub,
              let url = URL(string: "\(hub.baseURL)/command") else {
            throw URLError(.badURL)
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: ["command": command])

        let _ = try await session.data(for: request)
    }

    // MARK: - WebSocket

    private func connectWebSocket(to hub: HubDevice) {
        guard let url = URL(string: "ws://\(hub.host):\(hub.port)/ws") else { return }

        webSocketTask?.cancel()
        webSocketTask = session.webSocketTask(with: url)
        webSocketTask?.resume()

        receiveWebSocketMessage()
    }

    private func receiveWebSocketMessage() {
        webSocketTask?.receive { [weak self] result in
            switch result {
            case .success(let message):
                if case .string(let text) = message {
                    self?.handleWebSocketMessage(text)
                }
                self?.receiveWebSocketMessage()

            case .failure(let error):
                print("WebSocket error: \(error)")
            }
        }
    }

    private func handleWebSocketMessage(_ text: String) {
        guard let data = text.data(using: .utf8),
              let event = try? JSONDecoder().decode(HubEvent.self, from: data) else { return }

        Task { @MainActor in
            switch event.eventType {
            case "status_update":
                if let statusData = try? JSONSerialization.data(withJSONObject: event.data.mapValues { $0.value }),
                   let status = try? JSONDecoder().decode(HubStatus.self, from: statusData) {
                    self.hubStatus = status
                }

            case "listening_started":
                self.hubStatus?.isListening = true

            case "config_updated":
                if let configData = try? JSONSerialization.data(withJSONObject: event.data.mapValues { $0.value }),
                   let config = try? JSONDecoder().decode(HubConfig.self, from: configData) {
                    self.hubConfig = config
                }

            default:
                break
            }
        }
    }

    // MARK: - Persistence

    private func saveLastHub(_ hub: HubDevice) {
        UserDefaults.standard.set(hub.host, forKey: "lastHubHost")
        UserDefaults.standard.set(hub.port, forKey: "lastHubPort")
    }

    func connectToLastHub() async {
        guard let host = UserDefaults.standard.string(forKey: "lastHubHost") else { return }
        let port = UserDefaults.standard.integer(forKey: "lastHubPort")

        let hub = HubDevice(
            id: "\(host):\(port)",
            name: "Last Hub",
            location: "Saved",
            host: host,
            port: port > 0 ? port : 8080,
            isConnected: false,
            lastSeen: Date()
        )

        await connect(to: hub)
    }
}

/*
 * 鏡
 */
