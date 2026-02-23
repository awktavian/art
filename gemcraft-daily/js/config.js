export const GRID_W = 10;
export const GRID_H = 14;
export const TOTAL_WAVES = 10;
export const GEMS_PER_PUZZLE = 4;

export const CELL = { EMPTY: 0, PATH: 1, TOWER: 2, ENTRY: 3, EXIT: 4, BLOCKED: 5 };
export const PHASE = { MENU: 0, SETUP: 1, PLAYING: 2, BETWEEN: 3, VICTORY: 4, DEFEAT: 5, RESULTS: 6 };

export const GEM_TYPES = [
  { id: 0, name: 'Ruby',       color: '#ff3355', rgb: [255,51,85],  glow: 'rgba(255,51,85,',  ability: 'splash',   desc: 'Area damage',  freq: 523 },
  { id: 1, name: 'Topaz',      color: '#ff8833', rgb: [255,136,51], glow: 'rgba(255,136,51,', ability: 'leech',    desc: 'Mana on hit',  freq: 587 },
  { id: 2, name: 'Citrine',    color: '#ffdd33', rgb: [255,221,51], glow: 'rgba(255,221,51,', ability: 'critical', desc: 'Crit chance',  freq: 659 },
  { id: 3, name: 'Peridot',    color: '#88ff33', rgb: [136,255,51], glow: 'rgba(136,255,51,', ability: 'chain',    desc: 'Chain hits',   freq: 698 },
  { id: 4, name: 'Emerald',    color: '#33ff88', rgb: [51,255,136], glow: 'rgba(51,255,136,', ability: 'poison',   desc: 'Damage/tick',  freq: 784 },
  { id: 5, name: 'Aquamarine', color: '#33ddff', rgb: [51,221,255], glow: 'rgba(51,221,255,', ability: 'shock',    desc: 'Stun chance',  freq: 880 },
  { id: 6, name: 'Sapphire',   color: '#3366ff', rgb: [51,102,255], glow: 'rgba(51,102,255,', ability: 'slow',     desc: 'Slow enemies', freq: 988 },
  { id: 7, name: 'Amethyst',   color: '#aa33ff', rgb: [170,51,255], glow: 'rgba(170,51,255,', ability: 'tear',     desc: 'Armor tear',   freq: 1047 },
];

export const GEM_GRADE_SIDES = [3, 4, 5, 6, 7, 8, 10, 12];

export const BASE_DAMAGE = 12;
export const DAMAGE_SCALE = 1.9;
export const BASE_RANGE = 2.2;
export const RANGE_SCALE = 0.15;
export const BASE_FIRE_RATE = 1.0;
export const FIRE_RATE_SCALE = 0.12;

export const SPECIAL = {
  splash:   { base: 0.4,  scale: 0.1,  radius: 1.2, duration: 0,   mult: 0.5 },
  leech:    { base: 5,    scale: 3,    radius: 0,   duration: 0,   mult: 1 },
  critical: { base: 0.15, scale: 0.05, radius: 0,   duration: 0,   mult: 3 },
  chain:    { base: 1,    scale: 0.5,  radius: 0,   duration: 0,   mult: 0.6 },
  poison:   { base: 4,    scale: 2.5,  radius: 0,   duration: 3,   mult: 1 },
  shock:    { base: 0.1,  scale: 0.03, radius: 0,   duration: 0.6, mult: 1 },
  slow:     { base: 0.25, scale: 0.05, radius: 0,   duration: 2,   mult: 1 },
  tear:     { base: 2,    scale: 1.5,  radius: 0,   duration: 0,   mult: 1 },
};

export const PURE_SPECIAL_BONUS = 1.5;
export const DUAL_DAMAGE_BONUS = 1.3;
export const TRIPLE_DAMAGE_BONUS = 1.5;
export const BASE_GEM_COST = 30;
export const GEM_COST_SCALE = 1.8;

export const STARTING_MANA = 200;
export const MANA_PER_KILL_BASE = 8;
export const MANA_LEAK_PENALTY = 20;
export const PROJECTILE_SPEED = 8;

export const WAVE_BASE_HP = 80;
export const WAVE_HP_SCALE = 1.4;
export const WAVE_SPAWN_INTERVAL = 0.7;
export const WAVE_BETWEEN_DELAY = 2.0;

export const ENEMY_TYPES = [
  { key: 'basic',   name: 'Shade',    color: '#887788', hpMul: 1.0, speed: 1.0, armor: 0,  mana: 1.0, radius: 0.30 },
  { key: 'fast',    name: 'Wisp',     color: '#aaddaa', hpMul: 0.6, speed: 1.8, armor: 0,  mana: 0.8, radius: 0.22 },
  { key: 'armored', name: 'Golem',    color: '#8888aa', hpMul: 1.8, speed: 0.6, armor: 5,  mana: 1.5, radius: 0.38 },
  { key: 'swarm',   name: 'Mite',     color: '#cc8866', hpMul: 0.3, speed: 1.3, armor: 0,  mana: 0.4, radius: 0.18 },
  { key: 'boss',    name: 'Revenant', color: '#ff4466', hpMul: 8.0, speed: 0.5, armor: 10, mana: 10,  radius: 0.45 },
];

export const WAVE_TEMPLATES = [
  [{ t: 0, n: 8 }],
  [{ t: 0, n: 10 }],
  [{ t: 0, n: 5 }, { t: 1, n: 4 }],
  [{ t: 0, n: 5 }, { t: 1, n: 3 }, { t: 3, n: 6 }],
  [{ t: 0, n: 4 }, { t: 2, n: 2 }, { t: 1, n: 4 }],
  [{ t: 0, n: 3 }, { t: 2, n: 3 }, { t: 3, n: 10 }],
  [{ t: 0, n: 4 }, { t: 2, n: 4 }, { t: 1, n: 5 }],
  [{ t: 2, n: 3 }, { t: 1, n: 5 }, { t: 3, n: 14 }],
  [{ t: 0, n: 5 }, { t: 2, n: 5 }, { t: 1, n: 6 }, { t: 3, n: 8 }],
  [{ t: 4, n: 1 }, { t: 1, n: 5 }, { t: 0, n: 6 }],
];

export const HAPTIC = { forge: [10, 10, 30], combine: [15, 10, 15, 10, 40], wave: [30, 20, 50], place: [10] };
export const IS_TOUCH = typeof window !== 'undefined' && ('ontouchstart' in window || navigator.maxTouchPoints > 0);
export const SPEED_SETTINGS = [1, 2, 3];
export const POD_VOCAB = 'https://vocab.awkronos.io/agent#';
