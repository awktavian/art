/// Hub Discovery Protocol — Unified hub discovery interface
///
/// Defines the platform-agnostic interface for discovering Kagami Hubs.
/// iOS implements using Network.framework's NWBrowser.
/// Android implements using NsdManager.
///
/// This protocol mirrors the Rust SDK's HubDiscoveryDelegate trait.
///
/// h(x) >= 0. Always.

import Foundation
import Network
import Combine

// MARK: - Constants

/// mDNS service type for Kagami Hub discovery.
public let KagamiHubServiceType = "_kagami-hub._tcp"

/// Default hub HTTP port.
public let DefaultHubPort: UInt16 = 8080

// MARK: - Discovery Method

/// Method by which a hub was discovered.
public enum HubDiscoveryMethod: String, Codable, Sendable {
    /// Discovered via NWBrowser (Network.framework).
    case bonjour
    /// Manual configuration.
    case manual
    /// Direct IP probe.
    case directProbe
    /// Saved from previous session.
    case cached
}

// MARK: - Discovery State

/// Current state of hub discovery.
public enum HubDiscoveryState: Sendable {
    /// Discovery not started.
    case idle
    /// Discovery in progress.
    case discovering
    /// Discovery completed.
    case completed
    /// Discovery failed.
    case failed(Error)
}

// MARK: - Discovered Hub

/// Information about a discovered hub.
public struct DiscoveredHub: Identifiable, Equatable, Sendable {
    /// Unique identifier (host:port).
    public let id: String
    /// Human-readable hub name.
    public var name: String
    /// Location description.
    public var location: String
    /// IP address or hostname.
    public let host: String
    /// HTTP API port.
    public let port: UInt16
    /// Discovery method used.
    public let discoveryMethod: HubDiscoveryMethod
    /// Last seen timestamp.
    public var lastSeen: Date
    /// Whether this hub is currently reachable.
    public var isReachable: Bool
    /// Hub version if known.
    public var version: String?
    /// TXT record attributes from mDNS.
    public var attributes: [String: String]

    public init(
        name: String,
        host: String,
        port: UInt16 = DefaultHubPort,
        discoveryMethod: HubDiscoveryMethod = .manual,
        location: String = "Unknown"
    ) {
        self.id = "\(host):\(port)"
        self.name = name
        self.host = host
        self.port = port
        self.discoveryMethod = discoveryMethod
        self.location = location
        self.lastSeen = Date()
        self.isReachable = false
        self.version = nil
        self.attributes = [:]
    }

    /// Base URL for HTTP API calls.
    public var baseURL: URL {
        URL(string: "http://\(host):\(port)")!
    }

    /// WebSocket URL.
    public var websocketURL: URL {
        URL(string: "ws://\(host):\(port)/ws")!
    }

    /// Health check URL.
    public var healthURL: URL {
        baseURL.appendingPathComponent("health")
    }

    /// Update last seen timestamp.
    public mutating func touch() {
        lastSeen = Date()
    }

    /// Check if hub was seen within a duration.
    public func seenWithin(_ interval: TimeInterval) -> Bool {
        Date().timeIntervalSince(lastSeen) < interval
    }

    public static func == (lhs: DiscoveredHub, rhs: DiscoveredHub) -> Bool {
        lhs.id == rhs.id
    }
}

// MARK: - Discovery Configuration

/// Configuration for hub discovery.
public struct HubDiscoveryConfig: Sendable {
    /// Service type for mDNS.
    public let serviceType: String
    /// Discovery timeout.
    public let timeout: TimeInterval
    /// Whether to probe known addresses directly.
    public let probeKnownAddresses: Bool
    /// Known addresses to probe.
    public let knownAddresses: [(String, UInt16)]
    /// Whether to cache discovered hubs.
    public let enableCaching: Bool
    /// Hub cache TTL.
    public let cacheTTL: TimeInterval

    public init(
        serviceType: String = KagamiHubServiceType,
        timeout: TimeInterval = 10.0,
        probeKnownAddresses: Bool = true,
        knownAddresses: [(String, UInt16)] = [
            ("kagami-hub.local", DefaultHubPort),
            ("raspberrypi.local", DefaultHubPort)
        ],
        enableCaching: Bool = true,
        cacheTTL: TimeInterval = 300 // 5 minutes
    ) {
        self.serviceType = serviceType
        self.timeout = timeout
        self.probeKnownAddresses = probeKnownAddresses
        self.knownAddresses = knownAddresses
        self.enableCaching = enableCaching
        self.cacheTTL = cacheTTL
    }
}

// MARK: - Discovery Events

/// Events emitted during discovery.
public enum HubDiscoveryEvent: Sendable {
    /// Discovery started.
    case started
    /// A hub was discovered.
    case hubFound(DiscoveredHub)
    /// A hub was lost (no longer advertising).
    case hubLost(hubId: String)
    /// A hub's reachability changed.
    case reachabilityChanged(hubId: String, isReachable: Bool)
    /// Discovery completed.
    case completed(hubCount: Int)
    /// Discovery failed.
    case failed(Error)
    /// Discovery timed out.
    case timeout
}

// MARK: - Hub Discovery Delegate

/// Delegate protocol for receiving discovery events.
public protocol HubDiscoveryDelegate: AnyObject, Sendable {
    /// Called when a hub is discovered.
    func hubDiscoveryService(_ service: HubDiscoveryServiceProtocol, didFindHub hub: DiscoveredHub)

    /// Called when a hub is lost.
    func hubDiscoveryService(_ service: HubDiscoveryServiceProtocol, didLoseHub hubId: String)

    /// Called when discovery state changes.
    func hubDiscoveryService(_ service: HubDiscoveryServiceProtocol, didChangeState state: HubDiscoveryState)

    /// Called when an error occurs.
    func hubDiscoveryService(_ service: HubDiscoveryServiceProtocol, didEncounterError error: Error)
}

// MARK: - Hub Discovery Service Protocol

/// Protocol for hub discovery service implementations.
public protocol HubDiscoveryServiceProtocol: AnyObject, Sendable {
    /// The discovery configuration.
    var config: HubDiscoveryConfig { get }

    /// Current discovery state.
    var state: HubDiscoveryState { get }

    /// Currently discovered hubs.
    var discoveredHubs: [DiscoveredHub] { get }

    /// The delegate for receiving events.
    var delegate: HubDiscoveryDelegate? { get set }

    /// Start hub discovery.
    func startDiscovery()

    /// Stop hub discovery.
    func stopDiscovery()

    /// Check if a specific hub is reachable.
    func checkReachability(for hubId: String) async -> Bool

    /// Manually add a hub.
    func addManualHub(host: String, port: UInt16, name: String?)

    /// Remove a hub from the list.
    func removeHub(hubId: String)

    /// Clear all discovered hubs.
    func clearHubs()

    /// Get a specific hub by ID.
    func hub(withId id: String) -> DiscoveredHub?

    /// Get reachable hubs only.
    func reachableHubs() -> [DiscoveredHub]
}

// MARK: - NWBrowser Hub Discovery Service

/// iOS implementation of hub discovery using Network.framework.
@available(iOS 13.0, macOS 10.15, *)
public final class NWBrowserHubDiscoveryService: HubDiscoveryServiceProtocol, @unchecked Sendable {
    public let config: HubDiscoveryConfig

    private let queue = DispatchQueue(label: "com.kagami.hub-discovery", qos: .userInitiated)
    private var browser: NWBrowser?
    private var hubs: [String: DiscoveredHub] = [:]
    private let hubsLock = NSLock()
    private var discoveryTimer: Timer?

    private var _state: HubDiscoveryState = .idle
    public var state: HubDiscoveryState {
        get { _state }
    }

    public weak var delegate: HubDiscoveryDelegate?

    public var discoveredHubs: [DiscoveredHub] {
        hubsLock.lock()
        defer { hubsLock.unlock() }
        return Array(hubs.values)
    }

    public init(config: HubDiscoveryConfig = HubDiscoveryConfig()) {
        self.config = config
    }

    public func startDiscovery() {
        queue.async { [weak self] in
            self?.startDiscoveryInternal()
        }
    }

    private func startDiscoveryInternal() {
        guard case .idle = _state else { return }

        _state = .discovering
        delegate?.hubDiscoveryService(self, didChangeState: .discovering)

        // Start NWBrowser
        let descriptor = NWBrowser.Descriptor.bonjour(type: config.serviceType, domain: nil)
        let parameters = NWParameters()
        parameters.includePeerToPeer = true

        browser = NWBrowser(for: descriptor, using: parameters)
        browser?.stateUpdateHandler = { [weak self] state in
            self?.handleBrowserState(state)
        }
        browser?.browseResultsChangedHandler = { [weak self] results, changes in
            self?.handleBrowseResults(results, changes: changes)
        }
        browser?.start(queue: queue)

        // Also probe known addresses if configured
        if config.probeKnownAddresses {
            Task {
                await probeKnownAddresses()
            }
        }

        // Set discovery timeout
        DispatchQueue.main.async { [weak self] in
            guard let self = self else { return }
            self.discoveryTimer = Timer.scheduledTimer(withTimeInterval: self.config.timeout, repeats: false) { [weak self] _ in
                self?.handleTimeout()
            }
        }
    }

    public func stopDiscovery() {
        queue.async { [weak self] in
            self?.stopDiscoveryInternal()
        }
    }

    private func stopDiscoveryInternal() {
        browser?.cancel()
        browser = nil
        discoveryTimer?.invalidate()
        discoveryTimer = nil

        let count = discoveredHubs.count
        _state = .completed
        delegate?.hubDiscoveryService(self, didChangeState: .completed)
    }

    private func handleBrowserState(_ state: NWBrowser.State) {
        switch state {
        case .failed(let error):
            _state = .failed(error)
            delegate?.hubDiscoveryService(self, didChangeState: .failed(error))
            delegate?.hubDiscoveryService(self, didEncounterError: error)
        case .cancelled:
            break
        default:
            break
        }
    }

    private func handleBrowseResults(_ results: Set<NWBrowser.Result>, changes: Set<NWBrowser.Result.Change>) {
        for change in changes {
            switch change {
            case .added(let result):
                resolveEndpoint(result)
            case .removed(let result):
                if case .service(let name, _, _, _) = result.endpoint {
                    // Find and remove hub by name
                    hubsLock.lock()
                    if let hubId = hubs.first(where: { $0.value.name == name })?.key {
                        hubs.removeValue(forKey: hubId)
                        hubsLock.unlock()
                        delegate?.hubDiscoveryService(self, didLoseHub: hubId)
                    } else {
                        hubsLock.unlock()
                    }
                }
            default:
                break
            }
        }
    }

    private func resolveEndpoint(_ result: NWBrowser.Result) {
        guard case .service(let name, let type, let domain, let interface) = result.endpoint else {
            return
        }

        let parameters = NWParameters()
        let connection = NWConnection(to: result.endpoint, using: parameters)
        connection.stateUpdateHandler = { [weak self] state in
            switch state {
            case .ready:
                if let innerEndpoint = connection.currentPath?.remoteEndpoint,
                   case .hostPort(let host, let port) = innerEndpoint {
                    let hostString: String
                    switch host {
                    case .ipv4(let addr):
                        hostString = "\(addr)"
                    case .ipv6(let addr):
                        hostString = "\(addr)"
                    case .name(let hostname, _):
                        hostString = hostname
                    @unknown default:
                        hostString = "unknown"
                    }

                    var hub = DiscoveredHub(
                        name: name,
                        host: hostString,
                        port: port.rawValue,
                        discoveryMethod: .bonjour
                    )

                    // Parse TXT records if available
                    if case .bonjour(let txtRecord) = result.metadata {
                        hub.attributes = self?.parseTXTRecord(txtRecord) ?? [:]
                        if let location = hub.attributes["location"] {
                            hub.location = location
                        }
                        if let version = hub.attributes["version"] {
                            hub.version = version
                        }
                    }

                    self?.addHub(hub)
                }
                connection.cancel()
            case .failed:
                connection.cancel()
            default:
                break
            }
        }
        connection.start(queue: queue)
    }

    private func parseTXTRecord(_ record: NWTXTRecord) -> [String: String] {
        var result: [String: String] = [:]
        for key in record.dictionary.keys {
            if let value = record.dictionary[key] {
                result[key] = value
            }
        }
        return result
    }

    private func probeKnownAddresses() async {
        for (host, port) in config.knownAddresses {
            let hub = DiscoveredHub(
                name: "Kagami Hub",
                host: host,
                port: port,
                discoveryMethod: .directProbe
            )

            if await checkReachabilityInternal(hub: hub) {
                var reachableHub = hub
                reachableHub.isReachable = true
                addHub(reachableHub)
            }
        }
    }

    private func addHub(_ hub: DiscoveredHub) {
        hubsLock.lock()
        let isNew = hubs[hub.id] == nil
        hubs[hub.id] = hub
        hubsLock.unlock()

        if isNew {
            delegate?.hubDiscoveryService(self, didFindHub: hub)
        }
    }

    public func checkReachability(for hubId: String) async -> Bool {
        guard let hub = hub(withId: hubId) else { return false }
        let isReachable = await checkReachabilityInternal(hub: hub)

        hubsLock.lock()
        if var existingHub = hubs[hubId] {
            let wasReachable = existingHub.isReachable
            existingHub.isReachable = isReachable
            existingHub.touch()
            hubs[hubId] = existingHub
            hubsLock.unlock()

            if wasReachable != isReachable {
                delegate?.hubDiscoveryService(self, didChangeState: state)
            }
        } else {
            hubsLock.unlock()
        }

        return isReachable
    }

    private func checkReachabilityInternal(hub: DiscoveredHub) async -> Bool {
        do {
            var request = URLRequest(url: hub.healthURL)
            request.timeoutInterval = 5.0
            let (_, response) = try await URLSession.shared.data(for: request)
            return (response as? HTTPURLResponse)?.statusCode == 200
        } catch {
            return false
        }
    }

    public func addManualHub(host: String, port: UInt16, name: String? = nil) {
        let hub = DiscoveredHub(
            name: name ?? "Manual Hub",
            host: host,
            port: port,
            discoveryMethod: .manual
        )
        addHub(hub)
    }

    public func removeHub(hubId: String) {
        hubsLock.lock()
        hubs.removeValue(forKey: hubId)
        hubsLock.unlock()
        delegate?.hubDiscoveryService(self, didLoseHub: hubId)
    }

    public func clearHubs() {
        hubsLock.lock()
        hubs.removeAll()
        hubsLock.unlock()
    }

    public func hub(withId id: String) -> DiscoveredHub? {
        hubsLock.lock()
        defer { hubsLock.unlock() }
        return hubs[id]
    }

    public func reachableHubs() -> [DiscoveredHub] {
        hubsLock.lock()
        defer { hubsLock.unlock() }
        return hubs.values.filter { $0.isReachable }
    }

    private func handleTimeout() {
        stopDiscovery()
    }

    deinit {
        browser?.cancel()
        discoveryTimer?.invalidate()
    }
}

/*
 * Kagami Hub Discovery Service
 * h(x) >= 0. Always.
 */
