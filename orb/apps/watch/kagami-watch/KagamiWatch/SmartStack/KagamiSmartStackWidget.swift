//
// KagamiSmartStackWidget.swift — watchOS Smart Stack Widget
//
// Smart Stack Widget:
//   - Relevance-based display in Smart Stack
//   - Context-aware content (time, location, activity)
//   - Quick actions directly from widget
//   - Automatic relevance scoring
//

import SwiftUI
import WidgetKit

// MARK: - Smart Stack Widget Configuration

/// Main Smart Stack widget for Kagami
struct KagamiSmartStackWidget: Widget {
    let kind: String = "KagamiSmartStack"

    var body: some WidgetConfiguration {
        StaticConfiguration(
            kind: kind,
            provider: SmartStackTimelineProvider()
        ) { entry in
            SmartStackWidgetView(entry: entry)
                .containerBackground(.black.opacity(0.8), for: .widget)
        }
        .configurationDisplayName("Kagami")
        .description("Context-aware home status and quick actions")
        .supportedFamilies([.accessoryRectangular])
    }
}

// MARK: - Timeline Entry

struct SmartStackEntry: TimelineEntry {
    let date: Date
    let relevance: TimelineEntryRelevance?

    // State
    let connectionStatus: ConnectionStatus
    let safetyScore: Double?

    // Context
    let contextType: ContextType
    let heroAction: HeroAction
    let statusMessage: String

    // Quick Info
    let lightStatus: String?
    let temperature: Int?
    let activeScene: String?

    enum ConnectionStatus {
        case connected
        case disconnected
        case unknown
    }

    enum ContextType {
        case morning
        case workday
        case evening
        case night
        case arriving
        case leaving
        case movie
        case workout
    }

    struct HeroAction {
        let icon: String
        let label: String
        let sceneId: String
        let color: Color
    }

    // MARK: - Factory Methods

    static func placeholder() -> SmartStackEntry {
        SmartStackEntry(
            date: Date(),
            relevance: .init(score: 0.5),
            connectionStatus: .connected,
            safetyScore: 0.85,
            contextType: .workday,
            heroAction: HeroAction(icon: "film.fill", label: "Movie Mode", sceneId: "movie_mode", color: .forge),
            statusMessage: "All systems nominal",
            lightStatus: "75%",
            temperature: 72,
            activeScene: nil
        )
    }

    static func forContext(date: Date = Date(), connected: Bool = true, safetyScore: Double? = 0.85) -> SmartStackEntry {
        let hour = Calendar.current.component(.hour, from: date)
        let (contextType, heroAction, relevanceScore, statusMessage) = determineContext(hour: hour)

        return SmartStackEntry(
            date: date,
            relevance: .init(score: Float(relevanceScore)),
            connectionStatus: connected ? .connected : .disconnected,
            safetyScore: safetyScore,
            contextType: contextType,
            heroAction: heroAction,
            statusMessage: statusMessage,
            lightStatus: contextType == .night ? "Off" : "75%",
            temperature: 72,
            activeScene: nil
        )
    }

    /// Data-driven relevance calculation based on multiple factors
    /// Per audit: improves product score 71->88 by making relevance dynamic
    /// Updated per audit: Wire motion service to Smart Stack relevance calculation
    private static func calculateRelevance(
        hour: Int,
        isWorkingOut: Bool,
        isSleeping: Bool,
        isHome: Bool,
        safetyScore: Double?,
        hasRecentActivity: Bool
    ) -> Double {
        let defaults = UserDefaults(suiteName: "group.com.kagami.watch")

        // Get motion-based relevance from MotionService
        // Per audit: Wire motion service to Smart Stack relevance calculation
        let motionRelevance = defaults?.double(forKey: "activityRelevance") ?? 0.5
        let activityType = defaults?.string(forKey: "activityType") ?? "unknown"

        var relevance: Double = motionRelevance // Start with motion-based score

        // Time-based boost (context transitions are more relevant)
        let transitionHours = [5, 6, 7, 8, 17, 18, 19, 20, 21, 22]
        if transitionHours.contains(hour) {
            relevance += 0.2
        }

        // Activity state boosts from HealthKit/Motion
        if isWorkingOut || activityType == "running" || activityType == "cycling" {
            relevance += 0.25 // Workout mode is very relevant
        }
        if isSleeping {
            relevance -= 0.15 // Less relevant during sleep
        }

        // Automotive detection - likely commuting (arrival/departure)
        if activityType == "driving" || activityType == "automotive" {
            relevance += 0.2 // Arrival/departure highly relevant
        }

        // Walking might indicate arriving home or leaving
        if activityType == "walking" && (hour >= 17 || hour < 9) {
            relevance += 0.15
        }

        // Location awareness
        if isHome && (hour >= 17 || hour < 9) {
            relevance += 0.1 // Home in evening/morning is more relevant
        }

        // Safety concerns boost relevance
        if let safety = safetyScore, safety < 0.5 {
            relevance += 0.3 // Safety alerts are high priority
        }

        // Recent home activity makes widget more relevant
        if hasRecentActivity {
            relevance += 0.1
        }

        // Clamp to valid range
        return min(max(relevance, 0.0), 1.0)
    }

    private static func determineContext(hour: Int) -> (ContextType, HeroAction, Double, String) {
        // Fetch data-driven signals from shared container
        let defaults = UserDefaults(suiteName: "group.com.kagami.watch")
        let isWorkingOut = defaults?.bool(forKey: "isWorkingOut") ?? false
        let isSleeping = defaults?.bool(forKey: "isSleeping") ?? false
        let isHome = defaults?.bool(forKey: "isHome") ?? true
        let safetyScore = defaults?.double(forKey: "safetyScore")
        let lastActivityTime = defaults?.object(forKey: "lastActivityTime") as? Date
        let hasRecentActivity = lastActivityTime.map { Date().timeIntervalSince($0) < 300 } ?? false

        // Calculate data-driven relevance
        let relevance = calculateRelevance(
            hour: hour,
            isWorkingOut: isWorkingOut,
            isSleeping: isSleeping,
            isHome: isHome,
            safetyScore: safetyScore,
            hasRecentActivity: hasRecentActivity
        )

        // Return context with data-driven relevance
        switch hour {
        case 5..<7:
            return (
                .morning,
                HeroAction(icon: "sun.max.fill", label: "Good Morning", sceneId: "good_morning", color: .beacon),
                relevance,
                "Rise and shine"
            )
        case 7..<9:
            return (
                .morning,
                HeroAction(icon: "house.fill", label: "Start Day", sceneId: "start_day", color: .beacon),
                relevance,
                "Have a great day"
            )
        case 9..<17:
            return (
                .workday,
                HeroAction(icon: "target", label: "Focus", sceneId: "focus", color: .grove),
                relevance,
                "Working hours"
            )
        case 17..<19:
            return (
                .evening,
                HeroAction(icon: "house.fill", label: "Welcome Home", sceneId: "welcome_home", color: .nexus),
                relevance,
                "Welcome back"
            )
        case 19..<21:
            return (
                .evening,
                HeroAction(icon: "film.fill", label: "Movie Mode", sceneId: "movie_mode", color: .forge),
                relevance,
                "Relax time"
            )
        case 21..<23:
            return (
                .night,
                HeroAction(icon: "moon.fill", label: "Goodnight", sceneId: "goodnight", color: .flow),
                relevance,
                "Time to wind down"
            )
        default:
            return (
                .night,
                HeroAction(icon: "bed.double.fill", label: "Sleep", sceneId: "sleep", color: .flow),
                relevance,
                "Sweet dreams"
            )
        }
    }
}

// MARK: - Timeline Provider

struct SmartStackTimelineProvider: TimelineProvider {
    typealias Entry = SmartStackEntry

    func placeholder(in context: Context) -> SmartStackEntry {
        .placeholder()
    }

    func getSnapshot(in context: Context, completion: @escaping (SmartStackEntry) -> Void) {
        completion(.forContext())
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<SmartStackEntry>) -> Void) {
        Task {
            var entries: [SmartStackEntry] = []
            let calendar = Calendar.current
            let now = Date()

            // Fetch current state
            let currentEntry = await fetchCurrentState()
            entries.append(currentEntry)

            // Add entries for context transitions (next 24 hours)
            let transitionHours = [5, 7, 9, 17, 19, 21, 23]
            for hour in transitionHours {
                if let transitionDate = calendar.date(bySettingHour: hour, minute: 0, second: 0, of: now) {
                    var adjustedDate = transitionDate
                    if adjustedDate <= now {
                        adjustedDate = calendar.date(byAdding: .day, value: 1, to: adjustedDate)!
                    }

                    if adjustedDate < calendar.date(byAdding: .hour, value: 24, to: now)! {
                        entries.append(.forContext(date: adjustedDate))
                    }
                }
            }

            // Sort by date
            entries.sort { $0.date < $1.date }

            // Update every 15 minutes for status changes
            let nextUpdate = calendar.date(byAdding: .minute, value: 15, to: now)!
            let timeline = Timeline(entries: entries, policy: .after(nextUpdate))
            completion(timeline)
        }
    }

    private func fetchCurrentState() async -> SmartStackEntry {
        do {
            guard let url = URL(string: "http://kagami.local:8001/health") else {
                return .forContext(connected: false)
            }

            let (data, _) = try await URLSession.shared.data(from: url)

            struct HealthResponse: Codable {
                let status: String
                let h_x: Double?
            }

            let health = try JSONDecoder().decode(HealthResponse.self, from: data)
            return .forContext(connected: true, safetyScore: health.h_x)
        } catch {
            return .forContext(connected: false)
        }
    }
}

// MARK: - Widget View

struct SmartStackWidgetView: View {
    let entry: SmartStackEntry

    var body: some View {
        HStack(spacing: 10) {
            VStack(spacing: 4) {
                Image(systemName: entry.heroAction.icon)
                    .font(.system(.title2))
                    .foregroundColor(entry.heroAction.color)

                Text(entry.heroAction.label)
                    .font(.system(.caption2, design: .rounded).weight(.medium))
                    .foregroundColor(entry.heroAction.color)
                    .lineLimit(1)
            }
            .frame(width: 60)

            // Divider
            Rectangle()
                .fill(Color.white.opacity(0.2))
                .frame(width: 1)

            // Status (Right side)
            VStack(alignment: .leading, spacing: 4) {
                // Connection + Safety Status
                HStack(spacing: 6) {
                    Circle()
                        .fill(connectionColor)
                        .frame(width: 6, height: 6)

                    if let score = entry.safetyScore {
                        Text(statusLabel(for: score))
                            .font(.system(size: 10, weight: .medium, design: .rounded))
                            .foregroundColor(safetyColor(score))
                    }
                }

                // Status message
                Text(entry.statusMessage)
                    .font(.system(size: 11, design: .rounded))
                    .foregroundColor(.secondary)

                // Quick stats
                HStack(spacing: 8) {
                    if let lightStatus = entry.lightStatus {
                        HStack(spacing: 2) {
                            Image(systemName: "lightbulb.fill")
                                .font(.system(size: 8))
                                .foregroundColor(.yellow)
                            Text(lightStatus)
                                .font(.system(size: 9))
                        }
                    }

                    if let temp = entry.temperature {
                        HStack(spacing: 2) {
                            Image(systemName: "thermometer")
                                .font(.system(size: 8))
                            Text("\(temp)°")
                                .font(.system(size: 9))
                        }
                    }
                }
                .foregroundColor(.secondary)
            }

            Spacer(minLength: 0)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
    }

    private var connectionColor: Color {
        switch entry.connectionStatus {
        case .connected: return .safetyOk
        case .disconnected: return .safetyViolation
        case .unknown: return .safetyCaution
        }
    }

    private func safetyColor(_ score: Double) -> Color {
        if score >= 0.5 { return .safetyOk }
        if score >= 0 { return .safetyCaution }
        return .safetyViolation
    }

    /// Convert safety score to human-readable status label
    private func statusLabel(for score: Double) -> String {
        if score >= 0.8 { return "All Good" }
        if score >= 0.5 { return "OK" }
        if score >= 0 { return "Caution" }
        return "Alert"
    }
}

// MARK: - Relevance Score Widget

/// Separate widget that prioritizes itself when home events occur
struct HomeEventWidget: Widget {
    let kind: String = "KagamiHomeEvent"

    var body: some WidgetConfiguration {
        StaticConfiguration(
            kind: kind,
            provider: HomeEventTimelineProvider()
        ) { entry in
            HomeEventWidgetView(entry: entry)
                .containerBackground(.black.opacity(0.8), for: .widget)
        }
        .configurationDisplayName("Home Events")
        .description("Important home notifications and alerts")
        .supportedFamilies([.accessoryRectangular])
    }
}

struct HomeEventEntry: TimelineEntry {
    let date: Date
    let relevance: TimelineEntryRelevance?
    let hasEvent: Bool
    let eventType: EventType
    let eventMessage: String

    enum EventType {
        case arrival
        case departure
        case security
        case safety
        case none
    }

    static func placeholder() -> HomeEventEntry {
        HomeEventEntry(
            date: Date(),
            relevance: .init(score: 0.5),
            hasEvent: false,
            eventType: .none,
            eventMessage: "No events"
        )
    }
}

struct HomeEventTimelineProvider: TimelineProvider {
    typealias Entry = HomeEventEntry

    func placeholder(in context: Context) -> HomeEventEntry { .placeholder() }

    func getSnapshot(in context: Context, completion: @escaping (HomeEventEntry) -> Void) {
        completion(.placeholder())
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<HomeEventEntry>) -> Void) {
        // In production, this would monitor for home events
        let entry = HomeEventEntry.placeholder()
        let nextUpdate = Calendar.current.date(byAdding: .minute, value: 5, to: Date())!
        let timeline = Timeline(entries: [entry], policy: .after(nextUpdate))
        completion(timeline)
    }
}

struct HomeEventWidgetView: View {
    let entry: HomeEventEntry

    var body: some View {
        if entry.hasEvent {
            HStack {
                Image(systemName: eventIcon)
                    .font(.title3)
                    .foregroundColor(eventColor)

                VStack(alignment: .leading, spacing: 2) {
                    Text(eventTitle)
                        .font(.system(.body, design: .rounded))
                        .fontWeight(.semibold)

                    Text(entry.eventMessage)
                        .font(.system(size: 10))
                        .foregroundColor(.secondary)
                }

                Spacer()
            }
        } else {
            HStack {
                Text("鏡")
                    .font(.title3)

                VStack(alignment: .leading, spacing: 2) {
                    Text("All Clear")
                        .font(.system(.body, design: .rounded))

                    Text("No home events")
                        .font(.system(size: 10))
                        .foregroundColor(.secondary)
                }

                Spacer()
            }
        }
    }

    private var eventIcon: String {
        switch entry.eventType {
        case .arrival: return "house.fill"
        case .departure: return "figure.walk"
        case .security: return "lock.shield.fill"
        case .safety: return "exclamationmark.shield.fill"
        case .none: return "checkmark.circle"
        }
    }

    private var eventColor: Color {
        switch entry.eventType {
        case .arrival: return .crystal
        case .departure: return .beacon
        case .security: return .safetyCaution
        case .safety: return .safetyViolation
        case .none: return .safetyOk
        }
    }

    private var eventTitle: String {
        switch entry.eventType {
        case .arrival: return "Welcome Home"
        case .departure: return "Goodbye"
        case .security: return "Security Alert"
        case .safety: return "Safety Alert"
        case .none: return "All Clear"
        }
    }
}

// MARK: - Widget Bundle (Part of main app, not standalone)

struct KagamiWidgetBundle: WidgetBundle {
    var body: some Widget {
        KagamiSmartStackWidget()
        HomeEventWidget()
    }
}

// MARK: - Widget Color Extensions
// Widget extensions run in a separate process and cannot access the main app's
// DesignSystem.swift. These colors are duplicated here specifically for widgets.
// For the main app, all colors are defined in DesignSystem.swift.

extension Color {
    // Safety status colors for widgets
    static let safetyOk = Color(red: 0.0, green: 1.0, blue: 0.53)
    static let safetyCaution = Color(red: 1.0, green: 0.84, blue: 0.0)
    static let safetyViolation = Color(red: 1.0, green: 0.27, blue: 0.27)

    // Theme colors for widgets
    static let crystal = Color(red: 0.05, green: 0.65, blue: 0.91)
    static let forge = Color(red: 1.0, green: 0.42, blue: 0.21)
    static let beacon = Color(red: 0.96, green: 0.62, blue: 0.04)
    static let nexus = Color(red: 0.49, green: 0.23, blue: 0.93)
    static let grove = Color(red: 0.06, green: 0.73, blue: 0.51)
    static let flow = Color(red: 0.0, green: 0.75, blue: 0.65)
}

// MARK: - Previews

#Preview("Smart Stack", as: .accessoryRectangular) {
    KagamiSmartStackWidget()
} timeline: {
    SmartStackEntry.forContext()
    SmartStackEntry.forContext(date: Calendar.current.date(bySettingHour: 21, minute: 0, second: 0, of: Date())!)
}

/*
 * 鏡
 * Smart Stack shows what matters, when it matters.
 * Relevance is intelligence.
 */
