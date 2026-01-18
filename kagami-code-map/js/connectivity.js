/**
 * Code Map Connectivity
 * Functions for analyzing and visualizing file relationships
 */

// Get connected files for a given file (using imports/exports from AST)
window.getConnectedFiles = function(file, allFiles) {
    if (!file || !allFiles) return { imports: [], exports: [], shared: [] };
    
    const imports = [];
    const exports = [];
    const shared = [];
    
    // Find files this file imports
    const fileImports = file.imports || [];
    for (const imp of fileImports) {
        const imported = allFiles.find(f => 
            f.path.endsWith(imp) || 
            f.path.includes(imp.replace(/\./g, '/')) ||
            f.path.replace(/\.[^.]+$/, '').endsWith(imp.replace(/\./g, '/'))
        );
        if (imported) imports.push(imported);
    }
    
    // Find files that import this file
    for (const f of allFiles) {
        if (f.path === file.path) continue;
        const fImports = f.imports || [];
        const fileName = file.path.split('/').pop().replace(/\.[^.]+$/, '');
        const fileDir = file.path.split('/').slice(0, -1).join('/');
        
        for (const imp of fImports) {
            if (imp.includes(fileName) || file.path.includes(imp.replace(/\./g, '/'))) {
                exports.push(f);
                break;
            }
        }
    }
    
    // Find files with shared dependencies
    if (fileImports.length > 0) {
        for (const f of allFiles) {
            if (f.path === file.path) continue;
            const fImports = f.imports || [];
            const sharedImps = fImports.filter(imp => 
                fileImports.some(fi => fi === imp || fi.includes(imp) || imp.includes(fi))
            );
            if (sharedImps.length > 0) {
                shared.push({ file: f, count: sharedImps.length, shared: sharedImps });
            }
        }
    }
    
    return { 
        imports, 
        exports, 
        shared: shared.sort((a, b) => b.count - a.count).map(s => s.file)
    };
};

// Build a dependency graph from all files
window.buildDependencyGraph = function(files) {
    const graph = {
        nodes: new Map(),
        edges: []
    };
    
    // Add all files as nodes
    for (const file of files) {
        graph.nodes.set(file.path, {
            file,
            inDegree: 0,
            outDegree: 0,
            cluster: file.cluster
        });
    }
    
    // Build edges from imports
    for (const file of files) {
        const imports = file.imports || [];
        for (const imp of imports) {
            // Find target file
            const target = files.find(f => 
                f.path.endsWith(imp) || 
                f.path.includes(imp.replace(/\./g, '/'))
            );
            
            if (target) {
                graph.edges.push({
                    source: file.path,
                    target: target.path,
                    type: 'import'
                });
                
                const sourceNode = graph.nodes.get(file.path);
                const targetNode = graph.nodes.get(target.path);
                if (sourceNode) sourceNode.outDegree++;
                if (targetNode) targetNode.inDegree++;
            }
        }
    }
    
    return graph;
};

// Find strongly connected components (for detecting circular dependencies)
window.findCircularDependencies = function(graph) {
    const visited = new Set();
    const stack = new Set();
    const cycles = [];
    
    function dfs(node, path) {
        if (stack.has(node)) {
            // Found cycle
            const cycleStart = path.indexOf(node);
            if (cycleStart >= 0) {
                cycles.push(path.slice(cycleStart));
            }
            return;
        }
        
        if (visited.has(node)) return;
        
        visited.add(node);
        stack.add(node);
        path.push(node);
        
        // Find outgoing edges
        const outgoing = graph.edges.filter(e => e.source === node);
        for (const edge of outgoing) {
            dfs(edge.target, [...path]);
        }
        
        stack.delete(node);
    }
    
    for (const [nodePath] of graph.nodes) {
        dfs(nodePath, []);
    }
    
    return cycles;
};

// Calculate PageRank-like importance scores for files
window.calculateFileImportance = function(graph, iterations = 20, damping = 0.85) {
    const scores = new Map();
    const n = graph.nodes.size;
    
    // Initialize scores
    for (const [path] of graph.nodes) {
        scores.set(path, 1 / n);
    }
    
    // Iterate
    for (let i = 0; i < iterations; i++) {
        const newScores = new Map();
        
        for (const [path, node] of graph.nodes) {
            // Sum of scores from incoming edges
            let incomingScore = 0;
            const incoming = graph.edges.filter(e => e.target === path);
            
            for (const edge of incoming) {
                const sourceNode = graph.nodes.get(edge.source);
                if (sourceNode && sourceNode.outDegree > 0) {
                    incomingScore += scores.get(edge.source) / sourceNode.outDegree;
                }
            }
            
            newScores.set(path, (1 - damping) / n + damping * incomingScore);
        }
        
        // Update scores
        for (const [path, score] of newScores) {
            scores.set(path, score);
        }
    }
    
    return scores;
};

// Get files that would be affected by changing a given file
window.getAffectedFiles = function(file, graph, maxDepth = 3) {
    const affected = new Set();
    const queue = [{ path: file.path, depth: 0 }];
    
    while (queue.length > 0) {
        const { path, depth } = queue.shift();
        
        if (depth > maxDepth) continue;
        if (affected.has(path)) continue;
        
        affected.add(path);
        
        // Find files that depend on this file (reverse edges)
        const dependents = graph.edges
            .filter(e => e.target === path)
            .map(e => e.source);
        
        for (const dep of dependents) {
            if (!affected.has(dep)) {
                queue.push({ path: dep, depth: depth + 1 });
            }
        }
    }
    
    // Remove the original file
    affected.delete(file.path);
    
    return Array.from(affected);
};
