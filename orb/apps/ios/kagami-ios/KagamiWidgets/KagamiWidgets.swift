//
// KagamiWidgets.swift — iOS Widget Extension
//
// Widget Gallery:
//   - Small: Safety score or Hero action
//   - Medium: Quick scenes grid
//   - Large: Room status overview
//   - Lock Screen: Safety indicator
//   - Accessory: Complications
//   - Live Activity: Scene progress, timers
//

import WidgetKit
import SwiftUI
import AppIntents
import ActivityKit

// MARK: - Widget Bundle

@main
struct KagamiWidgetBundle: WidgetBundle {
    var body: some Widget {
        SafetyScoreWidget()
        QuickScenesWidget()
        RoomStatusWidget()
        HeroActionWidget()
        SafetyAccessoryWidget()
        ConfigurableScenesWidget()
        ConfigurableRoomsWidget()
        AmbientStatusWidget()
    }
}

// MARK: - Timeline Provider

struct KagamiTimelineProvider: TimelineProvider {
    func placeholder(in context: Context) -> KagamiEntry {
        KagamiEntry(date: Date(), safetyScore: 0.85, heroScene: "Movie Mode", rooms: DemoRooms.all)
    }

    func getSnapshot(in context: Context, completion: @escaping (KagamiEntry) -> Void) {
        let entry = KagamiEntry(date: Date(), safetyScore: 0.85, heroScene: "Movie Mode", rooms: DemoRooms.all)
        completion(entry)
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<KagamiEntry>) -> Void) {
        Task {
            let entry = await fetchCurrentState()
            let timeline = Timeline(entries: [entry], policy: .after(Date().addingTimeInterval(60 * 15)))
            completion(timeline)
        }
    }

    private func fetchCurrentState() async -> KagamiEntry {
        // In production, this would fetch from the API
        // For now, return demo data
        return KagamiEntry(
            date: Date(),
            safetyScore: 0.85,
            heroScene: determineHeroScene(),
            rooms: DemoRooms.all
        )
    }

    private func determineHeroScene() -> String {
        let hour = Calendar.current.component(.hour, from: Date())
        switch hour {
        case 0..<6: return "Sleep Mode"
        case 6..<9: return "Good Morning"
        case 9..<17: return "Focus"
        case 17..<21: return "Movie Mode"
        default: return "Goodnight"
        }
    }
}

// MARK: - Timeline Entry

struct KagamiEntry: TimelineEntry {
    let date: Date
    let safetyScore: Double
    let heroScene: String
    let rooms: [WidgetRoom]
}

struct WidgetRoom: Identifiable {
    let id: String
    let name: String
    let lightLevel: Int
    let isOccupied: Bool
}

// MARK: - Demo Data

enum DemoRooms {
    static let all: [WidgetRoom] = [
        WidgetRoom(id: "57", name: "Living Room", lightLevel: 75, isOccupied: true),
        WidgetRoom(id: "59", name: "Kitchen", lightLevel: 100, isOccupied: false),
        WidgetRoom(id: "47", name: "Office", lightLevel: 80, isOccupied: true),
        WidgetRoom(id: "36", name: "Primary Bed", lightLevel: 0, isOccupied: false),
    ]
}

// MARK: - Widget 1: Safety Score (Small)

struct SafetyScoreWidget: Widget {
    let kind: String = "SafetyScoreWidget"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: KagamiTimelineProvider()) { entry in
            SafetyScoreWidgetView(entry: entry)
                .containerBackground(.black, for: .widget)
        }
        .configurationDisplayName("Safety Score")
        .description("Shows your home's current safety status")
        .supportedFamilies([.systemSmall])
    }
}

struct SafetyScoreWidgetView: View {
    let entry: KagamiEntry

    var body: some View {
        VStack(spacing: 8) {
            Text("鏡")
                .font(.system(size: 32))
                .foregroundColor(safetyColor)
                .accessibilityLabel("Kagami")

            Text(String(format: "%.0f", entry.safetyScore * 100))
                .font(.system(size: 48, weight: .bold, design: .rounded))
                .foregroundColor(safetyColor)
                .accessibilityLabel("Safety score: \(Int(entry.safetyScore * 100)) percent")

            Text("Safety")
                .font(.caption)
                .foregroundColor(.gray)
                .accessibilityHidden(true)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Kagami safety score: \(Int(entry.safetyScore * 100)) percent")
    }

    var safetyColor: Color {
        if entry.safetyScore >= 0.5 { return Color(hex: "00ff88") }
        if entry.safetyScore >= 0 { return Color(hex: "ffd700") }
        return Color(hex: "ff4444")
    }
}

// MARK: - Widget 2: Quick Scenes (Medium)

struct QuickScenesWidget: Widget {
    let kind: String = "QuickScenesWidget"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: KagamiTimelineProvider()) { entry in
            QuickScenesWidgetView(entry: entry)
                .containerBackground(.black, for: .widget)
        }
        .configurationDisplayName("Quick Scenes")
        .description("One-tap access to common scenes")
        .supportedFamilies([.systemMedium])
    }
}

struct QuickScenesWidgetView: View {
    let entry: KagamiEntry

    let scenes: [(emoji: String, name: String, label: String)] = [
        ("🎬", "Movie", "Movie mode"),
        ("🌙", "Goodnight", "Goodnight scene"),
        ("🏡", "Welcome", "Welcome home"),
        ("🔒", "Away", "Away mode"),
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("鏡")
                    .font(.headline)
                    .foregroundColor(Color(hex: "67d4e4"))
                    .accessibilityLabel("Kagami")
                Text("Kagami")
                    .font(.headline)
                    .foregroundColor(.white)
                Spacer()
                Text(String(format: "Safe %.0f", entry.safetyScore * 100))
                    .font(.caption)
                    .foregroundColor(Color(hex: "00ff88"))
                    .accessibilityLabel("Safety score \(Int(entry.safetyScore * 100)) percent")
            }
            .accessibilityElement(children: .combine)

            HStack(spacing: 12) {
                ForEach(scenes, id: \.name) { scene in
                    if let url = URL(string: "kagami://scene/\(scene.name.lowercased())") {
                        Link(destination: url) {
                            VStack(spacing: 4) {
                                Text(scene.emoji)
                                    .font(.title2)
                                    .accessibilityHidden(true)
                                Text(scene.name)
                                    .font(.caption2)
                                    .foregroundColor(.gray)
                            }
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 8)
                            .background(Color.white.opacity(0.1))
                            .cornerRadius(12)
                        }
                        .accessibilityLabel("Activate \(scene.label)")
                    }
                }
            }
        }
        .padding()
    }
}

// MARK: - Widget 3: Room Status (Large)

struct RoomStatusWidget: Widget {
    let kind: String = "RoomStatusWidget"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: KagamiTimelineProvider()) { entry in
            RoomStatusWidgetView(entry: entry)
                .containerBackground(.black, for: .widget)
        }
        .configurationDisplayName("Room Status")
        .description("Overview of rooms and lighting")
        .supportedFamilies([.systemLarge])
    }
}

struct RoomStatusWidgetView: View {
    let entry: KagamiEntry

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Header
            HStack {
                Text("鏡")
                    .font(.title2)
                    .foregroundColor(Color(hex: "67d4e4"))
                Text("Home Status")
                    .font(.headline)
                    .foregroundColor(.white)
                Spacer()
                Text(entry.date.formatted(date: .omitted, time: .shortened))
                    .font(.caption)
                    .foregroundColor(.gray)
            }

            // Hero Scene
            HStack {
                Text("🎯")
                Text(entry.heroScene)
                    .font(.subheadline)
                    .foregroundColor(.white)
                Spacer()
                if let url = URL(string: "kagami://scene/\(entry.heroScene.lowercased().replacingOccurrences(of: " ", with: "_"))") {
                    Link(destination: url) {
                        Text("Activate")
                            .font(.caption)
                            .padding(.horizontal, 12)
                            .padding(.vertical, 4)
                            .background(Color(hex: "67d4e4"))
                            .foregroundColor(.black)
                            .cornerRadius(8)
                    }
                }
            }
            .padding()
            .background(Color.white.opacity(0.1))
            .cornerRadius(12)

            // Room Grid
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 8) {
                ForEach(entry.rooms) { room in
                    RoomWidgetCell(room: room)
                }
            }

            // Safety Bar
            HStack {
                Text("Safety Status")
                    .font(.caption)
                    .foregroundColor(.gray)
                Spacer()
                ProgressView(value: entry.safetyScore)
                    .tint(Color(hex: "00ff88"))
                    .frame(width: 100)
            }
        }
        .padding()
    }
}

struct RoomWidgetCell: View {
    let room: WidgetRoom

    private var accessibilityDescription: String {
        var description = "\(room.name), lights at \(room.lightLevel) percent"
        if room.isOccupied {
            description += ", occupied"
        }
        return description
    }

    var body: some View {
        Group {
            if let url = URL(string: "kagami://room/\(room.id)") {
                Link(destination: url) {
                    roomContent
                }
            } else {
                roomContent
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel(accessibilityDescription)
        .accessibilityHint("Tap to control \(room.name)")
    }

    private var roomContent: some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text(room.name)
                    .font(.caption)
                    .foregroundColor(.white)
                    .lineLimit(1)

                HStack(spacing: 4) {
                    Image(systemName: room.lightLevel > 0 ? "lightbulb.fill" : "lightbulb")
                        .font(.caption2)
                        .foregroundColor(room.lightLevel > 0 ? .yellow : .gray)
                        .accessibilityHidden(true)

                    Text("\(room.lightLevel)%")
                        .font(.caption2)
                        .foregroundColor(.gray)
                        .accessibilityHidden(true)
                }
            }

            Spacer()

            if room.isOccupied {
                Circle()
                    .fill(Color(hex: "00ff88"))
                    .frame(width: 8, height: 8)
                    .accessibilityHidden(true)
            }
        }
        .padding(8)
        .background(Color.white.opacity(0.05))
        .cornerRadius(8)
    }
}

// MARK: - Widget 4: Hero Action (Small)

struct HeroActionWidget: Widget {
    let kind: String = "HeroActionWidget"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: KagamiTimelineProvider()) { entry in
            HeroActionWidgetView(entry: entry)
                .containerBackground(.black, for: .widget)
        }
        .configurationDisplayName("Hero Action")
        .description("Context-aware quick action")
        .supportedFamilies([.systemSmall])
    }
}

struct HeroActionWidgetView: View {
    let entry: KagamiEntry

    var heroIcon: String {
        switch entry.heroScene {
        case "Movie Mode": return "🎬"
        case "Goodnight": return "🌙"
        case "Good Morning": return "☀️"
        case "Focus": return "🎯"
        case "Sleep Mode": return "😴"
        default: return "🏡"
        }
    }

    var body: some View {
        Group {
            if let url = URL(string: "kagami://scene/\(entry.heroScene.lowercased().replacingOccurrences(of: " ", with: "_"))") {
                Link(destination: url) {
                    heroContent
                }
            } else {
                heroContent
            }
        }
        .accessibilityLabel("Activate \(entry.heroScene)")
        .accessibilityHint("Double tap to activate this scene")
    }

    private var heroContent: some View {
        VStack(spacing: 8) {
            Text(heroIcon)
                .font(.system(size: 40))
                .accessibilityHidden(true)

            Text(entry.heroScene)
                .font(.headline)
                .foregroundColor(.white)
                .multilineTextAlignment(.center)

            Text("Tap to activate")
                .font(.caption2)
                .foregroundColor(.gray)
                .accessibilityHidden(true)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

// MARK: - Widget 5: Lock Screen Safety (Accessory)

struct SafetyAccessoryWidget: Widget {
    let kind: String = "SafetyAccessoryWidget"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: KagamiTimelineProvider()) { entry in
            SafetyAccessoryWidgetView(entry: entry)
                .containerBackground(.clear, for: .widget)
        }
        .configurationDisplayName("Safety Indicator")
        .description("Lock screen safety score")
        .supportedFamilies([.accessoryCircular, .accessoryRectangular, .accessoryInline])
    }
}

struct SafetyAccessoryWidgetView: View {
    @Environment(\.widgetFamily) var family
    let entry: KagamiEntry

    private var safetyStatusText: String {
        let score = Int(entry.safetyScore * 100)
        if entry.safetyScore >= 0.5 {
            return "All systems normal, safety score \(score) percent"
        } else if entry.safetyScore >= 0 {
            return "Attention needed, safety score \(score) percent"
        } else {
            return "Safety alert, score \(score) percent"
        }
    }

    var body: some View {
        switch family {
        case .accessoryCircular:
            Gauge(value: entry.safetyScore) {
                Text("鏡")
                    .accessibilityHidden(true)
            }
            .gaugeStyle(.accessoryCircular)
            .accessibilityElement(children: .ignore)
            .accessibilityLabel("Kagami safety score")
            .accessibilityValue("\(Int(entry.safetyScore * 100)) percent")

        case .accessoryRectangular:
            HStack {
                Text("鏡")
                    .font(.headline)
                    .accessibilityHidden(true)
                VStack(alignment: .leading) {
                    Text("Safe \(String(format: "%.0f", entry.safetyScore * 100))")
                        .font(.headline)
                    Text(entry.heroScene)
                        .font(.caption)
                        .foregroundColor(.gray)
                }
            }
            .accessibilityElement(children: .combine)
            .accessibilityLabel("Kagami: \(safetyStatusText). Current scene: \(entry.heroScene)")

        case .accessoryInline:
            Text("鏡 \(String(format: "%.0f", entry.safetyScore * 100)) | \(entry.heroScene)")
                .accessibilityLabel("Kagami safety \(Int(entry.safetyScore * 100)) percent, \(entry.heroScene)")

        default:
            Text("鏡")
                .accessibilityLabel("Kagami")
        }
    }
}

// MARK: - Color Extension
// Note: Color.init(hex:) is defined in KagamiIOS/DesignTokens.generated.swift
// Widget extensions cannot share code with main app, so we define locally here.

private extension Color {
    init(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let a, r, g, b: UInt64
        switch hex.count {
        case 3:
            (a, r, g, b) = (255, (int >> 8) * 17, (int >> 4 & 0xF) * 17, (int & 0xF) * 17)
        case 6:
            (a, r, g, b) = (255, int >> 16, int >> 8 & 0xFF, int & 0xFF)
        case 8:
            (a, r, g, b) = (int >> 24, int >> 16 & 0xFF, int >> 8 & 0xFF, int & 0xFF)
        default:
            (a, r, g, b) = (255, 0, 0, 0)
        }
        self.init(
            .sRGB,
            red: Double(r) / 255,
            green: Double(g) / 255,
            blue: Double(b) / 255,
            opacity: Double(a) / 255
        )
    }
}

// MARK: - Widget 6: Configurable Favorite Scenes

/// App Intent for selecting favorite scenes
struct SelectSceneIntent: WidgetConfigurationIntent {
    static var title: LocalizedStringResource = "Select Scenes"
    static var description: IntentDescription = "Choose your favorite scenes to display"

    @Parameter(title: "Scene 1")
    var scene1: SceneOption?

    @Parameter(title: "Scene 2")
    var scene2: SceneOption?

    @Parameter(title: "Scene 3")
    var scene3: SceneOption?

    @Parameter(title: "Scene 4")
    var scene4: SceneOption?
}

/// Scene options for widget configuration
struct SceneOption: AppEntity {
    let id: String
    let name: String
    let icon: String

    static var typeDisplayRepresentation = TypeDisplayRepresentation(name: "Scene")

    var displayRepresentation: DisplayRepresentation {
        DisplayRepresentation(title: "\(icon) \(name)")
    }

    static var defaultQuery = SceneQuery()

    static let allScenes: [SceneOption] = [
        SceneOption(id: "movie_mode", name: "Movie Mode", icon: "🎬"),
        SceneOption(id: "goodnight", name: "Goodnight", icon: "🌙"),
        SceneOption(id: "welcome_home", name: "Welcome Home", icon: "🏡"),
        SceneOption(id: "away", name: "Away Mode", icon: "🔒"),
        SceneOption(id: "focus", name: "Focus", icon: "🎯"),
        SceneOption(id: "relax", name: "Relax", icon: "🧘"),
        SceneOption(id: "coffee", name: "Coffee Time", icon: "☕"),
        SceneOption(id: "morning", name: "Good Morning", icon: "☀️"),
    ]
}

struct SceneQuery: EntityQuery {
    func entities(for identifiers: [String]) async throws -> [SceneOption] {
        SceneOption.allScenes.filter { identifiers.contains($0.id) }
    }

    func suggestedEntities() async throws -> [SceneOption] {
        SceneOption.allScenes
    }

    func defaultResult() async -> SceneOption? {
        SceneOption.allScenes.first
    }
}

struct ConfigurableScenesWidget: Widget {
    let kind: String = "ConfigurableScenesWidget"

    var body: some WidgetConfiguration {
        AppIntentConfiguration(
            kind: kind,
            intent: SelectSceneIntent.self,
            provider: ConfigurableScenesProvider()
        ) { entry in
            ConfigurableScenesView(entry: entry)
                .containerBackground(.black, for: .widget)
        }
        .configurationDisplayName("Favorite Scenes")
        .description("Customize your quick-access scenes")
        .supportedFamilies([.systemMedium])
    }
}

struct ConfigurableScenesEntry: TimelineEntry {
    let date: Date
    let scenes: [SceneOption]
    let safetyScore: Double
}

struct ConfigurableScenesProvider: AppIntentTimelineProvider {
    func placeholder(in context: Context) -> ConfigurableScenesEntry {
        ConfigurableScenesEntry(
            date: Date(),
            scenes: Array(SceneOption.allScenes.prefix(4)),
            safetyScore: 0.85
        )
    }

    func snapshot(for configuration: SelectSceneIntent, in context: Context) async -> ConfigurableScenesEntry {
        let scenes = [configuration.scene1, configuration.scene2, configuration.scene3, configuration.scene4]
            .compactMap { $0 }

        return ConfigurableScenesEntry(
            date: Date(),
            scenes: scenes.isEmpty ? Array(SceneOption.allScenes.prefix(4)) : scenes,
            safetyScore: 0.85
        )
    }

    func timeline(for configuration: SelectSceneIntent, in context: Context) async -> Timeline<ConfigurableScenesEntry> {
        let scenes = [configuration.scene1, configuration.scene2, configuration.scene3, configuration.scene4]
            .compactMap { $0 }

        let entry = ConfigurableScenesEntry(
            date: Date(),
            scenes: scenes.isEmpty ? Array(SceneOption.allScenes.prefix(4)) : scenes,
            safetyScore: 0.85
        )

        return Timeline(entries: [entry], policy: .after(Date().addingTimeInterval(60 * 15)))
    }
}

struct ConfigurableScenesView: View {
    let entry: ConfigurableScenesEntry

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("鏡")
                    .font(.headline)
                    .foregroundColor(Color(hex: "67d4e4"))
                    .accessibilityLabel("Kagami")
                Text("Favorites")
                    .font(.headline)
                    .foregroundColor(.white)
                Spacer()
                Text(String(format: "Safe %.0f", entry.safetyScore * 100))
                    .font(.caption)
                    .foregroundColor(Color(hex: "00ff88"))
            }
            .accessibilityElement(children: .combine)

            HStack(spacing: 12) {
                ForEach(entry.scenes, id: \.id) { scene in
                    if let url = URL(string: "kagami://scene/\(scene.id)") {
                        Link(destination: url) {
                            VStack(spacing: 4) {
                                Text(scene.icon)
                                    .font(.title2)
                                    .accessibilityHidden(true)
                                Text(scene.name)
                                    .font(.caption2)
                                    .foregroundColor(.gray)
                                    .lineLimit(1)
                            }
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 8)
                            .background(Color.white.opacity(0.1))
                            .cornerRadius(12)
                        }
                        .accessibilityLabel("Activate \(scene.name)")
                    }
                }
            }
        }
        .padding()
    }
}

// MARK: - Widget 7: Configurable Favorite Rooms

/// App Intent for selecting favorite rooms
struct SelectRoomsIntent: WidgetConfigurationIntent {
    static var title: LocalizedStringResource = "Select Rooms"
    static var description: IntentDescription = "Choose your favorite rooms to display"

    @Parameter(title: "Room 1")
    var room1: RoomOption?

    @Parameter(title: "Room 2")
    var room2: RoomOption?

    @Parameter(title: "Room 3")
    var room3: RoomOption?

    @Parameter(title: "Room 4")
    var room4: RoomOption?
}

/// Room options for widget configuration
struct RoomOption: AppEntity {
    let id: String
    let name: String

    static var typeDisplayRepresentation = TypeDisplayRepresentation(name: "Room")

    var displayRepresentation: DisplayRepresentation {
        DisplayRepresentation(title: "\(name)")
    }

    static var defaultQuery = RoomQuery()

    static let allRooms: [RoomOption] = [
        RoomOption(id: "57", name: "Living Room"),
        RoomOption(id: "59", name: "Kitchen"),
        RoomOption(id: "47", name: "Office"),
        RoomOption(id: "36", name: "Primary Bedroom"),
        RoomOption(id: "38", name: "Guest Bedroom"),
        RoomOption(id: "42", name: "Media Room"),
        RoomOption(id: "45", name: "Dining Room"),
        RoomOption(id: "50", name: "Entry"),
    ]
}

struct RoomQuery: EntityQuery {
    func entities(for identifiers: [String]) async throws -> [RoomOption] {
        RoomOption.allRooms.filter { identifiers.contains($0.id) }
    }

    func suggestedEntities() async throws -> [RoomOption] {
        RoomOption.allRooms
    }

    func defaultResult() async -> RoomOption? {
        RoomOption.allRooms.first
    }
}

struct ConfigurableRoomsWidget: Widget {
    let kind: String = "ConfigurableRoomsWidget"

    var body: some WidgetConfiguration {
        AppIntentConfiguration(
            kind: kind,
            intent: SelectRoomsIntent.self,
            provider: ConfigurableRoomsProvider()
        ) { entry in
            ConfigurableRoomsView(entry: entry)
                .containerBackground(.black, for: .widget)
        }
        .configurationDisplayName("Favorite Rooms")
        .description("Customize your quick-access rooms")
        .supportedFamilies([.systemMedium, .systemLarge])
    }
}

struct ConfigurableRoomsEntry: TimelineEntry {
    let date: Date
    let rooms: [ConfigurableRoom]
}

struct ConfigurableRoom: Identifiable {
    let id: String
    let name: String
    let lightLevel: Int
    let isOccupied: Bool
}

struct ConfigurableRoomsProvider: AppIntentTimelineProvider {
    func placeholder(in context: Context) -> ConfigurableRoomsEntry {
        ConfigurableRoomsEntry(
            date: Date(),
            rooms: [
                ConfigurableRoom(id: "57", name: "Living Room", lightLevel: 75, isOccupied: true),
                ConfigurableRoom(id: "47", name: "Office", lightLevel: 80, isOccupied: true),
                ConfigurableRoom(id: "59", name: "Kitchen", lightLevel: 0, isOccupied: false),
                ConfigurableRoom(id: "36", name: "Primary Bedroom", lightLevel: 0, isOccupied: false),
            ]
        )
    }

    func snapshot(for configuration: SelectRoomsIntent, in context: Context) async -> ConfigurableRoomsEntry {
        let selectedRooms = [configuration.room1, configuration.room2, configuration.room3, configuration.room4]
            .compactMap { $0 }

        let rooms = selectedRooms.isEmpty ?
            Array(RoomOption.allRooms.prefix(4)) : selectedRooms

        return ConfigurableRoomsEntry(
            date: Date(),
            rooms: rooms.map { room in
                ConfigurableRoom(
                    id: room.id,
                    name: room.name,
                    lightLevel: Int.random(in: 0...100),
                    isOccupied: Bool.random()
                )
            }
        )
    }

    func timeline(for configuration: SelectRoomsIntent, in context: Context) async -> Timeline<ConfigurableRoomsEntry> {
        let selectedRooms = [configuration.room1, configuration.room2, configuration.room3, configuration.room4]
            .compactMap { $0 }

        let rooms = selectedRooms.isEmpty ?
            Array(RoomOption.allRooms.prefix(4)) : selectedRooms

        // In production, fetch actual room status from API
        let entry = ConfigurableRoomsEntry(
            date: Date(),
            rooms: rooms.map { room in
                ConfigurableRoom(
                    id: room.id,
                    name: room.name,
                    lightLevel: 50, // Placeholder - would fetch from API
                    isOccupied: false
                )
            }
        )

        return Timeline(entries: [entry], policy: .after(Date().addingTimeInterval(60 * 15)))
    }
}

struct ConfigurableRoomsView: View {
    @Environment(\.widgetFamily) var family
    let entry: ConfigurableRoomsEntry

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("鏡")
                    .font(.headline)
                    .foregroundColor(Color(hex: "67d4e4"))
                    .accessibilityLabel("Kagami")
                Text("Rooms")
                    .font(.headline)
                    .foregroundColor(.white)
                Spacer()
                Text(entry.date.formatted(date: .omitted, time: .shortened))
                    .font(.caption)
                    .foregroundColor(.gray)
            }
            .accessibilityElement(children: .combine)

            if family == .systemLarge {
                LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 8) {
                    ForEach(entry.rooms) { room in
                        ConfigurableRoomCell(room: room)
                    }
                }
            } else {
                HStack(spacing: 8) {
                    ForEach(entry.rooms) { room in
                        ConfigurableRoomCell(room: room)
                    }
                }
            }
        }
        .padding()
    }
}

struct ConfigurableRoomCell: View {
    let room: ConfigurableRoom

    private var accessibilityDescription: String {
        var description = "\(room.name), lights at \(room.lightLevel) percent"
        if room.isOccupied {
            description += ", occupied"
        }
        return description
    }

    var body: some View {
        Group {
            if let url = URL(string: "kagami://room/\(room.id)") {
                Link(destination: url) {
                    configurableRoomContent
                }
            } else {
                configurableRoomContent
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel(accessibilityDescription)
        .accessibilityHint("Tap to control \(room.name)")
    }

    private var configurableRoomContent: some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text(room.name)
                    .font(.caption)
                    .foregroundColor(.white)
                    .lineLimit(1)

                HStack(spacing: 4) {
                    Image(systemName: room.lightLevel > 0 ? "lightbulb.fill" : "lightbulb")
                        .font(.caption2)
                        .foregroundColor(room.lightLevel > 0 ? .yellow : .gray)
                        .accessibilityHidden(true)

                    Text("\(room.lightLevel)%")
                        .font(.caption2)
                        .foregroundColor(.gray)
                        .accessibilityHidden(true)
                }
            }

            Spacer()

            if room.isOccupied {
                Circle()
                    .fill(Color(hex: "00ff88"))
                    .frame(width: 8, height: 8)
                    .accessibilityHidden(true)
            }
        }
        .padding(8)
        .background(Color.white.opacity(0.05))
        .cornerRadius(8)
    }
}

// MARK: - Widget 8: Ambient Status (Medium/Large)

/// Ambient status showing weather, next meeting, and home overview
struct AmbientStatusWidget: Widget {
    let kind: String = "AmbientStatusWidget"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: AmbientStatusProvider()) { entry in
            AmbientStatusWidgetView(entry: entry)
                .containerBackground(.black, for: .widget)
        }
        .configurationDisplayName("Ambient Status")
        .description("Weather, calendar, and home status at a glance")
        .supportedFamilies([.systemMedium, .systemLarge])
    }
}

// MARK: - Ambient Status Data Models

struct AmbientStatusEntry: TimelineEntry {
    let date: Date
    let weather: WeatherData
    let nextMeeting: MeetingData?
    let homeStatus: HomeStatusData
    let safetyScore: Double
}

struct WeatherData {
    let temperature: Int
    let condition: WeatherCondition
    let high: Int
    let low: Int
    let humidity: Int

    enum WeatherCondition: String {
        case sunny = "sun.max.fill"
        case partlyCloudy = "cloud.sun.fill"
        case cloudy = "cloud.fill"
        case rainy = "cloud.rain.fill"
        case stormy = "cloud.bolt.rain.fill"
        case snowy = "cloud.snow.fill"
        case foggy = "cloud.fog.fill"
        case clear = "moon.stars.fill"

        var description: String {
            switch self {
            case .sunny: return "Sunny"
            case .partlyCloudy: return "Partly Cloudy"
            case .cloudy: return "Cloudy"
            case .rainy: return "Rainy"
            case .stormy: return "Stormy"
            case .snowy: return "Snowy"
            case .foggy: return "Foggy"
            case .clear: return "Clear"
            }
        }
    }
}

struct MeetingData {
    let title: String
    let startTime: Date
    let duration: TimeInterval
    let isAllDay: Bool

    var timeUntil: String {
        let interval = startTime.timeIntervalSince(Date())
        if interval < 0 {
            return "Now"
        } else if interval < 3600 {
            let minutes = Int(interval / 60)
            return "in \(minutes)m"
        } else if interval < 86400 {
            let hours = Int(interval / 3600)
            return "in \(hours)h"
        } else {
            return startTime.formatted(date: .abbreviated, time: .omitted)
        }
    }
}

struct HomeStatusData {
    let lightsOn: Int
    let totalLights: Int
    let shadesOpen: Int
    let totalShades: Int
    let doorsLocked: Bool
    let temperature: Int?
    let occupiedRooms: [String]
}

// MARK: - Ambient Status Provider

struct AmbientStatusProvider: TimelineProvider {
    func placeholder(in context: Context) -> AmbientStatusEntry {
        AmbientStatusEntry(
            date: Date(),
            weather: WeatherData(
                temperature: 68,
                condition: .partlyCloudy,
                high: 72,
                low: 58,
                humidity: 45
            ),
            nextMeeting: MeetingData(
                title: "Team Standup",
                startTime: Date().addingTimeInterval(3600),
                duration: 1800,
                isAllDay: false
            ),
            homeStatus: HomeStatusData(
                lightsOn: 3,
                totalLights: 41,
                shadesOpen: 5,
                totalShades: 11,
                doorsLocked: true,
                temperature: 72,
                occupiedRooms: ["Office", "Living Room"]
            ),
            safetyScore: 0.85
        )
    }

    func getSnapshot(in context: Context, completion: @escaping (AmbientStatusEntry) -> Void) {
        completion(placeholder(in: context))
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<AmbientStatusEntry>) -> Void) {
        Task {
            let entry = await fetchAmbientStatus()
            // Refresh every 15 minutes
            let timeline = Timeline(entries: [entry], policy: .after(Date().addingTimeInterval(60 * 15)))
            completion(timeline)
        }
    }

    private func fetchAmbientStatus() async -> AmbientStatusEntry {
        // In production, this would fetch from weather API, calendar, and home API
        // For now, return contextual demo data based on time of day

        let hour = Calendar.current.component(.hour, from: Date())
        let isNight = hour < 6 || hour >= 20

        let weather = WeatherData(
            temperature: isNight ? 52 : 68,
            condition: isNight ? .clear : .partlyCloudy,
            high: 72,
            low: 48,
            humidity: isNight ? 65 : 45
        )

        let nextMeeting: MeetingData?
        if hour >= 9 && hour < 17 {
            nextMeeting = MeetingData(
                title: "Design Review",
                startTime: Date().addingTimeInterval(Double.random(in: 1800...7200)),
                duration: 3600,
                isAllDay: false
            )
        } else {
            nextMeeting = nil
        }

        let homeStatus = HomeStatusData(
            lightsOn: isNight ? 5 : 2,
            totalLights: 41,
            shadesOpen: isNight ? 0 : 8,
            totalShades: 11,
            doorsLocked: true,
            temperature: 72,
            occupiedRooms: isNight ? ["Primary Bedroom"] : ["Office", "Living Room"]
        )

        return AmbientStatusEntry(
            date: Date(),
            weather: weather,
            nextMeeting: nextMeeting,
            homeStatus: homeStatus,
            safetyScore: 0.92
        )
    }
}

// MARK: - Ambient Status Widget View

struct AmbientStatusWidgetView: View {
    @Environment(\.widgetFamily) var family
    let entry: AmbientStatusEntry

    var body: some View {
        switch family {
        case .systemMedium:
            mediumView
        case .systemLarge:
            largeView
        default:
            mediumView
        }
    }

    // MARK: - Medium Widget View

    private var mediumView: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Header with time and safety
            headerRow

            // Main content row
            HStack(spacing: 16) {
                // Weather
                weatherCard
                    .frame(maxWidth: .infinity)

                // Divider
                Rectangle()
                    .fill(Color.white.opacity(0.1))
                    .frame(width: 1)

                // Home status
                homeStatusCard
                    .frame(maxWidth: .infinity)
            }
        }
        .padding()
    }

    // MARK: - Large Widget View

    private var largeView: some View {
        VStack(alignment: .leading, spacing: 16) {
            // Header
            headerRow

            // Weather section
            HStack(spacing: 12) {
                weatherDetailCard
                    .frame(maxWidth: .infinity)
            }

            // Calendar section
            if let meeting = entry.nextMeeting {
                meetingCard(meeting)
            } else {
                noMeetingCard
            }

            // Home status section
            homeStatusDetailCard
        }
        .padding()
    }

    // MARK: - Component Views

    private var headerRow: some View {
        HStack {
            Text("鏡")
                .font(.headline)
                .foregroundColor(Color(hex: "67d4e4"))
                .accessibilityLabel("Kagami")

            Text(entry.date.formatted(date: .abbreviated, time: .shortened))
                .font(.caption)
                .foregroundColor(.gray)

            Spacer()

            // Safety indicator
            HStack(spacing: 4) {
                Circle()
                    .fill(safetyColor)
                    .frame(width: 8, height: 8)
                Text("Safe \(Int(entry.safetyScore * 100))")
                    .font(.caption2)
                    .foregroundColor(safetyColor)
            }
            .accessibilityElement(children: .combine)
            .accessibilityLabel("Safety score \(Int(entry.safetyScore * 100)) percent")
        }
    }

    private var weatherCard: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 8) {
                Image(systemName: entry.weather.condition.rawValue)
                    .font(.title2)
                    .foregroundColor(.yellow)
                    .accessibilityHidden(true)

                Text("\(entry.weather.temperature)°")
                    .font(.system(size: 32, weight: .medium, design: .rounded))
                    .foregroundColor(.white)
            }

            Text(entry.weather.condition.description)
                .font(.caption)
                .foregroundColor(.gray)

            Text("H:\(entry.weather.high)° L:\(entry.weather.low)°")
                .font(.caption2)
                .foregroundColor(.gray)
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(entry.weather.temperature) degrees, \(entry.weather.condition.description), high \(entry.weather.high), low \(entry.weather.low)")
    }

    private var weatherDetailCard: some View {
        HStack(spacing: 16) {
            // Main temp
            VStack(alignment: .leading, spacing: 4) {
                HStack(spacing: 8) {
                    Image(systemName: entry.weather.condition.rawValue)
                        .font(.largeTitle)
                        .foregroundColor(.yellow)
                        .accessibilityHidden(true)

                    Text("\(entry.weather.temperature)°")
                        .font(.system(size: 48, weight: .medium, design: .rounded))
                        .foregroundColor(.white)
                }

                Text(entry.weather.condition.description)
                    .font(.subheadline)
                    .foregroundColor(.gray)
            }

            Spacer()

            // Details
            VStack(alignment: .trailing, spacing: 8) {
                HStack(spacing: 4) {
                    Image(systemName: "arrow.up")
                        .font(.caption2)
                        .accessibilityHidden(true)
                    Text("\(entry.weather.high)°")
                        .font(.caption)
                }
                .foregroundColor(.orange)

                HStack(spacing: 4) {
                    Image(systemName: "arrow.down")
                        .font(.caption2)
                        .accessibilityHidden(true)
                    Text("\(entry.weather.low)°")
                        .font(.caption)
                }
                .foregroundColor(.cyan)

                HStack(spacing: 4) {
                    Image(systemName: "humidity.fill")
                        .font(.caption2)
                        .accessibilityHidden(true)
                    Text("\(entry.weather.humidity)%")
                        .font(.caption)
                }
                .foregroundColor(.blue)
            }
        }
        .padding()
        .background(Color.white.opacity(0.05))
        .cornerRadius(12)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Weather: \(entry.weather.temperature) degrees, \(entry.weather.condition.description), high \(entry.weather.high), low \(entry.weather.low), humidity \(entry.weather.humidity) percent")
    }

    private func meetingCard(_ meeting: MeetingData) -> some View {
        HStack(spacing: 12) {
            Image(systemName: "calendar")
                .font(.title3)
                .foregroundColor(Color(hex: "67d4e4"))
                .accessibilityHidden(true)

            VStack(alignment: .leading, spacing: 2) {
                Text(meeting.title)
                    .font(.subheadline)
                    .fontWeight(.medium)
                    .foregroundColor(.white)
                    .lineLimit(1)

                Text(meeting.timeUntil)
                    .font(.caption)
                    .foregroundColor(Color(hex: "67d4e4"))
            }

            Spacer()

            if let url = URL(string: "kagami://calendar") {
                Link(destination: url) {
                    Image(systemName: "chevron.right")
                        .font(.caption)
                        .foregroundColor(.gray)
                }
            }
        }
        .padding()
        .background(Color.white.opacity(0.05))
        .cornerRadius(12)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Next meeting: \(meeting.title), \(meeting.timeUntil)")
    }

    private var noMeetingCard: some View {
        HStack(spacing: 12) {
            Image(systemName: "calendar")
                .font(.title3)
                .foregroundColor(.gray)
                .accessibilityHidden(true)

            Text("No upcoming meetings")
                .font(.subheadline)
                .foregroundColor(.gray)

            Spacer()
        }
        .padding()
        .background(Color.white.opacity(0.05))
        .cornerRadius(12)
        .accessibilityLabel("No upcoming meetings")
    }

    private var homeStatusCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            // Lights
            HStack(spacing: 4) {
                Image(systemName: entry.homeStatus.lightsOn > 0 ? "lightbulb.fill" : "lightbulb")
                    .font(.caption)
                    .foregroundColor(entry.homeStatus.lightsOn > 0 ? .yellow : .gray)
                    .accessibilityHidden(true)
                Text("\(entry.homeStatus.lightsOn)/\(entry.homeStatus.totalLights)")
                    .font(.caption)
                    .foregroundColor(.white)
            }

            // Lock status
            HStack(spacing: 4) {
                Image(systemName: entry.homeStatus.doorsLocked ? "lock.fill" : "lock.open")
                    .font(.caption)
                    .foregroundColor(entry.homeStatus.doorsLocked ? Color(hex: "00ff88") : .orange)
                    .accessibilityHidden(true)
                Text(entry.homeStatus.doorsLocked ? "Locked" : "Unlocked")
                    .font(.caption)
                    .foregroundColor(.white)
            }

            // Temperature
            if let temp = entry.homeStatus.temperature {
                HStack(spacing: 4) {
                    Image(systemName: "thermometer.medium")
                        .font(.caption)
                        .foregroundColor(.cyan)
                        .accessibilityHidden(true)
                    Text("\(temp)°")
                        .font(.caption)
                        .foregroundColor(.white)
                }
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Home status: \(entry.homeStatus.lightsOn) lights on, doors \(entry.homeStatus.doorsLocked ? "locked" : "unlocked")\(entry.homeStatus.temperature != nil ? ", \(entry.homeStatus.temperature!)degrees" : "")")
    }

    private var homeStatusDetailCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Home Status")
                .font(.caption)
                .fontWeight(.medium)
                .foregroundColor(.gray)

            HStack(spacing: 16) {
                // Lights
                statusPill(
                    icon: entry.homeStatus.lightsOn > 0 ? "lightbulb.fill" : "lightbulb",
                    value: "\(entry.homeStatus.lightsOn)",
                    label: "lights",
                    color: entry.homeStatus.lightsOn > 0 ? .yellow : .gray
                )

                // Shades
                statusPill(
                    icon: entry.homeStatus.shadesOpen > 0 ? "blinds.horizontal.open" : "blinds.horizontal.closed",
                    value: "\(entry.homeStatus.shadesOpen)",
                    label: "shades",
                    color: entry.homeStatus.shadesOpen > 0 ? .cyan : .gray
                )

                // Locks
                statusPill(
                    icon: entry.homeStatus.doorsLocked ? "lock.fill" : "lock.open",
                    value: entry.homeStatus.doorsLocked ? "Secure" : "Open",
                    label: "",
                    color: entry.homeStatus.doorsLocked ? Color(hex: "00ff88") : .orange
                )

                // Temperature
                if let temp = entry.homeStatus.temperature {
                    statusPill(
                        icon: "thermometer.medium",
                        value: "\(temp)°",
                        label: "",
                        color: .cyan
                    )
                }
            }

            // Occupied rooms
            if !entry.homeStatus.occupiedRooms.isEmpty {
                HStack(spacing: 4) {
                    Image(systemName: "person.fill")
                        .font(.caption2)
                        .foregroundColor(Color(hex: "00ff88"))
                        .accessibilityHidden(true)
                    Text(entry.homeStatus.occupiedRooms.joined(separator: ", "))
                        .font(.caption2)
                        .foregroundColor(.gray)
                        .lineLimit(1)
                }
            }
        }
        .padding()
        .background(Color.white.opacity(0.05))
        .cornerRadius(12)
    }

    private func statusPill(icon: String, value: String, label: String, color: Color) -> some View {
        VStack(spacing: 4) {
            Image(systemName: icon)
                .font(.title3)
                .foregroundColor(color)
                .accessibilityHidden(true)
            Text(value)
                .font(.caption)
                .fontWeight(.medium)
                .foregroundColor(.white)
            if !label.isEmpty {
                Text(label)
                    .font(.caption2)
                    .foregroundColor(.gray)
            }
        }
        .frame(maxWidth: .infinity)
    }

    private var safetyColor: Color {
        if entry.safetyScore >= 0.5 { return Color(hex: "00ff88") }
        if entry.safetyScore >= 0 { return Color(hex: "ffd700") }
        return Color(hex: "ff4444")
    }
}

// MARK: - Ambient Status Preview

#if DEBUG
struct AmbientStatusWidget_Previews: PreviewProvider {
    static var previews: some View {
        AmbientStatusWidgetView(entry: AmbientStatusEntry(
            date: Date(),
            weather: WeatherData(
                temperature: 68,
                condition: .partlyCloudy,
                high: 72,
                low: 58,
                humidity: 45
            ),
            nextMeeting: MeetingData(
                title: "Design Review",
                startTime: Date().addingTimeInterval(3600),
                duration: 3600,
                isAllDay: false
            ),
            homeStatus: HomeStatusData(
                lightsOn: 3,
                totalLights: 41,
                shadesOpen: 5,
                totalShades: 11,
                doorsLocked: true,
                temperature: 72,
                occupiedRooms: ["Office", "Living Room"]
            ),
            safetyScore: 0.92
        ))
        .previewContext(WidgetPreviewContext(family: .systemMedium))
        .containerBackground(.black, for: .widget)
    }
}
#endif

// MARK: - Live Activity Support

/// Attributes for Kagami Live Activities
struct KagamiActivityAttributes: ActivityAttributes {
    /// Static context that doesn't change during the activity
    public struct ContentState: Codable, Hashable {
        /// Current scene name
        var sceneName: String

        /// Progress (0.0 - 1.0) for timed activities
        var progress: Double

        /// Time remaining in seconds (for timers)
        var timeRemaining: TimeInterval?

        /// Status message
        var statusMessage: String

        /// Safety score
        var safetyScore: Double

        /// Activity type
        var activityType: ActivityType

        enum ActivityType: String, Codable, Hashable {
            case sceneTransition = "scene"
            case timer = "timer"
            case focusSession = "focus"
            case sleepTimer = "sleep"
            case cooking = "cooking"
        }
    }

    /// Name of the activity (static, doesn't change)
    var activityName: String

    /// Icon for the activity
    var activityIcon: String
}

/// Live Activity Widget for Kagami
struct KagamiLiveActivityWidget: Widget {
    var body: some WidgetConfiguration {
        ActivityConfiguration(for: KagamiActivityAttributes.self) { context in
            // Lock screen banner
            KagamiLiveActivityView(context: context)
                .activityBackgroundTint(Color.black.opacity(0.8))
                .activitySystemActionForegroundColor(.white)
        } dynamicIsland: { context in
            DynamicIsland {
                // Expanded leading region
                DynamicIslandExpandedRegion(.leading) {
                    HStack(spacing: 8) {
                        Text("鏡")
                            .font(.headline)
                            .foregroundColor(Color(hex: "67d4e4"))
                        Text(context.attributes.activityName)
                            .font(.caption)
                            .foregroundColor(.white)
                    }
                }

                // Expanded trailing region
                DynamicIslandExpandedRegion(.trailing) {
                    if let timeRemaining = context.state.timeRemaining {
                        Text(formatTimeRemaining(timeRemaining))
                            .font(.system(.headline, design: .monospaced))
                            .foregroundColor(Color(hex: "67d4e4"))
                    } else {
                        Text("\(Int(context.state.progress * 100))%")
                            .font(.headline)
                            .foregroundColor(Color(hex: "00ff88"))
                    }
                }

                // Expanded center region
                DynamicIslandExpandedRegion(.center) {
                    VStack(spacing: 4) {
                        Text(context.state.sceneName)
                            .font(.subheadline)
                            .fontWeight(.medium)
                            .foregroundColor(.white)

                        ProgressView(value: context.state.progress)
                            .tint(activityColor(for: context.state.activityType))
                    }
                }

                // Expanded bottom region
                DynamicIslandExpandedRegion(.bottom) {
                    Text(context.state.statusMessage)
                        .font(.caption)
                        .foregroundColor(.gray)
                }
            } compactLeading: {
                // Compact leading (small pill view)
                Image(systemName: context.attributes.activityIcon)
                    .font(.caption)
                    .foregroundColor(activityColor(for: context.state.activityType))
            } compactTrailing: {
                // Compact trailing (small pill view)
                if let timeRemaining = context.state.timeRemaining {
                    Text(formatTimeRemainingCompact(timeRemaining))
                        .font(.caption2)
                        .fontWeight(.medium)
                        .foregroundColor(.white)
                } else {
                    Text("\(Int(context.state.progress * 100))%")
                        .font(.caption2)
                        .fontWeight(.medium)
                        .foregroundColor(Color(hex: "00ff88"))
                }
            } minimal: {
                // Minimal (circle indicator)
                Image(systemName: context.attributes.activityIcon)
                    .font(.caption2)
                    .foregroundColor(activityColor(for: context.state.activityType))
            }
        }
    }

    private func activityColor(for type: KagamiActivityAttributes.ContentState.ActivityType) -> Color {
        switch type {
        case .sceneTransition: return Color(hex: "67d4e4")  // Crystal
        case .timer: return Color(hex: "ff9500")           // Forge
        case .focusSession: return Color(hex: "5ac8fa")    // Flow
        case .sleepTimer: return Color(hex: "af52de")      // Nexus
        case .cooking: return Color(hex: "ff6b35")         // Spark
        }
    }

    private func formatTimeRemaining(_ seconds: TimeInterval) -> String {
        let minutes = Int(seconds) / 60
        let secs = Int(seconds) % 60
        if minutes >= 60 {
            let hours = minutes / 60
            let mins = minutes % 60
            return String(format: "%d:%02d:%02d", hours, mins, secs)
        }
        return String(format: "%d:%02d", minutes, secs)
    }

    private func formatTimeRemainingCompact(_ seconds: TimeInterval) -> String {
        let minutes = Int(seconds) / 60
        if minutes >= 60 {
            return "\(minutes / 60)h"
        }
        return "\(minutes)m"
    }
}

/// Lock screen banner view for Live Activity
struct KagamiLiveActivityView: View {
    let context: ActivityViewContext<KagamiActivityAttributes>

    var body: some View {
        HStack(spacing: 16) {
            // Leading icon
            VStack {
                Text("鏡")
                    .font(.title2)
                    .foregroundColor(Color(hex: "67d4e4"))

                Image(systemName: context.attributes.activityIcon)
                    .font(.caption)
                    .foregroundColor(.gray)
            }

            // Main content
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text(context.state.sceneName)
                        .font(.headline)
                        .foregroundColor(.white)

                    Spacer()

                    if let timeRemaining = context.state.timeRemaining {
                        Text(formatTimeRemaining(timeRemaining))
                            .font(.system(.subheadline, design: .monospaced))
                            .foregroundColor(Color(hex: "67d4e4"))
                    }
                }

                ProgressView(value: context.state.progress)
                    .tint(activityColor)

                Text(context.state.statusMessage)
                    .font(.caption)
                    .foregroundColor(.gray)
            }

            // Safety indicator
            VStack {
                Circle()
                    .fill(safetyColor)
                    .frame(width: 12, height: 12)

                Text("Safe")
                    .font(.caption2)
                    .foregroundColor(.gray)
            }
        }
        .padding()
        .accessibilityElement(children: .combine)
        .accessibilityLabel(accessibilityDescription)
    }

    private var activityColor: Color {
        switch context.state.activityType {
        case .sceneTransition: return Color(hex: "67d4e4")
        case .timer: return Color(hex: "ff9500")
        case .focusSession: return Color(hex: "5ac8fa")
        case .sleepTimer: return Color(hex: "af52de")
        case .cooking: return Color(hex: "ff6b35")
        }
    }

    private var safetyColor: Color {
        if context.state.safetyScore >= 0.5 { return Color(hex: "00ff88") }
        if context.state.safetyScore >= 0 { return Color(hex: "ffd700") }
        return Color(hex: "ff4444")
    }

    private func formatTimeRemaining(_ seconds: TimeInterval) -> String {
        let minutes = Int(seconds) / 60
        let secs = Int(seconds) % 60
        if minutes >= 60 {
            let hours = minutes / 60
            let mins = minutes % 60
            return String(format: "%d:%02d:%02d", hours, mins, secs)
        }
        return String(format: "%d:%02d", minutes, secs)
    }

    private var accessibilityDescription: String {
        var description = "\(context.state.sceneName), \(Int(context.state.progress * 100)) percent complete"
        if let timeRemaining = context.state.timeRemaining {
            let minutes = Int(timeRemaining / 60)
            description += ", \(minutes) minutes remaining"
        }
        description += ". \(context.state.statusMessage)"
        return description
    }
}

// MARK: - Live Activity Manager

/// Manager for starting and updating Kagami Live Activities
@MainActor
final class KagamiActivityManager {
    static let shared = KagamiActivityManager()

    private var currentActivity: Activity<KagamiActivityAttributes>?

    private init() {}

    /// Start a scene transition activity
    func startSceneActivity(sceneName: String, duration: TimeInterval? = nil) async throws {
        guard ActivityAuthorizationInfo().areActivitiesEnabled else {
            return
        }

        let attributes = KagamiActivityAttributes(
            activityName: sceneName,
            activityIcon: iconForScene(sceneName)
        )

        let initialState = KagamiActivityAttributes.ContentState(
            sceneName: sceneName,
            progress: 0,
            timeRemaining: duration,
            statusMessage: "Activating scene...",
            safetyScore: 0.85,
            activityType: .sceneTransition
        )

        currentActivity = try Activity.request(
            attributes: attributes,
            content: .init(state: initialState, staleDate: nil),
            pushType: nil
        )
    }

    /// Start a focus session activity
    func startFocusSession(duration: TimeInterval, room: String? = nil) async throws {
        guard ActivityAuthorizationInfo().areActivitiesEnabled else {
            return
        }

        let attributes = KagamiActivityAttributes(
            activityName: "Focus Session",
            activityIcon: "brain.head.profile"
        )

        let roomText = room ?? "Home"
        let initialState = KagamiActivityAttributes.ContentState(
            sceneName: "Focus Mode",
            progress: 0,
            timeRemaining: duration,
            statusMessage: "Focusing in \(roomText)",
            safetyScore: 0.90,
            activityType: .focusSession
        )

        currentActivity = try Activity.request(
            attributes: attributes,
            content: .init(state: initialState, staleDate: nil),
            pushType: nil
        )
    }

    /// Start a sleep timer activity
    func startSleepTimer(duration: TimeInterval) async throws {
        guard ActivityAuthorizationInfo().areActivitiesEnabled else {
            return
        }

        let attributes = KagamiActivityAttributes(
            activityName: "Sleep Timer",
            activityIcon: "moon.fill"
        )

        let initialState = KagamiActivityAttributes.ContentState(
            sceneName: "Goodnight",
            progress: 0,
            timeRemaining: duration,
            statusMessage: "Preparing for sleep",
            safetyScore: 0.95,
            activityType: .sleepTimer
        )

        currentActivity = try Activity.request(
            attributes: attributes,
            content: .init(state: initialState, staleDate: nil),
            pushType: nil
        )
    }

    /// Update the current activity
    func updateActivity(
        progress: Double,
        timeRemaining: TimeInterval?,
        statusMessage: String
    ) async {
        guard let activity = currentActivity else { return }

        let updatedState = KagamiActivityAttributes.ContentState(
            sceneName: activity.content.state.sceneName,
            progress: progress,
            timeRemaining: timeRemaining,
            statusMessage: statusMessage,
            safetyScore: activity.content.state.safetyScore,
            activityType: activity.content.state.activityType
        )

        await activity.update(
            ActivityContent(state: updatedState, staleDate: nil)
        )
    }

    /// End the current activity
    func endActivity(finalMessage: String = "Complete") async {
        guard let activity = currentActivity else { return }

        let finalState = KagamiActivityAttributes.ContentState(
            sceneName: activity.content.state.sceneName,
            progress: 1.0,
            timeRemaining: nil,
            statusMessage: finalMessage,
            safetyScore: activity.content.state.safetyScore,
            activityType: activity.content.state.activityType
        )

        await activity.end(
            ActivityContent(state: finalState, staleDate: nil),
            dismissalPolicy: .default
        )

        currentActivity = nil
    }

    private func iconForScene(_ sceneName: String) -> String {
        let lowercased = sceneName.lowercased()
        if lowercased.contains("movie") { return "film" }
        if lowercased.contains("goodnight") || lowercased.contains("sleep") { return "moon.fill" }
        if lowercased.contains("morning") { return "sunrise.fill" }
        if lowercased.contains("focus") { return "brain.head.profile" }
        if lowercased.contains("relax") { return "leaf.fill" }
        if lowercased.contains("welcome") || lowercased.contains("home") { return "house.fill" }
        if lowercased.contains("away") { return "figure.walk.departure" }
        return "sparkles"
    }
}

/*
 * Kagami Widgets
 * Widgets are windows into presence.
 * Live Activities bridge the moment.
 */
