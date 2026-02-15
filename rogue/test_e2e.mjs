/**
 * Shattered Mirror — E2E Integration Test Suite
 * Tests all game systems without a browser DOM
 */
import { readFileSync } from 'fs';

// ── Extract JS from HTML ──
const html = readFileSync('./index.html', 'utf8');
const scriptMatch = html.match(/<script type="module">([\s\S]*?)<\/script>/);
if (!scriptMatch) { console.error('FAIL: No script tag found'); process.exit(1); }

// ── Mock DOM ──
const elements = {};
const classLists = {};
function mockElement(id) {
  if (elements[id]) return elements[id];
  const cl = new Set();
  const el = {
    id, innerHTML: '', textContent: '', style: { cssText: '' },
    className: '', dataset: {},
    classList: { add: (c) => cl.add(c), remove: (c) => cl.delete(c), toggle: (a,b) => b ? cl.add(a) : cl.delete(a), contains: (c) => cl.has(c) },
    querySelectorAll: () => [], querySelector: () => null,
    addEventListener: () => {}, onclick: null,
    appendChild: (c) => c, children: [], cloneNode: () => mockElement('clone_' + id),
    getBoundingClientRect: () => ({ left: 100, top: 100, width: 420, height: 400 }),
    closest: () => null,
    remove: () => {},
  };
  elements[id] = el;
  return el;
}

// Global mocks
globalThis.window = globalThis;
globalThis.document = {
  getElementById: (id) => mockElement(id),
  createElement: (tag) => mockElement('_new_' + tag + '_' + Math.random().toString(36).slice(2,6)),
  querySelectorAll: () => [],
  addEventListener: () => {},
  body: { appendChild: () => {}, classList: { add: () => {}, remove: () => {} } },
};
Object.defineProperty(globalThis, 'navigator', { value: { vibrate: () => true, clipboard: { writeText: async () => {} }, serviceWorker: { register: async () => {} }, share: undefined }, writable: true, configurable: true });
globalThis.localStorage = (() => {
  const store = {};
  return { getItem: (k) => store[k] || null, setItem: (k, v) => store[k] = v, removeItem: (k) => delete store[k] };
})();
globalThis.requestAnimationFrame = (fn) => setTimeout(fn, 0);
globalThis.setTimeout = globalThis.setTimeout;
globalThis.AudioContext = class { constructor() {} };
globalThis.webkitAudioContext = class { constructor() {} };

// ── Evaluate game code ──
// We need to strip the import/export module syntax and top-level await usage
let code = scriptMatch[1];
// Replace window.emitParticles usage in particle IIFE - skip it for tests
code = code.replace(/\(function particles\(\)\{[\s\S]*?\}\)\(\);/, '// particles skipped for test');
// Strip serviceWorker registration
code = code.replace(/if\('serviceWorker'[\s\S]*?\}/, '// sw skipped');

// Wrap in async to handle any top-level logic
const AsyncFunction = Object.getPrototypeOf(async function(){}).constructor;
let gameModule;
try {
  const fn = new AsyncFunction(code + '\nreturn { Game, Renderer, CARDS, ENEMIES, RELICS, POTIONS, EVENTS, CARD_POOLS, STATUS_DEFS, HEX, mulberry32, generateMap, generateShareGrid, FUSION_RECIPES, getFusedCard, deckCard, wallet, ASCENSION_MODS, DAILY_MODS, applyStatus, tickStatuses, game, renderer };');
  gameModule = await fn();
} catch (e) {
  console.error('FAIL: Code evaluation error:', e.message);
  console.error(e.stack?.split('\n').slice(0, 5).join('\n'));
  process.exit(1);
}

const { Game, CARDS, ENEMIES, RELICS, POTIONS, EVENTS, CARD_POOLS, STATUS_DEFS, HEX, mulberry32, generateMap, generateShareGrid, FUSION_RECIPES, getFusedCard, deckCard, applyStatus, tickStatuses, wallet, ASCENSION_MODS, DAILY_MODS } = gameModule;

let passed = 0, failed = 0;
function assert(cond, msg) {
  if (cond) { passed++; }
  else { failed++; console.error('  FAIL:', msg); }
}
function section(name) { console.log('\n── ' + name + ' ──'); }

// ═══ TESTS ═══

section('Card Definitions');
const cardIds = Object.keys(CARDS);
assert(cardIds.length >= 85, `Expected ≥85 cards, got ${cardIds.length}`);
// Check all colonies represented
const colonies = new Set(cardIds.map(id => CARDS[id].colony));
['spark','forge','flow','nexus','beacon','grove','crystal','colorless'].forEach(c => {
  assert(colonies.has(c), `Colony ${c} missing from cards`);
});
// Check starter deck cards exist
['strike','defend','advance'].forEach(id => {
  assert(CARDS[id], `Starter card ${id} not defined`);
});
// Check upgrade variants
let cardsWithUpgrades = 0;
cardIds.forEach(id => { if (CARDS[id].upgraded) cardsWithUpgrades++; });
assert(cardsWithUpgrades >= 60, `Expected ≥60 cards with upgrades, got ${cardsWithUpgrades}`);
// Check card pools
assert(CARD_POOLS.common.length >= 20, `Common pool too small: ${CARD_POOLS.common.length}`);
assert(CARD_POOLS.uncommon.length >= 20, `Uncommon pool too small: ${CARD_POOLS.uncommon.length}`);
assert(CARD_POOLS.rare.length >= 15, `Rare pool too small: ${CARD_POOLS.rare.length}`);
// Verify all pool cards exist
[...CARD_POOLS.common, ...CARD_POOLS.uncommon, ...CARD_POOLS.rare].forEach(id => {
  assert(CARDS[id], `Pool card ${id} not in CARDS`);
});
console.log(`  ${cardIds.length} cards defined, ${cardsWithUpgrades} with upgrades`);

section('Card Effects');
// Test Strike
const testGame = new Game();
testGame.player = { q: 0, r: 0, hp: 60, maxHp: 60, block: 0, energy: 3, maxEnergy: 3, gold: 99, strength: 0, dexterity: 0, thorn: 0, artifact: 0, vulnerable: 0, weak: 0, frail: 0, nextAttackBonus: 0, attacksWithBonus: 0, attackBonus: 0, cardsPlayedThisTurn: 0, hexesMovedThisTurn: 0, nextCardFree: false, nextCardDouble: false, retainAllBlock: false, canopyActive: 0, nextTurnBlock: 0, extraDrawNext: 0 };
testGame.enemies = [{ name: 'Test', type: 'shade', q: 1, r: 0, hp: 20, maxHp: 20, block: 0, vulnerable: 0, weak: 0, strength: 0, artifact: 0, id: 0, _tc: 0, getIntent: () => ({ type: 'attack', value: 5, label: 'Atk 5' }) }];
testGame.powers = [];
testGame.relics = [];
testGame.drawPile = [];
testGame.discardPile = [];
testGame.hand = [];
testGame.exhaustPile = [];
testGame.deck = [];
testGame.rng = Math.random;

// Test Strike damage
const strikeDef = CARDS.strike;
const strikeResult = strikeDef.effect(testGame, { q: 1, r: 0 });
assert(strikeResult === true, 'Strike should return true');
assert(testGame.enemies[0].hp === 14, `Strike should deal 6, enemy HP=${testGame.enemies[0].hp}`);

// Test Defend block
testGame.player.block = 0;
const defendDef = CARDS.defend;
defendDef.effect(testGame);
assert(testGame.player.block >= 5, `Defend should give ≥5 block, got ${testGame.player.block}`);

// Test Foresight draw
testGame.drawPile = [deckCard('strike'), deckCard('defend'), deckCard('advance')];
testGame.hand = [];
CARDS.foresight.effect(testGame);
assert(testGame.hand.length === 2, `Foresight should draw 2, drew ${testGame.hand.length}`);

// Test Eruption range 2
testGame.enemies[0].hp = 20;
testGame.enemies[0].q = 0; testGame.enemies[0].r = -2; // distance 2
const eruptResult = CARDS.eruption.effect(testGame, { q: 0, r: -2 });
assert(eruptResult === true, 'Eruption should hit at range 2');
assert(testGame.enemies[0].hp < 20, `Eruption should deal damage, HP=${testGame.enemies[0].hp}`);

console.log('  Card effects validated');

section('Status Effects');
assert(Object.keys(STATUS_DEFS).length === 12, `Expected 12 status effects, got ${Object.keys(STATUS_DEFS).length}`);
// Test vulnerable
const testEntity = { hp: 20, maxHp: 20, vulnerable: 0, weak: 0, artifact: 0 };
applyStatus(testEntity, 'vulnerable', 2);
assert(testEntity.vulnerable === 2, `Vulnerable should be 2, got ${testEntity.vulnerable}`);
// Test artifact blocks debuffs
testEntity.artifact = 1;
applyStatus(testEntity, 'weak', 1);
assert(testEntity.weak === 0, 'Artifact should block weak');
assert(testEntity.artifact === 0, 'Artifact should decrement');
// Test poison tick
testEntity.poison = 3;
tickStatuses(testEntity, 'turnStart');
assert(testEntity.hp === 17, `Poison should deal 3, HP=${testEntity.hp}`);
assert(testEntity.poison === 2, `Poison should decrement, got ${testEntity.poison}`);
// Test regen tick
testEntity.hp = 15; testEntity.regen = 2;
tickStatuses(testEntity, 'turnEnd');
assert(testEntity.hp === 17, `Regen should heal 2, HP=${testEntity.hp}`);
assert(testEntity.regen === 1, `Regen should decrement, got ${testEntity.regen}`);
console.log('  12 status effects validated');

section('Enemy Definitions');
const enemyIds = Object.keys(ENEMIES);
assert(enemyIds.length >= 30, `Expected ≥30 enemies, got ${enemyIds.length}`);
// Check acts
const act1 = enemyIds.filter(id => ENEMIES[id].act === 1);
const act2 = enemyIds.filter(id => ENEMIES[id].act === 2);
const act3 = enemyIds.filter(id => ENEMIES[id].act === 3);
assert(act1.length >= 8, `Act 1 should have ≥8 enemies, got ${act1.length}`);
assert(act2.length >= 8, `Act 2 should have ≥8 enemies, got ${act2.length}`);
assert(act3.length >= 8, `Act 3 should have ≥8 enemies, got ${act3.length}`);
// Check tiers
const bosses = enemyIds.filter(id => ENEMIES[id].tier === 'boss');
const elites = enemyIds.filter(id => ENEMIES[id].tier === 'elite');
assert(bosses.length >= 6, `Expected ≥6 bosses, got ${bosses.length}`);
assert(elites.length >= 6, `Expected ≥6 elites, got ${elites.length}`);
// Test enemy intents
enemyIds.forEach(id => {
  const e = ENEMIES[id];
  const mockSelf = { ...e, hp: e.maxHp, q: 0, r: -2, _tc: 0, vulnerable: 0, _wasAttacked: false };
  const mockGame = { player: { q: 0, r: 0, block: 5 }, lastPlayedType: 'attack' };
  try {
    const intent = e.getIntent(mockSelf, mockGame);
    assert(intent && intent.type, `Enemy ${id} getIntent should return valid intent`);
  } catch (err) {
    assert(false, `Enemy ${id} getIntent threw: ${err.message}`);
  }
});
console.log(`  ${enemyIds.length} enemies validated with intent generation`);

section('Relics');
const relicIds = Object.keys(RELICS);
assert(relicIds.length >= 32, `Expected ≥32 relics, got ${relicIds.length}`);
const relicRarities = {};
relicIds.forEach(id => { const r = RELICS[id].rarity; relicRarities[r] = (relicRarities[r] || 0) + 1; });
assert(relicRarities.common >= 10, `Expected ≥10 common relics, got ${relicRarities.common}`);
assert(relicRarities.uncommon >= 10, `Expected ≥10 uncommon relics, got ${relicRarities.uncommon}`);
assert(relicRarities.rare >= 6, `Expected ≥6 rare relics, got ${relicRarities.rare}`);
assert(relicRarities.boss >= 6, `Expected ≥6 boss relics, got ${relicRarities.boss}`);
relicIds.forEach(id => {
  assert(RELICS[id].name, `Relic ${id} missing name`);
  assert(RELICS[id].icon, `Relic ${id} missing icon`);
  assert(RELICS[id].desc, `Relic ${id} missing desc`);
});
console.log(`  ${relicIds.length} relics validated`);

section('Potions');
const potionIds = Object.keys(POTIONS);
assert(potionIds.length >= 10, `Expected ≥10 potions, got ${potionIds.length}`);
potionIds.forEach(id => {
  assert(POTIONS[id].name, `Potion ${id} missing name`);
  assert(typeof POTIONS[id].effect === 'function', `Potion ${id} missing effect function`);
});
console.log(`  ${potionIds.length} potions validated`);

section('Events');
assert(EVENTS.length >= 10, `Expected ≥10 events, got ${EVENTS.length}`);
EVENTS.forEach((ev, i) => {
  assert(ev.text, `Event ${i} missing text`);
  assert(ev.choices && ev.choices.length >= 2, `Event ${i} should have ≥2 choices`);
  ev.choices.forEach((ch, j) => {
    assert(ch.text, `Event ${i} choice ${j} missing text`);
    assert(typeof ch.effect === 'function', `Event ${i} choice ${j} missing effect`);
  });
});
console.log(`  ${EVENTS.length} events validated`);

section('HEX Math');
assert(HEX.distance(0, 0, 1, 0) === 1, 'Adjacent hex distance should be 1');
assert(HEX.distance(0, 0, 2, 0) === 2, 'Distance 2 should be 2');
assert(HEX.distance(0, 0, 0, 0) === 0, 'Same hex distance should be 0');
const allHexes = HEX.allHexes(2);
assert(allHexes.length === 19, `Radius 2 grid should have 19 hexes, got ${allHexes.length}`);
const neighbors = HEX.neighbors(0, 0);
assert(neighbors.length === 6, `Should have 6 neighbors, got ${neighbors.length}`);
console.log('  Hex math validated');

section('PRNG');
const rng1 = mulberry32(12345);
const rng2 = mulberry32(12345);
const vals1 = Array.from({ length: 10 }, () => rng1());
const vals2 = Array.from({ length: 10 }, () => rng2());
assert(JSON.stringify(vals1) === JSON.stringify(vals2), 'Same seed should produce same sequence');
const rng3 = mulberry32(99999);
const vals3 = Array.from({ length: 10 }, () => rng3());
assert(JSON.stringify(vals1) !== JSON.stringify(vals3), 'Different seeds should differ');
assert(vals1.every(v => v >= 0 && v < 1), 'Values should be in [0,1)');
console.log('  Seeded PRNG validated');

section('Map Generator');
const rng = mulberry32(42);
const map = generateMap(1, rng);
assert(map.length === 15, `Map should have 15 rows, got ${map.length}`);
assert(map[0].length === 1, 'Row 0 should have 1 node (start)');
assert(map[14].length === 1, 'Row 14 should have 1 node (boss)');
assert(map[14][0].type === 'boss', 'Last row should be boss');
// Check all nodes have edges (except last row)
for (let r = 0; r < 14; r++) {
  map[r].forEach((node, c) => {
    assert(node.edges && node.edges.length > 0, `Node (${r},${c}) should have edges`);
    node.edges.forEach(e => {
      assert(e >= 0 && e < map[r + 1].length, `Edge from (${r},${c}) to col ${e} out of bounds`);
    });
  });
}
// Check node type distribution
const types = {};
map.forEach(row => row.forEach(n => { types[n.type] = (types[n.type] || 0) + 1; }));
assert(types.boss === 1, 'Should have exactly 1 boss');
assert(types.rest >= 1, 'Should have ≥1 rest site');
assert(types.shop >= 1, 'Should have ≥1 shop');
console.log(`  Map validated: ${map.reduce((a, r) => a + r.length, 0)} nodes across 15 rows`);

section('Game State & Full Combat Loop');
const g = new Game();
g.rng = mulberry32(42);
g.player.hp = 60; g.player.maxHp = 60; g.player.energy = 3; g.player.maxEnergy = 3;
g.deck = ['strike','strike','strike','strike','defend','defend','defend','advance','advance','advance'].map(id => deckCard(id));
// Start encounter
g.startEncounter(['shade', 'phantom'], [{ q: 1, r: -1 }, { q: -1, r: 1 }]);
assert(g.enemies.length === 2, `Should have 2 enemies, got ${g.enemies.length}`);
assert(g.enemies[0].hp > 0, 'Enemy should have HP');
assert(g.hand.length >= 5, `Should draw ≥5 cards, drew ${g.hand.length}`);
assert(g.player.energy === 3, `Should have 3 energy, got ${g.player.energy}`);
assert(g.phase === 'player', `Phase should be player, got ${g.phase}`);
assert(g.turn === 1, `Turn should be 1, got ${g.turn}`);

// Play a card
const handBefore = g.hand.length;
const card = g.hand[0];
const def = g.getCardDef(card);
const targets = def.validTargets(g);
if (targets.length) {
  const target = targets[0];
  const result = g.playCard(0, target);
  assert(result === true || result === 'victory', `playCard should succeed, got ${result}`);
  assert(g.hand.length === handBefore - 1, 'Hand should shrink by 1');
  assert(g.player.energy <= 3, 'Energy should be spent');
}

// End turn
g.endPlayerTurn();
assert(g.phase === 'enemy', `Phase should be enemy after end turn, got ${g.phase}`);
assert(g.hand.length <= 1, 'Hand should be mostly discarded (retained cards may remain)');
console.log('  Combat loop validated');

section('Damage Calculation');
const dg = new Game();
dg.rng = Math.random;
dg.player = { q: 0, r: 0, hp: 60, maxHp: 60, block: 0, energy: 3, maxEnergy: 3, gold: 0, strength: 2, dexterity: 0, thorn: 0, artifact: 0, vulnerable: 0, weak: 0, frail: 0, nextAttackBonus: 3, attacksWithBonus: 0, attackBonus: 0, cardsPlayedThisTurn: 0, hexesMovedThisTurn: 0, nextCardFree: false, canopyActive: 0, nextTurnBlock: 0, _penNibCount: 0, _atkCount: 0 };
dg.enemies = [{ name: 'T', type: 'shade', q: 1, r: 0, hp: 100, maxHp: 100, block: 5, vulnerable: 2, weak: 0, strength: 0, intangible: 0, artifact: 0, id: 0 }];
dg.powers = [];
dg.relics = [];
// Base 6 + 3 (nextAttackBonus) + 2 (strength) = 11, x1.5 (vulnerable) = 16, minus 5 block = 11 dmg to HP
dg.dealDamage(dg.enemies[0], 6);
const expectedHp = 100 - Math.max(0, Math.floor((6 + 3 + 2) * 1.5) - 5);
assert(dg.enemies[0].hp === expectedHp, `Damage calc: expected HP=${expectedHp}, got ${dg.enemies[0].hp}`);
assert(dg.enemies[0].block === 0, 'Block should be consumed');
assert(dg.player.nextAttackBonus === 0, 'nextAttackBonus should reset');
console.log(`  Damage calculation validated (6+3str+2bonus=11, x1.5vuln=16, -5blk = 11 to HP)`);

section('Block with Dexterity & Frail');
dg.player.block = 0;
dg.player.dexterity = 3;
dg.player.frail = 0;
dg.gainBlock(5); // 5 + 3 dex = 8
assert(dg.player.block === 8, `Block with dex: expected 8, got ${dg.player.block}`);
dg.player.block = 0;
dg.player.frail = 1;
dg.gainBlock(8); // (8+3) * 0.75 = 8.25 -> 8
const expectedBlk = Math.floor((8 + 3) * 0.75);
assert(dg.player.block === expectedBlk, `Block with frail: expected ${expectedBlk}, got ${dg.player.block}`);
console.log('  Block modifiers validated');

section('Fusion System');
const fusionKeys = Object.keys(FUSION_RECIPES);
assert(fusionKeys.length >= 5, `Expected ≥5 fusion recipes, got ${fusionKeys.length}`);
const fused = getFusedCard('strike', 'advance');
assert(fused, 'strike+advance should produce fusion');
assert(fused.name === 'Lunge', `Fusion name should be Lunge, got ${fused.name}`);
assert(fused.fused === true, 'Fused card should have fused=true');
// Generic fusion fallback
const genericFused = getFusedCard('eruption', 'bulwark');
assert(genericFused, 'Generic fusion should work');
assert(genericFused.fused === true, 'Generic fusion should be fused');
console.log(`  ${fusionKeys.length} fusion recipes + generic fallback validated`);

section('Save/Load');
const sg = new Game();
sg.rng = mulberry32(42);
sg.player.hp = 45; sg.player.gold = 123; sg.act = 2;
sg.relics = ['spark_shard', 'grove_root'];
sg.deck = [deckCard('strike'), deckCard('defend', true)];
sg.saveRun();
const sg2 = new Game();
const loaded = sg2.loadRun();
assert(loaded === true, 'loadRun should return true');
assert(sg2.player.hp === 45, `Loaded HP should be 45, got ${sg2.player.hp}`);
assert(sg2.player.gold === 123, `Loaded gold should be 123, got ${sg2.player.gold}`);
assert(sg2.act === 2, `Loaded act should be 2, got ${sg2.act}`);
assert(sg2.relics.length === 2, `Loaded relics should be 2, got ${sg2.relics.length}`);
assert(sg2.deck.length === 2, `Loaded deck should be 2, got ${sg2.deck.length}`);
assert(sg2.deck[1].upgraded === true, 'Upgraded card should persist');
sg.clearSave();
console.log('  Save/load validated');

section('Meta Progression');
const mg = new Game();
mg.saveMeta({ ascension: 5, bestScore: 1234, wins: 3 });
const meta = mg.loadMeta();
assert(meta.ascension === 5, `Ascension should be 5, got ${meta.ascension}`);
assert(meta.bestScore === 1234, `Best score should be 1234, got ${meta.bestScore}`);
assert(meta.wins === 3, `Wins should be 3, got ${meta.wins}`);
console.log('  Meta progression validated');

section('Ascension Levels');
assert(ASCENSION_MODS.length === 20, `Expected 20 ascension levels, got ${ASCENSION_MODS.length}`);
console.log('  20 ascension levels defined');

section('Daily Modifiers');
assert(DAILY_MODS.length >= 12, `Expected ≥12 daily modifiers, got ${DAILY_MODS.length}`);
DAILY_MODS.forEach((m, i) => {
  assert(m.name, `Modifier ${i} missing name`);
  assert(m.desc, `Modifier ${i} missing desc`);
  assert(typeof m.apply === 'function', `Modifier ${i} missing apply function`);
});
// Test applying a modifier
const modGame = new Game();
modGame.player.hp = 60; modGame.player.maxHp = 60;
const glassCannon = DAILY_MODS.find(m => m.name === 'Glass Cannon');
if (glassCannon) {
  glassCannon.apply(modGame);
  assert(modGame.player.maxHp === 30, `Glass Cannon should halve HP, got ${modGame.player.maxHp}`);
  assert(modGame.player.strength >= 3, `Glass Cannon should give +3 str, got ${modGame.player.strength}`);
}
console.log(`  ${DAILY_MODS.length} daily modifiers validated`);

section('Share Grid Generation');
const shareGame = new Game();
shareGame.turnsPlayed = 3;
shareGame.totalDamageDealt = 42;
shareGame.score = 1500;
shareGame.ascension = 3;
shareGame.dailySeed = 42;
shareGame.rng = mulberry32(42);
const puzzleGrid = generateShareGrid(shareGame, 'puzzle');
assert(puzzleGrid.includes('Mirror Puzzle'), 'Puzzle grid should contain title');
assert(puzzleGrid.includes('awktavian.github.io/art/rogue'), 'Grid should contain GitHub Pages URL');
const runGrid = generateShareGrid(shareGame, 'run');
assert(runGrid.includes('Mirror Run'), 'Run grid should contain title');
assert(runGrid.includes('awktavian.github.io/art/rogue'), 'Run grid should contain URL');
console.log('  Share grids validated with correct URL');

section('Wallet SDK');
assert(wallet, 'Wallet should exist');
await wallet.earnShards(50);
assert(wallet.shards === 50, `Should have 50 shards, got ${wallet.shards}`);
const spent = await wallet.spendShards(30);
assert(spent === true, 'Should succeed spending 30');
assert(wallet.shards === 20, `Should have 20 left, got ${wallet.shards}`);
const failSpend = await wallet.spendShards(100);
assert(failSpend === false, 'Should fail spending more than balance');
await wallet.purchaseCosmetic('card_back_1', 10);
assert(wallet.cosmetics.includes('card_back_1'), 'Should own cosmetic');
console.log('  Wallet SDK validated');

section('Power System');
const pg = new Game();
pg.rng = Math.random;
pg.powers = [];
pg.player = { q: 0, r: 0, hp: 50, maxHp: 60, block: 0, energy: 3, maxEnergy: 3, strength: 0, dexterity: 0, thorn: 0, vulnerable: 0, weak: 0, frail: 0, artifact: 0, nextAttackBonus: 0, attacksWithBonus: 0, attackBonus: 0, cardsPlayedThisTurn: 0, hexesMovedThisTurn: 0, nextCardFree: false, canopyActive: 0, nextTurnBlock: 0, retainAllBlock: false, extraDrawNext: 0, gold: 0, _adaptationLeft: 0 };
pg.enemies = [{ name: 'T', type: 'shade', q: 1, r: 0, hp: 30, maxHp: 30, block: 0, vulnerable: 0, weak: 0, strength: 0, artifact: 0, id: 0, _tc: 0, getIntent: () => ({ type: 'attack', value: 5, label: 'Atk 5' }) }];
pg.relics = [];
pg.deck = [deckCard('strike'), deckCard('strike'), deckCard('strike'), deckCard('strike'), deckCard('strike'), deckCard('defend'), deckCard('defend'), deckCard('defend'), deckCard('advance'), deckCard('advance')];
pg.drawPile = [];
pg.discardPile = [];
pg.hand = [];
pg.exhaustPile = [];

// Test Combustion power
CARDS.combustion.effect(pg);
assert(pg.powers.length === 1, `Should have 1 power, got ${pg.powers.length}`);
assert(pg.powers[0].id === 'combustion', 'Power should be combustion');
assert(pg.powers[0].dmg === 3, 'Combustion should do 3 dmg');

// Test Spring power
CARDS.spring.effect(pg);
assert(pg.powers.length === 2, 'Should have 2 powers');
assert(pg.powers[1].id === 'spring', 'Second power should be spring');
console.log('  Power system validated');

section('Keyword System');
// Exhaust
assert(CARDS.supernova.keywords.includes('exhaust'), 'Supernova should have exhaust');
assert(CARDS.bide.keywords.includes('exhaust'), 'Bide should have exhaust');
// Power
assert(CARDS.combustion.keywords.includes('power'), 'Combustion should have power keyword');
// Unplayable
assert(CARDS.doubt.keywords.includes('unplayable'), 'Doubt should be unplayable');
assert(CARDS.dazed.keywords.includes('unplayable'), 'Dazed should be unplayable');
// Ethereal
assert(CARDS.shame.keywords.includes('ethereal'), 'Shame should be ethereal');
assert(CARDS.dazed.keywords.includes('ethereal'), 'Dazed should be ethereal');
console.log('  Keywords validated');

section('Encounter Generation');
const eg = new Game();
eg.rng = mulberry32(42);
eg.ascension = 0;
eg.act = 1;
const combatEnc = eg.generateCombatEnemies();
assert(combatEnc.types.length >= 1, `Should generate ≥1 enemy, got ${combatEnc.types.length}`);
combatEnc.types.forEach(t => {
  assert(ENEMIES[t], `Generated enemy type ${t} should exist`);
  assert(ENEMIES[t].act === 1, `Act 1 combat should only have act 1 enemies`);
});
eg.act = 2;
const eliteEnc = eg.generateEliteEnemies();
assert(eliteEnc.types.length === 1, 'Elite encounter should have 1 enemy');
assert(ENEMIES[eliteEnc.types[0]].tier === 'elite', 'Should be an elite');
eg.act = 3;
const bossEnc = eg.generateBossEnemies();
assert(bossEnc.types.length === 1, 'Boss encounter should have 1 enemy');
assert(ENEMIES[bossEnc.types[0]].tier === 'boss', 'Should be a boss');
console.log('  Encounter generation validated for all 3 acts');

section('Full Run Simulation');
const sim = new Game();
sim.rng = mulberry32(777);
sim.player.hp = 60; sim.player.maxHp = 60; sim.player.maxEnergy = 3; sim.player.gold = 99;
sim.deck = ['strike','strike','strike','strike','defend','defend','defend','advance','advance','advance'].map(id => deckCard(id));
sim.relics = [];
sim.potions = [null, null];
sim.act = 1;
// Simulate 5 combats
let simFights = 0;
for (let fight = 0; fight < 5 && sim.player.hp > 0; fight++) {
  const enc = sim.generateCombatEnemies();
  sim.startEncounter(enc.types, enc.pos);
  // Simple AI: play first playable card each turn, then end
  for (let turn = 0; turn < 20 && sim.enemies.some(e => e.hp > 0) && sim.player.hp > 0; turn++) {
    // Play cards
    for (let attempt = 0; attempt < 5; attempt++) {
      if (!sim.hand.length || sim.player.energy <= 0) break;
      const h = sim.hand[0];
      const d = sim.getCardDef(h);
      if (!d || d.keywords?.includes('unplayable') || sim.player.energy < d.cost) {
        sim.hand.push(sim.hand.shift()); // rotate
        continue;
      }
      const tgts = d.validTargets(sim);
      if (tgts.length) {
        const result = sim.playCard(0, tgts[0]);
        if (result === 'victory') break;
      } else {
        sim.hand.push(sim.hand.shift());
      }
    }
    if (sim.enemies.every(e => e.hp <= 0)) break;
    // Enemy turn (simplified - just deal damage)
    sim.endPlayerTurn();
    for (const e of sim.enemies) {
      if (e.hp <= 0 || !e.intent) continue;
      if (e.intent.type === 'attack') {
        sim.dealDamageToPlayer(e.intent.value + (e.strength || 0));
      } else if (e.intent.type === 'block') {
        e.block += e.intent.value;
      } else if (e.intent.type === 'move') {
        sim.moveEnemyToward(e);
      }
    }
    if (sim.player.hp <= 0) break;
    sim.startPlayerTurn();
  }
  if (sim.enemies.every(e => e.hp <= 0)) simFights++;
}
assert(simFights >= 1, `Should win at least 1 fight in simulation, won ${simFights}`);
console.log(`  Simulated ${simFights}/5 combat victories, player HP=${sim.player.hp}`);

section('Score Calculation');
sim.calculateScore();
assert(sim.score > 0, `Score should be positive, got ${sim.score}`);
console.log(`  Score: ${sim.score}`);

// ═══ SUMMARY ═══
console.log('\n' + '═'.repeat(50));
console.log(`  PASSED: ${passed}  FAILED: ${failed}`);
console.log('═'.repeat(50));
process.exit(failed > 0 ? 1 : 0);
