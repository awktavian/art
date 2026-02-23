import { GRID_W, GRID_H, CELL, TOTAL_WAVES, GEMS_PER_PUZZLE, GEM_TYPES, ENEMY_TYPES,
  WAVE_TEMPLATES, WAVE_BASE_HP, WAVE_HP_SCALE, STARTING_MANA } from './config.js';
import { Rng, dailySeed, puzzleNumber } from './rng.js';

export function generatePuzzle(overrideSeed) {
  const seed = overrideSeed ?? dailySeed();
  const rng = new Rng(seed);
  const pNum = puzzleNumber();

  const grid = new Uint8Array(GRID_W * GRID_H);
  const path = generatePath(rng, grid);
  const towerSlots = generateTowerSlots(rng, grid, path);
  const gemTypes = pickGemTypes(rng);
  const waves = generateWaves(rng, gemTypes);
  const startingMana = STARTING_MANA + rng.int(-20, 30);

  return { grid, path, towerSlots, gemTypes, waves, startingMana, seed, puzzleNum: pNum };
}

function generatePath(rng, grid) {
  const entryX = rng.int(3, GRID_W - 3);
  const exitX = rng.int(3, GRID_W - 3);
  const waypoints = [];

  waypoints.push({ x: entryX, y: 0 });
  let cx = entryX, cy = 0;

  const segments = rng.int(4, 7);
  for (let s = 0; s < segments; s++) {
    const targetY = Math.min(GRID_H - 2, Math.floor((s + 1) / segments * (GRID_H - 2)) + rng.int(0, 2));
    if (targetY <= cy) continue;
    // Horizontal run
    const tx = s === segments - 1 ? exitX : rng.int(1, GRID_W - 2);
    waypoints.push({ x: tx, y: cy });
    // Vertical run
    waypoints.push({ x: tx, y: targetY });
    cx = tx; cy = targetY;
  }
  waypoints.push({ x: exitX, y: GRID_H - 1 });

  // Expand waypoints to cell path
  const path = [];
  for (let i = 0; i < waypoints.length - 1; i++) {
    const a = waypoints[i], b = waypoints[i + 1];
    const dx = Math.sign(b.x - a.x), dy = Math.sign(b.y - a.y);
    let px = a.x, py = a.y;
    while (px !== b.x || py !== b.y) {
      path.push({ x: px, y: py });
      if (px !== b.x) px += dx;
      else if (py !== b.y) py += dy;
    }
  }
  path.push(waypoints[waypoints.length - 1]);

  // Deduplicate
  const seen = new Set();
  const deduped = [];
  for (const p of path) {
    const k = p.x + ',' + p.y;
    if (!seen.has(k)) { seen.add(k); deduped.push(p); }
  }

  // Mark grid
  for (const p of deduped) {
    if (p.y === 0) grid[p.y * GRID_W + p.x] = CELL.ENTRY;
    else if (p.y === GRID_H - 1) grid[p.y * GRID_W + p.x] = CELL.EXIT;
    else grid[p.y * GRID_W + p.x] = CELL.PATH;
  }

  return deduped;
}

function generateTowerSlots(rng, grid, path) {
  const pathSet = new Set(path.map(p => p.x + ',' + p.y));
  const candidates = [];
  const dirs = [[-1,0],[1,0],[0,-1],[0,1]];

  for (const p of path) {
    for (const [dx, dy] of dirs) {
      const nx = p.x + dx, ny = p.y + dy;
      if (nx < 0 || nx >= GRID_W || ny < 0 || ny >= GRID_H) continue;
      const k = nx + ',' + ny;
      if (pathSet.has(k)) continue;
      if (grid[ny * GRID_W + nx] !== CELL.EMPTY) continue;
      // Score by path adjacency count (prefer bends)
      let adj = 0;
      for (const [dx2, dy2] of dirs) {
        if (pathSet.has((nx+dx2)+','+(ny+dy2))) adj++;
      }
      candidates.push({ x: nx, y: ny, score: adj + rng.random() });
    }
  }

  // Deduplicate and sort
  const seen = new Set();
  const unique = [];
  for (const c of candidates) {
    const k = c.x + ',' + c.y;
    if (!seen.has(k)) { seen.add(k); unique.push(c); }
  }
  unique.sort((a, b) => b.score - a.score);

  const count = Math.min(unique.length, rng.int(8, 13));
  const slots = unique.slice(0, count);

  for (const s of slots) {
    grid[s.y * GRID_W + s.x] = CELL.TOWER;
  }

  return slots.map(s => ({ x: s.x, y: s.y, towerId: null }));
}

function pickGemTypes(rng) {
  const indices = rng.shuffle([0,1,2,3,4,5,6,7]);
  return indices.slice(0, GEMS_PER_PUZZLE).sort((a,b) => a - b);
}

function generateWaves(rng, gemTypes) {
  const hasArmorTear = gemTypes.includes(7);
  const hasSlow = gemTypes.includes(6);

  return WAVE_TEMPLATES.map((template, waveIdx) => {
    const groups = template.map(g => {
      let t = g.t;
      // Reduce armored enemies if no armor tear
      let n = g.n;
      if (t === 2 && !hasArmorTear) n = Math.max(1, Math.ceil(n * 0.6));
      // Add more fast enemies if no slow
      if (t === 1 && !hasSlow) n = Math.ceil(n * 1.3);
      // Daily variation
      n = Math.max(1, n + rng.int(-1, 2));
      return { type: t, count: n };
    });
    return groups;
  });
}
