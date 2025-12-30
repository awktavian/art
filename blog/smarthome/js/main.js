/**
 * One Command — Technical Deep Dive
 * Minimal, purposeful interactions
 */

(function() {
    'use strict';

    // =========================================================================
    // Reading Progress Bar
    // =========================================================================

    function initReadingProgress() {
        const progressBar = document.querySelector('.reading-progress');
        const progressFill = document.querySelector('.reading-progress-bar');
        if (!progressBar || !progressFill) return;

        let ticking = false;

        function updateProgress() {
            const scrollTop = window.scrollY;
            const docHeight = document.documentElement.scrollHeight - window.innerHeight;
            const progress = Math.min((scrollTop / docHeight) * 100, 100);

            progressFill.style.width = progress + '%';
            progressBar.setAttribute('aria-valuenow', Math.round(progress));

            // Show progress bar after scrolling past hero
            if (scrollTop > 200) {
                progressBar.classList.add('visible');
            } else {
                progressBar.classList.remove('visible');
            }

            ticking = false;
        }

        window.addEventListener('scroll', function() {
            if (!ticking) {
                requestAnimationFrame(updateProgress);
                ticking = true;
            }
        }, { passive: true });
    }

    // =========================================================================
    // Sticky Navigation
    // =========================================================================

    function initStickyNav() {
        const nav = document.querySelector('.sticky-nav');
        const navLinks = document.querySelectorAll('.sticky-nav-links a');
        const sections = document.querySelectorAll('section[id]');
        if (!nav || !sections.length) return;

        let ticking = false;
        const heroHeight = document.querySelector('.scene-hook')?.offsetHeight || 600;

        function updateNav() {
            const scrollTop = window.scrollY;

            // Show/hide nav based on scroll position
            if (scrollTop > heroHeight - 100) {
                nav.classList.add('visible');
            } else {
                nav.classList.remove('visible');
            }

            // Update active section
            let currentSection = '';
            sections.forEach(section => {
                const sectionTop = section.offsetTop - 100;
                const sectionBottom = sectionTop + section.offsetHeight;
                if (scrollTop >= sectionTop && scrollTop < sectionBottom) {
                    currentSection = section.getAttribute('id');
                }
            });

            navLinks.forEach(link => {
                const href = link.getAttribute('href').replace('#', '');
                if (href === currentSection) {
                    link.classList.add('active');
                } else {
                    link.classList.remove('active');
                }
            });

            ticking = false;
        }

        window.addEventListener('scroll', function() {
            if (!ticking) {
                requestAnimationFrame(updateNav);
                ticking = true;
            }
        }, { passive: true });

        // Smooth scroll for nav links
        navLinks.forEach(link => {
            link.addEventListener('click', function(e) {
                e.preventDefault();
                const targetId = this.getAttribute('href').replace('#', '');
                const target = document.getElementById(targetId);
                if (target) {
                    target.scrollIntoView({ behavior: 'smooth' });
                }
            });
        });
    }

    // =========================================================================
    // Copy Button
    // =========================================================================

    function initCopyButton() {
        const terminal = document.querySelector('.terminal');
        if (!terminal) return;

        // Create copy button
        const copyBtn = document.createElement('button');
        copyBtn.className = 'copy-button';
        copyBtn.textContent = 'Copy';
        copyBtn.setAttribute('aria-label', 'Copy command to clipboard');
        copyBtn.type = 'button';

        terminal.appendChild(copyBtn);

        copyBtn.addEventListener('click', async function() {
            const command = document.querySelector('.terminal-command');
            if (!command) return;

            try {
                await navigator.clipboard.writeText(command.textContent);
                copyBtn.textContent = 'Copied!';
                copyBtn.classList.add('copied');

                setTimeout(() => {
                    copyBtn.textContent = 'Copy';
                    copyBtn.classList.remove('copied');
                }, 2000);
            } catch (err) {
                copyBtn.textContent = 'Failed';
                setTimeout(() => {
                    copyBtn.textContent = 'Copy';
                }, 2000);
            }
        });
    }

    // =========================================================================
    // Interactive Architecture Diagram
    // =========================================================================

    function initArchDiagram() {
        const archBoxes = document.querySelectorAll('.arch-box');
        if (!archBoxes.length) return;

        // Add tooltips and keyboard accessibility
        const tooltips = {
            'SmartHomeController': 'Singleton orchestrator managing all 26 rooms and integrations',
            'RoomOrchestrator': 'Coordinates devices within each room context',
            'PresenceEngine': 'WiFi + Tesla + Eight Sleep for occupancy detection',
            'FailoverManager': 'Circuit breakers and graceful degradation paths'
        };

        archBoxes.forEach(box => {
            const label = box.querySelector('.arch-label');
            if (!label) return;

            const labelText = label.textContent.trim();
            if (tooltips[labelText]) {
                box.setAttribute('data-tooltip', tooltips[labelText]);
                box.setAttribute('tabindex', '0');
                box.setAttribute('role', 'button');
                box.setAttribute('aria-label', labelText + ': ' + tooltips[labelText]);
            }
        });
    }

    // =========================================================================
    // Terminal Animation - Enhanced with realistic typing
    // =========================================================================

    function initTerminal() {
        const terminal = document.querySelector('.terminal');
        const commandEl = document.querySelector('.terminal-command');
        const items = document.querySelectorAll('.output-item');
        const result = document.querySelector('.terminal-result');

        if (!terminal || !items.length) return;

        let animationStarted = false;

        // Add cursor element after command
        const cursor = document.createElement('span');
        cursor.className = 'terminal-cursor';
        cursor.textContent = '|';
        if (commandEl) {
            commandEl.parentNode.insertBefore(cursor, commandEl.nextSibling);
        }

        // Typing animation helper
        function typeText(element, text, speed = 50) {
            return new Promise(resolve => {
                element.textContent = '';
                let i = 0;

                function type() {
                    if (i < text.length) {
                        element.textContent += text.charAt(i);
                        i++;
                        // Variable typing speed for realism
                        const variance = Math.random() * 40 - 20;
                        setTimeout(type, speed + variance);
                    } else {
                        resolve();
                    }
                }
                type();
            });
        }

        async function runTerminal() {
            if (animationStarted) return;
            animationStarted = true;

            // Type the command first
            if (commandEl) {
                const originalText = commandEl.textContent;
                cursor.classList.add('typing');
                await typeText(commandEl, originalText, 45);
                cursor.classList.remove('typing');

                // Brief pause after typing command
                await new Promise(r => setTimeout(r, 300));
            }

            // Animate each output item with staggered timing
            for (let i = 0; i < items.length; i++) {
                const item = items[i];

                // Show spinner first
                item.classList.add('processing');

                // Wait for "processing"
                await new Promise(r => setTimeout(r, 150 + Math.random() * 100));

                // Complete the item
                item.classList.remove('processing');
                item.classList.add('done');

                // Small delay between items
                await new Promise(r => setTimeout(r, 80 + Math.random() * 80));
            }

            // Show result with a satisfying animation
            if (result) {
                await new Promise(r => setTimeout(r, 200));
                result.classList.add('visible');
            }

            // Hide cursor after completion
            setTimeout(() => {
                cursor.classList.add('hidden');
            }, 1000);
        }

        // Start on scroll into view
        const observer = new IntersectionObserver((entries) => {
            if (entries[0].isIntersecting) {
                setTimeout(runTerminal, 500);
                observer.disconnect();
            }
        }, { threshold: 0.5 });

        observer.observe(terminal);
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
    // Scroll Reveal - Enhanced with staggered children
    // =========================================================================

    function initScrollReveal() {
        const scenes = document.querySelectorAll('.scene');

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('revealed');

                    // Stagger reveal children
                    const staggerChildren = entry.target.querySelectorAll(
                        '.content-block, .stats-row, .data-table, .trigger-list, .lesson, .upnext-item, .card, .callout, blockquote'
                    );
                    staggerChildren.forEach((child, i) => {
                        child.style.transitionDelay = `${i * 80}ms`;
                        child.classList.add('child-revealed');
                    });
                }
            });
        }, {
            threshold: 0.1,
            rootMargin: '-50px'
        });

        scenes.forEach(scene => {
            scene.style.opacity = '0';
            scene.style.transform = 'translateY(24px)';
            scene.style.transition = 'opacity 0.6s var(--ease), transform 0.6s var(--ease)';
            observer.observe(scene);
        });

        // Add styles for revealed state
        const style = document.createElement('style');
        style.textContent = `
            .scene.revealed { opacity: 1 !important; transform: translateY(0) !important; }
            .content-block, .stats-row, .data-table, .trigger-list, .lesson, .upnext-item, .card, .callout, blockquote {
                opacity: 0;
                transform: translateY(16px);
                transition: opacity 0.5s var(--ease), transform 0.5s var(--ease);
            }
            .child-revealed {
                opacity: 1 !important;
                transform: translateY(0) !important;
            }
        `;
        document.head.appendChild(style);

        // Reveal hook immediately
        const hook = document.querySelector('.scene-hook');
        if (hook) {
            hook.style.opacity = '1';
            hook.style.transform = 'translateY(0)';
        }
    }

    // =========================================================================
    // Architecture Diagram Animation - Progressive connections
    // =========================================================================

    function initArchAnimation() {
        const archDiagram = document.querySelector('.arch-diagram');
        if (!archDiagram) return;

        const connectors = archDiagram.querySelectorAll('.arch-connector');
        const boxes = archDiagram.querySelectorAll('.arch-box');
        const tiers = archDiagram.querySelectorAll('.tier');

        // Initial state - hidden
        connectors.forEach(c => {
            c.style.transform = 'scaleY(0)';
            c.style.transformOrigin = 'top';
            c.style.transition = 'transform 0.4s var(--ease)';
        });

        boxes.forEach(b => {
            b.style.opacity = '0';
            b.style.transform = 'scale(0.9)';
            b.style.transition = 'opacity 0.4s var(--ease), transform 0.4s var(--ease)';
        });

        tiers.forEach(t => {
            t.style.opacity = '0';
            t.style.transform = 'translateY(10px)';
            t.style.transition = 'opacity 0.3s var(--ease), transform 0.3s var(--ease)';
        });

        // Animate when in view
        const observer = new IntersectionObserver((entries) => {
            if (entries[0].isIntersecting) {
                animateArchDiagram();
                observer.disconnect();
            }
        }, { threshold: 0.3 });

        observer.observe(archDiagram);

        async function animateArchDiagram() {
            // Layer 1: Main controller
            const mainBox = archDiagram.querySelector('.arch-box-main');
            if (mainBox) {
                mainBox.style.opacity = '1';
                mainBox.style.transform = 'scale(1)';
            }

            await new Promise(r => setTimeout(r, 300));

            // Connector 1
            if (connectors[0]) {
                connectors[0].style.transform = 'scaleY(1)';
            }

            await new Promise(r => setTimeout(r, 250));

            // Layer 2: Sub-controllers (staggered)
            const layer2Boxes = archDiagram.querySelectorAll('.arch-layer:nth-child(3) .arch-box');
            layer2Boxes.forEach((box, i) => {
                setTimeout(() => {
                    box.style.opacity = '1';
                    box.style.transform = 'scale(1)';
                }, i * 100);
            });

            await new Promise(r => setTimeout(r, 400));

            // Connector 2
            if (connectors[1]) {
                connectors[1].style.transform = 'scaleY(1)';
            }

            await new Promise(r => setTimeout(r, 250));

            // Tiers (staggered)
            tiers.forEach((tier, i) => {
                setTimeout(() => {
                    tier.style.opacity = '1';
                    tier.style.transform = 'translateY(0)';
                }, i * 80);
            });
        }
    }

    // =========================================================================
    // Interactive Code Blocks - Copy to clipboard
    // =========================================================================

    function initCodeBlocks() {
        const codeBlocks = document.querySelectorAll('.code-block');

        codeBlocks.forEach(block => {
            // Create copy button
            const copyBtn = document.createElement('button');
            copyBtn.className = 'code-copy-btn';
            copyBtn.innerHTML = `
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                </svg>
                <span>Copy</span>
            `;
            copyBtn.setAttribute('aria-label', 'Copy code to clipboard');

            // Add to header or create one
            let header = block.querySelector('.code-header');
            if (header) {
                header.appendChild(copyBtn);
            } else {
                block.insertBefore(copyBtn, block.firstChild);
                copyBtn.style.position = 'absolute';
                copyBtn.style.top = '8px';
                copyBtn.style.right = '8px';
                block.style.position = 'relative';
            }

            // Click handler
            copyBtn.addEventListener('click', async () => {
                const codeContent = block.querySelector('.code-content');
                if (!codeContent) return;

                try {
                    await navigator.clipboard.writeText(codeContent.textContent);
                    copyBtn.classList.add('copied');
                    copyBtn.querySelector('span').textContent = 'Copied!';

                    setTimeout(() => {
                        copyBtn.classList.remove('copied');
                        copyBtn.querySelector('span').textContent = 'Copy';
                    }, 2000);
                } catch (err) {
                    copyBtn.querySelector('span').textContent = 'Failed';
                    setTimeout(() => {
                        copyBtn.querySelector('span').textContent = 'Copy';
                    }, 2000);
                }
            });
        });
    }

    // =========================================================================
    // Trigger List Hover Animations
    // =========================================================================

    function initTriggerAnimations() {
        const triggerItems = document.querySelectorAll('.trigger-item');

        triggerItems.forEach(item => {
            const arrow = item.querySelector('.trigger-arrow');
            const action = item.querySelector('.trigger-action');

            item.addEventListener('mouseenter', () => {
                if (arrow) {
                    arrow.style.transform = 'translateX(4px)';
                    arrow.style.color = 'var(--accent)';
                }
                if (action) {
                    action.style.color = 'var(--text)';
                }
            });

            item.addEventListener('mouseleave', () => {
                if (arrow) {
                    arrow.style.transform = 'translateX(0)';
                    arrow.style.color = '';
                }
                if (action) {
                    action.style.color = '';
                }
            });
        });
    }

    // =========================================================================
    // Data Table Row Hover
    // =========================================================================

    function initTableAnimations() {
        const tableRows = document.querySelectorAll('.data-table tbody tr');

        tableRows.forEach(row => {
            row.style.transition = 'background 0.2s var(--ease), transform 0.2s var(--ease)';

            row.addEventListener('mouseenter', () => {
                row.style.background = 'var(--bg-alt)';
                row.style.transform = 'translateX(4px)';
            });

            row.addEventListener('mouseleave', () => {
                row.style.background = '';
                row.style.transform = '';
            });
        });
    }

    // =========================================================================
    // Stat Counter Animation
    // =========================================================================

    function initStatCounters() {
        const stats = document.querySelectorAll('.stat-value');

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    animateCounter(entry.target);
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.5 });

        stats.forEach(stat => {
            observer.observe(stat);
        });

        function animateCounter(element) {
            const finalValue = parseInt(element.textContent, 10);
            if (isNaN(finalValue)) return;

            const duration = 1000;
            const startTime = performance.now();

            function update(currentTime) {
                const elapsed = currentTime - startTime;
                const progress = Math.min(elapsed / duration, 1);

                // Easing function (ease-out)
                const eased = 1 - Math.pow(1 - progress, 3);
                const current = Math.round(eased * finalValue);

                element.textContent = current;

                if (progress < 1) {
                    requestAnimationFrame(update);
                } else {
                    element.textContent = finalValue;
                }
            }

            requestAnimationFrame(update);
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
        // Core functionality
        initReadingProgress();
        initStickyNav();
        initCopyButton();
        initArchDiagram();
        initTerminal();
        initScrollReveal();
        initEasterEgg();

        // Enhanced interactions
        initArchAnimation();
        initCodeBlocks();
        initTriggerAnimations();
        initTableAnimations();
        initStatCounters();

        // Delay chaos lines until layout stabilizes
        setTimeout(initChaosLines, 100);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
