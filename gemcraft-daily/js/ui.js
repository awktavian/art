import { PHASE, GEM_TYPES, HAPTIC, IS_TOUCH, TOTAL_WAVES } from './config.js';
import { state, forgeGem, placeTower, assignGemToTower, removeTowerGem, getTowerAtSlot, startWave, getResult } from './engine.js';
import { gemCost, gemDamage, gemRange, gemFireRate, gemSpecial, gemColor, drawGemShape, gemGlowColor } from './gems.js';
import { screenToGrid, findSlotAt } from './render.js';
import * as audio from './audio.js';
import { saveResult, getStreak, getStats, shareText, hasPlayedToday, getTodayResult, syncToPod, getHistory } from './storage.js';
import { puzzleNumber } from './rng.js';

let onStartGame = null, onBackToMenu = null;

export function initUI(callbacks) {
  onStartGame = callbacks.onStartGame;
  onBackToMenu = callbacks.onBackToMenu;

  document.getElementById('btn-play').onclick = () => { haptic(HAPTIC.wave); onStartGame(); };
  document.getElementById('btn-stats').onclick = showStats;
  document.getElementById('btn-howto').onclick = showHowTo;
  document.getElementById('btn-wave').onclick = () => { haptic(HAPTIC.wave); audio.playWaveStart(); startWave(); updateHUD(); };
  document.getElementById('btn-speed').onclick = cycleSpeed;
  document.getElementById('btn-pause').onclick = togglePause;
  document.getElementById('btn-share').onclick = doShare;
  document.getElementById('btn-menu').onclick = () => { haptic(HAPTIC.place); onBackToMenu(); };
  document.getElementById('modal-close').onclick = closeModal;
  document.getElementById('btn-upgrade').onclick = upgradeSelectedTower;
  document.getElementById('btn-remove').onclick = removeSelectedTower;

  const canvas = document.getElementById('game-canvas');
  canvas.addEventListener(IS_TOUCH ? 'touchstart' : 'mousedown', onCanvasTap, { passive: false });

  updateMenuScreen();
}

export function showScreen(id) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  document.getElementById(id).classList.add('active');
}

export function updateMenuScreen() {
  const num = puzzleNumber();
  const streak = getStreak();
  document.getElementById('menu-puzzle-num').textContent = `Puzzle #${num}`;
  document.getElementById('menu-streak').textContent = streak.current > 0 ? `🔥 ${streak.current} day streak` : '';
  const played = hasPlayedToday();
  const btn = document.getElementById('btn-play');
  if (played) {
    btn.textContent = 'View Today\'s Result';
    btn.onclick = () => showTodayResult();
  } else {
    btn.textContent = 'Play Today\'s Puzzle';
    btn.onclick = () => { haptic(HAPTIC.wave); onStartGame(); };
  }
  const yesterday = getHistory(1)[0];
  const yd = document.getElementById('menu-yesterday');
  if (yesterday && yesterday.puzzleNum === num - 1) {
    yd.textContent = `Yesterday: ${yesterday.victory ? '⚡' : '💀'} ${yesterday.score} pts`;
  } else { yd.textContent = ''; }
}

export function buildGemTray() {
  const tray = document.getElementById('gem-tray');
  tray.innerHTML = '';
  for (const typeId of state.availableGemTypes) {
    const gem = GEM_TYPES[typeId];
    const slot = document.createElement('div');
    slot.className = 'gem-slot';
    slot.dataset.type = typeId;
    const cvs = document.createElement('canvas');
    cvs.width = 64; cvs.height = 64;
    const c = cvs.getContext('2d');
    const fakeGem = { grade: 1, types: new Map([[typeId, 1.0]]), primaryType: typeId };
    drawGemShape(c, fakeGem, 32, 28, 14);
    slot.appendChild(cvs);
    const cost = document.createElement('span');
    cost.className = 'gem-cost';
    cost.textContent = `⚡${gemCost(1)}`;
    slot.appendChild(cost);
    const name = document.createElement('span');
    name.className = 'gem-name';
    name.textContent = gem.name;
    slot.appendChild(name);
    slot.onclick = () => onGemSlotTap(typeId);
    tray.appendChild(slot);
  }
  // Inventory gems
  updateInventoryDisplay();
}

export function updateInventoryDisplay() {
  const tray = document.getElementById('gem-tray');
  tray.querySelectorAll('.inv-gem').forEach(e => e.remove());
  for (let i = 0; i < state.gemInventory.length; i++) {
    const gem = state.gemInventory[i];
    const slot = document.createElement('div');
    slot.className = 'gem-slot inv-gem';
    if (i === state.selectedGemIdx) slot.classList.add('selected');
    slot.dataset.invIdx = i;
    const cvs = document.createElement('canvas');
    cvs.width = 64; cvs.height = 64;
    drawGemShape(cvs.getContext('2d'), gem, 32, 28, 14);
    slot.appendChild(cvs);
    const label = document.createElement('span');
    label.className = 'gem-cost';
    label.textContent = `G${gem.grade}`;
    label.style.color = gemColor(gem);
    slot.appendChild(label);
    slot.onclick = () => onInventoryTap(i);
    tray.appendChild(slot);
  }
}

function onGemSlotTap(typeId) {
  const cost = gemCost(1);
  if (state.mana < cost) return;
  haptic(HAPTIC.forge);
  audio.playForge(typeId);
  forgeGem(typeId);
  updateInventoryDisplay();
  updateHUD();
}

function onInventoryTap(idx) {
  haptic(HAPTIC.place);
  if (state.selectedGemIdx === idx) { state.selectedGemIdx = -1; }
  else { state.selectedGemIdx = idx; }
  updateInventoryDisplay();

  if (state.selectedGemIdx >= 0 && state.selectedSlot >= 0) {
    tryPlaceOrAssign();
  }
}

function onCanvasTap(e) {
  e.preventDefault();
  const rect = e.target.getBoundingClientRect();
  const cx = (e.touches ? e.touches[0].clientX : e.clientX) - rect.left;
  const cy = (e.touches ? e.touches[0].clientY : e.clientY) - rect.top;
  const { x: gx, y: gy } = screenToGrid(cx, cy);

  const slotIdx = findSlotAt(gx, gy);
  if (slotIdx >= 0) {
    haptic(HAPTIC.place);
    audio.playPlace();
    if (state.selectedSlot === slotIdx) {
      state.selectedSlot = -1;
      hideTowerPanel();
    } else {
      state.selectedSlot = slotIdx;
      showTowerPanel(slotIdx);
    }
    if (state.selectedGemIdx >= 0 && state.selectedSlot >= 0) tryPlaceOrAssign();
    return;
  }
  state.selectedSlot = -1;
  hideTowerPanel();
}

function tryPlaceOrAssign() {
  const slot = state.towerSlots[state.selectedSlot];
  if (!slot) return;
  if (slot.towerId != null) {
    const ok = assignGemToTower(slot.towerId, state.selectedGemIdx);
    if (ok) {
      haptic(HAPTIC.combine);
      audio.playCombine(2);
      state.selectedGemIdx = -1;
      updateInventoryDisplay();
      showTowerPanel(state.selectedSlot);
    }
  } else {
    const ok = placeTower(state.selectedSlot, state.selectedGemIdx);
    if (ok) {
      haptic(HAPTIC.place);
      audio.playPlace();
      state.selectedGemIdx = -1;
      updateInventoryDisplay();
      showTowerPanel(state.selectedSlot);
    }
  }
  updateHUD();
}

function showTowerPanel(slotIdx) {
  const panel = document.getElementById('tower-panel');
  const info = document.getElementById('tower-info');
  const tw = getTowerAtSlot(slotIdx);
  if (!tw || !tw.gem) {
    info.innerHTML = '<span style="color:var(--text-dim)">Empty slot — select a gem below to place</span>';
    document.getElementById('btn-upgrade').style.display = 'none';
    document.getElementById('btn-remove').style.display = 'none';
  } else {
    const sp = gemSpecial(tw.gem);
    const typeName = GEM_TYPES[tw.gem.primaryType].name;
    info.innerHTML = `<b style="color:${gemColor(tw.gem)}">${typeName}</b> Grade ${tw.gem.grade}<br>` +
      `<span class="gem-stat">⚔ ${Math.floor(gemDamage(tw.gem))}</span> dmg · ` +
      `<span class="gem-stat">◎ ${gemRange(tw.gem).toFixed(1)}</span> range · ` +
      `<span class="gem-stat">⚡ ${gemFireRate(tw.gem).toFixed(2)}/s</span><br>` +
      `✦ ${sp.ability} (${sp.power.toFixed(2)})` +
      (tw.gem.types.size === 1 ? ' <span style="color:var(--citrine)">Pure</span>' : ` <span style="color:var(--text-dim)">${tw.gem.types.size}-type</span>`);
    document.getElementById('btn-upgrade').style.display = '';
    document.getElementById('btn-remove').style.display = '';
    document.getElementById('btn-upgrade').disabled = state.gemInventory.length === 0;
  }
  panel.classList.remove('hidden');
}

function hideTowerPanel() { document.getElementById('tower-panel').classList.add('hidden'); }

function upgradeSelectedTower() {
  if (state.selectedSlot < 0 || state.gemInventory.length === 0) return;
  state.selectedGemIdx = 0;
  tryPlaceOrAssign();
}

function removeSelectedTower() {
  if (state.selectedSlot < 0) return;
  const slot = state.towerSlots[state.selectedSlot];
  if (!slot || slot.towerId == null) return;
  haptic(HAPTIC.place);
  removeTowerGem(slot.towerId);
  updateInventoryDisplay();
  hideTowerPanel();
  state.selectedSlot = -1;
}

export function updateHUD() {
  document.querySelector('#hud-wave b').textContent = state.wave;
  const manaEl = document.getElementById('mana-value');
  const newMana = Math.floor(state.mana).toString();
  if (manaEl.textContent !== newMana) {
    manaEl.textContent = newMana;
    manaEl.classList.remove('bump');
    void manaEl.offsetWidth;
    manaEl.classList.add('bump');
  }
  const enemies = state.enemies.filter(e => !e.dead).length;
  document.getElementById('hud-enemies').textContent = enemies > 0 ? `👾 ${enemies}` : '';
  const waveBtn = document.getElementById('btn-wave');
  const isActive = state.waveActive || state.phase === PHASE.PLAYING;
  waveBtn.disabled = isActive;
  if (state.wave >= TOTAL_WAVES && !state.waveActive) {
    waveBtn.style.display = 'none';
  } else if (state.wave === 0) {
    waveBtn.textContent = 'Send Wave 1';
  } else if (!isActive) {
    waveBtn.textContent = `Wave ${state.wave + 1} →`;
  } else {
    waveBtn.textContent = `Wave ${state.wave}...`;
  }
  const forgeInfo = document.getElementById('forge-info');
  forgeInfo.textContent = state.phase === PHASE.SETUP ? 'Forge gems & place on tower slots' :
    state.phase === PHASE.BETWEEN ? '✓ Wave clear — upgrade before next!' :
    state.phase === PHASE.PLAYING ? '' : '';
  document.querySelectorAll('.gem-slot:not(.inv-gem)').forEach(s => {
    const cost = gemCost(1);
    s.classList.toggle('disabled', state.mana < cost);
  });
}

function cycleSpeed() {
  const opts = [1, 2, 3];
  const idx = (opts.indexOf(state.speed) + 1) % opts.length;
  state.speed = opts[idx];
  document.getElementById('btn-speed').textContent = state.speed + 'x';
  haptic(HAPTIC.place);
}

function togglePause() {
  state.paused = !state.paused;
  const btn = document.getElementById('btn-pause');
  btn.textContent = state.paused ? '▶' : '⏸';
  btn.classList.toggle('active', state.paused);
  haptic(HAPTIC.place);
}

export function showResults() {
  const r = getResult();
  const saved = saveResult(r);
  syncToPod(saved);
  showScreen('screen-results');
  document.getElementById('results-title').textContent = r.victory ? '✨ Victory' : '💀 Defeat';
  const scoreGems = r.victory ? Math.min(5, Math.max(1, Math.floor(r.score / 600))) : Math.min(2, Math.floor(r.score / 500));
  let html = `<div class="gem-bar">${Array.from({length:5},(_,i)=>`<div class="gem-pip ${i<scoreGems?'filled':''}" style="animation-delay:${i*89}ms"></div>`).join('')}</div>`;
  html += row('Score', r.score, 'gold');
  html += row('Waves', `${r.wavesCleared}/${r.totalWaves}`);
  html += row('Mana Left', r.manaLeft, 'mana-color');
  html += row('Kills', r.kills);
  html += row('Leaks', r.leaks, r.leaks === 0 ? '' : 'danger');
  html += row('Gems Forged', r.gemsForged);
  html += row('Time', formatTime(r.time));
  document.getElementById('results-body').innerHTML = html;
}

function row(label, value, cls = '') {
  return `<div class="result-row"><span class="result-label">${label}</span><span class="result-value ${cls}">${value}</span></div>`;
}

function formatTime(ms) {
  const s = Math.floor(ms / 1000);
  return `${Math.floor(s/60)}:${String(s%60).padStart(2,'0')}`;
}

async function doShare() {
  const r = getTodayResult() || getResult();
  if (!r) return;
  const text = shareText(r);
  haptic(HAPTIC.combine);
  if (navigator.share) {
    try { await navigator.share({ title: 'Gemcraft Daily', text }); return; } catch {}
  }
  try { await navigator.clipboard.writeText(text); showToast('Copied!'); } catch {}
}

function showTodayResult() {
  const r = getTodayResult();
  if (!r) return;
  Object.assign(state, { phase: PHASE.RESULTS });
  showResults();
  showScreen('screen-results');
}

function showStats() {
  const s = getStats();
  const streak = getStreak();
  let html = `<h2>Stats</h2><div class="stat-grid">`;
  html += statCard(s.played, 'Played');
  html += statCard(s.wins, 'Wins');
  html += statCard(streak.current, 'Streak');
  html += statCard(streak.best, 'Best Streak');
  html += statCard(s.bestScore, 'Best Score');
  html += statCard(s.perfectWins, 'Perfect');
  html += `</div>`;
  if (s.played > 0) {
    html += `<p style="font-size:0.8rem;color:var(--text-dim)">Win rate: ${Math.round(s.wins/s.played*100)}% · Avg score: ${Math.round(s.totalScore/s.played)}</p>`;
  }
  openModal(html);
}

function showHowTo() {
  openModal(`<h2>How to Play</h2>
<ul>
<li>Each day brings a unique puzzle with a map, 4 gem types, and 10 waves of enemies.</li>
<li><b>Forge gems</b> from the tray (costs mana) and place them on tower slots.</li>
<li>Towers with gems auto-fire at enemies walking the path.</li>
<li><b>Combine gems</b> by placing a gem onto an occupied tower — creates a stronger gem!</li>
<li>Pure gems (same type) get <b>+50% special power</b>. Mixed gems get <b>+30% damage</b>.</li>
<li>Enemies that reach the exit drain your mana. Mana = 0 means defeat.</li>
<li>Survive all 10 waves to win. Maximize your score!</li>
</ul>
<h3 style="margin-top:1rem">Gem Abilities</h3>
<ul>
${GEM_TYPES.map(g=>`<li><span class="howto-gem" style="background:${g.color}"></span> <b>${g.name}</b> — ${g.desc}</li>`).join('')}
</ul>`);
}

function statCard(value, label) {
  return `<div class="stat-card"><div class="stat-value">${value}</div><div class="stat-label">${label}</div></div>`;
}

function openModal(html) {
  document.getElementById('modal-content').innerHTML = html;
  document.getElementById('modal-overlay').classList.add('visible');
  document.getElementById('modal-overlay').classList.remove('hidden');
}
function closeModal() {
  document.getElementById('modal-overlay').classList.remove('visible');
  setTimeout(() => document.getElementById('modal-overlay').classList.add('hidden'), 300);
}

function showToast(msg) {
  const el = document.createElement('div');
  el.style.cssText = 'position:fixed;bottom:80px;left:50%;transform:translateX(-50%);background:var(--surface2);color:var(--text-bright);padding:0.5rem 1.2rem;border-radius:2rem;font-size:0.85rem;z-index:200;border:1px solid var(--border);animation:fadeSlideUp 233ms ease;';
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 1500);
}

function haptic(pattern) { try { navigator?.vibrate?.(pattern); } catch {} }
