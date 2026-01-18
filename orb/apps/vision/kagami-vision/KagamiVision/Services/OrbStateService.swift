//
// OrbStateService.swift — Cross-Client Orb State Synchronization
//
// Colony: Nexus (e₄) — Integration
//
// Connects to the Kagami API orb WebSocket for real-time state sync.
// When the orb is tapped on any client, all clients receive the event.
//
// Canonical colors are fetched from /api/v1/orb/colors
// State is received via WebSocket at /api/v1/orb/stream
//
// η → s → μ → a → η′
// h(x) ≥ 0. Always.
//

import Foundation
import Combine
import SwiftUI

// MARK: - Orb State Model

/// Canonical orb state synchronized across all clients.
struct OrbState: Codable {
    let activeColony: String?
    let activity: String
    let safetyScore: Double
    let connection: String
    let activeColonies: [String]
    let color: OrbColorInfo
    let timestamp: Double
    
    enum CodingKeys: String, CodingKey {
        case activeColony = "active_colony"
        case activity
        case safetyScore = "safety_score"
        case connection
        case activeColonies = "active_colonies"
        case color
        case timestamp
    }
}

struct OrbColorInfo: Codable {
    let hex: String
    let rgb: [Int]
    let name: String
}

/// Interaction event from any client
struct OrbInteractionEvent: Codable {
    let type: String
    let eventId: String
    let client: String
    let action: String
    let context: [String: String]
    let timestamp: Double
    
    enum CodingKeys: String, CodingKey {
        case type
        case eventId = "event_id"
        case client
        case action
        case context
        case timestamp
    }
}

/// Colony color definition
struct ColonyColorDefinition: Codable {
    let hex: String
    let rgb: [Int]
    let name: String
    
    /// Convert to SwiftUI Color
    var swiftColor: Color {
        Color(
            red: Double(rgb[0]) / 255.0,
            green: Double(rgb[1]) / 255.0,
            blue: Double(rgb[2]) / 255.0
        )
    }
}

// MARK: - Orb State Service

@MainActor
class OrbStateService: ObservableObject {
    
    // MARK: - Singleton
    
    static let shared = OrbStateService()
    
    // MARK: - Published State
    
    /// Current orb state from server
    @Published var currentState: OrbState?
    
    /// Canonical colony colors from server
    @Published var colonyColors: [String: ColonyColorDefinition] = [:]
    
    /// Whether connected to orb WebSocket
    @Published var isConnected = false
    
    /// Last interaction event received
    @Published var lastInteraction: OrbInteractionEvent?
    
    /// Number of connected clients
    @Published var connectedClients: Int = 0
    
    // MARK: - Private
    
    private var baseURL: String = KagamiAPIService.defaultAPIURL
    private var webSocket: URLSessionWebSocketTask?
    private var cancellables = Set<AnyCancellable>()
    private let session: URLSession
    
    // MARK: - Init
    
    init() {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 10
        self.session = URLSession(configuration: config)
    }
    
    // MARK: - Connect
    
    /// Connect to the orb WebSocket stream
    func connect() async {
        // Fetch canonical colors first
        await fetchColonyColors()
        
        // Connect to WebSocket
        connectWebSocket()
    }
    
    /// Disconnect from orb stream
    func disconnect() {
        webSocket?.cancel(with: .goingAway, reason: nil)
        webSocket = nil
        isConnected = false
    }
    
    // MARK: - Colors
    
    /// Fetch canonical colony colors from API
    func fetchColonyColors() async {
        let url = URL(string: "\(baseURL)/api/v1/orb/colors")!
        
        do {
            let (data, _) = try await session.data(from: url)
            let colors = try JSONDecoder().decode([String: ColonyColorDefinition].self, from: data)
            self.colonyColors = colors
            print("🔮 Loaded \(colors.count) colony colors from API")
        } catch {
            print("⚠️ Failed to fetch colony colors: \(error)")
            // Use fallback colors
            loadFallbackColors()
        }
    }
    
    /// Load hardcoded fallback colors if API unavailable
    private func loadFallbackColors() {
        colonyColors = [
            "spark": ColonyColorDefinition(hex: "#FF6B35", rgb: [255, 107, 53], name: "Phoenix Orange"),
            "forge": ColonyColorDefinition(hex: "#FFB347", rgb: [255, 179, 71], name: "Forge Amber"),
            "flow": ColonyColorDefinition(hex: "#4ECDC4", rgb: [78, 205, 196], name: "Ocean Teal"),
            "nexus": ColonyColorDefinition(hex: "#9B59B6", rgb: [155, 89, 182], name: "Bridge Purple"),
            "beacon": ColonyColorDefinition(hex: "#D4AF37", rgb: [212, 175, 55], name: "Tower Gold"),
            "grove": ColonyColorDefinition(hex: "#27AE60", rgb: [39, 174, 96], name: "Forest Green"),
            "crystal": ColonyColorDefinition(hex: "#E0E0E0", rgb: [224, 224, 224], name: "Diamond White"),
        ]
    }
    
    /// Get color for a colony (from API or fallback)
    func colorForColony(_ colony: String?) -> Color {
        guard let colony = colony,
              let definition = colonyColors[colony] else {
            // Default idle color
            return Color(red: 74/255, green: 144/255, blue: 217/255)
        }
        return definition.swiftColor
    }
    
    // MARK: - WebSocket
    
    private func connectWebSocket() {
        let wsURL = baseURL
            .replacingOccurrences(of: "http://", with: "ws://")
            .replacingOccurrences(of: "https://", with: "wss://")
        
        guard let url = URL(string: "\(wsURL)/api/v1/orb/stream") else {
            print("⚠️ Invalid orb WebSocket URL")
            return
        }
        
        webSocket = session.webSocketTask(with: url)
        webSocket?.resume()
        isConnected = true
        
        print("🔮 Connected to orb WebSocket")
        
        // Start receiving messages
        receiveMessage()
    }
    
    private func receiveMessage() {
        webSocket?.receive { [weak self] result in
            Task { @MainActor in
                switch result {
                case .success(let message):
                    self?.handleMessage(message)
                    self?.receiveMessage()  // Continue listening
                    
                case .failure(let error):
                    print("⚠️ Orb WebSocket error: \(error)")
                    self?.isConnected = false
                    
                    // Retry after delay
                    try? await Task.sleep(nanoseconds: 2_000_000_000)
                    self?.connectWebSocket()
                }
            }
        }
    }
    
    private func handleMessage(_ message: URLSessionWebSocketTask.Message) {
        guard case .string(let text) = message,
              let data = text.data(using: .utf8) else {
            return
        }
        
        do {
            // Parse the message type first
            if let json = try JSONSerialization.jsonObject(with: data) as? [String: Any],
               let type = json["type"] as? String {
                
                switch type {
                case "orb_state":
                    let state = try JSONDecoder().decode(OrbState.self, from: data)
                    self.currentState = state
                    print("🔮 State update: \(state.activity), colony: \(state.activeColony ?? "idle")")
                    
                case "orb_interaction":
                    let event = try JSONDecoder().decode(OrbInteractionEvent.self, from: data)
                    self.lastInteraction = event
                    print("🔮 Interaction from \(event.client): \(event.action)")
                    
                    // Notify observers
                    NotificationCenter.default.post(
                        name: .orbInteractionReceived,
                        object: event
                    )
                    
                case "orb_state_changed":
                    print("🔮 Colony changed")
                    // Refresh state
                    
                default:
                    print("🔮 Unknown message type: \(type)")
                }
            }
        } catch {
            print("⚠️ Failed to parse orb message: \(error)")
        }
    }
    
    // MARK: - Report Interaction
    
    /// Report an orb interaction to broadcast to all clients
    func reportInteraction(action: String, context: [String: String] = [:]) async {
        let url = URL(string: "\(baseURL)/api/v1/orb/interaction")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body: [String: Any] = [
            "client": "vision_pro",
            "action": action,
            "context": context
        ]
        
        do {
            request.httpBody = try JSONSerialization.data(withJSONObject: body)
            let (data, _) = try await session.data(for: request)
            
            if let response = try? JSONDecoder().decode(InteractionResponse.self, from: data) {
                connectedClients = response.broadcastCount
                print("🔮 Interaction broadcast to \(response.broadcastCount) clients")
            }
        } catch {
            print("⚠️ Failed to report interaction: \(error)")
        }
    }
}

// MARK: - Response Models

private struct InteractionResponse: Codable {
    let success: Bool
    let eventId: String
    let broadcastCount: Int
    
    enum CodingKeys: String, CodingKey {
        case success
        case eventId = "event_id"
        case broadcastCount = "broadcast_count"
    }
}

// MARK: - Notifications

extension Notification.Name {
    static let orbInteractionReceived = Notification.Name("orbInteractionReceived")
}

// MARK: - Preview Helper

extension OrbStateService {
    static var preview: OrbStateService {
        let service = OrbStateService()
        service.loadFallbackColors()
        return service
    }
}

/*
 * 鏡
 * One orb. Seven colors. Infinite presence.
 */
