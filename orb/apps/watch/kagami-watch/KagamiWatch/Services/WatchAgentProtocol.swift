//
// WatchAgentProtocol.swift — Native Agent Protocol for watchOS
//
// Enables the Apple Watch to participate in the Kagami agent ecosystem
// as a lightweight native observer. Since watchOS doesn't support WebViews,
// this implements agent protocol semantics natively.
//
// Colony: Nexus (e4) — Integration
// h(x) >= 0. Always.
//

import Foundation
import WatchKit
import Combine

// MARK: - Agent Types

/// Represents a registered agent in the ecosystem
struct AgentInfo: Identifiable, Codable {
    let id: String
    let name: String
    let description: String
    let colony: String
    let capabilities: [String]
    let consensusWeight: Int
    var isOnline: Bool
}

/// Agent state updates received from the network
struct AgentStateUpdate: Codable {
    let agentId: String
    let key: String
    let value: AnyCodableValue
    let timestamp: Date
    let source: String
}

/// Consensus proposal from the network
struct ConsensusProposal: Identifiable, Codable {
    let id: String
    let proposerId: String
    let operation: String
    let payload: [String: AnyCodableValue]
    let timestamp: Date
    let votes: [String: ConsensusVote]
}

/// A vote on a consensus proposal
struct ConsensusVote: Codable {
    let agentId: String
    let decision: String // "approve" or "reject"
    let reason: String?
    let weight: Int
    let timestamp: Date
}

/// Type-erased Codable wrapper for dynamic JSON
struct AnyCodableValue: Codable {
    let value: Any

    init(_ value: Any) {
        self.value = value
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()

        if let bool = try? container.decode(Bool.self) {
            value = bool
        } else if let int = try? container.decode(Int.self) {
            value = int
        } else if let double = try? container.decode(Double.self) {
            value = double
        } else if let string = try? container.decode(String.self) {
            value = string
        } else {
            value = NSNull()
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()

        switch value {
        case let bool as Bool:
            try container.encode(bool)
        case let int as Int:
            try container.encode(int)
        case let double as Double:
            try container.encode(double)
        case let string as String:
            try container.encode(string)
        default:
            try container.encodeNil()
        }
    }
}

// MARK: - Watch Agent Protocol

/// Protocol for watchOS to participate in the agent ecosystem.
///
/// The watch acts as a lightweight OBSERVER agent that:
/// - Receives agent state updates
/// - Can trigger agent actions
/// - Participates in consensus voting (with low weight)
/// - Provides haptic feedback for agent events
///
/// Usage:
/// ```swift
/// let protocol = WatchAgentProtocol()
/// await protocol.connect()
///
/// // Trigger an agent action
/// await protocol.triggerAgentAction("scenes", action: "activate", params: ["scene": "movie_mode"])
///
/// // Subscribe to updates
/// protocol.$activeAgents.sink { agents in
///     print("Active agents: \(agents.count)")
/// }
/// ```
@MainActor
class WatchAgentProtocol: ObservableObject {
    // MARK: - Constants

    private let watchAgentId = "kagami-watch"
    private let watchAgentName = "Kagami Watch"
    private let consensusWeight = 1 // Low weight for watch

    // MARK: - Published State

    @Published var activeAgents: [AgentInfo] = []
    @Published var pendingProposals: [ConsensusProposal] = []
    @Published var isConnected = false
    @Published var lastError: Error?

    // MARK: - Private

    private let apiService = KagamiAPIService.shared
    private var cancellables = Set<AnyCancellable>()
    private var webSocketTask: URLSessionWebSocketTask?
    private let logger = KagamiLogger.watch

    // MARK: - Connection

    /// Connect to the agent ecosystem
    func connect() async {
        guard !isConnected else { return }

        do {
            // Register as an agent
            try await registerAsAgent()

            // Fetch active agents
            try await refreshAgents()

            // Connect to WebSocket for real-time updates
            connectWebSocket()

            isConnected = true
            logger.info("Watch agent protocol connected")

            // Provide haptic feedback
            WKInterfaceDevice.current().play(.success)

        } catch {
            lastError = error
            logger.error("Failed to connect: \(error.localizedDescription)")
            WKInterfaceDevice.current().play(.failure)
        }
    }

    /// Disconnect from the ecosystem
    func disconnect() {
        webSocketTask?.cancel(with: .normalClosure, reason: nil)
        webSocketTask = nil
        isConnected = false
        logger.info("Watch agent protocol disconnected")
    }

    // MARK: - Agent Registration

    private func registerAsAgent() async throws {
        let registration: [String: Any] = [
            "agentId": watchAgentId,
            "name": watchAgentName,
            "type": "OBSERVER",
            "capabilities": ["haptic", "notification", "voice_trigger"],
            "consensusWeight": consensusWeight,
            "platform": "watchos",
            "version": Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "1.0"
        ]

        // Call registration endpoint
        try await apiService.post(endpoint: "/api/v1/agents/register", body: registration)
        logger.info("Registered as watch agent")
    }

    // MARK: - Agent List

    /// Refresh the list of active agents
    func refreshAgents() async throws {
        let response: AgentsListResponse = try await apiService.get(endpoint: "/api/v1/agents")
        activeAgents = response.agents
        logger.info("Fetched \(activeAgents.count) agents")
    }

    // MARK: - Agent Actions

    /// Trigger an action on a specific agent
    /// - Parameters:
    ///   - agentId: The target agent's ID
    ///   - action: The action to trigger
    ///   - params: Additional parameters for the action
    func triggerAgentAction(
        _ agentId: String,
        action: String,
        params: [String: Any] = [:]
    ) async throws {
        let payload: [String: Any] = [
            "agentId": agentId,
            "action": action,
            "params": params,
            "source": watchAgentId,
            "timestamp": ISO8601DateFormatter().string(from: Date())
        ]

        try await apiService.post(endpoint: "/api/v1/agents/\(agentId)/action", body: payload)

        // Haptic feedback for action trigger
        WKInterfaceDevice.current().play(.click)

        logger.info("Triggered action '\(action)' on agent '\(agentId)'")
    }

    /// Execute a scene via the scenes agent
    func executeScene(_ sceneName: String) async throws {
        try await triggerAgentAction("scenes", action: "activate", params: ["scene": sceneName])
    }

    /// Control lights via the rooms agent
    func setLights(level: Int, rooms: [String]? = nil) async throws {
        var params: [String: Any] = ["level": level]
        if let rooms = rooms {
            params["rooms"] = rooms
        }
        try await triggerAgentAction("rooms", action: "setLights", params: params)
    }

    // MARK: - Consensus

    /// Vote on a consensus proposal
    func voteOnProposal(_ proposalId: String, approve: Bool, reason: String? = nil) async throws {
        let vote: [String: Any] = [
            "proposalId": proposalId,
            "agentId": watchAgentId,
            "decision": approve ? "approve" : "reject",
            "reason": reason ?? "",
            "weight": consensusWeight,
            "timestamp": ISO8601DateFormatter().string(from: Date())
        ]

        try await apiService.post(endpoint: "/api/v1/consensus/vote", body: vote)

        // Haptic feedback for voting
        WKInterfaceDevice.current().play(.click)

        logger.info("Voted \(approve ? "approve" : "reject") on proposal \(proposalId)")
    }

    /// Auto-approve low-risk proposals
    func autoApproveProposal(_ proposal: ConsensusProposal) async {
        // Only auto-approve certain operations
        let safeOperations = ["toggle_light", "activate_scene", "set_brightness"]

        guard safeOperations.contains(proposal.operation) else {
            logger.info("Skipping auto-approval for operation: \(proposal.operation)")
            return
        }

        do {
            try await voteOnProposal(proposal.id, approve: true, reason: "Auto-approved by watch (low-risk)")
        } catch {
            logger.error("Failed to auto-approve: \(error.localizedDescription)")
        }
    }

    // MARK: - WebSocket

    private func connectWebSocket() {
        guard let baseURL = apiService.currentBaseURL,
              let wsURL = URL(string: baseURL.replacingOccurrences(of: "http", with: "ws") + "/ws/agents") else {
            logger.error("Invalid WebSocket URL")
            return
        }

        let session = URLSession(configuration: .default)
        webSocketTask = session.webSocketTask(with: wsURL)
        webSocketTask?.resume()

        // Send registration message
        let registerMessage: [String: Any] = [
            "type": "register",
            "agentId": watchAgentId,
            "capabilities": ["receive_state", "receive_proposals", "vote"]
        ]

        if let data = try? JSONSerialization.data(withJSONObject: registerMessage),
           let string = String(data: data, encoding: .utf8) {
            webSocketTask?.send(.string(string)) { [weak self] error in
                if let error = error {
                    self?.logger.error("WebSocket registration error: \(error.localizedDescription)")
                }
            }
        }

        // Start receiving messages
        receiveWebSocketMessage()
    }

    private func receiveWebSocketMessage() {
        webSocketTask?.receive { [weak self] result in
            guard let self = self else { return }

            switch result {
            case .success(let message):
                switch message {
                case .string(let text):
                    self.handleWebSocketMessage(text)
                case .data(let data):
                    if let text = String(data: data, encoding: .utf8) {
                        self.handleWebSocketMessage(text)
                    }
                @unknown default:
                    break
                }

                // Continue receiving
                self.receiveWebSocketMessage()

            case .failure(let error):
                self.logger.error("WebSocket receive error: \(error.localizedDescription)")
                Task { @MainActor in
                    self.isConnected = false
                }
            }
        }
    }

    private func handleWebSocketMessage(_ text: String) {
        guard let data = text.data(using: .utf8),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let type = json["type"] as? String else {
            return
        }

        Task { @MainActor in
            switch type {
            case "state_update":
                handleStateUpdate(json)
            case "proposal":
                handleProposal(json)
            case "agent_online", "agent_offline":
                try? await refreshAgents()
            case "ping":
                sendPong()
            default:
                logger.logDebug("Unknown message type: \(type)")
            }
        }
    }

    private func handleStateUpdate(_ json: [String: Any]) {
        // Provide haptic feedback for important state changes
        if let key = json["key"] as? String {
            switch key {
            case "safety_alert":
                WKInterfaceDevice.current().play(.notification)
            case "scene_activated":
                WKInterfaceDevice.current().play(.success)
            default:
                break
            }
        }
    }

    private func handleProposal(_ json: [String: Any]) {
        guard let proposalData = try? JSONSerialization.data(withJSONObject: json["proposal"] ?? [:]),
              let proposal = try? JSONDecoder().decode(ConsensusProposal.self, from: proposalData) else {
            return
        }

        // Add to pending proposals
        pendingProposals.append(proposal)

        // Haptic for new proposal
        WKInterfaceDevice.current().play(.notification)

        // Auto-approve safe operations
        Task {
            await autoApproveProposal(proposal)
        }
    }

    private func sendPong() {
        let pong: [String: Any] = ["type": "pong", "agentId": watchAgentId]
        if let data = try? JSONSerialization.data(withJSONObject: pong),
           let string = String(data: data, encoding: .utf8) {
            webSocketTask?.send(.string(string)) { _ in }
        }
    }
}

// MARK: - API Response Models

private struct AgentsListResponse: Codable {
    let agents: [AgentInfo]
}

// MARK: - API Service Extension

extension KagamiAPIService {
    func post(endpoint: String, body: [String: Any]) async throws {
        // Implementation would use URLSession to POST
        // This is a placeholder - the actual implementation depends on KagamiAPIService
    }

    func get<T: Decodable>(endpoint: String) async throws -> T {
        // Implementation would use URLSession to GET
        // This is a placeholder - the actual implementation depends on KagamiAPIService
        throw NSError(domain: "NotImplemented", code: -1)
    }

    var currentBaseURL: String? {
        // Return the current API base URL
        return "http://kagami.local:8000"
    }
}

/*
 * 鏡
 * h(x) >= 0. Always.
 */
