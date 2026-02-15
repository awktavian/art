/**
 * Robo-Skip Data Layer
 * ====================
 * Live game data from Curling IO API.
 * Fry et al. (2024) constrained geometric scoring model.
 * Famous games & tournament browser.
 * WP table computation from real competitive data.
 *
 * Zero hardcoded scoring distributions. Everything derived from data or model.
 */
'use strict';

const RoboSkipData = (() => {

    // ═══════════════════════════════════════════════════════════════════
    // API CLIENT — Curling IO
    // ═══════════════════════════════════════════════════════════════════

    const API_BASE = 'https://api-curlingio.global.ssl.fastly.net/en';
    const CORS_PROXIES = [
        url => `https://api.allorigins.win/raw?url=${encodeURIComponent(url)}`,
    ];

    let _proxyIndex = -1; // -1 = try direct first

    async function apiFetch(url) {
        // Try direct fetch first
        if (_proxyIndex === -1) {
            try {
                const res = await fetch(url, { mode: 'cors' });
                if (res.ok) return await res.json();
            } catch (_) { /* CORS blocked, fall through */ }
            _proxyIndex = 0;
        }

        // Try CORS proxies in order
        for (let i = _proxyIndex; i < CORS_PROXIES.length; i++) {
            try {
                const proxyUrl = CORS_PROXIES[i](url);
                const res = await fetch(proxyUrl);
                if (res.ok) {
                    _proxyIndex = i; // remember working proxy
                    return await res.json();
                }
            } catch (_) { continue; }
        }

        throw new Error(`Failed to fetch: ${url}`);
    }

    // ═══════════════════════════════════════════════════════════════════
    // CACHE — localStorage with TTL
    // ═══════════════════════════════════════════════════════════════════

    const CACHE_PREFIX = 'roboskip_';
    const CACHE_TTL_MS = 3600000; // 1 hour

    function cacheGet(key) {
        try {
            const raw = localStorage.getItem(CACHE_PREFIX + key);
            if (!raw) return null;
            const { data, ts } = JSON.parse(raw);
            if (Date.now() - ts > CACHE_TTL_MS) {
                localStorage.removeItem(CACHE_PREFIX + key);
                return null;
            }
            return data;
        } catch (_) { return null; }
    }

    function cacheSet(key, data) {
        try {
            localStorage.setItem(CACHE_PREFIX + key, JSON.stringify({ data, ts: Date.now() }));
        } catch (_) { /* quota exceeded */ }
    }

    // ═══════════════════════════════════════════════════════════════════
    // EVENT FETCHING
    // ═══════════════════════════════════════════════════════════════════

    async function fetchEvent(subdomain, eventId) {
        const cacheKey = `event_${subdomain}_${eventId}`;
        const cached = cacheGet(cacheKey);
        if (cached) return cached;

        const url = `${API_BASE}/clubs/${subdomain}/events/${eventId}`;
        const data = await apiFetch(url);
        cacheSet(cacheKey, data);
        return data;
    }

    /** Extract completed games with full data from an event payload. */
    function extractGames(event) {
        const games = [];
        const teamMap = new Map();
        for (const t of (event.teams || [])) teamMap.set(t.id, t);

        for (const stage of (event.stages || [])) {
            for (const game of (stage.games || [])) {
                if (game.state !== 'complete') continue;
                // API uses "sides" for the two team positions in a game
                const sides = game.sides || game.game_positions || [];
                if (sides.length !== 2) continue;

                const makeTeam = (side) => {
                    const team = teamMap.get(side.team_id);
                    return {
                        id: side.team_id,
                        name: team?.short_name || team?.name || `Team ${side.team_id}`,
                        fullName: team?.name || '',
                        score: side.score,
                        endScores: side.end_scores || [],
                        firstHammer: !!side.first_hammer,
                        result: side.result,
                        topRock: !!side.top_rock,
                    };
                };

                games.push({
                    id: game.id,
                    name: game.name || `Game`,
                    stageName: stage.name || '',
                    team1: makeTeam(sides[0]),
                    team2: makeTeam(sides[1]),
                    numberOfEnds: event.number_of_ends || 10,
                    shotByShot: !!(game.sides?.[0]?.shots?.length),
                });
            }
        }
        return games;
    }

    /**
     * Reconstruct end-by-end progression with hammer tracking.
     * Returns array of end states: { end, score1, score2, runningScore1/2, hammerTeam, scoreDiff, endsRemaining }
     */
    function reconstructHammerProgression(game) {
        const ends = [];
        const numEnds = Math.max(game.team1.endScores.length, game.team2.endScores.length);
        let hammerTeam = game.team1.firstHammer ? 1 : 2;
        let run1 = 0, run2 = 0;

        for (let i = 0; i < numEnds; i++) {
            const s1 = game.team1.endScores[i] || 0;
            const s2 = game.team2.endScores[i] || 0;
            run1 += s1;
            run2 += s2;

            ends.push({
                end: i + 1,
                score1: s1,
                score2: s2,
                runningScore1: run1,
                runningScore2: run2,
                hammerTeam,
                scoreDiff: run1 - run2,
                endsRemaining: game.numberOfEnds - (i + 1),
            });

            // Hammer transition: scoring team loses hammer. Blank = no change.
            if (s1 > 0) hammerTeam = 2;
            else if (s2 > 0) hammerTeam = 1;
        }

        return ends;
    }

    // ═══════════════════════════════════════════════════════════════════
    // SCORING MODEL — Fry et al. (2024)
    // Constrained geometric distribution via maximum entropy
    //
    // P(Z = n) = θ^n / Σ(θ^k, k=1..8)  for n = 1, ..., 8
    // E[Z] = Σ(k·θ^k) / Σ(θ^k) = μ
    //
    // Hammer advantage (logistic):
    // p_hammer = e^β · p / (1 - p + e^β · p)
    // ═══════════════════════════════════════════════════════════════════

    const MAX_SCORE_PER_END = 8; // WCF rules: max 8 stones per team

    /**
     * Fit constrained geometric: solve for θ given mean μ.
     * Newton-Raphson on f(θ) = E[Z](θ) - μ = 0.
     */
    function fitConstrainedGeometric(mu) {
        let theta = 0.5;
        const N = MAX_SCORE_PER_END;

        for (let iter = 0; iter < 100; iter++) {
            let S = 0, K = 0, dS = 0, dK = 0;
            for (let k = 1; k <= N; k++) {
                const tk = theta ** k;
                S += tk;
                K += k * tk;
                dS += k * theta ** (k - 1);
                dK += k * k * theta ** (k - 1);
            }
            const f = K / S - mu;
            const df = (dK * S - K * dS) / (S * S);
            if (Math.abs(df) < 1e-15) break;
            theta -= f / df;
            theta = Math.max(0.001, Math.min(0.999, theta));
            if (Math.abs(f) < 1e-12) break;
        }

        let S = 0;
        for (let k = 1; k <= N; k++) S += theta ** k;
        const dist = new Map();
        for (let k = 1; k <= N; k++) dist.set(k, theta ** k / S);

        return { theta, dist };
    }

    /**
     * Build full scoring distributions from game data.
     * Computes P(net_score = k | has_hammer) and P(net_score = k | no_hammer)
     * empirically from end-by-end results.
     */
    function computeDistributionsFromGames(games) {
        const hammerCounts = new Map();
        const noHammerCounts = new Map();
        let hammerTotal = 0, noHammerTotal = 0;

        for (const game of games) {
            const ends = reconstructHammerProgression(game);
            for (const end of ends) {
                const { score1, score2, hammerTeam } = end;
                // Net score from perspective of the team with hammer
                const netForHammer = hammerTeam === 1 ? (score1 - score2) : (score2 - score1);

                hammerCounts.set(netForHammer, (hammerCounts.get(netForHammer) || 0) + 1);
                hammerTotal++;

                // Mirror for non-hammer
                const netForNonHammer = -netForHammer;
                noHammerCounts.set(netForNonHammer, (noHammerCounts.get(netForNonHammer) || 0) + 1);
                noHammerTotal++;
            }
        }

        const toDist = (counts, total) => {
            const dist = new Map();
            for (const [k, c] of counts) dist.set(k, c / total);
            return dist;
        };

        return {
            hammer: toDist(hammerCounts, hammerTotal),
            noHammer: toDist(noHammerCounts, noHammerTotal),
            sampleSize: hammerTotal,
            source: `${games.length} games, ${hammerTotal} ends`,
        };
    }

    /**
     * Generate scoring distributions from the Fry et al. model.
     * Parameters:
     *   pWin:   base probability of winning an end (without hammer)
     *   beta:   hammer advantage (log-odds shift)
     *   mu:     mean score in a scoring end
     */
    function generateModelDistributions(pWin = 0.26, beta = 1.00, mu = 1.85) {
        const { dist: scoringDist } = fitConstrainedGeometric(mu);

        // P(hammer team wins end) via logistic model
        const pHammerWins = (Math.exp(beta) * pWin) / (1 - pWin + Math.exp(beta) * pWin);
        // P(non-hammer team wins end) = base probability (steals)
        const pSteal = pWin;
        // P(blank) = 1 - both
        const pBlank = Math.max(0, 1 - pHammerWins - pSteal);

        // Build P(net_score = k | has_hammer)
        const hammer = new Map();
        hammer.set(0, pBlank);
        for (const [k, p] of scoringDist) {
            hammer.set(k, pHammerWins * p);      // hammer team scores k
            hammer.set(-k, pSteal * p);            // steal of k (rare for large k)
        }

        // Build P(net_score = k | no_hammer) — mirror
        const noHammer = new Map();
        for (const [k, p] of hammer) {
            noHammer.set(-k, p);
        }

        return { hammer, noHammer, source: `Fry et al. model (β=${beta}, θ→μ=${mu}, pWin=${pWin})` };
    }

    // ═══════════════════════════════════════════════════════════════════
    // TOURNAMENT CATALOG — Known Curling IO references
    // These are catalog entries (like API route definitions), not
    // hardcoded data values.
    // ═══════════════════════════════════════════════════════════════════

    const TOURNAMENTS = Object.freeze([
        // 2024 Season
        { subdomain: 'canada', id: 15210, name: '2024 Tim Hortons Brier', type: 'men', country: 'CAN' },
        { subdomain: 'canada', id: 15211, name: '2024 Scotties Tournament of Hearts', type: 'women', country: 'CAN' },
        { subdomain: 'worldcurling', id: 15280, name: '2024 World Men\'s Championship', type: 'men', country: 'INT' },
        { subdomain: 'worldcurling', id: 15281, name: '2024 World Women\'s Championship', type: 'women', country: 'INT' },
        // Grand Slam
        { subdomain: 'gsoc', id: 15150, name: '2024 Players\' Championship', type: 'mixed', country: 'CAN' },
        { subdomain: 'gsoc', id: 15100, name: '2024 Boost National', type: 'mixed', country: 'CAN' },
        { subdomain: 'gsoc', id: 15120, name: '2024 Canadian Open', type: 'mixed', country: 'CAN' },
        { subdomain: 'gsoc', id: 15140, name: '2024 Champions Cup', type: 'mixed', country: 'CAN' },
        // 2023 Season
        { subdomain: 'canada', id: 14890, name: '2023 Tim Hortons Brier', type: 'men', country: 'CAN' },
        { subdomain: 'canada', id: 14891, name: '2023 Scotties Tournament of Hearts', type: 'women', country: 'CAN' },
        { subdomain: 'worldcurling', id: 14950, name: '2023 World Men\'s Championship', type: 'men', country: 'INT' },
        { subdomain: 'worldcurling', id: 14951, name: '2023 World Women\'s Championship', type: 'women', country: 'INT' },
    ]);

    // ═══════════════════════════════════════════════════════════════════
    // WP TABLE BUILDER — From real data
    // ═══════════════════════════════════════════════════════════════════

    /**
     * Build win probability lookup table from scoring distributions.
     * State: (scoreDiff, endsRemaining, hasHammer)
     * scoreDiff ∈ [-maxDiff, +maxDiff], ends ∈ [0, maxEnds], hammer ∈ {0, 1}
     * Returns: { table, maxDiff, maxEnds, source }
     */
    function buildWPTable(distHammer, distNoHammer, maxDiff = 8, maxEnds = 10, extraEndHammerWP = 0.60) {
        // 3D array: wp[diff+maxDiff][ends][hammer]
        const size = maxDiff * 2 + 1;
        const wp = new Array(size);

        for (let d = 0; d < size; d++) {
            wp[d] = new Array(maxEnds + 1);
            for (let e = 0; e <= maxEnds; e++) {
                wp[d][e] = new Float64Array(2);
            }
        }

        // Base case: ends = 0
        for (let d = -maxDiff; d <= maxDiff; d++) {
            const idx = d + maxDiff;
            if (d > 0) {
                wp[idx][0][0] = 1.0;
                wp[idx][0][1] = 1.0;
            } else if (d < 0) {
                wp[idx][0][0] = 0.0;
                wp[idx][0][1] = 0.0;
            } else {
                wp[idx][0][0] = 1 - extraEndHammerWP;
                wp[idx][0][1] = extraEndHammerWP;
            }
        }

        const clamp = (v, lo, hi) => v < lo ? lo : v > hi ? hi : v;

        // Fill: ends 1..maxEnds
        for (let e = 1; e <= maxEnds; e++) {
            for (let d = -maxDiff; d <= maxDiff; d++) {
                const dIdx = d + maxDiff;

                for (let h = 0; h <= 1; h++) {
                    const scoreDist = h === 1 ? distHammer : distNoHammer;
                    let prob = 0;

                    for (const [k, pk] of scoreDist) {
                        const newDiff = clamp(d + k, -maxDiff, maxDiff);
                        const newDIdx = newDiff + maxDiff;

                        // Hammer transition
                        let newH;
                        if (h === 1) {
                            // We have hammer
                            newH = k > 0 ? 0 : 1; // scored → lose hammer; blank/steal → keep
                        } else {
                            // Opponent has hammer
                            newH = k < 0 ? 1 : 0; // opponent scored → we get hammer; blank/steal → opponent keeps
                        }

                        prob += pk * wp[newDIdx][e - 1][newH];
                    }

                    wp[dIdx][e][h] = prob;
                }
            }
        }

        return { table: wp, maxDiff, maxEnds };
    }

    // ═══════════════════════════════════════════════════════════════════
    // LIVE DATA PIPELINE — End-to-end from API to WP table
    // ═══════════════════════════════════════════════════════════════════

    /** Status tracking for UI updates */
    const _status = {
        state: 'idle', // idle | loading | ready | error
        message: '',
        source: '',
        sampleSize: 0,
    };

    /**
     * Load real scoring data and build WP table.
     * Tries multiple tournaments, aggregates all end data.
     * @param {Function} onProgress - callback({ state, message })
     * @returns {{ distHammer, distNoHammer, wpTable, source }}
     */
    async function loadLiveData(onProgress = () => {}) {
        _status.state = 'loading';
        _status.message = 'Fetching tournament data...';
        onProgress({ ..._status });

        const allGames = [];
        const loadedTournaments = [];
        let errors = 0;

        for (let ti = 0; ti < TOURNAMENTS.length; ti++) {
            const tourney = TOURNAMENTS[ti];
            try {
                onProgress({ state: 'loading', message: `Loading ${tourney.name}...` });
                const event = await fetchEvent(tourney.subdomain, tourney.id);
                const games = extractGames(event);
                allGames.push(...games);
                loadedTournaments.push(tourney.name);
                // Rate-limit: 300ms delay between API calls (skip if cached)
                if (ti < TOURNAMENTS.length - 1) {
                    await new Promise(r => setTimeout(r, 300));
                }
            } catch (err) {
                errors++;
                console.warn(`Failed to load ${tourney.name}:`, err.message);
            }
        }

        if (allGames.length === 0) {
            // Use Fry et al. model as the theoretical baseline
            onProgress({ state: 'loading', message: 'Using Fry et al. (2024) theoretical model...' });
            const model = generateModelDistributions();
            const wpResult = buildWPTable(model.hammer, model.noHammer);

            _status.state = 'ready';
            _status.message = 'Fry et al. (2024) model active';
            _status.source = model.source;
            _status.sampleSize = 0;
            onProgress({ ..._status });

            return {
                distHammer: model.hammer,
                distNoHammer: model.noHammer,
                wpTable: wpResult.table,
                maxDiff: wpResult.maxDiff,
                maxEnds: wpResult.maxEnds,
                source: model.source,
                sampleSize: 0,
                tournaments: [],
            };
        }

        // Compute distributions from real data
        onProgress({ state: 'loading', message: `Computing from ${allGames.length} games...` });
        const dists = computeDistributionsFromGames(allGames);
        const wpResult = buildWPTable(dists.hammer, dists.noHammer);

        _status.state = 'ready';
        _status.source = dists.source;
        _status.sampleSize = dists.sampleSize;
        _status.message = `Live data: ${dists.source}`;
        onProgress({ ..._status });

        return {
            distHammer: dists.hammer,
            distNoHammer: dists.noHammer,
            wpTable: wpResult.table,
            maxDiff: wpResult.maxDiff,
            maxEnds: wpResult.maxEnds,
            source: dists.source,
            sampleSize: dists.sampleSize,
            tournaments: loadedTournaments,
        };
    }

    // ═══════════════════════════════════════════════════════════════════
    // GAME BROWSER — Browse & load real games
    // ═══════════════════════════════════════════════════════════════════

    /** Load a specific tournament and return its games. */
    async function browseTournament(subdomain, eventId) {
        const event = await fetchEvent(subdomain, eventId);
        return {
            event: {
                id: event.id,
                name: event.name,
                location: event.location,
                startsOn: event.starts_on,
                endsOn: event.ends_on,
                numberOfEnds: event.number_of_ends || 10,
            },
            games: extractGames(event),
        };
    }

    // ═══════════════════════════════════════════════════════════════════
    // URL HASH — Encode/decode position state in URL
    // ═══════════════════════════════════════════════════════════════════

    /**
     * Encode game state to URL hash.
     * Format: #s=<scoreR>-<scoreY>&e=<end>&h=<hammer>&stones=<encoded>
     */
    function encodeStateToHash(state) {
        const parts = [];
        parts.push(`s=${state.scoreRed}-${state.scoreYellow}`);
        parts.push(`e=${state.currentEnd}`);
        parts.push(`h=${state.hammerTeam === 'red' ? 'r' : 'y'}`);

        if (state.stones.length > 0) {
            // Encode stones: team,x,y;team,x,y;...
            const stoneStr = state.stones
                .filter(s => s.active)
                .map(s => `${s.team === 'red' ? 'r' : 'y'},${s.x.toFixed(3)},${s.y.toFixed(3)}`)
                .join(';');
            parts.push(`stones=${encodeURIComponent(stoneStr)}`);
        }

        return '#' + parts.join('&');
    }

    /** Decode URL hash back to state object. */
    function decodeHashToState(hash) {
        if (!hash || hash.length < 2) return null;
        const params = new URLSearchParams(hash.slice(1));

        const score = params.get('s');
        const end = params.get('e');
        const hammer = params.get('h');
        const stonesStr = params.get('stones');

        if (!score || !end || !hammer) return null;

        const [scoreRed, scoreYellow] = score.split('-').map(Number);
        const currentEnd = parseInt(end);
        const hammerTeam = hammer === 'r' ? 'red' : 'yellow';

        const stones = [];
        if (stonesStr) {
            const decoded = decodeURIComponent(stonesStr);
            for (const part of decoded.split(';')) {
                const [team, x, y] = part.split(',');
                stones.push({
                    team: team === 'r' ? 'red' : 'yellow',
                    x: parseFloat(x),
                    y: parseFloat(y),
                });
            }
        }

        return { scoreRed, scoreYellow, currentEnd, hammerTeam, stones };
    }

    // ═══════════════════════════════════════════════════════════════════
    // DATA PROVENANCE DISPLAY
    // ═══════════════════════════════════════════════════════════════════

    function getStatus() {
        return { ..._status };
    }

    // ═══════════════════════════════════════════════════════════════════
    // PUBLIC API
    // ═══════════════════════════════════════════════════════════════════

    return Object.freeze({
        // API
        fetchEvent,
        extractGames,
        reconstructHammerProgression,

        // Scoring model
        fitConstrainedGeometric,
        computeDistributionsFromGames,
        generateModelDistributions,

        // WP
        buildWPTable,

        // Pipeline
        loadLiveData,
        getStatus,

        // Browser
        browseTournament,
        TOURNAMENTS,

        // URL
        encodeStateToHash,
        decodeHashToState,
    });
})();

window.RoboSkipData = RoboSkipData;
