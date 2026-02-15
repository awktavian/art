/**
 * Robo-Skip Main
 * ==============
 * Canvas rendering, interaction, dashboard, animations, particles.
 * Depends on engine.js (CurlingEngine global).
 */

'use strict';

// ═══════════════════════════════════════════════════════════════════════════
// CONSTANTS & CONFIG
// ═══════════════════════════════════════════════════════════════════════════

const E = window.CurlingEngine;
const C = E.CurlingConst;

const IS_TOUCH = 'ontouchstart' in window;
const SCALE = 80; // pixels per meter

// Coaching descriptions for shot types — helps players learn strategy
const SHOT_TIPS = {
    'draw':      'Place stone in scoring position',
    'guard':     'Protect a stone in the house',
    'takeout':   'Remove opponent stone from play',
    'peel':      'Remove a guard stone',
    'freeze':    'Park against opponent stone — hard to remove',
    'hit-and-roll': 'Remove opponent + roll to a better spot',
    'raise':     'Promote your own stone closer to the button',
    'tick':      'Nudge a guard to the side',
    'runback':   'Hit your stone into an opponent stone',
    'double':    'Remove two opponent stones at once',
    'come-around': 'Curl behind a guard into scoring position',
};

// Visible area in meters (origin = button)
const VIEW = {
    xMin: -C.SHEET_WIDTH / 2 - 0.3,
    xMax: C.SHEET_WIDTH / 2 + 0.3,
    yMin: C.BACK_LINE_Y - 0.6,
    yMax: C.HOG_LINE_Y + 1.5,
};
const VIEW_W = VIEW.xMax - VIEW.xMin;
const VIEW_H = VIEW.yMax - VIEW.yMin;

// Fibonacci timing in ms
const T = { instant: 89, fast: 144, normal: 233, slow: 377, slower: 610, slowest: 987, glacial: 1597, breathing: 2584 };

// ═══════════════════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════════════════

const state = {
    // Mode: 'freeplay-ai' | 'freeplay-pvp' | 'replay' | 'capture'
    //   freeplay-ai:  sandbox — place both colors, throw yourself or let AI throw on demand
    //   freeplay-pvp: pass-and-play — alternate turns, same device
    //   replay:       browsing historical game in archive
    //   capture:      loaded a position from archive, ready to analyze
    mode: 'freeplay-ai',
    humanTeam: 'red',        // cosmetic — which team the human started as
    aiTeam: 'yellow',        // cosmetic — which team the AI throws for
    aiThinking: false,       // true while AI is computing a throw
    turnNumber: 0,           // stones placed this end (0-15)
    
    stones: [],
    nextStoneId: 1,
    activeTeam: 'red',       // which color to place next
    
    // Game state
    scoreRed: 0,
    scoreYellow: 0,
    currentEnd: 1,
    hammerTeam: 'red',
    
    // Interaction
    dragging: null,          // { stone, offsetX, offsetY }
    hoveredStone: null,
    hoveredShot: null,
    
    // Ghost preview (tap-to-preview, tap-to-confirm)
    ghost: null,             // { x, y, team } — pending stone before confirmation
    
    // Delete confirmation (tap stone once → highlight, tap again → delete)
    pendingDelete: null,     // stone object awaiting confirmation
    pendingDeleteTimer: 0,   // auto-cancel timeout
    
    // Throwing (drag-to-throw from hack zone)
    throwing: null,          // { startX, startY, currentX, currentY }
    sweeping: false,         // true while user is sweeping during animation
    _sweepPoint: null,       // { x, y } canvas coords of sweep brush
    
    // Animation (real-time physics)
    animationFinalStones: null,
    animationCollisions: null,
    
    // Daily puzzle
    puzzle: null,            // { dateStr, stones, activeTeam, ... }
    
    // Analysis
    analyzing: false,
    analysisResults: null,
    
    // Animation
    animating: false,
    animationStones: null,
    animationTrajectories: null,
    animationCollisions: null,
    animationStartTime: 0,
    animationDuration: 0,
    lastAnimationShot: null,
    
    // Undo
    undoStack: [],
    redoStack: [],
    
    // Particles
    particles: [],
    
    // Ripple effects
    ripples: [],
    
    // Canvas
    canvasW: 0,
    canvasH: 0,
    dpr: 1,
    offsetX: 0,
    offsetY: 0,
    
    // Auto-analysis
    autoAnalysisTimer: null,
    
    // Game replay
    replayEndIndex: -1,
    
    // Loaded game context (set when transitioning from playback → capture)
    loadedGameContext: null,
};

// ═══════════════════════════════════════════════════════════════════════════
// LOCALSTORAGE PERSISTENCE
// ═══════════════════════════════════════════════════════════════════════════

const LS_PREFIX = 'roboskip_';
const LS_KEYS = {
    FIRST_VISIT: LS_PREFIX + 'first_visit',
    PREFERENCES: LS_PREFIX + 'preferences',
    GAME_STATE: LS_PREFIX + 'game_state',
    RECENT_GAMES: LS_PREFIX + 'recent_games',
};

function lsGet(key, fallback = null) {
    try {
        const raw = localStorage.getItem(key);
        return raw ? JSON.parse(raw) : fallback;
    } catch (_) { return fallback; }
}

function lsSet(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch (_) {}
}

function saveGameState() {
    lsSet(LS_KEYS.GAME_STATE, {
        stones: state.stones.filter(s => s.active).map(s => ({ x: s.x, y: s.y, team: s.team })),
        scoreRed: state.scoreRed,
        scoreYellow: state.scoreYellow,
        currentEnd: state.currentEnd,
        hammerTeam: state.hammerTeam,
        activeTeam: state.activeTeam,
        nextStoneId: state.nextStoneId,
        savedAt: Date.now(),
    });
}

function restoreGameState() {
    const saved = lsGet(LS_KEYS.GAME_STATE);
    if (!saved || !saved.savedAt) return false;
    // Only restore if saved within last 24 hours
    if (Date.now() - saved.savedAt > 86400000) return false;
    
    state.scoreRed = saved.scoreRed || 0;
    state.scoreYellow = saved.scoreYellow || 0;
    state.currentEnd = saved.currentEnd || 1;
    state.hammerTeam = saved.hammerTeam || 'red';
    state.activeTeam = saved.activeTeam || 'red';
    state.nextStoneId = saved.nextStoneId || 1;
    state.stones = (saved.stones || []).map(s => 
        new E.Stone(s.x, s.y, s.team, `s${state.nextStoneId++}`)
    );
    return state.stones.length > 0;
}

function savePreferences() {
    lsSet(LS_KEYS.PREFERENCES, {
        activeTeam: state.activeTeam,
    });
}

function addRecentGame(game, tourney) {
    const recent = lsGet(LS_KEYS.RECENT_GAMES, []);
    const entry = {
        team1: game.team1.name,
        team2: game.team2.name,
        score1: game.team1.score,
        score2: game.team2.score,
        tourney: tourney || '',
        ts: Date.now(),
    };
    recent.unshift(entry);
    lsSet(LS_KEYS.RECENT_GAMES, recent.slice(0, 10));
}

function isFirstVisit() {
    return !lsGet(LS_KEYS.FIRST_VISIT);
}

function markVisited() {
    lsSet(LS_KEYS.FIRST_VISIT, { ts: Date.now() });
}

// Delete encouragement messages
const DELETE_MESSAGES = [
    'Good reset!',
    'Clean sheet.',
    'Fresh start.',
    'All clear!',
    'Let\'s try again.',
    'Clean slate.',
    'New strategy incoming.',
    'Cleared for takeoff.',
];
function randomDeleteMsg() {
    return DELETE_MESSAGES[Math.floor(Math.random() * DELETE_MESSAGES.length)];
}

// ═══════════════════════════════════════════════════════════════════════════
// AUTO-ANALYSIS (debounced)
// ═══════════════════════════════════════════════════════════════════════════

function scheduleAutoAnalysis() {
    if (state.autoAnalysisTimer) clearTimeout(state.autoAnalysisTimer);
    const activeStones = state.stones.filter(s => s.active);
    if (activeStones.length === 0) return;
    
    // Visual hint that analysis will run
    document.getElementById('ice-container').classList.add('auto-analysis-pending');
    
    state.autoAnalysisTimer = setTimeout(() => {
        document.getElementById('ice-container').classList.remove('auto-analysis-pending');
        if (!state.analyzing && !state.animating && state.stones.filter(s => s.active).length > 0) {
            runAnalysis();
        }
    }, 1200); // 1.2s debounce
}

function cancelAutoAnalysis() {
    if (state.autoAnalysisTimer) {
        clearTimeout(state.autoAnalysisTimer);
        state.autoAnalysisTimer = null;
    }
    document.getElementById('ice-container')?.classList.remove('auto-analysis-pending');
}

// ═══════════════════════════════════════════════════════════════════════════
// CANVAS SETUP
// ═══════════════════════════════════════════════════════════════════════════

const bgCanvas = document.getElementById('ice-bg');
const mainCanvas = document.getElementById('ice-main');
const overlayCanvas = document.getElementById('ice-overlay');
const bgCtx = bgCanvas.getContext('2d');
const mainCtx = mainCanvas.getContext('2d');
const overlayCtx = overlayCanvas.getContext('2d');

function resizeCanvases() {
    const container = document.getElementById('ice-container');
    const rect = container.getBoundingClientRect();
    state.dpr = Math.min(window.devicePixelRatio || 1, 2);
    
    // Calculate canvas size to fit the view with padding
    const availW = rect.width;
    const availH = rect.height;
    
    const scaleX = availW / (VIEW_W * SCALE);
    const scaleY = availH / (VIEW_H * SCALE);
    const fitScale = Math.min(scaleX, scaleY) * 0.92; // 8% padding
    
    const canvasW = Math.floor(VIEW_W * SCALE * fitScale);
    const canvasH = Math.floor(VIEW_H * SCALE * fitScale);
    
    state.canvasW = canvasW;
    state.canvasH = canvasH;
    state.fitScale = fitScale;
    
    // Center in container
    const left = Math.floor((availW - canvasW) / 2);
    const top = Math.floor((availH - canvasH) / 2);
    state.offsetX = left;
    state.offsetY = top;
    
    [bgCanvas, mainCanvas, overlayCanvas].forEach(c => {
        c.width = canvasW * state.dpr;
        c.height = canvasH * state.dpr;
        c.style.width = canvasW + 'px';
        c.style.height = canvasH + 'px';
        c.style.left = left + 'px';
        c.style.top = top + 'px';
        c.getContext('2d').setTransform(state.dpr, 0, 0, state.dpr, 0, 0);
    });
    
    drawBackground();
    drawMain();
}

// ═══════════════════════════════════════════════════════════════════════════
// COORDINATE TRANSFORMS
// ═══════════════════════════════════════════════════════════════════════════

/** World (meters, origin=button) → Canvas pixels */
function worldToCanvas(wx, wy) {
    const px = (wx - VIEW.xMin) * SCALE * state.fitScale;
    const py = (VIEW.yMax - wy) * SCALE * state.fitScale; // flip Y
    return { x: px, y: py };
}

/** Canvas pixels → World meters */
function canvasToWorld(cx, cy) {
    const wx = cx / (SCALE * state.fitScale) + VIEW.xMin;
    const wy = VIEW.yMax - cy / (SCALE * state.fitScale);
    return { x: wx, y: wy };
}

/** Mouse/touch event → Canvas pixels */
function eventToCanvas(e) {
    const rect = mainCanvas.getBoundingClientRect();
    return {
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
    };
}

/** Meters to pixels at current scale */
function mToPx(m) {
    return m * SCALE * state.fitScale;
}

// ═══════════════════════════════════════════════════════════════════════════
// BACKGROUND CANVAS (static, render once)
// ═══════════════════════════════════════════════════════════════════════════

function drawBackground() {
    const ctx = bgCtx;
    const w = state.canvasW;
    const h = state.canvasH;
    
    ctx.clearRect(0, 0, w, h);
    
    // Ice surface — subtle cool-to-warm gradient for depth
    const iceGrad = ctx.createLinearGradient(0, 0, 0, h);
    iceGrad.addColorStop(0, 'rgba(195, 215, 230, 0.90)');
    iceGrad.addColorStop(0.35, 'rgba(210, 228, 240, 0.94)');
    iceGrad.addColorStop(0.65, 'rgba(215, 232, 242, 0.94)');
    iceGrad.addColorStop(1, 'rgba(200, 220, 232, 0.90)');
    
    // Sheet area (clipped to sheet width)
    const sheetLeft = worldToCanvas(-C.SHEET_WIDTH / 2, 0).x;
    const sheetRight = worldToCanvas(C.SHEET_WIDTH / 2, 0).x;
    const sheetTop = worldToCanvas(0, VIEW.yMax).y;
    const sheetBottom = worldToCanvas(0, VIEW.yMin).y;
    
    ctx.save();
    ctx.beginPath();
    ctx.rect(sheetLeft, sheetTop, sheetRight - sheetLeft, sheetBottom - sheetTop);
    ctx.fillStyle = iceGrad;
    ctx.fill();
    
    // Pebble texture (procedural noise)
    drawPebbleTexture(ctx, sheetLeft, sheetTop, sheetRight - sheetLeft, sheetBottom - sheetTop);
    
    ctx.restore();
    
    // Sheet border
    ctx.strokeStyle = 'rgba(100, 130, 150, 0.3)';
    ctx.lineWidth = 1;
    ctx.strokeRect(sheetLeft, sheetTop, sheetRight - sheetLeft, sheetBottom - sheetTop);
    
    // Lines
    drawSheetLines(ctx);
    
    // House rings
    drawHouse(ctx);
}

function drawPebbleTexture(ctx, x, y, w, h) {
    // Subtle noise dots to simulate pebbled ice
    ctx.save();
    ctx.globalAlpha = 0.08;
    const step = 4;
    for (let px = x; px < x + w; px += step) {
        for (let py = y; py < y + h; py += step) {
            const noise = (Math.sin(px * 12.9898 + py * 78.233) * 43758.5453) % 1;
            if (Math.abs(noise) > 0.7) {
                ctx.fillStyle = noise > 0 ? 'rgba(255,255,255,0.5)' : 'rgba(180,200,220,0.5)';
                ctx.fillRect(px, py, 1.5, 1.5);
            }
        }
    }
    ctx.restore();
}

function drawSheetLines(ctx) {
    ctx.save();
    
    // Centre line
    const cl = worldToCanvas(0, VIEW.yMax);
    const cb = worldToCanvas(0, VIEW.yMin);
    ctx.beginPath();
    ctx.moveTo(cl.x, cl.y);
    ctx.lineTo(cb.x, cb.y);
    ctx.strokeStyle = 'rgba(100, 120, 140, 0.25)';
    ctx.lineWidth = 1;
    ctx.stroke();
    
    // Tee line (y=0)
    const tlL = worldToCanvas(-C.SHEET_WIDTH / 2, 0);
    const tlR = worldToCanvas(C.SHEET_WIDTH / 2, 0);
    ctx.beginPath();
    ctx.moveTo(tlL.x, tlL.y);
    ctx.lineTo(tlR.x, tlR.y);
    ctx.strokeStyle = 'rgba(100, 120, 140, 0.3)';
    ctx.lineWidth = 1.5;
    ctx.stroke();
    
    // Back line
    const blL = worldToCanvas(-C.SHEET_WIDTH / 2, C.BACK_LINE_Y);
    const blR = worldToCanvas(C.SHEET_WIDTH / 2, C.BACK_LINE_Y);
    ctx.beginPath();
    ctx.moveTo(blL.x, blL.y);
    ctx.lineTo(blR.x, blR.y);
    ctx.strokeStyle = 'rgba(100, 120, 140, 0.3)';
    ctx.lineWidth = 1.5;
    ctx.stroke();
    
    // Hog line
    const hlL = worldToCanvas(-C.SHEET_WIDTH / 2, C.HOG_LINE_Y);
    const hlR = worldToCanvas(C.SHEET_WIDTH / 2, C.HOG_LINE_Y);
    ctx.beginPath();
    ctx.moveTo(hlL.x, hlL.y);
    ctx.lineTo(hlR.x, hlR.y);
    ctx.strokeStyle = 'rgba(220, 60, 60, 0.3)';
    ctx.lineWidth = 2;
    ctx.stroke();
    
    // Hog line label
    ctx.fillStyle = 'rgba(220, 60, 60, 0.25)';
    ctx.font = `${mToPx(0.15)}px ${getComputedStyle(document.body).fontFamily}`;
    ctx.textAlign = 'right';
    ctx.fillText('HOG', hlR.x - 4, hlR.y - 4);
    
    // FGZ shading (between hog and tee, outside house)
    const hogY = worldToCanvas(0, C.HOG_LINE_Y).y;
    const teeY = worldToCanvas(0, 0).y;
    ctx.fillStyle = 'rgba(103, 212, 228, 0.03)';
    ctx.fillRect(worldToCanvas(-C.SHEET_WIDTH / 2, 0).x, hogY,
                 worldToCanvas(C.SHEET_WIDTH / 2, 0).x - worldToCanvas(-C.SHEET_WIDTH / 2, 0).x,
                 teeY - hogY);
    
    // FGZ label
    ctx.fillStyle = 'rgba(103, 212, 228, 0.15)';
    ctx.font = `${mToPx(0.12)}px ${getComputedStyle(document.body).fontFamily}`;
    ctx.textAlign = 'center';
    const fgzMidY = (hogY + teeY) / 2;
    ctx.fillText('FREE GUARD ZONE', worldToCanvas(0, 0).x, fgzMidY);
    
    ctx.restore();
}

function drawHouse(ctx) {
    const button = worldToCanvas(0, 0);
    ctx.save();
    
    // 12-foot ring (outermost, red) — richer color
    const r12 = mToPx(C.HOUSE_RADIUS_12);
    ctx.beginPath();
    ctx.arc(button.x, button.y, r12, 0, Math.PI * 2);
    const grad12 = ctx.createRadialGradient(button.x, button.y, r12 * 0.7, button.x, button.y, r12);
    grad12.addColorStop(0, 'rgba(200, 60, 60, 0.06)');
    grad12.addColorStop(1, 'rgba(200, 60, 60, 0.14)');
    ctx.fillStyle = grad12;
    ctx.fill();
    ctx.strokeStyle = 'rgba(200, 60, 60, 0.35)';
    ctx.lineWidth = 1.5;
    ctx.stroke();
    
    // 8-foot ring (white)
    const r8 = mToPx(C.HOUSE_RADIUS_8);
    ctx.beginPath();
    ctx.arc(button.x, button.y, r8, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(240, 240, 245, 0.12)';
    ctx.fill();
    ctx.strokeStyle = 'rgba(240, 240, 245, 0.35)';
    ctx.lineWidth = 1.5;
    ctx.stroke();
    
    // 4-foot ring (blue) — richer blue
    const r4 = mToPx(C.HOUSE_RADIUS_4);
    ctx.beginPath();
    ctx.arc(button.x, button.y, r4, 0, Math.PI * 2);
    const grad4 = ctx.createRadialGradient(button.x, button.y, 0, button.x, button.y, r4);
    grad4.addColorStop(0, 'rgba(60, 120, 220, 0.08)');
    grad4.addColorStop(1, 'rgba(60, 100, 200, 0.15)');
    ctx.fillStyle = grad4;
    ctx.fill();
    ctx.strokeStyle = 'rgba(60, 100, 200, 0.35)';
    ctx.lineWidth = 1.5;
    ctx.stroke();
    
    // Button (center) — brighter, slight glow
    const rBtn = mToPx(C.BUTTON_RADIUS);
    ctx.save();
    ctx.shadowColor = 'rgba(240, 240, 250, 0.15)';
    ctx.shadowBlur = 4;
    ctx.beginPath();
    ctx.arc(button.x, button.y, rBtn, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(240, 240, 245, 0.35)';
    ctx.fill();
    ctx.restore();
    ctx.beginPath();
    ctx.arc(button.x, button.y, rBtn, 0, Math.PI * 2);
    ctx.strokeStyle = 'rgba(240, 240, 245, 0.5)';
    ctx.lineWidth = 1;
    ctx.stroke();
    
    // Ring labels
    ctx.fillStyle = 'rgba(0, 0, 0, 0.12)';
    ctx.font = `${mToPx(0.1)}px ${getComputedStyle(document.body).fontFamily}`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('12', button.x + r12 - mToPx(0.15), button.y);
    ctx.fillText('8', button.x + r8 - mToPx(0.12), button.y);
    ctx.fillText('4', button.x + r4 - mToPx(0.1), button.y);
    
    ctx.restore();
}

// ═══════════════════════════════════════════════════════════════════════════
// MAIN CANVAS (stones, trajectories)
// ═══════════════════════════════════════════════════════════════════════════

function drawMain() {
    const ctx = mainCtx;
    const w = state.canvasW;
    const h = state.canvasH;
    
    ctx.clearRect(0, 0, w, h);
    
    // ── MCTS heat map layer (behind everything) ──
    if (state.analysisResults && state.analysisResults.length > 0) {
        // Show top 3 shots as subtle heat clouds
        const topN = Math.min(3, state.analysisResults.length);
        for (let i = topN - 1; i >= 0; i--) {
            const result = state.analysisResults[i];
            const isHoveredResult = state.hoveredShot && 
                state.hoveredShot.name === result.candidate.name;
            // Only show full heat map for hovered shot, subtle for top shot
            if (isHoveredResult) {
                drawMCTSHeatmap(ctx, result, true);
            } else if (i === 0 && !state.hoveredShot) {
                drawMCTSHeatmap(ctx, result, false);
            }
        }
    }
    
    // ── Trajectory preview (hovered or top shot) ──
    if (state.hoveredShot) {
        drawTrajectoryPreview(ctx, state.hoveredShot);
    } else if (state.analysisResults && state.analysisResults.length > 0) {
        const top = state.analysisResults[0];
        if (top) drawTrajectoryPreview(ctx, top.candidate, 0.3);
    }
    
    // ── Stones ──
    for (const stone of state.stones) {
        if (!stone.active) continue;
        drawStone(ctx, stone, stone === state.hoveredStone);
    }
    
    // ── Ghost stone preview ──
    if (state.ghost) {
        drawGhostStone(ctx, state.ghost);
    }
    
    // ── Hack zone indicator (when not throwing) ──
    drawHackZone(ctx);
    
    // ── Throwing guide ──
    if (state.throwing) {
        drawThrowingGuide(ctx, state.throwing);
    }
    
    // ── Hover tooltip ──
    if (state.hoveredStone && !state.dragging) {
        drawStoneTooltip(ctx, state.hoveredStone);
    }
}

function drawStone(ctx, stone, hovered = false) {
    const pos = worldToCanvas(stone.x, stone.y);
    const r = mToPx(C.STONE_RADIUS);
    
    ctx.save();
    
    // Team-tinted shadow
    ctx.beginPath();
    ctx.arc(pos.x + 2, pos.y + 2, r, 0, Math.PI * 2);
    ctx.fillStyle = stone.team === 'red' ? 'rgba(231, 76, 60, 0.12)' : 'rgba(241, 196, 15, 0.12)';
    ctx.fill();
    ctx.beginPath();
    ctx.arc(pos.x + 1.5, pos.y + 1.5, r, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(0, 0, 0, 0.2)';
    ctx.fill();
    
    // Glow (hovered or dragging)
    if (hovered || state.dragging?.stone === stone) {
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, r * 1.6, 0, Math.PI * 2);
        ctx.fillStyle = stone.team === 'red' ? 'rgba(231, 76, 60, 0.15)' : 'rgba(241, 196, 15, 0.15)';
        ctx.fill();
    }
    
    // Stone body (radial gradient for 3D look)
    const isRed = stone.team === 'red';
    const baseColor = isRed ? '#E74C3C' : '#F1C40F';
    const darkColor = isRed ? '#A93226' : '#B7950B';
    const lightColor = isRed ? '#F1948A' : '#F9E154';
    
    const grad = ctx.createRadialGradient(pos.x - r * 0.25, pos.y - r * 0.25, 0, pos.x, pos.y, r);
    grad.addColorStop(0, lightColor);
    grad.addColorStop(0.6, baseColor);
    grad.addColorStop(1, darkColor);
    
    ctx.beginPath();
    ctx.arc(pos.x, pos.y, r, 0, Math.PI * 2);
    ctx.fillStyle = grad;
    ctx.fill();
    
    // Running band (darker ring at edge)
    ctx.beginPath();
    ctx.arc(pos.x, pos.y, r * 0.92, 0, Math.PI * 2);
    ctx.strokeStyle = darkColor;
    ctx.lineWidth = r * 0.12;
    ctx.stroke();
    
    // Handle bar on top — rotates with stone theta
    const theta = stone.theta || 0;
    ctx.save();
    ctx.translate(pos.x, pos.y);
    ctx.rotate(theta);
    
    const handleW = r * 0.6;
    const handleH = r * 0.2;
    ctx.beginPath();
    ctx.roundRect(-handleW / 2, -handleH / 2, handleW, handleH, 2);
    ctx.fillStyle = isRed ? '#C0392B' : '#D4AC0D';
    ctx.fill();
    ctx.strokeStyle = 'rgba(0,0,0,0.2)';
    ctx.lineWidth = 0.5;
    ctx.stroke();
    
    // Highlight (relative to rotated frame)
    ctx.beginPath();
    ctx.arc(-r * 0.2, -r * 0.25, r * 0.25, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(255, 255, 255, 0.2)';
    ctx.fill();
    
    ctx.restore(); // pop rotation
    
    // Pending delete overlay — pulsing red ring + X
    if (state.pendingDelete === stone) {
        const pulse = 0.5 + 0.3 * Math.sin(performance.now() / 150);
        
        // Red ring
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, r * 1.4, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(248, 113, 113, ${pulse})`;
        ctx.lineWidth = 2;
        ctx.stroke();
        
        // X mark
        const xr = r * 0.5;
        ctx.beginPath();
        ctx.moveTo(pos.x - xr, pos.y - xr);
        ctx.lineTo(pos.x + xr, pos.y + xr);
        ctx.moveTo(pos.x + xr, pos.y - xr);
        ctx.lineTo(pos.x - xr, pos.y + xr);
        ctx.strokeStyle = `rgba(248, 113, 113, ${pulse * 1.2})`;
        ctx.lineWidth = 2.5;
        ctx.lineCap = 'round';
        ctx.stroke();
        
        // "tap to delete" label
        ctx.font = `600 ${Math.max(9, r * 0.5)}px "IBM Plex Mono", monospace`;
        ctx.textAlign = 'center';
        ctx.fillStyle = `rgba(248, 113, 113, ${pulse})`;
        ctx.fillText('tap to delete', pos.x, pos.y + r * 1.9);
    }
    
    ctx.restore();
}

function drawGhostStone(ctx, ghost) {
    const pos = worldToCanvas(ghost.x, ghost.y);
    const r = mToPx(C.STONE_RADIUS);
    const isRed = ghost.team === 'red';
    const t = performance.now();
    
    ctx.save();
    
    // Pulsing outer ring
    const pulseR = r * (1.4 + 0.15 * Math.sin(t / 300));
    ctx.beginPath();
    ctx.arc(pos.x, pos.y, pulseR, 0, Math.PI * 2);
    ctx.strokeStyle = isRed ? 'rgba(231, 76, 60, 0.25)' : 'rgba(241, 196, 15, 0.25)';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([4, 4]);
    ctx.lineDashOffset = -(t / 50) % 8;
    ctx.stroke();
    ctx.setLineDash([]);
    
    // Soft glow underneath
    const glow = ctx.createRadialGradient(pos.x, pos.y, 0, pos.x, pos.y, r * 1.8);
    glow.addColorStop(0, isRed ? 'rgba(231, 76, 60, 0.12)' : 'rgba(241, 196, 15, 0.12)');
    glow.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.beginPath();
    ctx.arc(pos.x, pos.y, r * 1.8, 0, Math.PI * 2);
    ctx.fillStyle = glow;
    ctx.fill();
    
    // Ghost stone body (semi-transparent)
    ctx.globalAlpha = 0.5 + 0.1 * Math.sin(t / 400);
    const baseColor = isRed ? '#E74C3C' : '#F1C40F';
    const darkColor = isRed ? '#A93226' : '#B7950B';
    const lightColor = isRed ? '#F1948A' : '#F9E154';
    
    const grad = ctx.createRadialGradient(pos.x - r * 0.25, pos.y - r * 0.25, 0, pos.x, pos.y, r);
    grad.addColorStop(0, lightColor);
    grad.addColorStop(0.6, baseColor);
    grad.addColorStop(1, darkColor);
    
    ctx.beginPath();
    ctx.arc(pos.x, pos.y, r, 0, Math.PI * 2);
    ctx.fillStyle = grad;
    ctx.fill();
    
    // Dashed border
    ctx.globalAlpha = 0.7;
    ctx.beginPath();
    ctx.arc(pos.x, pos.y, r, 0, Math.PI * 2);
    ctx.strokeStyle = isRed ? '#E74C3C' : '#F1C40F';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([3, 3]);
    ctx.stroke();
    ctx.setLineDash([]);
    
    // Distance label below ghost — with background pill
    ctx.globalAlpha = 0.9;
    const d = E.dist(ghost.x, ghost.y, 0, 0);
    const label = E.feetInchesStr(d);
    const inHouse = d <= C.HOUSE_RADIUS_12 + C.STONE_RADIUS;
    ctx.font = `600 ${mToPx(0.11)}px "IBM Plex Mono", monospace`;
    const labelW = ctx.measureText(label).width;
    const labelY = pos.y + r + mToPx(0.16);
    const pillPadH = 6, pillPadV = 3;
    
    // Background pill
    ctx.beginPath();
    ctx.roundRect(pos.x - labelW / 2 - pillPadH, labelY - mToPx(0.055) - pillPadV, labelW + pillPadH * 2, mToPx(0.11) + pillPadV * 2, 4);
    ctx.fillStyle = 'rgba(7, 6, 11, 0.75)';
    ctx.fill();
    
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = inHouse ? (isRed ? '#F1948A' : '#F9E154') : '#8A8680';
    ctx.fillText(label, pos.x, labelY);
    
    ctx.restore();
}

// Continuous ghost animation via a single rAF loop (non-recursive)
let _ghostAnimId = 0;
function startGhostPulse() {
    cancelAnimationFrame(_ghostAnimId);
    function tick() {
        if (!state.ghost) return;
        drawMain();
        _ghostAnimId = requestAnimationFrame(tick);
    }
    _ghostAnimId = requestAnimationFrame(tick);
}

// ═══════════════════════════════════════════════════════════════════════════
// THROWING GUIDE
// ═══════════════════════════════════════════════════════════════════════════

function isInHackZone(wy) {
    // Larger zone on touch devices for easier interaction
    const threshold = IS_TOUCH ? 1.5 : 0.8;
    return wy > C.HOG_LINE_Y - threshold;
}

/**
 * Draw the hack/throw zone indicator when not dragging.
 * Makes it obvious you can throw from the bottom of the sheet.
 */
function drawHackZone(ctx) {
    if (state.throwing || state.ghost || state.animating || state.mode === 'replay') return;
    if (!canPlace()) return;
    
    const hackY = C.HOG_LINE_Y + 1.5;
    const hackPos = worldToCanvas(0, hackY);
    const w = mToPx(C.SHEET_WIDTH);
    
    // Hack circle
    ctx.save();
    ctx.globalAlpha = 0.2 + Math.sin(performance.now() / 1500) * 0.08;
    ctx.beginPath();
    ctx.arc(hackPos.x, hackPos.y, mToPx(0.3), 0, Math.PI * 2);
    ctx.strokeStyle = state.activeTeam === 'red' ? '#E74C3C' : '#F1C40F';
    ctx.lineWidth = 2;
    ctx.setLineDash([4, 3]);
    ctx.stroke();
    ctx.setLineDash([]);
    
    // Label
    ctx.font = `600 9px "IBM Plex Mono", monospace`;
    ctx.textAlign = 'center';
    ctx.fillStyle = 'rgba(103, 212, 228, 0.35)';
    ctx.fillText('DRAG TO THROW', hackPos.x, hackPos.y + mToPx(0.3) + 14);
    
    // Small arrow pointing up
    const arrowY = hackPos.y - mToPx(0.3) - 6;
    ctx.beginPath();
    ctx.moveTo(hackPos.x - 5, arrowY + 4);
    ctx.lineTo(hackPos.x, arrowY);
    ctx.lineTo(hackPos.x + 5, arrowY + 4);
    ctx.strokeStyle = 'rgba(103, 212, 228, 0.3)';
    ctx.lineWidth = 1.5;
    ctx.stroke();
    
    ctx.globalAlpha = 1;
    ctx.restore();
}

function drawThrowingGuide(ctx, throwing) {
    if (!throwing) return;
    const start = worldToCanvas(throwing.startX, throwing.startY);
    const current = worldToCanvas(throwing.currentX, throwing.currentY);
    const isRed = state.activeTeam === 'red';
    const teamFill = isRed ? '#E74C3C' : '#F1C40F';
    const teamFillAlpha = isRed ? 'rgba(231, 76, 60,' : 'rgba(241, 196, 15,';
    
    // Compute throw parameters (match releaseThrow exactly)
    const dragDx = throwing.currentX - throwing.startX;
    const dragDy = throwing.currentY - throwing.startY;
    const dragDist = Math.sqrt(dragDx * dragDx + dragDy * dragDy);
    const speed = E.clamp(dragDist * 0.6, 0.8, 3.5);
    const lateralOffset = throwing.startX - throwing.currentX;
    const curlThreshold = IS_TOUCH ? 0.12 : 0.05;
    const curl = lateralOffset > curlThreshold ? 1 : lateralOffset < -curlThreshold ? -1 : 0;
    
    // Power classification
    let powerLabel, powerColor, powerGlow;
    if (speed < 1.5) {
        powerLabel = 'DRAW'; 
        powerColor = 'rgba(74, 222, 128, 0.9)';
        powerGlow = 'rgba(74, 222, 128, 0.2)';
    } else if (speed < 2.2) {
        powerLabel = 'GUARD'; 
        powerColor = 'rgba(251, 191, 36, 0.9)';
        powerGlow = 'rgba(251, 191, 36, 0.2)';
    } else if (speed < 3.0) {
        powerLabel = 'HIT'; 
        powerColor = 'rgba(251, 146, 60, 0.9)';
        powerGlow = 'rgba(251, 146, 60, 0.2)';
    } else {
        powerLabel = 'PEEL'; 
        powerColor = 'rgba(248, 113, 113, 0.9)';
        powerGlow = 'rgba(248, 113, 113, 0.2)';
    }
    
    const r = mToPx(C.STONE_RADIUS);
    ctx.save();
    
    // ── Stone at hack (origin point) with glow ──
    ctx.save();
    ctx.shadowColor = teamFill;
    ctx.shadowBlur = 12;
    ctx.globalAlpha = 0.6;
    ctx.beginPath();
    ctx.arc(start.x, start.y, r, 0, Math.PI * 2);
    ctx.fillStyle = teamFill;
    ctx.fill();
    ctx.restore();
    
    // Handle bar on origin stone
    ctx.save();
    ctx.globalAlpha = 0.5;
    ctx.beginPath();
    ctx.arc(start.x, start.y, r * 0.55, 0, Math.PI * 2);
    ctx.strokeStyle = 'rgba(255,255,255,0.6)';
    ctx.lineWidth = 1.5;
    ctx.stroke();
    ctx.restore();
    
    // ── Aim line: animated dashes from hack toward drag ──
    ctx.beginPath();
    ctx.moveTo(start.x, start.y);
    ctx.lineTo(current.x, current.y);
    ctx.strokeStyle = `${teamFillAlpha}0.5)`;
    ctx.lineWidth = 2;
    ctx.setLineDash([6, 4]);
    ctx.lineDashOffset = -(performance.now() / 25) % 10;
    ctx.stroke();
    ctx.setLineDash([]);
    
    // ── Predicted trajectory with stone outline at endpoint ──
    if (dragDist > 0.3) {
        const aimAngle = Math.atan2(dragDy, dragDx);
        const travelDist = speed * 4;
        const curlAmount = curl * 0.3 * (travelDist / 8);
        const endX = throwing.startX + Math.cos(aimAngle) * travelDist + curlAmount;
        const endY = throwing.startY + Math.sin(aimAngle) * travelDist;
        const endPos = worldToCanvas(endX, endY);
        
        // Multi-point trajectory curve
        const points = 20;
        ctx.beginPath();
        for (let i = 0; i <= points; i++) {
            const t = i / points;
            const px = start.x + (endPos.x - start.x) * t + curl * mToPx(curlAmount) * t * (1 - t) * 2;
            const py = start.y + (endPos.y - start.y) * t;
            if (i === 0) ctx.moveTo(px, py);
            else ctx.lineTo(px, py);
        }
        
        // Gradient along trajectory
        const tGrad = ctx.createLinearGradient(start.x, start.y, endPos.x, endPos.y);
        tGrad.addColorStop(0, `${teamFillAlpha}0.4)`);
        tGrad.addColorStop(1, 'rgba(103, 212, 228, 0.3)');
        ctx.strokeStyle = tGrad;
        ctx.lineWidth = 2;
        ctx.setLineDash([4, 3]);
        ctx.lineDashOffset = -(performance.now() / 20) % 7;
        ctx.stroke();
        ctx.setLineDash([]);
        
        // Stone outline at estimated endpoint
        ctx.save();
        ctx.globalAlpha = 0.35 + Math.sin(performance.now() / 300) * 0.1;
        ctx.beginPath();
        ctx.arc(endPos.x, endPos.y, r, 0, Math.PI * 2);
        ctx.strokeStyle = teamFill;
        ctx.lineWidth = 2;
        ctx.setLineDash([3, 2]);
        ctx.stroke();
        ctx.setLineDash([]);
        
        // Crosshair at endpoint
        const ch = 6;
        ctx.beginPath();
        ctx.moveTo(endPos.x - ch, endPos.y);
        ctx.lineTo(endPos.x + ch, endPos.y);
        ctx.moveTo(endPos.x, endPos.y - ch);
        ctx.lineTo(endPos.x, endPos.y + ch);
        ctx.strokeStyle = 'rgba(103, 212, 228, 0.45)';
        ctx.lineWidth = 1;
        ctx.stroke();
        ctx.restore();
    }
    
    // ── Power bar (left of hack, vertical, with gradient and glow) ──
    const barX = start.x - 40;
    const barH = 90;
    const barY = start.y - barH / 2;
    const barW = 8;
    const fillRatio = E.clamp(speed / 3.5, 0, 1);
    const fillH = barH * fillRatio;
    
    // Bar shadow/glow
    ctx.save();
    ctx.shadowColor = powerColor;
    ctx.shadowBlur = fillRatio > 0.7 ? 8 : 0;
    
    // Bar track
    ctx.beginPath();
    ctx.roundRect(barX, barY, barW, barH, 4);
    ctx.fillStyle = 'rgba(7, 6, 11, 0.7)';
    ctx.strokeStyle = 'rgba(103, 212, 228, 0.15)';
    ctx.lineWidth = 0.5;
    ctx.fill();
    ctx.stroke();
    
    // Bar fill gradient
    const barGrad = ctx.createLinearGradient(0, barY + barH, 0, barY);
    barGrad.addColorStop(0, 'rgba(74, 222, 128, 0.9)');
    barGrad.addColorStop(0.4, 'rgba(251, 191, 36, 0.9)');
    barGrad.addColorStop(0.7, 'rgba(251, 146, 60, 0.9)');
    barGrad.addColorStop(1, 'rgba(248, 113, 113, 0.9)');
    
    ctx.beginPath();
    ctx.roundRect(barX, barY + barH - fillH, barW, fillH, 4);
    ctx.fillStyle = barGrad;
    ctx.fill();
    ctx.restore();
    
    // Tick marks on power bar
    const ticks = [
        { y: 0, label: '' },
        { y: 1.5 / 3.5, label: '' },
        { y: 2.2 / 3.5, label: '' },
        { y: 3.0 / 3.5, label: '' },
    ];
    ctx.strokeStyle = 'rgba(103, 212, 228, 0.2)';
    ctx.lineWidth = 0.5;
    ticks.forEach(t => {
        const ty = barY + barH - barH * t.y;
        ctx.beginPath();
        ctx.moveTo(barX - 2, ty);
        ctx.lineTo(barX + barW + 2, ty);
        ctx.stroke();
    });
    
    // Power label above bar
    ctx.font = `700 11px "IBM Plex Mono", monospace`;
    ctx.textAlign = 'center';
    ctx.fillStyle = powerColor;
    ctx.fillText(powerLabel, barX + barW / 2, barY - 8);
    
    // Speed value below bar
    ctx.font = `500 9px "IBM Plex Mono", monospace`;
    ctx.fillStyle = 'rgba(103, 212, 228, 0.5)';
    ctx.fillText(`${speed.toFixed(1)} m/s`, barX + barW / 2, barY + barH + 14);
    
    // ── Curl indicator (right of hack) ──
    const curlX = start.x + 35;
    const curlY = start.y;
    
    if (curl !== 0) {
        // Curl arc arrow
        ctx.save();
        ctx.beginPath();
        const arcR = 14;
        const startAngle = curl > 0 ? -Math.PI * 0.7 : -Math.PI * 0.3;
        const endAngle = curl > 0 ? -Math.PI * 0.3 : -Math.PI * 0.7;
        ctx.arc(curlX, curlY, arcR, startAngle, endAngle, curl < 0);
        ctx.strokeStyle = 'rgba(103, 212, 228, 0.6)';
        ctx.lineWidth = 2;
        ctx.stroke();
        
        // Arrowhead
        const tipAngle = endAngle;
        const tipX = curlX + Math.cos(tipAngle) * arcR;
        const tipY = curlY + Math.sin(tipAngle) * arcR;
        const arrowAngle = tipAngle + (curl > 0 ? Math.PI / 2 : -Math.PI / 2);
        ctx.beginPath();
        ctx.moveTo(tipX, tipY);
        ctx.lineTo(tipX + Math.cos(arrowAngle - 0.5) * 5, tipY + Math.sin(arrowAngle - 0.5) * 5);
        ctx.moveTo(tipX, tipY);
        ctx.lineTo(tipX + Math.cos(arrowAngle + 0.5) * 5, tipY + Math.sin(arrowAngle + 0.5) * 5);
        ctx.stroke();
        ctx.restore();
        
        // Label
        ctx.font = `600 9px "IBM Plex Mono", monospace`;
        ctx.fillStyle = 'rgba(103, 212, 228, 0.55)';
        ctx.textAlign = 'center';
        ctx.fillText(curl > 0 ? 'IN-TURN' : 'OUT-TURN', curlX, curlY + arcR + 14);
    } else {
        // No curl: show straight arrow
        ctx.save();
        ctx.globalAlpha = 0.3;
        ctx.font = `500 8px "IBM Plex Mono", monospace`;
        ctx.textAlign = 'center';
        ctx.fillStyle = 'rgba(103, 212, 228, 0.4)';
        ctx.fillText('STRAIGHT', curlX, curlY + 4);
        ctx.restore();
    }
    
    // ── Instruction text (top of canvas, fades after a moment) ──
    if (dragDist < 0.5) {
        ctx.save();
        ctx.globalAlpha = 0.5;
        ctx.font = `500 11px "IBM Plex Mono", monospace`;
        ctx.textAlign = 'center';
        ctx.fillStyle = 'rgba(103, 212, 228, 0.6)';
        const canvasW = ctx.canvas.width / (window.devicePixelRatio || 1);
        ctx.fillText('Drag up to aim · Pull farther for power · Offset for curl', canvasW / 2, 24);
        ctx.restore();
    }
    
    ctx.restore();
}

function drawSweepingEffect(ctx) {
    if (!state.sweeping || !state.animating) return;
    const t = performance.now();
    ctx.save();
    
    // Find the delivery stone's current screen position
    const del = state.animationFinalStones?.find(s => s.id === 'delivery' && s.active);
    const sweepTarget = del ? worldToCanvas(del.x, del.y) : state._sweepPoint;
    
    // Draw at user's sweep point (mouse/finger)
    const cp = state._sweepPoint;
    if (cp) {
        // Wide brush strokes — vigorous sweeping motion
        for (let i = 0; i < 8; i++) {
            const offset = Math.sin(t / 50 + i * 0.9) * 14;
            const alpha = 0.15 + 0.12 * Math.sin(t / 60 + i);
            const wobble = Math.sin(t / 35 + i * 2) * 3;
            ctx.beginPath();
            ctx.moveTo(cp.x - 20 + wobble, cp.y + offset);
            ctx.lineTo(cp.x + 20 + wobble, cp.y + offset);
            ctx.strokeStyle = `rgba(200, 230, 245, ${alpha})`;
            ctx.lineWidth = 2.5;
            ctx.lineCap = 'round';
            ctx.stroke();
        }
        // Ice particle spray from brush
        for (let i = 0; i < 8; i++) {
            const angle = t / 120 + i * 0.785;
            const dist = 10 + Math.sin(t / 80 + i * 1.5) * 8;
            const size = 1 + Math.random() * 1.5;
            ctx.beginPath();
            ctx.arc(cp.x + Math.cos(angle) * dist, cp.y + Math.sin(angle) * dist, size, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(200, 230, 245, ${0.25 + Math.random() * 0.3})`;
            ctx.fill();
        }
    }
    
    // Draw sweep glow near delivery stone — the actual physics effect zone
    if (sweepTarget && del) {
        const r = mToPx(C.STONE_RADIUS);
        // Green friction-reduction aura
        const aura = ctx.createRadialGradient(sweepTarget.x, sweepTarget.y, r, sweepTarget.x, sweepTarget.y, r * 3.5);
        aura.addColorStop(0, `rgba(74, 222, 128, ${0.12 + 0.06 * Math.sin(t / 200)})`);
        aura.addColorStop(0.5, 'rgba(74, 222, 128, 0.04)');
        aura.addColorStop(1, 'rgba(74, 222, 128, 0)');
        ctx.beginPath();
        ctx.arc(sweepTarget.x, sweepTarget.y, r * 3.5, 0, Math.PI * 2);
        ctx.fillStyle = aura;
        ctx.fill();
        
        // Tiny ice crystals spraying ahead of the stone
        const heading = del.speed() > 0.01 ? Math.atan2(del.vy, del.vx) : -Math.PI / 2;
        for (let i = 0; i < 6; i++) {
            const spread = (Math.random() - 0.5) * 1.2;
            const ahead = r * 1.5 + Math.random() * r * 2;
            const cx = sweepTarget.x + Math.cos(heading + spread) * ahead;
            const cy = sweepTarget.y + Math.sin(heading + spread) * ahead;
            ctx.beginPath();
            ctx.arc(cx, cy, 0.8 + Math.random(), 0, Math.PI * 2);
            ctx.fillStyle = `rgba(200, 240, 255, ${0.2 + Math.random() * 0.25})`;
            ctx.fill();
        }
    }
    
    ctx.restore();
}

function drawStoneTooltip(ctx, stone) {
    const pos = worldToCanvas(stone.x, stone.y);
    const r = mToPx(C.STONE_RADIUS);
    const d = stone.distToButton();
    const distText = E.feetInchesStr(d);
    const isRed = stone.team === 'red';
    
    // Determine counting status
    const active = state.stones.filter(s => s.active);
    const counting = E.PositionEval.countingStones(active);
    const stoneEntry = counting.distances?.find(e => e.id === stone.id);
    const isCounting = stoneEntry?.counting ?? false;
    const rank = stoneEntry ? counting.distances.indexOf(stoneEntry) + 1 : null;
    
    // Find placement order (index in stones array)
    const order = state.stones.filter(s => s.active).indexOf(stone) + 1;
    
    // Is this stone in the house?
    const inHouse = stone.isInHouse();
    
    // Build tooltip lines
    const lines = [];
    
    // Line 1: Distance + counting badge
    if (inHouse && rank) {
        lines.push({ text: `${distText}  ${isCounting ? '● counting' : `#${rank}`}`, color: isCounting ? (isRed ? '#F1948A' : '#F9E154') : '#8A8680' });
    } else if (inHouse) {
        lines.push({ text: `${distText}  in house`, color: '#8A8680' });
    } else {
        lines.push({ text: `${distText}  guard`, color: '#8A8680' });
    }
    
    // Line 2: Team + placement order
    lines.push({ text: `${isRed ? 'Red' : 'Yellow'} • stone ${order}`, color: '#666' });
    
    ctx.save();
    
    const fontSize = mToPx(0.11);
    const lineH = fontSize * 1.5;
    const padH = 10, padV = 7;
    const totalH = lines.length * lineH;
    
    // Measure widest line
    ctx.font = `500 ${fontSize}px "IBM Plex Mono", monospace`;
    let maxW = 0;
    for (const line of lines) {
        const w = ctx.measureText(line.text).width;
        if (w > maxW) maxW = w;
    }
    
    const boxW = maxW + padH * 2;
    const boxH = totalH + padV * 2;
    const tipY = pos.y - r - 10 - boxH;
    const tipX = pos.x - boxW / 2;
    
    // Background
    ctx.beginPath();
    ctx.roundRect(tipX, tipY, boxW, boxH, 6);
    ctx.fillStyle = 'rgba(7, 6, 11, 0.9)';
    ctx.fill();
    
    // Team-colored accent line on left
    ctx.beginPath();
    ctx.roundRect(tipX, tipY, 3, boxH, [6, 0, 0, 6]);
    ctx.fillStyle = isRed ? 'rgba(231, 76, 60, 0.7)' : 'rgba(241, 196, 15, 0.7)';
    ctx.fill();
    
    // Border
    ctx.beginPath();
    ctx.roundRect(tipX, tipY, boxW, boxH, 6);
    ctx.strokeStyle = isCounting ? (isRed ? 'rgba(231, 76, 60, 0.3)' : 'rgba(241, 196, 15, 0.3)') : 'rgba(103, 212, 228, 0.12)';
    ctx.lineWidth = 0.5;
    ctx.stroke();
    
    // Pointer triangle
    ctx.beginPath();
    ctx.moveTo(pos.x - 5, tipY + boxH);
    ctx.lineTo(pos.x, tipY + boxH + 5);
    ctx.lineTo(pos.x + 5, tipY + boxH);
    ctx.fillStyle = 'rgba(7, 6, 11, 0.9)';
    ctx.fill();
    
    // Lines
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    for (let i = 0; i < lines.length; i++) {
        ctx.font = i === 0 ? `600 ${fontSize}px "IBM Plex Mono", monospace` : `400 ${fontSize * 0.9}px "IBM Plex Mono", monospace`;
        ctx.fillStyle = lines[i].color;
        ctx.fillText(lines[i].text, tipX + padH + 4, tipY + padV + i * lineH + lineH / 2);
    }
    
    ctx.restore();
}

function drawTrajectoryPreview(ctx, candidate, alpha = 0.7) {
    ctx.save();
    ctx.globalAlpha = alpha;
    
    // Simulate a single clean trajectory for preview
    const simStones = state.stones.filter(s => s.active).map(s => s.clone());
    const delivery = E.Physics.createDelivery({
        targetX: candidate.targetX,
        targetY: candidate.targetY,
        speed: candidate.speed,
        curl: candidate.curl,
        team: state.activeTeam,
        id: 'preview',
    });
    simStones.push(delivery);
    
    const { trajectories, collisions } = E.Physics.simulate(simStones, { recordTrajectory: true });
    
    // Draw trajectory line
    const traj = trajectories.get('preview');
    if (traj && traj.length > 1) {
        ctx.beginPath();
        const first = worldToCanvas(traj[0].x, traj[0].y);
        ctx.moveTo(first.x, first.y);
        
        for (let i = 1; i < traj.length; i++) {
            const p = worldToCanvas(traj[i].x, traj[i].y);
            ctx.lineTo(p.x, p.y);
        }
        
        ctx.strokeStyle = '#67D4E4';
        ctx.lineWidth = 2;
        ctx.setLineDash([6, 4]);
        ctx.lineDashOffset = -(performance.now() / 30) % 10; // animated flow
        ctx.stroke();
        ctx.setLineDash([]);
    }
    
    // Ghost stone at final position
    const finalStone = simStones.find(s => s.id === 'preview');
    if (finalStone && finalStone.active) {
        const pos = worldToCanvas(finalStone.x, finalStone.y);
        const r = mToPx(C.STONE_RADIUS);
        
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, r, 0, Math.PI * 2);
        ctx.fillStyle = state.activeTeam === 'red' ?
            'rgba(231, 76, 60, 0.3)' : 'rgba(241, 196, 15, 0.3)';
        ctx.fill();
        ctx.strokeStyle = state.activeTeam === 'red' ?
            'rgba(231, 76, 60, 0.6)' : 'rgba(241, 196, 15, 0.6)';
        ctx.lineWidth = 1;
        ctx.setLineDash([3, 3]);
        ctx.stroke();
        ctx.setLineDash([]);
    }
    
    // Collision markers
    for (const col of collisions) {
        const cp = worldToCanvas(col.x, col.y);
        ctx.beginPath();
        ctx.arc(cp.x, cp.y, 4, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(255, 255, 255, 0.5)';
        ctx.fill();
    }
    
    // Target marker
    const tp = worldToCanvas(candidate.targetX, candidate.targetY);
    ctx.beginPath();
    ctx.arc(tp.x, tp.y, 4, 0, Math.PI * 2);
    ctx.strokeStyle = '#67D4E4';
    ctx.lineWidth = 1.5;
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(tp.x - 6, tp.y);
    ctx.lineTo(tp.x + 6, tp.y);
    ctx.moveTo(tp.x, tp.y - 6);
    ctx.lineTo(tp.x, tp.y + 6);
    ctx.strokeStyle = 'rgba(103, 212, 228, 0.5)';
    ctx.lineWidth = 0.5;
    ctx.stroke();
    
    ctx.restore();
}

// ═══════════════════════════════════════════════════════════════════════════
// MCTS PROBABILISTIC TRAJECTORY HEAT MAP
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Draw MCTS trial trajectories and endpoint heat map on ice.
 * Shows the probability cloud of where the stone ends up across
 * Monte Carlo trials — like seeing the entire decision tree at once.
 */
function drawMCTSHeatmap(ctx, result, isHovered = false) {
    if (!result || !result.trialEndpoints || result.trialEndpoints.length === 0) return;
    
    const endpoints = result.trialEndpoints;
    const alpha = isHovered ? 0.85 : 0.35;
    
    ctx.save();
    ctx.globalAlpha = alpha;
    
    const teamColor = state.activeTeam === 'red';
    const baseR = teamColor ? 231 : 241;
    const baseG = teamColor ? 76 : 196;
    const baseB = teamColor ? 60 : 15;
    
    // ── 1. Draw trial trajectories (ghostly paths) ──
    for (let i = 0; i < endpoints.length; i++) {
        const trial = endpoints[i];
        if (!trial.trajectory || trial.trajectory.length < 2) continue;
        
        ctx.beginPath();
        const first = worldToCanvas(trial.trajectory[0].x, trial.trajectory[0].y);
        ctx.moveTo(first.x, first.y);
        
        // Draw smooth path — skip some points for performance
        const step = Math.max(1, Math.floor(trial.trajectory.length / 40));
        for (let j = step; j < trial.trajectory.length; j += step) {
            const p = worldToCanvas(trial.trajectory[j].x, trial.trajectory[j].y);
            ctx.lineTo(p.x, p.y);
        }
        // Always include final point
        const last = worldToCanvas(
            trial.trajectory[trial.trajectory.length - 1].x,
            trial.trajectory[trial.trajectory.length - 1].y
        );
        ctx.lineTo(last.x, last.y);
        
        // Fade from brighter to dimmer along path
        const trailAlpha = 0.08 + (i / endpoints.length) * 0.12;
        ctx.strokeStyle = `rgba(${baseR}, ${baseG}, ${baseB}, ${trailAlpha})`;
        ctx.lineWidth = 1.5;
        ctx.stroke();
    }
    
    // ── 2. Draw endpoint heat map (radial glow at each landing spot) ──
    for (let i = 0; i < endpoints.length; i++) {
        const ep = endpoints[i];
        if (!ep.active) continue; // stone went out of play
        
        const pos = worldToCanvas(ep.x, ep.y);
        const r = mToPx(C.STONE_RADIUS);
        
        // Soft glow circle
        const grad = ctx.createRadialGradient(pos.x, pos.y, 0, pos.x, pos.y, r * 2);
        grad.addColorStop(0, `rgba(${baseR}, ${baseG}, ${baseB}, 0.25)`);
        grad.addColorStop(0.5, `rgba(${baseR}, ${baseG}, ${baseB}, 0.08)`);
        grad.addColorStop(1, `rgba(${baseR}, ${baseG}, ${baseB}, 0)`);
        
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, r * 2, 0, Math.PI * 2);
        ctx.fillStyle = grad;
        ctx.fill();
        
        // Dot at center
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, 2, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${baseR}, ${baseG}, ${baseB}, 0.4)`;
        ctx.fill();
    }
    
    // ── 3. Draw aggregate density contour (mean + spread) ──
    const activeEps = endpoints.filter(ep => ep.active);
    if (activeEps.length >= 3) {
        // Compute mean endpoint
        let meanX = 0, meanY = 0;
        for (const ep of activeEps) { meanX += ep.x; meanY += ep.y; }
        meanX /= activeEps.length;
        meanY /= activeEps.length;
        
        // Compute spread (standard deviation)
        let varX = 0, varY = 0;
        for (const ep of activeEps) {
            varX += (ep.x - meanX) ** 2;
            varY += (ep.y - meanY) ** 2;
        }
        const stdX = Math.sqrt(varX / activeEps.length);
        const stdY = Math.sqrt(varY / activeEps.length);
        
        const meanPos = worldToCanvas(meanX, meanY);
        const spreadPxX = mToPx(stdX * 2); // 2-sigma ellipse
        const spreadPxY = mToPx(stdY * 2);
        
        // Draw 2σ confidence ellipse
        ctx.save();
        ctx.beginPath();
        ctx.ellipse(meanPos.x, meanPos.y, Math.max(spreadPxX, 3), Math.max(spreadPxY, 3), 0, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(103, 212, 228, ${isHovered ? 0.4 : 0.15})`;
        ctx.lineWidth = 1;
        ctx.setLineDash([4, 4]);
        ctx.stroke();
        ctx.setLineDash([]);
        
        // Mean marker (crosshair)
        if (isHovered) {
            ctx.beginPath();
            ctx.arc(meanPos.x, meanPos.y, 3, 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(103, 212, 228, 0.6)';
            ctx.fill();
            
            // Success rate label near mean
            ctx.font = `500 ${mToPx(0.1)}px "IBM Plex Mono", monospace`;
            ctx.fillStyle = 'rgba(103, 212, 228, 0.7)';
            ctx.textAlign = 'center';
            ctx.fillText(
                `${Math.round(result.successRate * 100)}% success`,
                meanPos.x,
                meanPos.y - spreadPxY - 8
            );
        }
        ctx.restore();
    }
    
    ctx.restore();
}

// ═══════════════════════════════════════════════════════════════════════════
// OVERLAY CANVAS (particles, effects — every frame)
// ═══════════════════════════════════════════════════════════════════════════

function initParticles() {
    state.particles = [];
    for (let i = 0; i < 30; i++) {
        state.particles.push({
            x: Math.random() * state.canvasW,
            y: Math.random() * state.canvasH,
            size: 1 + Math.random() * 2,
            speed: 0.1 + Math.random() * 0.3,
            angle: Math.random() * Math.PI * 2,
            opacity: 0.1 + Math.random() * 0.2,
            rotation: Math.random() * Math.PI,
            rotSpeed: (Math.random() - 0.5) * 0.01,
        });
    }
}

function drawOverlay(timestamp) {
    const ctx = overlayCtx;
    const w = state.canvasW;
    const h = state.canvasH;
    
    ctx.clearRect(0, 0, w, h);
    
    // Frost particles
    for (const p of state.particles) {
        // Update
        p.x += Math.cos(p.angle) * p.speed;
        p.y += Math.sin(p.angle) * p.speed;
        p.rotation += p.rotSpeed;
        
        // Wrap
        if (p.x < -10) p.x = w + 10;
        if (p.x > w + 10) p.x = -10;
        if (p.y < -10) p.y = h + 10;
        if (p.y > h + 10) p.y = -10;
        
        // Draw crystalline shape
        ctx.save();
        ctx.translate(p.x, p.y);
        ctx.rotate(p.rotation);
        ctx.globalAlpha = p.opacity;
        ctx.fillStyle = '#D0E8F0';
        
        // Six-pointed star (ice crystal)
        ctx.beginPath();
        for (let i = 0; i < 6; i++) {
            const a = (i / 6) * Math.PI * 2;
            const r = p.size;
            const method = i === 0 ? 'moveTo' : 'lineTo';
            ctx[method](Math.cos(a) * r, Math.sin(a) * r);
            ctx.lineTo(Math.cos(a + Math.PI / 6) * r * 0.4, Math.sin(a + Math.PI / 6) * r * 0.4);
        }
        ctx.closePath();
        ctx.fill();
        ctx.restore();
    }
    
    // Ripple effects
    for (let i = state.ripples.length - 1; i >= 0; i--) {
        const rip = state.ripples[i];
        const age = timestamp - rip.startTime;
        const progress = age / rip.duration;
        
        if (progress >= 1) {
            state.ripples.splice(i, 1);
            continue;
        }
        
        ctx.save();
        ctx.beginPath();
        ctx.arc(rip.x, rip.y, rip.maxRadius * progress, 0, Math.PI * 2);
        ctx.strokeStyle = rip.color;
        ctx.lineWidth = 1.5 * (1 - progress);
        ctx.globalAlpha = (1 - progress) * 0.5;
        ctx.stroke();
        ctx.restore();
    }
    
    // Shot animation
    if (state.animating) {
        drawShotAnimation(ctx, timestamp);
    }
    
    requestAnimationFrame(drawOverlay);
}

// ═══════════════════════════════════════════════════════════════════════════
// SHOT ANIMATION
// ═══════════════════════════════════════════════════════════════════════════

function animateShot(candidate) {
    if (state.animating) return;
    if (state.ghost) dismissGhost();
    
    // ── Set up live physics stones ──
    const simStones = state.stones.filter(s => s.active).map(s => s.clone());
    const delivery = E.Physics.createDelivery({
        targetX: candidate.targetX,
        targetY: candidate.targetY,
        speed: candidate.speed,
        curl: candidate.curl,
        team: state.activeTeam,
        id: 'delivery',
    });
    simStones.push(delivery);
    
    // AI auto-sweep: pre-determine if AI should sweep this shot
    // AI sweeps draws/guards/freezes (need weight), skips takeouts/peels (want to stop)
    const isAiShot = state.mode === 'freeplay-ai' && state.activeTeam === state.aiTeam;
    const aiShouldSweep = isAiShot && (
        candidate.type === 'draw' || candidate.type === 'guard' || 
        candidate.type === 'freeze' || candidate.type === 'hit-and-roll'
    );
    
    // Real-time physics state
    playSound('slide');
    state.animating = true;
    state.lastAnimationShot = candidate;
    state.animationFinalStones = simStones; // mutated in-place by stepN
    state.animationCollisions = [];
    
    // Trail history for delivery stone (canvas coords)
    const trailPts = [];
    
    // Physics sub-steps per render frame (~60fps render, 240hz physics = 4 steps/frame)
    const STEPS_PER_FRAME = 4;
    // For fast-forward after all stones stop (or max time)
    let totalPhysicsSteps = 0;
    const maxPhysicsSteps = C.SIM_MAX_TIME / C.SIM_DT;
    
    // Collision effects queue: { x, y, force, renderTime }
    const collisionEffects = [];
    const playedCollisionKeys = new Set();
    
    // Sweep prompt banner
    const sweepBanner = document.createElement('div');
    sweepBanner.className = 'sweep-banner';
    sweepBanner.textContent = 'SWEEP!';
    sweepBanner.style.cssText = `
        position:absolute; top:50%; left:50%; transform:translate(-50%,-50%);
        font-family:"IBM Plex Mono",monospace; font-size:18px; font-weight:700;
        color:rgba(103,212,228,0.7); letter-spacing:3px;
        pointer-events:none; z-index:20; opacity:0; transition:opacity 0.15s;
    `;
    document.getElementById('ice-container')?.appendChild(sweepBanner);
    
    const animStart = performance.now();
    
    const animFrame = () => {
        if (!state.animating) {
            sweepBanner.remove();
            return;
        }
        
        const now = performance.now();
        const renderElapsed = now - animStart;
        
        // ── Step physics forward with live sweep state ──
        // Sweep: player sweeping or AI auto-sweep (while delivery is still moving fast)
        const deliveryStone = simStones.find(s => s.id === 'delivery');
        const deliveryMoving = deliveryStone && deliveryStone.active && deliveryStone.speed() > 0.1;
        const isSweeping = state.sweeping || (aiShouldSweep && deliveryMoving);
        const stepResult = E.Physics.stepN(simStones, STEPS_PER_FRAME, {
            sweepZone: isSweeping ? (s) => s.id === 'delivery' : null,
        });
        totalPhysicsSteps += STEPS_PER_FRAME;
        
        // Show/hide sweep banner
        sweepBanner.style.opacity = isSweeping ? '1' : '0';
        if (isSweeping) sweepBanner.textContent = aiShouldSweep && !state.sweeping ? 'AI SWEEPING' : 'SWEEP!';
        
        // Auto-set sweep point to delivery stone position for AI sweeping visual
        if (aiShouldSweep && deliveryMoving && !state._sweepPoint && deliveryStone) {
            const dp = worldToCanvas(deliveryStone.x, deliveryStone.y);
            state._sweepPoint = { x: dp.x, y: dp.y };
        } else if (aiShouldSweep && deliveryStone && deliveryStone.active) {
            const dp = worldToCanvas(deliveryStone.x, deliveryStone.y);
            state._sweepPoint = { x: dp.x, y: dp.y };
        }
        
        // Collect new collisions
        for (const col of stepResult.collisions) {
            const key = `${col.stoneA}_${col.stoneB}_${totalPhysicsSteps}`;
            if (!playedCollisionKeys.has(key)) {
                playedCollisionKeys.add(key);
                col.renderTime = now;
                collisionEffects.push(col);
                state.animationCollisions.push(col);
                const forceNorm = Math.min(col.force / 3.0, 1.0);
                playCollisionScaled(forceNorm);
                haptic(HAPTIC.collision);
            }
        }
        
        // Record trail for delivery stone
        const del = simStones.find(s => s.id === 'delivery');
        if (del && del.active) {
            const cp = worldToCanvas(del.x, del.y);
            trailPts.push({ x: cp.x, y: cp.y, t: now, swept: isSweeping });
        }
        
        // ── Render ──
        const ctx = mainCtx;
        ctx.clearRect(0, 0, state.canvasW, state.canvasH);
        
        // Draw delivery trail
        if (trailPts.length > 1) {
            ctx.save();
            // Outer glow
            ctx.beginPath();
            ctx.moveTo(trailPts[0].x, trailPts[0].y);
            for (let i = 1; i < trailPts.length; i++) ctx.lineTo(trailPts[i].x, trailPts[i].y);
            ctx.strokeStyle = 'rgba(103, 212, 228, 0.10)';
            ctx.lineWidth = 6;
            ctx.lineCap = 'round';
            ctx.stroke();
            
            // Core trail segments — color-coded by sweep state
            for (let i = 1; i < trailPts.length; i++) {
                const progress = i / trailPts.length;
                const alpha = 0.1 + progress * 0.55;
                const wasSweeping = trailPts[i].swept;
                ctx.beginPath();
                ctx.moveTo(trailPts[i - 1].x, trailPts[i - 1].y);
                ctx.lineTo(trailPts[i].x, trailPts[i].y);
                // Swept segments glow green, normal glow ice blue
                ctx.strokeStyle = wasSweeping
                    ? `rgba(74, 222, 128, ${alpha})`
                    : `rgba(103, 212, 228, ${alpha})`;
                ctx.lineWidth = 1 + progress * 2;
                ctx.lineCap = 'round';
                ctx.stroke();
            }
            
            // Head glow
            const head = trailPts[trailPts.length - 1];
            const hGlow = ctx.createRadialGradient(head.x, head.y, 0, head.x, head.y, 8);
            hGlow.addColorStop(0, isSweeping ? 'rgba(74, 222, 128, 0.5)' : 'rgba(103, 212, 228, 0.5)');
            hGlow.addColorStop(1, 'rgba(103, 212, 228, 0)');
            ctx.beginPath();
            ctx.arc(head.x, head.y, 8, 0, Math.PI * 2);
            ctx.fillStyle = hGlow;
            ctx.fill();
            
            ctx.restore();
        }
        
        // Draw all stones at current live positions
        for (const s of simStones) {
            if (!s.active) continue;
            drawStone(ctx, s, false);
        }
        
        // Draw collision effects (decay over 400ms from render time)
        let shakeX = 0, shakeY = 0;
        for (let ci = collisionEffects.length - 1; ci >= 0; ci--) {
            const col = collisionEffects[ci];
            const timeDiff = (now - col.renderTime) / 1000; // seconds
            if (timeDiff > 0.5) { collisionEffects.splice(ci, 1); continue; }
            
            const forceNorm = Math.min(col.force / 3.0, 1.0);
            const cp = worldToCanvas(col.x, col.y);
            
            // Camera shake
            if (timeDiff < 0.1) {
                const intensity = (1 - timeDiff / 0.1) * (1.5 + forceNorm * 3);
                shakeX += (Math.random() - 0.5) * intensity;
                shakeY += (Math.random() - 0.5) * intensity;
            }
            
            ctx.save();
            
            // Shockwave rings
            for (let ring = 0; ring < 2; ring++) {
                const delay = ring * 0.06;
                const rf = Math.max(0, 1 - (timeDiff - delay) / 0.35);
                if (rf <= 0) continue;
                const maxR = 0.12 + forceNorm * 0.15;
                const ringR = mToPx(0.04 + (1 - rf) * maxR);
                ctx.beginPath();
                ctx.arc(cp.x, cp.y, ringR, 0, Math.PI * 2);
                ctx.strokeStyle = `rgba(255,255,255,${rf * (ring === 0 ? 0.5 : 0.2)})`;
                ctx.lineWidth = (ring === 0 ? 2 : 1.5) * rf;
                ctx.stroke();
            }
            
            // Flash
            if (timeDiff < 0.06) {
                const ff = 1 - timeDiff / 0.06;
                ctx.beginPath();
                ctx.arc(cp.x, cp.y, mToPx(0.08) * ff, 0, Math.PI * 2);
                ctx.fillStyle = `rgba(255,255,255,${ff * 0.7})`;
                ctx.fill();
            }
            
            // Ice chips
            const chipCount = IS_TOUCH ? 5 : 10;
            for (let k = 0; k < chipCount; k++) {
                const seed = (col.renderTime % 10000) + k;
                const angle = ((seed * 7.13) % 1) * Math.PI * 2;
                const spd = 0.05 + ((seed * 3.7) % 1) * 0.15;
                const t2 = timeDiff / 0.4;
                const chipDist = mToPx(spd * t2 * 3);
                const chipFade = Math.max(0, 1 - t2 * 1.5);
                if (chipFade <= 0) continue;
                ctx.beginPath();
                ctx.arc(cp.x + Math.cos(angle) * chipDist, cp.y + Math.sin(angle) * chipDist,
                    (1 + ((seed * 2.3) % 1)) * chipFade, 0, Math.PI * 2);
                ctx.fillStyle = `rgba(200,230,245,${chipFade * 0.6})`;
                ctx.fill();
            }
            ctx.restore();
        }
        
        // Draw sweeping visual effect
        if (isSweeping) {
            drawSweepingEffect(ctx);
        }
        
        // Camera shake
        mainCanvas.style.transform = (shakeX || shakeY) ? `translate(${shakeX}px,${shakeY}px)` : '';
        
        // Safety: check for NaN in any stone position (physics blew up)
        const hasNaN = simStones.some(s => s.active && (!isFinite(s.x) || !isFinite(s.y)));
        if (hasNaN) {
            // Kill bad stones silently
            for (const s of simStones) {
                if (s.active && (!isFinite(s.x) || !isFinite(s.y))) {
                    s.active = false; s.vx = 0; s.vy = 0;
                }
            }
        }
        
        // Continue or finish
        if (stepResult.anyMoving && totalPhysicsSteps < maxPhysicsSteps && !hasNaN) {
            requestAnimationFrame(animFrame);
        } else {
            sweepBanner.remove();
            finishAnimation();
        }
    };
    
    requestAnimationFrame(animFrame);
}

function finishAnimation() {
    if (!state.animating) return;
    mainCanvas.style.transform = '';
    mainCanvas.style.cursor = 'crosshair';
    
    const finalStones = state.animationFinalStones;
    
    // FGZ enforcement: check if any FGZ stones were illegally removed
    const fgzCheck = E.Physics.checkFGZ(
        state.stones,
        finalStones,
        state.turnNumber,
        state.activeTeam
    );
    
    if (fgzCheck.violation) {
        // FGZ violation — restore the removed stones, remove the delivery
        state.animating = false;
        state.animationSnapshots = null;
        state.analysisResults = null;
        showToast(fgzCheck.message, 'warning');
        playSound('collision');
        drawMain();
        return;
    }
    
    // Save undo state
    pushUndo();
    
    // Update stones to final positions
    const newStones = [];
    for (const fs of finalStones) {
        if (!fs.active) continue;
        if (fs.id === 'delivery') {
            const stone = new E.Stone(fs.x, fs.y, fs.team, `s${state.nextStoneId++}`);
            stone.theta = fs.theta || 0;
            newStones.push(stone);
        } else {
            const existing = state.stones.find(s => s.id === fs.id);
            if (existing) {
                existing.x = fs.x;
                existing.y = fs.y;
                existing.active = fs.active;
                existing.theta = fs.theta || 0;
                newStones.push(existing);
            }
        }
    }
    
    state.stones = newStones;
    state.animating = false;
    state.sweeping = false;
    state._sweepPoint = null;
    state.animationFinalStones = null;
    state.animationCollisions = null;
    state.analysisResults = null;
    haptic(HAPTIC.collision);
    
    if (state.mode === 'puzzle') {
        // Puzzle mode — don't advance turns, just redraw
        drawMain();
    } else {
        advanceTurn();
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// SOUND ENGINE — synthesized, no external files
// ═══════════════════════════════════════════════════════════════════════════

const audioCtx = (() => { try { return new (window.AudioContext || window.webkitAudioContext)(); } catch { return null; } })();
let soundEnabled = true;

function playSound(name) {
    if (!audioCtx || !soundEnabled) return;
    // Lazily resume AudioContext on first user gesture
    if (audioCtx.state === 'suspended') audioCtx.resume();
    
    const now = audioCtx.currentTime;
    const gain = audioCtx.createGain();
    gain.connect(audioCtx.destination);
    
    switch (name) {
        case 'preview': {
            // Soft "tink" — high pitched, quiet
            const osc = audioCtx.createOscillator();
            osc.type = 'sine';
            osc.frequency.setValueAtTime(1200, now);
            osc.frequency.exponentialRampToValueAtTime(800, now + 0.08);
            gain.gain.setValueAtTime(0.06, now);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.1);
            osc.connect(gain);
            osc.start(now);
            osc.stop(now + 0.1);
            break;
        }
        case 'place': {
            // Ice thud — low noise burst + subtle tone
            const noise = audioCtx.createBufferSource();
            const buf = audioCtx.createBuffer(1, audioCtx.sampleRate * 0.08, audioCtx.sampleRate);
            const data = buf.getChannelData(0);
            for (let i = 0; i < data.length; i++) data[i] = (Math.random() * 2 - 1) * Math.exp(-i / (data.length * 0.15));
            noise.buffer = buf;
            gain.gain.setValueAtTime(0.1, now);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.08);
            noise.connect(gain);
            noise.start(now);
            // Subtle tone
            const osc = audioCtx.createOscillator();
            const g2 = audioCtx.createGain();
            g2.connect(audioCtx.destination);
            osc.type = 'sine';
            osc.frequency.setValueAtTime(180, now);
            osc.frequency.exponentialRampToValueAtTime(100, now + 0.12);
            g2.gain.setValueAtTime(0.08, now);
            g2.gain.exponentialRampToValueAtTime(0.001, now + 0.12);
            osc.connect(g2);
            osc.start(now);
            osc.stop(now + 0.12);
            break;
        }
        case 'collision': {
            // Crack — sharp noise burst
            const noise = audioCtx.createBufferSource();
            const buf = audioCtx.createBuffer(1, audioCtx.sampleRate * 0.05, audioCtx.sampleRate);
            const data = buf.getChannelData(0);
            for (let i = 0; i < data.length; i++) data[i] = (Math.random() * 2 - 1) * Math.exp(-i / (data.length * 0.08));
            noise.buffer = buf;
            gain.gain.setValueAtTime(0.15, now);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.05);
            noise.connect(gain);
            noise.start(now);
            break;
        }
        case 'slide': {
            // Whoosh — filtered noise sweep
            const noise = audioCtx.createBufferSource();
            const buf = audioCtx.createBuffer(1, audioCtx.sampleRate * 0.3, audioCtx.sampleRate);
            const data = buf.getChannelData(0);
            for (let i = 0; i < data.length; i++) data[i] = (Math.random() * 2 - 1) * 0.5;
            noise.buffer = buf;
            const filter = audioCtx.createBiquadFilter();
            filter.type = 'bandpass';
            filter.frequency.setValueAtTime(2000, now);
            filter.frequency.exponentialRampToValueAtTime(400, now + 0.25);
            filter.Q.value = 2;
            gain.gain.setValueAtTime(0.04, now);
            gain.gain.setValueAtTime(0.06, now + 0.05);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.3);
            noise.connect(filter);
            filter.connect(gain);
            noise.start(now);
            break;
        }
        case 'turn': {
            // Chime — two tones ascending
            const o1 = audioCtx.createOscillator();
            const o2 = audioCtx.createOscillator();
            o1.type = 'sine'; o2.type = 'sine';
            o1.frequency.value = 523; // C5
            o2.frequency.value = 659; // E5
            const g1 = audioCtx.createGain();
            const g2 = audioCtx.createGain();
            g1.connect(audioCtx.destination);
            g2.connect(audioCtx.destination);
            g1.gain.setValueAtTime(0.06, now);
            g1.gain.exponentialRampToValueAtTime(0.001, now + 0.15);
            g2.gain.setValueAtTime(0, now);
            g2.gain.setValueAtTime(0.06, now + 0.08);
            g2.gain.exponentialRampToValueAtTime(0.001, now + 0.2);
            o1.connect(g1); o2.connect(g2);
            o1.start(now); o1.stop(now + 0.15);
            o2.start(now + 0.08); o2.stop(now + 0.2);
            break;
        }
        case 'sweep': {
            // Rhythmic brush sound — filtered noise with LFO modulation
            const noise = audioCtx.createBufferSource();
            const buf = audioCtx.createBuffer(1, audioCtx.sampleRate * 0.2, audioCtx.sampleRate);
            const data = buf.getChannelData(0);
            for (let i = 0; i < data.length; i++) {
                const env = Math.sin((i / data.length) * Math.PI);
                data[i] = (Math.random() * 2 - 1) * env * 0.8;
            }
            noise.buffer = buf;
            const filter = audioCtx.createBiquadFilter();
            filter.type = 'bandpass';
            filter.frequency.setValueAtTime(1200, now);
            filter.frequency.linearRampToValueAtTime(2400, now + 0.1);
            filter.frequency.linearRampToValueAtTime(800, now + 0.2);
            filter.Q.value = 1.5;
            gain.gain.setValueAtTime(0.05, now);
            gain.gain.linearRampToValueAtTime(0.08, now + 0.05);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.2);
            noise.connect(filter);
            filter.connect(gain);
            noise.start(now);
            break;
        }
        case 'throw': {
            // Whoosh with increasing pitch — release snap
            const noise = audioCtx.createBufferSource();
            const buf = audioCtx.createBuffer(1, audioCtx.sampleRate * 0.15, audioCtx.sampleRate);
            const data = buf.getChannelData(0);
            for (let i = 0; i < data.length; i++) data[i] = (Math.random() * 2 - 1) * Math.exp(-i / (data.length * 0.4));
            noise.buffer = buf;
            const filter = audioCtx.createBiquadFilter();
            filter.type = 'bandpass';
            filter.frequency.setValueAtTime(600, now);
            filter.frequency.exponentialRampToValueAtTime(3000, now + 0.1);
            filter.frequency.exponentialRampToValueAtTime(800, now + 0.15);
            filter.Q.value = 3;
            gain.gain.setValueAtTime(0.04, now);
            gain.gain.linearRampToValueAtTime(0.12, now + 0.06);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.15);
            noise.connect(filter);
            filter.connect(gain);
            noise.start(now);
            break;
        }
        case 'endComplete': {
            // Chord — major triad (C-E-G) or minor based on context
            const freqs = [523, 659, 784]; // C5-E5-G5 major
            for (let i = 0; i < freqs.length; i++) {
                const osc = audioCtx.createOscillator();
                const g = audioCtx.createGain();
                g.connect(audioCtx.destination);
                osc.type = 'sine';
                osc.frequency.value = freqs[i];
                g.gain.setValueAtTime(0, now + i * 0.04);
                g.gain.linearRampToValueAtTime(0.05, now + i * 0.04 + 0.02);
                g.gain.exponentialRampToValueAtTime(0.001, now + 0.6);
                osc.connect(g);
                osc.start(now + i * 0.04);
                osc.stop(now + 0.6);
            }
            break;
        }
        case 'score': {
            // Ascending arpeggio — C5, E5, G5, C6
            const notes = [523, 659, 784, 1047];
            for (let i = 0; i < notes.length; i++) {
                const osc = audioCtx.createOscillator();
                const g = audioCtx.createGain();
                g.connect(audioCtx.destination);
                osc.type = 'sine';
                osc.frequency.value = notes[i];
                const t = now + i * 0.07;
                g.gain.setValueAtTime(0, t);
                g.gain.linearRampToValueAtTime(0.06, t + 0.02);
                g.gain.exponentialRampToValueAtTime(0.001, t + 0.2);
                osc.connect(g);
                osc.start(t);
                osc.stop(t + 0.2);
            }
            break;
        }
    }
}

/**
 * Play collision sound scaled by impact force.
 * @param {number} force - Relative velocity at impact (0-1 normalized)
 */
function playCollisionScaled(force) {
    if (!audioCtx || !soundEnabled) return;
    if (audioCtx.state === 'suspended') audioCtx.resume();
    
    const now = audioCtx.currentTime;
    const gain = audioCtx.createGain();
    gain.connect(audioCtx.destination);
    
    const noise = audioCtx.createBufferSource();
    const duration = 0.03 + force * 0.04; // longer for harder hits
    const buf = audioCtx.createBuffer(1, audioCtx.sampleRate * duration, audioCtx.sampleRate);
    const data = buf.getChannelData(0);
    for (let i = 0; i < data.length; i++) data[i] = (Math.random() * 2 - 1) * Math.exp(-i / (data.length * 0.08));
    noise.buffer = buf;
    const volume = 0.05 + force * 0.15; // louder for harder hits
    gain.gain.setValueAtTime(volume, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + duration);
    noise.connect(gain);
    noise.start(now);
}

// ═══════════════════════════════════════════════════════════════════════════
// HAPTICS — vibration feedback on mobile
// ═══════════════════════════════════════════════════════════════════════════

function haptic(pattern) {
    try { navigator?.vibrate?.(pattern); } catch {}
}
const HAPTIC = {
    place:    [12],          // light tap
    remove:   [6, 30, 6],   // double-tap poof
    turn:     [8, 60, 15],  // bump on turn pass
    collision:[20],          // thud
    newGame:  [6, 40, 6, 40, 12], // triple pulse
    ai:       [4],           // subtle
};

// ═══════════════════════════════════════════════════════════════════════════
// INTERACTION — UNIFIED STONE PLACEMENT
// ═══════════════════════════════════════════════════════════════════════════

function findStoneAt(wx, wy) {
    const R = C.STONE_RADIUS * 1.5;
    for (let i = state.stones.length - 1; i >= 0; i--) {
        const s = state.stones[i];
        if (!s.active) continue;
        if (E.dist(wx, wy, s.x, s.y) < R) return s;
    }
    return null;
}

function isOnSheet(wx, wy) {
    return Math.abs(wx) <= C.SHEET_WIDTH / 2 + 0.1 &&
           wy >= C.BACK_LINE_Y - 0.3 &&
           wy <= C.HOG_LINE_Y + 0.5;
}

/** Can the current user place a stone right now? */
function canPlace() {
    if (state.animating || state.aiThinking) return false;
    if (state.mode === 'replay') return false;
    if (state.mode === 'freeplay-ai' && state.activeTeam !== state.humanTeam) return false;
    if (state.turnNumber >= 16) return false; // end is over
    return true;
}

/**
 * Show a ghost stone at (wx, wy) — preview before confirming.
 */
function showGhost(wx, wy) {
    // Clear pending delete if any
    if (state.pendingDelete && typeof cancelPendingDelete === 'function') cancelPendingDelete();
    state.ghost = { x: wx, y: wy, team: state.activeTeam };
    haptic(HAPTIC.place);
    playSound('preview');
    drawMain();
    startGhostPulse();
    
    // Show confirm bar
    const bar = document.getElementById('ghost-confirm');
    const actions = document.getElementById('ice-actions');
    if (bar) bar.classList.add('visible');
    if (actions) actions.style.display = 'none';
}

/**
 * Move the ghost to a new position (re-tap ice while ghost is visible).
 */
function moveGhost(wx, wy) {
    if (!state.ghost) return;
    state.ghost.x = wx;
    state.ghost.y = wy;
    haptic([6]);
    drawMain();
}

/**
 * Confirm the ghost — actually place the stone.
 */
function confirmGhost() {
    if (!state.ghost) return;
    const g = state.ghost;
    const cp = worldToCanvas(g.x, g.y);
    
    pushUndo();
    const newStone = new E.Stone(g.x, g.y, g.team, `s${state.nextStoneId++}`);
    state.stones.push(newStone);
    
    const teamColor = g.team === 'red' ? 'rgba(231, 76, 60,' : 'rgba(241, 196, 15,';
    addRipple(cp.x, cp.y, `${teamColor}0.45)`);
    setTimeout(() => addRipple(cp.x, cp.y, `${teamColor}0.2)`), 40);
    haptic(HAPTIC.place);
    playSound('place');
    
    dismissGhost();
    if (state.mode !== 'puzzle') {
        advanceTurn();
    }
}

/**
 * Cancel the ghost preview.
 */
function dismissGhost() {
    state.ghost = null;
    cancelAnimationFrame(_ghostAnimId);
    const bar = document.getElementById('ghost-confirm');
    const actions = document.getElementById('ice-actions');
    if (bar) bar.classList.remove('visible');
    if (actions) actions.style.display = '';
    drawMain();
}

/**
 * Release a throw — compute delivery params from drag and launch.
 */
function releaseThrow() {
    if (!state.throwing) return;
    const t = state.throwing;
    
    const dragDx = t.currentX - t.startX;
    const dragDy = t.currentY - t.startY;
    const dragDist = Math.sqrt(dragDx * dragDx + dragDy * dragDy);
    
    // Need minimum drag to throw (lower on touch for easier use)
    const minDrag = IS_TOUCH ? 0.10 : 0.20;
    if (dragDist < minDrag) {
        state.throwing = null;
        mainCanvas.style.cursor = 'crosshair';
        drawMain();
        showToast('Drag farther to throw', 'info', 1500);
        return;
    }
    
    // Compute delivery parameters — more responsive mapping
    const speed = E.clamp(dragDist * 0.6, 0.8, 3.5);
    const lateralOffset = t.startX - t.currentX;
    // Wider curl deadzone on touch to avoid accidental curl
    const curlThreshold = IS_TOUCH ? 0.12 : 0.05;
    const curl = lateralOffset > curlThreshold ? 1 : lateralOffset < -curlThreshold ? -1 : 1;
    
    // Aim: use drag direction to determine target
    const aimAngle = Math.atan2(dragDy, dragDx);
    const travelDist = speed * 4;
    const targetX = t.startX + Math.cos(aimAngle) * travelDist;
    const targetY = t.startY + Math.sin(aimAngle) * travelDist;
    
    state.throwing = null;
    mainCanvas.style.cursor = 'crosshair';
    
    playSound('throw');
    haptic(HAPTIC.place);
    
    // Create and animate the delivery
    const candidate = {
        type: 'manual',
        name: 'Manual Throw',
        targetX: E.clamp(targetX, -C.SHEET_WIDTH / 2, C.SHEET_WIDTH / 2),
        targetY: E.clamp(targetY, C.BACK_LINE_Y - 1, C.HOG_LINE_Y),
        speed,
        curl,
    };
    
    // Puzzle mode: evaluate the throw as the player's answer
    if (state.mode === 'puzzle' && state.puzzle && !state.puzzle.solved) {
        handlePuzzleShot(candidate);
    }
    
    animateShot(candidate);
}

// Wire confirm/cancel buttons
document.getElementById('ghost-place')?.addEventListener('click', confirmGhost);
document.getElementById('ghost-cancel')?.addEventListener('click', dismissGhost);

// Mobile shots toggle
document.getElementById('mobile-shots-toggle')?.addEventListener('click', () => {
    document.getElementById('mobile-shots')?.classList.toggle('collapsed');
});
document.getElementById('mobile-shots')?.querySelector('.mobile-shots__header')?.addEventListener('click', (e) => {
    if (e.target.closest('.mobile-shots__toggle')) return; // handled above
    document.getElementById('mobile-shots')?.classList.toggle('collapsed');
});

/**
 * Cancel a pending delete.
 */
function cancelPendingDelete() {
    clearTimeout(state.pendingDeleteTimer);
    state.pendingDelete = null;
    cancelAnimationFrame(_pendingDeleteAnimId);
}

/**
 * Animate the pending delete pulse overlay.
 */
let _pendingDeleteAnimId = 0;
function startPendingDeletePulse() {
    cancelAnimationFrame(_pendingDeleteAnimId);
    function tick() {
        if (!state.pendingDelete) return;
        drawMain();
        _pendingDeleteAnimId = requestAnimationFrame(tick);
    }
    _pendingDeleteAnimId = requestAnimationFrame(tick);
}

/**
 * Remove a stone with effects.
 */
function removeStone(stone, cpx, cpy) {
    pushUndo();
    const teamColor = stone.team === 'red' ? 'rgba(231, 76, 60,' : 'rgba(241, 196, 15,';
    for (let i = 0; i < 6; i++) {
        const angle = (i / 6) * Math.PI * 2 + (Math.random() - 0.5) * 0.3;
        const dist = mToPx(0.12) + Math.random() * mToPx(0.1);
        addRipple(cpx + Math.cos(angle) * dist * 0.4, cpy + Math.sin(angle) * dist * 0.4,
                  `${teamColor}${0.15 + Math.random() * 0.2})`, T.normal);
    }
    addRipple(cpx, cpy, `${teamColor}0.4)`, T.slow);
    haptic(HAPTIC.remove);
    
    stone.active = false;
    state.stones = state.stones.filter(s => s.active);
    state.turnNumber = Math.max(0, state.turnNumber - 1);
    state.analysisResults = null; // clear stale analysis
    drawMain();
    updateDashboard();
    saveGameState();
    scheduleAutoAnalysis();
}

/**
 * Advance turn after stone placement or shot animation.
 */
function advanceTurn() {
    state.turnNumber++;
    setActiveTeam(state.activeTeam === 'red' ? 'yellow' : 'red');
    
    drawMain();
    updateDashboard();
    saveGameState();
    showTurnBanner();
    
    playSound('turn');
    
    // End-of-end: 16 stones placed
    if (state.turnNumber >= 16) {
        haptic(HAPTIC.newGame);
        playSound('endComplete');
        showToast('End complete — score and clear to continue', 'info');
        return;
    }
    
    // Always schedule analysis after any placement
    scheduleAutoAnalysis();
    
    // PvP: flash the turn banner for handoff
    if (state.mode === 'freeplay-pvp') {
        haptic(HAPTIC.turn);
        flashTurnHandoff();
    }
    // AI mode: do NOT auto-trigger — user chooses when to let AI throw
}

/**
 * PvP turn handoff — brief screen flash so you know to pass the phone.
 */
function flashTurnHandoff() {
    const banner = document.getElementById('turn-banner');
    if (!banner) return;
    banner.classList.add('handoff');
    setTimeout(() => banner.classList.remove('handoff'), 600);
}

// ── Core click handler ──
function handleIceClick(e) {
    e.preventDefault();
    
    // Block interaction during puzzle result modal
    const puzzleResultEl = document.getElementById('puzzle-result');
    if (puzzleResultEl?.classList.contains('visible')) return;
    
    const canvasRect = mainCanvas.getBoundingClientRect();
    const cp = { x: e.clientX - canvasRect.left, y: e.clientY - canvasRect.top };
    const wp = canvasToWorld(cp.x, cp.y);
    
    // Sweeping: mousedown during animation starts sweep
    if (state.animating) {
        if (!state.sweeping) {
            playSound('sweep');
            haptic([10]);
        }
        state.sweeping = true;
        state._sweepPoint = { x: cp.x, y: cp.y };
        mainCanvas.style.cursor = 'grabbing';
        return;
    }
    
    // Right-click: instant remove (desktop shortcut, always allowed except replay)
    if (e.button === 2 && state.mode !== 'replay') {
        if (state.ghost) { dismissGhost(); return; }
        cancelPendingDelete();
        const stone = findStoneAt(wp.x, wp.y);
        if (stone) removeStone(stone, cp.x, cp.y);
        return;
    }
    
    // Tap existing stone: first tap → mark for delete, second tap → confirm
    const stone = findStoneAt(wp.x, wp.y);
    if (stone && state.mode !== 'replay' && state.mode !== 'puzzle' && !state.ghost) {
        if (state.pendingDelete === stone) {
            // Second tap on the same stone → delete it
            cancelPendingDelete();
            removeStone(stone, cp.x, cp.y);
            return;
        } else {
            // First tap → mark for delete (also enables drag on hold)
            cancelPendingDelete();
            state.pendingDelete = stone;
            state.dragging = { stone, startX: stone.x, startY: stone.y };
            mainCanvas.style.cursor = 'grabbing';
            playSound('preview');
            haptic([6]);
            // Auto-cancel after 3 seconds if no second tap
            state.pendingDeleteTimer = setTimeout(() => {
                state.pendingDelete = null;
                drawMain();
            }, 3000);
            drawMain();
            startPendingDeletePulse();
            return;
        }
    }
    
    // Tap on empty space clears pending delete
    if (state.pendingDelete) {
        cancelPendingDelete();
        drawMain();
    }
    
    if (!canPlace()) return;
    if (!isOnSheet(wp.x, wp.y) && !isInHackZone(wp.y)) return;
    
    // Hack zone: start a throw (drag-to-throw)
    if (isInHackZone(wp.y) && !state.ghost) {
        state.throwing = { startX: wp.x, startY: wp.y, currentX: wp.x, currentY: wp.y };
        mainCanvas.style.cursor = 'ns-resize';
        playSound('preview');
        haptic(HAPTIC.place);
        drawMain();
        return;
    }
    
    // Puzzle mode: throw only, no placement
    if (state.mode === 'puzzle') {
        showToast('Drag from the hack zone to throw!', 'info', 2000);
        return;
    }
    
    // Ghost system: first tap → preview, re-tap → move, double-tap same spot → confirm
    if (state.ghost) {
        const dx = wp.x - state.ghost.x;
        const dy = wp.y - state.ghost.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < C.STONE_RADIUS * 2.5) {
            // Tapped near the ghost — confirm it
            confirmGhost();
        } else {
            // Tapped elsewhere — move the ghost
            moveGhost(wp.x, wp.y);
        }
    } else {
        showGhost(wp.x, wp.y);
    }
}

mainCanvas.addEventListener('mousedown', handleIceClick);

document.getElementById('ice-container').addEventListener('mousedown', (e) => {
    if (e.target === mainCanvas) return;
    const r = mainCanvas.getBoundingClientRect();
    if (e.clientX >= r.left && e.clientX <= r.right && e.clientY >= r.top && e.clientY <= r.bottom) {
        handleIceClick(e);
    }
});

mainCanvas.addEventListener('mousemove', (e) => {
    const cp = eventToCanvas(e);
    const wp = canvasToWorld(cp.x, cp.y);
    
    // Sweeping with mouse during animation (hold mouse button or just move)
    if (state.animating && !state.throwing && !state.dragging) {
        if (e.buttons > 0) {
            // Mouse button held — active sweeping
            if (!state.sweeping) {
                playSound('sweep');
                haptic([10]);
            }
            state.sweeping = true;
            state._sweepPoint = { x: cp.x, y: cp.y };
            mainCanvas.style.cursor = 'grab';
        } else {
            // Just hovering during animation — show sweep cursor hint
            mainCanvas.style.cursor = 'grab';
            state._sweepPoint = { x: cp.x, y: cp.y };
        }
        return;
    }
    
    // Throwing: update drag position
    if (state.throwing) {
        state.throwing.currentX = wp.x;
        state.throwing.currentY = wp.y;
        drawMain();
        return;
    }
    
    if (state.dragging) {
        state.dragging.stone.x = wp.x;
        state.dragging.stone.y = wp.y;
        drawMain();
        return;
    }
    
    const stone = findStoneAt(wp.x, wp.y);
    if (stone !== state.hoveredStone) {
        state.hoveredStone = stone;
        mainCanvas.style.cursor = stone ? 'grab' : (canPlace() ? 'crosshair' : 'default');
        drawMain();
    }
});

mainCanvas.addEventListener('mouseup', (e) => {
    // Stop sweep on mouse release
    if (state.animating && state.sweeping) {
        state.sweeping = false;
        mainCanvas.style.cursor = 'grab';
        return;
    }
    
    // Throwing: release = launch delivery
    if (state.throwing) {
        releaseThrow();
        return;
    }
    
    if (state.dragging) {
        const stone = state.dragging.stone;
        const wp = canvasToWorld(...Object.values(eventToCanvas(e)));
        
        if (!isOnSheet(stone.x, stone.y)) {
            const snapTo = worldToCanvas(state.dragging.startX, state.dragging.startY);
            addRipple(snapTo.x, snapTo.y, 'rgba(103, 212, 228, 0.3)');
            stone.x = state.dragging.startX;
            stone.y = state.dragging.startY;
        } else {
            // Valid position — save undo
            if (stone.x !== state.dragging.startX || stone.y !== state.dragging.startY) {
                pushUndo();
                // Subtle confirmation ripple at new position
                const newPos = worldToCanvas(stone.x, stone.y);
                addRipple(newPos.x, newPos.y, stone.team === 'red'
                    ? 'rgba(231, 76, 60, 0.2)' : 'rgba(241, 196, 15, 0.2)');
            }
        }
        
        state.dragging = null;
        mainCanvas.style.cursor = 'crosshair';
        drawMain();
        updateDashboard();
        saveGameState();
        scheduleAutoAnalysis();
    }
});

mainCanvas.addEventListener('mouseleave', () => {
    if (state.sweeping) {
        state.sweeping = false;
        state._sweepPoint = null;
    }
    if (state.throwing) {
        state.throwing = null;
        drawMain();
    }
    if (state.dragging) {
        state.dragging.stone.x = state.dragging.startX;
        state.dragging.stone.y = state.dragging.startY;
        state.dragging = null;
        mainCanvas.style.cursor = 'crosshair';
        drawMain();
    }
    state.hoveredStone = null;
});

mainCanvas.addEventListener('contextmenu', (e) => e.preventDefault());

// Touch support
mainCanvas.addEventListener('touchstart', (e) => {
    e.preventDefault();
    const touch = e.touches[0];
    const cp = eventToCanvas(touch);
    const wp = canvasToWorld(cp.x, cp.y);
    
    // Touch during animation = start sweeping immediately
    if (state.animating) {
        if (!state.sweeping) {
            playSound('sweep');
            haptic([10]);
        }
        state.sweeping = true;
        state._sweepPoint = { x: cp.x, y: cp.y };
        return;
    }
    
    const stone = findStoneAt(wp.x, wp.y);
    if (stone && !state.ghost && state.mode !== 'replay') {
        if (state.pendingDelete === stone) {
            // Second tap → confirm delete
            cancelPendingDelete();
            removeStone(stone, cp.x, cp.y);
            return;
        } else {
            // First tap → mark for delete + start drag
            cancelPendingDelete();
            state.pendingDelete = stone;
            state.dragging = { stone, startX: stone.x, startY: stone.y };
            playSound('preview');
            haptic([6]);
            state.pendingDeleteTimer = setTimeout(() => {
                state.pendingDelete = null;
                drawMain();
            }, 3000);
            drawMain();
            startPendingDeletePulse();
            return;
        }
    }
    
    // Tap empty space clears pending delete
    if (state.pendingDelete) {
        cancelPendingDelete();
        drawMain();
    }
    
    if (!canPlace() || (!isOnSheet(wp.x, wp.y) && !isInHackZone(wp.y))) return;
    
    // Hack zone: start throw
    if (isInHackZone(wp.y) && !state.ghost) {
        state.throwing = { startX: wp.x, startY: wp.y, currentX: wp.x, currentY: wp.y };
        playSound('preview');
        haptic(HAPTIC.place);
        drawMain();
        return;
    }
    
    // Puzzle mode: throw only
    if (state.mode === 'puzzle') return;
    
    if (state.ghost) {
        const dx = wp.x - state.ghost.x;
        const dy = wp.y - state.ghost.y;
        if (Math.sqrt(dx * dx + dy * dy) < C.STONE_RADIUS * 2.5) {
            confirmGhost();
        } else {
            moveGhost(wp.x, wp.y);
        }
    } else {
        showGhost(wp.x, wp.y);
    }
}, { passive: false });

mainCanvas.addEventListener('touchmove', (e) => {
    e.preventDefault();
    const touch = e.touches[0];
    const wp = canvasToWorld(...Object.values(eventToCanvas(touch)));
    
    // Throwing drag
    if (state.throwing) {
        state.throwing.currentX = wp.x;
        state.throwing.currentY = wp.y;
        drawMain();
        return;
    }
    
    // Sweeping during animation
    if (state.animating && !state.dragging) {
        const cp = eventToCanvas(touch);
        if (!state.sweeping) {
            playSound('sweep');
            haptic([10]);
        }
        state.sweeping = true;
        state._sweepPoint = { x: cp.x, y: cp.y };
        return;
    }
    
    if (!state.dragging) return;
    state.dragging.stone.x = wp.x;
    state.dragging.stone.y = wp.y;
    drawMain();
}, { passive: false });

mainCanvas.addEventListener('touchend', () => {
    // Release throw
    if (state.throwing) {
        releaseThrow();
        return;
    }
    
    // Stop sweeping
    state.sweeping = false;
    state._sweepPoint = null;
    
    if (state.dragging) {
        const stone = state.dragging.stone;
        if (!isOnSheet(stone.x, stone.y)) {
            stone.x = state.dragging.startX;
            stone.y = state.dragging.startY;
        }
        state.dragging = null;
        drawMain();
        updateDashboard();
        saveGameState();
        scheduleAutoAnalysis();
    }
});

// ═══════════════════════════════════════════════════════════════════════════
// EFFECTS
// ═══════════════════════════════════════════════════════════════════════════

function addRipple(x, y, color = 'rgba(103, 212, 228, 0.4)', duration = T.normal) {
    state.ripples.push({
        x, y, color,
        startTime: performance.now(),
        duration,
        maxRadius: mToPx(0.4),
    });
}

// ═══════════════════════════════════════════════════════════════════════════
// UNDO / REDO
// ═══════════════════════════════════════════════════════════════════════════

function pushUndo() {
    state.undoStack.push(state.stones.map(s => s.clone()));
    state.redoStack = [];
    document.getElementById('btn-undo').disabled = false;
}

function undo() {
    if (state.animating || state.aiThinking) {
        showToast('Wait for the shot to finish', 'warning');
        return;
    }
    if (state.undoStack.length === 0) {
        showToast('Nothing to undo', 'info');
        return;
    }
    cancelAutoAnalysis();
    state.redoStack.push(state.stones.map(s => s.clone()));
    state.stones = state.undoStack.pop();
    document.getElementById('btn-undo').disabled = state.undoStack.length === 0;
    state.analysisResults = null;

    // Gentle rewind ripple at center
    const center = worldToCanvas(0, 0);
    addRipple(center.x, center.y, 'rgba(103, 212, 228, 0.25)', T.slow);

    drawMain();
    updateDashboard();
    saveGameState();
    scheduleAutoAnalysis();
}

function redo() {
    if (state.redoStack.length === 0) return;
    cancelAutoAnalysis();
    state.undoStack.push(state.stones.map(s => s.clone()));
    state.stones = state.redoStack.pop();
    document.getElementById('btn-undo').disabled = false;
    state.analysisResults = null;
    drawMain();
    updateDashboard();
    saveGameState();
    scheduleAutoAnalysis();
}

// ═══════════════════════════════════════════════════════════════════════════
// DASHBOARD UPDATES
// ═══════════════════════════════════════════════════════════════════════════

function updateDashboard() {
    updateEmptyState();
    updateWPGauge();
    updatePositionSummary();
    updateStoneCount();
    updateAnalysisDetail();
    updateShotsDisplay();
}

function updateEmptyState() {
    const el = document.getElementById('empty-state');
    const hasStones = state.stones.some(s => s.active);
    el.classList.toggle('hidden', hasStones);
}

function updateWPGauge() {
    const scoreDiff = state.scoreRed - state.scoreYellow;
    const endsRemaining = C.ENDS_TOTAL - state.currentEnd + 1;
    
    // WP from red's perspective
    const redHasHammer = state.hammerTeam === 'red';
    const wp = E.WinProbability.get(scoreDiff, endsRemaining, redHasHammer);
    const wpPct = Math.round(wp * 100);
    
    // Animate number
    const numEl = document.getElementById('wp-number');
    const currentVal = parseInt(numEl.textContent) || 50;
    animateNumber(numEl, currentVal, wpPct, T.slow);
    
    // Animate arc — compute arc length from SVG path
    const arc = document.getElementById('wp-arc');
    const arcGlow = document.getElementById('wp-arc-glow');
    const arcLength = arc.getTotalLength(); // exact from SVG
    const dashLen = arcLength * wp;
    arc.style.strokeDasharray = `${dashLen} ${arcLength}`;
    if (arcGlow) arcGlow.style.strokeDasharray = `${dashLen} ${arcLength}`;
    
    // Smooth color blend based on WP value
    let color;
    if (wpPct < 25) color = 'var(--negative)';
    else if (wpPct < 40) color = 'var(--warning)';
    else if (wpPct < 60) color = 'var(--ice)';
    else if (wpPct < 75) color = 'var(--positive)';
    else color = 'var(--positive)';
    arc.style.stroke = color;
    if (arcGlow) arcGlow.style.stroke = color;
    numEl.style.color = color;
    
    // Glow attribute for extreme values
    if (wpPct >= 75) numEl.setAttribute('data-glow', 'high');
    else if (wpPct <= 25) numEl.setAttribute('data-glow', 'low');
    else numEl.removeAttribute('data-glow');
    
    // Shimmer + glow pulse on big change
    const gauge = document.getElementById('wp-gauge');
    if (Math.abs(wpPct - currentVal) > 10) {
        gauge.classList.add('shimmer');
        setTimeout(() => gauge.classList.remove('shimmer'), T.slower);
    }
}

function updatePositionSummary() {
    const el = document.getElementById('position-summary');
    const active = state.stones.filter(s => s.active);
    
    if (active.length === 0) {
        el.innerHTML = '<span class="position-summary__empty">No stones placed</span>';
        return;
    }
    
    const counting = E.PositionEval.countingStones(active);
    
    let html = '';
    
    // Counting header
    if (counting.team) {
        const cls = counting.team === 'red' ? 'red' : 'yellow';
        html += `<div class="position-summary__counting position-summary__counting--${cls}">
            ${counting.team === 'red' ? 'Red' : 'Yellow'} counting ${counting.count}
        </div>`;
    } else {
        html += '<div class="position-summary__counting position-summary__counting--blank">Blank house</div>';
    }
    
    // Distance table
    if (counting.distances && counting.distances.length > 0) {
        html += `<table class="position-summary__table">
            <thead><tr><th></th><th>#</th><th>Dist</th><th></th></tr></thead>
            <tbody>`;
        
        for (let i = 0; i < Math.min(counting.distances.length, 8); i++) {
            const d = counting.distances[i];
            const cls = d.counting ? ' class="counting-row"' : '';
            const dot = `<span class="stone-dot stone-dot--${d.team}"></span>`;
            const badge = d.counting ? '<span class="counting-badge">●</span>' : '';
            html += `<tr${cls}><td>${dot}</td><td>${i + 1}</td><td>${d.distStr}</td><td>${badge}</td></tr>`;
        }
        
        html += '</tbody></table>';
    }
    
    el.innerHTML = html;
}

function updateStoneCount() {
    const count = state.stones.filter(s => s.active).length;
    document.getElementById('stone-count').textContent = `${count} / 16`;
}

function updateAnalysisDetail() {
    const scoreDiff = state.scoreRed - state.scoreYellow;
    const endsRemaining = C.ENDS_TOTAL - state.currentEnd + 1;
    const redHasHammer = state.hammerTeam === 'red';
    
    // Scoring distribution
    const distEl = document.getElementById('score-dist');
    const dist = E.WinProbability.getScoringDist(redHasHammer);
    
    let distHtml = '';
    const maxProb = Math.max(...dist.values());
    
    for (const [k, p] of [...dist.entries()].sort((a, b) => a[0] - b[0])) {
        const heightPct = (p / maxProb) * 100;
        const isPositive = (redHasHammer && k > 0) || (!redHasHammer && k > 0);
        const color = k > 0 ? 'var(--positive)' : k < 0 ? 'var(--negative)' : 'var(--ice)';
        distHtml += `<div class="score-dist-bar">
            <div class="score-dist-bar__fill" style="height:${heightPct}%;background:${color}"></div>
            <span class="score-dist-bar__label">${k > 0 ? '+' : ''}${k}</span>
        </div>`;
    }
    distEl.innerHTML = distHtml;
    
    // Strategic factors
    const factorsEl = document.getElementById('strategic-factors');
    const active = state.stones.filter(s => s.active);
    
    if (active.length > 0) {
        const factors = E.PositionEval.getStrategicFactors(active, 'red');
        factorsEl.innerHTML = `
            <div class="factor-item"><span class="factor-item__label">Red counting</span><span class="factor-item__value">${factors.counting}</span></div>
            <div class="factor-item"><span class="factor-item__label">Yel counting</span><span class="factor-item__value">${factors.opponentCounting}</span></div>
            <div class="factor-item"><span class="factor-item__label">Red in house</span><span class="factor-item__value">${factors.ourInHouse}</span></div>
            <div class="factor-item"><span class="factor-item__label">Yel in house</span><span class="factor-item__value">${factors.theirInHouse}</span></div>
            <div class="factor-item"><span class="factor-item__label">Red guards</span><span class="factor-item__value">${factors.ourGuards}</span></div>
            <div class="factor-item"><span class="factor-item__label">Yel guards</span><span class="factor-item__value">${factors.theirGuards}</span></div>
            <div class="factor-item"><span class="factor-item__label">Evaluation</span><span class="factor-item__value ${factors.evaluation > 0 ? 'factor-item__value--positive' : factors.evaluation < 0 ? 'factor-item__value--negative' : ''}">${factors.evaluation > 0 ? '+' : ''}${factors.evaluation.toFixed(1)}</span></div>
            <div class="factor-item"><span class="factor-item__label">Total stones</span><span class="factor-item__value">${factors.totalStones}</span></div>
        `;
    } else {
        factorsEl.innerHTML = '<span style="color:var(--text-disabled);font-size:0.75rem">Place stones for analysis</span>';
    }
    
    // Blanking analysis
    const blankEl = document.getElementById('blank-analysis');
    const blank = E.WinProbability.blankingAnalysis(scoreDiff, endsRemaining, redHasHammer);
    
    if (redHasHammer && endsRemaining > 0) {
        const verdict = blank.shouldBlank ? 'Blank recommended' : 'Score recommended';
        const cls = blank.shouldBlank ? 'blank' : 'score';
        blankEl.innerHTML = `
            <div class="blank-analysis__verdict blank-analysis__verdict--${cls}">${verdict}</div>
            <div class="blank-analysis__detail">
                Blank (keep hammer): ${(blank.blankWP * 100).toFixed(1)}%<br>
                Score 1 (lose hammer): ${(blank.score1WP * 100).toFixed(1)}%<br>
                Delta: ${blank.delta > 0 ? '+' : ''}${(blank.delta * 100).toFixed(1)}%
            </div>
        `;
    } else {
        blankEl.innerHTML = `<div class="blank-analysis__detail" style="color:var(--text-disabled)">
            ${redHasHammer ? 'Last end — score!' : 'No hammer — try to steal'}
        </div>`;
    }
}

// ── Shot type visual identity ──
const SHOT_TYPE_META = {
    'draw':           { color: '#67D4E4', tag: 'DRAW' },
    'guard':          { color: '#4ADE80', tag: 'GUARD' },
    'takeout':        { color: '#F87171', tag: 'HIT' },
    'peel':           { color: '#FB923C', tag: 'PEEL' },
    'freeze':         { color: '#A78BFA', tag: 'FREEZE' },
    'hit-and-roll':   { color: '#FBBF24', tag: 'H&R' },
    'raise':          { color: '#38BDF8', tag: 'RAISE' },
    'tick':           { color: '#E879F9', tag: 'TICK' },
    'runback':        { color: '#FB7185', tag: 'RUN' },
    'double-takeout': { color: '#F87171', tag: 'DBL' },
    'come-around':    { color: '#2DD4BF', tag: 'C/A' },
};

/**
 * Generate strategic insight text for a shot result.
 * Returns a short phrase explaining WHY this shot matters.
 */
function shotInsight(result) {
    const { candidate, wpDelta, successRate, avgCounting } = result;
    const hasHammer = state.hammerTeam === state.activeTeam;
    const scoreDiff = state.scoreRed - state.scoreYellow;
    const teamSign = state.activeTeam === 'red' ? 1 : -1;
    const relDiff = scoreDiff * teamSign;
    
    if (successRate > 0.90 && wpDelta > 0.01) return 'High confidence play';
    if (successRate < 0.40) return 'High risk, high reward';
    
    if (candidate.type === 'draw' || candidate.type === 'come-around') {
        if (avgCounting > 1.5) return `Likely score ${Math.round(avgCounting)}`;
        if (hasHammer && relDiff >= 0) return 'Build pressure with hammer';
        if (!hasHammer && avgCounting > 0) return 'Set up a steal';
        if (hasHammer) return 'Draw for position';
        return 'Put stone in play';
    }
    if (candidate.type === 'guard') {
        if (hasHammer) return 'Protect scoring position';
        return 'Defensive setup';
    }
    if (candidate.type === 'takeout' || candidate.type === 'peel' || candidate.type === 'double-takeout') {
        if (relDiff > 0 && !hasHammer) return 'Simplify with the lead';
        if (avgCounting < -0.5) return 'Clear the threat';
        return 'Remove opponent stone';
    }
    if (candidate.type === 'freeze') return 'Freeze — hard to remove';
    if (candidate.type === 'hit-and-roll') return 'Remove + reposition';
    if (candidate.type === 'raise') return 'Promote closer to button';
    if (candidate.type === 'tick') return 'Shift guard off-center';
    if (candidate.type === 'runback') return 'Chain reaction hit';
    
    if (wpDelta > 0.03) return 'Strong winning play';
    if (wpDelta > 0) return 'Slight improvement';
    if (wpDelta > -0.01) return 'Maintains position';
    return 'Defensive option';
}

/**
 * SVG donut ring for success rate — compact, scannable.
 */
function successRingSVG(rate, color, size = 30) {
    const r = (size - 4) / 2;
    const circumference = 2 * Math.PI * r;
    const filled = circumference * rate;
    const gap = circumference - filled;
    return `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" class="success-ring">
        <circle cx="${size/2}" cy="${size/2}" r="${r}" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="2.5"/>
        <circle cx="${size/2}" cy="${size/2}" r="${r}" fill="none" stroke="${color}" stroke-width="2.5"
            stroke-dasharray="${filled} ${gap}" stroke-dashoffset="${circumference * 0.25}"
            stroke-linecap="round" opacity="0.85"/>
        <text x="${size/2}" y="${size/2}" text-anchor="middle" dominant-baseline="central"
            fill="var(--text-secondary)" font-family="var(--font-mono)" font-size="8.5" font-weight="600">${Math.round(rate * 100)}</text>
    </svg>`;
}

function updateShotsDisplay() {
    const listEl = document.getElementById('shots-list');
    const mobileListEl = document.getElementById('mobile-shots-list');
    const mobilePanel = document.getElementById('mobile-shots');
    if (!listEl) return;
    
    if (!state.analysisResults || state.analysisResults.length === 0) {
        if (!state.analyzing) {
            const hasStones = state.stones.some(s => s.active);
            if (hasStones) {
                listEl.innerHTML = '<div class="shots-empty"><p>Press <kbd>A</kbd> to analyze this position</p><p style="color:var(--text-tertiary);font-size:11px;margin-top:4px">See optimal shots ranked by win probability</p></div>';
                if (mobileListEl) mobileListEl.innerHTML = '<div class="mobile-shots__empty">Tap Analyze to see shots</div>';
            } else {
                listEl.innerHTML = '<div class="shots-empty"><p>Place stones on the ice to get started</p><p style="color:var(--text-tertiary);font-size:11px;margin-top:4px">Tap ice to place · Drag from hack to throw</p></div>';
                if (mobileListEl) mobileListEl.innerHTML = '<div class="mobile-shots__empty">Place stones first</div>';
            }
            if (mobilePanel) mobilePanel.classList.remove('has-shots');
        }
        return;
    }
    
    const top5 = state.analysisResults.slice(0, 5);
    
    listEl.innerHTML = top5.map((result, i) => {
        const { candidate, wpDelta, successRate, avgWP } = result;
        const typeMeta = SHOT_TYPE_META[candidate.type] || { color: '#67D4E4', tag: '?' };
        const wpPct = (wpDelta * 100).toFixed(1);
        const wpSign = wpDelta > 0 ? '+' : '';
        const wpClass = wpDelta > 0.005 ? 'positive' : wpDelta < -0.005 ? 'negative' : 'neutral';
        const insight = shotInsight(result);
        const avgWpPct = Math.round(avgWP * 100);
        
        return `<div class="shot-card shot-card--type-${candidate.type}" role="listitem" data-shot-idx="${i}" 
                     tabindex="0" aria-label="${candidate.name}: ${wpSign}${wpPct}% win probability"
                     style="--type-color: ${typeMeta.color}">
            <div class="shot-card__left">
                <span class="shot-card__tag">${typeMeta.tag}</span>
                ${successRingSVG(successRate, typeMeta.color)}
            </div>
            <div class="shot-card__info">
                <div class="shot-card__name">${candidate.name}</div>
                <div class="shot-card__insight">${insight}</div>
            </div>
            <div class="shot-card__right">
                <div class="shot-card__wp shot-card__wp--${wpClass}">${wpSign}${wpPct}%</div>
                <div class="shot-card__wp-after">${avgWpPct}% WP</div>
            </div>
            <span class="shot-card__shortcut">${i + 1}</span>
        </div>`;
    }).join('');
    
    // Event listeners for shot cards
    listEl.querySelectorAll('.shot-card').forEach(card => {
        const idx = parseInt(card.dataset.shotIdx);
        
        card.addEventListener('mouseenter', () => {
            state.hoveredShot = state.analysisResults[idx]?.candidate;
            drawMain();
        });
        
        card.addEventListener('mouseleave', () => {
            state.hoveredShot = null;
            drawMain();
        });
        
        card.addEventListener('click', () => {
            const result = state.analysisResults[idx];
            if (result) {
                if (state.mode === 'puzzle') {
                    showToast(`${result.candidate.name}: drag from hack to throw this shot`, 'info', 2500);
                    return;
                }
                animateShot(result.candidate);
            }
        });
    });
    
    // ── Mobile shots overlay ──
    if (mobileListEl && mobilePanel) {
        mobilePanel.classList.add('has-shots');
        const top3 = state.analysisResults.slice(0, 3);
        
        mobileListEl.innerHTML = top3.map((result, i) => {
            const { candidate, wpDelta, successRate } = result;
            const typeMeta = SHOT_TYPE_META[candidate.type] || { color: '#67D4E4', tag: '?' };
            const wpPct = (wpDelta * 100).toFixed(1);
            const wpSign = wpDelta > 0 ? '+' : '';
            const wpClass = wpDelta > 0.005 ? 'positive' : wpDelta < -0.005 ? 'negative' : 'neutral';
            
            return `<div class="mobile-shot-item" data-shot-idx="${i}" style="--type-color: ${typeMeta.color}">
                <span class="mobile-shot-item__tag">${typeMeta.tag}</span>
                <span class="mobile-shot-item__name">${candidate.name}</span>
                <span class="mobile-shot-item__pct">${Math.round(successRate * 100)}%</span>
                <span class="mobile-shot-item__wp mobile-shot-item__wp--${wpClass}">${wpSign}${wpPct}</span>
            </div>`;
        }).join('');
        
        mobileListEl.querySelectorAll('.mobile-shot-item').forEach(item => {
            const idx = parseInt(item.dataset.shotIdx);
            item.addEventListener('click', () => {
                const result = state.analysisResults[idx];
                if (result) {
                    if (state.mode === 'puzzle') {
                        showToast(`${result.candidate.name}: drag from hack to throw`, 'info', 2500);
                        return;
                    }
                    animateShot(result.candidate);
                }
            });
        });
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// ANALYSIS
// ═══════════════════════════════════════════════════════════════════════════

async function runAnalysis() {
    if (state.analyzing || state.animating || state.aiThinking) return;
    if (state.ghost) { showToast('Confirm or cancel placement first', 'info'); return; }
    if (state.stones.filter(s => s.active).length === 0) {
        showToast('Place stones first', 'info');
        return;
    }
    
    state.analyzing = true;
    state.analysisResults = null;
    
    const btnAnalyze = document.getElementById('btn-analyze');
    btnAnalyze.classList.add('analyzing');
    
    const statusEl = document.getElementById('shots-status');
    statusEl.textContent = 'Analyzing...';
    
    const shotsCard = document.getElementById('shots-card');
    shotsCard.classList.add('analyzing');
    
    const listEl = document.getElementById('shots-list');
    listEl.innerHTML = '<div class="shots-empty" style="color:var(--ice-dim)">Computing optimal shots...</div>';
    
    // Mobile analyzing state
    const mobileListEl = document.getElementById('mobile-shots-list');
    if (mobileListEl) mobileListEl.innerHTML = '<div class="mobile-shots__analyzing">Analyzing...</div>';
    
    const scoreDiff = state.scoreRed - state.scoreYellow;
    const endsRemaining = C.ENDS_TOTAL - state.currentEnd + 1;
    
    const gameState = {
        scoreDiff,
        endsRemaining,
        hammerTeam: state.hammerTeam,
    };
    
    try {
        // Try Web Workers first
        const results = await E.WorkerPool.evaluateParallel(
            state.stones,
            gameState,
            state.activeTeam,
            C.MC_FULL_N,
            (progress) => {
                statusEl.textContent = `Worker ${progress.done}/${progress.total}`;
                if (progress.partial) {
                    state.analysisResults = progress.partial;
                    updateShotsDisplay();
                }
            },
            { turnNumber: state.turnNumber }
        );
        
        state.analysisResults = results;
    } catch (err) {
        // Fallback to synchronous
        console.warn('Worker pool failed, using synchronous evaluation:', err);
        const results = E.ShotEvaluator.evaluateAll(
            state.stones,
            gameState,
            state.activeTeam,
            C.MC_QUICK_N,
            (progress) => {
                statusEl.textContent = `${progress.done}/${progress.total}`;
                state.analysisResults = progress.best;
                updateShotsDisplay();
            },
            { turnNumber: state.turnNumber }
        );
        state.analysisResults = results;
    }
    
    state.analyzing = false;
    btnAnalyze.classList.remove('analyzing');
    shotsCard.classList.remove('analyzing');
    statusEl.textContent = `${state.analysisResults.length} shots evaluated`;
    
    updateShotsDisplay();
    
    // Track progression
    bumpStat('positionsAnalyzed');
    
    // Toast with top result
    if (state.analysisResults.length > 0) {
        const top = state.analysisResults[0];
        const wpPct = (top.wpDelta * 100).toFixed(1);
        showToast(`Best: ${top.candidate.name} (${top.wpDelta > 0 ? '+' : ''}${wpPct}%)`, 
                  top.wpDelta > 0 ? 'positive' : 'info');
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// NUMBER ANIMATION
// ═══════════════════════════════════════════════════════════════════════════

function animateNumber(el, from, to, duration) {
    const start = performance.now();
    const diff = to - from;
    
    const tick = (now) => {
        const elapsed = now - start;
        const t = Math.min(elapsed / duration, 1);
        // Ease out cubic
        const eased = 1 - Math.pow(1 - t, 3);
        const val = Math.round(from + diff * eased);
        el.textContent = val;
        
        if (t < 1) requestAnimationFrame(tick);
    };
    
    requestAnimationFrame(tick);
}

// ═══════════════════════════════════════════════════════════════════════════
// TOAST NOTIFICATIONS
// ═══════════════════════════════════════════════════════════════════════════

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast toast--${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    
    // Auto dismiss
    setTimeout(() => {
        toast.classList.add('dismissing');
        setTimeout(() => toast.remove(), T.slow);
    }, 3000);
}

// ═══════════════════════════════════════════════════════════════════════════
// UI CONTROLS
// ═══════════════════════════════════════════════════════════════════════════

function setActiveTeam(team) {
    state.activeTeam = team;
    const btn = document.getElementById('btn-switch-team');
    if (btn) btn.dataset.active = team;
    savePreferences();
}

// Switch team button
document.getElementById('btn-switch-team')?.addEventListener('click', () => {
    if (state.mode === 'replay') return;
    setActiveTeam(state.activeTeam === 'red' ? 'yellow' : 'red');
    if (state.ghost) {
        state.ghost.team = state.activeTeam;
    }
    playSound('turn');
    haptic(HAPTIC.turn);
    drawMain();
    showTurnBanner();
});

// Initialize switch button state
(() => {
    const btn = document.getElementById('btn-switch-team');
    if (btn) btn.dataset.active = state.activeTeam;
})();

// Analyze button
document.getElementById('btn-analyze').addEventListener('click', runAnalysis);

// AI Throw button
document.getElementById('btn-ai-throw')?.addEventListener('click', aiThrow);

// Undo button
document.getElementById('btn-undo').addEventListener('click', undo);

// Hammer toggle
document.getElementById('btn-hammer').addEventListener('click', () => {
    state.hammerTeam = state.hammerTeam === 'red' ? 'yellow' : 'red';
    const btn = document.getElementById('btn-hammer');
    btn.classList.toggle('hammer-btn--red', state.hammerTeam === 'red');
    btn.classList.toggle('hammer-btn--yellow', state.hammerTeam === 'yellow');
    document.getElementById('hammer-label').textContent = state.hammerTeam === 'red' ? 'Red' : 'Yellow';
    // Flip animation
    btn.classList.add('flipping');
    setTimeout(() => btn.classList.remove('flipping'), 233);
    updateDashboard();
    saveGameState();
});

// End selector
document.getElementById('end-select').addEventListener('change', (e) => {
    state.currentEnd = parseInt(e.target.value);
    updateDashboard();
    saveGameState();
});

// Score editing (click to increment)
// Score increment (left click) / decrement (right click)
function bumpScore(el, team, delta) {
    if (team === 'red') {
        state.scoreRed = Math.max(0, (state.scoreRed + delta + 16) % 16);
        el.textContent = state.scoreRed;
    } else {
        state.scoreYellow = Math.max(0, (state.scoreYellow + delta + 16) % 16);
        el.textContent = state.scoreYellow;
    }
    el.classList.remove('bump');
    void el.offsetWidth;
    el.classList.add('bump');
    if (delta > 0) playSound('score');
    setTimeout(() => el.classList.remove('bump'), T.normal);
    updateDashboard();
    saveGameState();
}

const scoreRedEl = document.getElementById('score-red');
const scoreYellowEl = document.getElementById('score-yellow');
scoreRedEl.addEventListener('click', () => bumpScore(scoreRedEl, 'red', 1));
scoreRedEl.addEventListener('contextmenu', (e) => { e.preventDefault(); bumpScore(scoreRedEl, 'red', -1); });
scoreYellowEl.addEventListener('click', () => bumpScore(scoreYellowEl, 'yellow', 1));
scoreYellowEl.addEventListener('contextmenu', (e) => { e.preventDefault(); bumpScore(scoreYellowEl, 'yellow', -1); });

// Preset selector (kept minimal)
const presetEl = document.getElementById('preset-select');
if (presetEl) {
    presetEl.addEventListener('change', (e) => {
        const key = e.target.value;
        if (!key) return;
        if (key === 'empty') {
            newGame();
        }
        e.target.value = '';
    });
}

// Keyboard shortcuts overlay
document.getElementById('btn-shortcuts').addEventListener('click', toggleShortcuts);
document.querySelector('.shortcuts-overlay__close').addEventListener('click', toggleShortcuts);
document.getElementById('shortcuts-overlay').addEventListener('click', (e) => {
    if (e.target === e.currentTarget) toggleShortcuts();
});

function toggleShortcuts() {
    const overlay = document.getElementById('shortcuts-overlay');
    const visible = overlay.classList.toggle('visible');
    overlay.setAttribute('aria-hidden', !visible);
}

// ═══════════════════════════════════════════════════════════════════════════
// KEYBOARD SHORTCUTS
// ═══════════════════════════════════════════════════════════════════════════

document.addEventListener('keydown', (e) => {
    // Don't handle if focused on input
    if (e.target.tagName === 'SELECT' || e.target.tagName === 'INPUT') return;
    
    const key = e.key.toLowerCase();
    
    // Shortcuts overlay
    if (key === '?' || (key === '/' && e.shiftKey)) {
        e.preventDefault();
        toggleShortcuts();
        return;
    }
    
    // Close overlays on Escape / return home
    if (key === 'escape') {
        const gameBrowserEl = document.getElementById('game-browser');
        if (gameBrowserEl.classList.contains('visible')) {
            toggleGameBrowser();
            return;
        }
        const overlay = document.getElementById('shortcuts-overlay');
        if (overlay.classList.contains('visible')) {
            toggleShortcuts();
            return;
        }
        // Cancel ghost preview
        if (state.ghost) {
            dismissGhost();
            return;
        }
        // Cancel animation with full cleanup
        if (state.animating) {
            state.animating = false;
            state.sweeping = false;
            state._sweepPoint = null;
            state.animationFinalStones = null;
            state.animationCollisions = null;
            mainCanvas.style.transform = '';
            mainCanvas.style.cursor = 'crosshair';
            const sweepBanner = document.getElementById('sweep-banner');
            if (sweepBanner) sweepBanner.classList.remove('visible');
            drawMain();
            return;
        }
        // Close puzzle result modal
        const puzzleResultEl = document.getElementById('puzzle-result');
        if (puzzleResultEl?.classList.contains('visible')) {
            puzzleResultEl.classList.remove('visible');
            return;
        }
        // Return home from replay/capture
        if (state.mode === 'replay' || state.mode === 'capture') {
            goHome();
            return;
        }
    }
    
    // New game
    if (key === 'n') {
        e.preventDefault();
        newGame();
        return;
    }
    
    // Switch modes with Tab (only in free play)
    if (e.code === 'Tab' && !e.ctrlKey && !e.metaKey) {
        const isFreeplay = state.mode === 'freeplay-ai' || state.mode === 'freeplay-pvp';
        if (isFreeplay) {
            e.preventDefault();
            setGameMode(state.mode === 'freeplay-ai' ? 'freeplay-pvp' : 'freeplay-ai');
            showToast(state.mode === 'freeplay-ai' ? 'vs AI' : '2 Player', 'info');
            return;
        }
    }
    
    // Analyze
    if (key === 'a') {
        e.preventDefault();
        runAnalysis();
        return;
    }
    
    // AI Throw
    if (key === 'i') {
        e.preventDefault();
        aiThrow();
        return;
    }
    
    // Reset / Clear
    if (key === 'r') {
        e.preventDefault();
        newGame();
        return;
    }
    
    // Toggle hammer
    if (key === 'h') {
        e.preventDefault();
        document.getElementById('btn-hammer').click();
        return;
    }
    
    // Play shot 1-5
    if (key >= '1' && key <= '5') {
        const idx = parseInt(key) - 1;
        if (state.analysisResults && state.analysisResults[idx]) {
            e.preventDefault();
            animateShot(state.analysisResults[idx].candidate);
        }
        return;
    }
    
    // Replay
    if (key === ' ') {
        if (state.lastAnimationShot) {
            e.preventDefault();
            animateShot(state.lastAnimationShot);
        }
        return;
    }
    
    // Game replay navigation (when game detail is open)
    if (key === 'ArrowLeft' || key === 'ArrowRight' || key === ' ') {
        const detailEl = document.getElementById('game-detail');
        if (detailEl && detailEl.style.display !== 'none') {
            e.preventDefault();
            if (key === ' ') {
                toggleAutoPlay();
            } else if (key === 'ArrowLeft' && state.replayEndIndex > 0) {
                stopAutoPlay();
                setReplayEnd(state.replayEndIndex - 1);
            } else if (key === 'ArrowRight') {
                stopAutoPlay();
                const ends = gameBrowser.selectedEnds;
                if (ends && state.replayEndIndex < ends.length - 1) {
                    setReplayEnd(state.replayEndIndex + 1);
                }
            }
            return;
        }
    }
    
    // Share position
    if (key === 's' && !e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        sharePosition();
        return;
    }
    
    // Prev/next end
    if (key === '[') {
        const sel = document.getElementById('end-select');
        const val = Math.max(1, parseInt(sel.value) - 1);
        sel.value = val;
        state.currentEnd = val;
        updateDashboard();
        return;
    }
    if (key === ']') {
        const sel = document.getElementById('end-select');
        const val = Math.min(10, parseInt(sel.value) + 1);
        sel.value = val;
        state.currentEnd = val;
        updateDashboard();
        return;
    }
    
    // Undo
    if ((e.ctrlKey || e.metaKey) && key === 'z') {
        e.preventDefault();
        if (e.shiftKey) redo();
        else undo();
        return;
    }
    
    // Undo (U key)
    if (key === 'u') {
        e.preventDefault();
        undo();
        return;
    }
});

// ═══════════════════════════════════════════════════════════════════════════
// INITIALIZATION
// ═══════════════════════════════════════════════════════════════════════════

// ═══════════════════════════════════════════════════════════════════════════
// ONBOARDING
// ═══════════════════════════════════════════════════════════════════════════

function showOnboarding() {
    const overlay = document.getElementById('onboarding-overlay');
    if (!overlay) return;
    overlay.classList.add('visible');
    overlay.setAttribute('aria-hidden', 'false');
    
    // Auto-dismiss after 8 seconds so nothing stays blocked
    state._onboardingTimer = setTimeout(() => hideOnboarding(), 8000);
    
    // Dismiss on ANY key press
    const dismissOnKey = () => {
        hideOnboarding();
        document.removeEventListener('keydown', dismissOnKey);
    };
    document.addEventListener('keydown', dismissOnKey);
}

function hideOnboarding() {
    const overlay = document.getElementById('onboarding-overlay');
    if (!overlay) return;
    if (!overlay.classList.contains('visible')) return; // already hidden
    overlay.classList.remove('visible');
    overlay.setAttribute('aria-hidden', 'true');
    if (state._onboardingTimer) { clearTimeout(state._onboardingTimer); state._onboardingTimer = null; }
    
    // ALWAYS mark as visited — never show again
    markVisited();
}

// Onboarding button listeners
document.getElementById('btn-onboarding-start')?.addEventListener('click', () => {
    hideOnboarding();
});
document.getElementById('btn-onboarding-archive')?.addEventListener('click', () => {
    hideOnboarding();
    setTimeout(() => toggleGameBrowser(), 300);
});
// Close onboarding on click anywhere on overlay background
document.getElementById('onboarding-overlay')?.addEventListener('click', (e) => {
    hideOnboarding();
});

// ═══════════════════════════════════════════════════════════════════════════
// INITIALIZATION
// ═══════════════════════════════════════════════════════════════════════════

function init() {
    resizeCanvases();
    initParticles();

    let restoredFromHash = false;
    let restoredFromStorage = false;

    // Priority 1: URL hash state (shared links)
    const hashState = window.RoboSkipData?.decodeHashToState(window.location.hash);
    if (hashState) {
        state.scoreRed = hashState.scoreRed;
        state.scoreYellow = hashState.scoreYellow;
        state.currentEnd = hashState.currentEnd;
        state.hammerTeam = hashState.hammerTeam;
        state.stones = hashState.stones.map(s => new E.Stone(s.x, s.y, s.team, `s${state.nextStoneId++}`));
        restoredFromHash = true;
    }
    // Priority 2: localStorage restore (returning user)
    else if (!isFirstVisit()) {
        restoredFromStorage = restoreGameState();
    }

    // Restore preferences
    const prefs = lsGet(LS_KEYS.PREFERENCES, {});
    if (prefs.activeTeam) {
        state.activeTeam = prefs.activeTeam;
    }

    // Sync UI from state
    syncUIFromState();

    // Set initial WP without animation
    const scoreDiff = state.scoreRed - state.scoreYellow;
    const endsRemaining = C.ENDS_TOTAL - state.currentEnd + 1;
    const wp = E.WinProbability.get(scoreDiff, endsRemaining, state.hammerTeam === 'red');
    document.getElementById('wp-number').textContent = Math.round(wp * 100);

    updateDashboard();

    // Start overlay animation loop
    requestAnimationFrame(drawOverlay);

    // Continuously redraw main canvas to animate trajectory dashes
    let lastDrawTime = 0;
    const animLoop = (t) => {
        if (state.hoveredShot || (state.analysisResults && !state.animating)) {
            if (t - lastDrawTime > 50) {
                drawMain();
                lastDrawTime = t;
            }
        }
        requestAnimationFrame(animLoop);
    };
    requestAnimationFrame(animLoop);

    // Handle resize
    window.addEventListener('resize', () => {
        resizeCanvases();
        initParticles();
    });

    // Initialize Web Worker pool
    try { E.WorkerPool.init(); } catch (e) {
        console.warn('Web Worker pool init failed:', e.message);
    }

    // Load live data in background
    initLiveData();

    // Initialize mode UI — use rAF so layout is settled for slider measurement
    updateModeUI();
    requestAnimationFrame(() => positionModeSlider());

    // Show appropriate welcome state
    if (isFirstVisit() && !restoredFromHash) {
        showOnboarding();
        markVisited();
    } else if (restoredFromStorage) {
        showToast('Welcome back — restored your position', 'info');
        if (state.stones.filter(s => s.active).length > 0) {
            scheduleAutoAnalysis();
        }
    } else if (restoredFromHash) {
        showToast('Loaded shared position', 'info');
        if (state.stones.filter(s => s.active).length > 0) {
            scheduleAutoAnalysis();
        }
    }

    // Track visit
    bumpStat('sessions');

    // Register service worker for PWA
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('sw.js').catch(() => {});
    }

    console.log(
        '%c🥌 Robo-Skip %cCurling Strategist',
        'color: #67D4E4; font-weight: bold; font-size: 16px;',
        'color: #C4BFBA; font-size: 14px;'
    );
    console.log(
        '%cPowered by Curling IO API + Fry et al. (2024) model.\n' +
        'Markov chain WP | Monte Carlo shots | Newtonian physics',
        'color: #9E9994; font-size: 11px;'
    );
}

// ═══════════════════════════════════════════════════════════════════════════
// LIVE DATA PIPELINE
// ═══════════════════════════════════════════════════════════════════════════

async function initLiveData() {
    const Data = window.RoboSkipData;
    if (!Data) return;

    const provDot = document.querySelector('.data-provenance__dot');
    const provText = document.getElementById('data-provenance-text');
    const liveBadge = document.getElementById('live-badge');
    const dataSrcDot = document.querySelector('.data-source__dot');
    const dataSrcText = document.querySelector('.data-source__text');

    try {
        const result = await Data.loadLiveData((status) => {
            if (provText) provText.textContent = status.message;
            if (dataSrcText) dataSrcText.textContent = status.message;
        });

        // Update engine with live data
        if (result.distHammer && result.distNoHammer) {
            E.WinProbability.updateDistributions(result.distHammer, result.distNoHammer);
            updateDashboard(); // Refresh WP with new distributions
        }

        if (provDot) {
            provDot.classList.toggle('live', result.sampleSize > 0);
            provDot.classList.toggle('model', result.sampleSize === 0);
        }
        if (provText) provText.textContent = result.source;

        // Update header live badge
        if (liveBadge) {
            if (result.sampleSize > 0) {
                liveBadge.classList.add('live');
                liveBadge.classList.remove('hidden');
            } else {
                liveBadge.classList.remove('live');
            }
        }

        // Update game browser data source
        if (dataSrcDot) {
            dataSrcDot.classList.toggle('connected', result.sampleSize > 0);
            dataSrcDot.classList.toggle('error', result.sampleSize === 0);
        }
        if (dataSrcText) {
            dataSrcText.textContent = result.sampleSize > 0
                ? `${result.source}`
                : 'Model';
        }

        if (result.sampleSize > 0) {
            showToast(`Live data: ${result.source}`, 'positive');
        } else {
            showToast('Using Fry et al. (2024) model', 'info');
        }
    } catch (err) {
        console.error('Live data pipeline failed:', err);
        if (provDot) provDot.classList.add('model');
        if (provText) provText.textContent = 'Fry et al. (2024) model (offline)';
        if (dataSrcDot) dataSrcDot.classList.add('error');
        if (dataSrcText) dataSrcText.textContent = 'Offline';
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// GAME BROWSER
// ═══════════════════════════════════════════════════════════════════════════
// MODE MANAGEMENT
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Update all UI elements to reflect current mode.
 */
function updateModeUI() {
    const badge = document.getElementById('mode-badge');
    const turnBanner = document.getElementById('turn-banner');
    const modeToggle = document.getElementById('mode-toggle');
    
    const isFreeplay = state.mode === 'freeplay-ai' || state.mode === 'freeplay-pvp' || state.mode === 'puzzle';
    
    // --- Mode toggle (segmented control) ---
    if (modeToggle) {
        modeToggle.style.display = isFreeplay ? 'flex' : 'none';
        modeToggle.classList.toggle('pvp', state.mode === 'freeplay-pvp');
        modeToggle.querySelectorAll('.mode-toggle__btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.mode === state.mode);
        });
        // Slide the pill to the active button
        positionModeSlider();
    }
    
    // --- Puzzle prompt ---
    const puzzlePrompt = document.getElementById('puzzle-prompt');
    if (puzzlePrompt) {
        puzzlePrompt.classList.toggle('visible', state.mode === 'puzzle');
    }
    
    // --- Context badge (replay / capture only) ---
    if (badge) {
        badge.className = 'header__mode-badge';
        if (state.mode === 'replay') {
            badge.textContent = 'Viewing Replay';
            badge.classList.add('mode--replay');
            badge.style.display = '';
        } else if (state.mode === 'capture') {
            badge.textContent = 'Loaded Position';
            badge.classList.add('mode--capture');
            badge.style.display = '';
        } else {
            badge.style.display = 'none';
        }
    }
    
    // --- Turn banner ---
    if (isFreeplay && state.mode !== 'puzzle') {
        showTurnBanner();
    } else if (turnBanner) {
        turnBanner.classList.remove('visible');
    }
    
    // --- Mobile shots panel visibility ---
    const mobileShots = document.getElementById('mobile-shots');
    if (mobileShots) {
        mobileShots.style.display = (state.mode === 'replay') ? 'none' : '';
    }
    
    // --- AI Throw button: visible in freeplay-ai, hidden otherwise ---
    const aiThrowBtn = document.getElementById('btn-ai-throw');
    if (aiThrowBtn) {
        aiThrowBtn.style.display = (state.mode === 'freeplay-ai') ? '' : 'none';
    }
}

/**
 * Position the sliding pill behind the active mode-toggle button.
 */
function positionModeSlider() {
    const toggle = document.getElementById('mode-toggle');
    const slider = document.getElementById('mode-slider');
    if (!toggle || !slider) return;
    const activeBtn = toggle.querySelector('.mode-toggle__btn.active');
    if (!activeBtn) return;
    const toggleRect = toggle.getBoundingClientRect();
    const btnRect = activeBtn.getBoundingClientRect();
    slider.style.width = btnRect.width + 'px';
    slider.style.transform = `translateX(${btnRect.left - toggleRect.left - 3}px)`;
}

function showTurnBanner() {
    const banner = document.getElementById('turn-banner');
    const text = document.getElementById('turn-text');
    const dot = document.getElementById('turn-dot');
    if (!banner) return;
    
    if (state.mode === 'puzzle') {
        banner.classList.remove('visible');
        return;
    }
    
    banner.classList.add('visible');
    banner.classList.remove('ai-thinking', 'pvp-red', 'pvp-yellow');
    
    const isRed = state.activeTeam === 'red';
    dot.classList.toggle('yellow', !isRed);
    
    // Stones remaining — only show after play has started
    const teamLeft = Math.max(0, 8 - Math.ceil(state.turnNumber / 2));
    const countHint = state.turnNumber > 0 && teamLeft > 0 ? ` · ${teamLeft} left` : '';
    
    if (state.aiThinking) {
        banner.classList.add('ai-thinking');
        text.textContent = 'AI thinking…';
    } else if (state.mode === 'freeplay-ai') {
        text.textContent = `Placing ${isRed ? 'Red' : 'Yellow'}${countHint}`;
    } else if (state.mode === 'freeplay-pvp') {
        banner.classList.add(isRed ? 'pvp-red' : 'pvp-yellow');
        text.textContent = `${isRed ? 'Red' : 'Yellow'} to play${countHint}`;
    }
}

/**
 * Switch to a game mode. Clears stones for a clean break.
 */
function setGameMode(mode) {
    // Guard: don't switch while animation or AI is running
    if (state.animating) {
        state.animating = false;
        state.sweeping = false;
        state._sweepPoint = null;
        state.animationFinalStones = null;
        state.animationCollisions = null;
        mainCanvas.style.transform = '';
    }
    if (state.aiThinking) {
        state.aiThinking = false;
    }
    
    // Clean up any pending interaction state
    if (state.ghost) dismissGhost();
    if (state.throwing) state.throwing = null;
    if (typeof cancelPendingDelete === 'function' && state.pendingDelete) cancelPendingDelete();
    state.analyzing = false;
    
    // Close puzzle result modal if open
    const puzzleResultEl = document.getElementById('puzzle-result');
    if (puzzleResultEl?.classList.contains('visible')) {
        puzzleResultEl.classList.remove('visible');
    }
    
    // Close sweep banner
    const sweepBanner = document.getElementById('sweep-banner');
    if (sweepBanner) sweepBanner.classList.remove('visible');
    
    if (mode !== 'replay') state._prevMode = mode;
    
    const wasMode = state.mode;
    state.mode = mode;
    
    // Clean up replay state when leaving replay
    if (wasMode === 'replay' && mode !== 'replay') {
        state.replayEndIndex = -1;
        stopAutoPlay();
    }
    
    if (mode === 'freeplay-ai' || mode === 'freeplay-pvp') {
        state.loadedGameContext = null;
        state.turnNumber = 0;
        state.aiThinking = false;
        state.activeTeam = 'red';
        
        if (mode === 'freeplay-ai') {
            state.humanTeam = 'red';
            state.aiTeam = 'yellow';
        }
        
        // If switching between modes, clear for fresh start
        if (wasMode !== mode) {
            state.stones = [];
            state.nextStoneId = 1;
            state.analysisResults = null;
            state.hoveredShot = null;
            state.scoreRed = 0;
            state.scoreYellow = 0;
            state.currentEnd = 1;
            drawMain();
            updateDashboard();
            saveGameState();
        }
    }
    
    if (mode === 'puzzle') {
        state.loadedGameContext = null;
        state.aiThinking = false;
        state.turnNumber = 0;
        state.analysisResults = null;
        state.hoveredShot = null;
        state.ghost = null;
        initDailyPuzzle();
    }
    
    updateModeUI();
}

/**
 * Return to home/free play — resets everything to clean state.
 */
function goHome() {
    stopAutoPlay();
    
    // Close game browser if open
    const overlay = document.getElementById('game-browser');
    if (overlay?.classList.contains('visible')) {
        overlay.classList.remove('visible');
        overlay.setAttribute('aria-hidden', 'true');
    }
    
    // Full reset
    state.loadedGameContext = null;
    state.analysisResults = null;
    state.replayEndIndex = -1;
    state.stones = [];
    state.nextStoneId = 1;
    state.turnNumber = 0;
    state.aiThinking = false;
    state.animating = false;
    state.hoveredShot = null;
    state.undoStack = [];
    state.redoStack = [];
    
    setGameMode(state._prevMode || 'freeplay-ai');
    
    drawMain();
    updateDashboard();
    saveGameState();
    showToast('Fresh sheet', 'info');
}

/**
 * New game — clears the board and resets turns, stays in current mode.
 */
function newGame() {
    if (state.animating || state.aiThinking) {
        showToast('Wait for the shot to finish', 'warning');
        return;
    }
    pushUndo();
    cancelAutoAnalysis();
    if (state.ghost) dismissGhost();
    if (state.pendingDelete && typeof cancelPendingDelete === 'function') cancelPendingDelete();
    
    state.stones = [];
    state.nextStoneId = 1;
    state.analysisResults = null;
    state.hoveredShot = null;
    state.turnNumber = 0;
    state.aiThinking = false;
    state.activeTeam = 'red';
    state.scoreRed = 0;
    state.scoreYellow = 0;
    state.currentEnd = 1;
    
    // If in replay/capture, snap back to free play
    if (state.mode === 'replay' || state.mode === 'capture') {
        state.loadedGameContext = null;
        state.replayEndIndex = -1;
        const overlay = document.getElementById('game-browser');
        if (overlay?.classList.contains('visible')) {
            overlay.classList.remove('visible');
            overlay.setAttribute('aria-hidden', 'true');
        }
        setGameMode(state._prevMode || 'freeplay-ai');
    }
    
    haptic(HAPTIC.newGame);
    drawMain();
    updateDashboard();
    saveGameState();
    updateModeUI();
    showToast('New game', 'info');
}

// Mode toggle click handlers
document.getElementById('mode-toggle')?.querySelectorAll('.mode-toggle__btn').forEach(btn => {
    btn.addEventListener('click', () => {
        if (btn.dataset.mode === state.mode) return; // already active
        setGameMode(btn.dataset.mode);
    });
});

// Reposition slider on window resize
window.addEventListener('resize', () => positionModeSlider());

// ═══════════════════════════════════════════════════════════════════════════
// AI THROW (ON DEMAND)
// ═══════════════════════════════════════════════════════════════════════════

/**
 * AI Throw — evaluates the current position for the active team,
 * picks the best shot, and executes it with animation.
 * Called explicitly by user via "AI Throw" button or 'I' key. Never auto-triggered.
 */
async function aiThrow() {
    if (state.aiThinking || state.animating) return;
    if (state.stones.filter(s => s.active).length === 0) {
        showToast('Place some stones first', 'info');
        return;
    }
    
    state.aiThinking = true;
    const throwTeam = state.activeTeam;
    showToast(`AI thinking for ${throwTeam}...`, 'info');
    
    // Update turn banner if visible
    const banner = document.getElementById('turn-banner');
    if (banner?.classList.contains('visible')) {
        banner.classList.add('ai-thinking');
        document.getElementById('turn-text').textContent = `AI analyzing for ${throwTeam}...`;
    }
    
    const scoreDiff = state.scoreRed - state.scoreYellow;
    const endsRemaining = C.ENDS_TOTAL - state.currentEnd + 1;
    const gameState = {
        scoreDiff,
        endsRemaining,
        hammerTeam: state.hammerTeam,
    };
    
    try {
        // Try worker pool first for speed, fall back to sync
        let results;
        try {
            results = await E.WorkerPool.evaluateParallel(
                state.stones, gameState, throwTeam,
                Math.min(C.MC_FULL_N || 100, 100),
                null
            );
        } catch (_) {
            results = E.ShotEvaluator.evaluateAll(
                state.stones, gameState, throwTeam,
                Math.min(C.MC_QUICK_N || 30, 30)
            );
        }
        
        state.aiThinking = false;
        if (banner) banner.classList.remove('ai-thinking');
        
        if (results.length > 0) {
            const best = results[0];
            const wpPct = (best.wpDelta * 100).toFixed(1);
            showToast(
                `AI plays: ${best.candidate.name} (${best.wpDelta > 0 ? '+' : ''}${wpPct}%)`,
                best.wpDelta > 0 ? 'positive' : 'info'
            );
            animateShot(best.candidate);
        } else {
            // No shots available — place a draw to the button
            showToast('No shots available — drawing to button', 'info');
            pushUndo();
            state.stones.push(new E.Stone(0, 0, throwTeam, `s${state.nextStoneId++}`));
            drawMain();
            updateDashboard();
            saveGameState();
        }
    } catch (err) {
        console.warn('AI throw error:', err);
        state.aiThinking = false;
        if (banner) banner.classList.remove('ai-thinking');
        showToast('AI error — try again', 'info');
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// GAME BROWSER
// ═══════════════════════════════════════════════════════════════════════════

const gameBrowser = {
    currentEvent: null,
    currentGames: [],
    selectedGame: null,
    selectedEnds: null,
};

function toggleGameBrowser() {
    const overlay = document.getElementById('game-browser');
    const visible = overlay.classList.toggle('visible');
    overlay.setAttribute('aria-hidden', !visible);

    if (visible) {
        state.mode = 'replay';
        loadTournamentList();
    } else {
        state.mode = state.loadedGameContext ? 'capture' : state._prevMode || 'freeplay-ai';
    }
    updateModeUI();
}

function loadTournamentList() {
    const Data = window.RoboSkipData;
    if (!Data) return;

    const listEl = document.getElementById('tournament-list');
    const gameListEl = document.getElementById('game-list');
    const detailEl = document.getElementById('game-detail');

    listEl.style.display = '';
    gameListEl.style.display = 'none';
    detailEl.style.display = 'none';

    listEl.innerHTML = Data.TOURNAMENTS.map((t, i) => `
        <button class="tournament-card" data-idx="${i}" aria-label="${t.name} (${t.type})">
            <span class="tournament-card__name">${t.name}</span>
            <span class="tournament-card__type">${t.type.toUpperCase()}</span>
            <span class="tournament-card__arrow">&#9656;</span>
        </button>
    `).join('');

    listEl.querySelectorAll('.tournament-card').forEach(card => {
        card.addEventListener('click', () => {
            const idx = parseInt(card.dataset.idx);
            loadTournamentGames(Data.TOURNAMENTS[idx]);
        });
    });
}

async function loadTournamentGames(tourney) {
    const Data = window.RoboSkipData;
    const listEl = document.getElementById('tournament-list');
    const gameListEl = document.getElementById('game-list');
    const cardsEl = document.getElementById('game-cards');
    const nameEl = document.getElementById('tournament-name');

    listEl.style.display = 'none';
    gameListEl.style.display = '';
    nameEl.textContent = tourney.name;
    cardsEl.innerHTML = createShimmerCards(4, 'game-card');

    try {
        const { games } = await Data.browseTournament(tourney.subdomain, tourney.id);
        gameBrowser.currentGames = games;

        if (games.length === 0) {
            cardsEl.innerHTML = '<p class="game-browser__loading">No completed games found</p>';
            return;
        }

        cardsEl.innerHTML = games.map((g, i) => {
            const winner = g.team1.result === 'won' ? 1 : 2;
            return `<button class="game-card" data-idx="${i}" aria-label="${g.team1.name} ${g.team1.score} vs ${g.team2.score} ${g.team2.name}">
                <span class="game-card__team game-card__team--left ${winner === 1 ? 'game-card__winner' : ''}">${g.team1.name}</span>
                <span class="game-card__score">${g.team1.score} - ${g.team2.score}</span>
                <span class="game-card__team game-card__team--right ${winner === 2 ? 'game-card__winner' : ''}">${g.team2.name}</span>
            </button>`;
        }).join('');

        cardsEl.querySelectorAll('.game-card').forEach(card => {
            card.addEventListener('click', () => {
                const idx = parseInt(card.dataset.idx);
                showGameDetail(gameBrowser.currentGames[idx]);
            });
        });
    } catch (err) {
        cardsEl.innerHTML = `<p class="game-browser__loading" style="color:var(--negative)">Error: ${err.message}</p>`;
    }
}

function showGameDetail(game) {
    const Data = window.RoboSkipData;
    const gameListEl = document.getElementById('game-list');
    const detailEl = document.getElementById('game-detail');

    gameListEl.style.display = 'none';
    detailEl.style.display = '';

    gameBrowser.selectedGame = game;
    gameBrowser.selectedEnds = Data.reconstructHammerProgression(game);

    // Header
    const headerEl = document.getElementById('game-detail-header');
    headerEl.innerHTML = `
        <div class="game-detail__teams">${game.team1.name} vs ${game.team2.name}</div>
        <div class="game-detail__final">${game.team1.score} - ${game.team2.score}</div>
    `;

    // Linescore
    const ends = gameBrowser.selectedEnds;
    const numEnds = ends.length;
    const lineEl = document.getElementById('game-linescore');

    let headerRow = '<th>Team</th>';
    for (let i = 1; i <= numEnds; i++) headerRow += `<th>${i}</th>`;
    headerRow += '<th class="total">T</th>';

    const makeRow = (team, teamNum) => {
        let row = `<td>${team.name}</td>`;
        for (let i = 0; i < numEnds; i++) {
            const s = team.endScores[i] || 0;
            const isHammer = ends[i].hammerTeam === teamNum;
            const otherScore = teamNum === 1 ? (game.team2.endScores[i] || 0) : (game.team1.endScores[i] || 0);
            const cls = s > 0
                ? (isHammer ? 'scored' : 'stolen')
                : (otherScore > 0 ? '' : 'blank');
            const hammerCls = isHammer ? ' hammer' : '';
            row += `<td class="${cls}${hammerCls}">${s}</td>`;
        }
        row += `<td class="total">${team.score}</td>`;
        return row;
    };

    lineEl.innerHTML = `
        <table class="linescore-table">
            <thead><tr>${headerRow}</tr></thead>
            <tbody>
                <tr>${makeRow(game.team1, 1)}</tr>
                <tr>${makeRow(game.team2, 2)}</tr>
            </tbody>
        </table>
    `;

    // WP chart
    const wpEl = document.getElementById('game-wp-chart');
    wpEl.innerHTML = ends.map((end, i) => {
        const wp1val = E.WinProbability.get(
            end.runningScore1 - end.runningScore2,
            end.endsRemaining,
            ends[i + 1] ? ends[i + 1].hammerTeam === 1 : end.hammerTeam === 1
        );
        const pct = Math.round(wp1val * 100);
        const color = pct > 55 ? 'var(--positive)' : pct < 45 ? 'var(--negative)' : 'var(--ice)';
        return `<div class="wp-bar" style="height:${Math.max(pct, 3)}%;background:${color}" data-end="${i}">
            <span class="wp-bar__tooltip">End ${end.end}: ${game.team1.name} ${pct}%</span>
        </div>`;
    }).join('');

    // WP bar click → jump to that end in replay
    wpEl.querySelectorAll('.wp-bar').forEach(bar => {
        bar.addEventListener('click', () => {
            const idx = parseInt(bar.dataset.end);
            setReplayEnd(idx);
        });
    });

    // Build end-by-end replay timeline
    buildReplayTimeline(game, ends);
    
    // Auto-select first end so user immediately sees data
    state.replayEndIndex = -1;
    if (ends.length > 0) {
        // Set state directly and update all UI manually
        state.replayEndIndex = 0;
        
        // Highlight active timeline dot
        document.querySelectorAll('.replay-dot').forEach((d, i) => {
            d.classList.toggle('active', i === 0);
        });
        
        // Highlight WP bar
        document.querySelectorAll('#game-wp-chart .wp-bar').forEach((bar, i) => {
            bar.style.opacity = i === 0 ? '1' : '0.4';
        });
        
        // Build end summary
        renderEndSummary(0);
    }
    updateReplayControls();
}

// ═══════════════════════════════════════════════════════════════════════════
// END-BY-END REPLAY — Real Data Only
// ═══════════════════════════════════════════════════════════════════════════

// Replay state (no fake stone generation — data comes from API only)
state.replayAnimating = false;
state.replayAutoPlay = false;
state.replayAutoTimer = null;

function buildReplayTimeline(game, ends) {
    const timelineEl = document.getElementById('replay-timeline');
    if (!timelineEl) return;

    timelineEl.innerHTML = ends.map((end, i) => {
        const s1 = game.team1.endScores[i] || 0;
        const s2 = game.team2.endScores[i] || 0;
        let cls = '';
        if (s1 === 0 && s2 === 0) cls = 'blank';
        else if ((end.hammerTeam === 1 && s1 > 0) || (end.hammerTeam === 2 && s2 > 0)) cls = 'scored';
        else cls = 'stolen';

        return `<button class="replay-dot ${cls}" data-idx="${i}" aria-label="End ${end.end}" title="End ${end.end}: ${s1}-${s2}">${end.end}</button>`;
    }).join('');

    timelineEl.querySelectorAll('.replay-dot').forEach(dot => {
        dot.addEventListener('click', () => {
            setReplayEnd(parseInt(dot.dataset.idx));
        });
    });
}

function setReplayEnd(idx) {
    const ends = gameBrowser.selectedEnds;
    const game = gameBrowser.selectedGame;
    if (!ends || !game || idx < 0 || idx >= ends.length) return;

    state.replayEndIndex = idx;
    updateReplayControls();
    renderEndSummary(idx);

    // Highlight the corresponding WP bar
    document.querySelectorAll('#game-wp-chart .wp-bar').forEach((bar, i) => {
        bar.style.opacity = i === idx ? '1' : '0.4';
    });
    
    // Auto-play: advance after viewing each end
    if (state.replayAutoPlay && idx < ends.length - 1) {
        state.replayAutoTimer = setTimeout(() => setReplayEnd(idx + 1), 2500);
    } else if (state.replayAutoPlay && idx >= ends.length - 1) {
        stopAutoPlay();
    }
}

function startAutoPlay() {
    state.replayAutoPlay = true;
    const btn = document.getElementById('replay-autoplay');
    if (btn) { btn.textContent = '⏸'; btn.title = 'Pause auto-play'; }
    
    // Start from beginning if at end or not started
    const ends = gameBrowser.selectedEnds;
    if (!ends) return;
    if (state.replayEndIndex < 0 || state.replayEndIndex >= ends.length - 1) {
        setReplayEnd(0);
    } else {
        setReplayEnd(state.replayEndIndex + 1);
    }
}

function stopAutoPlay() {
    state.replayAutoPlay = false;
    if (state.replayAutoTimer) { clearTimeout(state.replayAutoTimer); state.replayAutoTimer = null; }
    const btn = document.getElementById('replay-autoplay');
    if (btn) { btn.textContent = '▶'; btn.title = 'Auto-play through ends'; }
}

function toggleAutoPlay() {
    if (state.replayAutoPlay) stopAutoPlay();
    else startAutoPlay();
}

/**
 * Render a rich end summary card for the selected end.
 * Shows score change, WP swing, hammer info, and strategic narrative.
 */
function renderEndSummary(idx) {
    const el = document.getElementById('end-summary');
    if (!el) return;

    const ends = gameBrowser.selectedEnds;
    const game = gameBrowser.selectedGame;
    if (!ends || !game || idx < 0 || idx >= ends.length) {
        el.innerHTML = '';
        return;
    }

    const end = ends[idx];
    const s1 = game.team1.endScores[idx] || 0;
    const s2 = game.team2.endScores[idx] || 0;
    const hammerTeamName = end.hammerTeam === 1 ? game.team1.name : game.team2.name;
    const nonHammerName = end.hammerTeam === 1 ? game.team2.name : game.team1.name;

    // Determine end outcome type
    let outcomeType, outcomeLabel, outcomeText;
    if (s1 === 0 && s2 === 0) {
        outcomeType = 'blank';
        outcomeLabel = 'Blank End';
        outcomeText = `${hammerTeamName} kept hammer — no points scored.`;
    } else {
        const hammerScored = (end.hammerTeam === 1 && s1 > 0) || (end.hammerTeam === 2 && s2 > 0);
        const scoringTeam = s1 > 0 ? game.team1.name : game.team2.name;
        const points = Math.max(s1, s2);

        if (hammerScored) {
            outcomeType = 'scored';
            outcomeLabel = points === 1 ? 'Force' : `Score ${points}`;
            if (points === 1) {
                outcomeText = `${scoringTeam} forced to a single with hammer — ${nonHammerName} successfully limited the damage.`;
            } else if (points >= 3) {
                outcomeText = `${scoringTeam} capitalized with a big ${points}-point end with hammer — a significant swing.`;
            } else {
                outcomeText = `${scoringTeam} scored ${points} with hammer — a solid end.`;
            }
        } else {
            outcomeType = 'stolen';
            outcomeLabel = `Steal of ${points}`;
            if (points >= 2) {
                outcomeText = `${scoringTeam} stole ${points} without hammer — a momentum-shifting end that puts serious pressure on ${hammerTeamName}.`;
            } else {
                outcomeText = `${scoringTeam} stole 1 — a strong defensive effort that flips hammer possession.`;
            }
        }
    }

    // WP swing: compare WP before and after this end
    const wpBefore = idx === 0
        ? E.WinProbability.get(0, game.numberOfEnds || 10, end.hammerTeam === 1)
        : (() => {
            const prev = ends[idx - 1];
            return E.WinProbability.get(
                prev.runningScore1 - prev.runningScore2,
                prev.endsRemaining,
                end.hammerTeam === 1
            );
        })();

    // WP after this end (for team 1)
    const nextHammer = (s1 > 0) ? 2 : (s2 > 0) ? 1 : end.hammerTeam;
    const wpAfter = E.WinProbability.get(
        end.runningScore1 - end.runningScore2,
        end.endsRemaining,
        nextHammer === 1
    );

    const wpSwing = wpAfter - wpBefore;
    const wpSwingPct = Math.abs(wpSwing * 100).toFixed(1);
    const wpDirection = wpSwing > 0.001 ? 'up' : wpSwing < -0.001 ? 'down' : 'flat';
    const wpArrow = wpDirection === 'up' ? '↑' : wpDirection === 'down' ? '↓' : '→';
    const swingColor = wpDirection === 'up' ? 'var(--positive)' : wpDirection === 'down' ? 'var(--negative)' : 'var(--text-tertiary)';

    // Build the card
    el.innerHTML = `
        <div class="end-summary__card">
            <div class="end-summary__header">
                <span class="end-summary__end-num">End ${end.end} of ${game.numberOfEnds || 10}</span>
                <span class="end-summary__badge end-summary__badge--${outcomeType}">${outcomeLabel}</span>
            </div>
            <div class="end-summary__score-line">
                ${game.team1.name} ${end.runningScore1} — ${end.runningScore2} ${game.team2.name}
                <span class="end-summary__score-change">${s1 > 0 ? `(+${s1})` : s2 > 0 ? `(+${s2})` : '(0-0)'}</span>
            </div>
            <div class="end-summary__narrative">${outcomeText}</div>
            <div class="end-summary__stats">
                <div class="end-summary__stat">
                    <span class="end-summary__stat-value">${hammerTeamName.split(' ').pop()}</span>
                    <span class="end-summary__stat-label">Hammer</span>
                </div>
                <div class="end-summary__stat">
                    <span class="end-summary__stat-value">${end.endsRemaining}</span>
                    <span class="end-summary__stat-label">Ends Left</span>
                </div>
                <div class="end-summary__stat">
                    <span class="end-summary__stat-value">${Math.round(wpAfter * 100)}%</span>
                    <span class="end-summary__stat-label">${game.team1.name.split(' ').pop()} WP</span>
                </div>
            </div>
            <div class="end-summary__wp-swing">
                <span class="end-summary__wp-swing-arrow" style="color:${swingColor}">${wpArrow}</span>
                <div class="end-summary__wp-swing-bar">
                    <div class="end-summary__wp-swing-fill" style="width:${Math.round(wpAfter * 100)}%;background:${swingColor}"></div>
                </div>
                <span class="end-summary__wp-swing-text" style="color:${swingColor}">
                    ${wpDirection === 'flat' ? 'No swing' : `${wpSwingPct}pp ${wpDirection === 'up' ? 'for' : 'against'} ${game.team1.name.split(' ').pop()}`}
                </span>
            </div>
        </div>
    `;
}

function updateReplayControls() {
    const ends = gameBrowser.selectedEnds;
    const game = gameBrowser.selectedGame;
    const idx = state.replayEndIndex;
    const prevBtn = document.getElementById('replay-prev');
    const nextBtn = document.getElementById('replay-next');
    const labelEl = document.getElementById('replay-label');
    const detailEl = document.getElementById('replay-detail');
    const loadBtn = document.getElementById('btn-load-game-state');

    if (!ends || !game || !prevBtn) return;

    if (idx < 0) {
        // No end selected yet
        prevBtn.disabled = true;
        nextBtn.disabled = ends.length === 0;
        labelEl.textContent = 'Click an end to start';
        detailEl.textContent = `${ends.length} ends played`;
        if (loadBtn) loadBtn.querySelector('.action-btn__label').textContent = 'Load Final State';
        
        // Reset WP bar opacity
        document.querySelectorAll('#game-wp-chart .wp-bar').forEach(bar => {
            bar.style.opacity = '1';
        });
        // Reset timeline dots
        document.querySelectorAll('.replay-dot').forEach(d => d.classList.remove('active'));
        // Clear end summary
        const summaryEl = document.getElementById('end-summary');
        if (summaryEl) summaryEl.innerHTML = '';
        return;
    }

    const end = ends[idx];
    prevBtn.disabled = idx <= 0;
    nextBtn.disabled = idx >= ends.length - 1;

    const s1 = game.team1.endScores[idx] || 0;
    const s2 = game.team2.endScores[idx] || 0;
    const hammerName = end.hammerTeam === 1 ? game.team1.name : game.team2.name;

    let outcome = '';
    if (s1 === 0 && s2 === 0) outcome = 'Blank end';
    else if (s1 > 0) outcome = `${game.team1.name} scored ${s1}`;
    else outcome = `${game.team2.name} scored ${s2}`;

    labelEl.textContent = `End ${end.end} — ${outcome}`;
    detailEl.textContent = `${end.runningScore1}-${end.runningScore2} · ${hammerName} had hammer · ${end.endsRemaining} remaining`;
    
    if (loadBtn) loadBtn.querySelector('.action-btn__label').textContent = `Load After End ${end.end}`;

    // Highlight active timeline dot
    document.querySelectorAll('.replay-dot').forEach((d, i) => {
        d.classList.toggle('active', i === idx);
    });
}

// Replay navigation buttons
document.getElementById('replay-prev')?.addEventListener('click', () => {
    stopAutoPlay();
    if (state.replayEndIndex > 0) setReplayEnd(state.replayEndIndex - 1);
});
document.getElementById('replay-next')?.addEventListener('click', () => {
    stopAutoPlay();
    const ends = gameBrowser.selectedEnds;
    if (ends && state.replayEndIndex < ends.length - 1) setReplayEnd(state.replayEndIndex + 1);
});
document.getElementById('replay-autoplay')?.addEventListener('click', toggleAutoPlay);

function loadGameFromBrowser() {
    const game = gameBrowser.selectedGame;
    const ends = gameBrowser.selectedEnds;
    if (!game || !ends || ends.length === 0) return;

    // Use replay end index if set, otherwise use last end
    const endIdx = state.replayEndIndex >= 0 ? state.replayEndIndex : ends.length - 1;
    const targetEnd = ends[endIdx];

    // Set game state
    state.scoreRed = targetEnd.runningScore1;
    state.scoreYellow = targetEnd.runningScore2;
    state.currentEnd = Math.min(targetEnd.end + 1, C.ENDS_TOTAL);

    // Determine hammer for next end
    const s1 = game.team1.endScores[targetEnd.end - 1] || 0;
    const s2 = game.team2.endScores[targetEnd.end - 1] || 0;
    if (s1 > 0) state.hammerTeam = 'yellow';
    else if (s2 > 0) state.hammerTeam = 'red';
    else state.hammerTeam = targetEnd.hammerTeam === 1 ? 'red' : 'yellow';

    // Clear stones (no position data from API)
    state.stones = [];
    state.nextStoneId = 1;
    state.analysisResults = null;

    // Update UI
    syncUIFromState();
    drawMain();
    updateDashboard();
    saveGameState();

    // Track this game in recent games
    addRecentGame(game, gameBrowser.currentEvent?.name || '');

    // Track progression
    bumpStat('gamesStudied');

    // Store game context for capture mode
    state.loadedGameContext = {
        game,
        endIdx: endIdx,
        end: targetEnd,
    };
    state.mode = 'capture';

    // Close browser
    toggleGameBrowser();
    showToast(`Loaded End ${targetEnd.end}: ${game.team1.name} ${state.scoreRed}–${state.scoreYellow} ${game.team2.name}`, 'positive');

    // Update URL hash
    if (window.RoboSkipData) {
        window.location.hash = window.RoboSkipData.encodeStateToHash(state).slice(1);
    }
}

/** Sync all UI elements from current state values */
function syncUIFromState() {
    document.getElementById('score-red').textContent = state.scoreRed;
    document.getElementById('score-yellow').textContent = state.scoreYellow;
    document.getElementById('end-select').value = state.currentEnd;
    document.getElementById('hammer-label').textContent = state.hammerTeam === 'red' ? 'Red' : 'Yellow';
    document.getElementById('btn-hammer').classList.toggle('hammer-btn--red', state.hammerTeam === 'red');
    document.getElementById('btn-hammer').classList.toggle('hammer-btn--yellow', state.hammerTeam === 'yellow');
    
}

/** Progression stat tracking */
function bumpStat(key) {
    const stats = lsGet(LS_PREFIX + 'stats', {});
    stats[key] = (stats[key] || 0) + 1;
    stats.lastActive = Date.now();
    
    // Track streak
    const today = new Date().toISOString().slice(0, 10);
    if (stats.lastDay !== today) {
        const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10);
        if (stats.lastDay === yesterday) {
            stats.streak = (stats.streak || 0) + 1;
        } else {
            stats.streak = 1;
        }
        stats.lastDay = today;
    }
    
    lsSet(LS_PREFIX + 'stats', stats);
    return stats;
}

function getStats() {
    return lsGet(LS_PREFIX + 'stats', { positionsAnalyzed: 0, gamesStudied: 0, streak: 0 });
}

// Header action event listeners
document.getElementById('btn-new-game')?.addEventListener('click', newGame);
document.getElementById('btn-share')?.addEventListener('click', sharePosition);

// Game browser event listeners
document.getElementById('btn-browse-games')?.addEventListener('click', toggleGameBrowser);
document.getElementById('btn-close-browser')?.addEventListener('click', toggleGameBrowser);
document.getElementById('game-browser')?.addEventListener('click', (e) => {
    if (e.target === e.currentTarget) toggleGameBrowser();
});
document.getElementById('btn-back-tournaments')?.addEventListener('click', loadTournamentList);
document.getElementById('btn-back-games')?.addEventListener('click', () => {
    document.getElementById('game-detail').style.display = 'none';
    document.getElementById('game-list').style.display = '';
});
document.getElementById('btn-load-game-state')?.addEventListener('click', loadGameFromBrowser);

// ═══════════════════════════════════════════════════════════════════════════
// URL HASH — Update on state changes
// ═══════════════════════════════════════════════════════════════════════════

function updateURLHash() {
    if (window.RoboSkipData && state.stones.length > 0) {
        const hash = window.RoboSkipData.encodeStateToHash(state);
        if (window.location.hash !== hash) {
            history.replaceState(null, '', hash);
        }
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// SHARE POSITION
// ═══════════════════════════════════════════════════════════════════════════

async function sharePosition() {
    const activeStones = state.stones.filter(s => s.active);
    if (activeStones.length === 0) {
        showToast('Place stones first to share', 'info');
        return;
    }

    updateURLHash();
    const url = window.location.href;

    // Try native share API first (mobile), then clipboard
    if (navigator.share) {
        try {
            await navigator.share({
                title: 'Robo-Skip Position',
                text: `Curling position: ${activeStones.length} stones, End ${state.currentEnd}`,
                url: url,
            });
            showToast('Shared!', 'positive');
            return;
        } catch (_) {} // User cancelled or not supported
    }

    // Fallback: copy to clipboard
    try {
        await navigator.clipboard.writeText(url);
        showToast('Link copied!', 'positive');
    } catch (_) {
        // Final fallback
        const input = document.createElement('input');
        input.value = url;
        document.body.appendChild(input);
        input.select();
        document.execCommand('copy');
        document.body.removeChild(input);
        showToast('Link copied!', 'positive');
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// PWA INSTALL PROMPT
// ═══════════════════════════════════════════════════════════════════════════

let deferredInstallPrompt = null;

window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredInstallPrompt = e;
    
    // Show install button after short delay
    setTimeout(() => {
        showToast('Install Robo-Skip for offline use', 'info', 8000);
    }, 5000);
});

// ═══════════════════════════════════════════════════════════════════════════
// LOADING SHIMMER HELPERS
// ═══════════════════════════════════════════════════════════════════════════

function createShimmerCards(count, className) {
    return Array(count).fill(0).map(() => 
        `<div class="${className} shimmer-card" aria-hidden="true"><div class="shimmer-line" style="width:60%"></div><div class="shimmer-line short" style="width:30%"></div></div>`
    ).join('');
}

// Hook into state changes
const _origUpdateDashboard = updateDashboard;
updateDashboard = function() {
    _origUpdateDashboard();
    updateURLHash();
};

// ═══════════════════════════════════════════════════════════════════════════
// DAILY PUZZLE
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Seeded PRNG (mulberry32) — deterministic from day string.
 */
function mulberry32(seed) {
    let t = seed | 0;
    return function() {
        t = (t + 0x6D2B79F5) | 0;
        let r = Math.imul(t ^ (t >>> 15), 1 | t);
        r ^= r + Math.imul(r ^ (r >>> 7), 61 | r);
        return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
    };
}

function dayHash(dateStr) {
    let h = 0;
    for (let i = 0; i < dateStr.length; i++) {
        h = ((h << 5) - h + dateStr.charCodeAt(i)) | 0;
    }
    return h;
}

// ═══════════════════════════════════════════════════════════════════════════
// PUZZLE GENERATOR — Optimal procedural curling puzzles
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Scenario templates: curated tactical situations that produce interesting puzzles.
 * Each template has a pattern function that places stones using the seeded RNG
 * and a description of the strategic theme.
 */
const PUZZLE_TEMPLATES = [
    {
        name: 'Buried Draw',
        desc: 'Draw behind cover to score',
        build(rng) {
            // Opponent stone on button, our guard in front, need to draw behind it
            const stones = [];
            const oppX = (rng() - 0.5) * 0.4;
            stones.push(new E.Stone(oppX, -0.1, 'yellow', 1));            // opp near button
            stones.push(new E.Stone(oppX + (rng() - 0.5) * 0.3, 2.2, 'red', 2)); // our guard
            if (rng() > 0.3) stones.push(new E.Stone(oppX + 0.8 * (rng() > 0.5 ? 1 : -1), 0.5, 'yellow', 3));
            if (rng() > 0.5) stones.push(new E.Stone(-oppX * 0.5, 1.0, 'red', 4));
            return stones;
        }
    },
    {
        name: 'Double Takeout',
        desc: 'Remove two opponent stones in one shot',
        build(rng) {
            const stones = [];
            const spread = 0.25 + rng() * 0.15;
            const cy = -0.3 + rng() * 0.6;
            stones.push(new E.Stone(-spread, cy, 'yellow', 1));
            stones.push(new E.Stone(spread, cy + (rng() - 0.5) * 0.15, 'yellow', 2));
            stones.push(new E.Stone(0, 2.5, 'red', 3)); // guard
            if (rng() > 0.4) stones.push(new E.Stone(0.6 * (rng() > 0.5 ? 1 : -1), -0.8, 'red', 4));
            return stones;
        }
    },
    {
        name: 'Freeze',
        desc: 'Draw tight to opponent stone',
        build(rng) {
            const stones = [];
            const ox = (rng() - 0.5) * 1.0;
            const oy = -0.5 + rng() * 0.8;
            stones.push(new E.Stone(ox, oy, 'yellow', 1)); // target stone
            stones.push(new E.Stone(-ox * 0.3, 1.5 + rng() * 0.5, 'red', 2)); // guard
            if (rng() > 0.3) stones.push(new E.Stone(ox + 0.6, oy + 0.3, 'red', 3));
            if (rng() > 0.5) stones.push(new E.Stone(-ox, oy - 0.4, 'yellow', 4));
            return stones;
        }
    },
    {
        name: 'Hit & Roll',
        desc: 'Remove opponent and roll to scoring position',
        build(rng) {
            const stones = [];
            const side = rng() > 0.5 ? 1 : -1;
            stones.push(new E.Stone(side * 0.8, 0.3, 'yellow', 1));  // target
            stones.push(new E.Stone(-side * 0.4, -0.2, 'red', 2));    // our counter
            stones.push(new E.Stone(0, 2.0, 'red', 3));               // guard
            if (rng() > 0.4) stones.push(new E.Stone(side * 0.3, -1.0, 'yellow', 4));
            if (rng() > 0.5) stones.push(new E.Stone(-side * 0.9, 0.8, 'yellow', 5));
            return stones;
        }
    },
    {
        name: 'Peel the Guard',
        desc: 'Remove the guard to open the house',
        build(rng) {
            const stones = [];
            const gx = (rng() - 0.5) * 0.6;
            stones.push(new E.Stone(gx, 2.5 + rng() * 0.5, 'yellow', 1));        // guard
            stones.push(new E.Stone(gx + (rng() - 0.5) * 0.3, -0.2, 'yellow', 2)); // behind guard
            stones.push(new E.Stone(-gx, 0.5, 'red', 3));
            if (rng() > 0.3) stones.push(new E.Stone(gx * 0.5, 1.2, 'red', 4));
            return stones;
        }
    },
    {
        name: 'Crowded House',
        desc: 'Navigate through traffic',
        build(rng) {
            const stones = [];
            // 5-7 stones scattered in/around house
            const n = 5 + Math.floor(rng() * 3);
            const teams = ['red', 'yellow'];
            for (let i = 0; i < n; i++) {
                const angle = rng() * Math.PI * 2;
                const dist = rng() * 1.8;
                const x = Math.cos(angle) * dist;
                const y = Math.sin(angle) * dist * 0.6 + (rng() - 0.5) * 0.5;
                const overlap = stones.some(s => {
                    const dx = s.x - x, dy = s.y - y;
                    return Math.sqrt(dx * dx + dy * dy) < C.STONE_RADIUS * 2.5;
                });
                if (!overlap) {
                    stones.push(new E.Stone(
                        E.clamp(x, -C.SHEET_WIDTH / 2 + 0.2, C.SHEET_WIDTH / 2 - 0.2),
                        E.clamp(y, C.BACK_LINE_Y + 0.2, C.HOG_LINE_Y - 1),
                        teams[i % 2], i + 1
                    ));
                }
            }
            return stones;
        }
    },
    {
        name: 'Last Stone Draw',
        desc: 'Draw to the button with last stone',
        build(rng) {
            const stones = [];
            stones.push(new E.Stone((rng() - 0.5) * 0.6, -0.3 - rng() * 0.3, 'yellow', 1));
            if (rng() > 0.3) stones.push(new E.Stone((rng() - 0.5) * 1.2, 0.8, 'yellow', 2));
            stones.push(new E.Stone((rng() - 0.5) * 0.8, 0.5, 'red', 3));
            if (rng() > 0.4) stones.push(new E.Stone(0, 2.8, 'red', 4));
            return stones;
        }
    },
    {
        name: 'Raise to Score',
        desc: 'Promote your own stone to a scoring position',
        build(rng) {
            const stones = [];
            const side = rng() > 0.5 ? 1 : -1;
            // Our stone sitting in front of house
            stones.push(new E.Stone(side * 0.3, 1.5 + rng() * 0.5, 'red', 1));
            // Opponent stones inside
            stones.push(new E.Stone(-side * 0.2, -0.1, 'yellow', 2));
            stones.push(new E.Stone(side * 0.5, -0.5, 'yellow', 3));
            if (rng() > 0.4) stones.push(new E.Stone(-side * 0.7, 0.6, 'red', 4));
            return stones;
        }
    },
    {
        name: 'Tick Shot',
        desc: 'Nudge a guard aside without removing it',
        build(rng) {
            const stones = [];
            const gx = (rng() - 0.5) * 0.4;
            // Opponent guard protecting the button
            stones.push(new E.Stone(gx, 2.0 + rng() * 0.8, 'yellow', 1));
            // Opponent on button behind the guard
            stones.push(new E.Stone(gx + (rng() - 0.5) * 0.2, -0.1, 'yellow', 2));
            // Our stone in 8-foot
            stones.push(new E.Stone(-gx + (rng() - 0.5) * 0.3, 0.4, 'red', 3));
            if (rng() > 0.5) stones.push(new E.Stone(gx * 2, 1.0, 'yellow', 4));
            return stones;
        }
    },
    {
        name: 'Corner Freeze',
        desc: 'Tight freeze on the edge of the house',
        build(rng) {
            const stones = [];
            const side = rng() > 0.5 ? 1 : -1;
            // Opponent stone on the wing
            stones.push(new E.Stone(side * 1.2, 0.2 + rng() * 0.3, 'yellow', 1));
            // Our stone near center
            stones.push(new E.Stone(-side * 0.3, -0.4, 'red', 2));
            // Guards
            stones.push(new E.Stone(side * 0.4, 2.0, 'red', 3));
            if (rng() > 0.3) stones.push(new E.Stone(side * 0.8, -0.6, 'yellow', 4));
            return stones;
        }
    },
    {
        name: 'Steal Opportunity',
        desc: 'Score without the hammer — aggressive play',
        build(rng) {
            const stones = [];
            // We don't have hammer, but have a scoring chance
            stones.push(new E.Stone((rng() - 0.5) * 0.4, -0.2, 'red', 1));  // our shot stone near button
            stones.push(new E.Stone(0, 0.6, 'yellow', 2));                    // opponent counter
            stones.push(new E.Stone((rng() - 0.5) * 0.8, 2.5, 'yellow', 3)); // opponent guard
            if (rng() > 0.3) stones.push(new E.Stone(-0.8, -0.5, 'red', 4));
            if (rng() > 0.5) stones.push(new E.Stone(0.7, 1.0, 'yellow', 5));
            return stones;
        },
        hammerOverride: 'yellow'  // opponent has hammer — we're trying to steal
    },
    {
        name: 'Runback',
        desc: 'Hit your own stone into an opponent behind it',
        build(rng) {
            const stones = [];
            const side = rng() > 0.5 ? 1 : -1;
            // Our stone in front
            stones.push(new E.Stone(side * 0.2, 1.2, 'red', 1));
            // Opponent behind ours
            stones.push(new E.Stone(side * 0.25, -0.3, 'yellow', 2));
            // Additional stones
            stones.push(new E.Stone(-side * 0.6, 0.5, 'red', 3));
            if (rng() > 0.4) stones.push(new E.Stone(-side * 0.3, -0.8, 'yellow', 4));
            return stones;
        }
    },
];

/**
 * Generate a puzzle: pick template by date seed, build position, 
 * set up game context with meaningful score state.
 */
function generatePuzzle(dateStr) {
    const rng = mulberry32(dayHash(dateStr));
    
    // Pick template deterministically
    const template = PUZZLE_TEMPLATES[Math.floor(rng() * PUZZLE_TEMPLATES.length)];
    
    // Build stones from template
    const stones = template.build(rng);
    
    // Validate stones: ensure none overlap and all are in-bounds
    for (let i = stones.length - 1; i >= 0; i--) {
        const s = stones[i];
        if (s.x < -C.SHEET_WIDTH / 2 + 0.1 || s.x > C.SHEET_WIDTH / 2 - 0.1 ||
            s.y < C.BACK_LINE_Y + 0.1 || s.y > C.HOG_LINE_Y) {
            stones.splice(i, 1);
            continue;
        }
        for (let j = 0; j < i; j++) {
            const dx = stones[j].x - s.x, dy = stones[j].y - s.y;
            if (Math.sqrt(dx * dx + dy * dy) < C.STONE_RADIUS * 2.1) {
                stones.splice(i, 1);
                break;
            }
        }
    }
    
    // Game context — vary the stakes for more interesting decisions
    // Weighted toward later ends and close scores for drama
    const scenarios = [
        { end: 8, diff:  0, desc: 'Tied, 8th end' },
        { end: 9, diff: -1, desc: 'Down 1, 9th end' },
        { end: 10, diff: 0, desc: 'Tied, final end!' },
        { end: 7, diff:  1, desc: 'Up 1, 7th end' },
        { end: 8, diff: -2, desc: 'Down 2, 8th end' },
        { end: 9, diff:  1, desc: 'Up 1, 9th end' },
        { end: 6, diff:  0, desc: 'Tied, 6th end' },
        { end: 10, diff: -1, desc: 'Down 1, final end!' },
    ];
    const scenario = scenarios[Math.floor(rng() * scenarios.length)];
    const endNumber = scenario.end;
    const scoreDiff = scenario.diff;
    const hammerTeam = template.hammerOverride || (rng() > 0.5 ? 'red' : 'yellow');
    const activeTeam = 'red'; // always Red plays (consistency for sharing)
    const turnNumber = stones.length;
    
    return {
        dateStr, stones, activeTeam, hammerTeam, endNumber, scoreDiff, turnNumber,
        templateName: template.name, templateDesc: template.desc,
        scenarioDesc: scenario.desc,
    };
}

/**
 * Initialize daily puzzle.
 * Auto-analyzes position, shows recommended shots, forces throw mechanic.
 */
function initDailyPuzzle() {
    const today = new Date();
    const dateStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
    
    // Check saved state
    const saved = localStorage.getItem('roboskip_puzzle');
    let puzzleData;
    try { puzzleData = saved ? JSON.parse(saved) : null; } catch { puzzleData = null; }
    
    const puzzle = generatePuzzle(dateStr);
    state.puzzle = {
        ...puzzle,
        solved: puzzleData?.dateStr === dateStr && puzzleData.solved,
        bestShot: null,
        allResults: null,
        playerShot: null,
        analyzing: true,
    };
    
    // Set up board — throw only, no placement
    state.stones = puzzle.stones.map(s => s.clone());
    state.nextStoneId = puzzle.stones.length + 1;
    state.activeTeam = puzzle.activeTeam;
    state.hammerTeam = puzzle.hammerTeam;
    state.currentEnd = puzzle.endNumber;
    state.scoreRed = puzzle.scoreDiff > 0 ? puzzle.scoreDiff : 0;
    state.scoreYellow = puzzle.scoreDiff < 0 ? -puzzle.scoreDiff : 0;
    state.turnNumber = puzzle.turnNumber;
    state.analysisResults = null;
    state.hoveredShot = null;
    state.undoStack = [];
    
    // Update prompt
    const textEl = document.getElementById('puzzle-text');
    const metaEl = document.getElementById('puzzle-meta');
    
    if (textEl) textEl.textContent = `${puzzle.templateDesc || puzzle.templateName}`;
    if (metaEl) {
        const hammerStr = puzzle.hammerTeam === 'red' ? '🔴 Hammer' : '🟡 Hammer';
        const scenarioStr = puzzle.scenarioDesc || `End ${puzzle.endNumber}`;
        metaEl.textContent = `${scenarioStr} · ${hammerStr} · Drag from hack to throw`;
    }
    
    drawMain();
    updateDashboard();
    
    // Auto-analyze (shows recommended shots so player can study)
    runPuzzleAnalysis();
    
    if (state.puzzle.solved) {
        showToast('Already solved — try again tomorrow!', 'info');
    }
}

/**
 * Run analysis to find optimal shot. Shows results in the shot panel
 * so the player can study what the computer thinks before throwing.
 */
async function runPuzzleAnalysis() {
    if (!state.puzzle || state.mode !== 'puzzle') return;
    const puzzleMode = state.mode; // capture for race-condition check
    
    const scoreDiff = state.scoreRed - state.scoreYellow;
    const endsRemaining = C.ENDS_TOTAL - state.currentEnd + 1;
    const gameState = { scoreDiff, endsRemaining, hammerTeam: state.hammerTeam };
    
    showToast('Analyzing position...', 'info', 2000);
    
    try {
        const results = await E.WorkerPool.evaluateParallel(
            state.stones, gameState, state.activeTeam,
            C.MC_FULL_N, null, { turnNumber: state.turnNumber }
        );
        if (state.mode !== puzzleMode || !state.puzzle) return; // mode changed during async
        if (results.length > 0) {
            state.puzzle.bestShot = results[0];
            state.puzzle.allResults = results;
            state.analysisResults = results; // show in shot panel
            state.puzzle.analyzing = false;
            updateShotsDisplay();
            showToast('Position analyzed — drag from the hack to throw!', 'positive', 3000);
        }
    } catch {
        if (state.mode !== puzzleMode || !state.puzzle) return;
        const results = E.ShotEvaluator.evaluateAll(
            state.stones, gameState, state.activeTeam,
            C.MC_QUICK_N, null, { turnNumber: state.turnNumber }
        );
        if (state.mode !== puzzleMode || !state.puzzle) return;
        if (results.length > 0) {
            state.puzzle.bestShot = results[0];
            state.puzzle.allResults = results;
            state.analysisResults = results;
            state.puzzle.analyzing = false;
            updateShotsDisplay();
        }
    }
}

/**
 * Handle player's throw in puzzle mode.
 * Evaluates via MC and shows comparison after animation resolves.
 */
function handlePuzzleShot(candidate) {
    if (!state.puzzle || state.puzzle.solved) return;
    
    const scoreDiff = state.scoreRed - state.scoreYellow;
    const endsRemaining = C.ENDS_TOTAL - state.currentEnd + 1;
    const gameState = { scoreDiff, endsRemaining, hammerTeam: state.hammerTeam };
    
    // Evaluate player's shot with full MC for accurate rating
    const playerResult = E.ShotEvaluator.evaluateShot(
        state.puzzle.stones, candidate, gameState, state.activeTeam, C.MC_FULL_N
    );
    
    state.puzzle.playerShot = { candidate, result: playerResult };
    state.puzzle.solved = true;
    
    // Compute rating (0-5 blocks for sharing)
    const bDelta = state.puzzle.bestShot?.wpDelta || 0;
    const diff = bDelta - playerResult.wpDelta;
    let rating;
    if (diff < 0.02) rating = 5;       // Perfect
    else if (diff < 0.05) rating = 4;   // Great
    else if (diff < 0.10) rating = 3;   // Good
    else if (diff < 0.20) rating = 2;   // Decent
    else if (diff < 0.35) rating = 1;   // Okay
    else rating = 0;                      // Miss
    
    // Save to localStorage
    const saveData = {
        dateStr: state.puzzle.dateStr,
        solved: true,
        playerWpDelta: playerResult.wpDelta,
        bestWpDelta: bDelta,
        rating,
        shotName: candidate.name || 'Manual Throw',
    };
    localStorage.setItem('roboskip_puzzle', JSON.stringify(saveData));
    
    // Update streak stats
    const stats = JSON.parse(localStorage.getItem('roboskip_puzzle_stats') || '{"played":0,"perfect":0,"streak":0}');
    stats.played++;
    if (rating === 5) stats.perfect++;
    
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    const ydStr = `${yesterday.getFullYear()}-${String(yesterday.getMonth() + 1).padStart(2, '0')}-${String(yesterday.getDate()).padStart(2, '0')}`;
    if (stats.lastDate === ydStr) {
        stats.streak = (stats.streak || 0) + 1;
    } else if (stats.lastDate !== state.puzzle.dateStr) {
        stats.streak = 1;
    }
    stats.lastDate = state.puzzle.dateStr;
    localStorage.setItem('roboskip_puzzle_stats', JSON.stringify(stats));
    
    // Show result after animation settles
    setTimeout(() => showPuzzleResult(playerResult, stats, rating), 2500);
}

function showPuzzleResult(playerResult, stats, rating) {
    const resultEl = document.getElementById('puzzle-result');
    const titleEl = document.getElementById('puzzle-result-title');
    const scoreEl = document.getElementById('puzzle-result-score');
    const detailsEl = document.getElementById('puzzle-result-details');
    const bestEl = document.getElementById('puzzle-result-best');
    
    if (!resultEl) return;
    
    const pDelta = playerResult.wpDelta;
    const bDelta = state.puzzle.bestShot?.wpDelta || 0;
    const puzzleNum = Math.floor((Date.now() - new Date('2025-01-01').getTime()) / 86400000);
    
    // Rating tiers
    const ratingNames = ['Wide Miss', 'Passable', 'Decent', 'Good Shot', 'Great Shot!', 'Perfect!'];
    const ratingEmoji = ['💨', '🪨', '🤔', '👍', '🥌', '🎯'];
    const ratingColors = ['var(--negative)', 'var(--text-tertiary)', 'var(--warning)', 'var(--ice)', 'var(--positive)', 'var(--positive)'];
    const blocks = '🟩'.repeat(rating) + '⬜'.repeat(5 - rating);
    
    titleEl.textContent = `${ratingEmoji[rating]} ${ratingNames[rating]}`;
    titleEl.style.color = ratingColors[rating];
    
    // WP score with context
    const wpPct = (pDelta * 100).toFixed(1);
    const wpSign = pDelta > 0 ? '+' : '';
    scoreEl.textContent = `${wpSign}${wpPct}% WP`;
    scoreEl.style.color = pDelta >= 0 ? 'var(--positive)' : 'var(--negative)';
    
    // Detailed breakdown
    let html = `<div class="puzzle-blocks">${blocks}</div>`;
    html += `<div class="puzzle-stats-grid">`;
    html += `<div class="puzzle-stat"><span class="puzzle-stat__val">#${puzzleNum}</span><span class="puzzle-stat__label">Puzzle</span></div>`;
    html += `<div class="puzzle-stat"><span class="puzzle-stat__val">${stats.streak || 1}</span><span class="puzzle-stat__label">Streak</span></div>`;
    html += `<div class="puzzle-stat"><span class="puzzle-stat__val">${stats.played || 1}</span><span class="puzzle-stat__label">Played</span></div>`;
    html += `<div class="puzzle-stat"><span class="puzzle-stat__val">${stats.perfect || 0}</span><span class="puzzle-stat__label">Perfect</span></div>`;
    html += `</div>`;
    
    // Player shot analysis
    const playerShotName = state.puzzle.playerShot?.candidate.name || 'Manual Throw';
    const successPct = (playerResult.successRate * 100).toFixed(0);
    html += `<div class="puzzle-player-shot">`;
    html += `Your shot: <strong>${playerShotName}</strong> · ${successPct}% success rate`;
    html += `</div>`;
    
    detailsEl.innerHTML = html;
    
    // Best shot reveal with alternatives
    if (state.puzzle.bestShot) {
        const b = state.puzzle.bestShot;
        const bWp = (b.wpDelta * 100).toFixed(1);
        const bSign = b.wpDelta > 0 ? '+' : '';
        let bHtml = `<div class="puzzle-optimal">`;
        bHtml += `<div class="puzzle-optimal__label">Optimal Shot</div>`;
        bHtml += `<div class="puzzle-optimal__name">${b.candidate.icon || ''} ${b.candidate.name}</div>`;
        bHtml += `<div class="puzzle-optimal__wp">${bSign}${bWp}% WP · ${(b.successRate * 100).toFixed(0)}% success</div>`;
        bHtml += `</div>`;
        
        if (state.puzzle.allResults && state.puzzle.allResults.length > 1) {
            bHtml += `<div class="puzzle-alternatives">`;
            state.puzzle.allResults.slice(1, 4).forEach((r, i) => {
                const rWp = (r.wpDelta * 100).toFixed(1);
                const rSign = r.wpDelta > 0 ? '+' : '';
                bHtml += `<div class="puzzle-alt">${i + 2}. ${r.candidate.name} <span>${rSign}${rWp}%</span></div>`;
            });
            bHtml += `</div>`;
        }
        bestEl.innerHTML = bHtml;
    }
    
    resultEl.classList.add('visible');
    playSound('endComplete');
}

/**
 * Generate shareable text for the puzzle result (Wordle-style).
 */
function getPuzzleShareText() {
    const saved = localStorage.getItem('roboskip_puzzle');
    if (!saved) return null;
    const data = JSON.parse(saved);
    if (!data.solved) return null;
    
    const stats = JSON.parse(localStorage.getItem('roboskip_puzzle_stats') || '{}');
    const puzzleNum = Math.floor((Date.now() - new Date('2025-01-01').getTime()) / 86400000);
    const blocks = '🟩'.repeat(data.rating) + '⬜'.repeat(5 - data.rating);
    const wpStr = `${data.playerWpDelta > 0 ? '+' : ''}${(data.playerWpDelta * 100).toFixed(1)}%`;
    
    const ratingNames = ['Miss', 'Passable', 'Decent', 'Good Shot', 'Great!', 'Perfect!'];
    const ratingEmoji = ['💨', '🪨', '🤔', '👍', '🥌', '🎯'];
    const rating = data.rating || 0;
    
    return [
        `🥌 Robo-Skip #${puzzleNum}`,
        `${blocks} ${ratingEmoji[rating]}`,
        `WP: ${wpStr} | ${ratingNames[rating]}`,
        stats.streak > 1 ? `🔥 ${stats.streak} day streak` : '',
        ``,
        `awktavian.github.io/art/robo-skip`,
    ].filter(Boolean).join('\n');
}

// Share puzzle result
document.getElementById('puzzle-result-share')?.addEventListener('click', async (e) => {
    const btn = e.currentTarget;
    const shareText = getPuzzleShareText();
    if (!shareText) return;
    
    // Visual feedback immediately
    const origText = btn.textContent;
    btn.style.transform = 'scale(0.95)';
    
    let shared = false;
    // Try native share first, fall back to clipboard
    if (navigator.share) {
        try {
            await navigator.share({ text: shareText });
            shared = true;
        } catch (err) {
            if (err.name !== 'AbortError') {
                // User didn't cancel — fallback to clipboard
                await navigator.clipboard?.writeText(shareText);
                shared = true;
            }
        }
    } else if (navigator.clipboard) {
        await navigator.clipboard.writeText(shareText);
        shared = true;
    }
    
    if (shared) {
        btn.textContent = 'Copied!';
        btn.style.background = 'var(--positive-glow)';
        btn.style.borderColor = 'var(--positive)';
        btn.style.color = 'var(--positive)';
        showToast('Result copied — paste in your group chat!', 'positive');
        playSound('place');
        setTimeout(() => {
            btn.textContent = origText;
            btn.style.transform = '';
            btn.style.background = '';
            btn.style.borderColor = '';
            btn.style.color = '';
        }, 2000);
    } else {
        btn.style.transform = '';
    }
});

// Close puzzle result
document.getElementById('puzzle-result-close')?.addEventListener('click', () => {
    document.getElementById('puzzle-result')?.classList.remove('visible');
});

// ═══════════════════════════════════════════════════════════════════════════
// END DAILY PUZZLE
// ═══════════════════════════════════════════════════════════════════════════

init();
