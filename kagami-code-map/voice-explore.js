/**
 * Kagami Code Map — Voice Exploration
 * ====================================
 * Grove colony (The Motorist / sage) — the AI's sensorimotor interface
 * to the 3D semantic code galaxy. Tools give the AI perception of the
 * codebase topology and motor control over navigation.
 *
 * Perception:  survey_codebase, inspect_file, scan_cluster, find_by_concept
 * Action:      fly_to_file, fly_to_cluster, highlight_connections, search_and_highlight
 * Introspection: measure_similarity, trace_dependency_chain
 *
 * h(x) >= 0 always
 */

'use strict';

(function () {
  const isLocal = location.hostname === 'localhost' || location.hostname === '127.0.0.1';
  const PROXY_BASE = isLocal ? 'ws://localhost:8766' : 'wss://kagami-realtime-proxy.fly.dev';

  const toggleBtn = document.getElementById('voice-toggle');
  const statusEl = document.getElementById('voice-status');
  const transcriptEl = document.getElementById('voice-transcript');
  const overlay = document.getElementById('voice-overlay');

  if (!toggleBtn || !window.RealtimeVoice) return;

  const config = window.buildVoiceConfig ? window.buildVoiceConfig('kagami-code-map') : null;

  let voice = null;
  let connected = false;
  let holding = false;

  // ═══════════════════════════════════════════════════════════════════════
  // DATA ACCESS
  // ═══════════════════════════════════════════════════════════════════════

  function getFiles() {
    const d = window._codeGalaxyData || window._appData;
    return d?.files || d?.data?.files || [];
  }

  function findFile(pathOrName) {
    const files = getFiles();
    const q = (pathOrName || '').toLowerCase();
    return files.find(f => f.path === pathOrName || f.path?.toLowerCase() === q
      || f.name?.toLowerCase() === q || f.path?.toLowerCase().endsWith('/' + q));
  }

  // ═══════════════════════════════════════════════════════════════════════
  // AI TOOLS — sensorimotor interface
  // ═══════════════════════════════════════════════════════════════════════

  const tools = [
    // ── PERCEPTION ──────────────────────────────────────────────────────
    {
      name: 'survey_codebase',
      description: 'Perceive the entire codebase at a glance: total files, total lines, cluster breakdown with file counts and representative files, language distribution, largest files. This is your wide-angle sense.',
      parameters: { type: 'object', properties: {}, required: [] },
    },
    {
      name: 'inspect_file',
      description: 'Deep inspection of a single file: full metadata, functions, classes, imports, exports, keywords, concepts, summary, embedding position, cluster membership, line count.',
      parameters: {
        type: 'object',
        properties: { path: { type: 'string', description: 'File path or name to inspect' } },
        required: ['path'],
      },
    },
    {
      name: 'scan_cluster',
      description: 'Examine a specific cluster: all its files, common patterns, representative functions/classes, inter-cluster connections.',
      parameters: {
        type: 'object',
        properties: { cluster_id: { type: 'integer', description: 'Cluster ID number' } },
        required: ['cluster_id'],
      },
    },
    {
      name: 'find_by_concept',
      description: 'Search the codebase by semantic concept, function name, class name, keyword, or file path pattern. Returns ranked results with relevance context.',
      parameters: {
        type: 'object',
        properties: {
          query: { type: 'string', description: 'Concept, function, class, keyword, or path fragment to search for' },
          max_results: { type: 'integer', description: 'Maximum results (default 10)' },
        },
        required: ['query'],
      },
    },
    {
      name: 'measure_similarity',
      description: 'Compute semantic similarity between a target file and all others using embedding distance, cluster membership, and import relationships. Returns the N most similar files.',
      parameters: {
        type: 'object',
        properties: {
          path: { type: 'string', description: 'File path to measure from' },
          count: { type: 'integer', description: 'How many similar files to return (default 8)' },
        },
        required: ['path'],
      },
    },
    {
      name: 'trace_dependency_chain',
      description: 'Trace the import/export dependency chain from a file: what it imports, what imports it, and the transitive closure up to 2 hops.',
      parameters: {
        type: 'object',
        properties: { path: { type: 'string', description: 'File path to trace from' } },
        required: ['path'],
      },
    },

    // ── ACTION ──────────────────────────────────────────────────────────
    {
      name: 'fly_to_file',
      description: 'Navigate the 3D camera to center on a specific file node. Triggers smooth camera animation.',
      parameters: {
        type: 'object',
        properties: { path: { type: 'string', description: 'File path to fly to' } },
        required: ['path'],
      },
    },
    {
      name: 'fly_to_cluster',
      description: 'Navigate the 3D camera to the centroid of a cluster, showing all its member files.',
      parameters: {
        type: 'object',
        properties: { cluster_id: { type: 'integer', description: 'Cluster ID to fly to' } },
        required: ['cluster_id'],
      },
    },
    {
      name: 'search_and_highlight',
      description: 'Inject a search query into the app search field, highlighting matching files in the 3D view. Non-matching files dim.',
      parameters: {
        type: 'object',
        properties: { query: { type: 'string', description: 'Search query to highlight' } },
        required: ['query'],
      },
    },
  ];

  function handleFunctionCall(name, args) {
    const files = getFiles();

    switch (name) {
      // ── PERCEPTION ────────────────────────────────────────────────────
      case 'survey_codebase': {
        const clusterMap = {};
        const categories = {};
        let totalLines = 0;
        const largest = [];

        for (const f of files) {
          const cid = f.cluster ?? -1;
          if (!clusterMap[cid]) clusterMap[cid] = { id: cid, count: 0, sample_files: [], total_lines: 0 };
          clusterMap[cid].count++;
          clusterMap[cid].total_lines += (f.lines || f.lineCount || 0);
          if (clusterMap[cid].sample_files.length < 4) clusterMap[cid].sample_files.push(f.name || f.path);

          const cat = f.category || f.language || 'unknown';
          categories[cat] = (categories[cat] || 0) + 1;
          totalLines += (f.lines || f.lineCount || 0);
          largest.push({ path: f.path, lines: f.lines || f.lineCount || 0 });
        }
        largest.sort((a, b) => b.lines - a.lines);

        return {
          total_files: files.length,
          total_lines: totalLines,
          clusters: Object.values(clusterMap).sort((a, b) => b.count - a.count),
          languages: categories,
          largest_files: largest.slice(0, 10),
        };
      }

      case 'inspect_file': {
        const file = findFile(args.path);
        if (!file) return { error: `File not found: ${args.path}` };
        return {
          path: file.path, name: file.name,
          summary: file.summary || null,
          cluster: file.cluster, category: file.category,
          lines: file.lines || file.lineCount || 0,
          functions: file.functions || [], classes: file.classes || [],
          imports: file.imports || [], exports: file.exports || [],
          keywords: file.keywords || [], concepts: file.concepts || [],
          position_3d: { x: +(file.x || 0).toFixed(3), y: +(file.y || 0).toFixed(3), z: +(file.z || 0).toFixed(3) },
        };
      }

      case 'scan_cluster': {
        const cid = args.cluster_id;
        const members = files.filter(f => f.cluster === cid);
        if (members.length === 0) return { error: `Cluster ${cid} not found or empty` };

        const allFunctions = [];
        const allClasses = [];
        const allKeywords = {};
        for (const f of members) {
          (f.functions || []).forEach(fn => allFunctions.push({ file: f.name, function: fn }));
          (f.classes || []).forEach(cl => allClasses.push({ file: f.name, class: cl }));
          (f.keywords || []).forEach(kw => { allKeywords[kw] = (allKeywords[kw] || 0) + 1; });
        }

        // Find cross-cluster imports
        const crossCluster = new Set();
        for (const f of members) {
          for (const imp of (f.imports || [])) {
            const target = files.find(t => t.exports?.includes(imp));
            if (target && target.cluster !== cid) crossCluster.add(`${target.cluster}`);
          }
        }

        return {
          cluster_id: cid,
          file_count: members.length,
          total_lines: members.reduce((s, f) => s + (f.lines || 0), 0),
          files: members.map(f => ({ path: f.path, name: f.name, lines: f.lines || 0 })),
          top_functions: allFunctions.slice(0, 15),
          top_classes: allClasses.slice(0, 10),
          common_keywords: Object.entries(allKeywords).sort(([,a],[,b]) => b-a).slice(0, 10).map(([k,v]) => ({ keyword: k, count: v })),
          connected_clusters: [...crossCluster].map(Number),
        };
      }

      case 'find_by_concept': {
        const q = (args.query || '').toLowerCase();
        const max = args.max_results || 10;
        const scored = [];

        for (const f of files) {
          let score = 0;
          const name = (f.name || '').toLowerCase();
          const path = (f.path || '').toLowerCase();
          if (name === q) score += 100;
          else if (name.includes(q)) score += 50;
          if (path.includes(q)) score += 20;
          for (const fn of (f.functions || [])) { if (fn.toLowerCase().includes(q)) score += 30; }
          for (const cl of (f.classes || [])) { if (cl.toLowerCase().includes(q)) score += 35; }
          for (const kw of (f.keywords || [])) { if (kw.toLowerCase().includes(q)) score += 15; }
          for (const co of (f.concepts || [])) { if (co.toLowerCase().includes(q)) score += 20; }
          if ((f.summary || '').toLowerCase().includes(q)) score += 10;
          if (score > 0) scored.push({ path: f.path, name: f.name, score, cluster: f.cluster, summary: f.summary || null, lines: f.lines || 0 });
        }
        scored.sort((a, b) => b.score - a.score);
        return { query: args.query, results: scored.slice(0, max), total_matches: scored.length };
      }

      case 'measure_similarity': {
        const target = findFile(args.path);
        if (!target) return { error: `File not found: ${args.path}` };
        const count = args.count || 8;
        const scored = files.filter(f => f.path !== target.path).map(f => {
          const dx = (f.x||0) - (target.x||0), dy = (f.y||0) - (target.y||0), dz = (f.z||0) - (target.z||0);
          const dist = Math.sqrt(dx*dx + dy*dy + dz*dz);
          let score = 1 / (1 + dist * 1.2);
          if (f.cluster === target.cluster) score += 0.2;
          if (f.category === target.category) score += 0.1;
          const targetImports = target.imports || [];
          const fileExports = f.exports || [];
          if (targetImports.some(i => fileExports.includes(i))) score += 0.15;
          return { path: f.path, name: f.name, similarity: Math.round(score * 100), cluster: f.cluster, distance_3d: +dist.toFixed(3) };
        }).sort((a, b) => b.similarity - a.similarity).slice(0, count);
        return { target: target.path, similar: scored };
      }

      case 'trace_dependency_chain': {
        const target = findFile(args.path);
        if (!target) return { error: `File not found: ${args.path}` };
        const imports = (target.imports || []).map(imp => {
          const provider = files.find(f => (f.exports || []).includes(imp));
          return { symbol: imp, provided_by: provider?.path || 'external' };
        });
        const importedBy = files.filter(f => (f.imports || []).some(imp => (target.exports || []).includes(imp)))
          .map(f => ({ path: f.path, imports: (f.imports || []).filter(i => (target.exports || []).includes(i)) }));

        return {
          file: target.path,
          exports: target.exports || [],
          imports_from: imports,
          imported_by: importedBy.slice(0, 15),
          depth: { imports: imports.length, importers: importedBy.length },
        };
      }

      // ── ACTION ────────────────────────────────────────────────────────
      case 'fly_to_file': {
        const file = findFile(args.path);
        if (!file) return { error: `File not found: ${args.path}` };
        document.dispatchEvent(new CustomEvent('voice-navigate', { detail: { file } }));
        return { navigated: true, path: file.path, position: { x: +(file.x||0).toFixed(3), y: +(file.y||0).toFixed(3), z: +(file.z||0).toFixed(3) } };
      }

      case 'fly_to_cluster': {
        const members = files.filter(f => f.cluster === args.cluster_id);
        if (members.length === 0) return { error: `Cluster ${args.cluster_id} empty` };
        const cx = members.reduce((s,f) => s+(f.x||0), 0) / members.length;
        const cy = members.reduce((s,f) => s+(f.y||0), 0) / members.length;
        const cz = members.reduce((s,f) => s+(f.z||0), 0) / members.length;
        document.dispatchEvent(new CustomEvent('voice-navigate', { detail: { file: { x: cx, y: cy, z: cz, path: `cluster-${args.cluster_id}` } } }));
        return { navigated: true, cluster: args.cluster_id, centroid: { x: +cx.toFixed(3), y: +cy.toFixed(3), z: +cz.toFixed(3) }, file_count: members.length };
      }

      case 'search_and_highlight': {
        const input = document.querySelector('input[type="search"], input[placeholder*="earch"], #search-input, input[type="text"]');
        if (input) { input.value = args.query; input.dispatchEvent(new Event('input', { bubbles: true })); }
        return { highlighted: true, query: args.query };
      }

      default:
        return { error: `Unknown tool: ${name}` };
    }
  }

  // ═══════════════════════════════════════════════════════════════════════
  // TRANSCRIPT
  // ═══════════════════════════════════════════════════════════════════════

  let transcriptBuffer = '';
  function appendTranscript(text, role) {
    if (role === 'user') { transcriptBuffer = ''; addLine('You: ' + text, '#f0c860'); }
    else { transcriptBuffer += text; updateLast(transcriptBuffer); }
  }
  function addLine(text, color) {
    const div = document.createElement('div');
    div.style.cssText = `padding:2px 0;color:${color || 'var(--text-400)'}`;
    div.textContent = text;
    transcriptEl.appendChild(div);
    transcriptEl.scrollTop = transcriptEl.scrollHeight;
    while (transcriptEl.children.length > 8) transcriptEl.removeChild(transcriptEl.firstChild);
  }
  function updateLast(text) {
    const lines = transcriptEl.querySelectorAll('div');
    const last = lines[lines.length - 1];
    if (last && !last.textContent.startsWith('You:') && !last.textContent.includes('connected') && !last.textContent.includes('Error')) { last.textContent = text; }
    else { const div = document.createElement('div'); div.style.cssText = 'padding:2px 0;color:#ffd878'; div.textContent = text; transcriptEl.appendChild(div); }
    transcriptEl.scrollTop = transcriptEl.scrollHeight;
  }

  // ═══════════════════════════════════════════════════════════════════════
  // CONNECTION
  // ═══════════════════════════════════════════════════════════════════════

  async function connect() {
    const colony = config?.colony;
    const proxyUrl = new URL(PROXY_BASE);
    proxyUrl.searchParams.set('project', 'kagami-code-map');
    if (colony) proxyUrl.searchParams.set('colony', colony.colony.toLowerCase());

    voice = new RealtimeVoice({
      proxyUrl: proxyUrl.toString(),
      voice: config?.voice || 'sage',
      instructions: (config?.instructions || 'You explore a 3D code visualization.') +
        `\nThe codebase has ${getFiles().length} files. Use survey_codebase for an overview, find_by_concept to search, inspect_file for details, fly_to_file to navigate.`,
      tools,
      onTranscript: appendTranscript,
      onFunctionCall: handleFunctionCall,
      onStateChange: (s) => {
        overlay.dataset.state = s;
        const col = config?.colony;
        statusEl.textContent = s === 'ready' ? (col?.colony || 'Ready') : s === 'listening' ? 'Listening...' : s === 'speaking' ? 'Speaking' : 'Voice';
        toggleBtn.style.borderColor = s === 'listening' ? (col?.color || '#2d5a27') : s === 'speaking' ? '#ffd878' : connected ? 'rgba(255,255,255,0.15)' : 'rgba(255,255,255,0.08)';
        toggleBtn.style.boxShadow = s === 'listening' ? `0 0 16px ${col?.color || '#2d5a27'}40` : 'none';
        transcriptEl.style.display = ['ready','listening','speaking'].includes(s) ? 'block' : 'none';
      },
      onError: (e) => { addLine('Error: ' + (e.message || e), '#f87171'); },
    });
    await voice.connect();
    connected = true;
    const c = config?.colony;
    addLine(c ? `${c.character} (${c.colony}) online. Hold Space to speak.` : 'Connected. Hold Space to speak.', 'rgba(255,255,255,0.35)');
  }

  function disconnect() {
    if (voice) { voice.disconnect(); voice = null; }
    connected = false; statusEl.textContent = 'Voice';
    toggleBtn.style.borderColor = 'rgba(255,255,255,0.08)'; transcriptEl.style.display = 'none';
  }

  toggleBtn.addEventListener('click', async () => {
    if (connected) disconnect();
    else { statusEl.textContent = 'Connecting...'; try { await connect(); } catch { statusEl.textContent = 'Failed'; addLine('Proxy unreachable at :8766', '#f87171'); } }
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'v' && !e.ctrlKey && !e.metaKey && e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') { e.preventDefault(); toggleBtn.click(); return; }
    if (e.key === ' ' && connected && !holding && e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') { e.preventDefault(); holding = true; voice.startListening(); }
  });
  document.addEventListener('keyup', (e) => { if (e.key === ' ' && holding) { e.preventDefault(); holding = false; if (voice) voice.stopListening(); } });
})();
