import { GRID_W, GRID_H, CELL, PHASE, TOTAL_WAVES, ENEMY_TYPES, WAVE_BASE_HP, WAVE_HP_SCALE,
  WAVE_SPAWN_INTERVAL, WAVE_BETWEEN_DELAY, MANA_PER_KILL_BASE, MANA_LEAK_PENALTY,
  PROJECTILE_SPEED, STARTING_MANA, SPECIAL } from './config.js';
import { gemDamage, gemRange, gemFireRate, gemSpecial, gemColor, gemCost, createGem, combineGems, resetGemIds } from './gems.js';

let _eid = 1, _pid = 1, _tid = 1;

export const state = {
  phase: PHASE.MENU, grid: null, path: [], towerSlots: [], towers: [], enemies: [],
  projectiles: [], particles: [], ripples: [], floats: [], mana: 0, score: 0, leaks: 0,
  kills: 0, wave: 0, waveActive: false, spawnQueue: [], spawnTimer: 0, betweenTimer: 0,
  availableGemTypes: [], gemInventory: [], selectedSlot: -1, selectedGemIdx: -1,
  speed: 1, paused: false, time: 0, shake: {x:0,y:0,i:0},
  puzzleNum: 0, seed: 0, waves: [], cellSize: 0, offsetX: 0, offsetY: 0, startTime: 0,
  gemsForged: 0, gemsCombined: 0,
};

export function initState(puzzle) {
  _eid=1; _pid=1; _tid=1; resetGemIds();
  Object.assign(state, {
    phase: PHASE.SETUP, grid: puzzle.grid, path: puzzle.path, towerSlots: puzzle.towerSlots,
    towers: [], enemies: [], projectiles: [], particles: [], ripples: [], floats: [],
    mana: puzzle.startingMana || STARTING_MANA, score: 0, leaks: 0, kills: 0,
    wave: 0, waveActive: false, spawnQueue: [], spawnTimer: 0, betweenTimer: 0,
    availableGemTypes: puzzle.gemTypes, gemInventory: [],
    selectedSlot: -1, selectedGemIdx: -1, speed: 1, paused: false, time: 0,
    shake: {x:0,y:0,i:0}, puzzleNum: puzzle.puzzleNum, seed: puzzle.seed,
    waves: puzzle.waves, startTime: Date.now(), gemsForged: 0, gemsCombined: 0,
  });
}

export function update(dt) {
  if (state.paused || state.phase === PHASE.MENU || state.phase === PHASE.RESULTS) return;
  const sDt = dt * state.speed;
  state.time += sDt;

  if (state.phase === PHASE.PLAYING) {
    updateSpawning(sDt);
    updateEnemies(sDt);
    updateTowers(sDt);
    updateProjectiles(sDt);
    checkWaveComplete();
  } else if (state.phase === PHASE.BETWEEN) {
    state.betweenTimer -= sDt;
    if (state.betweenTimer <= 0) {
      if (state.wave >= TOTAL_WAVES) { state.phase = PHASE.VICTORY; return; }
      state.phase = PHASE.SETUP;
    }
  }
  updateEffects(sDt);
  updateParticles(sDt);
  updateShake(sDt);
}

export function startWave() {
  if (state.wave >= TOTAL_WAVES) return;
  state.wave++;
  const waveDef = state.waves[state.wave - 1];
  if (!waveDef) return;
  state.spawnQueue = [];
  for (const g of waveDef) {
    for (let i = 0; i < g.count; i++) state.spawnQueue.push(g.type);
  }
  state.spawnTimer = 0;
  state.waveActive = true;
  state.phase = PHASE.PLAYING;
}

function updateSpawning(dt) {
  if (state.spawnQueue.length === 0) return;
  state.spawnTimer -= dt;
  if (state.spawnTimer <= 0) {
    const typeIdx = state.spawnQueue.shift();
    spawnEnemy(typeIdx);
    state.spawnTimer = WAVE_SPAWN_INTERVAL;
  }
}

function spawnEnemy(typeIdx) {
  const def = ENEMY_TYPES[typeIdx];
  const hp = Math.floor(WAVE_BASE_HP * def.hpMul * Math.pow(WAVE_HP_SCALE, state.wave - 1));
  const p = state.path[0];
  state.enemies.push({
    id: _eid++, type: typeIdx, pathIdx: 0, pathT: 0,
    x: p.x, y: p.y, hp, maxHp: hp, armor: def.armor, baseSpeed: def.speed,
    speed: def.speed, manaValue: Math.ceil(MANA_PER_KILL_BASE * def.mana),
    effects: [], dead: false,
  });
}

function updateEnemies(dt) {
  for (const e of state.enemies) {
    if (e.dead) continue;
    let spd = e.baseSpeed;
    for (const ef of e.effects) {
      if (ef.type === 'slow') spd *= (1 - ef.power);
      if (ef.type === 'stun') spd = 0;
    }
    e.speed = spd;
    e.pathT += spd * dt;
    while (e.pathT >= 1 && e.pathIdx < state.path.length - 2) { e.pathT -= 1; e.pathIdx++; }
    if (e.pathIdx >= state.path.length - 2 && e.pathT >= 1) { leakEnemy(e); continue; }
    const a = state.path[e.pathIdx], b = state.path[Math.min(e.pathIdx + 1, state.path.length - 1)];
    const t = Math.min(e.pathT, 1);
    e.x = a.x + (b.x - a.x) * t;
    e.y = a.y + (b.y - a.y) * t;
  }
  state.enemies = state.enemies.filter(e => !e.dead);
}

function leakEnemy(e) {
  e.dead = true;
  state.mana -= MANA_LEAK_PENALTY;
  state.leaks++;
  addRipple(e.x, e.y, '#ff4466', 1.5);
  if (state.mana <= 0) { state.mana = 0; state.phase = PHASE.DEFEAT; }
}

function updateTowers(dt) {
  for (const tw of state.towers) {
    if (!tw.gem) continue;
    tw.cooldown -= dt;
    if (tw.cooldown > 0) continue;
    const range = gemRange(tw.gem);
    let best = null, bestProgress = -1;
    for (const e of state.enemies) {
      if (e.dead) continue;
      const dx = e.x - tw.x, dy = e.y - tw.y;
      if (dx*dx + dy*dy > range*range) continue;
      const prog = e.pathIdx + e.pathT;
      if (prog > bestProgress) { bestProgress = prog; best = e; }
    }
    if (best) {
      tw.angle = Math.atan2(best.y - tw.y, best.x - tw.x);
      fireProjectile(tw, best);
      tw.cooldown = 1 / gemFireRate(tw.gem);
    }
  }
}

function fireProjectile(tower, target) {
  const dmg = gemDamage(tower.gem);
  const spec = gemSpecial(tower.gem);
  const color = gemColor(tower.gem);
  state.projectiles.push({
    id: _pid++, x: tower.x, y: tower.y, targetId: target.id,
    damage: dmg, special: spec, color, typeId: tower.gem.primaryType, grade: tower.gem.grade,
  });
}

function updateProjectiles(dt) {
  const spd = PROJECTILE_SPEED * dt;
  for (const p of state.projectiles) {
    const target = state.enemies.find(e => e.id === p.targetId && !e.dead);
    if (!target) { p.dead = true; addBurstParticles(p.x, p.y, p.color, 3); continue; }
    const dx = target.x - p.x, dy = target.y - p.y;
    const dist = Math.sqrt(dx*dx + dy*dy);
    if (dist < 0.3) { hitEnemy(target, p); p.dead = true; continue; }
    p.x += (dx/dist) * spd;
    p.y += (dy/dist) * spd;
    addParticle(p.x, p.y, 0, 0, p.color, 0.15, 0.08);
  }
  state.projectiles = state.projectiles.filter(p => !p.dead);
}

function hitEnemy(enemy, proj) {
  let dmg = proj.damage;
  const sp = proj.special;

  if (sp.ability === 'critical' && Math.random() < sp.power) dmg *= (sp.mult || 3);

  const effectiveArmor = Math.max(0, enemy.armor);
  dmg = Math.max(1, dmg - effectiveArmor);
  enemy.hp -= dmg;

  addFloat(enemy.x, enemy.y - 0.3, Math.floor(dmg).toString(), proj.color);
  addBurstParticles(enemy.x, enemy.y, proj.color, 5);

  if (sp.ability === 'splash') {
    const r = sp.radius || 1.2;
    for (const e of state.enemies) {
      if (e === enemy || e.dead) continue;
      const dx = e.x - enemy.x, dy = e.y - enemy.y;
      if (dx*dx + dy*dy < r*r) {
        const sd = Math.max(1, dmg * sp.power - e.armor);
        e.hp -= sd;
        if (e.hp <= 0 && !e.dead) killEnemy(e, proj.typeId);
      }
    }
  }
  if (sp.ability === 'leech') { state.mana += Math.ceil(sp.power); addFloat(enemy.x, enemy.y - 0.5, '+' + Math.ceil(sp.power), '#4488ff'); }
  if (sp.ability === 'poison') enemy.effects.push({type:'poison', power:sp.power, duration:sp.duration||3, timer:sp.duration||3});
  if (sp.ability === 'shock' && Math.random() < sp.power) enemy.effects.push({type:'stun', power:1, duration:sp.duration||0.6, timer:sp.duration||0.6});
  if (sp.ability === 'slow') enemy.effects.push({type:'slow', power:sp.power, duration:sp.duration||2, timer:sp.duration||2});
  if (sp.ability === 'tear') { enemy.armor = Math.max(0, enemy.armor - sp.power); }
  if (sp.ability === 'chain') {
    let chains = Math.floor(sp.power);
    const hit = new Set([enemy.id]);
    let last = enemy;
    while (chains > 0) {
      let closest = null, cd = 2.5;
      for (const e of state.enemies) {
        if (e.dead || hit.has(e.id)) continue;
        const dx = e.x-last.x, dy = e.y-last.y, d = Math.sqrt(dx*dx+dy*dy);
        if (d < cd) { cd = d; closest = e; }
      }
      if (!closest) break;
      hit.add(closest.id);
      const cd2 = Math.max(1, dmg * 0.6 - closest.armor);
      closest.hp -= cd2;
      addBurstParticles(closest.x, closest.y, proj.color, 3);
      if (closest.hp <= 0 && !closest.dead) killEnemy(closest, proj.typeId);
      last = closest; chains--;
    }
  }

  if (enemy.hp <= 0 && !enemy.dead) killEnemy(enemy, proj.typeId);
  shakeScreen(0.3);
}

function killEnemy(e, typeId) {
  e.dead = true;
  state.kills++;
  state.mana += e.manaValue;
  state.score += e.manaValue * 10;
  addBurstParticles(e.x, e.y, ENEMY_TYPES[e.type].color, 12);
  addRipple(e.x, e.y, ENEMY_TYPES[e.type].color, 1.0);
  addFloat(e.x, e.y - 0.4, '+' + e.manaValue, '#4488ff');
}

function updateEffects(dt) {
  for (const e of state.enemies) {
    if (e.dead) continue;
    for (let i = e.effects.length - 1; i >= 0; i--) {
      const ef = e.effects[i];
      ef.timer -= dt;
      if (ef.type === 'poison') {
        e.hp -= ef.power * dt;
        if (e.hp <= 0 && !e.dead) killEnemy(e, 4);
      }
      if (ef.timer <= 0) e.effects.splice(i, 1);
    }
  }
}

function checkWaveComplete() {
  if (!state.waveActive) return;
  if (state.spawnQueue.length > 0) return;
  if (state.enemies.some(e => !e.dead)) return;
  state.waveActive = false;
  state.score += state.wave * 50;
  if (state.wave >= TOTAL_WAVES) { state.phase = PHASE.VICTORY; return; }
  state.phase = PHASE.BETWEEN;
  state.betweenTimer = WAVE_BETWEEN_DELAY;
}

export function forgeGem(typeId) {
  const cost = gemCost(1);
  if (state.mana < cost) return null;
  state.mana -= cost;
  const gem = createGem(typeId);
  state.gemInventory.push(gem);
  state.gemsForged++;
  return gem;
}

export function placeTower(slotIdx, gemIdx) {
  const slot = state.towerSlots[slotIdx];
  if (!slot || slot.towerId != null) return false;
  if (gemIdx < 0 || gemIdx >= state.gemInventory.length) return false;
  const gem = state.gemInventory.splice(gemIdx, 1)[0];
  const tower = { id: _tid++, x: slot.x + 0.5, y: slot.y + 0.5, gem, cooldown: 0, angle: 0 };
  state.towers.push(tower);
  slot.towerId = tower.id;
  addRipple(tower.x, tower.y, gemColor(gem), 1.2);
  return true;
}

export function assignGemToTower(towerId, gemIdx) {
  const tower = state.towers.find(t => t.id === towerId);
  if (!tower) return false;
  const gem = state.gemInventory[gemIdx];
  if (!gem) return false;
  if (tower.gem) {
    const combined = combineGems(tower.gem, state.gemInventory.splice(gemIdx, 1)[0]);
    tower.gem = combined;
    state.gemsCombined++;
    addBurstParticles(tower.x, tower.y, gemColor(combined), 10);
    addRipple(tower.x, tower.y, gemColor(combined), 1.5);
    return true;
  }
  tower.gem = state.gemInventory.splice(gemIdx, 1)[0];
  return true;
}

export function removeTowerGem(towerId) {
  const tower = state.towers.find(t => t.id === towerId);
  if (!tower || !tower.gem) return null;
  const gem = tower.gem;
  tower.gem = null;
  state.gemInventory.push(gem);
  const slot = state.towerSlots.find(s => s.towerId === towerId);
  if (slot) slot.towerId = null;
  state.towers = state.towers.filter(t => t.id !== towerId);
  return gem;
}

export function getTowerAtSlot(slotIdx) {
  const slot = state.towerSlots[slotIdx];
  if (!slot || slot.towerId == null) return null;
  return state.towers.find(t => t.id === slot.towerId) || null;
}

export function getResult() {
  return {
    victory: state.phase === PHASE.VICTORY,
    score: state.score,
    wavesCleared: state.wave,
    totalWaves: TOTAL_WAVES,
    leaks: state.leaks,
    kills: state.kills,
    manaLeft: state.mana,
    gemsForged: state.gemsForged,
    gemsCombined: state.gemsCombined,
    gemTypes: state.availableGemTypes,
    time: Date.now() - state.startTime,
  };
}

function shakeScreen(intensity) { state.shake.i = Math.max(state.shake.i, intensity); }
function updateShake(dt) {
  if (state.shake.i > 0.01) {
    state.shake.x = (Math.random()-0.5) * state.shake.i * 4;
    state.shake.y = (Math.random()-0.5) * state.shake.i * 4;
    state.shake.i *= 0.85;
  } else { state.shake.x = 0; state.shake.y = 0; state.shake.i = 0; }
}

function addParticle(x,y,vx,vy,color,life,size) {
  state.particles.push({x,y,vx,vy,color,life,maxLife:life,size});
}
function addBurstParticles(x,y,color,count) {
  for (let i=0;i<count;i++){
    const a=Math.random()*Math.PI*2, s=1+Math.random()*3;
    addParticle(x,y,Math.cos(a)*s,Math.sin(a)*s,color,0.3+Math.random()*0.3,0.06+Math.random()*0.04);
  }
}
export function addRipple(x,y,color,maxR) {
  state.ripples.push({x,y,color,radius:0,maxRadius:maxR,life:0.4,maxLife:0.4});
}
function addFloat(x,y,text,color) {
  state.floats.push({x,y,text,color,life:0.8,maxLife:0.8,vy:-1.5});
}
function updateParticles(dt) {
  for (const p of state.particles) { p.x+=p.vx*dt; p.y+=p.vy*dt; p.life-=dt; p.vx*=0.95; p.vy*=0.95; }
  state.particles = state.particles.filter(p=>p.life>0);
  for (const r of state.ripples) { r.radius+=r.maxRadius/r.maxLife*dt; r.life-=dt; }
  state.ripples = state.ripples.filter(r=>r.life>0);
  for (const f of state.floats) { f.y+=f.vy*dt; f.life-=dt; }
  state.floats = state.floats.filter(f=>f.life>0);
}

export function stateForLLM() {
  return {
    phase: Object.keys(PHASE).find(k=>PHASE[k]===state.phase),
    wave: state.wave, mana: state.mana, score: state.score, kills: state.kills, leaks: state.leaks,
    availableGems: state.availableGemTypes.map(i=>({id:i, name:import('./config.js').then?'':'' })),
    towers: state.towers.map(t=>({
      x:t.x, y:t.y, gem: t.gem ? { grade:t.gem.grade, type:t.gem.primaryType, damage:Math.floor(gemDamage(t.gem)),
        range:gemRange(t.gem).toFixed(1), ability:gemSpecial(t.gem).ability } : null
    })),
    enemiesAlive: state.enemies.filter(e=>!e.dead).length,
    inventory: state.gemInventory.length,
  };
}
