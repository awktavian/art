//
// OnboardingStateManager.swift — Onboarding State Management
//
// Colony: Beacon (e5) — Planning
//
// Manages all state for the onboarding flow:
//   - Step navigation and progress
//   - Server discovery and connection
//   - Integration credentials
//   - Room configuration
//   - Permission requests
//
// h(x) >= 0. Always.
//

import SwiftUI
import KagamiCore
import Network
import UserNotifications
import CoreLocation
import HealthKit

// MARK: - Demo Data Provider

/// Provides demo data for onboarding in demo mode
struct DemoDataProvider {
    struct Room: Identifiable {
        let id: String
        let name: String
        let floor: String
        let lights: [String]
        let shades: [String]
        let hvac: String?
        let audioZone: String?
    }

    static let rooms: [Room] = [
        Room(id: "57", name: "Living Room", floor: "First", lights: ["Living Room Cans"], shades: ["Living East", "Living South"], hvac: "Living HVAC", audioZone: "Living Zone"),
        Room(id: "59", name: "Kitchen", floor: "First", lights: ["Kitchen Cans", "Kitchen Pendants"], shades: [], hvac: "Kitchen HVAC", audioZone: "Kitchen Zone"),
        Room(id: "58", name: "Dining", floor: "First", lights: ["Dining Cans", "Dining Chandelier"], shades: ["Dining Shade"], hvac: nil, audioZone: "Dining Zone"),
        Room(id: "47", name: "Office", floor: "Second", lights: ["Office Cans"], shades: [], hvac: "Office HVAC", audioZone: "Office Zone"),
        Room(id: "36", name: "Primary Bedroom", floor: "Second", lights: ["Primary Cans"], shades: ["Primary North", "Primary West"], hvac: "Primary HVAC", audioZone: "Primary Zone"),
        Room(id: "39", name: "Game Room", floor: "Basement", lights: ["Game Room Cans"], shades: [], hvac: "Game HVAC", audioZone: "Game Zone"),
        Room(id: "41", name: "Gym", floor: "Basement", lights: ["Gym Cans"], shades: [], hvac: "Gym HVAC", audioZone: nil),
    ]
}

// MARK: - Onboarding State Manager

@MainActor
class OnboardingStateManager: ObservableObject {
    // Step state
    @Published var currentStep: OnboardingStep = .welcome
    @Published var completedSteps: Set<OnboardingStep> = []

    // Server state
    @Published var discoveredServers: [OnboardingServer] = []
    @Published var selectedServer: OnboardingServer?
    // Security: Default to HTTPS production URL
    @Published var serverURL: String = "https://api.awkronos.com"
    @Published var isDiscovering: Bool = false
    @Published var isConnecting: Bool = false
    @Published var connectionError: String?
    @Published var isServerConnected: Bool = false

    // Demo mode
    @Published var isDemoMode: Bool = false

    // Integration state
    @Published var selectedIntegration: SmartHomeIntegration?
    @Published var isTestingIntegration: Bool = false
    @Published var integrationConnected: Bool = false
    @Published var integrationError: String?

    // Integration credentials
    @Published var control4Host: String = ""
    @Published var control4Port: String = "5020"
    @Published var control4ApiKey: String = ""
    @Published var lutronHost: String = ""
    @Published var lutronPassword: String = ""
    @Published var smartthingsToken: String = ""
    @Published var homeAssistantURL: String = ""
    @Published var homeAssistantToken: String = ""
    @Published var hubitatHost: String = ""
    @Published var hubitatToken: String = ""

    // Room state
    @Published var discoveredRooms: [OnboardingRoom] = []
    @Published var isLoadingRooms: Bool = false

    // Permission state
    @Published var permissions: [PermissionState] = [
        PermissionState(
            id: "notifications",
            name: "Notifications",
            description: "Receive alerts and scene updates",
            icon: "bell.fill",
            status: .notDetermined,
            isRequired: false
        ),
        PermissionState(
            id: "location",
            name: "Location",
            description: "Enable presence detection",
            icon: "location.fill",
            status: .notDetermined,
            isRequired: false
        ),
        PermissionState(
            id: "health",
            name: "Health",
            description: "Sync sleep and activity data",
            icon: "heart.fill",
            status: .notDetermined,
            isRequired: false
        )
    ]

    // Network browser
    private var browser: NWBrowser?
    private var locationManager: CLLocationManager?

    // MARK: - Persistence Keys

    private let kCurrentStep = "onboarding.currentStep"
    private let kCompletedSteps = "onboarding.completedSteps"
    private let kServerURL = "kagamiServerURL"
    private let kIsDemoMode = "isDemoMode"
    private let kSelectedIntegration = "onboarding.selectedIntegration"

    init() {
        loadState()
        checkInitialPermissions()
    }

    // MARK: - State Persistence

    func loadState() {
        if let step = UserDefaults.standard.value(forKey: kCurrentStep) as? Int,
           let onboardingStep = OnboardingStep(rawValue: step) {
            currentStep = onboardingStep
        }

        if let completedData = UserDefaults.standard.array(forKey: kCompletedSteps) as? [Int] {
            completedSteps = Set(completedData.compactMap { OnboardingStep(rawValue: $0) })
        }

        if let url = UserDefaults.standard.string(forKey: kServerURL) {
            serverURL = url
        }

        isDemoMode = UserDefaults.standard.bool(forKey: kIsDemoMode)

        if let integrationRaw = UserDefaults.standard.string(forKey: kSelectedIntegration),
           let integration = SmartHomeIntegration(rawValue: integrationRaw) {
            selectedIntegration = integration
        }
    }

    func saveState() {
        UserDefaults.standard.set(currentStep.rawValue, forKey: kCurrentStep)
        UserDefaults.standard.set(completedSteps.map { $0.rawValue }, forKey: kCompletedSteps)
        UserDefaults.standard.set(serverURL, forKey: kServerURL)
        UserDefaults.standard.set(isDemoMode, forKey: kIsDemoMode)

        if let integration = selectedIntegration {
            UserDefaults.standard.set(integration.rawValue, forKey: kSelectedIntegration)
        }
    }

    // MARK: - Navigation

    func nextStep() {
        completedSteps.insert(currentStep)
        KagamiAnalytics.shared.trackOnboardingStep(
            currentStep.rawValue,
            name: currentStep.title,
            completed: true
        )

        if let nextIndex = OnboardingStep.allCases.firstIndex(of: currentStep),
           nextIndex + 1 < OnboardingStep.allCases.count {
            withAnimation(KagamiMotion.smooth) {
                currentStep = OnboardingStep.allCases[nextIndex + 1]
            }
        }

        saveState()
    }

    func previousStep() {
        if let currentIndex = OnboardingStep.allCases.firstIndex(of: currentStep),
           currentIndex > 0 {
            withAnimation(KagamiMotion.smooth) {
                currentStep = OnboardingStep.allCases[currentIndex - 1]
            }
        }
    }

    func skipStep() {
        KagamiAnalytics.shared.trackOnboardingStep(
            currentStep.rawValue,
            name: currentStep.title,
            skipped: true
        )
        nextStep()
    }

    func goToStep(_ step: OnboardingStep) {
        withAnimation(KagamiMotion.smooth) {
            currentStep = step
        }
        saveState()
    }

    // MARK: - Server Discovery (mDNS)

    func startServerDiscovery() {
        isDiscovering = true
        discoveredServers = []
        connectionError = nil
        KagamiAnalytics.shared.track(.serverDiscoveryStarted)

        let parameters = NWParameters()
        parameters.includePeerToPeer = true

        browser = NWBrowser(
            for: .bonjour(type: "_kagami._tcp", domain: nil),
            using: parameters
        )

        browser?.stateUpdateHandler = { [weak self] state in
            Task { @MainActor in
                switch state {
                case .failed(let error):
                    self?.isDiscovering = false
                    self?.connectionError = "Discovery failed: \(error.localizedDescription)"
                    KagamiAnalytics.shared.trackError("server_discovery_failed", error: error)
                default:
                    break
                }
            }
        }

        browser?.browseResultsChangedHandler = { [weak self] results, _ in
            Task { @MainActor in
                for result in results {
                    if case .service(let name, let type, let domain, _) = result.endpoint {
                        self?.resolveService(name: name, type: type, domain: domain)
                    }
                }
            }
        }

        browser?.start(queue: .main)

        // Also try common addresses
        Task {
            await tryCommonAddresses()

            // Stop after 5 seconds
            try? await Task.sleep(nanoseconds: 5_000_000_000)
            await MainActor.run {
                stopServerDiscovery()
            }
        }
    }

    func stopServerDiscovery() {
        browser?.cancel()
        browser = nil
        isDiscovering = false
    }

    private func resolveService(name: String, type: String, domain: String) {
        let endpoint = NWEndpoint.service(name: name, type: type, domain: domain, interface: nil)
        let connection = NWConnection(to: endpoint, using: .tcp)

        connection.stateUpdateHandler = { [weak self] state in
            if case .ready = state {
                if let innerEndpoint = connection.currentPath?.remoteEndpoint,
                   case .hostPort(let host, let port) = innerEndpoint {
                    // Security: Use HTTPS for discovered local services (self-signed certs)
                    let url = "https://\(host):\(port)"
                    Task { @MainActor in
                        guard let self = self else { return }
                        let server = OnboardingServer(
                            name: name,
                            url: url,
                            host: String(describing: host),
                            port: Int(port.rawValue),
                            isSecure: true
                        )
                        if !self.discoveredServers.contains(server) {
                            self.discoveredServers.append(server)
                            KagamiAnalytics.shared.track(.serverDiscovered, properties: [
                                "server_name": name,
                                "server_url": url
                            ])
                        }
                    }
                }
                connection.cancel()
            }
        }
        connection.start(queue: .main)
    }

    private func tryCommonAddresses() async {
        // Security: Use HTTPS for local addresses (self-signed certs required)
        let candidates = [
            ("Kagami Local", "https://kagami.local:8001", "kagami.local", 8001),
            ("Localhost", "https://localhost:8001", "localhost", 8001),
            ("192.168.1.100", "https://192.168.1.100:8001", "192.168.1.100", 8001),
        ]

        await withTaskGroup(of: OnboardingServer?.self) { group in
            for (name, url, host, port) in candidates {
                group.addTask {
                    if await self.testServerConnection(url: url) {
                        return OnboardingServer(name: name, url: url, host: host, port: port, isSecure: false)
                    }
                    return nil
                }
            }

            for await result in group {
                if let server = result {
                    await MainActor.run {
                        if !discoveredServers.contains(server) {
                            discoveredServers.append(server)
                        }
                    }
                }
            }
        }
    }

    private func testServerConnection(url: String) async -> Bool {
        guard let testURL = URL(string: "\(url)/health") else { return false }

        var request = URLRequest(url: testURL)
        request.timeoutInterval = 3

        do {
            let (_, response) = try await URLSession.shared.data(for: request)
            return (response as? HTTPURLResponse)?.statusCode == 200
        } catch {
            return false
        }
    }

    func connectToServer() async {
        isConnecting = true
        connectionError = nil
        KagamiAnalytics.shared.track(.serverConnectionAttempted, properties: [
            "server_url": selectedServer?.url ?? serverURL
        ])

        let urlToTest = selectedServer?.url ?? serverURL

        if await testServerConnection(url: urlToTest) {
            serverURL = urlToTest
            isServerConnected = true
            saveState()
            UINotificationFeedbackGenerator().notificationOccurred(.success)
            KagamiAnalytics.shared.track(.serverConnectionSucceeded, properties: [
                "server_url": urlToTest
            ])
        } else {
            connectionError = "Could not connect to server"
            UINotificationFeedbackGenerator().notificationOccurred(.error)
            KagamiAnalytics.shared.track(.serverConnectionFailed, properties: [
                "server_url": urlToTest,
                "error": "Connection failed"
            ])
        }

        isConnecting = false
    }

    func startDemoMode() {
        isDemoMode = true
        isServerConnected = true
        UserDefaults.standard.set(true, forKey: kIsDemoMode)
        saveState()
        KagamiAnalytics.shared.track(.demoModeActivated)
    }

    // MARK: - Integration Connection

    func testIntegration() async {
        guard let integration = selectedIntegration else { return }

        isTestingIntegration = true
        integrationError = nil
        KagamiAnalytics.shared.track(.integrationTestStarted, properties: [
            "integration_type": integration.rawValue
        ])

        // Build credentials based on integration type
        let body: [String: Any] = [
            "integration_type": integration.rawValue,
            "credentials": buildCredentials(for: integration)
        ]

        guard let url = URL(string: "\(serverURL)/api/user/smart-home/test") else {
            integrationError = "Invalid server URL"
            isTestingIntegration = false
            return
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)

        // Add auth token if available
        if let token = KagamiKeychain.getToken() {
            request.addValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        do {
            let (data, response) = try await URLSession.shared.data(for: request)

            if let httpResponse = response as? HTTPURLResponse,
               httpResponse.statusCode == 200,
               let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let success = json["success"] as? Bool, success {
                integrationConnected = true
                UINotificationFeedbackGenerator().notificationOccurred(.success)
                KagamiAnalytics.shared.track(.integrationTestSucceeded, properties: [
                    "integration_type": integration.rawValue
                ])
            } else {
                let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
                integrationError = json?["message"] as? String ?? "Connection test failed"
                UINotificationFeedbackGenerator().notificationOccurred(.error)
                KagamiAnalytics.shared.track(.integrationTestFailed, properties: [
                    "integration_type": integration.rawValue,
                    "error": integrationError ?? "unknown"
                ])
            }
        } catch {
            integrationError = error.localizedDescription
            UINotificationFeedbackGenerator().notificationOccurred(.error)
            KagamiAnalytics.shared.trackError("integration_test_error", error: error, properties: [
                "integration_type": integration.rawValue
            ])
        }

        isTestingIntegration = false
    }

    func connectIntegration() async {
        guard let integration = selectedIntegration else { return }

        isTestingIntegration = true
        integrationError = nil

        let body: [String: Any] = [
            "integration_type": integration.rawValue,
            "credentials": buildCredentials(for: integration),
            "name": integration.displayName,
            "is_primary": true
        ]

        guard let url = URL(string: "\(serverURL)/api/user/smart-home/connect") else {
            integrationError = "Invalid server URL"
            isTestingIntegration = false
            return
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)

        if let token = KagamiKeychain.getToken() {
            request.addValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        do {
            let (data, response) = try await URLSession.shared.data(for: request)

            if let httpResponse = response as? HTTPURLResponse,
               httpResponse.statusCode == 200,
               let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let success = json["success"] as? Bool, success {
                integrationConnected = true
                KagamiAnalytics.shared.track(.integrationConnected, properties: [
                    "integration_type": integration.rawValue
                ])

                // Load discovered rooms
                if let roomCount = json["discovered_rooms"] as? Int, roomCount > 0 {
                    await loadRooms()
                }

                saveState()
                UINotificationFeedbackGenerator().notificationOccurred(.success)
            } else {
                let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
                integrationError = json?["message"] as? String ?? "Connection failed"
            }
        } catch {
            integrationError = error.localizedDescription
            KagamiAnalytics.shared.trackError("integration_connect_error", error: error, properties: [
                "integration_type": integration.rawValue
            ])
        }

        isTestingIntegration = false
    }

    func buildCredentials(for integration: SmartHomeIntegration) -> [String: Any] {
        var credentials: [String: Any] = [:]

        switch integration {
        case .control4:
            credentials["control4_host"] = control4Host
            if let port = Int(control4Port) {
                credentials["control4_port"] = port
            }
            if !control4ApiKey.isEmpty {
                credentials["control4_api_key"] = control4ApiKey
            }

        case .lutron:
            credentials["lutron_host"] = lutronHost
            if !lutronPassword.isEmpty {
                credentials["lutron_password"] = lutronPassword
            }

        case .smartthings:
            credentials["smartthings_token"] = smartthingsToken

        case .homeAssistant:
            credentials["home_assistant_url"] = homeAssistantURL
            credentials["home_assistant_token"] = homeAssistantToken

        case .hubitat:
            credentials["hubitat_host"] = hubitatHost
            credentials["hubitat_access_token"] = hubitatToken

        default:
            break
        }

        return credentials
    }

    // MARK: - Room Loading

    func loadRooms() async {
        isLoadingRooms = true

        guard let url = URL(string: "\(serverURL)/api/user/smart-home/rooms") else {
            isLoadingRooms = false
            return
        }

        var request = URLRequest(url: url)
        if let token = KagamiKeychain.getToken() {
            request.addValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        do {
            let (data, response) = try await URLSession.shared.data(for: request)

            if let httpResponse = response as? HTTPURLResponse,
               httpResponse.statusCode == 200,
               let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let roomsData = json["rooms"] as? [[String: Any]] {

                discoveredRooms = roomsData.map { room in
                    OnboardingRoom(
                        id: room["id"] as? String ?? UUID().uuidString,
                        name: room["name"] as? String ?? "Unknown",
                        floor: room["floor"] as? String,
                        isEnabled: true,
                        hasLights: room["has_lights"] as? Bool ?? false,
                        hasShades: room["has_shades"] as? Bool ?? false,
                        hasClimate: room["has_climate"] as? Bool ?? false,
                        hasAudio: room["has_audio"] as? Bool ?? false
                    )
                }
            }
        } catch {
            // Log error for debugging - rooms are optional but we want to track failures
            KagamiAnalytics.shared.trackError(
                "room_loading_failed",
                error: error,
                properties: ["context": "onboarding_state_manager"]
            )
            #if DEBUG
            print("[Onboarding] Room loading failed: \(error.localizedDescription)")
            #endif
        }

        isLoadingRooms = false

        // If demo mode, provide demo rooms
        if isDemoMode && discoveredRooms.isEmpty {
            discoveredRooms = DemoDataProvider.rooms.map { room in
                OnboardingRoom(
                    id: room.id,
                    name: room.name,
                    floor: room.floor,
                    isEnabled: true,
                    hasLights: !room.lights.isEmpty,
                    hasShades: !room.shades.isEmpty,
                    hasClimate: room.hvac != nil,
                    hasAudio: room.audioZone != nil
                )
            }
        }
    }

    // MARK: - Permissions

    func checkInitialPermissions() {
        // Notifications
        UNUserNotificationCenter.current().getNotificationSettings { settings in
            Task { @MainActor in
                if let index = self.permissions.firstIndex(where: { $0.id == "notifications" }) {
                    switch settings.authorizationStatus {
                    case .authorized: self.permissions[index].status = .authorized
                    case .denied: self.permissions[index].status = .denied
                    case .notDetermined: self.permissions[index].status = .notDetermined
                    default: self.permissions[index].status = .restricted
                    }
                }
            }
        }

        // Location
        Task { @MainActor in
            let status = CLLocationManager.authorizationStatus()
            if let index = permissions.firstIndex(where: { $0.id == "location" }) {
                switch status {
                case .authorizedAlways, .authorizedWhenInUse: permissions[index].status = .authorized
                case .denied: permissions[index].status = .denied
                case .notDetermined: permissions[index].status = .notDetermined
                case .restricted: permissions[index].status = .restricted
                @unknown default: break
                }
            }
        }

        // Health
        if HKHealthStore.isHealthDataAvailable() {
            let healthStore = HKHealthStore()
            let stepType = HKObjectType.quantityType(forIdentifier: .stepCount)!

            Task { @MainActor in
                let status = healthStore.authorizationStatus(for: stepType)
                if let index = permissions.firstIndex(where: { $0.id == "health" }) {
                    switch status {
                    case .sharingAuthorized: permissions[index].status = .authorized
                    case .sharingDenied: permissions[index].status = .denied
                    case .notDetermined: permissions[index].status = .notDetermined
                    @unknown default: break
                    }
                }
            }
        }
    }

    func requestPermission(_ permissionId: String) async {
        switch permissionId {
        case "notifications":
            await requestNotificationPermission()
        case "location":
            await requestLocationPermission()
        case "health":
            await requestHealthPermission()
        default:
            break
        }

        checkInitialPermissions()
    }

    private func requestNotificationPermission() async {
        do {
            let granted = try await UNUserNotificationCenter.current().requestAuthorization(
                options: [.alert, .sound, .badge]
            )
            if let index = permissions.firstIndex(where: { $0.id == "notifications" }) {
                permissions[index].status = granted ? .authorized : .denied
            }
        } catch {
            KagamiAnalytics.shared.trackError("notification_permission_error", error: error)
        }
    }

    private func requestLocationPermission() async {
        if locationManager == nil {
            locationManager = CLLocationManager()
        }
        locationManager?.requestWhenInUseAuthorization()

        // Wait a moment for the permission dialog
        try? await Task.sleep(nanoseconds: 500_000_000)
    }

    private func requestHealthPermission() async {
        guard HKHealthStore.isHealthDataAvailable() else { return }

        let healthStore = HKHealthStore()
        let types: Set<HKObjectType> = [
            HKObjectType.quantityType(forIdentifier: .stepCount)!,
            HKObjectType.quantityType(forIdentifier: .heartRate)!,
            HKObjectType.categoryType(forIdentifier: .sleepAnalysis)!,
        ]

        do {
            try await healthStore.requestAuthorization(toShare: [], read: types)
        } catch {
            KagamiAnalytics.shared.trackError("health_permission_error", error: error)
        }
    }

    func requestAllPermissions() async {
        for permission in permissions {
            await requestPermission(permission.id)
        }
    }
}

/*
 * Mirror
 * h(x) >= 0. Always.
 */
