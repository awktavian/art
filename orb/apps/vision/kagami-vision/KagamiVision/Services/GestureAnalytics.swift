//
// GestureAnalytics.swift — Gesture History Analytics
//
// Colony: Crystal (e7) — Reflection
//
// P2 FIX: Comprehensive gesture history analytics
//
// Features:
//   - Export gesture history for ML training
//   - Success/failure pattern analysis
//   - User preference inference
//   - Time-based usage patterns
//   - Gesture sequence analysis
//   - Performance trend detection
//   - Data export (JSON, CSV)
//
// Architecture:
//   GestureEvents → AnalyticsCollector → PatternAnalyzer → Insights
//                                      → ExportManager → Files
//                                      → PreferenceInferrer → Recommendations
//
// Created: January 2, 2026
// 鏡

import Foundation
import Combine

// MARK: - Gesture Event

/// Detailed gesture event for analytics
struct GestureEvent: Codable, Identifiable {
    let id: UUID
    let timestamp: Date
    let gesture: String  // RecognizedGesture raw value
    let success: Bool
    let confidence: Float
    let duration: TimeInterval
    let targetDevice: String?
    let targetRoom: String?
    let handedness: String  // "left", "right", "both"
    let position: [Float]?  // [x, y, z]
    let sequence: Int  // Position in gesture sequence

    init(
        gesture: SpatialGestureRecognizer.RecognizedGesture,
        success: Bool,
        confidence: Float,
        duration: TimeInterval = 0,
        targetDevice: String? = nil,
        targetRoom: String? = nil,
        handedness: String = "right",
        position: SIMD3<Float>? = nil,
        sequence: Int = 0
    ) {
        self.id = UUID()
        self.timestamp = Date()
        self.gesture = gesture.rawValue
        self.success = success
        self.confidence = confidence
        self.duration = duration
        self.targetDevice = targetDevice
        self.targetRoom = targetRoom
        self.handedness = handedness
        self.position = position.map { [$0.x, $0.y, $0.z] }
        self.sequence = sequence
    }
}

// MARK: - Analytics Session

/// A session of gesture analytics
struct AnalyticsSession: Codable, Identifiable {
    let id: UUID
    let startTime: Date
    var endTime: Date?
    var events: [GestureEvent]
    var metadata: SessionMetadata

    struct SessionMetadata: Codable {
        var deviceModel: String = ""
        var osVersion: String = ""
        var appVersion: String = ""
        var skillLevel: String = ""
        var thermalState: String = ""
    }

    init() {
        self.id = UUID()
        self.startTime = Date()
        self.events = []
        self.metadata = SessionMetadata()
    }

    var duration: TimeInterval {
        (endTime ?? Date()).timeIntervalSince(startTime)
    }

    var successRate: Float {
        guard !events.isEmpty else { return 0 }
        let successes = events.filter { $0.success }.count
        return Float(successes) / Float(events.count)
    }

    var averageConfidence: Float {
        guard !events.isEmpty else { return 0 }
        return events.map { $0.confidence }.reduce(0, +) / Float(events.count)
    }
}

// MARK: - Pattern Analysis

/// Detected pattern in gesture usage
struct GesturePattern: Codable, Identifiable {
    let id: UUID
    let type: PatternType
    let gestures: [String]
    let frequency: Int
    let averageInterval: TimeInterval
    let contexts: [String]

    enum PatternType: String, Codable {
        case sequence      // A -> B -> C always
        case timeOfDay     // Uses gesture at specific time
        case location      // Uses gesture in specific room
        case deviceBased   // Uses gesture for specific device
        case errorRecovery // Uses gesture after failure
    }
}

// MARK: - User Preferences

/// Inferred user preferences from gesture patterns
struct InferredPreferences: Codable {
    var preferredHand: String = "unknown"  // "left", "right", "ambidextrous"
    var preferredGestures: [String] = []
    var avoidedGestures: [String] = []
    var peakUsageTimes: [Int] = []  // Hours of day
    var preferredRooms: [String] = []
    var gestureSpeed: Speed = .moderate

    enum Speed: String, Codable {
        case slow
        case moderate
        case fast
    }
}

// MARK: - Analytics Insights

/// Generated insights from analytics
struct AnalyticsInsight: Identifiable {
    let id: UUID
    let type: InsightType
    let title: String
    let description: String
    let actionable: Bool
    let recommendation: String?
    let relatedGestures: [String]

    enum InsightType {
        case performance
        case pattern
        case recommendation
        case warning
        case achievement
    }
}

// MARK: - Gesture Analytics Service

/// Main service for gesture analytics collection and analysis
@MainActor
final class GestureAnalytics: ObservableObject {

    // MARK: - Published State

    @Published private(set) var currentSession: AnalyticsSession?
    @Published private(set) var totalEvents: Int = 0
    @Published private(set) var detectedPatterns: [GesturePattern] = []
    @Published private(set) var inferredPreferences = InferredPreferences()
    @Published private(set) var latestInsights: [AnalyticsInsight] = []

    // Settings
    @Published var isCollectionEnabled = true
    @Published var collectLocationData = false
    @Published var autoExport = false

    // MARK: - Internal State

    private var allSessions: [AnalyticsSession] = []
    private var sequenceCounter = 0
    private var lastGestureTime: Date?
    private var cancellables = Set<AnyCancellable>()

    private let storageURL: URL
    private let maxEventsInMemory = 1000
    private let maxSessionAge: TimeInterval = 30 * 24 * 60 * 60  // 30 days

    // Pattern detection
    private var sequenceBuffer: [(gesture: String, timestamp: Date)] = []
    private let sequenceBufferSize = 10

    // MARK: - Init

    init() {
        // Setup storage location
        let documentsPath = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        self.storageURL = documentsPath.appendingPathComponent("GestureAnalytics", isDirectory: true)

        // Create directory if needed
        try? FileManager.default.createDirectory(at: storageURL, withIntermediateDirectories: true)

        // Load existing data
        loadStoredData()
    }

    // MARK: - Session Management

    /// Starts a new analytics session
    func startSession() {
        endCurrentSession()

        var session = AnalyticsSession()

        // Populate metadata
        #if os(visionOS)
        session.metadata.deviceModel = "Apple Vision Pro"
        #else
        session.metadata.deviceModel = "Mac"
        #endif
        session.metadata.osVersion = ProcessInfo.processInfo.operatingSystemVersionString
        session.metadata.appVersion = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "1.0"

        currentSession = session
        sequenceCounter = 0

        print("Analytics session started: \(session.id)")
    }

    /// Ends the current session
    func endCurrentSession() {
        guard var session = currentSession else { return }

        session.endTime = Date()
        allSessions.append(session)
        currentSession = nil

        // Persist session
        saveSession(session)

        // Analyze patterns after session
        Task {
            await analyzePatterns()
        }

        print("Analytics session ended: \(session.id), events: \(session.events.count)")
    }

    // MARK: - Event Recording

    /// Records a gesture event
    func recordEvent(
        gesture: SpatialGestureRecognizer.RecognizedGesture,
        success: Bool,
        confidence: Float,
        duration: TimeInterval = 0,
        targetDevice: String? = nil,
        targetRoom: String? = nil,
        handedness: String = "right",
        position: SIMD3<Float>? = nil
    ) {
        guard isCollectionEnabled, currentSession != nil else { return }

        let event = GestureEvent(
            gesture: gesture,
            success: success,
            confidence: confidence,
            duration: duration,
            targetDevice: targetDevice,
            targetRoom: collectLocationData ? targetRoom : nil,
            handedness: handedness,
            position: collectLocationData ? position : nil,
            sequence: sequenceCounter
        )

        currentSession?.events.append(event)
        sequenceCounter += 1
        totalEvents += 1

        // Update sequence buffer for pattern detection
        sequenceBuffer.append((gesture.rawValue, Date()))
        if sequenceBuffer.count > sequenceBufferSize {
            sequenceBuffer.removeFirst()
        }

        // Trim events in memory
        if let session = currentSession, session.events.count > maxEventsInMemory {
            // Save overflow to disk
            saveEventsOverflow(session.events.prefix(maxEventsInMemory / 2))
            currentSession?.events = Array(session.events.suffix(maxEventsInMemory / 2))
        }

        lastGestureTime = Date()
    }

    // MARK: - Pattern Analysis

    /// Analyzes gesture patterns from history
    func analyzePatterns() async {
        detectedPatterns.removeAll()

        // Collect all events
        let allEvents = collectAllEvents()
        guard allEvents.count >= 20 else { return }  // Need enough data

        // Detect sequence patterns
        detectSequencePatterns(allEvents)

        // Detect time-of-day patterns
        detectTimePatterns(allEvents)

        // Detect location patterns
        detectLocationPatterns(allEvents)

        // Infer preferences
        inferPreferences(from: allEvents)

        // Generate insights
        generateInsights(from: allEvents)
    }

    private func detectSequencePatterns(_ events: [GestureEvent]) {
        // Find common gesture sequences (bigrams and trigrams)
        var bigrams: [String: Int] = [:]
        var trigrams: [String: Int] = [:]

        for i in 0..<events.count {
            if i + 1 < events.count {
                let bigram = "\(events[i].gesture)->\(events[i+1].gesture)"
                bigrams[bigram, default: 0] += 1
            }

            if i + 2 < events.count {
                let trigram = "\(events[i].gesture)->\(events[i+1].gesture)->\(events[i+2].gesture)"
                trigrams[trigram, default: 0] += 1
            }
        }

        // Extract significant patterns
        for (sequence, count) in bigrams where count >= 5 {
            let gestures = sequence.split(separator: ">").map { String($0).trimmingCharacters(in: ["-"]) }
            let pattern = GesturePattern(
                id: UUID(),
                type: .sequence,
                gestures: gestures,
                frequency: count,
                averageInterval: 0.5,
                contexts: []
            )
            detectedPatterns.append(pattern)
        }
    }

    private func detectTimePatterns(_ events: [GestureEvent]) {
        // Group events by hour
        var hourCounts: [Int: [String: Int]] = [:]

        for event in events {
            let hour = Calendar.current.component(.hour, from: event.timestamp)
            if hourCounts[hour] == nil {
                hourCounts[hour] = [:]
            }
            hourCounts[hour]![event.gesture, default: 0] += 1
        }

        // Find gestures with strong time preference
        for (hour, gestures) in hourCounts {
            for (gesture, count) in gestures where count >= 10 {
                let totalForGesture = events.filter { $0.gesture == gesture }.count
                let percentage = Float(count) / Float(totalForGesture)

                if percentage > 0.3 {  // 30%+ at specific hour = pattern
                    let pattern = GesturePattern(
                        id: UUID(),
                        type: .timeOfDay,
                        gestures: [gesture],
                        frequency: count,
                        averageInterval: 0,
                        contexts: ["hour:\(hour)"]
                    )
                    detectedPatterns.append(pattern)
                }
            }
        }
    }

    private func detectLocationPatterns(_ events: [GestureEvent]) {
        // Group events by room
        var roomGestures: [String: [String: Int]] = [:]

        for event in events {
            guard let room = event.targetRoom else { continue }

            if roomGestures[room] == nil {
                roomGestures[room] = [:]
            }
            roomGestures[room]![event.gesture, default: 0] += 1
        }

        // Find room-specific gesture preferences
        for (room, gestures) in roomGestures {
            if let topGesture = gestures.max(by: { $0.value < $1.value }), topGesture.value >= 10 {
                let pattern = GesturePattern(
                    id: UUID(),
                    type: .location,
                    gestures: [topGesture.key],
                    frequency: topGesture.value,
                    averageInterval: 0,
                    contexts: [room]
                )
                detectedPatterns.append(pattern)
            }
        }
    }

    private func inferPreferences(from events: [GestureEvent]) {
        // Infer handedness
        let leftCount = events.filter { $0.handedness == "left" }.count
        let rightCount = events.filter { $0.handedness == "right" }.count
        let bothCount = events.filter { $0.handedness == "both" }.count

        if leftCount > rightCount * 2 {
            inferredPreferences.preferredHand = "left"
        } else if rightCount > leftCount * 2 {
            inferredPreferences.preferredHand = "right"
        } else if bothCount > (leftCount + rightCount) / 2 {
            inferredPreferences.preferredHand = "ambidextrous"
        }

        // Find preferred gestures (high success rate, frequently used)
        var gestureStats: [String: (count: Int, successRate: Float)] = [:]
        let grouped = Dictionary(grouping: events, by: { $0.gesture })

        for (gesture, gestureEvents) in grouped {
            let successCount = gestureEvents.filter { $0.success }.count
            let rate = Float(successCount) / Float(gestureEvents.count)
            gestureStats[gesture] = (gestureEvents.count, rate)
        }

        inferredPreferences.preferredGestures = gestureStats
            .filter { $0.value.count >= 10 && $0.value.successRate >= 0.8 }
            .sorted { $0.value.count > $1.value.count }
            .prefix(5)
            .map { $0.key }

        inferredPreferences.avoidedGestures = gestureStats
            .filter { $0.value.count >= 5 && $0.value.successRate < 0.5 }
            .map { $0.key }

        // Peak usage times
        var hourCounts: [Int: Int] = [:]
        for event in events {
            let hour = Calendar.current.component(.hour, from: event.timestamp)
            hourCounts[hour, default: 0] += 1
        }

        inferredPreferences.peakUsageTimes = hourCounts
            .sorted { $0.value > $1.value }
            .prefix(3)
            .map { $0.key }

        // Gesture speed
        let intervals = zip(events.dropFirst(), events).map {
            $0.timestamp.timeIntervalSince($1.timestamp)
        }
        if !intervals.isEmpty {
            let avgInterval = intervals.reduce(0, +) / Double(intervals.count)
            if avgInterval < 0.5 {
                inferredPreferences.gestureSpeed = .fast
            } else if avgInterval > 1.5 {
                inferredPreferences.gestureSpeed = .slow
            } else {
                inferredPreferences.gestureSpeed = .moderate
            }
        }
    }

    private func generateInsights(from events: [GestureEvent]) {
        latestInsights.removeAll()

        // Performance insight
        let successRate = events.filter { $0.success }.count / max(1, events.count)
        if Float(successRate) < 0.7 {
            latestInsights.append(AnalyticsInsight(
                id: UUID(),
                type: .performance,
                title: String(localized: "insight.lowsuccess.title"),
                description: String(localized: "insight.lowsuccess.description"),
                actionable: true,
                recommendation: String(localized: "insight.lowsuccess.recommendation"),
                relatedGestures: inferredPreferences.avoidedGestures
            ))
        }

        // Pattern insights
        if let frequentPattern = detectedPatterns.max(by: { $0.frequency < $1.frequency }) {
            latestInsights.append(AnalyticsInsight(
                id: UUID(),
                type: .pattern,
                title: String(localized: "insight.pattern.title"),
                description: String(localized: "insight.pattern.description \(frequentPattern.frequency)"),
                actionable: false,
                recommendation: nil,
                relatedGestures: frequentPattern.gestures
            ))
        }

        // Achievement insight
        if events.count >= 1000 {
            latestInsights.append(AnalyticsInsight(
                id: UUID(),
                type: .achievement,
                title: String(localized: "insight.achievement.1000.title"),
                description: String(localized: "insight.achievement.1000.description"),
                actionable: false,
                recommendation: nil,
                relatedGestures: []
            ))
        }
    }

    // MARK: - Export

    /// Exports analytics data as JSON
    func exportJSON() async throws -> URL {
        let allEvents = collectAllEvents()

        let exportData = ExportData(
            exportDate: Date(),
            totalEvents: allEvents.count,
            sessions: allSessions,
            patterns: detectedPatterns,
            preferences: inferredPreferences
        )

        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]

        let data = try encoder.encode(exportData)

        let filename = "gesture_analytics_\(ISO8601DateFormatter().string(from: Date())).json"
        let fileURL = storageURL.appendingPathComponent(filename)

        try data.write(to: fileURL)

        return fileURL
    }

    struct ExportData: Codable {
        let exportDate: Date
        let totalEvents: Int
        let sessions: [AnalyticsSession]
        let patterns: [GesturePattern]
        let preferences: InferredPreferences
    }

    /// Exports analytics as CSV for ML training
    func exportCSV() async throws -> URL {
        let allEvents = collectAllEvents()

        var csv = "id,timestamp,gesture,success,confidence,duration,handedness,target_device,target_room,sequence\n"

        let formatter = ISO8601DateFormatter()
        for event in allEvents {
            let row = [
                event.id.uuidString,
                formatter.string(from: event.timestamp),
                event.gesture,
                event.success ? "1" : "0",
                String(format: "%.3f", event.confidence),
                String(format: "%.3f", event.duration),
                event.handedness,
                event.targetDevice ?? "",
                event.targetRoom ?? "",
                String(event.sequence)
            ].joined(separator: ",")

            csv += row + "\n"
        }

        let filename = "gesture_events_\(ISO8601DateFormatter().string(from: Date())).csv"
        let fileURL = storageURL.appendingPathComponent(filename)

        try csv.write(to: fileURL, atomically: true, encoding: .utf8)

        return fileURL
    }

    /// Exports training data format for ML
    func exportMLTrainingData() async throws -> URL {
        let allEvents = collectAllEvents()

        // Format: Each row is a feature vector + label
        // Features: [gesture_type, confidence, duration, hour, success_rate_history]
        // Label: success (0/1)

        var trainingData: [[Float]] = []

        // Build gesture type mapping
        let allGestures = Set(allEvents.map { $0.gesture }).sorted()
        let gestureToIndex = Dictionary(uniqueKeysWithValues: allGestures.enumerated().map { ($1, $0) })

        var successHistory: [String: (successes: Int, total: Int)] = [:]

        for event in allEvents {
            // Update history first
            if successHistory[event.gesture] == nil {
                successHistory[event.gesture] = (0, 0)
            }

            let history = successHistory[event.gesture]!
            let historyRate = history.total > 0 ? Float(history.successes) / Float(history.total) : 0.5

            // Create feature vector
            let gestureIndex = Float(gestureToIndex[event.gesture] ?? 0)
            let hour = Float(Calendar.current.component(.hour, from: event.timestamp))

            let features: [Float] = [
                gestureIndex,
                event.confidence,
                Float(event.duration),
                hour,
                historyRate,
                event.success ? 1.0 : 0.0  // Label
            ]

            trainingData.append(features)

            // Update history after
            successHistory[event.gesture] = (
                successes: history.successes + (event.success ? 1 : 0),
                total: history.total + 1
            )
        }

        // Convert to JSON
        let encoder = JSONEncoder()
        let data = try encoder.encode(trainingData)

        let filename = "ml_training_\(ISO8601DateFormatter().string(from: Date())).json"
        let fileURL = storageURL.appendingPathComponent(filename)

        try data.write(to: fileURL)

        return fileURL
    }

    // MARK: - Storage

    private func collectAllEvents() -> [GestureEvent] {
        var all = currentSession?.events ?? []

        for session in allSessions {
            all.append(contentsOf: session.events)
        }

        // Load from disk
        if let storedEvents = loadStoredEvents() {
            all.append(contentsOf: storedEvents)
        }

        return all.sorted { $0.timestamp < $1.timestamp }
    }

    private func saveSession(_ session: AnalyticsSession) {
        let filename = "session_\(session.id.uuidString).json"
        let fileURL = storageURL.appendingPathComponent(filename)

        do {
            let encoder = JSONEncoder()
            encoder.dateEncodingStrategy = .iso8601
            let data = try encoder.encode(session)
            try data.write(to: fileURL)
        } catch {
            print("Failed to save session: \(error)")
        }
    }

    private func saveEventsOverflow(_ events: some Collection<GestureEvent>) {
        let filename = "overflow_\(UUID().uuidString).json"
        let fileURL = storageURL.appendingPathComponent(filename)

        do {
            let encoder = JSONEncoder()
            encoder.dateEncodingStrategy = .iso8601
            let data = try encoder.encode(Array(events))
            try data.write(to: fileURL)
        } catch {
            print("Failed to save overflow events: \(error)")
        }
    }

    private func loadStoredData() {
        let fileManager = FileManager.default

        do {
            let files = try fileManager.contentsOfDirectory(at: storageURL, includingPropertiesForKeys: nil)

            for file in files where file.lastPathComponent.hasPrefix("session_") {
                if let data = try? Data(contentsOf: file) {
                    let decoder = JSONDecoder()
                    decoder.dateDecodingStrategy = .iso8601
                    if let session = try? decoder.decode(AnalyticsSession.self, from: data) {
                        // Only load recent sessions
                        if session.startTime.timeIntervalSinceNow > -maxSessionAge {
                            allSessions.append(session)
                        }
                    }
                }
            }

            allSessions.sort { $0.startTime < $1.startTime }
            totalEvents = allSessions.reduce(0) { $0 + $1.events.count }

        } catch {
            print("Failed to load stored data: \(error)")
        }
    }

    private func loadStoredEvents() -> [GestureEvent]? {
        let fileManager = FileManager.default

        do {
            let files = try fileManager.contentsOfDirectory(at: storageURL, includingPropertiesForKeys: nil)
            var events: [GestureEvent] = []

            for file in files where file.lastPathComponent.hasPrefix("overflow_") {
                if let data = try? Data(contentsOf: file) {
                    let decoder = JSONDecoder()
                    decoder.dateDecodingStrategy = .iso8601
                    if let fileEvents = try? decoder.decode([GestureEvent].self, from: data) {
                        events.append(contentsOf: fileEvents)
                    }
                }
            }

            return events
        } catch {
            return nil
        }
    }

    /// Clears all stored analytics data
    func clearAllData() {
        let fileManager = FileManager.default

        do {
            let files = try fileManager.contentsOfDirectory(at: storageURL, includingPropertiesForKeys: nil)
            for file in files {
                try fileManager.removeItem(at: file)
            }
        } catch {
            print("Failed to clear data: \(error)")
        }

        allSessions.removeAll()
        currentSession = nil
        totalEvents = 0
        detectedPatterns.removeAll()
        latestInsights.removeAll()
        inferredPreferences = InferredPreferences()
    }
}

// MARK: - SwiftUI Views

import SwiftUI

/// Analytics dashboard view
struct GestureAnalyticsDashboard: View {
    @EnvironmentObject var analytics: GestureAnalytics

    var body: some View {
        NavigationStack {
            List {
                // Overview section
                Section(String(localized: "analytics.overview")) {
                    LabeledContent(String(localized: "analytics.total"), value: "\(analytics.totalEvents)")

                    if let session = analytics.currentSession {
                        LabeledContent(String(localized: "analytics.session.events"), value: "\(session.events.count)")
                        LabeledContent(String(localized: "analytics.session.success"), value: String(format: "%.0f%%", session.successRate * 100))
                    }
                }

                // Preferences section
                Section(String(localized: "analytics.preferences")) {
                    LabeledContent(String(localized: "analytics.hand"), value: analytics.inferredPreferences.preferredHand)
                    LabeledContent(String(localized: "analytics.speed"), value: analytics.inferredPreferences.gestureSpeed.rawValue)

                    if !analytics.inferredPreferences.preferredGestures.isEmpty {
                        Text(String(localized: "analytics.favorites \(analytics.inferredPreferences.preferredGestures.joined(separator: ", "))"))
                            .font(.caption)
                    }
                }

                // Patterns section
                Section(String(localized: "analytics.patterns")) {
                    ForEach(analytics.detectedPatterns.prefix(5)) { pattern in
                        HStack {
                            Image(systemName: patternIcon(pattern.type))
                            VStack(alignment: .leading) {
                                Text(pattern.gestures.joined(separator: " -> "))
                                    .font(.caption)
                                Text(String(localized: "analytics.pattern.frequency \(pattern.frequency)"))
                                    .font(.caption2)
                                    .foregroundColor(.secondary)
                            }
                        }
                    }
                }

                // Insights section
                Section(String(localized: "analytics.insights")) {
                    ForEach(analytics.latestInsights) { insight in
                        VStack(alignment: .leading, spacing: 4) {
                            HStack {
                                Image(systemName: insightIcon(insight.type))
                                    .foregroundColor(insightColor(insight.type))
                                Text(insight.title)
                                    .font(.subheadline.bold())
                            }
                            Text(insight.description)
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }
                }

                // Export section
                Section(String(localized: "analytics.export")) {
                    Button(String(localized: "analytics.export.json")) {
                        Task {
                            try? await analytics.exportJSON()
                        }
                    }
                    Button(String(localized: "analytics.export.csv")) {
                        Task {
                            try? await analytics.exportCSV()
                        }
                    }
                    Button(String(localized: "analytics.export.ml")) {
                        Task {
                            try? await analytics.exportMLTrainingData()
                        }
                    }
                }

                // Clear data
                Section {
                    Button(String(localized: "analytics.clear"), role: .destructive) {
                        analytics.clearAllData()
                    }
                }
            }
            .navigationTitle(String(localized: "analytics.title"))
        }
    }

    private func patternIcon(_ type: GesturePattern.PatternType) -> String {
        switch type {
        case .sequence: return "arrow.right.arrow.left"
        case .timeOfDay: return "clock"
        case .location: return "location"
        case .deviceBased: return "lightbulb"
        case .errorRecovery: return "arrow.counterclockwise"
        }
    }

    private func insightIcon(_ type: AnalyticsInsight.InsightType) -> String {
        switch type {
        case .performance: return "chart.line.uptrend.xyaxis"
        case .pattern: return "sparkles"
        case .recommendation: return "lightbulb"
        case .warning: return "exclamationmark.triangle"
        case .achievement: return "star.fill"
        }
    }

    private func insightColor(_ type: AnalyticsInsight.InsightType) -> Color {
        switch type {
        case .performance: return .blue
        case .pattern: return .purple
        case .recommendation: return .green
        case .warning: return .orange
        case .achievement: return .yellow
        }
    }
}

/*
 * 鏡
 * h(x) >= 0. Always.
 *
 * Every gesture tells a story.
 * Every pattern reveals preference.
 * From chaos, insight emerges.
 *
 * Data is the mirror.
 * Analytics is the reflection.
 * Understanding is the light.
 */
