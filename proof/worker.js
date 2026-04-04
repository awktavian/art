/**
 * Code Galaxy Web Worker — Background JSON Processing
 * 
 * Handles heavy computation off the main thread:
 * - JSON parsing (8MB+ files)
 * - File indexing for search
 * - Coordinate transformations
 */

'use strict';

// Message handler
self.onmessage = async function(e) {
    const { type, payload, id } = e.data;
    
    try {
        let result;
        
        switch (type) {
            case 'PARSE_JSON':
                result = await parseJSON(payload);
                break;
                
            case 'BUILD_SEARCH_INDEX':
                result = buildSearchIndex(payload);
                break;
                
            case 'COMPUTE_SIMILAR':
                result = computeSimilarFiles(payload.file, payload.files, payload.maxResults);
                break;
                
            case 'TRANSFORM_COORDINATES':
                result = transformCoordinates(payload.files, payload.transform);
                break;
                
            default:
                throw new Error(`Unknown message type: ${type}`);
        }
        
        self.postMessage({ type: 'SUCCESS', id, result });
        
    } catch (error) {
        self.postMessage({ 
            type: 'ERROR', 
            id, 
            error: { message: error.message, stack: error.stack }
        });
    }
};

/**
 * Parse JSON string into object with progress reporting
 */
async function parseJSON(jsonString) {
    const startTime = performance.now();
    
    // Report start
    self.postMessage({ type: 'PROGRESS', stage: 'parsing', progress: 0 });
    
    // Parse the JSON
    const data = JSON.parse(jsonString);
    
    self.postMessage({ type: 'PROGRESS', stage: 'parsing', progress: 50 });
    
    // Post-process: ensure arrays exist
    if (!data.files) data.files = [];
    if (!data.clusters) data.clusters = {};
    if (!data.colonies) data.colonies = {};
    
    // Build file lookup map for fast access
    const fileMap = new Map();
    for (const file of data.files) {
        fileMap.set(file.path, file);
    }
    
    self.postMessage({ type: 'PROGRESS', stage: 'parsing', progress: 100 });
    
    const duration = performance.now() - startTime;
    console.log(`[Worker] Parsed ${data.files.length} files in ${duration.toFixed(0)}ms`);
    
    return {
        data,
        fileCount: data.files.length,
        duration
    };
}

/**
 * Build inverted index for fast search
 */
function buildSearchIndex(files) {
    const startTime = performance.now();
    
    // Inverted index: term -> [{ fileIndex, field, score }]
    const index = new Map();
    
    // Stopwords to skip
    const stopwords = new Set([
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'from', 'is', 'it', 'this', 'that', 'as', 'be'
    ]);
    
    // Field weights for scoring
    const fieldWeights = {
        name: 10,
        functions: 5,
        classes: 6,
        keywords: 4,
        concepts: 3,
        exports: 3,
        path: 2,
        summary: 1
    };
    
    for (let i = 0; i < files.length; i++) {
        const file = files[i];
        
        // Index each field
        indexField(index, i, 'name', file.name || '', fieldWeights.name, stopwords);
        indexField(index, i, 'path', file.path || '', fieldWeights.path, stopwords);
        indexField(index, i, 'summary', file.summary || '', fieldWeights.summary, stopwords);
        
        // Index arrays
        (file.functions || []).forEach(f => indexField(index, i, 'functions', f, fieldWeights.functions, stopwords));
        (file.classes || []).forEach(c => indexField(index, i, 'classes', c, fieldWeights.classes, stopwords));
        (file.keywords || []).forEach(k => indexField(index, i, 'keywords', k, fieldWeights.keywords, stopwords));
        (file.concepts || []).forEach(c => indexField(index, i, 'concepts', c, fieldWeights.concepts, stopwords));
        (file.exports || []).forEach(e => indexField(index, i, 'exports', String(e), fieldWeights.exports, stopwords));
        
        // Report progress every 500 files
        if (i % 500 === 0) {
            self.postMessage({ 
                type: 'PROGRESS', 
                stage: 'indexing', 
                progress: Math.round((i / files.length) * 100)
            });
        }
    }
    
    const duration = performance.now() - startTime;
    console.log(`[Worker] Built search index with ${index.size} terms in ${duration.toFixed(0)}ms`);
    
    // Convert Map to serializable object
    const serializedIndex = {};
    for (const [term, entries] of index) {
        serializedIndex[term] = entries;
    }
    
    return {
        index: serializedIndex,
        termCount: index.size,
        duration
    };
}

function indexField(index, fileIndex, field, text, weight, stopwords) {
    if (!text) return;
    
    // Tokenize: split on non-alphanumeric, lowercase
    const tokens = text.toLowerCase()
        .split(/[^a-z0-9]+/)
        .filter(t => t.length >= 2 && !stopwords.has(t));
    
    for (const token of tokens) {
        if (!index.has(token)) {
            index.set(token, []);
        }
        index.get(token).push({ fileIndex, field, weight });
    }
}

/**
 * Compute similar files based on embedding distance and metadata
 */
function computeSimilarFiles(targetFile, files, maxResults = 10) {
    const startTime = performance.now();
    
    if (!targetFile || !files || files.length === 0) {
        return { similar: [], duration: 0 };
    }
    
    const targetPos = { x: targetFile.x || 0, y: targetFile.y || 0, z: targetFile.z || 0 };
    const targetCluster = targetFile.cluster;
    const targetCategory = targetFile.category;
    
    const scored = [];
    
    for (const file of files) {
        if (file.path === targetFile.path) continue;
        
        // 3D Euclidean distance (embedding space)
        const dx = (file.x || 0) - targetPos.x;
        const dy = (file.y || 0) - targetPos.y;
        const dz = (file.z || 0) - targetPos.z;
        const distance = Math.sqrt(dx * dx + dy * dy + dz * dz);
        
        // Distance score (inverse, normalized)
        let score = 1 / (1 + distance * 1.2);
        
        // Cluster bonus (same colony)
        if (file.cluster === targetCluster) {
            score += 0.2;
        }
        
        // Category bonus (same language)
        if (file.category === targetCategory) {
            score += 0.1;
        }
        
        // Import relationship bonus
        const targetImports = targetFile.imports || [];
        const fileExports = file.exports || [];
        if (targetImports.some(imp => fileExports.includes(imp))) {
            score += 0.15;
        }
        
        scored.push({ file, score, distance });
    }
    
    // Sort by score descending
    scored.sort((a, b) => b.score - a.score);
    
    const similar = scored.slice(0, maxResults).map(s => ({
        path: s.file.path,
        name: s.file.name,
        score: Math.round(s.score * 100),
        category: s.file.category,
        cluster: s.file.cluster
    }));
    
    const duration = performance.now() - startTime;
    
    return { similar, duration };
}

/**
 * Transform 3D coordinates with rotation and scale
 */
function transformCoordinates(files, transform) {
    const { rotX, rotY, zoom, cameraZ, fov, width, height } = transform;
    
    const cosX = Math.cos(rotX);
    const sinX = Math.sin(rotX);
    const cosY = Math.cos(rotY);
    const sinY = Math.sin(rotY);
    
    const cx = width / 2;
    const cy = height / 2;
    const scale = Math.min(width, height) * 0.85 * zoom;
    
    const projected = [];
    
    for (const file of files) {
        const x = file.x || 0;
        const y = file.y || 0;
        const z = file.z || 0;
        
        // Rotate around Y axis
        const x1 = x * cosY - z * sinY;
        const z1 = x * sinY + z * cosY;
        
        // Rotate around X axis
        const y1 = y * cosX - z1 * sinX;
        const z2 = y * sinX + z1 * cosX;
        
        // Perspective projection
        const depth = z2 + cameraZ;
        if (depth <= 0.1) continue;
        
        const perspective = fov / depth;
        const sx = cx + x1 * scale * perspective;
        const sy = cy + y1 * scale * perspective;
        
        projected.push({
            path: file.path,
            sx,
            sy,
            depth,
            scale: perspective
        });
    }
    
    // Sort by depth (back to front)
    projected.sort((a, b) => b.depth - a.depth);
    
    return projected;
}

// Signal worker is ready
self.postMessage({ type: 'READY' });
