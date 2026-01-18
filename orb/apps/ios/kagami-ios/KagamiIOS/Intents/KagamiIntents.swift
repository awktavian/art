//
// KagamiIntents.swift — App Intents for Siri and Shortcuts
//
// Colony: Nexus (e4) — Integration
//
// Defines AppIntents for smart home scene activation:
//   - MovieModeIntent: Enter movie mode
//   - GoodnightIntent: Goodnight scene
//   - WelcomeHomeIntent: Welcome home scene
//   - SetLightsIntent: Adjust lighting levels
//   - ToggleFireplaceIntent: Toggle fireplace on/off
//
// h(x) >= 0. Always.
//

import AppIntents
import SwiftUI

// MARK: - API Configuration

// Security Note: Production uses HTTPS. Local development requires self-signed certs.
// URL resolution: UserDefaults > Environment > Production default
private let kagamiBaseURL: String = {
    if let saved = UserDefaults.standard.string(forKey: "kagamiServerURL") {
        return saved
    }
    if let env = ProcessInfo.processInfo.environment["KAGAMI_BASE_URL"] {
        return env
    }
    return "https://api.awkronos.com"
}()

private func postToKagami(endpoint: String, body: [String: Any]? = nil) async throws {
    guard let url = URL(string: "\(kagamiBaseURL)\(endpoint)") else {
        throw KagamiIntentError.invalidURL
    }

    var request = URLRequest(url: url)
    request.httpMethod = "POST"
    request.addValue("application/json", forHTTPHeaderField: "Content-Type")
    request.timeoutInterval = 10

    if let body = body {
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)
    }

    let (_, response) = try await URLSession.shared.data(for: request)

    guard let httpResponse = response as? HTTPURLResponse,
          httpResponse.statusCode >= 200 && httpResponse.statusCode < 300 else {
        throw KagamiIntentError.requestFailed
    }
}

enum KagamiIntentError: Error, CustomLocalizedStringResourceConvertible {
    case invalidURL
    case requestFailed
    case notConnected

    var localizedStringResource: LocalizedStringResource {
        switch self {
        case .invalidURL:
            return "Invalid API URL"
        case .requestFailed:
            return "Request failed"
        case .notConnected:
            return "Not connected to Kagami"
        }
    }
}

// MARK: - Movie Mode Intent

struct MovieModeIntent: AppIntent {
    static var title: LocalizedStringResource = "Movie Mode"
    static var description = IntentDescription("Enter movie mode in your smart home")

    static var openAppWhenRun: Bool = false

    @Parameter(title: "Action", default: .enter)
    var action: MovieModeAction

    enum MovieModeAction: String, AppEnum {
        case enter = "enter"
        case exit = "exit"
        case toggle = "toggle"

        static var typeDisplayRepresentation = TypeDisplayRepresentation(name: "Movie Mode Action")

        static var caseDisplayRepresentations: [MovieModeAction: DisplayRepresentation] = [
            .enter: DisplayRepresentation(title: "Enter"),
            .exit: DisplayRepresentation(title: "Exit"),
            .toggle: DisplayRepresentation(title: "Toggle")
        ]
    }

    func perform() async throws -> some IntentResult & ProvidesDialog {
        let endpoint: String
        let message: String

        switch action {
        case .enter:
            endpoint = "/home/movie-mode/enter"
            message = "Movie mode activated. Lights dimmed, TV lowered."
        case .exit:
            endpoint = "/home/movie-mode/exit"
            message = "Movie mode deactivated."
        case .toggle:
            endpoint = "/home/movie-mode/toggle"
            message = "Movie mode toggled."
        }

        try await postToKagami(endpoint: endpoint)

        return .result(dialog: IntentDialog(stringLiteral: message))
    }

    static var parameterSummary: some ParameterSummary {
        Summary("\(\.$action) movie mode")
    }
}

// MARK: - Goodnight Intent

struct GoodnightIntent: AppIntent {
    static var title: LocalizedStringResource = "Goodnight"
    static var description = IntentDescription("Activate goodnight scene - turns off lights, locks doors")

    static var openAppWhenRun: Bool = false

    func perform() async throws -> some IntentResult & ProvidesDialog {
        try await postToKagami(endpoint: "/home/goodnight")
        return .result(dialog: "Goodnight. All lights off, doors locked.")
    }
}

// MARK: - Welcome Home Intent

struct WelcomeHomeIntent: AppIntent {
    static var title: LocalizedStringResource = "Welcome Home"
    static var description = IntentDescription("Activate welcome home scene with warm lighting")

    static var openAppWhenRun: Bool = false

    func perform() async throws -> some IntentResult & ProvidesDialog {
        try await postToKagami(endpoint: "/home/welcome-home")
        return .result(dialog: "Welcome home. Lights adjusted to warm settings.")
    }
}

// MARK: - Set Lights Intent

struct SetLightsIntent: AppIntent {
    static var title: LocalizedStringResource = "Set Lights"
    static var description = IntentDescription("Adjust lighting levels in your home")

    static var openAppWhenRun: Bool = false

    @Parameter(title: "Level", default: 50)
    var level: Int

    @Parameter(title: "Rooms")
    var rooms: [String]?

    func perform() async throws -> some IntentResult & ProvidesDialog {
        let body: [String: Any] = [
            "level": level,
            "rooms": rooms as Any
        ]

        try await postToKagami(endpoint: "/home/lights/set", body: body)

        let roomsText = rooms?.joined(separator: ", ") ?? "all rooms"
        return .result(dialog: "Lights set to \(level)% in \(roomsText).")
    }

    static var parameterSummary: some ParameterSummary {
        Summary("Set lights to \(\.$level)%") {
            \.$rooms
        }
    }
}

// MARK: - Toggle Fireplace Intent

struct ToggleFireplaceIntent: AppIntent {
    static var title: LocalizedStringResource = "Toggle Fireplace"
    static var description = IntentDescription("Turn the fireplace on or off")

    static var openAppWhenRun: Bool = false

    @Parameter(title: "State", default: .toggle)
    var state: FireplaceState

    enum FireplaceState: String, AppEnum {
        case on = "on"
        case off = "off"
        case toggle = "toggle"

        static var typeDisplayRepresentation = TypeDisplayRepresentation(name: "Fireplace State")

        static var caseDisplayRepresentations: [FireplaceState: DisplayRepresentation] = [
            .on: DisplayRepresentation(title: "On"),
            .off: DisplayRepresentation(title: "Off"),
            .toggle: DisplayRepresentation(title: "Toggle")
        ]
    }

    func perform() async throws -> some IntentResult & ProvidesDialog {
        let endpoint: String
        let message: String

        switch state {
        case .on:
            endpoint = "/home/fireplace/on"
            message = "Fireplace turned on."
        case .off:
            endpoint = "/home/fireplace/off"
            message = "Fireplace turned off."
        case .toggle:
            endpoint = "/home/fireplace/toggle"
            message = "Fireplace toggled."
        }

        try await postToKagami(endpoint: endpoint)

        return .result(dialog: IntentDialog(stringLiteral: message))
    }

    static var parameterSummary: some ParameterSummary {
        Summary("Turn fireplace \(\.$state)")
    }
}

// MARK: - Control Shades Intent

struct ControlShadesIntent: AppIntent {
    static var title: LocalizedStringResource = "Control Shades"
    static var description = IntentDescription("Open or close window shades")

    static var openAppWhenRun: Bool = false

    @Parameter(title: "Action", default: .open)
    var action: ShadeAction

    @Parameter(title: "Rooms")
    var rooms: [String]?

    enum ShadeAction: String, AppEnum {
        case open = "open"
        case close = "close"

        static var typeDisplayRepresentation = TypeDisplayRepresentation(name: "Shade Action")

        static var caseDisplayRepresentations: [ShadeAction: DisplayRepresentation] = [
            .open: DisplayRepresentation(title: "Open"),
            .close: DisplayRepresentation(title: "Close")
        ]
    }

    func perform() async throws -> some IntentResult & ProvidesDialog {
        let body: [String: Any] = ["rooms": rooms as Any]
        let endpoint = action == .open ? "/home/shades/open" : "/home/shades/close"

        try await postToKagami(endpoint: endpoint, body: body)

        let roomsText = rooms?.joined(separator: ", ") ?? "all rooms"
        let actionText = action == .open ? "opened" : "closed"
        return .result(dialog: "Shades \(actionText) in \(roomsText).")
    }

    static var parameterSummary: some ParameterSummary {
        Summary("\(\.$action) shades") {
            \.$rooms
        }
    }
}

// MARK: - Lock All Intent

struct LockAllIntent: AppIntent {
    static var title: LocalizedStringResource = "Lock All Doors"
    static var description = IntentDescription("Lock all doors in your home")

    static var openAppWhenRun: Bool = false

    func perform() async throws -> some IntentResult & ProvidesDialog {
        try await postToKagami(endpoint: "/home/locks/lock-all")
        return .result(dialog: "All doors locked.")
    }
}

// MARK: - Get Safety Score Intent

struct GetSafetyScoreIntent: AppIntent {
    static var title: LocalizedStringResource = "Get Safety Score"
    static var description = IntentDescription("Check the current safety status")

    static var openAppWhenRun: Bool = false

    func perform() async throws -> some IntentResult & ProvidesDialog {
        guard let url = URL(string: "\(kagamiBaseURL)/health") else {
            throw KagamiIntentError.invalidURL
        }

        let (data, _) = try await URLSession.shared.data(from: url)

        struct HealthResponse: Codable {
            let status: String
            let h_x: Double?
        }

        let response = try JSONDecoder().decode(HealthResponse.self, from: data)

        if let score = response.h_x {
            let percentage = Int(score * 100)
            let status: String
            if score >= 0.5 {
                status = "Safe"
            } else if score >= 0 {
                status = "Caution"
            } else {
                status = "Warning"
            }

            return .result(dialog: "Safety score is \(percentage)%. Status: \(status).")
        } else {
            return .result(dialog: "Safety score unavailable.")
        }
    }
}

// MARK: - TV Control Intent

struct TVControlIntent: AppIntent {
    static var title: LocalizedStringResource = "TV Control"
    static var description = IntentDescription("Control the TV mount and power")

    static var openAppWhenRun: Bool = false

    @Parameter(title: "Action", default: .lower)
    var action: TVAction

    enum TVAction: String, AppEnum {
        case lower = "lower"
        case raise = "raise"
        case on = "on"
        case off = "off"

        static var typeDisplayRepresentation = TypeDisplayRepresentation(name: "TV Action")

        static var caseDisplayRepresentations: [TVAction: DisplayRepresentation] = [
            .lower: DisplayRepresentation(title: "Lower"),
            .raise: DisplayRepresentation(title: "Raise"),
            .on: DisplayRepresentation(title: "Turn On"),
            .off: DisplayRepresentation(title: "Turn Off")
        ]
    }

    func perform() async throws -> some IntentResult & ProvidesDialog {
        let endpoint: String
        let message: String

        switch action {
        case .lower:
            endpoint = "/home/tv/lower"
            message = "TV lowered to viewing position."
        case .raise:
            endpoint = "/home/tv/raise"
            message = "TV raised to hidden position."
        case .on:
            endpoint = "/home/tv/on"
            message = "TV turned on."
        case .off:
            endpoint = "/home/tv/off"
            message = "TV turned off."
        }

        try await postToKagami(endpoint: endpoint)

        return .result(dialog: IntentDialog(stringLiteral: message))
    }

    static var parameterSummary: some ParameterSummary {
        Summary("\(\.$action) TV")
    }
}

// MARK: - Set Room Temperature Intent

struct SetTemperatureIntent: AppIntent {
    static var title: LocalizedStringResource = "Set Temperature"
    static var description = IntentDescription("Adjust thermostat in a room")

    static var openAppWhenRun: Bool = false

    @Parameter(title: "Room")
    var room: String

    @Parameter(title: "Temperature", default: 72)
    var temperature: Int

    func perform() async throws -> some IntentResult & ProvidesDialog {
        let body: [String: Any] = [
            "room": room,
            "temperature": temperature
        ]

        try await postToKagami(endpoint: "/home/climate/set", body: body)

        return .result(dialog: "Temperature in \(room) set to \(temperature) degrees.")
    }

    static var parameterSummary: some ParameterSummary {
        Summary("Set \(\.$room) to \(\.$temperature) degrees")
    }
}

// MARK: - Announce Intent

struct AnnounceIntent: AppIntent {
    static var title: LocalizedStringResource = "Announce"
    static var description = IntentDescription("Make an announcement through home speakers")

    static var openAppWhenRun: Bool = false

    @Parameter(title: "Message")
    var message: String

    @Parameter(title: "Rooms")
    var rooms: [String]?

    func perform() async throws -> some IntentResult & ProvidesDialog {
        let body: [String: Any] = [
            "message": message,
            "rooms": rooms as Any
        ]

        let endpoint = rooms == nil ? "/home/announce/all" : "/home/announce"
        try await postToKagami(endpoint: endpoint, body: body)

        return .result(dialog: "Announcement sent.")
    }

    static var parameterSummary: some ParameterSummary {
        Summary("Announce \"\(\.$message)\"") {
            \.$rooms
        }
    }
}

// MARK: - Intent Entity: Room

struct RoomEntity: AppEntity {
    var id: String
    var name: String

    static var typeDisplayRepresentation = TypeDisplayRepresentation(name: "Room")

    var displayRepresentation: DisplayRepresentation {
        DisplayRepresentation(title: LocalizedStringResource(stringLiteral: name))
    }

    static var defaultQuery = RoomEntityQuery()
}

struct RoomEntityQuery: EntityQuery {
    func entities(for identifiers: [String]) async throws -> [RoomEntity] {
        // In production, fetch from API
        return knownRooms.filter { identifiers.contains($0.id) }
    }

    func suggestedEntities() async throws -> [RoomEntity] {
        return knownRooms
    }

    // Known rooms from the house
    private var knownRooms: [RoomEntity] {
        [
            RoomEntity(id: "living_room", name: "Living Room"),
            RoomEntity(id: "office", name: "Office"),
            RoomEntity(id: "primary_bedroom", name: "Primary Bedroom"),
            RoomEntity(id: "kitchen", name: "Kitchen"),
            RoomEntity(id: "dining_room", name: "Dining Room"),
            RoomEntity(id: "garage", name: "Garage"),
            RoomEntity(id: "basement", name: "Basement"),
            RoomEntity(id: "guest_bedroom", name: "Guest Bedroom"),
        ]
    }
}

// MARK: - Focus Mode Intent

struct FocusModeIntent: AppIntent {
    static var title: LocalizedStringResource = "Focus Mode"
    static var description = IntentDescription("Activate focus mode with optimal lighting and minimal distractions")

    static var openAppWhenRun: Bool = false

    @Parameter(title: "Duration", default: 60)
    var duration: Int // minutes

    @Parameter(title: "Room")
    var room: String?

    func perform() async throws -> some IntentResult & ProvidesDialog {
        let body: [String: Any] = [
            "duration": duration,
            "room": room as Any
        ]

        try await postToKagami(endpoint: "/home/scenes/focus", body: body)

        let roomText = room ?? "office"
        return .result(dialog: "Focus mode activated in \(roomText) for \(duration) minutes. Optimal lighting set.")
    }

    static var parameterSummary: some ParameterSummary {
        Summary("Start focus mode for \(\.$duration) minutes") {
            \.$room
        }
    }
}

// MARK: - Relax Mode Intent

struct RelaxModeIntent: AppIntent {
    static var title: LocalizedStringResource = "Relax Mode"
    static var description = IntentDescription("Activate relaxation mode with warm ambient lighting")

    static var openAppWhenRun: Bool = false

    @Parameter(title: "Intensity", default: .medium)
    var intensity: RelaxIntensity

    enum RelaxIntensity: String, AppEnum {
        case low = "low"
        case medium = "medium"
        case high = "high"

        static var typeDisplayRepresentation = TypeDisplayRepresentation(name: "Relax Intensity")

        static var caseDisplayRepresentations: [RelaxIntensity: DisplayRepresentation] = [
            .low: DisplayRepresentation(title: "Low (Subtle warmth)"),
            .medium: DisplayRepresentation(title: "Medium (Cozy)"),
            .high: DisplayRepresentation(title: "High (Warm glow)")
        ]
    }

    func perform() async throws -> some IntentResult & ProvidesDialog {
        let lightLevel: Int
        switch intensity {
        case .low: lightLevel = 20
        case .medium: lightLevel = 40
        case .high: lightLevel = 60
        }

        let body: [String: Any] = [
            "level": lightLevel,
            "warmth": true
        ]

        try await postToKagami(endpoint: "/home/scenes/relax", body: body)

        return .result(dialog: "Relax mode activated with \(intensity.rawValue) intensity. Enjoy the warm ambiance.")
    }

    static var parameterSummary: some ParameterSummary {
        Summary("Relax at \(\.$intensity) intensity")
    }
}

// MARK: - Energy Mode Intent

struct EnergyModeIntent: AppIntent {
    static var title: LocalizedStringResource = "Energy Mode"
    static var description = IntentDescription("Activate energizing bright lights for productivity")

    static var openAppWhenRun: Bool = false

    func perform() async throws -> some IntentResult & ProvidesDialog {
        try await postToKagami(endpoint: "/home/scenes/energy")
        return .result(dialog: "Energy mode activated. Bright, cool lighting engaged.")
    }
}

// MARK: - Ambient Music Intent

struct AmbientMusicIntent: AppIntent {
    static var title: LocalizedStringResource = "Ambient Music"
    static var description = IntentDescription("Play ambient music throughout the home")

    static var openAppWhenRun: Bool = false

    @Parameter(title: "Genre", default: .lofi)
    var genre: MusicGenre

    @Parameter(title: "Rooms")
    var rooms: [String]?

    @Parameter(title: "Volume", default: 30)
    var volume: Int

    enum MusicGenre: String, AppEnum {
        case lofi = "lofi"
        case classical = "classical"
        case jazz = "jazz"
        case nature = "nature"
        case ambient = "ambient"

        static var typeDisplayRepresentation = TypeDisplayRepresentation(name: "Music Genre")

        static var caseDisplayRepresentations: [MusicGenre: DisplayRepresentation] = [
            .lofi: DisplayRepresentation(title: "Lo-fi"),
            .classical: DisplayRepresentation(title: "Classical"),
            .jazz: DisplayRepresentation(title: "Jazz"),
            .nature: DisplayRepresentation(title: "Nature Sounds"),
            .ambient: DisplayRepresentation(title: "Ambient")
        ]
    }

    func perform() async throws -> some IntentResult & ProvidesDialog {
        let body: [String: Any] = [
            "genre": genre.rawValue,
            "rooms": rooms as Any,
            "volume": volume
        ]

        try await postToKagami(endpoint: "/home/audio/ambient", body: body)

        let roomsText = rooms?.joined(separator: ", ") ?? "all rooms"
        return .result(dialog: "Playing \(genre.rawValue) music in \(roomsText) at \(volume)% volume.")
    }

    static var parameterSummary: some ParameterSummary {
        Summary("Play \(\.$genre) at \(\.$volume)%") {
            \.$rooms
        }
    }
}

// MARK: - Reading Mode Intent

struct ReadingModeIntent: AppIntent {
    static var title: LocalizedStringResource = "Reading Mode"
    static var description = IntentDescription("Optimize lighting for comfortable reading")

    static var openAppWhenRun: Bool = false

    @Parameter(title: "Room")
    var room: String?

    func perform() async throws -> some IntentResult & ProvidesDialog {
        let body: [String: Any] = ["room": room as Any]

        try await postToKagami(endpoint: "/home/scenes/reading", body: body)

        let roomText = room ?? "current room"
        return .result(dialog: "Reading mode activated in \(roomText). Enjoy your book.")
    }

    static var parameterSummary: some ParameterSummary {
        Summary("Start reading mode") {
            \.$room
        }
    }
}

// MARK: - Dinner Mode Intent

struct DinnerModeIntent: AppIntent {
    static var title: LocalizedStringResource = "Dinner Mode"
    static var description = IntentDescription("Set the perfect dining ambiance")

    static var openAppWhenRun: Bool = false

    @Parameter(title: "Guests", default: false)
    var hasGuests: Bool

    func perform() async throws -> some IntentResult & ProvidesDialog {
        let body: [String: Any] = ["guests": hasGuests]

        try await postToKagami(endpoint: "/home/scenes/dinner", body: body)

        let message = hasGuests
            ? "Dinner mode with guests activated. Elegant ambiance set."
            : "Dinner mode activated. Bon appetit."

        return .result(dialog: IntentDialog(stringLiteral: message))
    }

    static var parameterSummary: some ParameterSummary {
        Summary("Set dinner mode") {
            \.$hasGuests
        }
    }
}

// MARK: - Morning Routine Intent

struct MorningRoutineIntent: AppIntent {
    static var title: LocalizedStringResource = "Morning Routine"
    static var description = IntentDescription("Start your day with gradual wake-up lighting and information")

    static var openAppWhenRun: Bool = false

    @Parameter(title: "Gradual Wake", default: true)
    var gradualWake: Bool

    func perform() async throws -> some IntentResult & ProvidesDialog {
        let body: [String: Any] = ["gradual": gradualWake]

        try await postToKagami(endpoint: "/home/scenes/morning", body: body)

        let message = gradualWake
            ? "Good morning. Lights warming up gradually."
            : "Good morning. Lights on."

        return .result(dialog: IntentDialog(stringLiteral: message))
    }

    static var parameterSummary: some ParameterSummary {
        Summary("Start morning routine") {
            \.$gradualWake
        }
    }
}

// MARK: - Away Mode Intent

struct AwayModeIntent: AppIntent {
    static var title: LocalizedStringResource = "Away Mode"
    static var description = IntentDescription("Secure the home and enable presence simulation")

    static var openAppWhenRun: Bool = false

    @Parameter(title: "Simulate Presence", default: true)
    var simulatePresence: Bool

    func perform() async throws -> some IntentResult & ProvidesDialog {
        let body: [String: Any] = ["simulate": simulatePresence]

        try await postToKagami(endpoint: "/home/scenes/away", body: body)

        var message = "Away mode activated. All doors locked."
        if simulatePresence {
            message += " Presence simulation enabled."
        }

        return .result(dialog: IntentDialog(stringLiteral: message))
    }

    static var parameterSummary: some ParameterSummary {
        Summary("Activate away mode") {
            \.$simulatePresence
        }
    }
}

// MARK: - Quick Dim Intent

struct QuickDimIntent: AppIntent {
    static var title: LocalizedStringResource = "Quick Dim"
    static var description = IntentDescription("Quickly dim or brighten all lights")

    static var openAppWhenRun: Bool = false

    @Parameter(title: "Direction", default: .dim)
    var direction: DimDirection

    @Parameter(title: "Amount", default: 20)
    var amount: Int

    enum DimDirection: String, AppEnum {
        case dim = "dim"
        case brighten = "brighten"

        static var typeDisplayRepresentation = TypeDisplayRepresentation(name: "Direction")

        static var caseDisplayRepresentations: [DimDirection: DisplayRepresentation] = [
            .dim: DisplayRepresentation(title: "Dim"),
            .brighten: DisplayRepresentation(title: "Brighten")
        ]
    }

    func perform() async throws -> some IntentResult & ProvidesDialog {
        let body: [String: Any] = [
            "direction": direction.rawValue,
            "amount": amount
        ]

        try await postToKagami(endpoint: "/home/lights/adjust", body: body)

        let actionText = direction == .dim ? "dimmed" : "brightened"
        return .result(dialog: "Lights \(actionText) by \(amount)%.")
    }

    static var parameterSummary: some ParameterSummary {
        Summary("\(\.$direction) lights by \(\.$amount)%")
    }
}

// MARK: - Garage Door Intent

struct GarageDoorIntent: AppIntent {
    static var title: LocalizedStringResource = "Garage Door"
    static var description = IntentDescription("Control the garage door")

    static var openAppWhenRun: Bool = false

    @Parameter(title: "Action", default: .toggle)
    var action: GarageAction

    enum GarageAction: String, AppEnum {
        case open = "open"
        case close = "close"
        case toggle = "toggle"

        static var typeDisplayRepresentation = TypeDisplayRepresentation(name: "Garage Action")

        static var caseDisplayRepresentations: [GarageAction: DisplayRepresentation] = [
            .open: DisplayRepresentation(title: "Open"),
            .close: DisplayRepresentation(title: "Close"),
            .toggle: DisplayRepresentation(title: "Toggle")
        ]
    }

    func perform() async throws -> some IntentResult & ProvidesDialog {
        let endpoint = "/home/garage/\(action.rawValue)"
        try await postToKagami(endpoint: endpoint)

        let message: String
        switch action {
        case .open: message = "Garage door opening."
        case .close: message = "Garage door closing."
        case .toggle: message = "Garage door toggled."
        }

        return .result(dialog: IntentDialog(stringLiteral: message))
    }

    static var parameterSummary: some ParameterSummary {
        Summary("\(\.$action) garage door")
    }
}

/*
 * Mirror
 * h(x) >= 0. Always.
 */
