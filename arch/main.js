// Kagami Architecture Visualization - Main
// SVG-based, GPU-accelerated, performance-first

(function() {
  'use strict';

  const { packages, apps, packageDeps, coreModules, coreDeps, dataFlows, langColors } = window.ARCH_DATA;

  // State
  let currentView = 'packages';
  let selectedNode = null;
  let simulation = null;
  let transform = { x: 0, y: 0, k: 1 };

  // DOM Elements
  const svg = document.getElementById('graph');
  const tooltip = document.getElementById('tooltip');
  const detailPanel = document.getElementById('detail-panel');
  const detailTitle = document.getElementById('detail-title');
  const detailContent = document.getElementById('detail-content');
  const detailClose = document.getElementById('detail-close');
  const packageList = document.getElementById('package-list');

  // SVG setup
  let width, height;
  let g; // Main group for transform

  function initSVG() {
    const rect = svg.getBoundingClientRect();
    width = rect.width;
    height = rect.height;

    // Clear SVG
    svg.innerHTML = '';

    // Create defs for gradients and markers
    const defs = createSVGElement('defs');

    // Arrow marker for directed edges
    const marker = createSVGElement('marker', {
      id: 'arrowhead',
      viewBox: '0 -5 10 10',
      refX: 20,
      refY: 0,
      markerWidth: 6,
      markerHeight: 6,
      orient: 'auto'
    });
    const markerPath = createSVGElement('path', {
      d: 'M0,-5L10,0L0,5',
      fill: '#4a4a5a'
    });
    marker.appendChild(markerPath);
    defs.appendChild(marker);
    svg.appendChild(defs);

    // Main group for zoom/pan
    g = createSVGElement('g', { class: 'main-group' });
    svg.appendChild(g);

    // Links group (below nodes)
    const linksGroup = createSVGElement('g', { class: 'links' });
    g.appendChild(linksGroup);

    // Nodes group
    const nodesGroup = createSVGElement('g', { class: 'nodes' });
    g.appendChild(nodesGroup);

    // Setup zoom/pan
    setupZoom();
  }

  function createSVGElement(tag, attrs = {}) {
    const el = document.createElementNS('http://www.w3.org/2000/svg', tag);
    for (const [key, value] of Object.entries(attrs)) {
      el.setAttribute(key, value);
    }
    return el;
  }

  function setupZoom() {
    let isPanning = false;
    let startX, startY;

    svg.addEventListener('mousedown', (e) => {
      if (e.target === svg || e.target === g) {
        isPanning = true;
        startX = e.clientX - transform.x;
        startY = e.clientY - transform.y;
        svg.style.cursor = 'grabbing';
      }
    });

    svg.addEventListener('mousemove', (e) => {
      if (isPanning) {
        transform.x = e.clientX - startX;
        transform.y = e.clientY - startY;
        updateTransform();
      }
    });

    svg.addEventListener('mouseup', () => {
      isPanning = false;
      svg.style.cursor = 'default';
    });

    svg.addEventListener('mouseleave', () => {
      isPanning = false;
      svg.style.cursor = 'default';
    });

    svg.addEventListener('wheel', (e) => {
      e.preventDefault();
      const delta = e.deltaY > 0 ? 0.9 : 1.1;
      const newK = Math.max(0.3, Math.min(3, transform.k * delta));

      // Zoom toward mouse position
      const rect = svg.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      transform.x = mouseX - (mouseX - transform.x) * (newK / transform.k);
      transform.y = mouseY - (mouseY - transform.y) * (newK / transform.k);
      transform.k = newK;

      updateTransform();
    }, { passive: false });
  }

  function updateTransform() {
    g.setAttribute('transform', `translate(${transform.x}, ${transform.y}) scale(${transform.k})`);
  }

  // Force simulation
  function createSimulation(nodes, links) {
    // Simple force simulation without d3
    const alpha = 1;
    const alphaDecay = 0.02;
    const velocityDecay = 0.4;

    // Initialize positions
    nodes.forEach((node, i) => {
      if (node.x === undefined) {
        const angle = (i / nodes.length) * 2 * Math.PI;
        const radius = Math.min(width, height) * 0.3;
        node.x = width / 2 + Math.cos(angle) * radius;
        node.y = height / 2 + Math.sin(angle) * radius;
      }
      node.vx = 0;
      node.vy = 0;
    });

    // Create link map for quick lookup
    const linkMap = new Map();
    links.forEach(link => {
      const key = `${link.source}-${link.target}`;
      linkMap.set(key, link);
    });

    // Node map for quick lookup
    const nodeMap = new Map();
    nodes.forEach(node => nodeMap.set(node.id, node));

    let currentAlpha = alpha;

    function tick() {
      if (currentAlpha < 0.001) return false;

      // Apply forces
      nodes.forEach(node => {
        // Center force
        node.vx += (width / 2 - node.x) * 0.01;
        node.vy += (height / 2 - node.y) * 0.01;
      });

      // Repulsion between nodes
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const a = nodes[i];
          const b = nodes[j];
          let dx = b.x - a.x;
          let dy = b.y - a.y;
          let dist = Math.sqrt(dx * dx + dy * dy) || 1;

          const minDist = 80;
          if (dist < minDist * 2) {
            const force = (minDist * 2 - dist) * 0.05;
            dx /= dist;
            dy /= dist;
            a.vx -= dx * force;
            a.vy -= dy * force;
            b.vx += dx * force;
            b.vy += dy * force;
          }
        }
      }

      // Link forces
      links.forEach(link => {
        const source = nodeMap.get(link.source);
        const target = nodeMap.get(link.target);
        if (!source || !target) return;

        let dx = target.x - source.x;
        let dy = target.y - source.y;
        let dist = Math.sqrt(dx * dx + dy * dy) || 1;

        const targetDist = 150;
        const force = (dist - targetDist) * 0.01;
        dx /= dist;
        dy /= dist;

        source.vx += dx * force;
        source.vy += dy * force;
        target.vx -= dx * force;
        target.vy -= dy * force;
      });

      // Apply velocity
      nodes.forEach(node => {
        node.vx *= velocityDecay;
        node.vy *= velocityDecay;
        node.x += node.vx * currentAlpha;
        node.y += node.vy * currentAlpha;

        // Keep in bounds
        const margin = 50;
        node.x = Math.max(margin, Math.min(width - margin, node.x));
        node.y = Math.max(margin, Math.min(height - margin, node.y));
      });

      currentAlpha *= (1 - alphaDecay);
      return true;
    }

    return { tick, nodes, links, nodeMap };
  }

  // Render functions
  function renderPackageView() {
    const linksGroup = g.querySelector('.links');
    const nodesGroup = g.querySelector('.nodes');
    linksGroup.innerHTML = '';
    nodesGroup.innerHTML = '';

    // Combine packages and apps as nodes
    const allNodes = [
      ...packages.map(p => ({ ...p, type: 'package' })),
      ...apps.map(a => ({ ...a, type: 'app', loc: 5000 }))
    ];

    // Filter deps to only include existing nodes
    const nodeIds = new Set(allNodes.map(n => n.id));
    const validDeps = packageDeps.filter(d => nodeIds.has(d.from) && nodeIds.has(d.to));

    simulation = createSimulation(allNodes, validDeps);

    // Render links
    validDeps.forEach(dep => {
      const line = createSVGElement('line', {
        class: 'link',
        'data-source': dep.from,
        'data-target': dep.to,
        'stroke-width': Math.max(1, Math.min(4, dep.strength / 20)),
        'marker-end': 'url(#arrowhead)'
      });
      linksGroup.appendChild(line);
    });

    // Render nodes
    allNodes.forEach(node => {
      const group = createSVGElement('g', {
        class: 'node',
        'data-id': node.id
      });

      const radius = node.type === 'package'
        ? Math.max(15, Math.min(40, Math.sqrt(node.loc) / 10))
        : 12;

      const circle = createSVGElement('circle', {
        class: 'node-circle',
        r: radius,
        fill: langColors[node.lang] || langColors.mixed
      });
      group.appendChild(circle);

      const label = createSVGElement('text', {
        class: 'node-label',
        y: radius + 14
      });
      label.textContent = node.name.replace('kagami_', '').replace('kagami-', '').replace('app_', '');
      group.appendChild(label);

      // Events
      group.addEventListener('mouseenter', (e) => showTooltip(e, node));
      group.addEventListener('mouseleave', hideTooltip);
      group.addEventListener('click', () => selectNode(node));

      nodesGroup.appendChild(group);
    });

    // Animation loop
    function animate() {
      if (!simulation.tick()) return;

      // Update positions
      simulation.nodes.forEach(node => {
        const group = nodesGroup.querySelector(`[data-id="${node.id}"]`);
        if (group) {
          group.setAttribute('transform', `translate(${node.x}, ${node.y})`);
        }
      });

      // Update links
      validDeps.forEach(dep => {
        const source = simulation.nodeMap.get(dep.from);
        const target = simulation.nodeMap.get(dep.to);
        if (!source || !target) return;

        const line = linksGroup.querySelector(`[data-source="${dep.from}"][data-target="${dep.to}"]`);
        if (line) {
          line.setAttribute('x1', source.x);
          line.setAttribute('y1', source.y);
          line.setAttribute('x2', target.x);
          line.setAttribute('y2', target.y);
        }
      });

      requestAnimationFrame(animate);
    }
    requestAnimationFrame(animate);

    // Populate sidebar
    renderPackageList();
  }

  function renderCoreView() {
    const linksGroup = g.querySelector('.links');
    const nodesGroup = g.querySelector('.nodes');
    linksGroup.innerHTML = '';
    nodesGroup.innerHTML = '';

    const nodes = coreModules.map(m => ({ ...m, type: 'module' }));
    const nodeIds = new Set(nodes.map(n => n.id));
    const validDeps = coreDeps.filter(d => nodeIds.has(d.from) && nodeIds.has(d.to));

    simulation = createSimulation(nodes, validDeps);

    // Render links
    validDeps.forEach(dep => {
      const line = createSVGElement('line', {
        class: 'link',
        'data-source': dep.from,
        'data-target': dep.to,
        'stroke-width': Math.max(1, Math.min(3, dep.strength / 8)),
        'marker-end': 'url(#arrowhead)'
      });
      linksGroup.appendChild(line);
    });

    // Render nodes with module-specific styling
    const moduleColors = {
      world_model: '#6366f1',
      active_inference: '#8b5cf6',
      safety: '#ef4444',
      unified_agents: '#22c55e',
      effectors: '#f59e0b',
      symbiote: '#ec4899',
      training: '#14b8a6',
      services: '#64748b',
      default: '#3572A5'
    };

    nodes.forEach(node => {
      const group = createSVGElement('g', {
        class: 'node',
        'data-id': node.id
      });

      const radius = Math.max(12, Math.min(35, Math.sqrt(node.files) * 4));
      const color = moduleColors[node.id] || moduleColors.default;

      const circle = createSVGElement('circle', {
        class: 'node-circle',
        r: radius,
        fill: color
      });
      group.appendChild(circle);

      const label = createSVGElement('text', {
        class: 'node-label',
        y: radius + 12
      });
      label.textContent = node.name;
      group.appendChild(label);

      group.addEventListener('mouseenter', (e) => showTooltip(e, node));
      group.addEventListener('mouseleave', hideTooltip);
      group.addEventListener('click', () => selectNode(node));

      nodesGroup.appendChild(group);
    });

    // Animation
    function animate() {
      if (!simulation.tick()) return;

      simulation.nodes.forEach(node => {
        const group = nodesGroup.querySelector(`[data-id="${node.id}"]`);
        if (group) {
          group.setAttribute('transform', `translate(${node.x}, ${node.y})`);
        }
      });

      validDeps.forEach(dep => {
        const source = simulation.nodeMap.get(dep.from);
        const target = simulation.nodeMap.get(dep.to);
        if (!source || !target) return;

        const line = linksGroup.querySelector(`[data-source="${dep.from}"][data-target="${dep.to}"]`);
        if (line) {
          line.setAttribute('x1', source.x);
          line.setAttribute('y1', source.y);
          line.setAttribute('x2', target.x);
          line.setAttribute('y2', target.y);
        }
      });

      requestAnimationFrame(animate);
    }
    requestAnimationFrame(animate);

    renderCoreModuleList();
  }

  function renderFlowView() {
    const linksGroup = g.querySelector('.links');
    const nodesGroup = g.querySelector('.nodes');
    linksGroup.innerHTML = '';
    nodesGroup.innerHTML = '';

    // Create flow nodes
    const flowNodes = [
      { id: 'input', name: 'User Input', x: 100, y: height / 2, type: 'external' },
      { id: 'unified_agents', name: 'Agents', x: 250, y: height / 2, type: 'core' },
      { id: 'world_model', name: 'World Model', x: 400, y: height / 2 - 80, type: 'core' },
      { id: 'active_inference', name: 'Active Inference', x: 550, y: height / 2 - 40, type: 'core' },
      { id: 'safety', name: 'Safety', x: 700, y: height / 2, type: 'safety' },
      { id: 'effectors', name: 'Effectors', x: 850, y: height / 2, type: 'core' },
      { id: 'output', name: 'External World', x: 1000, y: height / 2, type: 'external' },
      { id: 'symbiote', name: 'Symbiote', x: 400, y: height / 2 + 100, type: 'core' },
      { id: 'memory', name: 'Memory', x: 250, y: height / 2 + 100, type: 'core' }
    ];

    const flowLinks = [
      { source: 'input', target: 'unified_agents' },
      { source: 'unified_agents', target: 'world_model' },
      { source: 'world_model', target: 'active_inference' },
      { source: 'active_inference', target: 'safety' },
      { source: 'safety', target: 'effectors' },
      { source: 'effectors', target: 'output' },
      { source: 'output', target: 'world_model', curved: true },
      { source: 'memory', target: 'symbiote' },
      { source: 'symbiote', target: 'active_inference' }
    ];

    const nodeMap = new Map();
    flowNodes.forEach(n => nodeMap.set(n.id, n));

    // Render links
    flowLinks.forEach(link => {
      const source = nodeMap.get(link.source);
      const target = nodeMap.get(link.target);
      if (!source || !target) return;

      if (link.curved) {
        // Curved path for feedback loop
        const path = createSVGElement('path', {
          class: 'link',
          d: `M${source.x},${source.y} C${source.x},${source.y - 150} ${target.x},${target.y - 150} ${target.x},${target.y}`,
          'stroke-dasharray': '5,5',
          'marker-end': 'url(#arrowhead)'
        });
        linksGroup.appendChild(path);
      } else {
        const line = createSVGElement('line', {
          class: 'link',
          x1: source.x,
          y1: source.y,
          x2: target.x,
          y2: target.y,
          'marker-end': 'url(#arrowhead)'
        });
        linksGroup.appendChild(line);
      }
    });

    // Render nodes
    const typeColors = {
      external: '#64748b',
      core: '#6366f1',
      safety: '#ef4444'
    };

    flowNodes.forEach(node => {
      const group = createSVGElement('g', {
        class: 'node',
        'data-id': node.id,
        transform: `translate(${node.x}, ${node.y})`
      });

      const rect = createSVGElement('rect', {
        class: 'node-rect',
        x: -50,
        y: -25,
        width: 100,
        height: 50,
        rx: 8,
        fill: typeColors[node.type],
        stroke: 'var(--bg-primary)',
        'stroke-width': 2
      });
      group.appendChild(rect);

      const label = createSVGElement('text', {
        class: 'node-label',
        y: 4,
        fill: 'white',
        'font-size': '12px'
      });
      label.textContent = node.name;
      group.appendChild(label);

      group.addEventListener('click', () => {
        const coreModule = coreModules.find(m => m.id === node.id);
        if (coreModule) selectNode(coreModule);
      });

      nodesGroup.appendChild(group);
    });

    // Add legend
    renderFlowLegend();
  }

  function renderFlowLegend() {
    packageList.innerHTML = `
      <div class="legend-item"><span class="legend-dot" style="background: #64748b"></span> External</div>
      <div class="legend-item"><span class="legend-dot" style="background: #6366f1"></span> Core Module</div>
      <div class="legend-item"><span class="legend-dot" style="background: #ef4444"></span> Safety Layer</div>
      <div style="margin-top: 16px; font-size: 11px; color: var(--text-muted);">
        Dashed lines indicate feedback loops
      </div>
    `;
  }

  function renderPackageList() {
    packageList.innerHTML = '';
    packages.forEach(pkg => {
      const item = document.createElement('div');
      item.className = 'package-item';
      item.innerHTML = `
        <span class="package-dot" style="background: ${langColors[pkg.lang]}"></span>
        <span class="package-name">${pkg.name.replace('kagami_', '').replace('kagami-', '')}</span>
        <span class="package-count">${pkg.modules}</span>
      `;
      item.addEventListener('click', () => {
        document.querySelectorAll('.package-item').forEach(i => i.classList.remove('active'));
        item.classList.add('active');
        selectNode(pkg);
      });
      packageList.appendChild(item);
    });
  }

  function renderCoreModuleList() {
    packageList.innerHTML = '';
    coreModules.forEach(mod => {
      const item = document.createElement('div');
      item.className = 'package-item';
      item.innerHTML = `
        <span class="package-dot" style="background: #6366f1"></span>
        <span class="package-name">${mod.name}</span>
        <span class="package-count">${mod.files}</span>
      `;
      item.addEventListener('click', () => {
        document.querySelectorAll('.package-item').forEach(i => i.classList.remove('active'));
        item.classList.add('active');
        selectNode(mod);
      });
      packageList.appendChild(item);
    });
  }

  // Tooltip
  function showTooltip(e, node) {
    const rect = svg.getBoundingClientRect();

    let statsHtml = '';
    if (node.loc) {
      statsHtml = `
        <div class="tooltip-stats">
          <div class="tooltip-stat"><strong>${(node.loc / 1000).toFixed(1)}K</strong> LOC</div>
          <div class="tooltip-stat"><strong>${node.modules || node.files || '?'}</strong> ${node.modules ? 'modules' : 'files'}</div>
        </div>
      `;
    }

    tooltip.innerHTML = `
      <div class="tooltip-title">${node.name}</div>
      <div class="tooltip-desc">${node.desc || ''}</div>
      ${statsHtml}
    `;

    tooltip.style.left = `${e.clientX - rect.left + 15}px`;
    tooltip.style.top = `${e.clientY - rect.top + 15}px`;
    tooltip.classList.add('visible');
  }

  function hideTooltip() {
    tooltip.classList.remove('visible');
  }

  // Detail panel
  function selectNode(node) {
    selectedNode = node;

    // Update visual selection
    document.querySelectorAll('.node').forEach(n => n.classList.remove('selected'));
    const nodeEl = document.querySelector(`.node[data-id="${node.id}"]`);
    if (nodeEl) nodeEl.classList.add('selected');

    // Highlight connected links
    document.querySelectorAll('.link').forEach(link => {
      link.classList.remove('highlighted');
      const source = link.getAttribute('data-source');
      const target = link.getAttribute('data-target');
      if (source === node.id || target === node.id) {
        link.classList.add('highlighted');
      }
    });

    // Show detail panel
    detailTitle.textContent = node.name;

    // Find dependencies
    const deps = currentView === 'packages' ? packageDeps : coreDeps;
    const outgoing = deps.filter(d => d.from === node.id);
    const incoming = deps.filter(d => d.to === node.id);

    detailContent.innerHTML = `
      <div class="detail-section">
        <div class="detail-section-title">Info</div>
        ${node.desc ? `<div class="detail-row"><span class="detail-label">Description</span></div><p style="font-size: 12px; color: var(--text-secondary); margin: 8px 0;">${node.desc}</p>` : ''}
        ${node.lang ? `<div class="detail-row"><span class="detail-label">Language</span><span class="detail-value">${node.lang}</span></div>` : ''}
        ${node.loc ? `<div class="detail-row"><span class="detail-label">Lines of Code</span><span class="detail-value">${(node.loc / 1000).toFixed(1)}K</span></div>` : ''}
        ${node.modules ? `<div class="detail-row"><span class="detail-label">Modules</span><span class="detail-value">${node.modules}</span></div>` : ''}
        ${node.files ? `<div class="detail-row"><span class="detail-label">Files</span><span class="detail-value">${node.files}</span></div>` : ''}
      </div>

      ${outgoing.length > 0 ? `
        <div class="detail-section">
          <div class="detail-section-title">Depends On (${outgoing.length})</div>
          <div class="detail-deps">
            ${outgoing.map(d => `
              <div class="detail-dep" data-id="${d.to}">
                <span class="detail-dep-arrow">→</span>
                ${d.to.replace('kagami_', '').replace('kagami-', '')}
                <span class="detail-dep-count">${d.strength} refs</span>
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
              <div class="detail-dep" data-id="${d.from}">
                <span class="detail-dep-arrow">←</span>
                ${d.from.replace('kagami_', '').replace('kagami-', '')}
                <span class="detail-dep-count">${d.strength} refs</span>
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
          ? [...packages, ...apps]
          : coreModules;
        const targetNode = allNodes.find(n => n.id === targetId);
        if (targetNode) selectNode(targetNode);
      });
    });

    detailPanel.classList.add('open');
  }

  function closeDetail() {
    detailPanel.classList.remove('open');
    selectedNode = null;
    document.querySelectorAll('.node').forEach(n => n.classList.remove('selected'));
    document.querySelectorAll('.link').forEach(l => l.classList.remove('highlighted'));
  }

  // View switching
  function switchView(view) {
    currentView = view;
    transform = { x: 0, y: 0, k: 1 };

    document.querySelectorAll('.nav-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.view === view);
    });

    closeDetail();

    switch (view) {
      case 'packages':
        renderPackageView();
        break;
      case 'core':
        renderCoreView();
        break;
      case 'flow':
        renderFlowView();
        break;
    }
  }

  // Event listeners
  document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.addEventListener('click', () => switchView(btn.dataset.view));
  });

  detailClose.addEventListener('click', closeDetail);

  // Handle resize
  let resizeTimeout;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(() => {
      initSVG();
      switchView(currentView);
    }, 200);
  });

  // Initialize
  initSVG();
  switchView('packages');

})();
