import { PHASE } from './config.js';
import { state, initState, update } from './engine.js';
import { generatePuzzle } from './puzzle.js';
import { initRenderer, resize, render } from './render.js';
import { initUI, showScreen, buildGemTray, updateHUD, updateMenuScreen, showResults } from './ui.js';
import { registerMCPTools } from './llm.js';
import * as audio from './audio.js';

let lastTime = 0, endHandled = false;

function boot() {
  const canvas = document.getElementById('game-canvas');
  initRenderer(canvas);
  initUI({ onStartGame: startGame, onBackToMenu: backToMenu });
  registerMCPTools();

  window.addEventListener('resize', resize);
  document.addEventListener('touchstart', () => audio.resume(), { once: true });
  document.addEventListener('click', () => audio.resume(), { once: true });

  showScreen('screen-menu');
  requestAnimationFrame(loop);

  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('./sw.js').catch(() => {});
  }
}

function startGame() {
  endHandled = false;
  const puzzle = generatePuzzle();
  initState(puzzle);
  showScreen('screen-game');
  buildGemTray();
  updateHUD();
  resize();
}

function backToMenu() {
  showScreen('screen-menu');
  updateMenuScreen();
}

function loop(time) {
  requestAnimationFrame(loop);
  const dt = Math.min((time - lastTime) / 1000, 0.05);
  lastTime = time;

  const p = state.phase;
  if (p === PHASE.MENU || p === PHASE.RESULTS) return;

  update(dt);
  render(time / 1000);

  if (state.time % 0.15 < dt) updateHUD();

  if (!endHandled && (p === PHASE.VICTORY || p === PHASE.DEFEAT)) {
    endHandled = true;
    const win = p === PHASE.VICTORY;
    if (win) audio.playVictory(); else audio.playDefeat();
    setTimeout(() => {
      showResults();
      showScreen('screen-results');
    }, win ? 1500 : 1000);
  }
}

document.addEventListener('DOMContentLoaded', boot);

window.__GEMCRAFT = {
  state: () => state,
  tools: () => import('./llm.js').then(m => m.MCP_TOOLS),
};
