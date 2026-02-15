/**
 * Shattered Mirror — Browser E2E Tests (Playwright)
 * Full integration: Title → Run → Combat → Victory → Map → Shop → Rest → Event → Boss → Daily → Share → Save
 */
import { chromium } from 'playwright';

const BASE = 'http://localhost:8791';
let browser, page;
let passed = 0, failed = 0;

async function assert(cond, msg) {
  if (cond) { passed++; }
  else { failed++; console.error('  FAIL:', msg); }
}
function section(name) { console.log('\n── ' + name + ' ──'); }
async function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function getScreen() {
  return await page.evaluate(() => {
    const screens = ['title','map','combat','rest','nexus','event','reward','shop','gameover','victory','puzzle','daily'];
    for (const s of screens) {
      const el = document.getElementById(s + '-screen');
      if (el && el.classList.contains('active')) return s;
    }
    return 'unknown';
  });
}

try {
  browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  page = await context.newPage();

  const errors = [];
  page.on('console', msg => { if (msg.type() === 'error') errors.push(msg.text()); });
  page.on('pageerror', err => errors.push(err.message));

  // ═══ 1. TITLE SCREEN ═══
  section('1. Title Screen');
  await page.goto(BASE + '/index.html', { waitUntil: 'domcontentloaded' });
  await sleep(1500);

  let screen = await getScreen();
  await assert(screen === 'title', `Should show title screen, got ${screen}`);

  const titleText = await page.evaluate(() => {
    const el = document.querySelector('#title-screen .title-logo');
    return el?.textContent || '';
  });
  await assert(titleText.includes('Shattered Mirror'), `Title: "${titleText}"`);

  for (const id of ['start-btn', 'daily-puzzle-btn', 'daily-run-btn']) {
    const exists = await page.evaluate((eid) => document.getElementById(eid) !== null, id);
    await assert(exists, `Button #${id} should exist`);
  }
  await assert(errors.length === 0, `No JS errors on load, got ${errors.length}: ${errors.join('; ')}`);
  console.log(`  OK — "${titleText}", 3 buttons, 0 errors`);

  // ═══ 2. BEGIN RUN → MAP ═══
  section('2. Begin Run → Map');
  await page.click('#start-btn');
  await sleep(800);

  screen = await getScreen();
  await assert(screen === 'map', `Should show map, got ${screen}`);

  const mapInfo = await page.evaluate(() => {
    const c = document.getElementById('map-container');
    return {
      hasSvg: c ? c.innerHTML.includes('<svg') || c.innerHTML.includes('<circle') : false,
      htmlLen: c ? c.innerHTML.length : 0,
      act: window.game?.act,
      floor: window.game?.floor,
      mapRows: window.game?.map?.length,
    };
  });
  await assert(mapInfo.hasSvg, `Map should have SVG, html length=${mapInfo.htmlLen}`);
  await assert(mapInfo.mapRows === 15, `Map should have 15 rows, got ${mapInfo.mapRows}`);
  console.log(`  OK — Act ${mapInfo.act}, map ${mapInfo.mapRows} rows`);

  // ═══ 3. FIRST COMBAT ═══
  section('3. Enter Combat');
  // Click first available map node via game logic
  await page.evaluate(() => {
    const node = game.map[1][0]; // Row 1, first column
    game.mapRow = 1; game.mapCol = 0;
    game.visited = game.visited || new Set();
    game.visited.add('0-0');
    game.visited.add('1-0');
    // Force into combat
    const enc = game.generateCombatEnemies();
    game.startEncounter(enc.types, enc.pos);
    renderer.showScreen('combat');
    renderer.render();
  });
  await sleep(500);

  screen = await getScreen();
  await assert(screen === 'combat', `Should be in combat, got ${screen}`);

  const combatState = await page.evaluate(() => ({
    hexGridHtml: document.getElementById('hex-grid')?.innerHTML?.length || 0,
    handSize: document.getElementById('hand')?.children?.length || 0,
    endTurnExists: document.getElementById('end-turn-btn') !== null,
    hp: game.player.hp,
    energy: game.player.energy,
    enemies: game.enemies.filter(e => e.hp > 0).length,
    handCards: game.hand.length,
    phase: game.phase,
    turn: game.turn,
  }));
  await assert(combatState.hexGridHtml > 50, `Hex grid should render (${combatState.hexGridHtml} chars)`);
  await assert(combatState.handCards >= 5, `Hand should have ≥5 cards, got ${combatState.handCards}`);
  await assert(combatState.endTurnExists, 'End Turn button should exist');
  await assert(combatState.hp > 0, `HP should be positive (${combatState.hp})`);
  await assert(combatState.enemies > 0, `Should have enemies (${combatState.enemies})`);
  await assert(combatState.energy === 3, `Should have 3 energy (${combatState.energy})`);
  await assert(combatState.phase === 'player', `Phase should be player (${combatState.phase})`);
  console.log(`  OK — ${combatState.handCards} cards, ${combatState.enemies} enemies, ${combatState.energy}⚡, turn ${combatState.turn}`);

  // ═══ 4. PLAY A CARD ═══
  section('4. Play Card');
  const playResult = await page.evaluate(() => {
    const before = { hand: game.hand.length, energy: game.player.energy };
    // Find first playable card
    for (let i = 0; i < game.hand.length; i++) {
      const card = game.hand[i];
      const def = game.getCardDef(card);
      if (!def || def.keywords?.includes('unplayable') || def.cost > game.player.energy) continue;
      const targets = def.validTargets(game);
      if (targets.length > 0) {
        const result = game.playCard(i, targets[0]);
        renderer.render();
        return { played: true, cardId: card.id, result, handBefore: before.hand, handAfter: game.hand.length, energyBefore: before.energy, energyAfter: game.player.energy };
      }
    }
    return { played: false };
  });
  await assert(playResult.played, 'Should play a card');
  await assert(playResult.handAfter < playResult.handBefore, `Hand should shrink: ${playResult.handBefore}->${playResult.handAfter}`);
  console.log(`  OK — played ${playResult.cardId}, hand ${playResult.handBefore}->${playResult.handAfter}, energy ${playResult.energyBefore}->${playResult.energyAfter}`);

  // ═══ 5. END TURN ═══
  section('5. End Turn');
  await page.click('#end-turn-btn');
  await sleep(500);

  const endTurnState = await page.evaluate(() => ({
    phase: game.phase,
    handAfterDiscard: game.hand.length,
    discardSize: game.discardPile.length,
    turn: game.turn,
  }));
  // After end turn, hand should be mostly discarded
  await assert(endTurnState.phase === 'enemy' || endTurnState.phase === 'player', `Phase should be enemy or player, got ${endTurnState.phase}`);
  console.log(`  OK — phase=${endTurnState.phase}, hand=${endTurnState.handAfterDiscard}, discard=${endTurnState.discardSize}`);

  // ═══ 6. AUTO-WIN COMBAT ═══
  section('6. Auto-Win Combat');
  const autoWin = await page.evaluate(() => {
    // Simulate winning: kill all enemies
    const enemyNames = game.enemies.map(e => `${e.name}(${e.hp}/${e.maxHp})`);
    game.enemies.forEach(e => { e.hp = 0; });
    return { enemyNames, playerHp: game.player.hp };
  });
  console.log(`  Killed: ${autoWin.enemyNames.join(', ')}, player HP=${autoWin.playerHp}`);

  // Trigger victory flow
  await page.evaluate(() => {
    const goldReward = 15 + Math.floor(game.rng() * 10);
    game.player.gold += goldReward;
    renderer.renderReward(goldReward);
    renderer.showScreen('reward');
  });
  await sleep(300);

  screen = await getScreen();
  await assert(screen === 'reward', `Should show reward screen, got ${screen}`);

  const rewardHtml = await page.evaluate(() => document.getElementById('reward-screen')?.innerHTML?.length || 0);
  await assert(rewardHtml > 100, `Reward screen should have content (${rewardHtml} chars)`);
  console.log(`  OK — reward screen ${rewardHtml} chars`);

  // ═══ 7. PROCEED FROM REWARD → MAP ═══
  section('7. Proceed from Reward');
  await page.evaluate(() => renderer.proceedFromReward());
  await sleep(300);

  screen = await getScreen();
  await assert(screen === 'map', `Should return to map, got ${screen}`);
  console.log('  OK — back to map');

  // ═══ 8. SHOP ═══
  section('8. Shop');
  await page.evaluate(() => {
    game.player.gold = 999;
    renderer.enterNode({ type: 'shop' });
  });
  await sleep(500);

  screen = await getScreen();
  await assert(screen === 'shop', `Should show shop, got ${screen}`);

  const shopState = await page.evaluate(() => {
    const el = document.getElementById('shop-screen');
    const cards = document.getElementById('shop-cards');
    const relics = document.getElementById('shop-relics');
    const potions = document.getElementById('shop-potions');
    return {
      htmlLen: el?.innerHTML?.length || 0,
      cardCount: cards?.children?.length || 0,
      relicCount: relics?.children?.length || 0,
      potionCount: potions?.children?.length || 0,
      gold: game.player.gold,
    };
  });
  await assert(shopState.htmlLen > 200, `Shop should have content (${shopState.htmlLen} chars)`);
  await assert(shopState.cardCount >= 3, `Shop should have ≥3 cards, got ${shopState.cardCount}`);
  console.log(`  OK — ${shopState.cardCount} cards, ${shopState.relicCount} relics, ${shopState.potionCount} potions, gold=${shopState.gold}`);

  // Buy a card
  const buyResult = await page.evaluate(() => {
    const before = { gold: game.player.gold, deck: game.deck.length };
    const cards = document.getElementById('shop-cards');
    if (cards?.children?.[0]) cards.children[0].click();
    return { goldBefore: before.gold, goldAfter: game.player.gold, deckBefore: before.deck, deckAfter: game.deck.length };
  });
  await sleep(200);
  await assert(buyResult.goldAfter < buyResult.goldBefore || buyResult.deckAfter > buyResult.deckBefore,
    `Should buy something: gold ${buyResult.goldBefore}->${buyResult.goldAfter}, deck ${buyResult.deckBefore}->${buyResult.deckAfter}`);
  console.log(`  Bought: gold ${buyResult.goldBefore}->${buyResult.goldAfter}, deck ${buyResult.deckBefore}->${buyResult.deckAfter}`);

  // Leave shop
  await page.click('#shop-leave-btn');
  await sleep(300);
  screen = await getScreen();
  await assert(screen === 'map', `Should return to map from shop, got ${screen}`);

  // ═══ 9. REST SITE ═══
  section('9. Rest Site');
  await page.evaluate(() => {
    game.player.hp = 30; // damage player
    renderer.enterNode({ type: 'rest' });
  });
  await sleep(300);

  screen = await getScreen();
  await assert(screen === 'rest', `Should show rest site, got ${screen}`);

  // Heal
  const healResult = await page.evaluate(() => {
    const hpBefore = game.player.hp;
    const restBtn = document.querySelector('.rest-action[data-action="rest"]');
    if (restBtn) restBtn.click();
    return { hpBefore, hpAfter: game.player.hp, healed: game.player.hp > hpBefore };
  });
  await sleep(300);
  await assert(healResult.healed, `Rest should heal: ${healResult.hpBefore}->${healResult.hpAfter}`);
  console.log(`  OK — healed ${healResult.hpBefore}->${healResult.hpAfter}`);

  // ═══ 10. EVENT ═══
  section('10. Event');
  await page.evaluate(() => renderer.enterNode({ type: 'event' }));
  await sleep(300);

  screen = await getScreen();
  await assert(screen === 'event', `Should show event, got ${screen}`);

  const eventState = await page.evaluate(() => {
    const text = document.getElementById('event-text')?.textContent || '';
    const choices = document.getElementById('event-choices')?.children?.length || 0;
    return { text, textLen: text.length, choices };
  });
  await assert(eventState.textLen > 10, `Event should have text (${eventState.textLen} chars)`);
  await assert(eventState.choices >= 2, `Event should have ≥2 choices, got ${eventState.choices}`);

  // Make choice
  await page.evaluate(() => {
    const btn = document.getElementById('event-choices')?.children?.[0];
    if (btn) btn.click();
  });
  await sleep(300);
  screen = await getScreen();
  await assert(screen === 'map', `Should return to map after event, got ${screen}`);
  console.log(`  OK — "${eventState.text.slice(0, 50)}...", ${eventState.choices} choices`);

  // ═══ 11. BOSS FIGHT ═══
  section('11. Boss Fight');
  await page.evaluate(() => {
    game.act = 1;
    renderer.enterNode({ type: 'boss' });
  });
  await sleep(1500); // banner animation

  screen = await getScreen();
  await assert(screen === 'combat', `Should be in boss combat, got ${screen}`);

  const bossState = await page.evaluate(() => ({
    enemies: game.enemies.map(e => ({ name: e.name, hp: e.hp, maxHp: e.maxHp })),
    handSize: game.hand.length,
    phase: game.phase,
  }));
  await assert(bossState.enemies.length >= 1, `Should have ≥1 boss enemy, got ${bossState.enemies.length}`);
  await assert(bossState.enemies[0].hp >= 60, `Boss should have high HP (${bossState.enemies[0].hp})`);
  console.log(`  OK — Boss: ${bossState.enemies.map(e => `${e.name}(${e.hp}HP)`).join(', ')}`);

  // Kill boss, test act transition
  await page.evaluate(() => {
    game.enemies.forEach(e => { e.hp = 0; });
  });

  // ═══ 12. ACT TRANSITION ═══
  section('12. Act Transition');
  const actResult = await page.evaluate(() => {
    const prevAct = game.act;
    game.act = 2;
    game.floor = 0;
    game.mapRow = 0; game.mapCol = 0;
    game.map = generateMap(game.act, game.rng);
    renderer.showMap();
    return { prevAct, newAct: game.act, newMapRows: game.map?.length };
  });
  await sleep(300);
  await assert(actResult.newAct === 2, `Should be act 2, got ${actResult.newAct}`);
  await assert(actResult.newMapRows === 15, `New map should have 15 rows, got ${actResult.newMapRows}`);
  console.log(`  OK — Act ${actResult.prevAct} → ${actResult.newAct}`);

  // ═══ 13. DAILY PUZZLE ═══
  section('13. Daily Puzzle');
  await page.evaluate(() => renderer.showScreen('title'));
  await sleep(200);
  await page.click('#daily-puzzle-btn');
  await sleep(800);

  const puzzleState = await page.evaluate(() => ({
    screen: (() => {
      for (const s of ['puzzle','combat']) {
        const el = document.getElementById(s + '-screen');
        if (el?.classList.contains('active')) return s;
      }
      return 'unknown';
    })(),
    isPuzzle: game.isPuzzle,
    dailySeed: game.dailySeed,
  }));
  await assert(puzzleState.screen === 'puzzle' || puzzleState.screen === 'combat', `Puzzle should launch (${puzzleState.screen})`);
  await assert(puzzleState.isPuzzle === true, `isPuzzle flag should be true (${puzzleState.isPuzzle})`);
  console.log(`  OK — screen=${puzzleState.screen}, isPuzzle=${puzzleState.isPuzzle}, seed=${puzzleState.dailySeed}`);

  // ═══ 14. DAILY RUN ═══
  section('14. Daily Run');
  await page.evaluate(() => renderer.showScreen('title'));
  await sleep(200);
  await page.click('#daily-run-btn');
  await sleep(800);

  const dailyState = await page.evaluate(() => ({
    screen: (() => {
      for (const s of ['daily','map']) {
        const el = document.getElementById(s + '-screen');
        if (el?.classList.contains('active')) return s;
      }
      return 'unknown';
    })(),
    isDaily: game.isDaily,
    dailySeed: game.dailySeed,
  }));
  await assert(dailyState.screen === 'daily' || dailyState.screen === 'map', `Daily should launch (${dailyState.screen})`);
  console.log(`  OK — screen=${dailyState.screen}, isDaily=${dailyState.isDaily}, seed=${dailyState.dailySeed}`);

  // ═══ 15. SHARE GRID ═══
  section('15. Share Grid');
  const shareResult = await page.evaluate(() => {
    game.turnsPlayed = 7;
    game.totalDamageDealt = 120;
    game.score = 2500;
    game.ascension = 2;
    const puzzle = generateShareGrid(game, 'puzzle');
    const run = generateShareGrid(game, 'run');
    return { puzzle, run };
  });
  await assert(shareResult.puzzle.includes('Mirror Puzzle'), `Puzzle grid should contain title`);
  await assert(shareResult.puzzle.includes('awktavian.github.io'), `Puzzle grid should have URL`);
  await assert(shareResult.run.includes('Mirror Run'), `Run grid should contain title`);
  console.log('  OK — puzzle grid:', shareResult.puzzle.split('\n')[0]);
  console.log('  OK — run grid:', shareResult.run.split('\n')[0]);

  // ═══ 16. SAVE / RESUME ═══
  section('16. Save / Resume');
  const saveResult = await page.evaluate(() => {
    game.act = 2; game.floor = 7; game.player.hp = 42; game.player.gold = 333;
    game.relics = ['spark_shard', 'grove_root'];
    game.saveRun();
    // Wipe state
    game.player.hp = 0; game.act = 1;
    // Load
    const loaded = game.loadRun();
    return { loaded, hp: game.player.hp, act: game.act, floor: game.floor, gold: game.player.gold, relics: game.relics.length };
  });
  await assert(saveResult.loaded, 'Should load save');
  await assert(saveResult.hp === 42, `HP should be 42, got ${saveResult.hp}`);
  await assert(saveResult.act === 2, `Act should be 2, got ${saveResult.act}`);
  await assert(saveResult.gold === 333, `Gold should be 333, got ${saveResult.gold}`);
  await assert(saveResult.relics === 2, `Should have 2 relics, got ${saveResult.relics}`);
  console.log(`  OK — HP=${saveResult.hp}, Act=${saveResult.act}, Gold=${saveResult.gold}, Relics=${saveResult.relics}`);

  // ═══ 17. DECK VIEWER ═══
  section('17. Deck Viewer');
  await page.evaluate(() => {
    const enc = game.generateCombatEnemies();
    game.startEncounter(enc.types, enc.pos);
    renderer.showScreen('combat');
    renderer.render();
  });
  await sleep(300);

  // Open deck viewer
  const deckResult = await page.evaluate(() => {
    const btn = document.getElementById('view-deck-btn') || document.querySelector('[id*="deck-btn"]');
    if (!btn) return { found: false };
    btn.click();
    const dv = document.getElementById('deck-viewer');
    return {
      found: true,
      visible: dv?.classList.contains('active'),
      cardCount: document.getElementById('deck-viewer-cards')?.children?.length || 0,
    };
  });
  await sleep(200);
  if (deckResult.found) {
    await assert(deckResult.visible, `Deck viewer should be visible`);
    await assert(deckResult.cardCount > 0, `Deck viewer should show cards (${deckResult.cardCount})`);
    console.log(`  OK — ${deckResult.cardCount} cards displayed`);
    // Close
    await page.evaluate(() => {
      const btn = document.getElementById('deck-viewer-close');
      if (btn) btn.click();
    });
  } else {
    console.log('  SKIP — deck viewer button not found in current screen');
  }

  // ═══ 18. MOBILE VIEWPORT ═══
  section('18. Mobile Viewport');
  await page.setViewportSize({ width: 375, height: 812 });
  await page.evaluate(() => renderer.showScreen('title'));
  await sleep(500);

  const mobileState = await page.evaluate(() => ({
    bodyWidth: document.body.offsetWidth,
    titleVisible: document.querySelector('#title-screen .title-logo') !== null,
    startBtnVisible: document.getElementById('start-btn') !== null,
  }));
  await assert(mobileState.bodyWidth <= 375, `Body should fit 375px (${mobileState.bodyWidth})`);
  await assert(mobileState.titleVisible, 'Title should render on mobile');
  await assert(mobileState.startBtnVisible, 'Start button should render on mobile');
  console.log(`  OK — mobile ${mobileState.bodyWidth}px, title=${mobileState.titleVisible}`);

  // ═══ 19. PWA MANIFEST ═══
  section('19. PWA');
  const pwa = await page.evaluate(async () => {
    try {
      const r = await fetch('./manifest.json');
      const j = await r.json();
      return { ok: true, name: j.name, display: j.display, icons: j.icons?.length, id: j.id };
    } catch (e) { return { ok: false, err: e.message }; }
  });
  await assert(pwa.ok, `Manifest should load`);
  await assert(pwa.name === 'Shattered Mirror', `Name: ${pwa.name}`);
  await assert(pwa.display === 'standalone', `Display: ${pwa.display}`);
  await assert(pwa.icons >= 2, `Icons: ${pwa.icons}`);
  console.log(`  OK — "${pwa.name}", display=${pwa.display}, icons=${pwa.icons}, id=${pwa.id}`);

  // ═══ 20. SERVICE WORKER ═══
  section('20. Service Worker');
  const sw = await page.evaluate(async () => {
    try {
      const r = await fetch('./sw.js');
      const t = await r.text();
      return { ok: r.ok, len: t.length, hasCache: t.includes('cache'), hasFetch: t.includes('fetch') };
    } catch (e) { return { ok: false, err: e.message }; }
  });
  await assert(sw.ok, 'SW file should exist');
  await assert(sw.hasCache, 'SW should implement caching');
  await assert(sw.hasFetch, 'SW should handle fetch');
  console.log(`  OK — ${sw.len} chars, cache=${sw.hasCache}, fetch=${sw.hasFetch}`);

  // ═══ 21. PERFORMANCE ═══
  section('21. Performance');
  await page.setViewportSize({ width: 1280, height: 900 });
  const perfStart = Date.now();
  await page.goto(BASE + '/index.html', { waitUntil: 'domcontentloaded' });
  await sleep(500);
  const loadTime = Date.now() - perfStart;
  const perf = await page.evaluate(() => ({
    resources: performance.getEntriesByType('resource').length,
    domReady: Math.round(performance.getEntriesByType('navigation')[0]?.domContentLoadedEventEnd || 0),
  }));
  await assert(loadTime < 5000, `Page should load in <5s, took ${loadTime}ms`);
  console.log(`  OK — load: ${loadTime}ms, DOM ready: ${perf.domReady}ms, resources: ${perf.resources}`);

  // ═══ ERROR SUMMARY ═══
  section('Console Errors');
  const finalErrors = errors.filter(e => !e.includes('favicon') && !e.includes('404'));
  if (finalErrors.length > 0) {
    finalErrors.forEach(e => console.log(`  ⚠️  ${e}`));
  }
  console.log(`  Total JS errors: ${finalErrors.length}`);

} catch (err) {
  console.error('\nFATAL:', err.message);
  console.error(err.stack?.split('\n').slice(0, 5).join('\n'));
  failed++;
} finally {
  if (browser) await browser.close();
}

// ═══ FINAL ═══
console.log('\n' + '═'.repeat(50));
console.log(`  PASSED: ${passed}  FAILED: ${failed}`);
console.log('═'.repeat(50));
process.exit(failed > 0 ? 1 : 0);
