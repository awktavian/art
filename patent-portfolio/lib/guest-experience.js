/**
 * Guest Experience Model
 * =======================
 *
 * One structured model of guest types and journeys so design and implementation
 * can be checked against it. Exposes current phase and persona from journey state
 * for wayfinding and narrative (e.g. "Return to Rotunda" only in wing;
 * beginner hints only for first-time).
 *
 * h(x) ≥ 0 always
 */

// ═══════════════════════════════════════════════════════════════════════════
// PERSONAS
// ═══════════════════════════════════════════════════════════════════════════

export const PERSONAS = {
    FIRST_TIME: 'first_time',       // Orientation, "what is this place?"
    RESEARCHER: 'researcher',       // Max patents, minimal distraction
    CASUAL_BROWSER: 'casual',      // Short visit, few wings
    ACCESSIBILITY: 'accessibility', // Reduced motion, clear paths, legible signage
    GROUP: 'group',                // Shared focus, possible splitting
    RETURN_VISITOR: 'return'       // Resume journey, new content
};

// ═══════════════════════════════════════════════════════════════════════════
// JOURNEY PHASES (per visit)
// ═══════════════════════════════════════════════════════════════════════════

export const PHASES = {
    ARRIVAL: 'arrival',         // Spawn/orientation, first 10–30s
    ORIENTATION: 'orientation', // Finding map/kiosk, choosing first direction
    CIRCULATION: 'circulation',  // Moving through corridors, decision points
    VIEWING: 'viewing',         // Dwell at artworks, read, interact
    REST: 'rest',               // Pause zones, fatigue
    EXIT: 'exit'                // Leaving or "I'm done"
};

// ═══════════════════════════════════════════════════════════════════════════
// DECISION POINTS AND POSSIBLE NEXT STATES
// ═══════════════════════════════════════════════════════════════════════════

export const DECISION_POINTS = {
    [PHASES.ARRIVAL]: { next: [PHASES.ORIENTATION] },
    [PHASES.ORIENTATION]: { next: [PHASES.CIRCULATION, PHASES.VIEWING] },
    [PHASES.CIRCULATION]: { next: [PHASES.CIRCULATION, PHASES.VIEWING, PHASES.REST, PHASES.EXIT] },
    [PHASES.VIEWING]: { next: [PHASES.CIRCULATION, PHASES.VIEWING, PHASES.REST, PHASES.EXIT] },
    [PHASES.REST]: { next: [PHASES.CIRCULATION, PHASES.VIEWING, PHASES.EXIT] },
    [PHASES.EXIT]: { next: [] }
};

// ═══════════════════════════════════════════════════════════════════════════
// METRICS (for implementation to measure against the model)
// ═══════════════════════════════════════════════════════════════════════════

export const METRICS = {
    TIME_IN_ZONE: 'timeInZone',
    PATENTS_VIEWED: 'patentsViewed',
    PATH_LENGTH: 'pathLength',
    SIGNS_SEEN: 'signsSeen',
    SIGNS_OCCLUDED: 'signsOccluded'
};

// ═══════════════════════════════════════════════════════════════════════════
// INFERENCE FROM JOURNEY STATE
// ═══════════════════════════════════════════════════════════════════════════

const ARRIVAL_DURATION_MS = 30_000;  // First 30 seconds
const ORIENTATION_DURATION_MS = 60_000; // First minute after arrival

/**
 * Infer current journey phase from journey tracker state.
 * @param {import('./journey-tracker.js').JourneyTracker} journeyTracker
 * @returns {string} One of PHASES.*
 */
export function getCurrentPhase(journeyTracker) {
    if (!journeyTracker || !journeyTracker.state) return PHASES.ARRIVAL;
    const state = journeyTracker.state;
    const sessionStart = state.currentSession?.start ?? Date.now();
    const sessionDuration = Date.now() - sessionStart;
    const path = state.currentSession?.path ?? ['rotunda'];
    const zone = journeyTracker.currentZone || path[path.length - 1] || 'rotunda';
    const patentsThisSession = state.currentSession?.patentsViewed ?? 0;

    if (sessionDuration < ARRIVAL_DURATION_MS) return PHASES.ARRIVAL;
    if (sessionDuration < ARRIVAL_DURATION_MS + ORIENTATION_DURATION_MS && path.length <= 1) return PHASES.ORIENTATION;
    if (zone === 'rotunda' && path.length > 2) return PHASES.REST; // Returned to center
    if (patentsThisSession > 0 && zone !== 'rotunda') return PHASES.VIEWING;
    if (path.length > 1 || zone !== 'rotunda') return PHASES.CIRCULATION;
    return PHASES.ORIENTATION;
}

/**
 * Infer current persona from journey tracker state.
 * @param {import('./journey-tracker.js').JourneyTracker} journeyTracker
 * @returns {string} One of PERSONAS.*
 */
export function getCurrentPersona(journeyTracker) {
    if (!journeyTracker || !journeyTracker.state) return PERSONAS.FIRST_TIME;
    const state = journeyTracker.state;
    const totalVisits = state.totalVisits ?? 1;
    const viewedCount = (state.viewedPatents ?? []).length;
    const wingTime = state.wingTime ?? {};
    const totalWingTime = Object.values(wingTime).reduce((a, b) => a + b, 0);
    const interactionStyle = state.interactionStyle ?? 'explorer';

    if (totalVisits === 1 && totalWingTime < 120) return PERSONAS.FIRST_TIME;
    if (totalVisits > 1) return PERSONAS.RETURN_VISITOR;
    if (viewedCount > 10 && interactionStyle === 'reader') return PERSONAS.RESEARCHER;
    if (totalWingTime < 300 && Object.keys(state.visitedWings ?? {}).filter(k => state.visitedWings[k]).length <= 2) return PERSONAS.CASUAL_BROWSER;
    return PERSONAS.FIRST_TIME;
}

/**
 * Whether to show "Return to Rotunda" style cues (only when guest is in a wing).
 * @param {import('./journey-tracker.js').JourneyTracker} journeyTracker
 * @returns {boolean}
 */
export function shouldShowReturnToRotunda(journeyTracker) {
    if (!journeyTracker) return false;
    const zone = journeyTracker.currentZone || 'rotunda';
    return zone !== 'rotunda';
}

/**
 * Whether to show beginner/orientation hints (first-time persona in arrival/orientation).
 * @param {import('./journey-tracker.js').JourneyTracker} journeyTracker
 * @returns {boolean}
 */
export function shouldShowBeginnerHints(journeyTracker) {
    const phase = getCurrentPhase(journeyTracker);
    const persona = getCurrentPersona(journeyTracker);
    return persona === PERSONAS.FIRST_TIME && (phase === PHASES.ARRIVAL || phase === PHASES.ORIENTATION);
}
