/**
 * Robo-Skip Voice Coach
 * =====================
 * Forge colony (Colonel Mustard / echo) — the AI's sensorimotor interface
 * to the curling sheet. Tools give the AI perception of board state and
 * motor control over the game, not the user.
 *
 * Perception:  observe_board, read_analysis, read_scoring, read_game_context
 * Action:      place_stone, remove_stone, execute_shot, run_analysis, set_game_state
 * Introspection: describe_shot_type
 *
 * h(x) >= 0 always
 */

'use strict';

(function () {
  const isLocal = location.hostname === 'localhost' || location.hostname === '127.0.0.1';
  const PROXY_BASE = isLocal ? 'ws://localhost:8766' : 'wss://kagami-realtime-proxy.fly.dev';

  const toggleBtn = document.getElementById('voice-toggle');
  const statusEl = document.getElementById('voice-status');
  const transcriptEl = document.getElementById('voice-transcript');
  const overlay = document.getElementById('voice-overlay');

  if (!toggleBtn || !window.RealtimeVoice) return;

  const config = window.buildVoiceConfig ? window.buildVoiceConfig('robo-skip') : null;

  let voice = null;
  let connected = false;
  let holding = false;

  // ═══════════════════════════════════════════════════════════════════════
  // STATE ACCESS
  // ═══════════════════════════════════════════════════════════════════════

  function gs() { return window._roboSkipState || {}; }
  const E = () => window.CurlingEngine;

  // ═══════════════════════════════════════════════════════════════════════
  // AI TOOLS — sensorimotor interface
  // ═══════════════════════════════════════════════════════════════════════

  const tools = [
    // ── PERCEPTION ──────────────────────────────────────────────────────
    {
      name: 'observe_board',
      description: 'Perceive the full board state: every stone position, distance to button, which team, scoring order, guards, and house occupancy. This is your primary visual sense.',
      parameters: { type: 'object', properties: {}, required: [] },
    },
    {
      name: 'read_analysis',
      description: 'Read the current Monte Carlo analysis results if available: top 5 recommended shots with win probability deltas, shot types, trajectories, and expected scoring distributions.',
      parameters: { type: 'object', properties: {}, required: [] },
    },
    {
      name: 'read_game_context',
      description: 'Read the full game context: mode, current end, scores, hammer, turn number, stones remaining, whether analysis is running, puzzle state.',
      parameters: { type: 'object', properties: {}, required: [] },
    },
    {
      name: 'describe_shot_type',
      description: 'Get a detailed tactical description of a curling shot type: what it does, when to use it, risk/reward profile.',
      parameters: {
        type: 'object',
        properties: { shot_type: { type: 'string', description: 'draw, guard, takeout, peel, freeze, hit-and-roll, raise, tick, runback, double, come-around' } },
        required: ['shot_type'],
      },
    },

    // ── ACTION ──────────────────────────────────────────────────────────
    {
      name: 'run_analysis',
      description: 'Trigger Monte Carlo shot analysis on the current board position. Results become available via read_analysis after computation completes (~1-3 seconds).',
      parameters: { type: 'object', properties: {}, required: [] },
    },
    {
      name: 'execute_shot',
      description: 'Execute a recommended shot by rank (1-5). Animates the throw with real-time physics. Only works after analysis has been run.',
      parameters: {
        type: 'object',
        properties: { rank: { type: 'integer', description: 'Shot rank from analysis, 1 = best recommended' } },
        required: ['rank'],
      },
    },
    {
      name: 'place_stone',
      description: 'Place a stone at specific coordinates on the sheet. Origin (0,0) = button. +y = toward hog line. Sheet width ~4.57m. Use for setting up positions.',
      parameters: {
        type: 'object',
        properties: {
          x: { type: 'number', description: 'X coordinate in meters (0 = center, +right, -left). Sheet half-width ~2.28m.' },
          y: { type: 'number', description: 'Y coordinate in meters (0 = button, +6.4 = hog line, -1.83 = back line).' },
          team: { type: 'string', enum: ['red', 'yellow'], description: 'Which team\'s stone to place.' },
        },
        required: ['x', 'y'],
      },
    },
    {
      name: 'remove_stone',
      description: 'Remove a specific stone from the board by its ID.',
      parameters: {
        type: 'object',
        properties: { stone_id: { type: 'integer', description: 'Stone ID (from observe_board)' } },
        required: ['stone_id'],
      },
    },
    {
      name: 'set_game_state',
      description: 'Modify game parameters: end number, hammer team, scores, active placement color.',
      parameters: {
        type: 'object',
        properties: {
          end: { type: 'integer', description: 'End number (1-10)' },
          hammer: { type: 'string', enum: ['red', 'yellow'], description: 'Which team has hammer' },
          score_red: { type: 'integer', description: 'Red team score' },
          score_yellow: { type: 'integer', description: 'Yellow team score' },
          active_team: { type: 'string', enum: ['red', 'yellow'], description: 'Which color to place next' },
        },
        required: [],
      },
    },
  ];

  function handleFunctionCall(name, args) {
    const s = gs();
    const engine = E();

    switch (name) {
      // ── PERCEPTION ────────────────────────────────────────────────────
      case 'observe_board': {
        const stones = (s.stones || []).map(st => {
          const d = Math.sqrt(st.x * st.x + st.y * st.y);
          const C = engine?.CurlingConst;
          const inHouse = C ? d <= C.HOUSE_RADIUS_12 + C.STONE_RADIUS : d < 2.0;
          const ring = !C ? null : d <= C.BUTTON_RADIUS ? 'button' : d <= C.HOUSE_RADIUS_4 ? '4-foot' : d <= C.HOUSE_RADIUS_8 ? '8-foot' : d <= C.HOUSE_RADIUS_12 ? '12-foot' : 'out';
          return {
            id: st.id, team: st.team,
            x: +st.x.toFixed(3), y: +st.y.toFixed(3),
            distance_to_button: +d.toFixed(3),
            in_house: inHouse, ring,
            is_guard: st.y > 0 && !inHouse,
          };
        });

        // Scoring order
        const sorted = stones.filter(st => st.in_house).sort((a, b) => a.distance_to_button - b.distance_to_button);
        const scoring = [];
        if (sorted.length > 0) {
          const closestTeam = sorted[0].team;
          for (const st of sorted) {
            if (st.team === closestTeam) scoring.push(st);
            else break;
          }
        }

        return {
          stones,
          stone_count: { total: stones.length, red: stones.filter(x => x.team === 'red').length, yellow: stones.filter(x => x.team === 'yellow').length },
          in_house: stones.filter(x => x.in_house).length,
          guards: stones.filter(x => x.is_guard).length,
          scoring_team: scoring.length > 0 ? scoring[0].team : null,
          scoring_count: scoring.length,
          scoring_stones: scoring.map(x => ({ id: x.id, distance: x.distance_to_button, ring: x.ring })),
        };
      }

      case 'read_analysis': {
        const results = s.analysisResults;
        if (!results || !Array.isArray(results) || results.length === 0) {
          return { available: false, analyzing: !!s.analyzing, message: s.analyzing ? 'Analysis in progress...' : 'No analysis results. Call run_analysis first.' };
        }
        return {
          available: true,
          shots: results.slice(0, 5).map((r, i) => ({
            rank: i + 1,
            type: r.type || r.shotType || 'unknown',
            wp_delta: +(r.wpDelta || 0).toFixed(3),
            wp_after: +(r.wpAfter || 0.5).toFixed(3),
            target: r.target ? { x: +r.target.x.toFixed(3), y: +r.target.y.toFixed(3) } : null,
            handle: r.handle || r.turn || 'unknown',
            description: r.description || '',
          })),
        };
      }

      case 'read_game_context': {
        return {
          mode: s.mode || 'puzzle',
          current_end: s.currentEnd || 1,
          score: { red: s.scoreRed || 0, yellow: s.scoreYellow || 0 },
          hammer_team: s.hammerTeam || 'red',
          active_team: s.activeTeam || 'red',
          turn_number: s.turnNumber || 0,
          stones_remaining: 16 - (s.stones || []).length,
          analyzing: !!s.analyzing,
          animating: !!s.animating,
          has_analysis: !!(s.analysisResults && s.analysisResults.length),
          puzzle: s.puzzle ? { date: s.puzzle.dateStr, prompt: s.puzzle.prompt || '' } : null,
        };
      }

      case 'describe_shot_type': {
        const descriptions = {
          'draw': { desc: 'Deliver stone to a specific spot without hitting anything.', when: 'When you need to score or set up position.', risk: 'Low — no collision physics. Requires precise weight.' },
          'guard': { desc: 'Place stone in front of the house to protect a scoring stone.', when: 'When you have a stone in scoring position that needs protection, especially with hammer.', risk: 'Low — placement shot. Guard too close can be peeled.' },
          'takeout': { desc: 'Remove an opponent stone from play with a direct hit.', when: 'When opponent has a better-positioned stone. Essential late in ends.', risk: 'Medium — must hit the stone. Miss = wasted shot.' },
          'peel': { desc: 'Remove a guard stone, ideally with both stones leaving play.', when: 'When opponent has guards protecting scoring stones.', risk: 'Medium — clean peel is difficult. Partial peel still useful.' },
          'freeze': { desc: 'Stop your stone touching an opponent stone. Extremely hard to remove.', when: 'When you want to make your stone very difficult to take out without giving up position.', risk: 'High precision required — too much weight = hit, too little = short.' },
          'hit-and-roll': { desc: 'Hit opponent stone and roll your stone to a protected position.', when: 'When you can remove a threat AND improve your position in one shot.', risk: 'High — requires precise angle and weight for both the hit and the roll.' },
          'raise': { desc: 'Hit your own stone to push it closer to the button.', when: 'When you have a stone that\'s almost scoring but needs to move closer.', risk: 'Medium — need to calculate the promotion angle.' },
          'tick': { desc: 'Barely touch a guard to move it sideways, opening a lane.', when: 'When a guard is protecting opponent stones and you want to create an angle.', risk: 'High — too much = takeout, too little = miss.' },
          'runback': { desc: 'Hit your own stone which then hits an opponent stone.', when: 'When you can\'t directly access an opponent stone but can reach it via your own.', risk: 'High — two-contact shot. Both angles must be right.' },
          'double': { desc: 'Remove two opponent stones in one shot.', when: 'When two opponent stones are aligned. Game-changing when it works.', risk: 'Very high — both contacts must connect. Miss either = disaster.' },
          'come-around': { desc: 'Curl around a guard stone into a protected scoring position.', when: 'When opponent has a guard and you want to score behind it.', risk: 'Medium-high — requires good curl read and precise handle/weight.' },
        };
        const d = descriptions[args.shot_type];
        return d || { error: `Unknown shot type. Valid: ${Object.keys(descriptions).join(', ')}` };
      }

      // ── ACTION ────────────────────────────────────────────────────────
      case 'run_analysis': {
        const btn = document.getElementById('btn-analyze');
        if (s.analyzing) return { status: 'already_running' };
        if (!s.stones || s.stones.length === 0) return { status: 'no_stones', message: 'Place stones before analyzing.' };
        if (btn) btn.click();
        return { status: 'started', message: 'Monte Carlo analysis started. Call read_analysis in a few seconds for results.' };
      }

      case 'execute_shot': {
        const rank = args.rank || 1;
        if (!s.analysisResults || s.analysisResults.length < rank) {
          return { status: 'no_results', message: 'Run analysis first.' };
        }
        document.dispatchEvent(new KeyboardEvent('keydown', { key: String(rank), bubbles: true }));
        return { status: 'executing', rank, shot: s.analysisResults[rank - 1]?.type || 'unknown' };
      }

      case 'place_stone': {
        const team = args.team || s.activeTeam || 'red';
        const x = args.x || 0;
        const y = args.y || 0;
        // Validate bounds
        const C = engine?.CurlingConst;
        if (C && (Math.abs(x) > C.SHEET_WIDTH / 2 || y < C.BACK_LINE_Y - 0.5 || y > C.HOG_LINE_Y + 1)) {
          return { status: 'out_of_bounds', message: 'Coordinates outside the sheet.' };
        }
        // Set active team and place via ghost system
        if (typeof setActiveTeam === 'function' && team !== s.activeTeam) setActiveTeam(team);
        if (typeof showGhost === 'function') showGhost(x, y);
        if (typeof confirmGhost === 'function') setTimeout(() => confirmGhost(), 50);
        return { status: 'placed', team, x, y };
      }

      case 'remove_stone': {
        const stone = (s.stones || []).find(st => st.id === args.stone_id);
        if (!stone) return { status: 'not_found', stone_id: args.stone_id };
        if (typeof removeStone === 'function') removeStone(stone);
        return { status: 'removed', stone_id: args.stone_id };
      }

      case 'set_game_state': {
        if (args.end !== undefined) {
          const sel = document.getElementById('end-select');
          if (sel) { sel.value = String(args.end); sel.dispatchEvent(new Event('change', { bubbles: true })); }
        }
        if (args.hammer !== undefined) {
          if (s.hammerTeam !== args.hammer) {
            const btn = document.getElementById('btn-hammer');
            if (btn) btn.click();
          }
        }
        if (args.score_red !== undefined) {
          const el = document.getElementById('score-red');
          if (el) { s.scoreRed = args.score_red; el.textContent = String(args.score_red); }
        }
        if (args.score_yellow !== undefined) {
          const el = document.getElementById('score-yellow');
          if (el) { s.scoreYellow = args.score_yellow; el.textContent = String(args.score_yellow); }
        }
        if (args.active_team !== undefined && typeof setActiveTeam === 'function') setActiveTeam(args.active_team);
        return { status: 'updated', ...args };
      }

      default:
        return { error: `Unknown tool: ${name}` };
    }
  }

  // ═══════════════════════════════════════════════════════════════════════
  // TRANSCRIPT
  // ═══════════════════════════════════════════════════════════════════════

  let transcriptBuffer = '';

  function appendTranscript(text, role) {
    if (role === 'user') { transcriptBuffer = ''; addLine('You: ' + text, 'user'); }
    else { transcriptBuffer += text; updateLast(transcriptBuffer); }
  }

  function addLine(text, cls) {
    const div = document.createElement('div');
    div.className = `voice-transcript__line voice-transcript__line--${cls}`;
    div.textContent = text;
    transcriptEl.appendChild(div);
    transcriptEl.scrollTop = transcriptEl.scrollHeight;
    while (transcriptEl.children.length > 8) transcriptEl.removeChild(transcriptEl.firstChild);
  }

  function updateLast(text) {
    let last = transcriptEl.querySelector('.voice-transcript__line--assistant:last-child');
    if (!last) { last = document.createElement('div'); last.className = 'voice-transcript__line voice-transcript__line--assistant'; transcriptEl.appendChild(last); }
    last.textContent = text;
    transcriptEl.scrollTop = transcriptEl.scrollHeight;
  }

  // ═══════════════════════════════════════════════════════════════════════
  // CONNECTION
  // ═══════════════════════════════════════════════════════════════════════

  async function connect() {
    const colony = config?.colony;
    const proxyUrl = new URL(PROXY_BASE);
    proxyUrl.searchParams.set('project', 'robo-skip');
    if (colony) proxyUrl.searchParams.set('colony', colony.colony.toLowerCase());

    voice = new RealtimeVoice({
      proxyUrl: proxyUrl.toString(),
      voice: config?.voice || 'echo',
      instructions: config?.instructions || 'You are a curling strategy coach.',
      tools,
      onTranscript: appendTranscript,
      onFunctionCall: handleFunctionCall,
      onStateChange: (s) => {
        overlay.dataset.state = s;
        const colony = config?.colony;
        statusEl.textContent = s === 'ready' ? (colony?.colony || 'Ready') : s === 'listening' ? 'Listening...' : s === 'speaking' ? 'Speaking' : s;
      },
      onError: (e) => { console.error('[VoiceCoach]', e); addLine('Error: ' + (e.message || e), 'error'); },
    });

    await voice.connect();
    connected = true;
    toggleBtn.classList.add('voice-toggle--active');
    const c = config?.colony;
    addLine(c ? `${c.character} (${c.colony}) online. Hold Space to speak.` : 'Voice coach online. Hold Space to speak.', 'system');
  }

  function disconnect() {
    if (voice) { voice.disconnect(); voice = null; }
    connected = false;
    toggleBtn.classList.remove('voice-toggle--active');
    statusEl.textContent = 'Off';
    overlay.dataset.state = 'disconnected';
  }

  // ═══════════════════════════════════════════════════════════════════════
  // EVENTS
  // ═══════════════════════════════════════════════════════════════════════

  toggleBtn.addEventListener('click', async () => {
    if (connected) { disconnect(); } else {
      statusEl.textContent = 'Connecting...';
      try { await connect(); } catch { statusEl.textContent = 'Failed'; addLine('Proxy unreachable at :8766', 'error'); }
    }
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'v' && !e.ctrlKey && !e.metaKey && e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') { e.preventDefault(); toggleBtn.click(); return; }
    if (e.key === ' ' && connected && !holding && e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') { e.preventDefault(); holding = true; voice.startListening(); }
  });

  document.addEventListener('keyup', (e) => { if (e.key === ' ' && holding) { e.preventDefault(); holding = false; if (voice) voice.stopListening(); } });

  // Expose state
  const raf = window.requestAnimationFrame;
  if (raf) { let synced = false; const trySync = () => { if (typeof state !== 'undefined') { window._roboSkipState = state; synced = true; } if (!synced) raf(trySync); }; raf(trySync); }
})();
