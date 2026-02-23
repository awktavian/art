import { GEM_TYPES, GEM_GRADE_SIDES, BASE_DAMAGE, DAMAGE_SCALE, BASE_RANGE, RANGE_SCALE,
  BASE_FIRE_RATE, FIRE_RATE_SCALE, SPECIAL, PURE_SPECIAL_BONUS, DUAL_DAMAGE_BONUS,
  TRIPLE_DAMAGE_BONUS, BASE_GEM_COST, GEM_COST_SCALE } from './config.js';

let _nid = 1;
export function resetGemIds() { _nid = 1; }

export function createGem(typeId, grade = 1) {
  return { id: _nid++, grade: Math.min(grade, 8), types: new Map([[typeId, 1.0]]), primaryType: typeId };
}

export function combineGems(a, b) {
  const grade = Math.min(Math.max(a.grade, b.grade) + 1, 8);
  const types = new Map();
  const wA = a.grade, wB = b.grade, wT = wA + wB;
  for (const [t,w] of a.types) types.set(t, (types.get(t)||0) + w*wA/wT);
  for (const [t,w] of b.types) types.set(t, (types.get(t)||0) + w*wB/wT);
  for (const [t,w] of types) if (w < 0.1) types.delete(t);
  const sum = [...types.values()].reduce((s,v)=>s+v, 0);
  for (const [t,w] of types) types.set(t, w/sum);
  let primaryType = a.primaryType, mx = 0;
  for (const [t,w] of types) if (w > mx) { primaryType = t; mx = w; }
  return { id: _nid++, grade, types, primaryType };
}

export function gemDamage(gem) {
  let d = BASE_DAMAGE * Math.pow(DAMAGE_SCALE, gem.grade - 1);
  if (gem.types.size === 2) d *= DUAL_DAMAGE_BONUS;
  else if (gem.types.size >= 3) d *= TRIPLE_DAMAGE_BONUS;
  return d;
}
export function gemRange(gem) { return BASE_RANGE + RANGE_SCALE * (gem.grade - 1); }
export function gemFireRate(gem) { return BASE_FIRE_RATE + FIRE_RATE_SCALE * (gem.grade - 1); }

export function gemSpecial(gem) {
  const type = GEM_TYPES[gem.primaryType];
  const sp = SPECIAL[type.ability];
  let power = sp.base + sp.scale * (gem.grade - 1);
  if (gem.types.size === 1) power *= PURE_SPECIAL_BONUS;
  return { ability: type.ability, power, radius: sp.radius, duration: sp.duration, mult: sp.mult };
}

export function gemCost(grade) { return Math.floor(BASE_GEM_COST * Math.pow(GEM_COST_SCALE, grade - 1)); }

export function gemColor(gem) {
  if (gem.types.size === 1) return GEM_TYPES[gem.primaryType].color;
  let r=0,g=0,b=0;
  for (const [t,w] of gem.types) { const c=GEM_TYPES[t].rgb; r+=c[0]*w; g+=c[1]*w; b+=c[2]*w; }
  return `rgb(${Math.round(r)},${Math.round(g)},${Math.round(b)})`;
}

export function gemGlowColor(gem, alpha=0.5) {
  if (gem.types.size===1) return GEM_TYPES[gem.primaryType].glow+alpha+')';
  let r=0,g=0,b=0;
  for (const [t,w] of gem.types) { const c=GEM_TYPES[t].rgb; r+=c[0]*w; g+=c[1]*w; b+=c[2]*w; }
  return `rgba(${Math.round(r)},${Math.round(g)},${Math.round(b)},${alpha})`;
}

export function gemSides(gem) { return GEM_GRADE_SIDES[Math.min(gem.grade-1, GEM_GRADE_SIDES.length-1)]; }

export function drawGemShape(ctx, gem, cx, cy, size) {
  const sides=gemSides(gem), color=gemColor(gem), glow=gemGlowColor(gem,0.6), rot=-Math.PI/2;
  ctx.save();
  ctx.shadowColor=glow; ctx.shadowBlur=size*0.8;
  ctx.beginPath();
  for (let i=0;i<sides;i++){const a=rot+(Math.PI*2*i)/sides;i===0?ctx.moveTo(cx+Math.cos(a)*size,cy+Math.sin(a)*size):ctx.lineTo(cx+Math.cos(a)*size,cy+Math.sin(a)*size);}
  ctx.closePath();
  const gr=ctx.createRadialGradient(cx-size*0.2,cy-size*0.2,0,cx,cy,size);
  gr.addColorStop(0,'#ffffff'); gr.addColorStop(0.3,color); gr.addColorStop(1,shade(color,-40));
  ctx.fillStyle=gr; ctx.fill();
  ctx.strokeStyle='rgba(255,255,255,0.35)'; ctx.lineWidth=1; ctx.stroke();
  ctx.shadowBlur=0;
  ctx.beginPath();
  const inn=size*0.5;
  for (let i=0;i<sides;i++){const a=rot+(Math.PI*2*i)/sides;i===0?ctx.moveTo(cx+Math.cos(a)*inn,cy+Math.sin(a)*inn):ctx.lineTo(cx+Math.cos(a)*inn,cy+Math.sin(a)*inn);}
  ctx.closePath(); ctx.fillStyle='rgba(255,255,255,0.12)'; ctx.fill();
  ctx.restore();
}

function shade(hex, amt) {
  const cl = v => Math.max(0,Math.min(255,v));
  if (hex.startsWith('rgb')) { const m=hex.match(/(\d+)/g); return `rgb(${cl(+m[0]+amt)},${cl(+m[1]+amt)},${cl(+m[2]+amt)})`; }
  const n=parseInt(hex.slice(1),16);
  return `rgb(${cl(((n>>16)&255)+amt)},${cl(((n>>8)&255)+amt)},${cl((n&255)+amt)})`;
}
