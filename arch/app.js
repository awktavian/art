/**
 * Kagami Architecture Visualization
 * Static, pre-computed layout with smooth interactions
 */

(function() {
  'use strict';

  // State
  let data = null;
  let currentView = 'packages';
  let selectedNode = null;
  let transform = { x: 0, y: 0, k: 1 };
  let svgRect = null;

  // DOM Elements
  const svg = document.getElementById('graph');
  const tooltip = document.getElementById('tooltip');
  const detailPanel = document.getElementById('detail-panel');
  const detailTitle = document.getElementById('detail-title');
  const detailContent = document.getElementById('detail-content');
  const detailClose = document.getElementById('detail-close');
  const componentList = document.getElementById('component-list');
  const legend = document.getElementById('legend');
  const stats = document.getElementById('stats');

  // SVG groups
  let mainGroup = null;
  let linksGroup = null;
  let nodesGroup = null;

  // Node element cache for fast access
  const nodeElements = new Map();
  const linkElements = new Map();

  // Load data
  async function loadData() {
    try {
      const response = await fetch('arch-data.json');
      data = await response.json();
      init();
    } catch (err) {
      console.error('Failed to load architecture data:', err);
    }
  }

  function init() {
    initSVG();
    initEvents();
    renderStats();
    renderView('packages');
  }

  function initSVG() {
    svgRect = svg.getBoundingClientRect();

    // Clear and setup SVG structure
    svg.innerHTML = '';

    // Defs for filters and markers
    const defs = createSVG('defs');

    // Glow filter for highlighted nodes
    const glow = createSVG('filter', { id: 'glow', x: '-50%', y: '-50%', width: '200%', height: '200%' });
    glow.innerHTML = `
      <feGaussianBlur stdDeviation="4" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    `;
    defs.appendChild(glow);

    // Arrow marker
    const marker = createSVG('marker', {
      id: 'arrow',
      viewBox: '0 -5 10 10',
      refX: 8,
      refY: 0,
      markerWidth: 5,
      markerHeight: 5,
      orient: 'auto'
    });
    marker.innerHTML = '<path d="M0,-4L10,0L0,4" fill="#4a4a5a"/>';
    defs.appendChild(marker);

    svg.appendChild(defs);

    // Main group for zoom/pan
    mainGroup = createSVG('g', { class: 'main-group' });
    linksGroup = createSVG('g', { class: 'links' });
    nodesGroup = createSVG('g', { class: 'nodes' });
    mainGroup.appendChild(linksGroup);
    mainGroup.appendChild(nodesGroup);
    svg.appendChild(mainGroup);
  }

  function createSVG(tag, attrs = {}) {
    const el = document.createElementNS('http://www.w3.org/2000/svg', tag);
    for (const [k, v] of Object.entries(attrs)) {
      el.setAttribute(k, v);
    }
    return el;
  }

  function initEvents() {
    // Zoom controls
    document.getElementById('zoom-in').addEventListener('click', () => zoom(1.2));
    document.getElementById('zoom-out').addEventListener('click', () => zoom(0.8));
    document.getElementById('zoom-reset').addEventListener('click', resetView);

    // Pan
    let isPanning = false;
    let panStart = { x: 0, y: 0 };

    svg.addEventListener('mousedown', (e) => {
      if (e.target === svg || e.target.classList.contains('main-group')) {
        isPanning = true;
        panStart = { x: e.clientX - transform.x, y: e.clientY - transform.y };
        svg.style.cursor = 'grabbing';
      }
    });

    svg.addEventListener('mousemove', (e) => {
      if (isPanning) {
        transform.x = e.clientX - panStart.x;
        transform.y = e.clientY - panStart.y;
        applyTransform();
      }
    });

    svg.addEventListener('mouseup', () => {
      isPanning = false;
      svg.style.cursor = 'default';
    });

    svg.addEventListener('mouseleave', () => {
      isPanning = false;
      svg.style.cursor = 'default';
      hideTooltip();
    });

    // Wheel zoom
    svg.addEventListener('wheel', (e) => {
      e.preventDefault();
      const delta = e.deltaY > 0 ? 0.9 : 1.1;
      const mouseX = e.clientX - svgRect.left;
      const mouseY = e.clientY - svgRect.top;
      zoomAt(delta, mouseX, mouseY);
    }, { passive: false });

    // Navigation
    document.querySelectorAll('.nav-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const view = btn.dataset.view;
        document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        renderView(view);
      });
    });

    // Detail panel
    detailClose.addEventListener('click', closeDetail);

    // Resize
    let resizeTimer;
    window.addEventListener('resize', () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => {
        svgRect = svg.getBoundingClientRect();
        renderView(currentView);
      }, 200);
    });
  }

  function zoom(factor) {
    const centerX = svgRect.width / 2;
    const centerY = svgRect.height / 2;
    zoomAt(factor, centerX, centerY);
  }

  function zoomAt(factor, x, y) {
    const newK = Math.max(0.3, Math.min(3, transform.k * factor));
    transform.x = x - (x - transform.x) * (newK / transform.k);
    transform.y = y - (y - transform.y) * (newK / transform.k);
    transform.k = newK;
    applyTransform();
  }

  function resetView() {
    transform = { x: 0, y: 0, k: 1 };
    applyTransform();
  }

  function applyTransform() {
    mainGroup.setAttribute('transform', `translate(${transform.x}, ${transform.y}) scale(${transform.k})`);
  }

  function renderStats() {
    if (!data?.meta) return;
    stats.innerHTML = `
      <div class="stat">
        <span class="stat-value">${data.meta.packageCount}</span> packages
      </div>
      <div class="stat">
        <span class="stat-value">${data.meta.coreModuleCount}</span> modules
      </div>
      <div class="stat">
        <span class="stat-value">${formatLoc(data.meta.totalLoc)}</span> LOC
      </div>
    `;
  }

  function formatLoc(loc) {
    if (loc >= 1000000) return (loc / 1000000).toFixed(1) + 'M';
    if (loc >= 1000) return Math.round(loc / 1000) + 'K';
    return loc;
  }

  function renderView(view) {
    currentView = view;
    closeDetail();
    nodeElements.clear();
    linkElements.clear();
    linksGroup.innerHTML = '';
    nodesGroup.innerHTML = '';
    resetView();

    switch (view) {
      case 'packages':
        renderPackages();
        break;
      case 'core':
        renderCore();
        break;
      case 'flow':
        renderFlow();
        break;
    }
  }

  function renderPackages() {
    const nodes = [...data.packages, ...data.apps];
    const edges = data.packageDeps;
    const positions = data.packagePositions;
    const colors = data.colors;

    // Scale positions to fit viewport
    const padding = 100;
    const { scale, offsetX, offsetY } = computeScale(positions, svgRect.width, svgRect.height, padding);

    // Render edges first (behind nodes)
    edges.forEach(edge => {
      const srcPos = positions[edge.source];
      const tgtPos = positions[edge.target];
      if (!srcPos || !tgtPos) return;

      const x1 = srcPos.x * scale + offsetX;
      const y1 = srcPos.y * scale + offsetY;
      const x2 = tgtPos.x * scale + offsetX;
      const y2 = tgtPos.y * scale + offsetY;

      const line = createSVG('line', {
        class: 'link',
        x1, y1, x2, y2,
        'stroke-width': Math.max(1, Math.min(3, Math.sqrt(edge.count) / 2)),
        'marker-end': 'url(#arrow)',
        'data-source': edge.source,
        'data-target': edge.target
      });

      linksGroup.appendChild(line);
      linkElements.set(`${edge.source}-${edge.target}`, line);
    });

    // Render nodes
    nodes.forEach(node => {
      const pos = positions[node.id];
      if (!pos) return;

      const x = pos.x * scale + offsetX;
      const y = pos.y * scale + offsetY;
      const radius = computeRadius(node.loc, 12, 45);
      const color = colors[node.lang] || colors.mixed || '#6366f1';

      const group = createSVG('g', {
        class: 'node',
        transform: `translate(${x}, ${y})`,
        'data-id': node.id
      });

      const circle = createSVG('circle', {
        class: 'node-circle',
        r: radius,
        fill: color
      });

      const label = createSVG('text', {
        class: 'node-label',
        y: radius + 16
      });
      label.textContent = formatName(node.name);

      group.appendChild(circle);
      group.appendChild(label);

      // Events
      group.addEventListener('mouseenter', (e) => showTooltip(e, node));
      group.addEventListener('mouseleave', hideTooltip);
      group.addEventListener('click', () => selectNode(node));

      nodesGroup.appendChild(group);
      nodeElements.set(node.id, group);
    });

    // Sidebar
    renderComponentList(nodes, colors);
    renderLegend(colors);
  }

  function renderCore() {
    const nodes = data.coreModules;
    const edges = data.coreDeps;
    const positions = data.corePositions;
    const colors = data.colors;

    // Use single color for core modules
    const coreColor = '#818cf8';

    // Scale positions
    const padding = 80;
    const { scale, offsetX, offsetY } = computeScale(positions, svgRect.width, svgRect.height, padding);

    // Render edges
    edges.forEach(edge => {
      const srcPos = positions[edge.source];
      const tgtPos = positions[edge.target];
      if (!srcPos || !tgtPos) return;

      const x1 = srcPos.x * scale + offsetX;
      const y1 = srcPos.y * scale + offsetY;
      const x2 = tgtPos.x * scale + offsetX;
      const y2 = tgtPos.y * scale + offsetY;

      const line = createSVG('line', {
        class: 'link',
        x1, y1, x2, y2,
        'stroke-width': Math.max(1, Math.min(2, edge.count / 5)),
        'marker-end': 'url(#arrow)',
        'data-source': edge.source,
        'data-target': edge.target
      });

      linksGroup.appendChild(line);
      linkElements.set(`${edge.source}-${edge.target}`, line);
    });

    // Render nodes
    nodes.forEach(node => {
      const pos = positions[node.id];
      if (!pos) return;

      const x = pos.x * scale + offsetX;
      const y = pos.y * scale + offsetY;
      const radius = computeRadius(node.loc, 10, 35);

      const group = createSVG('g', {
        class: 'node',
        transform: `translate(${x}, ${y})`,
        'data-id': node.id
      });

      const circle = createSVG('circle', {
        class: 'node-circle',
        r: radius,
        fill: coreColor
      });

      const label = createSVG('text', {
        class: 'node-label',
        y: radius + 14
      });
      label.textContent = node.name;

      group.appendChild(circle);
      group.appendChild(label);

      group.addEventListener('mouseenter', (e) => showTooltip(e, node));
      group.addEventListener('mouseleave', hideTooltip);
      group.addEventListener('click', () => selectNode(node));

      nodesGroup.appendChild(group);
      nodeElements.set(node.id, group);
    });

    // Sidebar
    renderComponentList(nodes, { python: coreColor });
    renderLegend({ 'Core Module': coreColor });
  }

  function renderFlow() {
    // Predefined data flow visualization - clear horizontal flow with feedback loops
    const flowNodes = [
      { id: 'input', name: 'User Input', x: 0.08, y: 0.5, type: 'external' },
      { id: 'agents', name: 'Agents', x: 0.21, y: 0.5, type: 'core' },
      { id: 'world_model', name: 'World Model', x: 0.34, y: 0.30, type: 'core' },
      { id: 'active_inference', name: 'Active Inference', x: 0.50, y: 0.40, type: 'core' },
      { id: 'safety', name: 'Safety', x: 0.66, y: 0.5, type: 'safety' },
      { id: 'effectors', name: 'Effectors', x: 0.79, y: 0.5, type: 'core' },
      { id: 'output', name: 'External World', x: 0.92, y: 0.5, type: 'external' },
      { id: 'symbiote', name: 'Symbiote', x: 0.34, y: 0.64, type: 'core' },
      { id: 'memory', name: 'Memory', x: 0.21, y: 0.64, type: 'core' }
    ];

    const flowEdges = [
      { source: 'input', target: 'agents' },
      { source: 'agents', target: 'world_model' },
      { source: 'world_model', target: 'active_inference' },
      { source: 'active_inference', target: 'safety' },
      { source: 'safety', target: 'effectors' },
      { source: 'effectors', target: 'output' },
      { source: 'memory', target: 'symbiote' },
      { source: 'symbiote', target: 'active_inference' }
    ];

    const typeColors = {
      external: '#64748b',
      core: '#818cf8',
      safety: '#f87171'
    };

    const width = svgRect.width;
    const height = svgRect.height;

    // Position map
    const posMap = {};
    flowNodes.forEach(n => {
      posMap[n.id] = { x: n.x * width, y: n.y * height };
    });

    // Render edges
    flowEdges.forEach(edge => {
      const src = posMap[edge.source];
      const tgt = posMap[edge.target];

      const line = createSVG('line', {
        class: 'link',
        x1: src.x, y1: src.y,
        x2: tgt.x, y2: tgt.y,
        'stroke-width': 2,
        'marker-end': 'url(#arrow)'
      });

      linksGroup.appendChild(line);
    });

    // Render nodes as rounded rectangles
    flowNodes.forEach(node => {
      const x = posMap[node.id].x;
      const y = posMap[node.id].y;
      const color = typeColors[node.type];

      const group = createSVG('g', {
        class: 'node',
        transform: `translate(${x}, ${y})`,
        'data-id': node.id
      });

      const rect = createSVG('rect', {
        x: -55,
        y: -25,
        width: 110,
        height: 50,
        rx: 8,
        fill: color,
        class: 'node-circle'
      });

      const label = createSVG('text', {
        class: 'node-label',
        y: 5,
        fill: 'white'
      });
      label.textContent = node.name;

      group.appendChild(rect);
      group.appendChild(label);

      group.addEventListener('click', () => {
        const coreModule = data.coreModules.find(m => m.id === node.id || m.name === node.id);
        if (coreModule) selectNode(coreModule);
      });

      nodesGroup.appendChild(group);
    });

    // Legend
    renderLegend(typeColors);
    componentList.innerHTML = `
      <p style="color: var(--text-muted); font-size: 12px;">
        Data flows from user input through the cognitive architecture to external actions.
        The safety layer (CBF) ensures all actions satisfy constraints.
      </p>
    `;
  }

  function computeScale(positions, width, height, padding) {
    let minX = Infinity, maxX = -Infinity;
    let minY = Infinity, maxY = -Infinity;

    for (const pos of Object.values(positions)) {
      if (pos.x < minX) minX = pos.x;
      if (pos.x > maxX) maxX = pos.x;
      if (pos.y < minY) minY = pos.y;
      if (pos.y > maxY) maxY = pos.y;
    }

    const dataWidth = maxX - minX || 1;
    const dataHeight = maxY - minY || 1;

    const scaleX = (width - padding * 2) / dataWidth;
    const scaleY = (height - padding * 2) / dataHeight;
    const scale = Math.min(scaleX, scaleY);

    const offsetX = padding - minX * scale + (width - padding * 2 - dataWidth * scale) / 2;
    const offsetY = padding - minY * scale + (height - padding * 2 - dataHeight * scale) / 2;

    return { scale, offsetX, offsetY };
  }

  function computeRadius(loc, min, max) {
    if (!loc) return min;
    // Log scale for better distribution
    const logLoc = Math.log10(loc + 1);
    const normalized = (logLoc - 2) / 4; // Assume loc ranges from 100 to 1M
    return Math.max(min, Math.min(max, min + (max - min) * normalized));
  }

  function formatName(name) {
    // Don't strip if it would leave nothing
    let formatted = name
      .replace(/^kagami[_-]/, '')  // Only strip "kagami_" or "kagami-", not "kagami" itself
      .replace(/^app[_-]/, '')
      .replace(/-/g, '_');
    return formatted || name;  // Fallback to original if empty
  }

  function renderComponentList(nodes, colors) {
    componentList.innerHTML = '';

    // Sort by LOC descending
    const sorted = [...nodes].sort((a, b) => (b.loc || 0) - (a.loc || 0));

    sorted.forEach(node => {
      const color = colors[node.lang] || colors.python || '#818cf8';
      const item = document.createElement('div');
      item.className = 'component-item';
      item.dataset.id = node.id;
      item.innerHTML = `
        <span class="component-dot" style="background: ${color}"></span>
        <span class="component-name">${formatName(node.name)}</span>
        <span class="component-meta">${node.loc ? formatLoc(node.loc) : node.files || ''}</span>
      `;

      item.addEventListener('click', () => {
        document.querySelectorAll('.component-item').forEach(i => i.classList.remove('active'));
        item.classList.add('active');
        selectNode(node);
        centerOnNode(node.id);
      });

      componentList.appendChild(item);
    });
  }

  function renderLegend(colors) {
    legend.innerHTML = '';
    for (const [name, color] of Object.entries(colors)) {
      const item = document.createElement('div');
      item.className = 'legend-item';
      item.innerHTML = `
        <span class="legend-dot" style="background: ${color}"></span>
        <span>${name.charAt(0).toUpperCase() + name.slice(1)}</span>
      `;
      legend.appendChild(item);
    }
  }

  function centerOnNode(nodeId) {
    const el = nodeElements.get(nodeId);
    if (!el) return;

    const transform_attr = el.getAttribute('transform');
    const match = transform_attr.match(/translate\(([^,]+),\s*([^)]+)\)/);
    if (!match) return;

    const x = parseFloat(match[1]);
    const y = parseFloat(match[2]);

    transform.x = svgRect.width / 2 - x * transform.k;
    transform.y = svgRect.height / 2 - y * transform.k;
    applyTransform();
  }

  // Tooltip
  function showTooltip(e, node) {
    let statsHtml = '';
    if (node.loc) {
      statsHtml = `
        <div class="tooltip-stats">
          <div class="tooltip-stat"><strong>${formatLoc(node.loc)}</strong> LOC</div>
          ${node.files ? `<div class="tooltip-stat"><strong>${node.files}</strong> files</div>` : ''}
        </div>
      `;
    }

    tooltip.innerHTML = `
      <div class="tooltip-title">${node.name}</div>
      ${node.description ? `<div class="tooltip-desc">${node.description}</div>` : ''}
      ${statsHtml}
    `;

    // Position
    let left = e.clientX + 12;
    let top = e.clientY + 12;

    // Keep in viewport
    const rect = tooltip.getBoundingClientRect();
    if (left + 300 > window.innerWidth) {
      left = e.clientX - 312;
    }
    if (top + 100 > window.innerHeight) {
      top = e.clientY - 112;
    }

    tooltip.style.left = left + 'px';
    tooltip.style.top = top + 'px';
    tooltip.classList.add('visible');
  }

  function hideTooltip() {
    tooltip.classList.remove('visible');
  }

  // Selection
  function selectNode(node) {
    selectedNode = node;

    // Update visual selection
    document.querySelectorAll('.node').forEach(n => n.classList.remove('selected'));
    const el = nodeElements.get(node.id);
    if (el) el.classList.add('selected');

    // Highlight connected links
    document.querySelectorAll('.link').forEach(link => {
      link.classList.remove('highlighted');
      const src = link.getAttribute('data-source');
      const tgt = link.getAttribute('data-target');
      if (src === node.id || tgt === node.id) {
        link.classList.add('highlighted');
      }
    });

    // Update sidebar
    document.querySelectorAll('.component-item').forEach(item => {
      item.classList.toggle('active', item.dataset.id === node.id);
    });

    // Show detail panel
    showDetail(node);
  }

  function showDetail(node) {
    detailTitle.textContent = node.name;

    // Find dependencies
    const deps = currentView === 'packages' ? data.packageDeps : data.coreDeps;
    const outgoing = deps.filter(d => d.source === node.id);
    const incoming = deps.filter(d => d.target === node.id);

    detailContent.innerHTML = `
      ${node.description ? `
        <div class="detail-section">
          <div class="detail-section-title">Description</div>
          <div class="detail-description">${node.description}</div>
        </div>
      ` : ''}

      <div class="detail-section">
        <div class="detail-section-title">Statistics</div>
        <div class="detail-grid">
          ${node.loc ? `
            <div class="detail-stat">
              <div class="detail-stat-label">Lines of Code</div>
              <div class="detail-stat-value">${formatLoc(node.loc)}</div>
            </div>
          ` : ''}
          ${node.files ? `
            <div class="detail-stat">
              <div class="detail-stat-label">Files</div>
              <div class="detail-stat-value">${node.files}</div>
            </div>
          ` : ''}
          ${node.modules ? `
            <div class="detail-stat">
              <div class="detail-stat-label">Modules</div>
              <div class="detail-stat-value">${node.modules}</div>
            </div>
          ` : ''}
          ${node.lang ? `
            <div class="detail-stat">
              <div class="detail-stat-label">Language</div>
              <div class="detail-stat-value">${node.lang}</div>
            </div>
          ` : ''}
        </div>
      </div>

      ${outgoing.length > 0 ? `
        <div class="detail-section">
          <div class="detail-section-title">Depends On (${outgoing.length})</div>
          <div class="detail-deps">
            ${outgoing.map(d => `
              <div class="detail-dep" data-id="${d.target}">
                <span class="detail-dep-arrow">→</span>
                <span class="detail-dep-name">${formatName(d.target)}</span>
                <span class="detail-dep-count">${d.count} refs</span>
              </div>
            `).join('')}
          </div>
        </div>
      ` : ''}

      ${incoming.length > 0 ? `
        <div class="detail-section">
          <div class="detail-section-title">Used By (${incoming.length})</div>
          <div class="detail-deps">
            ${incoming.map(d => `
              <div class="detail-dep" data-id="${d.source}">
                <span class="detail-dep-arrow">←</span>
                <span class="detail-dep-name">${formatName(d.source)}</span>
                <span class="detail-dep-count">${d.count} refs</span>
              </div>
            `).join('')}
          </div>
        </div>
      ` : ''}
    `;

    // Add click handlers for dependency navigation
    detailContent.querySelectorAll('.detail-dep').forEach(dep => {
      dep.addEventListener('click', () => {
        const targetId = dep.dataset.id;
        const allNodes = currentView === 'packages'
          ? [...data.packages, ...data.apps]
          : data.coreModules;
        const targetNode = allNodes.find(n => n.id === targetId);
        if (targetNode) {
          selectNode(targetNode);
          centerOnNode(targetId);
        }
      });
    });

    detailPanel.classList.add('open');
  }

  function closeDetail() {
    detailPanel.classList.remove('open');
    selectedNode = null;
    document.querySelectorAll('.node').forEach(n => n.classList.remove('selected'));
    document.querySelectorAll('.link').forEach(l => l.classList.remove('highlighted'));
    document.querySelectorAll('.component-item').forEach(i => i.classList.remove('active'));
  }

  // Initialize
  loadData();
})();
