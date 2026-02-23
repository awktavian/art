import { GRID_W, GRID_H, CELL, PHASE, ENEMY_TYPES, GEM_TYPES } from './config.js';
import { state } from './engine.js';
import { gemColor, gemGlowColor, gemRange, drawGemShape } from './gems.js';

let canvas, ctx, W, H, cz;

export function initRenderer(cvs) {
  canvas = cvs; ctx = cvs.getContext('2d');
  resize();
  return ctx;
}

export function resize() {
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  W = rect.width; H = rect.height;
  canvas.width = W * dpr; canvas.height = H * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  cz = Math.min(W / GRID_W, H / GRID_H);
  state.cellSize = cz;
  state.offsetX = (W - GRID_W * cz) / 2;
  state.offsetY = (H - GRID_H * cz) / 2;
}

function toScreen(gx, gy) { return [state.offsetX + gx * cz, state.offsetY + gy * cz]; }

export function render(time) {
  ctx.clearRect(0, 0, W, H);
  ctx.save();
  ctx.translate(state.shake.x, state.shake.y);

  drawBackground();
  drawPath();
  drawTowerSlots();
  drawTowers();
  drawEnemies();
  drawProjectiles();
  drawParticles();
  drawRipples();
  drawFloats();

  if (state.selectedSlot >= 0) drawRangeRing();

  ctx.restore();
}

function drawBackground() {
  ctx.fillStyle = '#08081a';
  ctx.fillRect(0, 0, W, H);
  // Subtle grid
  ctx.strokeStyle = 'rgba(30,30,60,0.3)';
  ctx.lineWidth = 0.5;
  for (let x = 0; x <= GRID_W; x++) {
    const sx = state.offsetX + x * cz;
    ctx.beginPath(); ctx.moveTo(sx, state.offsetY); ctx.lineTo(sx, state.offsetY + GRID_H * cz); ctx.stroke();
  }
  for (let y = 0; y <= GRID_H; y++) {
    const sy = state.offsetY + y * cz;
    ctx.beginPath(); ctx.moveTo(state.offsetX, sy); ctx.lineTo(state.offsetX + GRID_W * cz, sy); ctx.stroke();
  }
}

function drawPath() {
  if (!state.path.length) return;
  // Path fill
  ctx.fillStyle = 'rgba(25,20,45,0.8)';
  for (const p of state.path) {
    const [sx, sy] = toScreen(p.x, p.y);
    ctx.fillRect(sx + 1, sy + 1, cz - 2, cz - 2);
  }
  // Path line
  ctx.strokeStyle = 'rgba(80,60,120,0.5)';
  ctx.lineWidth = cz * 0.6;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  ctx.beginPath();
  for (let i = 0; i < state.path.length; i++) {
    const [sx, sy] = toScreen(state.path[i].x + 0.5, state.path[i].y + 0.5);
    i === 0 ? ctx.moveTo(sx, sy) : ctx.lineTo(sx, sy);
  }
  ctx.stroke();
  // Entry/exit markers
  const entry = state.path[0], exit = state.path[state.path.length - 1];
  const [ex, ey] = toScreen(entry.x + 0.5, entry.y + 0.5);
  const [xx, xy] = toScreen(exit.x + 0.5, exit.y + 0.5);
  ctx.fillStyle = 'rgba(68,136,255,0.4)';
  ctx.beginPath(); ctx.arc(ex, ey, cz * 0.3, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = 'rgba(255,68,102,0.4)';
  ctx.beginPath(); ctx.arc(xx, xy, cz * 0.3, 0, Math.PI * 2); ctx.fill();
}

function drawTowerSlots() {
  for (let i = 0; i < state.towerSlots.length; i++) {
    const s = state.towerSlots[i];
    if (s.towerId != null) continue;
    const [sx, sy] = toScreen(s.x, s.y);
    ctx.fillStyle = i === state.selectedSlot ? 'rgba(68,136,255,0.2)' : 'rgba(20,20,40,0.5)';
    ctx.strokeStyle = i === state.selectedSlot ? 'rgba(68,136,255,0.6)' : 'rgba(40,40,80,0.4)';
    ctx.lineWidth = 1.5;
    roundRect(sx + 2, sy + 2, cz - 4, cz - 4, 4);
    ctx.fill(); ctx.stroke();
    if (i === state.selectedSlot) {
      ctx.fillStyle = 'rgba(68,136,255,0.15)';
      roundRect(sx + 2, sy + 2, cz - 4, cz - 4, 4);
      ctx.fill();
    }
  }
}

function drawTowers() {
  for (const tw of state.towers) {
    const [sx, sy] = toScreen(tw.x, tw.y);
    // Base
    ctx.fillStyle = 'rgba(30,25,50,0.9)';
    ctx.beginPath(); ctx.arc(sx, sy, cz * 0.38, 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = 'rgba(60,50,100,0.6)';
    ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.arc(sx, sy, cz * 0.38, 0, Math.PI * 2); ctx.stroke();
    // Gem
    if (tw.gem) {
      const glow = gemGlowColor(tw.gem, 0.25);
      ctx.fillStyle = glow;
      ctx.beginPath(); ctx.arc(sx, sy, cz * 0.5, 0, Math.PI * 2); ctx.fill();
      drawGemShape(ctx, tw.gem, sx, sy, cz * 0.22);
      // Direction indicator
      ctx.strokeStyle = gemColor(tw.gem);
      ctx.lineWidth = 1.5;
      ctx.globalAlpha = 0.4;
      ctx.beginPath();
      ctx.moveTo(sx, sy);
      ctx.lineTo(sx + Math.cos(tw.angle) * cz * 0.35, sy + Math.sin(tw.angle) * cz * 0.35);
      ctx.stroke();
      ctx.globalAlpha = 1;
    }
  }
}

function drawEnemies() {
  for (const e of state.enemies) {
    if (e.dead) continue;
    const def = ENEMY_TYPES[e.type];
    const [sx, sy] = toScreen(e.x, e.y);
    const r = def.radius * cz;

    // Shadow
    ctx.fillStyle = 'rgba(0,0,0,0.3)';
    ctx.beginPath(); ctx.ellipse(sx, sy + r * 0.5, r * 0.8, r * 0.3, 0, 0, Math.PI * 2); ctx.fill();

    // Body
    const bodyGrad = ctx.createRadialGradient(sx, sy - r * 0.2, 0, sx, sy, r);
    bodyGrad.addColorStop(0, def.color);
    bodyGrad.addColorStop(1, 'rgba(0,0,0,0.6)');
    ctx.fillStyle = bodyGrad;
    ctx.beginPath(); ctx.arc(sx, sy, r, 0, Math.PI * 2); ctx.fill();

    // Boss glow
    if (e.type === 4) {
      ctx.strokeStyle = 'rgba(255,68,102,0.4)';
      ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(sx, sy, r + 3, 0, Math.PI * 2); ctx.stroke();
    }

    // Effects visual
    for (const ef of e.effects) {
      if (ef.type === 'poison') { ctx.strokeStyle='rgba(51,255,136,0.5)'; ctx.lineWidth=1.5; ctx.beginPath(); ctx.arc(sx,sy,r+2,0,Math.PI*2); ctx.stroke(); }
      if (ef.type === 'slow') { ctx.strokeStyle='rgba(51,102,255,0.5)'; ctx.lineWidth=1.5; ctx.beginPath(); ctx.arc(sx,sy,r+2,0,Math.PI*2); ctx.stroke(); }
      if (ef.type === 'stun') { ctx.fillStyle='rgba(51,221,255,0.3)'; ctx.beginPath(); ctx.arc(sx,sy,r+3,0,Math.PI*2); ctx.fill(); }
    }

    // HP bar
    const hpPct = e.hp / e.maxHp;
    const bw = r * 2.2, bh = 3;
    const bx = sx - bw / 2, by = sy - r - 6;
    ctx.fillStyle = 'rgba(0,0,0,0.5)';
    ctx.fillRect(bx, by, bw, bh);
    ctx.fillStyle = hpPct > 0.5 ? '#44ff88' : hpPct > 0.25 ? '#ffdd33' : '#ff4466';
    ctx.fillRect(bx, by, bw * Math.max(0, hpPct), bh);
  }
}

function drawProjectiles() {
  for (const p of state.projectiles) {
    const [sx, sy] = toScreen(p.x, p.y);
    ctx.fillStyle = p.color;
    ctx.shadowColor = p.color;
    ctx.shadowBlur = 6;
    ctx.beginPath(); ctx.arc(sx, sy, 3, 0, Math.PI * 2); ctx.fill();
    ctx.shadowBlur = 0;
  }
}

function drawParticles() {
  for (const p of state.particles) {
    const [sx, sy] = toScreen(p.x, p.y);
    const alpha = p.life / p.maxLife;
    ctx.globalAlpha = alpha;
    ctx.fillStyle = p.color;
    ctx.beginPath(); ctx.arc(sx, sy, p.size * cz, 0, Math.PI * 2); ctx.fill();
  }
  ctx.globalAlpha = 1;
}

function drawRipples() {
  for (const r of state.ripples) {
    const [sx, sy] = toScreen(r.x, r.y);
    const alpha = r.life / r.maxLife;
    ctx.strokeStyle = r.color;
    ctx.globalAlpha = alpha * 0.5;
    ctx.lineWidth = 2;
    ctx.beginPath(); ctx.arc(sx, sy, r.radius * cz, 0, Math.PI * 2); ctx.stroke();
  }
  ctx.globalAlpha = 1;
}

function drawFloats() {
  for (const f of state.floats) {
    const [sx, sy] = toScreen(f.x, f.y);
    const alpha = f.life / f.maxLife;
    ctx.globalAlpha = alpha;
    ctx.fillStyle = f.color;
    ctx.font = `bold ${Math.round(cz * 0.35)}px system-ui`;
    ctx.textAlign = 'center';
    ctx.fillText(f.text, sx, sy);
  }
  ctx.globalAlpha = 1;
}

function drawRangeRing() {
  const slot = state.towerSlots[state.selectedSlot];
  if (!slot) return;
  const tw = state.towers.find(t => t.id === slot.towerId);
  let range = 2.2;
  if (tw && tw.gem) range = gemRange(tw.gem);
  const [sx, sy] = toScreen(slot.x + 0.5, slot.y + 0.5);
  ctx.strokeStyle = 'rgba(68,136,255,0.3)';
  ctx.lineWidth = 1;
  ctx.setLineDash([4, 4]);
  ctx.beginPath(); ctx.arc(sx, sy, range * cz, 0, Math.PI * 2); ctx.stroke();
  ctx.setLineDash([]);
}

function roundRect(x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y); ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r); ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h); ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r); ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}

export function screenToGrid(sx, sy) {
  const gx = Math.floor((sx - state.offsetX) / cz);
  const gy = Math.floor((sy - state.offsetY) / cz);
  return { x: gx, y: gy };
}

export function findSlotAt(gx, gy) {
  return state.towerSlots.findIndex(s => s.x === gx && s.y === gy);
}
