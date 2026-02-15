/**
 * Shattered Mirror — Screenshot Filmstrip
 * Captures every game screen at desktop + mobile viewports
 */
import { chromium } from 'playwright';

const BASE = 'http://localhost:8791';
const DIR = './screenshots';

async function run() {
  const browser = await chromium.launch({ headless: true });

  // Desktop screenshots
  const desktop = await browser.newContext({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 2 });
  const dp = await desktop.newPage();
  await dp.goto(BASE + '/index.html', { waitUntil: 'domcontentloaded' });
  await dp.waitForTimeout(1500);

  // 1. Title Screen
  await dp.screenshot({ path: `${DIR}/01_title_desktop.png`, fullPage: false });
  console.log('📸 01 Title (desktop)');

  // 2. Map Screen
  await dp.click('#start-btn');
  await dp.waitForTimeout(800);
  await dp.screenshot({ path: `${DIR}/02_map_desktop.png`, fullPage: false });
  console.log('📸 02 Map (desktop)');

  // 3. Combat Screen
  await dp.evaluate(() => {
    const enc = game.generateCombatEnemies();
    game.startEncounter(enc.types, enc.pos);
    renderer.showScreen('combat');
    renderer.render();
  });
  await dp.waitForTimeout(500);
  await dp.screenshot({ path: `${DIR}/03_combat_desktop.png`, fullPage: false });
  console.log('📸 03 Combat (desktop)');

  // 4. Combat with card selected
  await dp.evaluate(() => {
    for (let i = 0; i < game.hand.length; i++) {
      const c = game.hand[i], d = game.getCardDef(c);
      if (d && !d.keywords?.includes('unplayable') && d.cost <= game.player.energy) {
        renderer.selectedCard = i;
        renderer.render();
        break;
      }
    }
  });
  await dp.waitForTimeout(200);
  await dp.screenshot({ path: `${DIR}/04_combat_card_selected.png`, fullPage: false });
  console.log('📸 04 Combat card selected');

  // 5. Combat after playing cards (mid-combat)
  await dp.evaluate(() => {
    for (let a = 0; a < 3; a++) {
      for (let i = 0; i < game.hand.length; i++) {
        const c = game.hand[i], d = game.getCardDef(c);
        if (d && !d.keywords?.includes('unplayable') && d.cost <= game.player.energy) {
          const t = d.validTargets(game);
          if (t.length) { game.playCard(i, t[0]); break; }
        }
      }
    }
    renderer.selectedCard = null;
    renderer.render();
  });
  await dp.waitForTimeout(300);
  await dp.screenshot({ path: `${DIR}/05_combat_mid.png`, fullPage: false });
  console.log('📸 05 Combat mid-fight');

  // 6. Reward Screen
  await dp.evaluate(() => {
    game.enemies.forEach(e => e.hp = 0);
    game.player.gold += 20;
    renderer.renderReward(20);
    renderer.showScreen('reward');
  });
  await dp.waitForTimeout(300);
  await dp.screenshot({ path: `${DIR}/06_reward_desktop.png`, fullPage: false });
  console.log('📸 06 Reward (desktop)');

  // 7. Shop Screen
  await dp.evaluate(() => {
    game.player.gold = 500;
    renderer.enterNode({ type: 'shop' });
  });
  await dp.waitForTimeout(500);
  await dp.screenshot({ path: `${DIR}/07_shop_desktop.png`, fullPage: false });
  console.log('📸 07 Shop (desktop)');

  // 8. Rest Site
  await dp.evaluate(() => {
    game.player.hp = 35;
    renderer.enterNode({ type: 'rest' });
  });
  await dp.waitForTimeout(300);
  await dp.screenshot({ path: `${DIR}/08_rest_desktop.png`, fullPage: false });
  console.log('📸 08 Rest (desktop)');

  // 9. Event Screen
  await dp.evaluate(() => renderer.enterNode({ type: 'event' }));
  await dp.waitForTimeout(300);
  await dp.screenshot({ path: `${DIR}/09_event_desktop.png`, fullPage: false });
  console.log('📸 09 Event (desktop)');

  // 10. Deck Viewer
  await dp.evaluate(() => {
    const enc = game.generateCombatEnemies();
    game.startEncounter(enc.types, enc.pos);
    renderer.showScreen('combat');
    renderer.render();
    const btn = document.getElementById('view-deck-btn') || document.querySelector('[id*="deck-btn"]');
    if (btn) btn.click();
  });
  await dp.waitForTimeout(300);
  await dp.screenshot({ path: `${DIR}/10_deck_viewer.png`, fullPage: false });
  console.log('📸 10 Deck Viewer');

  // 11. Daily Puzzle intro
  await dp.evaluate(() => {
    const dv = document.getElementById('deck-viewer');
    if (dv) dv.classList.remove('active');
    renderer.showScreen('title');
  });
  await dp.waitForTimeout(200);
  await dp.click('#daily-puzzle-btn');
  await dp.waitForTimeout(800);
  await dp.screenshot({ path: `${DIR}/11_daily_puzzle.png`, fullPage: false });
  console.log('📸 11 Daily Puzzle');

  // 12. Daily Run screen
  await dp.evaluate(() => renderer.showScreen('title'));
  await dp.waitForTimeout(200);
  await dp.click('#daily-run-btn');
  await dp.waitForTimeout(800);
  await dp.screenshot({ path: `${DIR}/12_daily_run.png`, fullPage: false });
  console.log('📸 12 Daily Run');

  // 13. Boss combat
  await dp.evaluate(() => {
    game.act = 1;
    renderer.enterNode({ type: 'boss' });
  });
  await dp.waitForTimeout(1200);
  await dp.screenshot({ path: `${DIR}/13_boss_combat.png`, fullPage: false });
  console.log('📸 13 Boss Combat');

  // 14. Elite combat
  await dp.evaluate(() => {
    game.act = 2;
    renderer.enterNode({ type: 'elite' });
  });
  await dp.waitForTimeout(1000);
  await dp.screenshot({ path: `${DIR}/14_elite_combat.png`, fullPage: false });
  console.log('📸 14 Elite Combat');

  // Close deck viewer if open
  await dp.evaluate(() => {
    const dv = document.getElementById('deck-viewer');
    if (dv) dv.classList.remove('active');
  });

  // === MOBILE SCREENSHOTS ===
  const mobile = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 3 });
  const mp = await mobile.newPage();
  await mp.goto(BASE + '/index.html', { waitUntil: 'domcontentloaded' });
  await mp.waitForTimeout(1500);

  // M1. Title
  await mp.screenshot({ path: `${DIR}/15_title_mobile.png`, fullPage: false });
  console.log('📸 15 Title (mobile)');

  // M2. Map
  await mp.click('#start-btn');
  await mp.waitForTimeout(800);
  await mp.screenshot({ path: `${DIR}/16_map_mobile.png`, fullPage: false });
  console.log('📸 16 Map (mobile)');

  // M3. Combat
  await mp.evaluate(() => {
    const enc = game.generateCombatEnemies();
    game.startEncounter(enc.types, enc.pos);
    renderer.showScreen('combat');
    renderer.render();
  });
  await mp.waitForTimeout(500);
  await mp.screenshot({ path: `${DIR}/17_combat_mobile.png`, fullPage: false });
  console.log('📸 17 Combat (mobile)');

  // M4. Shop
  await mp.evaluate(() => {
    game.player.gold = 500;
    renderer.enterNode({ type: 'shop' });
  });
  await mp.waitForTimeout(500);
  await mp.screenshot({ path: `${DIR}/18_shop_mobile.png`, fullPage: false });
  console.log('📸 18 Shop (mobile)');

  // M5. Event
  await mp.evaluate(() => renderer.enterNode({ type: 'event' }));
  await mp.waitForTimeout(300);
  await mp.screenshot({ path: `${DIR}/19_event_mobile.png`, fullPage: false });
  console.log('📸 19 Event (mobile)');

  // M6. Rest
  await mp.evaluate(() => {
    game.player.hp = 30;
    renderer.enterNode({ type: 'rest' });
  });
  await mp.waitForTimeout(300);
  await mp.screenshot({ path: `${DIR}/20_rest_mobile.png`, fullPage: false });
  console.log('📸 20 Rest (mobile)');

  // Tablet
  const tablet = await browser.newContext({ viewport: { width: 768, height: 1024 }, deviceScaleFactor: 2 });
  const tp = await tablet.newPage();
  await tp.goto(BASE + '/index.html', { waitUntil: 'domcontentloaded' });
  await tp.waitForTimeout(1500);

  await tp.screenshot({ path: `${DIR}/21_title_tablet.png`, fullPage: false });
  console.log('📸 21 Title (tablet)');

  await tp.click('#start-btn');
  await tp.waitForTimeout(800);
  await tp.evaluate(() => {
    const enc = game.generateCombatEnemies();
    game.startEncounter(enc.types, enc.pos);
    renderer.showScreen('combat');
    renderer.render();
  });
  await tp.waitForTimeout(500);
  await tp.screenshot({ path: `${DIR}/22_combat_tablet.png`, fullPage: false });
  console.log('📸 22 Combat (tablet)');

  await browser.close();
  console.log('\n✅ 22 screenshots captured in ./screenshots/');
}

run().catch(e => { console.error('FATAL:', e.message); process.exit(1); });
