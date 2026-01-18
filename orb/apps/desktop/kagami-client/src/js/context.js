/**
 * Context-Aware Interface — 鏡 Kagami
 *
 * Theory of Mind:
 *   Models Tim's intentions based on time, location, and activity.
 *   Surfaces optimal actions and adapts UI accordingly.
 *
 * Time Contexts:
 *   - Morning (5-9am): Start day, coffee
 *   - WorkDay (9am-5pm): Focus mode
 *   - Evening (5-10pm): Movie mode, fireplace
 *   - Night (10pm+): Goodnight
 *
 * η → s → μ → a → η′
 */

const isTauri = window.__TAURI_INTERNALS__ !== undefined;

// ═══════════════════════════════════════════════════════════════
// TIME CONTEXT
// ═══════════════════════════════════════════════════════════════

const TimeContext = {
    EARLY_MORNING: 'EarlyMorning',
    MORNING: 'Morning',
    WORK_DAY: 'WorkDay',
    EVENING: 'Evening',
    LATE_EVENING: 'LateEvening',
    NIGHT: 'Night',
    LATE_NIGHT: 'LateNight',
};

function getCurrentTimeContext() {
    const hour = new Date().getHours();
    if (hour >= 5 && hour < 7) return TimeContext.EARLY_MORNING;
    if (hour >= 7 && hour < 9) return TimeContext.MORNING;
    if (hour >= 9 && hour < 17) return TimeContext.WORK_DAY;
    if (hour >= 17 && hour < 20) return TimeContext.EVENING;
    if (hour >= 20 && hour < 22) return TimeContext.LATE_EVENING;
    if (hour >= 22 && hour < 24) return TimeContext.NIGHT;
    return TimeContext.LATE_NIGHT;
}

function getTimeContextColor() {
    const ctx = getCurrentTimeContext();
    switch (ctx) {
        case TimeContext.EARLY_MORNING:
        case TimeContext.MORNING:
            return 'var(--beacon)';  // Warm amber
        case TimeContext.WORK_DAY:
            return 'var(--grove)';   // Focused green
        case TimeContext.EVENING:
        case TimeContext.LATE_EVENING:
            return 'var(--nexus)';   // Relaxed purple
        case TimeContext.NIGHT:
        case TimeContext.LATE_NIGHT:
            return 'var(--flow)';    // Calm teal
        default:
            return 'var(--crystal)';
    }
}

function getTimeContextGreeting() {
    const ctx = getCurrentTimeContext();
    switch (ctx) {
        case TimeContext.EARLY_MORNING: return 'Good morning';
        case TimeContext.MORNING: return 'Morning';
        case TimeContext.WORK_DAY: return '';
        case TimeContext.EVENING: return 'Good evening';
        case TimeContext.LATE_EVENING: return 'Relaxing';
        case TimeContext.NIGHT: return 'Good night';
        case TimeContext.LATE_NIGHT: return 'Rest well';
        default: return '';
    }
}

// ═══════════════════════════════════════════════════════════════
// SUGGESTED ACTIONS
// ═══════════════════════════════════════════════════════════════

function getPrimaryAction() {
    const ctx = getCurrentTimeContext();
    switch (ctx) {
        case TimeContext.EARLY_MORNING:
        case TimeContext.MORNING:
            return { id: 'start_day', icon: '☀️', label: 'Start Day', action: 'lights_on' };
        case TimeContext.WORK_DAY:
            return { id: 'focus', icon: '🎯', label: 'Focus Mode', action: 'focus' };
        case TimeContext.EVENING:
        case TimeContext.LATE_EVENING:
            return { id: 'movie', icon: '🎬', label: 'Movie Mode', action: 'movie_mode' };
        case TimeContext.NIGHT:
        case TimeContext.LATE_NIGHT:
            return { id: 'goodnight', icon: '🌙', label: 'Goodnight', action: 'goodnight' };
        default:
            return { id: 'ready', icon: '鏡', label: 'Ready', action: null };
    }
}

function getSecondaryActions() {
    const ctx = getCurrentTimeContext();
    switch (ctx) {
        case TimeContext.EARLY_MORNING:
        case TimeContext.MORNING:
            return [
                { id: 'coffee', icon: '☕', label: 'Coffee Time', action: 'coffee' },
            ];
        case TimeContext.WORK_DAY:
            return [
                { id: 'dim', icon: '🌙', label: 'Dim Lights', action: 'lights_dim' },
            ];
        case TimeContext.EVENING:
        case TimeContext.LATE_EVENING:
            return [
                { id: 'fireplace', icon: '🔥', label: 'Fireplace', action: 'fireplace' },
                { id: 'relax', icon: '🛋️', label: 'Relax Mode', action: 'relax' },
            ];
        case TimeContext.NIGHT:
        case TimeContext.LATE_NIGHT:
            return [
                { id: 'lights_off', icon: '💤', label: 'Lights Off', action: 'lights_off' },
            ];
        default:
            return [];
    }
}

// ═══════════════════════════════════════════════════════════════
// CONTEXT STATE
// ═══════════════════════════════════════════════════════════════

class ContextState {
    constructor() {
        this.timeContext = getCurrentTimeContext();
        this.homeStatus = null;
        this.isConnected = false;
        this.safetyScore = null;
        this.listeners = new Set();
    }

    subscribe(callback) {
        this.listeners.add(callback);
        return () => this.listeners.delete(callback);
    }

    notify() {
        for (const cb of this.listeners) {
            try { cb(this); } catch (e) { console.error(e); }
        }
    }

    update(partial) {
        Object.assign(this, partial);
        this.timeContext = getCurrentTimeContext();  // Always recalc
        this.notify();
    }

    getPrimaryAction() {
        // Override if in movie mode
        if (this.homeStatus?.movieMode) {
            return { id: 'exit_movie', icon: '🎬', label: 'Exit Movie', action: 'welcome_home' };
        }
        return getPrimaryAction();
    }

    getSecondaryActions() {
        if (this.homeStatus?.movieMode) {
            return [{ id: 'lights', icon: '💡', label: 'Lights Up', action: 'lights_dim' }];
        }
        return getSecondaryActions();
    }

    getAllSuggestions() {
        return [this.getPrimaryAction(), ...this.getSecondaryActions()];
    }
}

const contextState = new ContextState();

// ═══════════════════════════════════════════════════════════════
// TAURI INTEGRATION
// ═══════════════════════════════════════════════════════════════

async function initContext() {
    if (!isTauri) {
        console.log('Context: Running in browser mode');
        return;
    }

    const { invoke } = await import('@tauri-apps/api/core');
    const { listen } = await import('@tauri-apps/api/event');

    // Subscribe to real-time state updates
    await listen('kagami-state', (event) => {
        contextState.update({
            isConnected: event.payload.connected,
            safetyScore: event.payload.safety_score,
        });
    });

    await listen('home-update', (event) => {
        contextState.update({
            homeStatus: event.payload,
        });
    });

    // Initial fetch
    try {
        const state = await invoke('get_context_state');
        contextState.update({
            isConnected: state.is_connected,
            safetyScore: state.safety_score,
            homeStatus: state.home_status,
        });
    } catch (e) {
        console.warn('Could not fetch initial context:', e);
    }

    // Update time context every minute
    setInterval(() => {
        contextState.update({});  // Triggers recalculation
    }, 60000);
}

async function executeAction(actionId) {
    console.log('Executing action:', actionId);

    if (!isTauri) {
        console.log('Mock execute:', actionId);
        return true;
    }

    const { invoke } = await import('@tauri-apps/api/core');

    try {
        // Map action ID to API call
        switch (actionId) {
            case 'movie_mode':
                await invoke('execute_scene', { scene: 'movie_mode' });
                break;
            case 'goodnight':
                await invoke('execute_scene', { scene: 'goodnight' });
                break;
            case 'welcome_home':
                await invoke('execute_scene', { scene: 'welcome_home' });
                break;
            case 'lights_on':
                await invoke('set_lights', { level: 80 });
                break;
            case 'lights_off':
                await invoke('set_lights', { level: 0 });
                break;
            case 'lights_dim':
                await invoke('set_lights', { level: 30 });
                break;
            case 'coffee':
                await invoke('set_lights', { level: 100, rooms: ['Kitchen'] });
                break;
            case 'focus':
                await invoke('set_lights', { level: 60, rooms: ['Office'] });
                break;
            case 'relax':
                await invoke('set_lights', { level: 40 });
                break;
            case 'fireplace':
                await invoke('toggle_fireplace');
                break;
            default:
                console.warn('Unknown action:', actionId);
                return false;
        }

        return true;
    } catch (e) {
        console.error('Action failed:', e);
        return false;
    }
}

// ═══════════════════════════════════════════════════════════════
// UI RENDERING
// ═══════════════════════════════════════════════════════════════

function renderSuggestions(container) {
    if (!container) return;

    const suggestions = contextState.getAllSuggestions();
    const primary = suggestions[0];
    const secondary = suggestions.slice(1);

    container.innerHTML = `
        <div class="context-suggestions">
            <button class="suggestion-primary" data-action="${primary.action || ''}" ${!primary.action ? 'disabled' : ''}>
                <span class="suggestion-icon">${primary.icon}</span>
                <span class="suggestion-label">${primary.label}</span>
            </button>
            ${secondary.length > 0 ? `
                <div class="suggestion-secondary">
                    ${secondary.map(s => `
                        <button class="suggestion-chip" data-action="${s.action}">
                            <span class="chip-icon">${s.icon}</span>
                            <span class="chip-label">${s.label}</span>
                        </button>
                    `).join('')}
                </div>
            ` : ''}
        </div>
    `;

    // Attach handlers
    container.querySelectorAll('[data-action]').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            const action = e.currentTarget.dataset.action;
            if (!action) return;

            e.currentTarget.classList.add('executing');
            const success = await executeAction(action);
            e.currentTarget.classList.remove('executing');

            if (success) {
                e.currentTarget.classList.add('success');
                setTimeout(() => e.currentTarget.classList.remove('success'), 987);  // standard timing
            }
        });
    });
}

function renderContextIndicator(container) {
    if (!container) return;

    const greeting = getTimeContextGreeting();
    const color = getTimeContextColor();

    container.innerHTML = `
        <div class="context-indicator" style="--context-color: ${color}">
            ${greeting ? `<span class="context-greeting">${greeting}</span>` : ''}
            <span class="context-status">
                ${contextState.isConnected ? '●' : '○'}
                ${contextState.safetyScore !== null ? '' : ''}
            </span>
        </div>
    `;
}

// ═══════════════════════════════════════════════════════════════
// INITIALIZATION
// ═══════════════════════════════════════════════════════════════

async function init() {
    console.log('🧠 Initializing context engine...');

    await initContext();

    // Subscribe to state changes for re-rendering
    contextState.subscribe(() => {
        const suggestionsEl = document.getElementById('context-suggestions');
        const indicatorEl = document.getElementById('context-indicator');

        if (suggestionsEl) renderSuggestions(suggestionsEl);
        if (indicatorEl) renderContextIndicator(indicatorEl);
    });

    // Initial render
    contextState.notify();

    console.log('✓ Context engine ready');
    console.log('  Time context:', getCurrentTimeContext());
    console.log('  Primary action:', getPrimaryAction().label);
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}

// ═══════════════════════════════════════════════════════════════
// EXPORTS
// ═══════════════════════════════════════════════════════════════

export const Context = {
    state: contextState,
    getTimeContext: getCurrentTimeContext,
    getPrimaryAction,
    getSecondaryActions,
    getAllSuggestions: () => contextState.getAllSuggestions(),
    executeAction,
    getColor: getTimeContextColor,
    getGreeting: getTimeContextGreeting,
};

window.Context = Context;

/*
 * 鏡
 * Context is the interface.
 * Time + Location + Activity = Optimal Action
 */
