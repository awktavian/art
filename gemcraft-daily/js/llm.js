import { GEM_TYPES, TOTAL_WAVES, POD_VOCAB } from './config.js';
import { state, stateForLLM, getResult } from './engine.js';
import { gemDamage, gemRange, gemSpecial } from './gems.js';
import { historyForLLM } from './storage.js';

// MCP tool definitions for agent integration
export const MCP_TOOLS = [
  {
    name: 'gemcraft_daily_state',
    description: 'Get current game state including towers, enemies, mana, wave',
    inputSchema: { type: 'object', properties: {} },
    handler: () => stateForLLM(),
  },
  {
    name: 'gemcraft_daily_history',
    description: 'Get player history including stats, streak, and recent games',
    inputSchema: { type: 'object', properties: { count: { type: 'number', default: 5 } } },
    handler: (args) => historyForLLM(),
  },
  {
    name: 'gemcraft_daily_suggest',
    description: 'Get a strategy suggestion based on current game state',
    inputSchema: { type: 'object', properties: {} },
    handler: () => generateSuggestion(),
  },
  {
    name: 'gemcraft_daily_analyze',
    description: 'Get post-game analysis of the completed puzzle',
    inputSchema: { type: 'object', properties: {} },
    handler: () => analyzeGame(),
  },
];

// Human-readable state for LLM context
export function statePrompt() {
  const s = state;
  const gems = s.availableGemTypes.map(i => `${GEM_TYPES[i].name} (${GEM_TYPES[i].desc})`).join(', ');
  const towers = s.towers.map(t => {
    if (!t.gem) return `  Tower at (${t.x.toFixed(0)},${t.y.toFixed(0)}): empty`;
    const sp = gemSpecial(t.gem);
    return `  Tower at (${t.x.toFixed(0)},${t.y.toFixed(0)}): ${GEM_TYPES[t.gem.primaryType].name} grade ${t.gem.grade} (${sp.ability}, dmg ${Math.floor(gemDamage(t.gem))}, range ${gemRange(t.gem).toFixed(1)})`;
  }).join('\n');
  const enemies = s.enemies.filter(e => !e.dead).length;

  return `Gemcraft Daily Puzzle #${s.puzzleNum}
Wave: ${s.wave}/${TOTAL_WAVES} | Mana: ${s.mana} | Score: ${s.score} | Kills: ${s.kills} | Leaks: ${s.leaks}
Available gems: ${gems}
Inventory: ${s.gemInventory.length} gems in forge
Towers:\n${towers || '  (none)'}
Enemies alive: ${enemies}
Tower slots open: ${s.towerSlots.filter(sl => sl.towerId == null).length}`;
}

function generateSuggestion() {
  const s = state;
  const suggestions = [];

  if (s.towers.length === 0 && s.gemInventory.length === 0) {
    suggestions.push('Forge your first gem and place it on a tower slot near a path bend for maximum coverage.');
  }

  if (s.mana > 200 && s.gemInventory.length === 0) {
    suggestions.push('You have plenty of mana — forge more gems to increase firepower.');
  }

  const hasLeech = s.availableGemTypes.includes(1);
  if (hasLeech && !s.towers.some(t => t.gem?.primaryType === 1)) {
    suggestions.push('Consider forging a Topaz (mana leech) gem early — it pays for itself over time.');
  }

  const hasSlow = s.availableGemTypes.includes(6);
  if (hasSlow && s.wave >= 3 && !s.towers.some(t => t.gem?.primaryType === 6)) {
    suggestions.push('A Sapphire (slow) gem near the entrance gives all other towers more time to fire.');
  }

  if (s.wave >= 5 && s.towers.length < 4) {
    suggestions.push('Build more towers — you need broader coverage for the late waves.');
  }

  if (suggestions.length === 0) {
    suggestions.push('Looking good! Focus on upgrading existing gems by combining rather than building new towers.');
  }

  return { suggestions, state: statePrompt() };
}

function analyzeGame() {
  const r = getResult();
  const analysis = { result: r, insights: [] };

  if (r.leaks === 0) analysis.insights.push('Perfect defense — no enemies leaked through!');
  else if (r.leaks <= 3) analysis.insights.push(`Only ${r.leaks} leak${r.leaks>1?'s':''} — close to perfect.`);
  else analysis.insights.push(`${r.leaks} leaks cost you ${r.leaks * 20} mana. Focus on covering weak spots.`);

  if (r.gemsCombined === 0) analysis.insights.push('You never combined gems — combining creates stronger gems exponentially.');
  if (r.gemsForged > 8) analysis.insights.push('Many gems forged. Try combining more for quality over quantity.');

  const efficiency = r.kills > 0 ? Math.floor(r.score / r.kills) : 0;
  analysis.insights.push(`Kill efficiency: ${efficiency} points per kill.`);

  return analysis;
}

// Register MCP tools if WebMCP is available
export function registerMCPTools() {
  if (typeof window !== 'undefined' && window.__MCP_REGISTER_TOOL) {
    for (const tool of MCP_TOOLS) {
      window.__MCP_REGISTER_TOOL(tool.name, tool.inputSchema, tool.handler);
    }
  }
}

// Pod capability declaration (Turtle format)
export function podCapabilityTurtle() {
  return `@prefix agent: <${POD_VOCAB}> .

<#gemcraft-state>
    a agent:Capability ;
    agent:name "Gemcraft Daily State" ;
    agent:description "Read current game state" ;
    agent:mcpTool "gemcraft_daily_state" .

<#gemcraft-history>
    a agent:Capability ;
    agent:name "Gemcraft Daily History" ;
    agent:description "Read player history and stats" ;
    agent:mcpTool "gemcraft_daily_history" .

<#gemcraft-suggest>
    a agent:Capability ;
    agent:name "Gemcraft Daily Suggest" ;
    agent:description "Get strategy suggestions" ;
    agent:mcpTool "gemcraft_daily_suggest" .
`;
}
