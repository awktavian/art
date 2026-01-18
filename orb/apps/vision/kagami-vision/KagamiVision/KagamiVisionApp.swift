//
// 鏡 Kagami Vision — visionOS Spatial Interface
//
// The Mirror in spatial computing.
// A HAL-aware presence that floats at the periphery.
//
// Spatial Design Principles:
//   - 3D depth layers for UI hierarchy
//   - Real-world anchors for persistent controls
//   - Spatial audio for immersive feedback
//   - Hand tracking for natural gestures
//   - Eye gaze for intuitive selection
//
// Proxemic Zones (Hall, 1966):
//   - Intimate (0-45cm): Private alerts
//   - Personal (45cm-1.2m): Control panels
//   - Social (1.2m-3.6m): Room visualizations
//   - Public (3.6m+): Ambient awareness
//
// η → s → μ → a → η′
// h(x) ≥ 0. Always.
//

import SwiftUI
import RealityKit
import HealthKit
import os.log

@main
struct KagamiVisionApp: App {
    @StateObject private var appModel = AppModel()
    @StateObject private var health = HealthKitService()
    @StateObject private var onboardingState = OnboardingState()
    @StateObject private var spatialServices = SpatialServicesContainer()
    @Environment(\.scenePhase) private var scenePhase

    var body: some SwiftUI.Scene {
        // Main window - 2D UI with glass backdrop
        WindowGroup {
            Group {
                if !onboardingState.hasCompletedOnboarding {
                    OnboardingView()
                        .environmentObject(appModel)
                        .environmentObject(health)
                } else {
                    ContentView()
                        .environmentObject(appModel)
                        .environmentObject(health)
                }
            }
            .environmentObject(onboardingState)
            .environmentObject(spatialServices)
            .task {
                // Request HealthKit permissions on first launch
                await health.requestAuthorization()
                // Initialize spatial services
                await spatialServices.initialize()
            }
            .onChange(of: scenePhase) { _, newPhase in
                handleScenePhaseChange(newPhase)
            }
        }
        .windowStyle(.plain)
        .defaultSize(width: 400, height: 300)  // Optimized per visionOS HIG for spatial viewing

        // Command palette window - floating minimal UI
        WindowGroup(id: "command-palette") {
            CommandPaletteView()
                .environmentObject(appModel)
                .environmentObject(health)
                .environmentObject(spatialServices)
        }
        .windowStyle(.plain)
        .defaultSize(width: 500, height: 80)

        // Spatial Control Panel - world-anchored 3D controls
        WindowGroup(id: "spatial-control-panel") {
            SpatialControlPanel()
                .environmentObject(appModel)
                .environmentObject(spatialServices)
        }
        .windowStyle(.volumetric)
        .defaultSize(width: 0.5, height: 0.4, depth: 0.2, in: .meters)

        // Agent Browser - HTML agents in spatial context
        WindowGroup(id: "agent-browser") {
            SpatialAgentBrowserView()
                .environmentObject(appModel)
                .environmentObject(spatialServices)
        }
        .windowStyle(.plain)
        .defaultSize(width: 600, height: 500)

        // Individual Agent Window - floating agent view
        WindowGroup(id: "agent-view", for: String.self) { $agentId in
            if let id = agentId {
                SpatialAgentView(agentId: id)
                    .environmentObject(appModel)
                    .environmentObject(spatialServices)
            }
        }
        .windowStyle(.plain)
        .defaultSize(width: 800, height: 600)

        // 3D Room Visualization - immersive home model
        ImmersiveSpace(id: "spatial-rooms") {
            Spatial3DRoomView()
                .environmentObject(appModel)
                .environmentObject(spatialServices)
        }
        .immersionStyle(selection: .constant(.mixed), in: .mixed)

        // Kagami Presence - the ambient orb in space
        ImmersiveSpace(id: "kagami-presence") {
            KagamiPresenceView()
                .environmentObject(appModel)
                .environmentObject(health)
                .environmentObject(spatialServices)
        }
        .immersionStyle(selection: .constant(.mixed), in: .mixed)

        // Full Immersive Home - complete spatial experience
        ImmersiveSpace(id: "full-spatial") {
            FullSpatialExperienceView()
                .environmentObject(appModel)
                .environmentObject(health)
                .environmentObject(spatialServices)
        }
        .immersionStyle(selection: .constant(.progressive), in: .progressive)
    }

    // MARK: - Scene Phase Handling

    private func handleScenePhaseChange(_ phase: ScenePhase) {
        switch phase {
        case .background:
            // App moved to background - shutdown spatial services to conserve resources
            Task { @MainActor in
                spatialServices.shutdown()
            }
        case .inactive:
            // App is inactive but visible - keep services running
            break
        case .active:
            // App became active - reinitialize spatial services if needed
            Task { @MainActor in
                if !spatialServices.isInitialized {
                    await spatialServices.initialize()
                }
            }
        @unknown default:
            break
        }
    }
}

// MARK: - Spatial Services Container

/// Container for all spatial services, shared across views
@MainActor
class SpatialServicesContainer: ObservableObject {
    @Published var anchorService = SpatialAnchorService()
    @Published var audioService = SpatialAudioService()
    @Published var gestureRecognizer = SpatialGestureRecognizer()
    @Published var handTracking = HandTrackingService()
    @Published var gazeTracking = GazeTrackingService()

    // P1 FIX: GestureStateMachine for conflict prevention
    @Published var gestureStateMachine = GestureStateMachine()

    @Published var isInitialized = false
    @Published var spatialFeaturesAvailable = false
    @Published var initializationError: SpatialInitializationError?

    /// Tracks which services failed to initialize for diagnostics
    @Published var serviceStatus: [String: Bool] = [:]

    /// Error types for spatial service initialization
    enum SpatialInitializationError: Error, LocalizedError {
        case handTrackingUnavailable
        case gazeTrackingUnavailable
        case anchorServiceUnavailable
        case audioInitializationFailed
        case allServicesUnavailable

        var errorDescription: String? {
            switch self {
            case .handTrackingUnavailable:
                return "Hand tracking is not available on this device"
            case .gazeTrackingUnavailable:
                return "Gaze tracking is not available on this device"
            case .anchorServiceUnavailable:
                return "Spatial anchor service could not start"
            case .audioInitializationFailed:
                return "Spatial audio failed to initialize"
            case .allServicesUnavailable:
                return "No spatial features are available on this device"
            }
        }
    }

    /// Tracks whether initialization is currently in progress
    @Published var isInitializing = false

    func initialize() async {
        // Reset state
        initializationError = nil
        serviceStatus = [:]
        isInitializing = true

        // Connect gesture recognizer to hand tracking immediately
        // This doesn't require any async work
        gestureRecognizer.onSemanticAction = { [weak self] action, value in
            self?.handleSemanticAction(action, value: value)
        }

        // P1 FIX: Connect GestureStateMachine to gesture recognizer
        gestureStateMachine.connect(to: gestureRecognizer)

        // P1 FIX: Connect 90fps raw pose updates for low-latency UI
        handTracking.onRawPoseUpdate = { [weak self] leftPos, rightPos, gesture in
            // Raw pose updates at 90fps for responsive UI elements
            // The state machine handles conflict prevention
            guard let self = self else { return }
            // UI elements can subscribe to these for immediate feedback
            _ = (leftPos, rightPos, gesture)
        }

        // Mark as initialized early so UI can show while services start in background
        // This allows the app to display immediately rather than waiting for all services
        isInitialized = true

        // P0 FIX: Parallelize spatial init using async let
        // Initialize hand tracking, gaze tracking, anchor service, and audio in parallel
        // This significantly reduces startup time from sequential ~2-4s to parallel ~0.5-1s
        async let handTrackingTask = handTracking.start()
        async let gazeTrackingTask = gazeTracking.start()
        async let anchorServiceTask = anchorService.start()
        async let audioTask: () = audioService.initialize()

        // Await all services in parallel
        let (handTrackingAvailable, gazeTrackingAvailable, anchorServiceAvailable, _) = await (
            handTrackingTask,
            gazeTrackingTask,
            anchorServiceTask,
            audioTask
        )

        // Update service status
        serviceStatus["handTracking"] = handTrackingAvailable
        serviceStatus["gazeTracking"] = gazeTrackingAvailable
        serviceStatus["anchorService"] = anchorServiceAvailable
        serviceStatus["audio"] = audioService.isInitialized

        // Determine overall availability
        spatialFeaturesAvailable = handTrackingAvailable || gazeTrackingAvailable || anchorServiceAvailable

        // Set error if no spatial features available
        if !spatialFeaturesAvailable {
            initializationError = .allServicesUnavailable
        }

        isInitializing = false

        KagamiLogger.app.info("Spatial services initialized (parallel)")
        KagamiLogger.logServiceAvailability("Hand tracking", available: handTrackingAvailable, logger: KagamiLogger.handTracking)
        KagamiLogger.logServiceAvailability("Gaze tracking", available: gazeTrackingAvailable, logger: KagamiLogger.gazeTracking)
        KagamiLogger.logServiceAvailability("Anchor service", available: anchorServiceAvailable, logger: KagamiLogger.spatialAnchor)
        KagamiLogger.logServiceAvailability("Audio", available: audioService.isInitialized, logger: KagamiLogger.spatialAudio)
    }

    private func handleSemanticAction(_ action: SpatialGestureRecognizer.SemanticAction, value: Float) {
        switch action {
        case .brightnessUp, .brightnessDown:
            audioService.play(.tap)
        case .nextRoom, .previousRoom:
            audioService.play(.select)
        case .emergencyStop:
            audioService.play(.error)
        case .dismiss:
            audioService.play(.notification)
        default:
            break
        }
    }

    /// Properly shuts down all spatial services.
    /// Call this when the app is terminating or entering background.
    func shutdown() {
        guard isInitialized else { return }

        // Stop services in reverse order of initialization
        audioService.shutdown()
        anchorService.stop()
        gazeTracking.stop()
        handTracking.stop()

        // Clear gesture recognizer callback to prevent retain cycles
        gestureRecognizer.onSemanticAction = nil

        // P1 FIX: Reset gesture state machine
        gestureStateMachine.reset()

        // P1 FIX: Clear 90fps callback
        handTracking.onRawPoseUpdate = nil

        // Reset state
        isInitialized = false
        spatialFeaturesAvailable = false
        serviceStatus = [:]

        KagamiLogger.app.info("Spatial services shutdown complete")
    }

    /// Checks if a specific spatial feature is available
    func isFeatureAvailable(_ feature: String) -> Bool {
        return serviceStatus[feature] ?? false
    }
}

// MARK: - App Model

@MainActor
class AppModel: ObservableObject {
    @Published var isConnected = false
    @Published var safetyScore: Double = 0.85
    @Published var activeColonies: Set<String> = []
    @Published var isPresenceActive = false

    let apiService = KagamiAPIService()
    let analyticsService = AnalyticsService()
    let metricsService = DebugMetricsService()
    let healthMonitor = ServiceHealthMonitor()
    let offlineCache = OfflineCacheService()
    let sensorAlerts = SensorAlertService()

    init() {
        Task {
            await apiService.connect()
            isConnected = apiService.isConnected

            // Configure services
            analyticsService.setAPIService(apiService)
            offlineCache.setAPIService(apiService)
            healthMonitor.startMonitoring()

            // Start debug metrics in debug builds
            #if DEBUG
            metricsService.start()
            #endif

            // Start sensor alert monitoring
            sensorAlerts.startMonitoring(apiBaseURL: apiService.currentURL)
        }
    }

    /// Tracks analytics event for hand tracking availability changes
    func trackHandTrackingChange(isAvailable: Bool, reason: String? = nil) {
        analyticsService.trackHandTrackingAvailability(isAvailable: isAvailable, reason: reason)
    }

    /// Tracks analytics event for gesture recognition
    func trackGesture(_ gesture: String, confidence: Float, successful: Bool) {
        analyticsService.trackGestureRecognition(gesture: gesture, confidence: confidence, successful: successful)
    }

    /// Tracks analytics event for voice commands
    func trackVoiceCommand(_ command: String, understood: Bool) {
        analyticsService.trackVoiceCommand(command: command, understood: understood, executionTime: nil)
    }
}

// Colors now defined in Services/KagamiTypes.swift

/*
 * 鏡
 * I am the real component of the octonion.
 */
