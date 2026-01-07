/**
 * 📖 Kagami Art Gallery — Accessibility Module
 * 
 * Domain-wide large text setting via localStorage.
 * Include this script on any page to enable the feature.
 * 
 * Usage:
 *   <script src="accessibility.js"></script>
 * 
 * CSS required (add to your page):
 *   body.large-text { font-size: 22px; }
 *   (customize other selectors as needed)
 */

(function() {
    'use strict';
    
    const STORAGE_KEY = 'kagami_large_text';
    
    // Apply large text immediately on page load (before DOMContentLoaded)
    // This prevents flash of small text
    if (localStorage.getItem(STORAGE_KEY) === 'true') {
        document.documentElement.classList.add('large-text');
    }
    
    // Once DOM is ready, also add to body and set up toggle if present
    document.addEventListener('DOMContentLoaded', function() {
        const isLarge = localStorage.getItem(STORAGE_KEY) === 'true';
        
        if (isLarge) {
            document.body.classList.add('large-text');
        }
        
        // If there's a font toggle button, wire it up
        const fontToggle = document.getElementById('font-toggle');
        if (fontToggle) {
            if (isLarge) {
                fontToggle.classList.add('large');
                fontToggle.title = 'Normal text size';
            }
            
            fontToggle.addEventListener('click', function() {
                const nowLarge = !document.body.classList.contains('large-text');
                
                document.documentElement.classList.toggle('large-text', nowLarge);
                document.body.classList.toggle('large-text', nowLarge);
                fontToggle.classList.toggle('large', nowLarge);
                
                localStorage.setItem(STORAGE_KEY, nowLarge);
                fontToggle.title = nowLarge ? 'Normal text size' : 'Increase text size';
                
                // Dispatch event for pages that want to react
                window.dispatchEvent(new CustomEvent('kagami:fontsize', { 
                    detail: { large: nowLarge } 
                }));
            });
        }
    });
    
    // Expose API for programmatic control
    window.kagamiAccessibility = {
        isLargeText: function() {
            return localStorage.getItem(STORAGE_KEY) === 'true';
        },
        setLargeText: function(enabled) {
            localStorage.setItem(STORAGE_KEY, enabled);
            document.documentElement.classList.toggle('large-text', enabled);
            document.body.classList.toggle('large-text', enabled);
            
            const toggle = document.getElementById('font-toggle');
            if (toggle) {
                toggle.classList.toggle('large', enabled);
                toggle.title = enabled ? 'Normal text size' : 'Increase text size';
            }
        },
        toggle: function() {
            this.setLargeText(!this.isLargeText());
        }
    };
})();
