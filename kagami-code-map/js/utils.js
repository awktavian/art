/**
 * Code Map Utilities
 * Shared utility functions for the code map visualization
 */

// Format large numbers with K/M suffixes
window.formatNumber = function(n) {
    if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
    if (n >= 1e3) return (n / 1e3).toFixed(1) + 'K';
    return n?.toLocaleString() || '0';
};

// Escape HTML special characters
window.escapeHtml = function(text) {
    if (!text) return '';
    return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
};

// Summarize text to a max length, respecting sentence boundaries
window.summarize = function(text, maxLength = 200) {
    if (!text) return '';
    const clean = text.replace(/\s+/g, ' ').trim();
    const sentences = clean.split(/(?<=[.!?])\s+/);
    let result = '';
    for (const sentence of sentences) {
        if (result.length + sentence.length > maxLength) break;
        result += (result ? ' ' : '') + sentence;
    }
    return result || clean.slice(0, maxLength) + (clean.length > maxLength ? '…' : '');
};

// Debounce function calls
window.debounce = function(fn, delay) {
    let timeout;
    return (...args) => {
        clearTimeout(timeout);
        timeout = setTimeout(() => fn(...args), delay);
    };
};

// Get category from file extension
window.getCategory = function(path) {
    if (!path) return 'Other';
    const ext = path.split('.').pop()?.toLowerCase();
    const mapping = {
        'py': 'Python',
        'js': 'JavaScript',
        'jsx': 'JavaScript',
        'ts': 'TypeScript',
        'tsx': 'TypeScript',
        'rs': 'Rust',
        'swift': 'Swift',
        'json': 'Config',
        'yaml': 'Config',
        'yml': 'Config',
        'toml': 'Config',
        'md': 'Documentation',
        'txt': 'Documentation',
        'test': 'Test',
        'spec': 'Test'
    };
    
    // Check for test files
    if (path.includes('test') || path.includes('spec')) {
        return 'Test';
    }
    
    return mapping[ext] || 'Other';
};

// Get file icon based on extension/category
window.getFileIcon = function(file) {
    if (file.isFile === false || file.children) return '📁';
    
    const ext = file.path?.split('.').pop()?.toLowerCase();
    const icons = {
        'py': '🐍',
        'js': '📜',
        'ts': '📘',
        'jsx': '⚛️',
        'tsx': '⚛️',
        'rs': '🦀',
        'swift': '🍎',
        'json': '📋',
        'yaml': '⚙️',
        'yml': '⚙️',
        'md': '📝',
        'html': '🌐',
        'css': '🎨',
        'sql': '🗄️'
    };
    
    return icons[ext] || '📄';
};

// HSL to CSS string
window.hslToString = function(h, s, l, a = 1) {
    if (a < 1) {
        return `hsla(${h}, ${s}%, ${l}%, ${a})`;
    }
    return `hsl(${h}, ${s}%, ${l}%)`;
};

// Lerp between two values
window.lerp = function(a, b, t) {
    return a + (b - a) * t;
};

// Clamp value between min and max
window.clamp = function(value, min, max) {
    return Math.min(Math.max(value, min), max);
};

// Ease out cubic
window.easeOutCubic = function(t) {
    return 1 - Math.pow(1 - t, 3);
};

// Ease in out cubic
window.easeInOutCubic = function(t) {
    return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
};
