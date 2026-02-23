export function mulberry32(seed) {
  let s = seed | 0;
  return function() {
    s = (s + 0x6D2B79F5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function dailySeed() {
  const d = new Date();
  const str = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  let h = 0;
  for (let i = 0; i < str.length; i++) {
    h = ((h << 5) - h + str.charCodeAt(i)) | 0;
  }
  return Math.abs(h);
}

export function puzzleNumber() {
  const epoch = new Date(2025, 0, 1);
  const now = new Date();
  now.setHours(0, 0, 0, 0);
  return Math.floor((now - epoch) / 86400000);
}

export function dateString() {
  return new Date().toISOString().slice(0, 10);
}

export class Rng {
  constructor(seed) { this._next = mulberry32(seed); }
  random()          { return this._next(); }
  int(min, max)     { return min + Math.floor(this._next() * (max - min)); }
  float(min, max)   { return min + this._next() * (max - min); }
  chance(p)         { return this._next() < p; }
  pick(arr)         { return arr[Math.floor(this._next() * arr.length)]; }
  shuffle(arr) {
    const a = [...arr];
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(this._next() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  }
  weightedPick(arr, weights) {
    const total = weights.reduce((s, w) => s + w, 0);
    let r = this._next() * total;
    for (let i = 0; i < arr.length; i++) {
      r -= weights[i];
      if (r <= 0) return arr[i];
    }
    return arr[arr.length - 1];
  }
}
