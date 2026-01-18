/**
 * Main Entry Point
 * Initializes application and coordinates modules
 */

import { CONFIG, THEME, applyTheme, getCategoryColor, getCategoryHSL } from './config.js';
import { initI18n, t, setLang, getLang, formatNumber, onLangChange } from './i18n.js';
import { loadData, store, findSimilarFiles, searchFiles, getFileRelationships, getCategoryStats } from './data.js';
import { SpatialGrid2D, ProjectionCache } from './spatial.js';

// ═══════════════════════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════════════════════

const state = {
  // View mode
  view: 'treemap', // 'treemap' | '3d'
  
  // Treemap state
  treemap: {
    path: [],
    selected: null,
    hovered: null,
    spatialGrid: null,
  },
  
  // 3D state
  semantic: {
    camera: {
      rotX: CONFIG.camera.defaultRotX,
      rotY: CONFIG.camera.defaultRotY,
      zoom: CONFIG.camera.defaultZoom,
    },
    dragging: false,
    lastMouse: { x: 0, y: 0 },
    hovered: null,
    selected: null,
    autoRotate: false,
    layers: {
      imports: true,
      exports: false,
      labels: true,
      grid: false,
    },
  },
  
  // Search
  searchQuery: '',
  searchResults: [],
  
  // Filters
  categoryFilter: null,
  
  // Progressive disclosure
  hoverTimer: null,
  tooltipExpanded: false,
  highlightedRelated: [],
};

// Canvas contexts
let treemapCanvas, treemapCtx;
let semanticCanvas, semanticCtx;

// Animation frame IDs
let treemapAnimationId = null;
let semanticAnimationId = null;

// Projection cache for 3D
const projectionCache = new ProjectionCache();

// ═══════════════════════════════════════════════════════════════════════════════
// INITIALIZATION
// ═══════════════════════════════════════════════════════════════════════════════

export async function init() {
  console.log(`Code Map v${CONFIG.version} initializing...`);
  
  // Apply theme
  applyTheme();
  
  // Initialize i18n
  initI18n();
  
  // Set up canvases
  setupCanvases();
  
  // Load data
  try {
    await loadData();
    console.log(`Loaded ${store.files.length} files`);
    
    // Update stats UI
    updateStats();
    
    // Build UI
    buildLegend();
    
    // Set up event listeners
    setupEventListeners();
    
    // Start rendering
    startRenderLoop();
    
    // Hide loading state
    document.body.classList.add('loaded');
    
  } catch (error) {
    console.error('Failed to initialize:', error);
    showError(error.message);
  }
}

function setupCanvases() {
  treemapCanvas = document.getElementById('treemap-canvas');
  semanticCanvas = document.getElementById('semantic-canvas');
  
  if (treemapCanvas) {
    treemapCtx = treemapCanvas.getContext('2d');
    resizeCanvas(treemapCanvas);
  }
  
  if (semanticCanvas) {
    semanticCtx = semanticCanvas.getContext('2d');
    resizeCanvas(semanticCanvas);
  }
}

function resizeCanvas(canvas) {
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);
}

// ═══════════════════════════════════════════════════════════════════════════════
// RENDERING
// ═══════════════════════════════════════════════════════════════════════════════

function startRenderLoop() {
  if (state.view === 'treemap') {
    renderTreemap();
  } else {
    renderSemantic();
  }
}

function renderTreemap() {
  if (!treemapCtx || !store.tree) return;
  
  const w = treemapCanvas.width / (window.devicePixelRatio || 1);
  const h = treemapCanvas.height / (window.devicePixelRatio || 1);
  
  // Clear
  treemapCtx.fillStyle = THEME.colors.void;
  treemapCtx.fillRect(0, 0, w, h);
  
  // Get current node based on path
  let currentNode = store.tree;
  for (const segment of state.treemap.path) {
    currentNode = currentNode.children?.[segment];
    if (!currentNode) break;
  }
  
  if (!currentNode) return;
  
  // Build spatial index
  state.treemap.spatialGrid = new SpatialGrid2D(w, h);
  
  // Layout and render
  const cells = layoutTreemap(currentNode, 0, 0, w, h);
  
  for (const cell of cells) {
    renderTreemapCell(cell);
    state.treemap.spatialGrid.insert(cell.node, cell.x, cell.y, cell.w, cell.h);
  }
  
  // Schedule next frame if needed
  treemapAnimationId = requestAnimationFrame(renderTreemap);
}

function layoutTreemap(node, x, y, w, h) {
  if (w < CONFIG.treemap.minCellSize || h < CONFIG.treemap.minCellSize) return [];
  
  const children = Object.values(node.children || {});
  if (children.length === 0) return [];
  
  // Sort by size
  children.sort((a, b) => (b.lines || 0) - (a.lines || 0));
  
  const totalLines = children.reduce((sum, c) => sum + (c.lines || 0), 0);
  if (totalLines === 0) return [];
  
  const cells = [];
  const pad = CONFIG.treemap.padding;
  
  let currentX = x + pad;
  let currentY = y + pad;
  let remainingW = w - pad * 2;
  let remainingH = h - pad * 2;
  
  // Simple squarified layout
  for (const child of children) {
    const ratio = (child.lines || 0) / totalLines;
    
    let cellW, cellH;
    if (remainingW > remainingH) {
      cellW = remainingW * ratio;
      cellH = remainingH;
      cells.push({ node: child, x: currentX, y: currentY, w: cellW - pad, h: cellH - pad });
      currentX += cellW;
      remainingW -= cellW;
    } else {
      cellW = remainingW;
      cellH = remainingH * ratio;
      cells.push({ node: child, x: currentX, y: currentY, w: cellW - pad, h: cellH - pad });
      currentY += cellH;
      remainingH -= cellH;
    }
  }
  
  return cells;
}

function renderTreemapCell(cell) {
  const { node, x, y, w, h } = cell;
  const ctx = treemapCtx;
  
  const isHovered = state.treemap.hovered === node;
  const isSelected = state.treemap.selected === node;
  const category = node.file?.category || 'Other';
  
  // Background
  const baseColor = getCategoryHSL(category);
  const alpha = node.isFile ? 0.8 : 0.4;
  ctx.fillStyle = `hsla(${baseColor.h}, ${baseColor.s}%, ${baseColor.l}%, ${alpha})`;
  
  // Rounded rect
  const r = Math.min(CONFIG.treemap.cornerRadius, w / 4, h / 4);
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r);
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
  ctx.fill();
  
  // Border for hover/selected
  if (isHovered || isSelected) {
    ctx.strokeStyle = isSelected ? THEME.colors.gold : THEME.colors.textPrimary;
    ctx.lineWidth = isSelected ? 2 : 1;
    ctx.stroke();
  }
  
  // Label
  if (w > CONFIG.treemap.labelMinSize && h > 20) {
    ctx.fillStyle = THEME.colors.textPrimary;
    ctx.font = `12px ${THEME.fonts.sans}`;
    ctx.textAlign = 'left';
    ctx.textBaseline = 'top';
    
    const label = node.name.length > 20 ? node.name.slice(0, 18) + '...' : node.name;
    ctx.fillText(label, x + 8, y + 8);
    
    // Line count
    if (h > 40) {
      ctx.fillStyle = THEME.colors.textTertiary;
      ctx.font = `10px ${THEME.fonts.mono}`;
      ctx.fillText(formatNumber(node.lines) + ' lines', x + 8, y + 24);
    }
  }
}

function renderSemantic() {
  if (!semanticCtx || !store.files.length) return;
  
  const w = semanticCanvas.width / (window.devicePixelRatio || 1);
  const h = semanticCanvas.height / (window.devicePixelRatio || 1);
  
  // Clear with gradient
  const grad = semanticCtx.createRadialGradient(w/2, h/2, 0, w/2, h/2, Math.max(w, h));
  grad.addColorStop(0, '#0a0a14');
  grad.addColorStop(1, '#020206');
  semanticCtx.fillStyle = grad;
  semanticCtx.fillRect(0, 0, w, h);
  
  // Filter files
  let files = store.files.filter(f => f.x !== undefined && f.y !== undefined && f.z !== undefined);
  if (state.categoryFilter) {
    files = files.filter(f => f.category === state.categoryFilter);
  }
  if (state.searchQuery) {
    const q = state.searchQuery.toLowerCase();
    files = files.filter(f => f.path.toLowerCase().includes(q) || f.name.toLowerCase().includes(q));
  }
  
  // Project to 2D
  const cx = w / 2;
  const cy = h / 2;
  const scale = Math.min(w, h) * 0.35 * state.semantic.camera.zoom;
  
  const projected = files.map(f => {
    const p = project3D(f.x, f.y, f.z, cx, cy, scale);
    return { file: f, ...p };
  }).sort((a, b) => a.z - b.z);
  
  // Draw connections for selected file
  if (state.semantic.selected) {
    drawConnections(projected);
  }
  
  // Draw nodes
  for (const p of projected) {
    drawNode(p);
  }
  
  // Auto rotate
  if (state.semantic.autoRotate && !state.semantic.dragging) {
    state.semantic.camera.rotY += CONFIG.camera.autoRotateSpeed;
    projectionCache.invalidate();
  }
  
  semanticAnimationId = requestAnimationFrame(renderSemantic);
}

function project3D(x, y, z, cx, cy, scale) {
  const cam = state.semantic.camera;
  
  // Center coordinates
  const px = (x - 0.5) * 2;
  const py = (y - 0.5) * 2;
  const pz = (z - 0.5) * 2;
  
  // Rotate around Y
  const cosY = Math.cos(cam.rotY);
  const sinY = Math.sin(cam.rotY);
  const x1 = px * cosY - pz * sinY;
  const z1 = px * sinY + pz * cosY;
  
  // Rotate around X
  const cosX = Math.cos(cam.rotX);
  const sinX = Math.sin(cam.rotX);
  const y1 = py * cosX - z1 * sinX;
  const z2 = py * sinX + z1 * cosX;
  
  // Perspective
  const perspective = CONFIG.camera.fov / (CONFIG.camera.fov + (z2 + CONFIG.camera.distance) * scale * 0.8);
  
  return {
    x: cx + x1 * scale * perspective,
    y: cy + y1 * scale * perspective,
    z: z2,
    scale: perspective,
  };
}

function drawNode(p) {
  const ctx = semanticCtx;
  const { file, x, y, scale } = p;
  
  const isHovered = state.semantic.hovered === file;
  const isSelected = state.semantic.selected === file;
  const isHighlighted = state.highlightedRelated.includes(file);
  
  const baseSize = CONFIG.nodes.minSize + Math.log1p(file.lines) * CONFIG.nodes.sizeScale;
  const size = baseSize * scale * (isHovered ? 1.5 : 1) * (isSelected ? 1.8 : 1);
  const alpha = 0.3 + scale * 0.7;
  
  // Glow for highlighted/selected
  if (isHighlighted || isSelected || isHovered) {
    const glowSize = size * (isSelected ? 4 : 3);
    const glow = ctx.createRadialGradient(x, y, 0, x, y, glowSize);
    glow.addColorStop(0, getCategoryColor(file.category, 0.5));
    glow.addColorStop(1, 'transparent');
    ctx.fillStyle = glow;
    ctx.beginPath();
    ctx.arc(x, y, glowSize, 0, Math.PI * 2);
    ctx.fill();
  }
  
  // Node
  ctx.beginPath();
  ctx.arc(x, y, size, 0, Math.PI * 2);
  ctx.fillStyle = getCategoryColor(file.category, alpha);
  ctx.fill();
  
  // Bright core
  if (size > 3) {
    ctx.beginPath();
    ctx.arc(x, y, size * 0.4, 0, Math.PI * 2);
    ctx.fillStyle = `rgba(255,255,255,${alpha * 0.8})`;
    ctx.fill();
  }
}

function drawConnections(projected) {
  const ctx = semanticCtx;
  const selected = state.semantic.selected;
  if (!selected) return;
  
  const selectedProj = projected.find(p => p.file === selected);
  if (!selectedProj) return;
  
  const similar = findSimilarFiles(selected, 8);
  
  for (const { file, score } of similar) {
    const targetProj = projected.find(p => p.file === file);
    if (!targetProj) continue;
    
    ctx.beginPath();
    ctx.moveTo(selectedProj.x, selectedProj.y);
    ctx.lineTo(targetProj.x, targetProj.y);
    ctx.strokeStyle = `rgba(240, 200, 96, ${0.1 + score * 0.4})`;
    ctx.lineWidth = 1 + score * 2;
    ctx.stroke();
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// EVENT HANDLERS
// ═══════════════════════════════════════════════════════════════════════════════

function setupEventListeners() {
  // Window resize
  window.addEventListener('resize', debounce(() => {
    if (treemapCanvas) resizeCanvas(treemapCanvas);
    if (semanticCanvas) resizeCanvas(semanticCanvas);
    projectionCache.invalidate();
  }, 100));
  
  // Treemap interactions
  if (treemapCanvas) {
    treemapCanvas.addEventListener('mousemove', onTreemapMouseMove);
    treemapCanvas.addEventListener('click', onTreemapClick);
    treemapCanvas.addEventListener('mouseleave', () => {
      state.treemap.hovered = null;
      hideTooltip();
    });
  }
  
  // 3D interactions
  if (semanticCanvas) {
    semanticCanvas.addEventListener('mousedown', onSemanticMouseDown);
    semanticCanvas.addEventListener('mousemove', onSemanticMouseMove);
    semanticCanvas.addEventListener('mouseup', onSemanticMouseUp);
    semanticCanvas.addEventListener('mouseleave', onSemanticMouseLeave);
    semanticCanvas.addEventListener('wheel', onSemanticWheel, { passive: false });
    semanticCanvas.addEventListener('click', onSemanticClick);
  }
  
  // Search
  const searchInput = document.getElementById('search');
  if (searchInput) {
    searchInput.addEventListener('input', debounce(onSearch, 150));
  }
  
  // Keyboard
  document.addEventListener('keydown', onKeyDown);
  
  // Language change
  onLangChange(() => {
    buildLegend();
    updateStats();
  });
}

function onTreemapMouseMove(e) {
  const rect = treemapCanvas.getBoundingClientRect();
  const x = e.clientX - rect.left;
  const y = e.clientY - rect.top;
  
  const nodes = state.treemap.spatialGrid?.queryPoint(x, y) || [];
  state.treemap.hovered = nodes[nodes.length - 1] || null;
  
  if (state.treemap.hovered) {
    showTooltip(state.treemap.hovered, e.clientX, e.clientY);
    treemapCanvas.style.cursor = 'pointer';
  } else {
    hideTooltip();
    treemapCanvas.style.cursor = 'default';
  }
}

function onTreemapClick(e) {
  if (state.treemap.hovered) {
    if (state.treemap.hovered.isFile) {
      selectFile(state.treemap.hovered.file);
    } else {
      // Navigate into folder
      state.treemap.path.push(state.treemap.hovered.name);
    }
  }
}

function onSemanticMouseDown(e) {
  state.semantic.dragging = true;
  state.semantic.lastMouse = { x: e.clientX, y: e.clientY };
  semanticCanvas.style.cursor = 'grabbing';
}

function onSemanticMouseMove(e) {
  if (state.semantic.dragging) {
    const dx = e.clientX - state.semantic.lastMouse.x;
    const dy = e.clientY - state.semantic.lastMouse.y;
    
    state.semantic.camera.rotY += dx * CONFIG.camera.rotationSpeed;
    state.semantic.camera.rotX += dy * CONFIG.camera.rotationSpeed;
    state.semantic.camera.rotX = Math.max(-Math.PI/2, Math.min(Math.PI/2, state.semantic.camera.rotX));
    
    state.semantic.lastMouse = { x: e.clientX, y: e.clientY };
    projectionCache.invalidate();
  } else {
    // Hit test
    const rect = semanticCanvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    
    state.semantic.hovered = findNodeAtPosition(x, y);
    
    if (state.semantic.hovered) {
      showTooltip(state.semantic.hovered, e.clientX, e.clientY);
      semanticCanvas.style.cursor = 'pointer';
      startHoverTimer(state.semantic.hovered);
    } else {
      hideTooltip();
      semanticCanvas.style.cursor = 'grab';
      clearHoverTimer();
    }
  }
}

function onSemanticMouseUp() {
  state.semantic.dragging = false;
  semanticCanvas.style.cursor = state.semantic.hovered ? 'pointer' : 'grab';
}

function onSemanticMouseLeave() {
  state.semantic.dragging = false;
  state.semantic.hovered = null;
  hideTooltip();
  clearHoverTimer();
}

function onSemanticWheel(e) {
  e.preventDefault();
  const delta = e.deltaY > 0 ? 0.9 : 1.1;
  state.semantic.camera.zoom = Math.max(
    CONFIG.camera.minZoom,
    Math.min(CONFIG.camera.maxZoom, state.semantic.camera.zoom * delta)
  );
  projectionCache.invalidate();
}

function onSemanticClick(e) {
  if (!state.semantic.dragging && state.semantic.hovered) {
    selectFile(state.semantic.hovered);
  }
}

function onSearch(e) {
  state.searchQuery = e.target.value;
  state.searchResults = searchFiles(state.searchQuery);
  // Update search results UI
}

function onKeyDown(e) {
  if (e.key === 'Escape') {
    state.treemap.selected = null;
    state.semantic.selected = null;
    state.highlightedRelated = [];
    hideSidePanel();
  }
  
  if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
    e.preventDefault();
    document.getElementById('search')?.focus();
  }
  
  // Backspace to go up in treemap
  if (e.key === 'Backspace' && state.view === 'treemap' && state.treemap.path.length > 0) {
    e.preventDefault();
    state.treemap.path.pop();
  }
}

function findNodeAtPosition(mx, my) {
  const files = store.files.filter(f => f.x !== undefined);
  const w = semanticCanvas.width / (window.devicePixelRatio || 1);
  const h = semanticCanvas.height / (window.devicePixelRatio || 1);
  const cx = w / 2;
  const cy = h / 2;
  const scale = Math.min(w, h) * 0.35 * state.semantic.camera.zoom;
  
  let closest = null;
  let closestDist = 30;
  
  for (const f of files) {
    const p = project3D(f.x, f.y, f.z, cx, cy, scale);
    const dist = Math.hypot(p.x - mx, p.y - my);
    if (dist < closestDist) {
      closestDist = dist;
      closest = f;
    }
  }
  
  return closest;
}

// ═══════════════════════════════════════════════════════════════════════════════
// UI HELPERS
// ═══════════════════════════════════════════════════════════════════════════════

function updateStats() {
  const stats = store.stats;
  if (!stats) return;
  
  document.getElementById('file-count')?.textContent && 
    (document.getElementById('file-count').textContent = formatNumber(stats.totalFiles));
  document.getElementById('line-count')?.textContent && 
    (document.getElementById('line-count').textContent = formatNumber(stats.totalLines));
  document.getElementById('cluster-count')?.textContent && 
    (document.getElementById('cluster-count').textContent = stats.clusters);
}

function buildLegend() {
  const legend = document.getElementById('legend');
  if (!legend) return;
  
  const stats = getCategoryStats().slice(0, 10);
  
  legend.innerHTML = `
    <div class="legend-title" data-i18n="categories">${t('categories')}</div>
    ${stats.map(({ name, count }) => `
      <div class="legend-item ${state.categoryFilter === name ? 'active' : ''}" data-category="${name}">
        <div class="legend-dot" style="background: ${getCategoryColor(name)}"></div>
        <span class="legend-name">${name}</span>
        <span class="legend-count">${count}</span>
      </div>
    `).join('')}
  `;
  
  legend.querySelectorAll('.legend-item').forEach(item => {
    item.addEventListener('click', () => {
      const cat = item.dataset.category;
      state.categoryFilter = state.categoryFilter === cat ? null : cat;
      buildLegend();
    });
  });
}

function showTooltip(node, x, y) {
  const tooltip = document.getElementById('tooltip');
  if (!tooltip) return;
  
  const file = node.file || node;
  tooltip.innerHTML = `
    <div class="tooltip-name">${file.name || node.name}</div>
    <div class="tooltip-path">${file.path || node.path}</div>
    <div class="tooltip-meta">
      <span><strong>${formatNumber(file.lines || node.lines)}</strong> ${t('lines')}</span>
      <span class="tooltip-category" style="color: ${getCategoryColor(file.category || 'Other')}">${file.category || 'Folder'}</span>
    </div>
  `;
  
  tooltip.style.left = (x + 15) + 'px';
  tooltip.style.top = (y + 15) + 'px';
  tooltip.classList.add('visible');
}

function hideTooltip() {
  document.getElementById('tooltip')?.classList.remove('visible');
}

function selectFile(file) {
  state.treemap.selected = file;
  state.semantic.selected = file;
  state.highlightedRelated = findSimilarFiles(file, 8).map(s => s.file);
  showSidePanel(file);
}

function showSidePanel(file) {
  const panel = document.getElementById('side-panel');
  if (!panel) return;
  
  const similar = findSimilarFiles(file, 6);
  const relationships = getFileRelationships(file);
  
  panel.innerHTML = `
    <div class="panel-header">
      <div class="panel-title">${t('fileDetails')}</div>
      <div class="file-name">${file.name}</div>
      <div class="file-path">${file.path}</div>
    </div>
    <div class="panel-content">
      <div class="info-section">
        <div class="info-grid">
          <div class="info-item">
            <div class="info-label">${t('lines')}</div>
            <div class="info-value">${formatNumber(file.lines)}</div>
          </div>
          <div class="info-item">
            <div class="info-label">${t('cluster')}</div>
            <div class="info-value">#${file.cluster}</div>
          </div>
        </div>
      </div>
      
      ${file.summary ? `
      <div class="info-section">
        <div class="info-section-title">${t('summary')}</div>
        <p class="file-summary">${file.summary}</p>
      </div>
      ` : ''}
      
      ${similar.length ? `
      <div class="info-section">
        <div class="info-section-title">${t('similarFiles')}</div>
        ${similar.map(s => `
          <div class="similar-file" data-path="${s.file.path}">
            <div class="similar-score">${Math.round(s.score * 100)}</div>
            <div class="similar-info">
              <div class="similar-name">${s.file.name}</div>
              <div class="similar-reason">${s.primaryReason}</div>
            </div>
          </div>
        `).join('')}
      </div>
      ` : ''}
    </div>
  `;
  
  panel.classList.add('open');
  
  // Add click handlers for similar files
  panel.querySelectorAll('.similar-file').forEach(el => {
    el.addEventListener('click', () => {
      const file = store.files.find(f => f.path === el.dataset.path);
      if (file) selectFile(file);
    });
  });
}

function hideSidePanel() {
  document.getElementById('side-panel')?.classList.remove('open');
}

function showError(message) {
  const container = document.getElementById('app');
  if (container) {
    container.innerHTML = `<div class="error-message">${t('error')}: ${message}</div>`;
  }
}

// Progressive disclosure
function startHoverTimer(node) {
  clearHoverTimer();
  state.hoverTimer = setTimeout(() => {
    state.tooltipExpanded = true;
    // Expand tooltip with more details
  }, CONFIG.performance.expandDelayMs);
}

function clearHoverTimer() {
  if (state.hoverTimer) {
    clearTimeout(state.hoverTimer);
    state.hoverTimer = null;
  }
  state.tooltipExpanded = false;
}

// Utility
function debounce(fn, ms) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}

// Export for HTML access
window.CodeMap = {
  init,
  setLang,
  getLang,
  state,
  store,
};
