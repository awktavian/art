//
// CommandRegistry.swift — Extensible Command System
//
// Provides a plugin-style architecture for:
// - Slash commands (/scene, /lights, etc.)
// - @ mentions (@room, @scene, etc.)
//
// Colony: Forge (e2) — Implementation
//

import Foundation

// MARK: - Command Protocol

@MainActor
protocol KagamiCommand {
    var name: String { get }
    var description: String { get }
    var aliases: [String] { get }
    var argsHint: String? { get }

    func execute(args: String) async throws -> CommandResult
    func suggest(partial: String) async -> [String]
}

extension KagamiCommand {
    var aliases: [String] { [] }
    var argsHint: String? { nil }
    func suggest(partial: String) async -> [String] { [] }
}

// MARK: - Command Result

struct CommandResult: @unchecked Sendable {
    let success: Bool
    let message: String?
    let data: [String: Any]?

    static func success(_ message: String? = nil) -> CommandResult {
        CommandResult(success: true, message: message, data: nil)
    }

    static func failure(_ message: String) -> CommandResult {
        CommandResult(success: false, message: message, data: nil)
    }
}

// MARK: - Mention Handler Protocol

protocol MentionHandler {
    var type: String { get }
    var prefix: String { get }

    func fetch(query: String) async -> [MentionItem]
    func resolve(item: MentionItem) -> [String: Any]
}

struct MentionItem: Identifiable, Hashable {
    let id: String
    let label: String
    let icon: String
    let value: String
    let secondary: String?

    init(id: String, label: String, icon: String = "", value: String? = nil, secondary: String? = nil) {
        self.id = id
        self.label = label
        self.icon = icon
        self.value = value ?? label
        self.secondary = secondary
    }
}

// MARK: - Command Registry

@MainActor
class CommandRegistry: ObservableObject {
    static let shared = CommandRegistry()

    @Published private(set) var commands: [String: any KagamiCommand] = [:]
    @Published private(set) var mentionHandlers: [String: any MentionHandler] = [:]

    private init() {
        registerBuiltinCommands()
        registerBuiltinMentions()
    }

    // MARK: - Registration

    func register(command: any KagamiCommand) {
        commands[command.name] = command
        for alias in command.aliases {
            commands[alias] = command
        }
    }

    func register(mentionHandler: any MentionHandler) {
        mentionHandlers[mentionHandler.type] = mentionHandler
    }

    // MARK: - Command Execution

    func parseSlashCommand(_ input: String) -> (command: (any KagamiCommand)?, args: String) {
        guard input.hasPrefix("/") else { return (nil, input) }

        let trimmed = String(input.dropFirst())
        let parts = trimmed.split(separator: " ", maxSplits: 1)
        let name = parts.first.map(String.init)?.lowercased() ?? ""
        let args = parts.count > 1 ? String(parts[1]) : ""

        return (commands[name], args)
    }

    func executeSlashCommand(_ input: String) async throws -> CommandResult {
        let (command, args) = parseSlashCommand(input)
        guard let command = command else {
            throw CommandError.unknownCommand(input.split(separator: " ").first.map(String.init) ?? input)
        }
        return try await command.execute(args: args)
    }

    // MARK: - Suggestions

    func getSuggestions(for input: String) async -> [CommandSuggestion] {
        guard input.hasPrefix("/") else { return [] }

        let trimmed = String(input.dropFirst())
        let parts = trimmed.split(separator: " ", maxSplits: 1)
        let partial = parts.first.map(String.init)?.lowercased() ?? ""

        // If we have a complete command and args, get arg suggestions
        if parts.count > 1, let command = commands[partial] {
            let argPartial = String(parts[1])
            let suggestions = await command.suggest(partial: argPartial)
            return suggestions.map {
                CommandSuggestion(
                    label: "/\(command.name) \($0)",
                    icon: "arrow.right",
                    value: "/\(command.name) \($0)"
                )
            }
        }

        // Get matching commands
        let uniqueCommands = Set(commands.values.map { $0.name })
        return uniqueCommands
            .filter { $0.hasPrefix(partial) }
            .sorted()
            .prefix(8)
            .map { name in
                let cmd = commands[name]!
                let hint = cmd.argsHint.map { " \($0)" } ?? ""
                return CommandSuggestion(
                    label: "/\(name)",
                    secondary: "\(hint) — \(cmd.description)",
                    icon: "chevron.right",
                    value: "/\(name) "
                )
            }
    }

    func getMentionSuggestions(type: String?, query: String) async -> [MentionItem] {
        if let type = type, let handler = mentionHandlers[type] {
            return await handler.fetch(query: query)
        }

        // Return mention type suggestions
        return mentionHandlers.keys.sorted().filter {
            query.isEmpty || $0.hasPrefix(query.lowercased())
        }.map { type in
            MentionItem(
                id: type,
                label: "@\(type)",
                icon: mentionHandlers[type]?.prefix ?? "@",
                value: "@\(type):",
                secondary: "Search \(type)s"
            )
        }
    }

    // MARK: - Built-in Commands

    private func registerBuiltinCommands() {
        register(command: SceneCommand())
        register(command: LightsCommand())
        register(command: TVCommand())
        register(command: FireplaceCommand())
        register(command: AnnounceCommand())
        register(command: HelpCommand(registry: self))
    }

    private func registerBuiltinMentions() {
        register(mentionHandler: RoomMentionHandler())
        register(mentionHandler: SceneMentionHandler())
    }
}

// MARK: - Suggestion Types

struct CommandSuggestion: Identifiable {
    let id = UUID()
    let label: String
    var secondary: String? = nil
    let icon: String
    let value: String
}

// MARK: - Errors

enum CommandError: LocalizedError {
    case unknownCommand(String)
    case invalidArgs(String)
    case executionFailed(String)

    var errorDescription: String? {
        switch self {
        case .unknownCommand(let cmd): return "Unknown command: \(cmd)"
        case .invalidArgs(let msg): return "Invalid arguments: \(msg)"
        case .executionFailed(let msg): return "Failed: \(msg)"
        }
    }
}

// MARK: - Built-in Commands

struct SceneCommand: KagamiCommand {
    let name = "scene"
    let description = "Execute a scene"
    let aliases = ["s"]
    let argsHint: String? = "<movie|goodnight|welcome>"

    func execute(args: String) async throws -> CommandResult {
        let scene = args.trimmingCharacters(in: .whitespaces).lowercased()
        guard !scene.isEmpty else {
            throw CommandError.invalidArgs("Scene name required")
        }
        await KagamiAPIService.shared.executeScene(scene)
        return .success("Scene \(scene) activated")
    }

    func suggest(partial: String) async -> [String] {
        let scenes = ["movie", "goodnight", "welcome", "exit_movie"]
        return scenes.filter { $0.hasPrefix(partial.lowercased()) }
    }
}

struct LightsCommand: KagamiCommand {
    let name = "lights"
    let description = "Set light level"
    let aliases = ["l", "light"]
    let argsHint: String? = "<0-100> [room]"

    func execute(args: String) async throws -> CommandResult {
        let parts = args.split(separator: " ")
        guard let levelStr = parts.first, let level = Int(levelStr) else {
            throw CommandError.invalidArgs("Level (0-100) required")
        }

        let room = parts.count > 1 ? parts.dropFirst().joined(separator: " ") : nil

        if let room = room {
            await KagamiAPIService.shared.setLights(level, rooms: [room])
        } else {
            await KagamiAPIService.shared.setLights(level)
        }

        return .success("Lights set to \(level)%")
    }

    func suggest(partial: String) async -> [String] {
        let levels = ["0", "25", "50", "75", "100"]
        if partial.isEmpty { return levels }

        // If partial starts with a number, suggest rooms
        if partial.first?.isNumber == true {
            let rooms = ["Living Room", "Kitchen", "Office", "Bedroom", "Dining"]
            let parts = partial.split(separator: " ", maxSplits: 1)
            if parts.count > 1 {
                let roomQuery = String(parts[1]).lowercased()
                return rooms
                    .filter { $0.lowercased().contains(roomQuery) }
                    .map { "\(parts[0]) \($0)" }
            }
        }

        return levels.filter { $0.hasPrefix(partial) }
    }
}

struct TVCommand: KagamiCommand {
    let name = "tv"
    let description = "Control TV mount"
    let argsHint: String? = "<up|down>"

    func execute(args: String) async throws -> CommandResult {
        let action = args.trimmingCharacters(in: .whitespaces).lowercased()
        guard ["up", "down", "raise", "lower"].contains(action) else {
            throw CommandError.invalidArgs("Use: /tv up or /tv down")
        }

        let normalizedAction = action == "up" ? "raise" : action == "down" ? "lower" : action
        await KagamiAPIService.shared.tvControl(normalizedAction)
        return .success("TV \(normalizedAction)")
    }

    func suggest(partial: String) async -> [String] {
        return ["up", "down"].filter { $0.hasPrefix(partial.lowercased()) }
    }
}

struct FireplaceCommand: KagamiCommand {
    let name = "fireplace"
    let description = "Toggle fireplace"
    let aliases = ["fire"]
    let argsHint: String? = "[on|off]"

    func execute(args: String) async throws -> CommandResult {
        let state = args.trimmingCharacters(in: .whitespaces).lowercased()
        let on = state != "off"
        await KagamiAPIService.shared.toggleFireplace(on: on)
        return .success("Fireplace \(on ? "on" : "off")")
    }

    func suggest(partial: String) async -> [String] {
        return ["on", "off"].filter { $0.hasPrefix(partial.lowercased()) }
    }
}

struct AnnounceCommand: KagamiCommand {
    let name = "announce"
    let description = "Announce message"
    let aliases = ["say", "tts"]
    let argsHint: String? = "<message>"

    func execute(args: String) async throws -> CommandResult {
        let message = args.trimmingCharacters(in: .whitespaces)
            .trimmingCharacters(in: CharacterSet(charactersIn: "\"'"))
        guard !message.isEmpty else {
            throw CommandError.invalidArgs("Message required")
        }
        await KagamiAPIService.shared.announce(message)
        return .success("Announced")
    }
}

struct HelpCommand: KagamiCommand {
    let name = "help"
    let description = "Show available commands"
    let aliases = ["?", "commands"]

    let registry: CommandRegistry

    func execute(args: String) async throws -> CommandResult {
        let commandList = Set(registry.commands.values.map { $0.name })
            .sorted()
            .map { name -> String in
                let cmd = registry.commands[name]!
                let hint = cmd.argsHint.map { " \($0)" } ?? ""
                return "/\(name)\(hint) — \(cmd.description)"
            }
            .joined(separator: "\n")

        return CommandResult(success: true, message: commandList, data: ["commands": commandList])
    }
}

// MARK: - Built-in Mention Handlers

struct RoomMentionHandler: MentionHandler {
    let type = "room"
    let prefix = "🏠"

    func fetch(query: String) async -> [MentionItem] {
        let rooms = [
            ("living", "Living Room", "1st"),
            ("kitchen", "Kitchen", "1st"),
            ("dining", "Dining", "1st"),
            ("office", "Office", "2nd"),
            ("bedroom", "Primary Bedroom", "2nd"),
            ("loft", "Loft", "2nd"),
            ("game", "Game Room", "Basement"),
            ("gym", "Gym", "Basement"),
        ]

        return rooms
            .filter { query.isEmpty || $0.1.lowercased().contains(query.lowercased()) }
            .map { MentionItem(id: $0.0, label: $0.1, icon: "🏠", secondary: $0.2) }
    }

    func resolve(item: MentionItem) -> [String: Any] {
        return ["room": item.id, "roomName": item.label]
    }
}

struct SceneMentionHandler: MentionHandler {
    let type = "scene"
    let prefix = "🎬"

    func fetch(query: String) async -> [MentionItem] {
        let scenes = [
            ("movie", "Movie Mode", "🎬"),
            ("goodnight", "Goodnight", "🌙"),
            ("welcome", "Welcome Home", "🏠"),
            ("exit_movie", "Exit Movie", "☀️"),
        ]

        return scenes
            .filter { query.isEmpty || $0.1.lowercased().contains(query.lowercased()) }
            .map { MentionItem(id: $0.0, label: $0.1, icon: $0.2) }
    }

    func resolve(item: MentionItem) -> [String: Any] {
        return ["scene": item.id]
    }
}
