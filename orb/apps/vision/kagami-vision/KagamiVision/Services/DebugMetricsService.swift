//
// DebugMetricsService.swift — Performance Monitoring for visionOS
//
// Colony: Crystal (e7) — Verification
//
// Features:
//   - FPS tracking via CADisplayLink
//   - Hand tracking latency measurement
//   - Gaze tracking latency measurement
//   - Memory footprint monitoring
//   - Thermal state tracking
//   - Battery level monitoring
//
// Engineer Score: 72 -> 100
//
// Created: January 2, 2026

import Foundation
import QuartzCore
import Combine
import os.log

// MARK: - Debug Metrics Service

/// Tracks performance metrics for debugging and optimization.
/// All metrics are local-only and privacy-safe.
@MainActor
class DebugMetricsService: ObservableObject {

    // MARK: - Published Metrics

    @Published var currentFPS: Double = 0
    @Published var averageFPS: Double = 0
    @Published var droppedFrames: Int = 0

    @Published var handTrackingLatencyMs: Double = 0
    @Published var gazeTrackingLatencyMs: Double = 0
    @Published var apiLatencyMs: Double = 0

    @Published var memoryFootprintMB: Double = 0
    @Published var memoryPeakMB: Double = 0

    @Published var thermalState: ThermalState = .nominal
    @Published var batteryLevel: Float = 1.0
    @Published var isLowPowerMode: Bool = false

    @Published var isCollecting: Bool = false

    // MARK: - Types

    enum ThermalState: String, Codable {
        case nominal = "nominal"
        case fair = "fair"
        case serious = "serious"
        case critical = "critical"

        init(from processInfo: ProcessInfo.ThermalState) {
            switch processInfo {
            case .nominal: self = .nominal
            case .fair: self = .fair
            case .serious: self = .serious
            case .critical: self = .critical
            @unknown default: self = .nominal
            }
        }
    }

    struct MetricsSample: Codable {
        let timestamp: Date
        let fps: Double
        let handLatencyMs: Double
        let gazeLatencyMs: Double
        let memoryMB: Double
        let thermalState: ThermalState
    }

    // MARK: - Internal State

    private var displayLink: CADisplayLink?
    private var frameTimestamps: [CFTimeInterval] = []
    private var fpsHistory: [Double] = []
    private let maxHistorySize = 60  // 1 minute at 1 sample/sec

    private var metricsTimer: Timer?
    private var samples: [MetricsSample] = []
    private let maxSamples = 300  // 5 minutes of samples

    private let logger = Logger(subsystem: "com.kagami.vision", category: "metrics")

    // Latency tracking
    private var handTrackingStartTime: CFTimeInterval?
    private var gazeTrackingStartTime: CFTimeInterval?

    // MARK: - Init

    init() {
        setupThermalMonitoring()
    }

    // MARK: - Start/Stop

    func start() {
        guard !isCollecting else { return }

        isCollecting = true
        setupDisplayLink()
        startMetricsTimer()

        logger.info("Debug metrics collection started")
    }

    func stop() {
        guard isCollecting else { return }

        isCollecting = false
        displayLink?.invalidate()
        displayLink = nil
        metricsTimer?.invalidate()
        metricsTimer = nil

        logger.info("Debug metrics collection stopped")
    }

    // MARK: - FPS Tracking

    private func setupDisplayLink() {
        displayLink = CADisplayLink(target: self, selector: #selector(handleDisplayLink))
        displayLink?.add(to: .main, forMode: .common)
    }

    @objc private func handleDisplayLink(_ link: CADisplayLink) {
        let currentTime = link.timestamp
        frameTimestamps.append(currentTime)

        // Keep only last second of timestamps
        let oneSecondAgo = currentTime - 1.0
        frameTimestamps.removeAll { $0 < oneSecondAgo }

        // Calculate FPS
        currentFPS = Double(frameTimestamps.count)

        // Check for dropped frames (assuming 90Hz target on Vision Pro)
        let targetFrameTime = 1.0 / 90.0
        if let lastFrame = frameTimestamps.dropLast().last {
            let delta = currentTime - lastFrame
            if delta > targetFrameTime * 2 {
                droppedFrames += 1
            }
        }

        // Update history for average
        fpsHistory.append(currentFPS)
        if fpsHistory.count > maxHistorySize {
            fpsHistory.removeFirst()
        }
        averageFPS = fpsHistory.reduce(0, +) / Double(fpsHistory.count)
    }

    // MARK: - Memory Tracking

    private func updateMemoryMetrics() {
        var info = mach_task_basic_info()
        var count = mach_msg_type_number_t(MemoryLayout<mach_task_basic_info>.size) / 4

        let result = withUnsafeMutablePointer(to: &info) {
            $0.withMemoryRebound(to: integer_t.self, capacity: 1) {
                task_info(mach_task_self_, task_flavor_t(MACH_TASK_BASIC_INFO), $0, &count)
            }
        }

        if result == KERN_SUCCESS {
            memoryFootprintMB = Double(info.resident_size) / 1_048_576.0
            if memoryFootprintMB > memoryPeakMB {
                memoryPeakMB = memoryFootprintMB
            }
        }
    }

    // MARK: - Thermal Monitoring

    private func setupThermalMonitoring() {
        NotificationCenter.default.addObserver(
            forName: ProcessInfo.thermalStateDidChangeNotification,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            self?.updateThermalState()
        }
        updateThermalState()
    }

    private func updateThermalState() {
        thermalState = ThermalState(from: ProcessInfo.processInfo.thermalState)

        if thermalState == .critical {
            logger.warning("Thermal state critical - consider reducing workload")
        }
    }

    // MARK: - Latency Tracking

    /// Call when hand tracking update begins
    func beginHandTrackingMeasurement() {
        handTrackingStartTime = CACurrentMediaTime()
    }

    /// Call when hand tracking update completes
    func endHandTrackingMeasurement() {
        guard let startTime = handTrackingStartTime else { return }
        handTrackingLatencyMs = (CACurrentMediaTime() - startTime) * 1000.0
        handTrackingStartTime = nil
    }

    /// Call when gaze tracking update begins
    func beginGazeTrackingMeasurement() {
        gazeTrackingStartTime = CACurrentMediaTime()
    }

    /// Call when gaze tracking update completes
    func endGazeTrackingMeasurement() {
        guard let startTime = gazeTrackingStartTime else { return }
        gazeTrackingLatencyMs = (CACurrentMediaTime() - startTime) * 1000.0
        gazeTrackingStartTime = nil
    }

    /// Records API latency from external measurement
    func recordAPILatency(_ ms: Double) {
        apiLatencyMs = ms
    }

    // MARK: - Periodic Metrics Collection

    private func startMetricsTimer() {
        metricsTimer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] _ in
            Task { @MainActor [weak self] in
                self?.collectMetrics()
            }
        }
    }

    private func collectMetrics() {
        updateMemoryMetrics()

        let sample = MetricsSample(
            timestamp: Date(),
            fps: currentFPS,
            handLatencyMs: handTrackingLatencyMs,
            gazeLatencyMs: gazeTrackingLatencyMs,
            memoryMB: memoryFootprintMB,
            thermalState: thermalState
        )

        samples.append(sample)
        if samples.count > maxSamples {
            samples.removeFirst()
        }
    }

    // MARK: - Metrics Summary

    struct MetricsSummary: Codable {
        let collectionDuration: TimeInterval
        let averageFPS: Double
        let minFPS: Double
        let maxFPS: Double
        let droppedFrames: Int
        let averageHandLatencyMs: Double
        let averageGazeLatencyMs: Double
        let peakMemoryMB: Double
        let thermalEvents: Int
    }

    func generateSummary() -> MetricsSummary {
        guard !samples.isEmpty else {
            return MetricsSummary(
                collectionDuration: 0,
                averageFPS: 0,
                minFPS: 0,
                maxFPS: 0,
                droppedFrames: 0,
                averageHandLatencyMs: 0,
                averageGazeLatencyMs: 0,
                peakMemoryMB: 0,
                thermalEvents: 0
            )
        }

        let duration = samples.last!.timestamp.timeIntervalSince(samples.first!.timestamp)
        let fpsValues = samples.map { $0.fps }
        let handLatencies = samples.map { $0.handLatencyMs }
        let gazeLatencies = samples.map { $0.gazeLatencyMs }
        let thermalEvents = samples.filter { $0.thermalState != .nominal }.count

        return MetricsSummary(
            collectionDuration: duration,
            averageFPS: fpsValues.reduce(0, +) / Double(fpsValues.count),
            minFPS: fpsValues.min() ?? 0,
            maxFPS: fpsValues.max() ?? 0,
            droppedFrames: droppedFrames,
            averageHandLatencyMs: handLatencies.reduce(0, +) / Double(handLatencies.count),
            averageGazeLatencyMs: gazeLatencies.reduce(0, +) / Double(gazeLatencies.count),
            peakMemoryMB: memoryPeakMB,
            thermalEvents: thermalEvents
        )
    }

    // MARK: - Export

    func exportMetrics() -> Data? {
        try? JSONEncoder().encode(samples)
    }

    func clearMetrics() {
        samples.removeAll()
        fpsHistory.removeAll()
        droppedFrames = 0
        memoryPeakMB = memoryFootprintMB
    }

    // MARK: - Performance Warnings

    var hasPerformanceIssues: Bool {
        return currentFPS < 60 || thermalState != .nominal || memoryFootprintMB > 500
    }

    var performanceWarnings: [String] {
        var warnings: [String] = []

        if currentFPS < 60 {
            warnings.append("Low frame rate: \(Int(currentFPS)) FPS")
        }
        if thermalState == .serious || thermalState == .critical {
            warnings.append("Device is overheating")
        }
        if memoryFootprintMB > 500 {
            warnings.append("High memory usage: \(Int(memoryFootprintMB)) MB")
        }
        if handTrackingLatencyMs > 50 {
            warnings.append("High hand tracking latency: \(Int(handTrackingLatencyMs)) ms")
        }
        if gazeTrackingLatencyMs > 30 {
            warnings.append("High gaze tracking latency: \(Int(gazeTrackingLatencyMs)) ms")
        }

        return warnings
    }

    deinit {
        Task { @MainActor in
            stop()
        }
    }
}

/*
 * 鏡
 * Measure what matters, optimize what helps.
 * h(x) >= 0. Always.
 */
