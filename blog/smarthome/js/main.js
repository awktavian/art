/**
 * One Command — Technical Deep Dive
 * Minimal, purposeful interactions
 */

(function() {
    'use strict';

    // =========================================================================
    // Terminal Animation
    // =========================================================================

    function initTerminal() {
        const items = document.querySelectorAll('.output-item');
        const result = document.querySelector('.terminal-result');
        if (!items.length) return;

        let animationStarted = false;

        function runTerminal() {
            if (animationStarted) return;
            animationStarted = true;

            items.forEach((item, i) => {
                // Mark as done after animation
                setTimeout(() => {
                    item.classList.add('done');
                }, (i + 1) * 200 + 300);
            });

            // Show result after all items
            if (result) {
                setTimeout(() => {
                    result.classList.add('visible');
                }, items.length * 200 + 600);
            }
        }

        // Start on scroll into view
        const observer = new IntersectionObserver((entries) => {
            if (entries[0].isIntersecting) {
                setTimeout(runTerminal, 500);
                observer.disconnect();
            }
        }, { threshold: 0.5 });

        const terminal = document.querySelector('.terminal');
        if (terminal) observer.observe(terminal);
    }

    // =========================================================================
    // Chaos Lines
    // =========================================================================

    function initChaosLines() {
        const svg = document.querySelector('.chaos-lines');
        if (!svg) return;

        const centerX = 300;
        const centerY = 300;
        const nodes = document.querySelectorAll('.chaos-node');

        // Create connecting lines
        nodes.forEach((node, i) => {
            // Connect to center
            const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
            line.setAttribute('x1', centerX);
            line.setAttribute('y1', centerY);
            
            // Calculate node position (approximate)
            const rect = node.getBoundingClientRect();
            const containerRect = svg.getBoundingClientRect();
            const x2 = rect.left - containerRect.left + rect.width / 2;
            const y2 = rect.top - containerRect.top + rect.height / 2;
            
            line.setAttribute('x2', x2 || centerX);
            line.setAttribute('y2', y2 || centerY);
            line.setAttribute('stroke', '#d6d0c5');
            line.setAttribute('stroke-width', '1');
            line.setAttribute('stroke-dasharray', '4 4');
            line.setAttribute('opacity', '0.5');
            
            svg.appendChild(line);
        });
    }

    // =========================================================================
    // Scroll Reveal
    // =========================================================================

    function initScrollReveal() {
        const scenes = document.querySelectorAll('.scene');
        
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('revealed');
                }
            });
        }, {
            threshold: 0.1,
            rootMargin: '-50px'
        });

        scenes.forEach(scene => {
            scene.style.opacity = '0';
            scene.style.transform = 'translateY(24px)';
            scene.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
            observer.observe(scene);
        });

        // Add styles for revealed state
        const style = document.createElement('style');
        style.textContent = `.scene.revealed { opacity: 1 !important; transform: translateY(0) !important; }`;
        document.head.appendChild(style);

        // Reveal hook immediately
        const hook = document.querySelector('.scene-hook');
        if (hook) {
            hook.style.opacity = '1';
            hook.style.transform = 'translateY(0)';
        }
    }

    // =========================================================================
    // Easter Egg
    // =========================================================================

    function initEasterEgg() {
        let buffer = '';
        let timeout;

        document.addEventListener('keydown', (e) => {
            clearTimeout(timeout);
            
            if (e.key.length === 1 && /[a-z]/i.test(e.key)) {
                buffer += e.key.toLowerCase();
                
                if (buffer.includes('goodnight')) {
                    buffer = '';
                    showGoodnight();
                }
            }

            timeout = setTimeout(() => buffer = '', 2000);
        });
    }

    function showGoodnight() {
        const overlay = document.createElement('div');
        overlay.innerHTML = `
            <div style="
                position: fixed;
                inset: 0;
                background: rgba(0,0,0,0.95);
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                z-index: 10000;
                cursor: pointer;
                animation: fadeIn 0.5s ease;
            ">
                <span style="
                    font-family: 'Cormorant Garamond', serif;
                    font-size: clamp(3rem, 10vw, 6rem);
                    font-style: italic;
                    color: #faf9f7;
                    opacity: 0;
                    animation: fadeIn 1s ease 0.3s forwards;
                ">Goodnight</span>
                <span style="
                    font-family: 'IBM Plex Mono', monospace;
                    font-size: 0.875rem;
                    color: #c9a96e;
                    margin-top: 2rem;
                    opacity: 0;
                    animation: fadeIn 1s ease 1s forwards;
                ">87ms</span>
            </div>
            <style>
                @keyframes fadeIn {
                    from { opacity: 0; }
                    to { opacity: 1; }
                }
            </style>
        `;

        document.body.appendChild(overlay);

        overlay.addEventListener('click', () => {
            overlay.style.opacity = '0';
            overlay.style.transition = 'opacity 0.3s';
            setTimeout(() => overlay.remove(), 300);
        });

        setTimeout(() => {
            if (document.body.contains(overlay)) {
                overlay.click();
            }
        }, 4000);
    }

    // =========================================================================
    // Initialize
    // =========================================================================

    function init() {
        initTerminal();
        initScrollReveal();
        initEasterEgg();
        
        // Delay chaos lines until layout stabilizes
        setTimeout(initChaosLines, 100);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
