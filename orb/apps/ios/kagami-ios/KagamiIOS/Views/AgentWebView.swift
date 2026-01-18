//
// AgentWebView.swift — WebView Container for HTML Agents
//
// Renders HTML agents with native bridge support.
// Enables agent websites to use iOS capabilities via JavaScript.
//
// Colony: Nexus (e4) — Integration
// h(x) >= 0. Always.

import SwiftUI
import WebKit
import KagamiDesign

// MARK: - Agent WebView

/// SwiftUI wrapper for WKWebView that renders HTML agents.
///
/// Features:
/// - Native bridge for JavaScript-to-Swift communication
/// - Offline caching support
/// - Dark mode sync with iOS
/// - Safe area handling
///
/// Usage:
/// ```swift
/// AgentWebView(agentId: "dashboard")
/// AgentWebView(url: URL(string: "https://api.awkronos.com/agents/dashboard.html")!)
/// ```
struct AgentWebView: UIViewRepresentable {

    // MARK: - Properties

    /// Agent identifier for loading from local/remote agents
    let agentId: String?

    /// Direct URL override (optional)
    let url: URL?

    /// Environment objects
    @EnvironmentObject var appModel: AppModel

    // MARK: - Initializers

    /// Initialize with agent ID (will resolve to URL)
    init(agentId: String) {
        self.agentId = agentId
        self.url = nil
    }

    /// Initialize with direct URL
    init(url: URL) {
        self.agentId = nil
        self.url = url
    }

    // MARK: - UIViewRepresentable

    func makeCoordinator() -> Coordinator {
        Coordinator(self)
    }

    func makeUIView(context: Context) -> WKWebView {
        // Configure WebView
        let configuration = WKWebViewConfiguration()

        // Enable JavaScript
        configuration.defaultWebpagePreferences.allowsContentJavaScript = true

        // Set up user content controller for bridge
        let contentController = WKUserContentController()

        // Add native bridge handler
        let bridge = KagamiNativeBridge()
        contentController.add(bridge, name: "kagamiBridge")

        // Inject platform info and bridge setup script
        let setupScript = """
        // Kagami Native Bridge Setup
        window.__KAGAMI_BRIDGE__ = {
            platform: 'ios',
            capabilities: ['haptic', 'notification', 'share', 'device_control', 'scenes'],
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

                    // Timeout after 30 seconds
                    setTimeout(() => {
                        if (this._callbacks.has(id)) {
                            this._callbacks.delete(id);
                            reject(new Error('Bridge call timeout: ' + action));
                        }
                    }, 30000);
                });
            },

            // Convenience methods
            haptic: function(style) {
                return this.invoke('haptic', { style: style || 'medium' });
            },

            notify: function(title, body) {
                return this.invoke('notification', { title, body });
            },

            share: function(text, url) {
                return this.invoke('share', { text, url });
            },

            setLights: function(level, rooms) {
                return this.invoke('setLights', { level, rooms });
            },

            executeScene: function(scene) {
                return this.invoke('executeScene', { scene });
            }
        };

        // Callback handler (called from native)
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

        console.log('✅ Kagami Native Bridge ready (iOS)');
        """

        let userScript = WKUserScript(
            source: setupScript,
            injectionTime: .atDocumentStart,
            forMainFrameOnly: true
        )
        contentController.addUserScript(userScript)

        configuration.userContentController = contentController

        // Configure preferences
        let preferences = WKWebpagePreferences()
        preferences.allowsContentJavaScript = true
        configuration.defaultWebpagePreferences = preferences

        // Create WebView
        let webView = WKWebView(frame: .zero, configuration: configuration)
        webView.navigationDelegate = context.coordinator
        webView.uiDelegate = context.coordinator

        // Store bridge reference
        bridge.webView = webView
        context.coordinator.bridge = bridge

        // Configure appearance
        webView.isOpaque = false
        webView.backgroundColor = UIColor(Color.void)
        webView.scrollView.backgroundColor = UIColor(Color.void)

        // Allow scroll bouncing
        webView.scrollView.bounces = true
        webView.scrollView.alwaysBounceVertical = true

        // Safe area insets
        webView.scrollView.contentInsetAdjustmentBehavior = .automatic

        return webView
    }

    func updateUIView(_ webView: WKWebView, context: Context) {
        // Resolve URL
        let targetURL: URL?

        if let url = url {
            targetURL = url
        } else if let agentId = agentId {
            // Resolve agent ID to URL
            // First try local API, then fallback to bundled
            let apiBase = KagamiAPIService.shared.currentBaseURL
            targetURL = URL(string: "\(apiBase)/agents/\(agentId).html")
                ?? URL(string: "kagami://agents/\(agentId)")
        } else {
            return
        }

        guard let validURL = targetURL else {
            print("AgentWebView: Failed to construct valid URL for agent")
            return
        }

        // Only load if URL changed
        if webView.url != validURL {
            let request = URLRequest(url: validURL)
            webView.load(request)
        }
    }

    // MARK: - Coordinator

    class Coordinator: NSObject, WKNavigationDelegate, WKUIDelegate {
        var parent: AgentWebView
        var bridge: KagamiNativeBridge?

        init(_ parent: AgentWebView) {
            self.parent = parent
        }

        // MARK: - WKNavigationDelegate

        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            print("✅ Agent loaded: \(webView.url?.absoluteString ?? "unknown")")

            // Inject dark mode CSS if needed
            injectDarkModeStyles(webView)
        }

        func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
            print("⚠️ Agent load failed: \(error.localizedDescription)")
        }

        func webView(
            _ webView: WKWebView,
            decidePolicyFor navigationAction: WKNavigationAction,
            decisionHandler: @escaping (WKNavigationActionPolicy) -> Void
        ) {
            guard let url = navigationAction.request.url else {
                decisionHandler(.allow)
                return
            }

            // Handle special URL schemes
            if url.scheme == "kagami" {
                handleKagamiScheme(url)
                decisionHandler(.cancel)
                return
            }

            // Allow local and kagami.local URLs
            if url.scheme == "file" ||
               url.host == "localhost" ||
               url.host?.hasSuffix(".local") == true {
                decisionHandler(.allow)
                return
            }

            // For external URLs, open in Safari
            if url.scheme == "https" || url.scheme == "http" {
                UIApplication.shared.open(url)
                decisionHandler(.cancel)
                return
            }

            decisionHandler(.allow)
        }

        // MARK: - WKUIDelegate

        func webView(
            _ webView: WKWebView,
            createWebViewWith configuration: WKWebViewConfiguration,
            for navigationAction: WKNavigationAction,
            windowFeatures: WKWindowFeatures
        ) -> WKWebView? {
            // Handle target="_blank" links
            if navigationAction.targetFrame == nil {
                webView.load(navigationAction.request)
            }
            return nil
        }

        // MARK: - Helpers

        private func handleKagamiScheme(_ url: URL) {
            // Handle kagami:// URLs
            // e.g., kagami://agents/dashboard
            //       kagami://scene/movie_mode

            guard let host = url.host else { return }

            switch host {
            case "agents":
                let agentId = url.lastPathComponent
                print("📱 Navigate to agent: \(agentId)")
                // TODO: Navigate to agent

            case "scene":
                let sceneName = url.lastPathComponent
                Task {
                    _ = await SceneService.shared.execute(sceneName)
                }

            default:
                print("⚠️ Unknown kagami scheme: \(url)")
            }
        }

        private func injectDarkModeStyles(_ webView: WKWebView) {
            // Ensure dark mode is applied
            let darkModeScript = """
            (function() {
                if (!document.documentElement.hasAttribute('data-theme')) {
                    document.documentElement.setAttribute('data-theme', 'dark');
                }
            })();
            """
            webView.evaluateJavaScript(darkModeScript, completionHandler: nil)
        }
    }
}

// MARK: - Agent Browser View

/// View that lists and opens HTML agents
struct AgentBrowserView: View {
    @State private var agents: [AgentInfo] = []
    @State private var isLoading = true
    @State private var selectedAgent: AgentInfo?

    var body: some View {
        NavigationStack {
            Group {
                if isLoading {
                    ProgressView()
                        .progressViewStyle(CircularProgressViewStyle(tint: .crystal))
                } else if agents.isEmpty {
                    ContentUnavailableView(
                        "No Agents",
                        systemImage: "app.badge",
                        description: Text("Connect to Kagami to load agents")
                    )
                } else {
                    List(agents) { agent in
                        AgentRow(agent: agent)
                            .onTapGesture {
                                selectedAgent = agent
                            }
                    }
                    .listStyle(.insetGrouped)
                }
            }
            .navigationTitle("Agents")
            .navigationBarTitleDisplayMode(.large)
            .task {
                await loadAgents()
            }
            .refreshable {
                await loadAgents()
            }
            .sheet(item: $selectedAgent) { agent in
                NavigationStack {
                    AgentWebView(agentId: agent.id)
                        .environmentObject(AppModel())
                        .navigationTitle(agent.name)
                        .navigationBarTitleDisplayMode(.inline)
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

        // TODO: Fetch agents from API
        // For now, return built-in agents
        agents = [
            AgentInfo(id: "dashboard", name: "Dashboard", description: "Home overview and quick actions", colony: "nexus"),
            AgentInfo(id: "rooms", name: "Rooms", description: "Per-room device control", colony: "beacon"),
            AgentInfo(id: "scenes", name: "Scenes", description: "Scene activation", colony: "forge"),
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

// MARK: - Agent Row

struct AgentRow: View {
    let agent: AgentInfo

    var colonyColor: Color {
        switch agent.colony {
        case "spark": return .spark
        case "forge": return .forge
        case "flow": return .flow
        case "nexus": return .nexus
        case "beacon": return .beacon
        case "grove": return .grove
        case "crystal": return .crystal
        default: return .crystal
        }
    }

    var body: some View {
        HStack(spacing: KagamiSpacing.md) {
            Circle()
                .fill(colonyColor.opacity(0.2))
                .frame(width: 44, height: 44)
                .overlay(
                    Text(String(agent.name.prefix(1)))
                        .font(KagamiFont.headline())
                        .foregroundColor(colonyColor)
                )

            VStack(alignment: .leading, spacing: KagamiSpacing.xs) {
                Text(agent.name)
                    .font(KagamiFont.headline())
                    .foregroundColor(.accessibleTextPrimary)

                Text(agent.description)
                    .font(KagamiFont.caption())
                    .foregroundColor(.accessibleTextSecondary)
                    .lineLimit(1)
            }

            Spacer()

            Image(systemName: "chevron.right")
                .font(.caption)
                .foregroundColor(.accessibleTextTertiary)
        }
        .padding(.vertical, KagamiSpacing.xs)
        .contentShape(Rectangle())
    }
}

// MARK: - Preview

#Preview("Agent Browser") {
    AgentBrowserView()
        .preferredColorScheme(.dark)
}

#Preview("Agent WebView") {
    AgentWebView(agentId: "dashboard")
        .environmentObject(AppModel())
        .preferredColorScheme(.dark)
}

/*
 * 鏡
 * h(x) >= 0. Always.
 */
