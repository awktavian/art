//
// ThermalManager.swift — Thermal Throttling Response
//
// Colony: Flow (e3) — Processing
//
// P2 FIX: Thermal management for sustained performance
//
// Features:
//   - ProcessInfo thermal state monitoring
//   - Automatic FPS reduction on thermal pressure
//   - Task offloading to background queues
//   - Quality degradation with graceful fallback
//   - User notification of thermal state
//   - Recovery when device cools down
//
// Architecture:
//   ProcessInfo.thermalState → ThermalManager → QualityProfile
//                                            → FPS Target
//                                            → Background Tasks
//                                            → User Notification
//
// visionOS Thermal States:
//   - nominal: Full quality, 90fps target
//   - fair: Slight reduction, 72fps target
//   - serious: Aggressive reduction, 60fps target
//   - critical: Minimal mode, pause non-essential
//
// Created: January 2, 2026
// 鏡

import Foundation
import Combine
import os.log

// MARK: - Quality Profile

/// Rendering and processing quality levels
enum QualityProfile: String, CaseIterable {
    case ultra = "ultra"      // Maximum quality (thermal nominal)
    case high = "high"        // High quality (thermal fair)
    case medium = "medium"    // Balanced (thermal serious)
    case low = "low"          // Performance mode (thermal critical)
    case minimal = "minimal"  // Survival mode (extreme thermal)

    var targetFPS: Int {
        switch self {
        case .ultra: return 90
        case .high: return 72
        case .medium: return 60
        case .low: return 45
        case .minimal: return 30
        }
    }

    var maxEntityCount: Int {
        switch self {
        case .ultra: return 500
        case .high: return 300
        case .medium: return 150
        case .low: return 75
        case .minimal: return 30
        }
    }

    var particleSystemsEnabled: Bool {
        switch self {
        case .ultra, .high: return true
        case .medium, .low, .minimal: return false
        }
    }

    var shadowQuality: ShadowQuality {
        switch self {
        case .ultra: return .high
        case .high: return .medium
        case .medium: return .low
        case .low, .minimal: return .none
        }
    }

    var reflectionProbesEnabled: Bool {
        switch self {
        case .ultra, .high: return true
        default: return false
        }
    }

    var handTrackingUpdateRate: Double {
        switch self {
        case .ultra: return 90
        case .high: return 72
        case .medium: return 60
        case .low: return 30
        case .minimal: return 15
        }
    }

    var spatialAudioEnabled: Bool {
        switch self {
        case .minimal: return false
        default: return true
        }
    }

    var animationQuality: AnimationQuality {
        switch self {
        case .ultra, .high: return .full
        case .medium: return .reduced
        case .low, .minimal: return .minimal
        }
    }

    enum ShadowQuality {
        case high, medium, low, none
    }

    enum AnimationQuality {
        case full, reduced, minimal
    }
}

// MARK: - Thermal State Extension

extension ProcessInfo.ThermalState {
    var description: String {
        switch self {
        case .nominal: return "Nominal"
        case .fair: return "Fair"
        case .serious: return "Serious"
        case .critical: return "Critical"
        @unknown default: return "Unknown"
        }
    }

    var recommendedProfile: QualityProfile {
        switch self {
        case .nominal: return .ultra
        case .fair: return .high
        case .serious: return .medium
        case .critical: return .low
        @unknown default: return .medium
        }
    }

    var isThrottling: Bool {
        switch self {
        case .serious, .critical: return true
        default: return false
        }
    }
}

// MARK: - Thermal Manager

/// Manages device thermal state and adjusts app quality accordingly
@MainActor
final class ThermalManager: ObservableObject {

    // MARK: - Published State

    @Published private(set) var thermalState: ProcessInfo.ThermalState = .nominal
    @Published private(set) var currentProfile: QualityProfile = .ultra
    @Published private(set) var isThrottling = false
    @Published private(set) var throttleDuration: TimeInterval = 0
    @Published private(set) var showThermalWarning = false

    // Performance metrics
    @Published private(set) var currentFPS: Int = 90
    @Published private(set) var droppedFrameCount: Int = 0
    @Published private(set) var averageFrameTime: Double = 0

    // MARK: - Configuration

    /// Minimum time before quality can increase again (prevents oscillation)
    private let qualityIncreaseDelay: TimeInterval = 30.0

    /// User override for quality (nil = automatic)
    @Published var userQualityOverride: QualityProfile?

    // MARK: - Internal State

    private var thermalStateObserver: NSObjectProtocol?
    private var throttleStartTime: Date?
    private var lastQualityDecrease: Date?
    private var cancellables = Set<AnyCancellable>()

    // Background task management
    private var deferredTasks: [DeferredTask] = []
    private let backgroundQueue = DispatchQueue(label: "com.kagami.thermal.background", qos: .utility)

    // Frame timing
    private var frameTimeSamples: [Double] = []
    private let maxFrameSamples = 60

    // Callbacks
    var onQualityChange: ((QualityProfile, QualityProfile) -> Void)?
    var onThermalWarning: ((ProcessInfo.ThermalState) -> Void)?
    var onRecovery: (() -> Void)?

    // MARK: - Types

    struct DeferredTask: Identifiable {
        let id: UUID
        let priority: Priority
        let task: () async -> Void
        let thermalThreshold: ProcessInfo.ThermalState

        enum Priority: Int, Comparable {
            case low = 0
            case normal = 1
            case high = 2

            static func < (lhs: Priority, rhs: Priority) -> Bool {
                return lhs.rawValue < rhs.rawValue
            }
        }

        init(
            priority: Priority = .normal,
            thermalThreshold: ProcessInfo.ThermalState = .serious,
            task: @escaping () async -> Void
        ) {
            self.id = UUID()
            self.priority = priority
            self.task = task
            self.thermalThreshold = thermalThreshold
        }
    }

    // MARK: - Init

    init() {
        setupThermalMonitoring()
        updateThermalState(ProcessInfo.processInfo.thermalState)
    }

    deinit {
        if let observer = thermalStateObserver {
            NotificationCenter.default.removeObserver(observer)
        }
    }

    // MARK: - Setup

    private func setupThermalMonitoring() {
        // Subscribe to thermal state changes
        thermalStateObserver = NotificationCenter.default.addObserver(
            forName: ProcessInfo.thermalStateDidChangeNotification,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            Task { @MainActor [weak self] in
                let newState = ProcessInfo.processInfo.thermalState
                self?.handleThermalStateChange(newState)
            }
        }

        // Start monitoring timer for throttle duration
        Timer.publish(every: 1.0, on: .main, in: .common)
            .autoconnect()
            .sink { [weak self] _ in
                self?.updateThrottleDuration()
            }
            .store(in: &cancellables)
    }

    // MARK: - State Management

    private func handleThermalStateChange(_ newState: ProcessInfo.ThermalState) {
        let oldState = thermalState
        thermalState = newState

        KagamiLogger.logThermalChange(from: oldState.description, to: newState.description)

        // Handle throttle timing
        if newState.isThrottling && !oldState.isThrottling {
            throttleStartTime = Date()
            isThrottling = true
        } else if !newState.isThrottling && oldState.isThrottling {
            throttleStartTime = nil
            throttleDuration = 0
            isThrottling = false
            onRecovery?()
        }

        // Update quality profile
        updateQualityProfile()

        // Handle warnings
        if newState == .serious || newState == .critical {
            showThermalWarning = true
            onThermalWarning?(newState)
        } else {
            showThermalWarning = false
        }

        // Process deferred tasks if cooling down
        if newState.rawValue < oldState.rawValue {
            Task {
                await processDeferredTasks()
            }
        }
    }

    private func updateQualityProfile() {
        let oldProfile = currentProfile
        let targetProfile: QualityProfile

        // Use override if set, otherwise automatic
        if let override = userQualityOverride {
            targetProfile = override
        } else {
            targetProfile = thermalState.recommendedProfile
        }

        // Only decrease quality immediately, increase with delay
        if targetProfile.rawValue > oldProfile.rawValue {
            // Decreasing quality
            currentProfile = targetProfile
            lastQualityDecrease = Date()
            onQualityChange?(oldProfile, targetProfile)
        } else if targetProfile.rawValue < oldProfile.rawValue {
            // Increasing quality - check delay
            if let lastDecrease = lastQualityDecrease,
               Date().timeIntervalSince(lastDecrease) < qualityIncreaseDelay {
                // Too soon to increase
                return
            }

            // Step up one level at a time (gradual recovery)
            let profileIndex = QualityProfile.allCases.firstIndex(of: oldProfile) ?? 0
            if profileIndex > 0 {
                currentProfile = QualityProfile.allCases[profileIndex - 1]
                onQualityChange?(oldProfile, currentProfile)
            }
        }
    }

    private func updateThrottleDuration() {
        if let start = throttleStartTime {
            throttleDuration = Date().timeIntervalSince(start)
        }
    }

    // MARK: - Force Update

    /// Forces a thermal state check (useful after app becomes active)
    func forceUpdate() {
        updateThermalState(ProcessInfo.processInfo.thermalState)
    }

    private func updateThermalState(_ state: ProcessInfo.ThermalState) {
        if thermalState != state {
            handleThermalStateChange(state)
        }
    }

    // MARK: - Quality Control API

    /// Gets the target FPS for current thermal state
    var targetFPS: Int {
        return currentProfile.targetFPS
    }

    /// Gets maximum entity count for current thermal state
    var maxEntities: Int {
        return currentProfile.maxEntityCount
    }

    /// Checks if a feature should be enabled based on thermal state
    func isFeatureEnabled(_ feature: ThermalFeature) -> Bool {
        switch feature {
        case .particleSystems:
            return currentProfile.particleSystemsEnabled

        case .spatialAudio:
            return currentProfile.spatialAudioEnabled

        case .reflectionProbes:
            return currentProfile.reflectionProbesEnabled

        case .highFPSHandTracking:
            return currentProfile.handTrackingUpdateRate >= 60

        case .fullAnimations:
            return currentProfile.animationQuality == .full
        }
    }

    enum ThermalFeature {
        case particleSystems
        case spatialAudio
        case reflectionProbes
        case highFPSHandTracking
        case fullAnimations
    }

    // MARK: - Background Task Management

    /// Defers a task to run when thermal state improves
    func deferTask(
        priority: DeferredTask.Priority = .normal,
        thermalThreshold: ProcessInfo.ThermalState = .serious,
        task: @escaping () async -> Void
    ) {
        let deferredTask = DeferredTask(
            priority: priority,
            thermalThreshold: thermalThreshold,
            task: task
        )

        deferredTasks.append(deferredTask)
        deferredTasks.sort { $0.priority > $1.priority }

        // Keep bounded
        if deferredTasks.count > 50 {
            deferredTasks.removeLast(deferredTasks.count - 50)
        }
    }

    /// Runs deferred tasks if thermal state allows
    private func processDeferredTasks() async {
        let tasksToRun = deferredTasks.filter { task in
            task.thermalThreshold.rawValue >= thermalState.rawValue
        }

        deferredTasks.removeAll { task in
            tasksToRun.contains { $0.id == task.id }
        }

        for task in tasksToRun {
            await task.task()
        }
    }

    /// Offloads work to background queue when thermally constrained
    func offloadToBackground<T: Sendable>(
        work: @escaping @Sendable () -> T
    ) async -> T {
        if thermalState.isThrottling {
            return await withCheckedContinuation { continuation in
                backgroundQueue.async {
                    let result = work()
                    continuation.resume(returning: result)
                }
            }
        } else {
            return work()
        }
    }

    // MARK: - Frame Timing

    /// Records a frame time sample for performance monitoring
    func recordFrameTime(_ frameTime: Double) {
        frameTimeSamples.append(frameTime)

        if frameTimeSamples.count > maxFrameSamples {
            frameTimeSamples.removeFirst()
        }

        // Update metrics
        averageFrameTime = frameTimeSamples.reduce(0, +) / Double(frameTimeSamples.count)
        currentFPS = Int(1.0 / averageFrameTime)

        // Count dropped frames (frame time > 1.5x target)
        let targetFrameTime = 1.0 / Double(targetFPS)
        if frameTime > targetFrameTime * 1.5 {
            droppedFrameCount += 1
        }
    }

    /// Resets frame timing metrics
    func resetFrameMetrics() {
        frameTimeSamples.removeAll()
        droppedFrameCount = 0
        averageFrameTime = 0
        currentFPS = targetFPS
    }

    // MARK: - User Control

    /// Sets a user quality override (nil for automatic)
    func setQualityOverride(_ profile: QualityProfile?) {
        userQualityOverride = profile
        updateQualityProfile()
    }

    /// Clears user quality override, returns to automatic
    func clearQualityOverride() {
        userQualityOverride = nil
        updateQualityProfile()
    }
}

// MARK: - Thermal Aware View Modifier

import SwiftUI

/// View modifier that adjusts based on thermal state
struct ThermalAwareModifier: ViewModifier {
    @EnvironmentObject var thermalManager: ThermalManager

    func body(content: Content) -> some View {
        content
            .animation(thermalManager.currentProfile.animationQuality == .minimal ? nil : .default, value: thermalManager.isThrottling)
            .overlay(alignment: .top) {
                if thermalManager.showThermalWarning {
                    ThermalWarningBanner(thermalState: thermalManager.thermalState)
                        .transition(.move(edge: .top).combined(with: .opacity))
                }
            }
    }
}

/// Thermal warning banner
struct ThermalWarningBanner: View {
    let thermalState: ProcessInfo.ThermalState

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: thermalState == .critical ? "flame.fill" : "thermometer.high")
                .foregroundColor(thermalState == .critical ? .red : .orange)

            Text(thermalState == .critical ?
                 String(localized: "thermal.warning.critical") :
                 String(localized: "thermal.warning.serious"))
                .font(.caption)
                .foregroundColor(.primary)

            Spacer()

            Button(action: {}) {
                Text(String(localized: "thermal.dismiss"))
                    .font(.caption2)
            }
            .buttonStyle(.plain)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 8))
        .padding(.horizontal, 16)
        .padding(.top, 8)
    }
}

extension View {
    func thermalAware() -> some View {
        modifier(ThermalAwareModifier())
    }
}

// MARK: - Quality Profile Picker

/// Settings view for manual quality selection
struct QualityProfilePicker: View {
    @EnvironmentObject var thermalManager: ThermalManager

    var body: some View {
        Section {
            Picker(String(localized: "settings.quality.profile"), selection: $thermalManager.userQualityOverride) {
                Text(String(localized: "settings.quality.automatic"))
                    .tag(nil as QualityProfile?)

                ForEach(QualityProfile.allCases, id: \.self) { profile in
                    Text(profile.rawValue.capitalized)
                        .tag(profile as QualityProfile?)
                }
            }
        } header: {
            Text(String(localized: "settings.quality.header"))
        } footer: {
            if let override = thermalManager.userQualityOverride {
                Text(String(localized: "settings.quality.override.active \(override.rawValue)"))
            } else {
                Text(String(localized: "settings.quality.automatic.description"))
            }
        }
    }
}

// MARK: - Thermal Stats View

/// Debug view showing thermal statistics
struct ThermalStatsView: View {
    @EnvironmentObject var thermalManager: ThermalManager

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Label("Thermal: \(thermalManager.thermalState.description)", systemImage: "thermometer")
            Label("Profile: \(thermalManager.currentProfile.rawValue)", systemImage: "slider.horizontal.3")
            Label("FPS: \(thermalManager.currentFPS)/\(thermalManager.targetFPS)", systemImage: "speedometer")

            if thermalManager.isThrottling {
                Label("Throttling: \(Int(thermalManager.throttleDuration))s", systemImage: "flame")
                    .foregroundColor(.orange)
            }

            Label("Dropped: \(thermalManager.droppedFrameCount)", systemImage: "exclamationmark.triangle")
        }
        .font(.caption)
        .padding()
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 8))
    }
}

/*
 * 鏡
 * h(x) >= 0. Always.
 *
 * Heat is the enemy of computation.
 * When the device warms, we cool our ambitions.
 * Graceful degradation preserves the experience.
 * Recovery restores what was lost.
 */
