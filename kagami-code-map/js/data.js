/**
 * Data Loading & Processing
 * Handles codebase analysis JSON with caching and preprocessing
 */

import { SimilarityCache, SpatialOctree } from './spatial.js';
import { CONFIG } from './config.js';

// Global data store
export const store = {
  raw: null,           // Raw JSON data
  files: [],           // Processed file array
  tree: null,          // Tree structure for treemap
  stats: null,         // Statistics
  meta: null,          // Metadata
  octree: null,        // 3D spatial index
  importGraph: null,   // Import dependency graph
  similarityCache: new SimilarityCache(),
};

/**
 * Load codebase analysis data
 */
export async function loadData(url = 'codebase-analysis.json') {
  try {
    // Cache bust for development
    const bustUrl = `${url}?v=${Date.now()}`;
    const response = await fetch(bustUrl);
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    
    store.raw = await response.json();
    
    // Process data
    processFiles();
    buildTree();
    buildSpatialIndex();
    buildImportGraph();
    
    // Extract metadata
    store.meta = store.raw.meta || {};
    store.stats = store.raw.stats || computeStats();
    
    // Log 3D coordinate stats
    const withZ = store.files.filter(f => f.z !== undefined);
    if (withZ.length > 0) {
      const zValues = withZ.map(f => f.z);
      console.log(`3D Coordinates: ${withZ.length} files, z range: ${Math.min(...zValues).toFixed(3)} - ${Math.max(...zValues).toFixed(3)}`);
    }
    
    return store;
  } catch (error) {
    console.error('Failed to load data:', error);
    throw error;
  }
}

/**
 * Process raw files into normalized format
 */
function processFiles() {
  const raw = store.raw.files || [];
  
  store.files = raw.map((f, index) => ({
    // Identity
    id: f.path || `file-${index}`,
    path: f.path || '',
    name: f.name || f.path?.split('/').pop() || 'unknown',
    
    // Metrics
    lines: f.lines || 0,
    size: f.size || 0,
    
    // Classification
    category: f.category || 'Other',
    cluster: f.cluster ?? 0,
    importance: f.importance || 0,
    
    // 3D coordinates (normalized 0-1)
    x: f.x ?? Math.random(),
    y: f.y ?? Math.random(),
    z: f.z ?? Math.random(),
    
    // Relationships
    imports: f.imports || [],
    exports: f.exports || [],
    
    // AST data
    ast: f.ast || null,
    classes: f.ast?.classes || [],
    functions: f.ast?.functions || [],
    
    // AI-generated
    summary: f.summary || '',
    concepts: f.concepts || [],
    
    // Original reference
    _raw: f,
  }));
}

/**
 * Build hierarchical tree structure for treemap
 */
function buildTree() {
  const root = {
    name: store.meta?.name || 'codebase',
    path: '',
    lines: 0,
    isFile: false,
    children: {},
  };
  
  for (const file of store.files) {
    const parts = file.path.split('/');
    let current = root;
    
    // Navigate/create path
    for (let i = 0; i < parts.length - 1; i++) {
      const part = parts[i];
      if (!current.children[part]) {
        current.children[part] = {
          name: part,
          path: parts.slice(0, i + 1).join('/'),
          lines: 0,
          isFile: false,
          children: {},
        };
      }
      current = current.children[part];
    }
    
    // Add file
    const fileName = parts[parts.length - 1];
    current.children[fileName] = {
      name: fileName,
      path: file.path,
      lines: file.lines,
      isFile: true,
      file: file,
    };
  }
  
  // Calculate folder sizes
  function computeSizes(node) {
    if (node.isFile) {
      return node.lines;
    }
    
    let total = 0;
    for (const child of Object.values(node.children)) {
      total += computeSizes(child);
    }
    node.lines = total;
    return total;
  }
  
  computeSizes(root);
  store.tree = root;
}

/**
 * Build 3D spatial index for fast queries
 */
function buildSpatialIndex() {
  store.octree = new SpatialOctree();
  
  for (const file of store.files) {
    if (file.x !== undefined && file.y !== undefined && file.z !== undefined) {
      store.octree.insert(file, file.x, file.y, file.z);
    }
  }
}

/**
 * Build import dependency graph
 */
function buildImportGraph() {
  // Map of module name -> file
  const moduleMap = new Map();
  for (const file of store.files) {
    const moduleName = file.path.replace(/\//g, '.').replace(/\.py$/, '');
    moduleMap.set(moduleName, file);
    moduleMap.set(file.name.replace(/\.py$/, ''), file);
  }
  
  // Build adjacency lists
  store.importGraph = {
    imports: new Map(),  // file -> files it imports
    importedBy: new Map(),  // file -> files that import it
  };
  
  for (const file of store.files) {
    const imports = [];
    const importedBy = [];
    
    for (const imp of file.imports) {
      const target = moduleMap.get(imp);
      if (target && target !== file) {
        imports.push(target);
      }
    }
    
    store.importGraph.imports.set(file.id, imports);
  }
  
  // Build reverse index
  for (const [fileId, imports] of store.importGraph.imports) {
    for (const target of imports) {
      if (!store.importGraph.importedBy.has(target.id)) {
        store.importGraph.importedBy.set(target.id, []);
      }
      const file = store.files.find(f => f.id === fileId);
      if (file) {
        store.importGraph.importedBy.get(target.id).push(file);
      }
    }
  }
}

/**
 * Compute statistics if not provided
 */
function computeStats() {
  const files = store.files;
  
  const categories = {};
  for (const f of files) {
    if (!categories[f.category]) {
      categories[f.category] = { count: 0, lines: 0 };
    }
    categories[f.category].count++;
    categories[f.category].lines += f.lines;
  }
  
  const clusters = new Set(files.map(f => f.cluster)).size;
  
  return {
    totalFiles: files.length,
    totalLines: files.reduce((sum, f) => sum + f.lines, 0),
    categories,
    clusters,
  };
}

/**
 * Find similar files using embedding distance
 */
export function findSimilarFiles(file, limit = 5) {
  if (!file) return [];
  
  // Check cache
  const cacheKey = file.id;
  const cached = store.similarityCache.get(cacheKey);
  if (cached) return cached.slice(0, limit);
  
  const results = [];
  
  for (const f of store.files) {
    if (f.id === file.id) continue;
    
    let score = 0;
    const signals = [];
    
    // 3D embedding distance
    const dist = Math.sqrt(
      (f.x - file.x) ** 2 +
      (f.y - file.y) ** 2 +
      (f.z - file.z) ** 2
    );
    const embScore = Math.max(0, 1 - dist * 1.5);
    if (embScore > 0.2) {
      score += embScore * 0.4;
      signals.push({ type: 'similar', weight: embScore });
    }
    
    // Same cluster
    if (f.cluster === file.cluster) {
      score += 0.2;
      signals.push({ type: 'cluster', weight: 0.2 });
    }
    
    // Import relationships
    const imports = store.importGraph.imports.get(file.id) || [];
    const importedBy = store.importGraph.importedBy.get(file.id) || [];
    
    if (imports.includes(f)) {
      score += 0.3;
      signals.push({ type: 'imports', weight: 0.3 });
    }
    if (importedBy.includes(f)) {
      score += 0.3;
      signals.push({ type: 'importedBy', weight: 0.3 });
    }
    
    // Shared imports
    const fImports = store.importGraph.imports.get(f.id) || [];
    const shared = imports.filter(i => fImports.includes(i)).length;
    if (shared > 0) {
      const sharedScore = Math.min(0.15, shared * 0.03);
      score += sharedScore;
      signals.push({ type: 'shared', weight: sharedScore, count: shared });
    }
    
    // Same category
    if (f.category === file.category) {
      score += 0.05;
    }
    
    if (score > 0.15) {
      results.push({
        file: f,
        score: Math.min(1, score),
        signals: signals.sort((a, b) => b.weight - a.weight),
        primaryReason: signals[0]?.type || 'similar',
      });
    }
  }
  
  const sorted = results.sort((a, b) => b.score - a.score).slice(0, 20);
  store.similarityCache.set(cacheKey, sorted);
  
  return sorted.slice(0, limit);
}

/**
 * Find files at 3D position
 */
export function findFilesNear(x, y, z, radius = 0.1) {
  if (!store.octree) return [];
  return store.octree.queryRadius(x, y, z, radius);
}

/**
 * Get file relationships
 */
export function getFileRelationships(file) {
  if (!file) return { imports: [], importedBy: [], shared: [] };
  
  const imports = store.importGraph.imports.get(file.id) || [];
  const importedBy = store.importGraph.importedBy.get(file.id) || [];
  
  // Find files with shared dependencies
  const shared = [];
  const fileImports = new Set(imports.map(f => f.id));
  
  for (const f of store.files) {
    if (f.id === file.id) continue;
    const fImports = store.importGraph.imports.get(f.id) || [];
    const sharedImports = fImports.filter(i => fileImports.has(i.id));
    if (sharedImports.length > 0) {
      shared.push({ file: f, sharedCount: sharedImports.length });
    }
  }
  
  return {
    imports,
    importedBy,
    shared: shared.sort((a, b) => b.sharedCount - a.sharedCount).slice(0, 10),
  };
}

/**
 * Search files
 */
export function searchFiles(query, limit = 50) {
  if (!query || query.length < 2) return [];
  
  const q = query.toLowerCase();
  const results = [];
  
  for (const file of store.files) {
    let score = 0;
    let reason = '';
    
    // Exact name match
    if (file.name.toLowerCase() === q) {
      score = 1;
      reason = 'exact';
    }
    // Name starts with
    else if (file.name.toLowerCase().startsWith(q)) {
      score = 0.9;
      reason = 'prefix';
    }
    // Name contains
    else if (file.name.toLowerCase().includes(q)) {
      score = 0.7;
      reason = 'contains';
    }
    // Path contains
    else if (file.path.toLowerCase().includes(q)) {
      score = 0.5;
      reason = 'path';
    }
    // Class/function name match
    else {
      for (const cls of file.classes) {
        if (cls.name?.toLowerCase().includes(q)) {
          score = 0.6;
          reason = 'class';
          break;
        }
      }
      if (!score) {
        for (const fn of file.functions) {
          if (fn.name?.toLowerCase().includes(q)) {
            score = 0.55;
            reason = 'function';
            break;
          }
        }
      }
    }
    // Summary/concepts
    if (!score && file.summary?.toLowerCase().includes(q)) {
      score = 0.3;
      reason = 'summary';
    }
    
    if (score > 0) {
      results.push({ file, score, reason });
    }
  }
  
  return results.sort((a, b) => b.score - a.score).slice(0, limit);
}

/**
 * Get files by category
 */
export function getFilesByCategory(category) {
  return store.files.filter(f => f.category === category);
}

/**
 * Get files in cluster
 */
export function getFilesInCluster(cluster) {
  return store.files.filter(f => f.cluster === cluster);
}

/**
 * Get category statistics
 */
export function getCategoryStats() {
  const stats = {};
  for (const file of store.files) {
    if (!stats[file.category]) {
      stats[file.category] = { count: 0, lines: 0 };
    }
    stats[file.category].count++;
    stats[file.category].lines += file.lines;
  }
  return Object.entries(stats)
    .map(([name, data]) => ({ name, ...data }))
    .sort((a, b) => b.count - a.count);
}
