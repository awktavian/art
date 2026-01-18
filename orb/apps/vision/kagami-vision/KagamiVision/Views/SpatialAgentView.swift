//
// SpatialAgentView.swift — Spatial WebView for HTML Agents
//
// Renders HTML agents in a visionOS spatial context.
// Agents float in space, respond to gaze, and use spatial gestures.
//
// Colony: Nexus (e4) — Integration
// h(x) >= 0. Always.
//

import SwiftUI
import WebKit
import RealityKit

// MARK: - Spatial Agent View

/// A spatial WebView that renders HTML agents in visionOS.
///
/// Features:
/// - Glass morphism backdrop
/// - Gaze-aware interaction
/// - Hand tracking for gestures
/// - Spatial audio feedback
/// - Native bridge for device control
///
/// Usage:
/// ```swift
/// SpatialAgentView(agentId: "dashboard")
///     .environmentObject(spatialServices)
/// ```
struct SpatialAgentView: View {
    let agentId: String
    let url: URL?

    @EnvironmentObject var appModel: AppModel
    @EnvironmentObject var spatialServices: SpatialServicesContainer

    @State private var isLoading = true
    @State private var webViewError: Error?
    @State private var isGazeFocused = false

    // MARK: - Initializers

    init(agentId: String) {
        self.agentId = agentId
        self.url = nil
    }

    init(url: URL) {
        self.agentId = url.lastPathComponent.replacingOccurrences(of: ".html", with: "")
        self.url = url
    }

    // MARK: - Body

    var body: some View {
        ZStack {
            // Glass background
            RoundedRectangle(cornerRadius: 24)
                .fill(.ultraThinMaterial)
                .opacity(isGazeFocused ? 0.9 : 0.7)

            // WebView
            SpatialWebView(
                agentId: agentId,
                url: resolvedURL,
                isLoading: $isLoading,
                error: $webViewError,
                spatialServices: spatialServices,
                appModel: appModel
            )
            .clipShape(RoundedRectangle(cornerRadius: 20))
            .padding(4)

            // Loading overlay
            if isLoading {
                ProgressView()
                    .progressViewStyle(CircularProgressViewStyle(tint: .white))
                    .scaleEffect(1.5)
            }

            // Error overlay
            if let error = webViewError {
                VStack(spacing: 16) {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .font(.system(size: 40))
                        .foregroundColor(.orange)

                    Text("Failed to load agent")
                        .font(.headline)

                    Text(error.localizedDescription)
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .multilineTextAlignment(.center)
                }
                .padding()
                .background(.ultraThinMaterial)
                .clipShape(RoundedRectangle(cornerRadius: 16))
            }
        }
        .frame(width: 800, height: 600)
        .hoverEffect(.highlight)
        .onHover { hovering in
            isGazeFocused = hovering
            if hovering {
                spatialServices.audioService.play(.select)
            }
        }
        .gesture(
            TapGesture()
                .onEnded { _ in
                    spatialServices.audioService.play(.select)
                }
        )
    }

    // MARK: - Helpers

    private var resolvedURL: URL {
        if let url = url {
            return url
        }

        let baseURL = appModel.apiService.currentURL
        return URL(string: "\(baseURL)/agents/\(agentId).html")
            ?? URL(string: "kagami://agents/\(agentId)")!
    }
}

// MARK: - Spatial WebView (UIViewRepresentable)

struct SpatialWebView: UIViewRepresentable {
    let agentId: String
    let url: URL
    @Binding var isLoading: Bool
    @Binding var error: Error?

    let spatialServices: SpatialServicesContainer
    let appModel: AppModel

    func makeCoordinator() -> Coordinator {
        Coordinator(self)
    }

    func makeUIView(context: Context) -> WKWebView {
        // Configure WebView
        let configuration = WKWebViewConfiguration()
        configuration.defaultWebpagePreferences.allowsContentJavaScript = true

        // Set up user content controller
        let contentController = WKUserContentController()

        // Add native bridge
        let bridge = VisionNativeBridge(
            spatialServices: spatialServices,
            appModel: appModel
        )
        contentController.add(bridge, name: "kagamiBridge")
        context.coordinator.bridge = bridge

        // Inject setup script
        let setupScript = createSetupScript()
        let userScript = WKUserScript(
            source: setupScript,
            injectionTime: .atDocumentStart,
            forMainFrameOnly: true
        )
        contentController.addUserScript(userScript)

        configuration.userContentController = contentController

        // Create WebView
        let webView = WKWebView(frame: .zero, configuration: configuration)
        webView.navigationDelegate = context.coordinator

        // Configure appearance for visionOS
        webView.isOpaque = false
        webView.backgroundColor = .clear
        webView.scrollView.backgroundColor = .clear

        // Store reference in bridge
        bridge.webView = webView

        return webView
    }

    func updateUIView(_ webView: WKWebView, context: Context) {
        if webView.url != url {
            webView.load(URLRequest(url: url))
        }
    }

    private func createSetupScript() -> String {
        return """
        // Kagami Spatial Native Bridge
        window.__KAGAMI_BRIDGE__ = {
            platform: 'visionos',
            capabilities: [
                'haptic', 'spatial_audio', 'gaze_tracking',
                'hand_tracking', 'spatial_anchors', 'device_control', 'scenes'
            ],
            _callbackId: 0,
            _callbacks: new Map(),

            invoke: function(action, params) {
                return new Promise((resolve, reject) => {
                    const id = ++this._callbackId;
                    this._callbacks.set(id, { resolve, reject });

                    window.webkit.messageHandlers.kagamiBridge.postMessage({
                        id: id,
                        action: action,
                        params: params || {}
                    });

                    setTimeout(() => {
                        if (this._callbacks.has(id)) {
                            this._callbacks.delete(id);
                            reject(new Error('Bridge call timeout: ' + action));
                        }
                    }, 30000);
                });
            },

            // visionOS-specific methods
            playSpatialSound: function(soundName, position) {
                return this.invoke('spatial_audio', { sound: soundName, position: position });
            },

            getGazePosition: function() {
                return this.invoke('get_gaze_position', {});
            },

            createSpatialAnchor: function(name, position) {
                return this.invoke('create_anchor', { name: name, position: position });
            },

            // Standard methods
            haptic: function(style) {
                return this.invoke('haptic', { style: style || 'medium' });
            },

            setLights: function(level, rooms) {
                return this.invoke('setLights', { level, rooms });
            },

            executeScene: function(scene) {
                return this.invoke('executeScene', { scene });
            }
        };

        window.kagamiBridgeCallback = function(id, response) {
            const callback = window.__KAGAMI_BRIDGE__._callbacks.get(id);
            if (callback) {
                window.__KAGAMI_BRIDGE__._callbacks.delete(id);
                if (response.success) {
                    callback.resolve(response.result);
                } else {
                    callback.reject(new Error(response.error || 'Unknown error'));
                }
            }
        };

        console.log('✅ Kagami Spatial Bridge ready (visionOS)');
        """
    }

    // MARK: - Coordinator

    class Coordinator: NSObject, WKNavigationDelegate {
        var parent: SpatialWebView
        var bridge: VisionNativeBridge?

        init(_ parent: SpatialWebView) {
            self.parent = parent
        }

        func webView(_ webView: WKWebView, didStartProvisionalNavigation navigation: WKNavigation!) {
            parent.isLoading = true
            parent.error = nil
        }

        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            parent.isLoading = false
        }

        func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
            parent.isLoading = false
            parent.error = error
        }

        func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
            parent.isLoading = false
            parent.error = error
        }
    }
}

// MARK: - Vision Native Bridge

/// Native bridge for visionOS spatial capabilities
class VisionNativeBridge: NSObject, WKScriptMessageHandler {
    weak var webView: WKWebView?
    let spatialServices: SpatialServicesContainer
    let appModel: AppModel

    init(spatialServices: SpatialServicesContainer, appModel: AppModel) {
        self.spatialServices = spatialServices
        self.appModel = appModel
        super.init()
    }

    func userContentController(
        _ userContentController: WKUserContentController,
        didReceive message: WKScriptMessage
    ) {
        guard message.name == "kagamiBridge" else { return }

        guard let body = message.body as? [String: Any],
              let id = body["id"] as? Int,
              let action = body["action"] as? String else {
            return
        }

        let params = body["params"] as? [String: Any] ?? [:]

        Task { @MainActor in
            do {
                let result = try await executeAction(action, params: params)
                sendResponse(id: id, success: true, result: result)
            } catch {
                sendResponse(id: id, success: false, error: error.localizedDescription)
            }
        }
    }

    @MainActor
    private func executeAction(_ action: String, params: [String: Any]) async throws -> Any? {
        switch action {
        case "haptic":
            // visionOS uses AudioEngine for haptic-like feedback
            let style = params["style"] as? String ?? "medium"
            switch style {
            case "success":
                spatialServices.audioService.play(.success)
            case "error":
                spatialServices.audioService.play(.error)
            default:
                spatialServices.audioService.play(.tap)
            }
            return ["triggered": true]

        case "spatial_audio":
            let sound = params["sound"] as? String ?? "tap"
            let position = params["position"] as? [Float]

            if let pos = position, pos.count == 3 {
                let point = SIMD3<Float>(pos[0], pos[1], pos[2])
                spatialServices.audioService.play(.select, at: point)
            } else {
                spatialServices.audioService.play(.select)
            }
            return ["played": true]

        case "get_gaze_position":
            // Gaze tracking position not exposed in visionOS 1.0
            return ["available": false]

        case "create_anchor":
            let name = params["name"] as? String ?? "agent-anchor"
            if let position = params["position"] as? [Float], position.count == 3 {
                let point = SIMD3<Float>(position[0], position[1], position[2])
                let anchor = spatialServices.anchorService.createAnchor(
                    at: point,
                    type: .worldLocked,
                    label: name
                )
                return ["anchorId": anchor.id.uuidString]
            }
            return ["anchorId": ""]

        case "setLights":
            guard let level = params["level"] as? Int else {
                throw BridgeError.missingParameter("level")
            }
            let rooms = params["rooms"] as? [String]
            await appModel.apiService.setLights(level, rooms: rooms)
            return ["success": true]

        case "executeScene":
            guard let scene = params["scene"] as? String else {
                throw BridgeError.missingParameter("scene")
            }
            await appModel.apiService.executeScene(scene)
            return ["success": true]

        case "getPlatformInfo":
            return [
                "platform": "visionos",
                "spatialFeaturesAvailable": spatialServices.spatialFeaturesAvailable,
                "handTrackingAvailable": spatialServices.isFeatureAvailable("handTracking"),
                "gazeTrackingAvailable": spatialServices.isFeatureAvailable("gazeTracking"),
                "capabilities": [
                    "haptic", "spatial_audio", "gaze_tracking",
                    "hand_tracking", "spatial_anchors", "device_control", "scenes"
                ]
            ]

        default:
            throw BridgeError.unknownAction(action)
        }
    }

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

        if let jsonData = try? JSONSerialization.data(withJSONObject: response),
           let jsonString = String(data: jsonData, encoding: .utf8) {
            let js = "window.kagamiBridgeCallback(\(id), \(jsonString))"
            DispatchQueue.main.async {
                webView.evaluateJavaScript(js) { _, _ in }
            }
        }
    }
}

// MARK: - Bridge Errors

enum BridgeError: LocalizedError {
    case unknownAction(String)
    case missingParameter(String)

    var errorDescription: String? {
        switch self {
        case .unknownAction(let action):
            return "Unknown action: \(action)"
        case .missingParameter(let param):
            return "Missing required parameter: \(param)"
        }
    }
}

// MARK: - Agent Browser View (Spatial)

/// A spatial browser for discovering and opening HTML agents
struct SpatialAgentBrowserView: View {
    @EnvironmentObject var appModel: AppModel
    @EnvironmentObject var spatialServices: SpatialServicesContainer
    @Environment(\.openWindow) private var openWindow

    @State private var agents: [AgentInfo] = []
    @State private var isLoading = true
    @State private var selectedAgent: AgentInfo?

    var body: some View {
        NavigationStack {
            Group {
                if isLoading {
                    ProgressView()
                        .progressViewStyle(CircularProgressViewStyle(tint: .white))
                } else if agents.isEmpty {
                    ContentUnavailableView(
                        "No Agents",
                        systemImage: "app.connected.to.app.below.fill",
                        description: Text("Connect to Kagami to load agents")
                    )
                } else {
                    ScrollView {
                        LazyVGrid(columns: [
                            GridItem(.adaptive(minimum: 200, maximum: 300), spacing: 16)
                        ], spacing: 16) {
                            ForEach(agents) { agent in
                                SpatialAgentCard(agent: agent)
                                    .onTapGesture {
                                        selectedAgent = agent
                                        spatialServices.audioService.play(.select)
                                    }
                            }
                        }
                        .padding()
                    }
                }
            }
            .navigationTitle("Agents")
            .task {
                await loadAgents()
            }
            .refreshable {
                await loadAgents()
            }
            .sheet(item: $selectedAgent) { agent in
                NavigationStack {
                    SpatialAgentView(agentId: agent.id)
                        .environmentObject(appModel)
                        .environmentObject(spatialServices)
                        .navigationTitle(agent.name)
                        .toolbar {
                            ToolbarItem(placement: .cancellationAction) {
                                Button("Done") {
                                    selectedAgent = nil
                                }
                            }
                        }
                }
            }
        }
    }

    private func loadAgents() async {
        isLoading = true
        defer { isLoading = false }

        // TODO: Fetch from API
        agents = [
            AgentInfo(id: "dashboard", name: "Dashboard", description: "Home overview and quick actions", colony: "nexus"),
            AgentInfo(id: "rooms", name: "Rooms", description: "Per-room device control", colony: "beacon"),
            AgentInfo(id: "scenes", name: "Scenes", description: "Scene activation", colony: "forge")
        ]
    }
}

// MARK: - Agent Info Model

struct AgentInfo: Identifiable {
    let id: String
    let name: String
    let description: String
    let colony: String
}

// MARK: - Spatial Agent Card

struct SpatialAgentCard: View {
    let agent: AgentInfo

    var colonyColor: Color {
        switch agent.colony {
        case "spark": return .red
        case "forge": return .orange
        case "flow": return .purple
        case "nexus": return .blue
        case "beacon": return .yellow
        case "grove": return .green
        case "crystal": return .cyan
        default: return .cyan
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Icon
            ZStack {
                Circle()
                    .fill(colonyColor.opacity(0.2))
                    .frame(width: 48, height: 48)

                Text(String(agent.name.prefix(1)))
                    .font(.title2.bold())
                    .foregroundColor(colonyColor)
            }

            // Name
            Text(agent.name)
                .font(.headline)
                .foregroundColor(.primary)

            // Description
            Text(agent.description)
                .font(.caption)
                .foregroundColor(.secondary)
                .lineLimit(2)
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.ultraThinMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .hoverEffect(.highlight)
    }
}

// MARK: - Preview

#Preview("Spatial Agent View") {
    SpatialAgentView(agentId: "dashboard")
        .environmentObject(AppModel())
        .environmentObject(SpatialServicesContainer())
}

#Preview("Spatial Agent Browser") {
    SpatialAgentBrowserView()
        .environmentObject(AppModel())
        .environmentObject(SpatialServicesContainer())
}

/*
 * 鏡
 * h(x) >= 0. Always.
 */
