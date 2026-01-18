/**
 * Kagami Command Registry — Extensible System
 *
 * Provides a plugin-style architecture for:
 * - Slash commands (/scene, /lights, /file, etc.)
 * - @ mentions (@room, @file, @scene, etc.)
 * - Custom command handlers
 *
 * Design: Registry pattern with async handlers and typeahead support.
 */

// ============================================================================
// Core Registry
// ============================================================================

class CommandRegistry {
    constructor() {
        this.slashCommands = new Map();
        this.mentionHandlers = new Map();
        this.middleware = [];
    }

    // -------------------------------------------------------------------------
    // Slash Commands
    // -------------------------------------------------------------------------

    /**
     * Register a slash command
     * @param {string} name - Command name (without /)
     * @param {Object} config - Command configuration
     * @param {string} config.description - Human-readable description
     * @param {string} [config.args] - Argument syntax hint
     * @param {string[]} [config.aliases] - Alternative names
     * @param {Function} config.execute - Async handler (args: string) => Promise<any>
     * @param {Function} [config.suggest] - Typeahead suggestions (partial: string) => Promise<string[]>
     */
    registerSlashCommand(name, config) {
        const command = {
            name,
            description: config.description || '',
            args: config.args || '',
            aliases: config.aliases || [],
            execute: config.execute,
            suggest: config.suggest || null,
        };

        this.slashCommands.set(name, command);

        // Register aliases
        for (const alias of command.aliases) {
            this.slashCommands.set(alias, command);
        }

        return this;
    }

    /**
     * Get all registered slash commands (excluding aliases)
     */
    getSlashCommands() {
        const seen = new Set();
        const commands = [];
        for (const [name, cmd] of this.slashCommands) {
            if (!seen.has(cmd)) {
                seen.add(cmd);
                commands.push(cmd);
            }
        }
        return commands;
    }

    /**
     * Parse input for slash command
     * @returns {{ command: Object|null, args: string }}
     */
    parseSlashCommand(input) {
        if (!input.startsWith('/')) {
            return { command: null, args: input };
        }

        const spaceIndex = input.indexOf(' ');
        const name = spaceIndex > 0
            ? input.slice(1, spaceIndex).toLowerCase()
            : input.slice(1).toLowerCase();
        const args = spaceIndex > 0 ? input.slice(spaceIndex + 1) : '';

        const command = this.slashCommands.get(name);
        return { command: command || null, args };
    }

    /**
     * Execute a slash command
     */
    async executeSlashCommand(input) {
        const { command, args } = this.parseSlashCommand(input);
        if (!command) {
            throw new Error(`Unknown command: ${input.split(' ')[0]}`);
        }

        // Run middleware
        for (const mw of this.middleware) {
            const result = await mw({ type: 'slash', command, args });
            if (result === false) return null;
        }

        return await command.execute(args);
    }

    // -------------------------------------------------------------------------
    // @ Mentions
    // -------------------------------------------------------------------------

    /**
     * Register a mention handler
     * @param {string} type - Mention type (room, file, scene, etc.)
     * @param {Object} config - Handler configuration
     * @param {string} config.prefix - Display prefix (e.g., "🏠" for rooms)
     * @param {Function} config.fetch - Fetch suggestions: (query: string) => Promise<MentionItem[]>
     * @param {Function} [config.onSelect] - Callback when item selected
     * @param {Function} [config.resolve] - Resolve mention to context: (item) => any
     */
    registerMentionHandler(type, config) {
        this.mentionHandlers.set(type, {
            type,
            prefix: config.prefix || '@',
            fetch: config.fetch,
            onSelect: config.onSelect || null,
            resolve: config.resolve || ((item) => item),
        });
        return this;
    }

    /**
     * Get all mention types
     */
    getMentionTypes() {
        return Array.from(this.mentionHandlers.keys());
    }

    /**
     * Fetch suggestions for a mention type
     */
    async fetchMentionSuggestions(type, query) {
        const handler = this.mentionHandlers.get(type);
        if (!handler) return [];
        return await handler.fetch(query);
    }

    /**
     * Parse input for @ mentions
     * Returns array of { type, query, start, end }
     */
    parseMentions(input) {
        const mentions = [];
        const regex = /@(\w+)(?::([^\s]*))?/g;
        let match;

        while ((match = regex.exec(input)) !== null) {
            const type = match[1].toLowerCase();
            const query = match[2] || '';
            mentions.push({
                type,
                query,
                start: match.index,
                end: match.index + match[0].length,
                raw: match[0],
            });
        }

        return mentions;
    }

    /**
     * Check if cursor is inside an incomplete mention
     * Returns { type, query, start } or null
     */
    getActiveMention(input, cursorPosition) {
        // Find @ before cursor
        const beforeCursor = input.slice(0, cursorPosition);
        const atMatch = beforeCursor.match(/@(\w*)$/);

        if (atMatch) {
            const start = beforeCursor.lastIndexOf('@');
            const query = atMatch[1];

            // Check if this is a typed mention (e.g., @room:)
            const afterAt = input.slice(start + 1, cursorPosition);
            const colonIndex = afterAt.indexOf(':');

            if (colonIndex > 0) {
                const type = afterAt.slice(0, colonIndex);
                const subQuery = afterAt.slice(colonIndex + 1);
                if (this.mentionHandlers.has(type)) {
                    return { type, query: subQuery, start };
                }
            }

            // Generic mention - show type picker
            return { type: null, query, start };
        }

        return null;
    }

    // -------------------------------------------------------------------------
    // Middleware
    // -------------------------------------------------------------------------

    /**
     * Add middleware that runs before command execution
     * Return false to cancel, anything else to continue
     */
    use(fn) {
        this.middleware.push(fn);
        return this;
    }
}

// ============================================================================
// Default Instance & Built-in Commands
// ============================================================================

const registry = new CommandRegistry();

// -------------------------------------------------------------------------
// Smart Home Commands
// -------------------------------------------------------------------------

registry.registerSlashCommand('scene', {
    description: 'Execute a scene',
    args: '<movie|goodnight|welcome>',
    aliases: ['s'],
    execute: async (args) => {
        const scene = args.trim().toLowerCase();
        if (window.__TAURI__) {
            return await window.__TAURI__.core.invoke('execute_scene', { scene });
        }
        return await KagamiAPI.executeScene(scene);
    },
    suggest: async (partial) => {
        const scenes = ['movie', 'goodnight', 'welcome', 'exit_movie'];
        return scenes.filter(s => s.startsWith(partial.toLowerCase()));
    }
});

registry.registerSlashCommand('lights', {
    description: 'Set light level',
    args: '<0-100> [room]',
    aliases: ['l', 'light'],
    execute: async (args) => {
        const parts = args.trim().split(/\s+/);
        const level = parseInt(parts[0], 10);
        const room = parts.slice(1).join(' ') || null;

        if (isNaN(level) || level < 0 || level > 100) {
            throw new Error('Level must be 0-100');
        }

        if (window.__TAURI__) {
            return await window.__TAURI__.core.invoke('set_lights', {
                level,
                rooms: room ? [room] : null
            });
        }
        return await KagamiAPI.setLights(level, room ? [room] : null);
    },
    suggest: async (partial) => {
        const levels = ['0', '25', '50', '75', '100'];
        if (!partial) return levels;

        // If numeric, suggest rooms
        if (/^\d+$/.test(partial.split(' ')[0])) {
            if (window.__TAURI__) {
                try {
                    const rooms = await window.__TAURI__.core.invoke('get_rooms');
                    const roomQuery = partial.split(' ').slice(1).join(' ').toLowerCase();
                    return rooms
                        .map(r => r.name)
                        .filter(n => n.toLowerCase().includes(roomQuery))
                        .map(n => `${partial.split(' ')[0]} ${n}`);
                } catch { return []; }
            }
        }
        return levels.filter(l => l.startsWith(partial));
    }
});

registry.registerSlashCommand('room', {
    description: 'Set room context',
    args: '<room name>',
    aliases: ['r'],
    execute: async (args) => {
        const roomName = args.trim();
        // Set as context for subsequent commands
        window.kagamiContext = window.kagamiContext || {};
        window.kagamiContext.room = roomName;
        return { success: true, room: roomName };
    },
    suggest: async (partial) => {
        if (window.__TAURI__) {
            try {
                const rooms = await window.__TAURI__.core.invoke('get_rooms');
                return rooms
                    .map(r => r.name)
                    .filter(n => n.toLowerCase().includes(partial.toLowerCase()));
            } catch { return []; }
        }
        // Fallback static list
        return ['Living Room', 'Kitchen', 'Office', 'Bedroom', 'Dining']
            .filter(n => n.toLowerCase().includes(partial.toLowerCase()));
    }
});

registry.registerSlashCommand('tv', {
    description: 'Control TV mount',
    args: '<up|down>',
    execute: async (args) => {
        const action = args.trim().toLowerCase();
        if (!['up', 'down', 'raise', 'lower'].includes(action)) {
            throw new Error('Use: /tv up or /tv down');
        }
        const normalizedAction = action === 'up' ? 'raise' : action === 'down' ? 'lower' : action;

        if (window.__TAURI__) {
            return await window.__TAURI__.core.invoke('control_tv', {
                action: normalizedAction,
                preset: normalizedAction === 'lower' ? 1 : null
            });
        }
        return await KagamiAPI.controlTV(normalizedAction);
    },
    suggest: async () => ['up', 'down']
});

registry.registerSlashCommand('fireplace', {
    description: 'Toggle fireplace',
    args: '[on|off]',
    aliases: ['fire'],
    execute: async (args) => {
        const state = args.trim().toLowerCase();
        const on = state !== 'off';

        if (window.__TAURI__) {
            return await window.__TAURI__.core.invoke('toggle_fireplace', { on });
        }
        return await KagamiAPI.toggleFireplace(on);
    },
    suggest: async () => ['on', 'off']
});

registry.registerSlashCommand('announce', {
    description: 'Announce message',
    args: '<message> [room]',
    aliases: ['say', 'tts'],
    execute: async (args) => {
        // Parse "message" or message [room]
        const match = args.match(/^"([^"]+)"(?:\s+(.+))?$/) ||
                      args.match(/^(.+?)(?:\s+in\s+(.+))?$/);

        if (!match) {
            throw new Error('Usage: /announce "message" [room]');
        }

        const text = match[1];
        const room = match[2] || null;

        if (window.__TAURI__) {
            return await window.__TAURI__.core.invoke('announce', {
                text,
                rooms: room ? [room] : null,
                colony: null
            });
        }
        return await KagamiAPI.announce(text, room ? [room] : null);
    }
});

// -------------------------------------------------------------------------
// Utility Commands
// -------------------------------------------------------------------------

registry.registerSlashCommand('help', {
    description: 'Show available commands',
    aliases: ['?', 'commands'],
    execute: async () => {
        const commands = registry.getSlashCommands();
        return {
            commands: commands.map(c => ({
                name: `/${c.name}`,
                args: c.args,
                description: c.description,
                aliases: c.aliases.map(a => `/${a}`)
            }))
        };
    }
});

registry.registerSlashCommand('clear', {
    description: 'Clear conversation',
    execute: async () => {
        window.kagamiContext = {};
        return { success: true, message: 'Context cleared' };
    }
});

registry.registerSlashCommand('status', {
    description: 'Show system status',
    execute: async () => {
        if (window.__TAURI__) {
            const status = await window.__TAURI__.core.invoke('get_api_status');
            return status;
        }
        return await KagamiAPI.getStatus();
    }
});

// -------------------------------------------------------------------------
// File Commands (HAL Integration)
// -------------------------------------------------------------------------

registry.registerSlashCommand('file', {
    description: 'Add file to context',
    args: '<path>',
    aliases: ['f'],
    execute: async (args) => {
        const path = args.trim();
        if (window.__TAURI__) {
            const preview = await window.__TAURI__.core.invoke('read_file_preview', {
                path,
                lines: 50
            });
            window.kagamiContext = window.kagamiContext || {};
            window.kagamiContext.files = window.kagamiContext.files || [];
            window.kagamiContext.files.push({ path, preview });
            return { success: true, path, lines: preview.split('\n').length };
        }
        throw new Error('File access requires desktop app');
    },
    suggest: async (partial) => {
        if (window.__TAURI__) {
            try {
                const files = await window.__TAURI__.core.invoke('search_files', {
                    query: partial || '*',
                    limit: 10
                });
                return files.map(f => f.path);
            } catch { return []; }
        }
        return [];
    }
});

// -------------------------------------------------------------------------
// @ Mention Handlers
// -------------------------------------------------------------------------

registry.registerMentionHandler('room', {
    prefix: '🏠',
    fetch: async (query) => {
        let rooms;
        if (window.__TAURI__) {
            try {
                rooms = await window.__TAURI__.core.invoke('get_rooms');
            } catch {
                rooms = [
                    { id: 'living', name: 'Living Room' },
                    { id: 'kitchen', name: 'Kitchen' },
                    { id: 'office', name: 'Office' },
                    { id: 'bedroom', name: 'Primary Bedroom' },
                    { id: 'dining', name: 'Dining' },
                ];
            }
        } else {
            rooms = [
                { id: 'living', name: 'Living Room' },
                { id: 'kitchen', name: 'Kitchen' },
                { id: 'office', name: 'Office' },
            ];
        }

        return rooms
            .filter(r => r.name.toLowerCase().includes(query.toLowerCase()))
            .map(r => ({
                id: r.id,
                label: r.name,
                icon: '🏠',
                value: r.name
            }));
    },
    resolve: (item) => ({ room: item.id, roomName: item.value })
});

registry.registerMentionHandler('scene', {
    prefix: '🎬',
    fetch: async (query) => {
        const scenes = [
            { id: 'movie', name: 'Movie Mode', icon: '🎬' },
            { id: 'goodnight', name: 'Goodnight', icon: '🌙' },
            { id: 'welcome', name: 'Welcome Home', icon: '🏠' },
            { id: 'exit_movie', name: 'Exit Movie', icon: '☀️' },
        ];

        return scenes
            .filter(s => s.name.toLowerCase().includes(query.toLowerCase()))
            .map(s => ({
                id: s.id,
                label: s.name,
                icon: s.icon,
                value: s.id
            }));
    },
    onSelect: async (item) => {
        await registry.executeSlashCommand(`/scene ${item.id}`);
    }
});

registry.registerMentionHandler('file', {
    prefix: '📄',
    fetch: async (query) => {
        if (!window.__TAURI__) return [];

        try {
            const files = await window.__TAURI__.core.invoke('search_files', {
                query: query || '*',
                limit: 10
            });
            return files.map(f => ({
                id: f.path,
                label: f.name,
                icon: '📄',
                value: f.path,
                secondary: f.directory
            }));
        } catch {
            return [];
        }
    },
    resolve: (item) => ({ file: item.id })
});

// ============================================================================
// Export
// ============================================================================

// Make globally available
window.CommandRegistry = CommandRegistry;
window.kagamiCommands = registry;

export { CommandRegistry, registry as default };
