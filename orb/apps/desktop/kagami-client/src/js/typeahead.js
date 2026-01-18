/**
 * Kagami Typeahead — Unified Suggestions UI
 *
 * Handles:
 * - Slash command suggestions (/)
 * - @ mention suggestions (@room:, @file:, etc.)
 * - Inline typeahead with keyboard navigation
 */

class TypeaheadController {
    constructor(inputEl, suggestionsEl, options = {}) {
        this.input = inputEl;
        this.suggestions = suggestionsEl;
        this.options = {
            maxSuggestions: options.maxSuggestions || 8,
            debounceMs: options.debounceMs || 100,
            onExecute: options.onExecute || (() => {}),
            onContextChange: options.onContextChange || (() => {}),
            ...options
        };

        this.selectedIndex = -1;
        this.items = [];
        this.mode = null; // 'slash' | 'mention' | 'mention-type' | null
        this.debounceTimer = null;

        this._bindEvents();
    }

    _bindEvents() {
        this.input.addEventListener('input', (e) => this._onInput(e));
        this.input.addEventListener('keydown', (e) => this._onKeyDown(e));
        this.input.addEventListener('blur', () => {
            // Delay hide to allow click on suggestions
            setTimeout(() => this.hide(), 150);
        });
        this.input.addEventListener('focus', () => this._onInput());

        this.suggestions.addEventListener('click', (e) => {
            const item = e.target.closest('[data-index]');
            if (item) {
                const index = parseInt(item.dataset.index, 10);
                this._selectItem(index);
            }
        });
    }

    _onInput() {
        clearTimeout(this.debounceTimer);
        this.debounceTimer = setTimeout(() => this._processInput(), this.options.debounceMs);
    }

    async _processInput() {
        const value = this.input.value;
        const cursorPos = this.input.selectionStart;

        // Check for slash command
        if (value.startsWith('/')) {
            await this._handleSlashCommand(value);
            return;
        }

        // Check for @ mention
        const registry = window.kagamiCommands;
        if (registry) {
            const activeMention = registry.getActiveMention(value, cursorPos);
            if (activeMention) {
                await this._handleMention(activeMention, value, cursorPos);
                return;
            }
        }

        // No special mode
        this.hide();
    }

    async _handleSlashCommand(value) {
        const registry = window.kagamiCommands;
        if (!registry) {
            this.hide();
            return;
        }

        const spaceIndex = value.indexOf(' ');
        const commandPart = spaceIndex > 0 ? value.slice(1, spaceIndex) : value.slice(1);
        const argsPart = spaceIndex > 0 ? value.slice(spaceIndex + 1) : '';

        // If we have a valid command and args, get arg suggestions
        const { command } = registry.parseSlashCommand(value);

        if (command && spaceIndex > 0 && command.suggest) {
            // Argument suggestions
            this.mode = 'slash-args';
            const suggestions = await command.suggest(argsPart);
            this.items = suggestions.map((s, i) => ({
                id: `arg-${i}`,
                label: typeof s === 'string' ? `/${command.name} ${s}` : s.label,
                value: typeof s === 'string' ? `/${command.name} ${s}` : s.value,
                icon: '→',
                replace: true // Replace entire input
            }));
        } else {
            // Command suggestions
            this.mode = 'slash';
            const commands = registry.getSlashCommands();
            this.items = commands
                .filter(c => c.name.startsWith(commandPart.toLowerCase()))
                .slice(0, this.options.maxSuggestions)
                .map(c => ({
                    id: c.name,
                    label: `/${c.name}`,
                    secondary: c.args ? `${c.args} — ${c.description}` : c.description,
                    value: `/${c.name} `,
                    icon: '/',
                    replace: true
                }));
        }

        this._render();
    }

    async _handleMention(mention, value, cursorPos) {
        const registry = window.kagamiCommands;
        if (!registry) {
            this.hide();
            return;
        }

        if (mention.type === null) {
            // Show mention type picker
            this.mode = 'mention-type';
            const types = registry.getMentionTypes();
            this.items = types
                .filter(t => t.startsWith(mention.query.toLowerCase()))
                .map(t => {
                    const handler = registry.mentionHandlers.get(t);
                    return {
                        id: t,
                        label: `@${t}`,
                        secondary: `Search ${t}s`,
                        icon: handler?.prefix || '@',
                        value: `@${t}:`,
                        insertAt: mention.start
                    };
                });
        } else {
            // Show items for specific mention type
            this.mode = 'mention';
            const items = await registry.fetchMentionSuggestions(mention.type, mention.query);
            this.items = items.slice(0, this.options.maxSuggestions).map(item => ({
                ...item,
                value: item.value || item.label,
                insertAt: mention.start
            }));
        }

        this._render();
    }

    _render() {
        if (this.items.length === 0) {
            this.hide();
            return;
        }

        this.selectedIndex = 0;
        this.suggestions.innerHTML = this.items.map((item, i) => `
            <div class="suggestion-item ${i === 0 ? 'selected' : ''}" data-index="${i}">
                <span class="suggestion-icon">${item.icon || ''}</span>
                <div class="suggestion-content">
                    <span class="suggestion-label">${this._escapeHtml(item.label)}</span>
                    ${item.secondary ? `<span class="suggestion-secondary">${this._escapeHtml(item.secondary)}</span>` : ''}
                </div>
            </div>
        `).join('');

        this.suggestions.classList.add('visible');
    }

    hide() {
        this.suggestions.classList.remove('visible');
        this.items = [];
        this.selectedIndex = -1;
        this.mode = null;
    }

    _onKeyDown(e) {
        if (!this.suggestions.classList.contains('visible')) {
            // Handle Enter on empty suggestions - might be a command to execute
            if (e.key === 'Enter' && this.input.value.startsWith('/')) {
                e.preventDefault();
                this._executeCommand();
            }
            return;
        }

        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                this._navigate(1);
                break;
            case 'ArrowUp':
                e.preventDefault();
                this._navigate(-1);
                break;
            case 'Tab':
            case 'Enter':
                e.preventDefault();
                if (this.selectedIndex >= 0) {
                    this._selectItem(this.selectedIndex);
                }
                break;
            case 'Escape':
                e.preventDefault();
                this.hide();
                break;
        }
    }

    _navigate(delta) {
        const newIndex = Math.max(0, Math.min(this.items.length - 1, this.selectedIndex + delta));
        if (newIndex !== this.selectedIndex) {
            this.selectedIndex = newIndex;
            this._updateSelection();
        }
    }

    _updateSelection() {
        const items = this.suggestions.querySelectorAll('.suggestion-item');
        items.forEach((el, i) => {
            el.classList.toggle('selected', i === this.selectedIndex);
        });

        // Scroll into view
        const selected = this.suggestions.querySelector('.suggestion-item.selected');
        if (selected) {
            selected.scrollIntoView({ block: 'nearest' });
        }
    }

    async _selectItem(index) {
        const item = this.items[index];
        if (!item) return;

        if (item.replace) {
            // Replace entire input
            this.input.value = item.value;
            this.input.setSelectionRange(item.value.length, item.value.length);
        } else if (item.insertAt !== undefined) {
            // Replace from insertAt to cursor
            const before = this.input.value.slice(0, item.insertAt);
            const after = this.input.value.slice(this.input.selectionStart);
            this.input.value = before + item.value + ' ' + after.trimStart();
            const newPos = before.length + item.value.length + 1;
            this.input.setSelectionRange(newPos, newPos);
        }

        this.hide();
        this.input.focus();

        // Trigger onSelect callback if it exists
        if (item.onSelect) {
            await item.onSelect(item);
        }

        // Notify context change
        this.options.onContextChange(item);
    }

    async _executeCommand() {
        const value = this.input.value.trim();
        if (!value) return;

        if (value.startsWith('/')) {
            const registry = window.kagamiCommands;
            if (registry) {
                try {
                    const result = await registry.executeSlashCommand(value);
                    this.options.onExecute({ type: 'slash', value, result });
                    this.input.value = '';
                } catch (err) {
                    this.options.onExecute({ type: 'slash', value, error: err.message });
                }
            }
        } else {
            // Natural language input
            this.options.onExecute({ type: 'natural', value });
        }
    }

    _escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }
}

// ============================================================================
// CSS for Typeahead (inject if not present)
// ============================================================================

const TYPEAHEAD_CSS = `
.suggestions-container {
    position: absolute;
    bottom: 100%;
    left: 0;
    right: 0;
    background: var(--surface-elevated, #1e1e1e);
    border: 1px solid var(--border-subtle, #333);
    border-radius: 8px;
    margin-bottom: 4px;
    max-height: 320px;
    overflow-y: auto;
    opacity: 0;
    transform: translateY(8px);
    pointer-events: none;
    transition: opacity 0.15s ease, transform 0.15s ease;
    z-index: 1000;
}

.suggestions-container.visible {
    opacity: 1;
    transform: translateY(0);
    pointer-events: auto;
}

.suggestion-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 14px;
    cursor: pointer;
    transition: background 0.1s ease;
}

.suggestion-item:hover,
.suggestion-item.selected {
    background: var(--surface-hover, #2a2a2a);
}

.suggestion-icon {
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    color: var(--text-muted, #a0a0a0);
    flex-shrink: 0;
}

.suggestion-content {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
}

.suggestion-label {
    font-size: 14px;
    font-weight: 500;
    color: var(--text-primary, #fff);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.suggestion-secondary {
    font-size: 12px;
    color: var(--text-muted, #a0a0a0);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
`;

// Inject CSS if not present
if (!document.getElementById('typeahead-styles')) {
    const style = document.createElement('style');
    style.id = 'typeahead-styles';
    style.textContent = TYPEAHEAD_CSS;
    document.head.appendChild(style);
}

// Export
window.TypeaheadController = TypeaheadController;
export { TypeaheadController };
