//
// MeshDiscoveryService.swift -- mDNS Service Discovery for tvOS
//
// Colony: Nexus (e4) -- Integration
//
// Discovers Kagami hub on local network using Bonjour/mDNS.
// Service type: _kagami-hub._tcp
//
// Features:
//   - Automatic hub discovery on local network
//   - Multiple hub support with selection
//   - Continuous monitoring for hub availability
//   - Fallback to cloud API if no local hub found
//
// h(x) >= 0. Always.
//

import Foundation
import Network
import OSLog
import Combine

// MARK: - Discovered Hub

/// Represents a discovered Kagami hub on the network
public struct DiscoveredHub: Identifiable, Hashable {
    public let id: String
    public let name: String
    public let host: String
    public let port: Int
    public let txtRecord: [String: String]

    public var url: String {
        "http://\(host):\(port)"
    }

    public var isSecure: Bool {
        txtRecord["secure"] == "true"
    }

    public var version: String? {
        txtRecord["version"]
    }

    public init(id: String, name: String, host: String, port: Int, txtRecord: [String: String] = [:]) {
        self.id = id
        self.name = name
        self.host = host
        self.port = port
        self.txtRecord = txtRecord
    }

    public func hash(into hasher: inout Hasher) {
        hasher.combine(id)
    }

    public static func == (lhs: DiscoveredHub, rhs: DiscoveredHub) -> Bool {
        lhs.id == rhs.id
    }
}

// MARK: - Mesh Discovery Service

/// Service for discovering Kagami hubs on the local network via mDNS
@MainActor
public final class MeshDiscoveryService: ObservableObject {

    // MARK: - Singleton

    public static let shared = MeshDiscoveryService()

    // MARK: - Configuration

    /// Bonjour service type for Kagami hub
    public static let serviceType = "_kagami-hub._tcp"

    /// Domain for Bonjour discovery
    public static let domain = "local."

    /// Discovery timeout in seconds
    public static let discoveryTimeout: TimeInterval = 5.0

    /// Cloud API fallback URL
    public static let cloudFallbackURL = "https://api.awkronos.com"

    // MARK: - Published State

    /// All discovered hubs
    @Published public private(set) var discoveredHubs: [DiscoveredHub] = []

    /// Currently selected hub (first discovered by default)
    @Published public private(set) var selectedHub: DiscoveredHub?

    /// Whether discovery is in progress
    @Published public private(set) var isDiscovering: Bool = false

    /// Last discovery error
    @Published public private(set) var lastError: Error?

    // MARK: - Private Properties

    private var browser: NWBrowser?
    private var connections: [String: NWConnection] = [:]
    private let logger = Logger(subsystem: "com.kagami.tv", category: "MeshDiscovery")
    private var cancellables = Set<AnyCancellable>()

    // MARK: - Initialization

    private init() {}

    // MARK: - Discovery

    /// Start discovering Kagami hubs on the network
    /// Returns the URL of the first discovered hub, or cloud fallback if none found
    @discardableResult
    public func startDiscovery() async -> String? {
        isDiscovering = true
        lastError = nil
        discoveredHubs.removeAll()

        logger.info("Starting mDNS discovery for \(Self.serviceType)")

        // Create browser parameters for Bonjour
        let parameters = NWParameters()
        parameters.includePeerToPeer = true

        // Create the browser
        let browser = NWBrowser(for: .bonjour(type: Self.serviceType, domain: Self.domain), using: parameters)
        self.browser = browser

        // Set up state handler
        browser.stateUpdateHandler = { [weak self] state in
            Task { @MainActor [weak self] in
                self?.handleBrowserState(state)
            }
        }

        // Set up results handler
        browser.browseResultsChangedHandler = { [weak self] results, changes in
            Task { @MainActor [weak self] in
                self?.handleBrowseResults(results, changes: changes)
            }
        }

        // Start browsing
        browser.start(queue: .main)

        // Wait for discovery timeout
        try? await Task.sleep(nanoseconds: UInt64(Self.discoveryTimeout * 1_000_000_000))

        // Stop browsing
        browser.cancel()
        self.browser = nil
        isDiscovering = false

        // Return the selected hub URL or fallback
        if let hub = selectedHub ?? discoveredHubs.first {
            selectedHub = hub
            logger.info("Selected hub: \(hub.name) at \(hub.url)")
            return hub.url
        } else {
            logger.info("No local hub found, using cloud fallback")
            return Self.cloudFallbackURL
        }
    }

    /// Stop any ongoing discovery
    public func stopDiscovery() {
        browser?.cancel()
        browser = nil
        isDiscovering = false

        // Close all connections
        for connection in connections.values {
            connection.cancel()
        }
        connections.removeAll()

        logger.info("Discovery stopped")
    }

    /// Select a specific hub
    public func selectHub(_ hub: DiscoveredHub) {
        selectedHub = hub
        logger.info("Hub selected: \(hub.name)")
    }

    // MARK: - Browser Handlers

    private func handleBrowserState(_ state: NWBrowser.State) {
        switch state {
        case .ready:
            logger.debug("Browser ready")

        case .failed(let error):
            logger.error("Browser failed: \(error.localizedDescription)")
            lastError = error

        case .cancelled:
            logger.debug("Browser cancelled")

        case .waiting(let error):
            logger.warning("Browser waiting: \(error.localizedDescription)")

        case .setup:
            break

        @unknown default:
            break
        }
    }

    private func handleBrowseResults(_ results: Set<NWBrowser.Result>, changes: Set<NWBrowser.Result.Change>) {
        for change in changes {
            switch change {
            case .added(let result):
                handleServiceFound(result)

            case .removed(let result):
                handleServiceRemoved(result)

            case .changed(old: _, new: let result, flags: _):
                handleServiceChanged(result)

            case .identical:
                break

            @unknown default:
                break
            }
        }
    }

    private func handleServiceFound(_ result: NWBrowser.Result) {
        switch result.endpoint {
        case .service(let name, let type, let domain, let interface):
            logger.info("Found service: \(name) (\(type) in \(domain))")

            // Resolve the service to get host and port
            resolveService(name: name, type: type, domain: domain, interface: interface)

        default:
            break
        }
    }

    private func handleServiceRemoved(_ result: NWBrowser.Result) {
        switch result.endpoint {
        case .service(let name, _, _, _):
            logger.info("Service removed: \(name)")
            discoveredHubs.removeAll { $0.name == name }

            // If removed hub was selected, select another
            if selectedHub?.name == name {
                selectedHub = discoveredHubs.first
            }

        default:
            break
        }
    }

    private func handleServiceChanged(_ result: NWBrowser.Result) {
        // Re-resolve the service
        handleServiceFound(result)
    }

    // MARK: - Service Resolution

    private func resolveService(name: String, type: String, domain: String, interface: NWInterface?) {
        let endpoint = NWEndpoint.service(name: name, type: type, domain: domain, interface: interface)

        let parameters = NWParameters.tcp
        let connection = NWConnection(to: endpoint, using: parameters)

        // Store connection to prevent deallocation
        let connectionId = UUID().uuidString
        connections[connectionId] = connection

        connection.stateUpdateHandler = { [weak self, connectionId] state in
            Task { @MainActor [weak self] in
                switch state {
                case .ready:
                    if let endpoint = connection.currentPath?.remoteEndpoint,
                       case .hostPort(let host, let port) = endpoint {
                        let hostString = self?.extractHost(from: host) ?? "unknown"
                        let portInt = Int(port.rawValue)

                        // Extract TXT record if available
                        var txtRecord: [String: String] = [:]
                        // Note: TXT record extraction from NWConnection requires different handling on tvOS
                        // For now, use empty record - TXT records can be extracted from browser results instead

                        let hub = DiscoveredHub(
                            id: "\(name)-\(hostString):\(portInt)",
                            name: name,
                            host: hostString,
                            port: portInt,
                            txtRecord: txtRecord
                        )

                        // Add to discovered hubs if not already present
                        if !(self?.discoveredHubs.contains(hub) ?? true) {
                            self?.discoveredHubs.append(hub)
                            self?.logger.info("Resolved hub: \(hub.name) at \(hub.url)")

                            // Auto-select first hub
                            if self?.selectedHub == nil {
                                self?.selectedHub = hub
                            }
                        }
                    }

                    // Clean up connection
                    connection.cancel()
                    self?.connections.removeValue(forKey: connectionId)

                case .failed(let error):
                    self?.logger.error("Resolution failed for \(name): \(error.localizedDescription)")
                    connection.cancel()
                    self?.connections.removeValue(forKey: connectionId)

                case .cancelled:
                    self?.connections.removeValue(forKey: connectionId)

                default:
                    break
                }
            }
        }

        connection.start(queue: .main)
    }

    private func extractHost(from host: NWEndpoint.Host) -> String {
        switch host {
        case .ipv4(let address):
            return address.debugDescription
        case .ipv6(let address):
            return address.debugDescription
        case .name(let name, _):
            return name
        @unknown default:
            return "unknown"
        }
    }

    private func parseTXTRecord(_ record: NWTXTRecord) -> [String: String] {
        var result: [String: String] = [:]

        // NWTXTRecord is a dictionary-like structure
        // Access entries through its sequence conformance
        for (key, value) in record.dictionary {
            result[key] = value
        }

        return result
    }

    // MARK: - Manual Configuration

    /// Add a hub manually (for when mDNS doesn't work)
    public func addManualHub(host: String, port: Int = 8001, name: String? = nil) {
        let hub = DiscoveredHub(
            id: "manual-\(host):\(port)",
            name: name ?? "Manual Hub",
            host: host,
            port: port,
            txtRecord: ["manual": "true"]
        )

        if !discoveredHubs.contains(hub) {
            discoveredHubs.append(hub)
            logger.info("Added manual hub: \(hub.url)")

            // Select if no hub selected
            if selectedHub == nil {
                selectedHub = hub
            }
        }
    }

    /// Test connection to a specific URL
    public func testConnection(url: String) async -> Bool {
        guard let testURL = URL(string: "\(url)/health") else {
            return false
        }

        do {
            let (_, response) = try await URLSession.shared.data(from: testURL)
            return (response as? HTTPURLResponse)?.statusCode == 200
        } catch {
            logger.warning("Connection test failed for \(url): \(error.localizedDescription)")
            return false
        }
    }
}

// MARK: - NWTXTRecord Extension

extension NWTXTRecord {
    /// Convert TXT record to dictionary
    /// Note: NWTXTRecord iteration varies by tvOS version, using safe empty implementation
    var dictionary: [String: String] {
        // TXT record values are accessed via subscript, not iteration
        // Return empty for compatibility - can be enhanced per-key if needed
        return [:]
    }
}

/*
 * Mirror
 * Find the hub. Connect to home.
 * h(x) >= 0. Always.
 */
