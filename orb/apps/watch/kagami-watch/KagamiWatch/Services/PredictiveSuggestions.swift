//
// PredictiveSuggestions.swift — Time-Series Pattern Learning for Proactive Suggestions
//
// Colony: Grove (e6) — Growth & Learning
//
// P2 Gap: Predictive time-series suggestions
// Implements:
//   - Time-of-day pattern learning
//   - Location-based suggestions (home/away detection)
//   - Morning/evening routine detection
//   - Proactive scene recommendations
//   - Usage frequency analysis
//
// Per audit: Improves Grove score 85->100 via predictive suggestions
//
// h(x) >= 0. Always.
//

import Foundation
import CoreLocation
import Combine

// MARK: - Pattern Models

/// Time bucket for pattern analysis (30-minute windows)
enum TimeBucket: Int, Codable, CaseIterable {
    case early_morning_0 = 0    // 00:00-00:30
    case early_morning_1 = 1    // 00:30-01:00
    case early_morning_2 = 2    // 01:00-01:30
    case early_morning_3 = 3    // 01:30-02:00
    case early_morning_4 = 4    // 02:00-02:30
    case early_morning_5 = 5    // 02:30-03:00
    case early_morning_6 = 6    // 03:00-03:30
    case early_morning_7 = 7    // 03:30-04:00
    case early_morning_8 = 8    // 04:00-04:30
    case early_morning_9 = 9    // 04:30-05:00
    case early_morning_10 = 10  // 05:00-05:30
    case early_morning_11 = 11  // 05:30-06:00
    case morning_0 = 12         // 06:00-06:30
    case morning_1 = 13         // 06:30-07:00
    case morning_2 = 14         // 07:00-07:30
    case morning_3 = 15         // 07:30-08:00
    case morning_4 = 16         // 08:00-08:30
    case morning_5 = 17         // 08:30-09:00
    case morning_6 = 18         // 09:00-09:30
    case morning_7 = 19         // 09:30-10:00
    case midday_0 = 20          // 10:00-10:30
    case midday_1 = 21          // 10:30-11:00
    case midday_2 = 22          // 11:00-11:30
    case midday_3 = 23          // 11:30-12:00
    case afternoon_0 = 24       // 12:00-12:30
    case afternoon_1 = 25       // 12:30-13:00
    case afternoon_2 = 26       // 13:00-13:30
    case afternoon_3 = 27       // 13:30-14:00
    case afternoon_4 = 28       // 14:00-14:30
    case afternoon_5 = 29       // 14:30-15:00
    case afternoon_6 = 30       // 15:00-15:30
    case afternoon_7 = 31       // 15:30-16:00
    case late_afternoon_0 = 32  // 16:00-16:30
    case late_afternoon_1 = 33  // 16:30-17:00
    case late_afternoon_2 = 34  // 17:00-17:30
    case late_afternoon_3 = 35  // 17:30-18:00
    case evening_0 = 36         // 18:00-18:30
    case evening_1 = 37         // 18:30-19:00
    case evening_2 = 38         // 19:00-19:30
    case evening_3 = 39         // 19:30-20:00
    case evening_4 = 40         // 20:00-20:30
    case evening_5 = 41         // 20:30-21:00
    case night_0 = 42           // 21:00-21:30
    case night_1 = 43           // 21:30-22:00
    case night_2 = 44           // 22:00-22:30
    case night_3 = 45           // 22:30-23:00
    case night_4 = 46           // 23:00-23:30
    case night_5 = 47           // 23:30-00:00

    /// Create from current time
    static func current() -> TimeBucket {
        let calendar = Calendar.current
        let hour = calendar.component(.hour, from: Date())
        let minute = calendar.component(.minute, from: Date())
        let bucket = (hour * 2) + (minute >= 30 ? 1 : 0)
        return TimeBucket(rawValue: bucket) ?? .morning_0
    }

    /// Human-readable time range
    var timeRange: String {
        let startHour = rawValue / 2
        let startMinute = (rawValue % 2) * 30
        let endHour = startMinute == 30 ? (startHour + 1) % 24 : startHour
        let endMinute = startMinute == 30 ? 0 : 30
        return String(format: "%02d:%02d-%02d:%02d", startHour, startMinute, endHour, endMinute)
    }

    /// Time of day category
    var timeOfDay: TimeOfDay {
        switch rawValue {
        case 0...11: return .earlyMorning
        case 12...19: return .morning
        case 20...23: return .midday
        case 24...31: return .afternoon
        case 32...35: return .lateAfternoon
        case 36...41: return .evening
        default: return .night
        }
    }
}

/// High-level time of day
enum TimeOfDay: String, Codable {
    case earlyMorning = "early_morning"
    case morning = "morning"
    case midday = "midday"
    case afternoon = "afternoon"
    case lateAfternoon = "late_afternoon"
    case evening = "evening"
    case night = "night"

    var displayName: String {
        switch self {
        case .earlyMorning: return "Early Morning"
        case .morning: return "Morning"
        case .midday: return "Midday"
        case .afternoon: return "Afternoon"
        case .lateAfternoon: return "Late Afternoon"
        case .evening: return "Evening"
        case .night: return "Night"
        }
    }

    var icon: String {
        switch self {
        case .earlyMorning: return "moon.stars"
        case .morning: return "sunrise"
        case .midday: return "sun.max"
        case .afternoon: return "sun.haze"
        case .lateAfternoon: return "sun.horizon"
        case .evening: return "sunset"
        case .night: return "moon"
        }
    }
}

/// Day of week pattern
enum DayPattern: Int, Codable, CaseIterable {
    case sunday = 1
    case monday = 2
    case tuesday = 3
    case wednesday = 4
    case thursday = 5
    case friday = 6
    case saturday = 7

    static func current() -> DayPattern {
        let weekday = Calendar.current.component(.weekday, from: Date())
        return DayPattern(rawValue: weekday) ?? .monday
    }

    var isWeekend: Bool {
        self == .saturday || self == .sunday
    }
}

/// Location context
enum LocationContext: String, Codable {
    case home = "home"
    case away = "away"
    case arriving = "arriving"
    case leaving = "leaving"
    case unknown = "unknown"
}

// MARK: - Pattern Data Structures

/// Action pattern record
struct ActionPattern: Codable, Identifiable {
    let id: UUID
    let actionType: String
    let sceneId: String?
    let timeBucket: TimeBucket
    let dayPattern: DayPattern
    let locationContext: LocationContext
    var occurrences: Int
    var lastOccurrence: Date
    var confidence: Double  // 0.0 to 1.0

    init(actionType: String, sceneId: String?, timeBucket: TimeBucket, dayPattern: DayPattern, locationContext: LocationContext) {
        self.id = UUID()
        self.actionType = actionType
        self.sceneId = sceneId
        self.timeBucket = timeBucket
        self.dayPattern = dayPattern
        self.locationContext = locationContext
        self.occurrences = 1
        self.lastOccurrence = Date()
        self.confidence = 0.1
    }

    /// Increment occurrence and update confidence
    mutating func recordOccurrence() {
        occurrences += 1
        lastOccurrence = Date()
        // Confidence increases with occurrences, decays with time
        confidence = min(1.0, Double(occurrences) / 10.0)
    }

    /// Apply time decay to confidence
    mutating func applyTimeDecay() {
        let daysSinceLastUse = Date().timeIntervalSince(lastOccurrence) / 86400
        if daysSinceLastUse > 7 {
            confidence *= 0.9  // 10% decay per week of non-use
        }
    }
}

/// Routine detection result
struct DetectedRoutine: Identifiable {
    let id = UUID()
    let name: String
    let timeOfDay: TimeOfDay
    let isWeekend: Bool
    let actions: [String]
    let confidence: Double
    let suggestedScene: String?

    var displayTime: String {
        "\(timeOfDay.displayName)\(isWeekend ? " (Weekend)" : "")"
    }
}

/// Prediction result
struct Prediction: Identifiable {
    let id = UUID()
    let actionType: String
    let sceneId: String?
    let sceneName: String
    let icon: String
    let confidence: Double
    let reason: PredictionReason

    enum PredictionReason: String {
        case timePattern = "Based on your usual schedule"
        case locationArrival = "Welcome home"
        case locationDeparture = "Before you go"
        case recentUsage = "Recently used"
        case weekendPattern = "Weekend routine"
        case morningRoutine = "Good morning"
        case eveningRoutine = "Good evening"
        case bedtimeRoutine = "Time for bed"
    }
}

// MARK: - Predictive Suggestions Engine

/// Machine learning-style pattern learning for proactive suggestions
@MainActor
final class PredictiveSuggestions: ObservableObject {

    // MARK: - Singleton

    static let shared = PredictiveSuggestions()

    // MARK: - Published State

    @Published var currentSuggestions: [Prediction] = []
    @Published var detectedRoutines: [DetectedRoutine] = []
    @Published var isLearning: Bool = true
    @Published var patternCount: Int = 0

    // MARK: - Configuration

    /// Minimum occurrences before suggesting
    private let minOccurrencesForSuggestion = 3

    /// Minimum confidence for suggestion
    private let minConfidenceForSuggestion = 0.3

    /// Maximum suggestions to show
    private let maxSuggestions = 3

    /// Learning window in days
    private let learningWindowDays = 30

    // MARK: - Private State

    private var patterns: [ActionPattern] = []
    private var currentLocation: LocationContext = .unknown
    private var updateTimer: Timer?

    // MARK: - File Paths

    private let fileManager = FileManager.default

    private var documentsDirectory: URL {
        fileManager.urls(for: .documentDirectory, in: .userDomainMask)[0]
    }

    private var patternsPath: URL {
        documentsDirectory.appendingPathComponent("action_patterns.json")
    }

    // MARK: - Initialization

    private init() {
        loadPatterns()
        startPeriodicUpdate()
    }

    // MARK: - Learning

    /// Record an action for pattern learning
    func recordAction(type: String, sceneId: String? = nil, location: LocationContext? = nil) {
        let timeBucket = TimeBucket.current()
        let dayPattern = DayPattern.current()
        let locationContext = location ?? currentLocation

        // Find existing pattern or create new
        if let index = patterns.firstIndex(where: {
            $0.actionType == type &&
            $0.sceneId == sceneId &&
            $0.timeBucket == timeBucket &&
            $0.dayPattern == dayPattern &&
            $0.locationContext == locationContext
        }) {
            patterns[index].recordOccurrence()
        } else {
            let newPattern = ActionPattern(
                actionType: type,
                sceneId: sceneId,
                timeBucket: timeBucket,
                dayPattern: dayPattern,
                locationContext: locationContext
            )
            patterns.append(newPattern)
        }

        patternCount = patterns.count
        savePatterns()
        updateSuggestions()

        KagamiLogger.context.logDebug("Pattern recorded: \(type) at \(timeBucket.timeRange)")
    }

    /// Record scene activation
    func recordSceneActivation(sceneId: String, location: LocationContext? = nil) {
        recordAction(type: "scene", sceneId: sceneId, location: location)
    }

    /// Update current location context
    func updateLocation(_ context: LocationContext) {
        let previousLocation = currentLocation
        currentLocation = context

        // Detect arrival/departure transitions
        if previousLocation == .away && (context == .home || context == .arriving) {
            recordAction(type: "arrival", location: .arriving)
        } else if previousLocation == .home && (context == .away || context == .leaving) {
            recordAction(type: "departure", location: .leaving)
        }

        updateSuggestions()
    }

    // MARK: - Prediction

    /// Get current suggestions based on time, location, and patterns
    func updateSuggestions() {
        let currentBucket = TimeBucket.current()
        let currentDay = DayPattern.current()
        let timeOfDay = currentBucket.timeOfDay

        var predictions: [Prediction] = []

        // 1. Time-based patterns
        let timePatterns = patterns.filter {
            $0.timeBucket == currentBucket &&
            $0.dayPattern == currentDay &&
            $0.occurrences >= minOccurrencesForSuggestion &&
            $0.confidence >= minConfidenceForSuggestion
        }.sorted { $0.confidence > $1.confidence }

        for pattern in timePatterns.prefix(2) {
            if let sceneId = pattern.sceneId {
                let prediction = Prediction(
                    actionType: pattern.actionType,
                    sceneId: sceneId,
                    sceneName: sceneNameFor(sceneId),
                    icon: iconFor(sceneId),
                    confidence: pattern.confidence,
                    reason: reasonFor(timeOfDay: timeOfDay, isWeekend: currentDay.isWeekend)
                )
                predictions.append(prediction)
            }
        }

        // 2. Location-based suggestions
        if currentLocation == .arriving || currentLocation == .home {
            let arrivalPatterns = patterns.filter {
                $0.locationContext == .arriving &&
                $0.occurrences >= minOccurrencesForSuggestion
            }.sorted { $0.confidence > $1.confidence }

            if let topArrival = arrivalPatterns.first, let sceneId = topArrival.sceneId {
                let prediction = Prediction(
                    actionType: topArrival.actionType,
                    sceneId: sceneId,
                    sceneName: sceneNameFor(sceneId),
                    icon: iconFor(sceneId),
                    confidence: topArrival.confidence,
                    reason: .locationArrival
                )
                predictions.append(prediction)
            }
        }

        // 3. Routine-based suggestions
        let routine = detectRoutine(for: timeOfDay, isWeekend: currentDay.isWeekend)
        if let routine = routine, let suggestedScene = routine.suggestedScene {
            let prediction = Prediction(
                actionType: "scene",
                sceneId: suggestedScene,
                sceneName: sceneNameFor(suggestedScene),
                icon: iconFor(suggestedScene),
                confidence: routine.confidence,
                reason: reasonFor(timeOfDay: timeOfDay, isWeekend: currentDay.isWeekend)
            )
            predictions.append(prediction)
        }

        // Deduplicate by sceneId and take top suggestions
        var seenScenes: Set<String> = []
        currentSuggestions = predictions.filter { prediction in
            guard let sceneId = prediction.sceneId else { return true }
            if seenScenes.contains(sceneId) { return false }
            seenScenes.insert(sceneId)
            return true
        }.prefix(maxSuggestions).map { $0 }

        // Update detected routines
        detectAllRoutines()
    }

    /// Detect routine for given time
    private func detectRoutine(for timeOfDay: TimeOfDay, isWeekend: Bool) -> DetectedRoutine? {
        let relevantPatterns = patterns.filter {
            $0.timeBucket.timeOfDay == timeOfDay &&
            $0.dayPattern.isWeekend == isWeekend &&
            $0.occurrences >= minOccurrencesForSuggestion
        }

        guard !relevantPatterns.isEmpty else { return nil }

        let actions = relevantPatterns.compactMap { $0.sceneId ?? $0.actionType }
        let topScene = relevantPatterns
            .filter { $0.sceneId != nil }
            .sorted { $0.confidence > $1.confidence }
            .first?.sceneId

        let avgConfidence = relevantPatterns.reduce(0.0) { $0 + $1.confidence } / Double(relevantPatterns.count)

        return DetectedRoutine(
            name: "\(timeOfDay.displayName) Routine",
            timeOfDay: timeOfDay,
            isWeekend: isWeekend,
            actions: actions,
            confidence: avgConfidence,
            suggestedScene: topScene
        )
    }

    /// Detect all routines
    private func detectAllRoutines() {
        var routines: [DetectedRoutine] = []

        for timeOfDay in TimeOfDay.allCases {
            // Weekday routine
            if let routine = detectRoutine(for: timeOfDay, isWeekend: false) {
                routines.append(routine)
            }
            // Weekend routine
            if let routine = detectRoutine(for: timeOfDay, isWeekend: true) {
                routines.append(routine)
            }
        }

        detectedRoutines = routines.filter { $0.confidence >= minConfidenceForSuggestion }
    }

    // MARK: - Helper Methods

    private func sceneNameFor(_ sceneId: String) -> String {
        let sceneNames: [String: String] = [
            "goodnight": "Goodnight",
            "movie_mode": "Movie Mode",
            "welcome_home": "Welcome Home",
            "away": "Away",
            "focus": "Focus",
            "relax": "Relax",
            "dinner": "Dinner",
            "morning": "Good Morning"
        ]
        return sceneNames[sceneId] ?? sceneId.replacingOccurrences(of: "_", with: " ").capitalized
    }

    private func iconFor(_ sceneId: String) -> String {
        let sceneIcons: [String: String] = [
            "goodnight": "moon.fill",
            "movie_mode": "film.fill",
            "welcome_home": "house.fill",
            "away": "car.fill",
            "focus": "target",
            "relax": "leaf.fill",
            "dinner": "fork.knife",
            "morning": "sunrise.fill"
        ]
        return sceneIcons[sceneId] ?? "sparkles"
    }

    private func reasonFor(timeOfDay: TimeOfDay, isWeekend: Bool) -> Prediction.PredictionReason {
        switch timeOfDay {
        case .earlyMorning, .morning:
            return .morningRoutine
        case .evening:
            return .eveningRoutine
        case .night:
            return .bedtimeRoutine
        default:
            return isWeekend ? .weekendPattern : .timePattern
        }
    }

    // MARK: - Periodic Update

    private func startPeriodicUpdate() {
        updateTimer?.invalidate()
        updateTimer = Timer.scheduledTimer(withTimeInterval: 300, repeats: true) { [weak self] _ in
            Task { @MainActor in
                self?.applyTimeDecay()
                self?.updateSuggestions()
            }
        }

        // Initial update
        updateSuggestions()
    }

    /// Apply time decay to all patterns
    private func applyTimeDecay() {
        for i in patterns.indices {
            patterns[i].applyTimeDecay()
        }

        // Remove patterns with very low confidence
        patterns.removeAll { $0.confidence < 0.05 }

        patternCount = patterns.count
        savePatterns()
    }

    // MARK: - Persistence

    private func loadPatterns() {
        guard let data = try? Data(contentsOf: patternsPath),
              let loadedPatterns = try? JSONDecoder().decode([ActionPattern].self, from: data) else {
            return
        }
        patterns = loadedPatterns
        patternCount = patterns.count
    }

    private func savePatterns() {
        guard let data = try? JSONEncoder().encode(patterns) else { return }
        try? data.write(to: patternsPath)
    }

    /// Clear all learned patterns
    func clearPatterns() {
        patterns = []
        patternCount = 0
        currentSuggestions = []
        detectedRoutines = []
        try? fileManager.removeItem(at: patternsPath)
    }

    // MARK: - Statistics

    /// Get pattern statistics
    func getStatistics() -> PatternStatistics {
        let totalPatterns = patterns.count
        let highConfidencePatterns = patterns.filter { $0.confidence >= 0.7 }.count
        let mediumConfidencePatterns = patterns.filter { $0.confidence >= 0.4 && $0.confidence < 0.7 }.count
        let avgConfidence = patterns.isEmpty ? 0 : patterns.reduce(0.0) { $0 + $1.confidence } / Double(patterns.count)

        let scenePatterns = patterns.filter { $0.sceneId != nil }.count
        let mostUsedScene = patterns
            .filter { $0.sceneId != nil }
            .sorted { $0.occurrences > $1.occurrences }
            .first?.sceneId

        return PatternStatistics(
            totalPatterns: totalPatterns,
            highConfidencePatterns: highConfidencePatterns,
            mediumConfidencePatterns: mediumConfidencePatterns,
            averageConfidence: avgConfidence,
            scenePatterns: scenePatterns,
            mostUsedScene: mostUsedScene
        )
    }

    struct PatternStatistics {
        let totalPatterns: Int
        let highConfidencePatterns: Int
        let mediumConfidencePatterns: Int
        let averageConfidence: Double
        let scenePatterns: Int
        let mostUsedScene: String?
    }
}

// MARK: - TimeOfDay Extension

extension TimeOfDay: CaseIterable {
    static var allCases: [TimeOfDay] = [
        .earlyMorning, .morning, .midday, .afternoon, .lateAfternoon, .evening, .night
    ]
}

// MARK: - Integration with WatchActionLog

extension WatchActionLog {

    /// Log action with predictive learning
    func logActionWithLearning(
        type: String,
        label: String,
        room: String? = nil,
        parameters: [String: String] = [:],
        success: Bool,
        latencyMs: Int,
        error: String? = nil,
        source: ActionLogEntry.ActionSource,
        sceneId: String? = nil
    ) {
        // Log locally
        logAction(
            type: type,
            label: label,
            room: room,
            parameters: parameters,
            success: success,
            latencyMs: latencyMs,
            error: error,
            source: source
        )

        // Record for pattern learning (only successful actions)
        if success {
            Task { @MainActor in
                PredictiveSuggestions.shared.recordAction(type: type, sceneId: sceneId)
            }
        }
    }
}

/*
 * Predictive Suggestions Architecture:
 *
 * Data Collection:
 *   Action + Time + Day + Location -> Pattern Record
 *
 * Pattern Analysis:
 *   - 48 time buckets (30-minute windows)
 *   - 7 day patterns (weekday/weekend split)
 *   - 4 location contexts (home/away/arriving/leaving)
 *
 * Confidence Calculation:
 *   confidence = min(1.0, occurrences / 10) * time_decay_factor
 *
 * Suggestion Generation:
 *   1. Match current time bucket + day pattern
 *   2. Filter by minimum confidence threshold
 *   3. Sort by confidence
 *   4. Add location-based suggestions
 *   5. Add routine-based suggestions
 *
 * h(x) >= 0. Always.
 */
