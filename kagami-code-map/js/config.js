/**
 * Code Map Configuration
 * Generalized configuration that works with any codebase
 */

// Default configuration - can be overridden by JSON data
window.CODEMAP_CONFIG = {
    rootName: 'codebase',
    title: 'Code Map',
    
    // Visual settings
    colors: {
        background: '#09090f',
        accent: '#f0c860',
        text: '#e8e4dc'
    },
    
    // Category color palettes (HSL)
    palettes: {
        Python: { h: 210, s: 45, l: 55 },
        JavaScript: { h: 48, s: 65, l: 55 },
        TypeScript: { h: 210, s: 55, l: 50 },
        Rust: { h: 25, s: 60, l: 50 },
        Swift: { h: 15, s: 70, l: 55 },
        Config: { h: 280, s: 30, l: 45 },
        Documentation: { h: 145, s: 40, l: 45 },
        Test: { h: 340, s: 50, l: 50 },
        Other: { h: 220, s: 15, l: 50 },
        default: { h: 220, s: 20, l: 55 }
    },
    
    // Layer defaults
    layers: {
        imports: true,
        exports: false,
        shared: false,
        clusters: true,
        labels: true,
        heatmap: false,
        grid: false,
        ast: false,
        recent: false
    },
    
    // Animation timings (ms)
    animation: {
        fast: 150,
        normal: 250,
        slow: 400
    },
    
    // Storage keys
    storage: {
        lang: 'codemap-lang',
        theme: 'codemap-theme'
    }
};

// Allow overriding from JSON metadata
window.initConfig = function(data) {
    if (data?.meta?.name) {
        window.CODEMAP_CONFIG.rootName = data.meta.name;
    }
    if (data?.meta?.title) {
        window.CODEMAP_CONFIG.title = data.meta.title;
    }
};
