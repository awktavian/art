/**
 * Spatial Indexing — High-performance hit testing and neighbor queries
 * Uses grid-based spatial hashing for O(1) lookups
 */

import { CONFIG } from './config.js';

/**
 * 2D Spatial Hash Grid for treemap
 */
export class SpatialGrid2D {
  constructor(width, height, cellSize = CONFIG.performance.spatialGridSize) {
    this.cellSize = cellSize;
    this.cols = Math.ceil(width / cellSize);
    this.rows = Math.ceil(height / cellSize);
    this.grid = new Map();
    this.items = [];
  }
  
  clear() {
    this.grid.clear();
    this.items = [];
  }
  
  /**
   * Insert item with bounding box
   */
  insert(item, x, y, width, height) {
    const entry = { item, x, y, width, height };
    this.items.push(entry);
    
    // Find all cells this item overlaps
    const startCol = Math.floor(x / this.cellSize);
    const endCol = Math.floor((x + width) / this.cellSize);
    const startRow = Math.floor(y / this.cellSize);
    const endRow = Math.floor((y + height) / this.cellSize);
    
    for (let col = startCol; col <= endCol; col++) {
      for (let row = startRow; row <= endRow; row++) {
        const key = `${col},${row}`;
        if (!this.grid.has(key)) {
          this.grid.set(key, []);
        }
        this.grid.get(key).push(entry);
      }
    }
  }
  
  /**
   * Query items at point
   */
  queryPoint(x, y) {
    const col = Math.floor(x / this.cellSize);
    const row = Math.floor(y / this.cellSize);
    const key = `${col},${row}`;
    
    const candidates = this.grid.get(key) || [];
    
    // Filter to items that actually contain the point
    return candidates
      .filter(e => x >= e.x && x <= e.x + e.width && y >= e.y && y <= e.y + e.height)
      .map(e => e.item);
  }
  
  /**
   * Query items in rectangle
   */
  queryRect(x, y, width, height) {
    const results = new Set();
    
    const startCol = Math.floor(x / this.cellSize);
    const endCol = Math.floor((x + width) / this.cellSize);
    const startRow = Math.floor(y / this.cellSize);
    const endRow = Math.floor((y + height) / this.cellSize);
    
    for (let col = startCol; col <= endCol; col++) {
      for (let row = startRow; row <= endRow; row++) {
        const key = `${col},${row}`;
        const cell = this.grid.get(key);
        if (cell) {
          cell.forEach(e => {
            // AABB intersection test
            if (!(e.x + e.width < x || e.x > x + width ||
                  e.y + e.height < y || e.y > y + height)) {
              results.add(e.item);
            }
          });
        }
      }
    }
    
    return Array.from(results);
  }
}

/**
 * 3D Spatial Octree for semantic explorer
 */
export class SpatialOctree {
  constructor(bounds = { min: { x: 0, y: 0, z: 0 }, max: { x: 1, y: 1, z: 1 } }, maxItems = 8, maxDepth = 8) {
    this.bounds = bounds;
    this.maxItems = maxItems;
    this.maxDepth = maxDepth;
    this.items = [];
    this.children = null;
    this.depth = 0;
  }
  
  clear() {
    this.items = [];
    this.children = null;
  }
  
  /**
   * Insert item with 3D position
   */
  insert(item, x, y, z) {
    // Check bounds
    if (x < this.bounds.min.x || x > this.bounds.max.x ||
        y < this.bounds.min.y || y > this.bounds.max.y ||
        z < this.bounds.min.z || z > this.bounds.max.z) {
      return false;
    }
    
    const entry = { item, x, y, z };
    
    // If we have children, insert into appropriate child
    if (this.children) {
      const child = this._getChild(x, y, z);
      return child.insert(item, x, y, z);
    }
    
    // Add to this node
    this.items.push(entry);
    
    // Subdivide if needed
    if (this.items.length > this.maxItems && this.depth < this.maxDepth) {
      this._subdivide();
    }
    
    return true;
  }
  
  /**
   * Query items within radius of point
   */
  queryRadius(x, y, z, radius) {
    const results = [];
    this._queryRadius(x, y, z, radius, results);
    return results;
  }
  
  _queryRadius(x, y, z, radius, results) {
    // Check if this node's bounds intersect the query sphere
    const closestX = Math.max(this.bounds.min.x, Math.min(x, this.bounds.max.x));
    const closestY = Math.max(this.bounds.min.y, Math.min(y, this.bounds.max.y));
    const closestZ = Math.max(this.bounds.min.z, Math.min(z, this.bounds.max.z));
    
    const distSq = (x - closestX) ** 2 + (y - closestY) ** 2 + (z - closestZ) ** 2;
    if (distSq > radius * radius) return;
    
    // Check items in this node
    for (const entry of this.items) {
      const d = Math.sqrt((entry.x - x) ** 2 + (entry.y - y) ** 2 + (entry.z - z) ** 2);
      if (d <= radius) {
        results.push({ item: entry.item, distance: d });
      }
    }
    
    // Recurse into children
    if (this.children) {
      for (const child of this.children) {
        child._queryRadius(x, y, z, radius, results);
      }
    }
  }
  
  /**
   * Find nearest item to point
   */
  queryNearest(x, y, z, maxDist = Infinity) {
    let best = null;
    let bestDist = maxDist;
    
    this._queryNearest(x, y, z, bestDist, (item, dist) => {
      if (dist < bestDist) {
        bestDist = dist;
        best = item;
      }
    });
    
    return best ? { item: best, distance: bestDist } : null;
  }
  
  _queryNearest(x, y, z, maxDist, callback) {
    // Check items in this node
    for (const entry of this.items) {
      const d = Math.sqrt((entry.x - x) ** 2 + (entry.y - y) ** 2 + (entry.z - z) ** 2);
      if (d < maxDist) {
        callback(entry.item, d);
      }
    }
    
    // Recurse into children, prioritizing closer ones
    if (this.children) {
      const childDists = this.children.map((child, i) => {
        const cx = (child.bounds.min.x + child.bounds.max.x) / 2;
        const cy = (child.bounds.min.y + child.bounds.max.y) / 2;
        const cz = (child.bounds.min.z + child.bounds.max.z) / 2;
        return { child, dist: (x - cx) ** 2 + (y - cy) ** 2 + (z - cz) ** 2 };
      }).sort((a, b) => a.dist - b.dist);
      
      for (const { child } of childDists) {
        child._queryNearest(x, y, z, maxDist, callback);
      }
    }
  }
  
  _subdivide() {
    const mid = {
      x: (this.bounds.min.x + this.bounds.max.x) / 2,
      y: (this.bounds.min.y + this.bounds.max.y) / 2,
      z: (this.bounds.min.z + this.bounds.max.z) / 2,
    };
    
    this.children = [];
    
    // Create 8 children (octants)
    for (let i = 0; i < 8; i++) {
      const childBounds = {
        min: {
          x: (i & 1) ? mid.x : this.bounds.min.x,
          y: (i & 2) ? mid.y : this.bounds.min.y,
          z: (i & 4) ? mid.z : this.bounds.min.z,
        },
        max: {
          x: (i & 1) ? this.bounds.max.x : mid.x,
          y: (i & 2) ? this.bounds.max.y : mid.y,
          z: (i & 4) ? this.bounds.max.z : mid.z,
        },
      };
      
      const child = new SpatialOctree(childBounds, this.maxItems, this.maxDepth);
      child.depth = this.depth + 1;
      this.children.push(child);
    }
    
    // Move items to children
    for (const entry of this.items) {
      const child = this._getChild(entry.x, entry.y, entry.z);
      child.items.push(entry);
    }
    this.items = [];
  }
  
  _getChild(x, y, z) {
    const mid = {
      x: (this.bounds.min.x + this.bounds.max.x) / 2,
      y: (this.bounds.min.y + this.bounds.max.y) / 2,
      z: (this.bounds.min.z + this.bounds.max.z) / 2,
    };
    
    let index = 0;
    if (x >= mid.x) index |= 1;
    if (y >= mid.y) index |= 2;
    if (z >= mid.z) index |= 4;
    
    return this.children[index];
  }
}

/**
 * Projected coordinates cache for 3D->2D
 */
export class ProjectionCache {
  constructor() {
    this.cache = new Map();
    this.version = 0;
  }
  
  invalidate() {
    this.version++;
    this.cache.clear();
  }
  
  get(key) {
    const entry = this.cache.get(key);
    if (entry && entry.version === this.version) {
      return entry.value;
    }
    return null;
  }
  
  set(key, value) {
    this.cache.set(key, { value, version: this.version });
  }
}

/**
 * Similarity cache for embedding-based queries
 */
export class SimilarityCache {
  constructor(maxSize = 500) {
    this.cache = new Map();
    this.maxSize = maxSize;
    this.accessOrder = [];
  }
  
  get(key) {
    const entry = this.cache.get(key);
    if (entry) {
      // Move to end (LRU)
      const idx = this.accessOrder.indexOf(key);
      if (idx > -1) {
        this.accessOrder.splice(idx, 1);
        this.accessOrder.push(key);
      }
      return entry;
    }
    return null;
  }
  
  set(key, value) {
    // Evict oldest if at capacity
    while (this.cache.size >= this.maxSize) {
      const oldest = this.accessOrder.shift();
      this.cache.delete(oldest);
    }
    
    this.cache.set(key, value);
    this.accessOrder.push(key);
  }
  
  clear() {
    this.cache.clear();
    this.accessOrder = [];
  }
}
