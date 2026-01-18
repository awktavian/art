/**
 * Kagami Command Registry — Extensible Command System
 *
 * Provides a plugin-style architecture for:
 * - Slash commands (/scene, /lights, etc.)
 * - @ mentions (@room, @scene, etc.)
 *
 * Colony: Forge (e2) — Implementation
 *
 * Architecture Note: Commands receive KagamiApiService via execute() parameter
 * to avoid direct KagamiApp.instance access. The registry is initialized
 * with the API service during app startup via DI.
 */

package com.kagami.android.services

import javax.inject.Inject
import javax.inject.Singleton

// MARK: - Command Interface

interface KagamiCommand {
    val name: String
    val description: String
    val aliases: List<String> get() = emptyList()
    val argsHint: String? get() = null

    suspend fun execute(args: String, apiService: KagamiApiService): CommandResult
    suspend fun suggest(partial: String): List<String> = emptyList()
}

// MARK: - Command Result

data class CommandResult(
    val success: Boolean,
    val message: String? = null,
    val data: Map<String, Any>? = null
) {
    companion object {
        fun success(message: String? = null) = CommandResult(true, message)
        fun failure(message: String) = CommandResult(false, message)
    }
}

// MARK: - Mention Handler Interface

interface MentionHandler {
    val type: String
    val prefix: String

    suspend fun fetch(query: String): List<MentionItem>
    fun resolve(item: MentionItem): Map<String, Any>
}

data class MentionItem(
    val id: String,
    val label: String,
    val icon: String = "",
    val value: String = label,
    val secondary: String? = null
)

// MARK: - Command Suggestion

data class CommandSuggestion(
    val label: String,
    val secondary: String? = null,
    val icon: String,
    val value: String
)

// MARK: - Command Registry

/**
 * Singleton command registry with proper DI support.
 * Commands receive the API service as a parameter to avoid global state access.
 */
@Singleton
class CommandRegistry @Inject constructor() {
    private val _commands = mutableMapOf<String, KagamiCommand>()
    val commands: Map<String, KagamiCommand> get() = _commands

    private val _mentionHandlers = mutableMapOf<String, MentionHandler>()
    val mentionHandlers: Map<String, MentionHandler> get() = _mentionHandlers

    init {
        registerBuiltinCommands()
        registerBuiltinMentions()
        // Register instance for static access
        _instance = this
    }

    companion object {
        @Volatile
        private var _instance: CommandRegistry? = null

        /**
         * Get singleton instance. Note: This should only be called after DI initialization.
         * For Composable functions, prefer using hiltViewModel or LocalComposition.
         */
        fun getInstance(): CommandRegistry = _instance ?: CommandRegistry().also { _instance = it }

        // Static convenience methods that delegate to instance
        suspend fun getSuggestions(input: String): List<CommandSuggestion> =
            getInstance().getSuggestions(input)

        suspend fun getMentionSuggestions(type: String?, query: String): List<MentionItem> =
            getInstance().getMentionSuggestions(type, query)

        suspend fun executeSlashCommand(input: String, apiService: KagamiApiService): CommandResult =
            getInstance().executeSlashCommand(input, apiService)
    }

    // MARK: - Registration

    fun register(command: KagamiCommand) {
        _commands[command.name] = command
        command.aliases.forEach { _commands[it] = command }
    }

    fun register(handler: MentionHandler) {
        _mentionHandlers[handler.type] = handler
    }

    // MARK: - Command Execution

    fun parseSlashCommand(input: String): Pair<KagamiCommand?, String> {
        if (!input.startsWith("/")) return null to input

        val trimmed = input.drop(1)
        val parts = trimmed.split(" ", limit = 2)
        val name = parts.firstOrNull()?.lowercase() ?: ""
        val args = parts.getOrNull(1) ?: ""

        return _commands[name] to args
    }

    suspend fun executeSlashCommand(input: String, apiService: KagamiApiService): CommandResult {
        val (command, args) = parseSlashCommand(input)
        return command?.execute(args, apiService)
            ?: CommandResult.failure("Unknown command: ${input.split(" ").first()}")
    }

    // MARK: - Suggestions

    suspend fun getSuggestions(input: String): List<CommandSuggestion> {
        if (!input.startsWith("/")) return emptyList()

        val trimmed = input.drop(1)
        val parts = trimmed.split(" ", limit = 2)
        val partial = parts.firstOrNull()?.lowercase() ?: ""

        // If we have args, get arg suggestions
        if (parts.size > 1) {
            val command = _commands[partial] ?: return emptyList()
            val argPartial = parts[1]
            return command.suggest(argPartial).map { suggestion ->
                CommandSuggestion(
                    label = "/${command.name} $suggestion",
                    icon = "→",
                    value = "/${command.name} $suggestion"
                )
            }
        }

        // Get matching commands
        return _commands.entries
            .distinctBy { it.value.name }
            .filter { it.key.startsWith(partial) }
            .sortedBy { it.key }
            .take(8)
            .map { (_, cmd) ->
                val hint = cmd.argsHint?.let { " $it" } ?: ""
                CommandSuggestion(
                    label = "/${cmd.name}",
                    secondary = "$hint — ${cmd.description}",
                    icon = "/",
                    value = "/${cmd.name} "
                )
            }
    }

    suspend fun getMentionSuggestions(type: String?, query: String): List<MentionItem> {
        if (type != null && _mentionHandlers.containsKey(type)) {
            return _mentionHandlers[type]!!.fetch(query)
        }

        // Return mention type suggestions
        return _mentionHandlers.keys.sorted()
            .filter { query.isEmpty() || it.startsWith(query.lowercase()) }
            .map { mentionType ->
                MentionItem(
                    id = mentionType,
                    label = "@$mentionType",
                    icon = _mentionHandlers[mentionType]?.prefix ?: "@",
                    value = "@$mentionType:",
                    secondary = "Search ${mentionType}s"
                )
            }
    }

    // MARK: - Built-in Commands

    private fun registerBuiltinCommands() {
        register(SceneCommand())
        register(LightsCommand())
        register(TVCommand())
        register(FireplaceCommand())
        register(AnnounceCommand())
        register(HelpCommand())
    }

    private fun registerBuiltinMentions() {
        register(RoomMentionHandler())
        register(SceneMentionHandler())
    }
}

// MARK: - Built-in Commands

class SceneCommand : KagamiCommand {
    override val name = "scene"
    override val description = "Execute a scene"
    override val aliases = listOf("s")
    override val argsHint = "<movie|goodnight|welcome>"

    override suspend fun execute(args: String, apiService: KagamiApiService): CommandResult {
        val scene = args.trim().lowercase()
        if (scene.isEmpty()) return CommandResult.failure("Scene name required")

        apiService.executeScene(scene)
        return CommandResult.success("Scene $scene activated")
    }

    override suspend fun suggest(partial: String): List<String> {
        val scenes = listOf("movie", "goodnight", "welcome", "exit_movie")
        return scenes.filter { it.startsWith(partial.lowercase()) }
    }
}

class LightsCommand : KagamiCommand {
    override val name = "lights"
    override val description = "Set light level"
    override val aliases = listOf("l", "light")
    override val argsHint = "<0-100> [room]"

    override suspend fun execute(args: String, apiService: KagamiApiService): CommandResult {
        val parts = args.trim().split(Regex("\\s+"))
        val level = parts.firstOrNull()?.toIntOrNull()
            ?: return CommandResult.failure("Level (0-100) required")

        val room = if (parts.size > 1) parts.drop(1).joinToString(" ") else null

        if (room != null) {
            apiService.setLights(level, listOf(room))
        } else {
            apiService.setLights(level)
        }

        return CommandResult.success("Lights set to $level%")
    }

    override suspend fun suggest(partial: String): List<String> {
        val levels = listOf("0", "25", "50", "75", "100")
        if (partial.isEmpty()) return levels

        // If partial starts with a number, suggest rooms
        if (partial.firstOrNull()?.isDigit() == true) {
            val rooms = listOf("Living Room", "Kitchen", "Office", "Bedroom", "Dining")
            val parts = partial.split(Regex("\\s+"), limit = 2)
            if (parts.size > 1) {
                val roomQuery = parts[1].lowercase()
                return rooms
                    .filter { it.lowercase().contains(roomQuery) }
                    .map { "${parts[0]} $it" }
            }
        }

        return levels.filter { it.startsWith(partial) }
    }
}

class TVCommand : KagamiCommand {
    override val name = "tv"
    override val description = "Control TV mount"
    override val argsHint = "<up|down>"

    override suspend fun execute(args: String, apiService: KagamiApiService): CommandResult {
        val action = args.trim().lowercase()
        if (action !in listOf("up", "down", "raise", "lower")) {
            return CommandResult.failure("Use: /tv up or /tv down")
        }

        val normalizedAction = when (action) {
            "up" -> "raise"
            "down" -> "lower"
            else -> action
        }

        apiService.tvControl(normalizedAction)
        return CommandResult.success("TV $normalizedAction")
    }

    override suspend fun suggest(partial: String): List<String> {
        return listOf("up", "down").filter { it.startsWith(partial.lowercase()) }
    }
}

class FireplaceCommand : KagamiCommand {
    override val name = "fireplace"
    override val description = "Toggle fireplace"
    override val aliases = listOf("fire")
    override val argsHint = "[on|off]"

    override suspend fun execute(args: String, apiService: KagamiApiService): CommandResult {
        val state = args.trim().lowercase()
        val on = state != "off"
        apiService.toggleFireplace(on)
        return CommandResult.success("Fireplace ${if (on) "on" else "off"}")
    }

    override suspend fun suggest(partial: String): List<String> {
        return listOf("on", "off").filter { it.startsWith(partial.lowercase()) }
    }
}

class AnnounceCommand : KagamiCommand {
    override val name = "announce"
    override val description = "Announce message"
    override val aliases = listOf("say", "tts")
    override val argsHint = "<message>"

    override suspend fun execute(args: String, apiService: KagamiApiService): CommandResult {
        val message = args.trim().trim('"', '\'')
        if (message.isEmpty()) return CommandResult.failure("Message required")

        apiService.announce(message)
        return CommandResult.success("Announced")
    }
}

class HelpCommand : KagamiCommand {
    override val name = "help"
    override val description = "Show available commands"
    override val aliases = listOf("?", "commands")

    override suspend fun execute(args: String, apiService: KagamiApiService): CommandResult {
        // Note: This accesses the static commands list, not requiring apiService
        val commandList = "Available commands:\n" +
            "/scene <name> - Execute a scene\n" +
            "/lights <0-100> [room] - Set light level\n" +
            "/tv <up|down> - Control TV mount\n" +
            "/fireplace [on|off] - Toggle fireplace\n" +
            "/announce <message> - Announce message\n" +
            "/help - Show this help"

        return CommandResult(true, commandList, mapOf("commands" to commandList))
    }
}

// MARK: - Built-in Mention Handlers

class RoomMentionHandler : MentionHandler {
    override val type = "room"
    override val prefix = "🏠"

    override suspend fun fetch(query: String): List<MentionItem> {
        val rooms = listOf(
            Triple("living", "Living Room", "1st"),
            Triple("kitchen", "Kitchen", "1st"),
            Triple("dining", "Dining", "1st"),
            Triple("office", "Office", "2nd"),
            Triple("bedroom", "Primary Bedroom", "2nd"),
            Triple("loft", "Loft", "2nd"),
            Triple("game", "Game Room", "Basement"),
            Triple("gym", "Gym", "Basement"),
        )

        return rooms
            .filter { query.isEmpty() || it.second.lowercase().contains(query.lowercase()) }
            .map { MentionItem(it.first, it.second, "🏠", secondary = it.third) }
    }

    override fun resolve(item: MentionItem) = mapOf("room" to item.id, "roomName" to item.label)
}

class SceneMentionHandler : MentionHandler {
    override val type = "scene"
    override val prefix = "🎬"

    override suspend fun fetch(query: String): List<MentionItem> {
        val scenes = listOf(
            Triple("movie", "Movie Mode", "🎬"),
            Triple("goodnight", "Goodnight", "🌙"),
            Triple("welcome", "Welcome Home", "🏠"),
            Triple("exit_movie", "Exit Movie", "☀️"),
        )

        return scenes
            .filter { query.isEmpty() || it.second.lowercase().contains(query.lowercase()) }
            .map { MentionItem(it.first, it.second, it.third) }
    }

    override fun resolve(item: MentionItem) = mapOf("scene" to item.id)
}
