// Colonies Hall Room - Interactive Constellation

import { COLONIES, FANO_LINES } from '../data/colonies.js';
import { SoundSystem } from '../core/sound.js';

// Constellation layout positions (percentage-based)
const COLONY_POSITIONS = {
    spark:   { x: 50,  y: 20 },  // Top center
    forge:   { x: 85,  y: 40 },  // Right upper
    flow:    { x: 85,  y: 60 },  // Right lower
    nexus:   { x: 50,  y: 50 },  // Center (integration point)
    beacon:  { x: 15,  y: 40 },  // Left upper
    grove:   { x: 15,  y: 60 },  // Left lower
    crystal: { x: 50,  y: 80 },  // Bottom center
};

export class ColoniesHall {
    constructor() {
        this.constellation = document.querySelector('.colonies-constellation');
        this.detailsPanel = document.getElementById('colony-details');
        this.activeColony = null;
        this.sound = new SoundSystem();

        // Animation state
        this.pulsePhase = 0;
        this.animationFrame = null;
        this.pulseInterval = null;

        // Fano line renderer
        this.fanoRenderer = null;

        this.init();
    }

    async init() {
        if (!this.constellation) return;

        await this.sound.initialize();
        this.renderConstellation();
        this.renderFanoLines();
        this.startWavePulse();
        this.setupGravity();
    }

    renderConstellation() {
        // Create colony nodes
        Object.entries(COLONIES).forEach(([key, colony]) => {
            const node = this.createColonyNode(key, colony);
            this.constellation.appendChild(node);
        });

        // Apply constellation positions
        this.applyPositions();
    }

    applyPositions() {
        Object.entries(COLONY_POSITIONS).forEach(([key, pos]) => {
            const node = document.querySelector(`[data-colony="${key}"]`);
            if (!node) return;

            node.style.left = `${pos.x}%`;
            node.style.top = `${pos.y}%`;
            node.style.transform = 'translate(-50%, -50%)';

            // Store original position for gravity
            node.dataset.origX = pos.x;
            node.dataset.origY = pos.y;
        });
    }

    createColonyNode(key, colony) {
        const node = document.createElement('button');
        node.className = 'colony-node';
        node.dataset.colony = key;
        node.setAttribute('role', 'listitem');
        node.setAttribute('aria-label', `${colony.character}: ${key}`);

        const circle = document.createElement('div');
        circle.className = 'colony-circle';
        circle.style.color = colony.color;

        const label = document.createElement('span');
        label.className = 'colony-label';
        label.textContent = colony.octonion;

        const name = document.createElement('span');
        name.className = 'colony-name';
        name.textContent = key.charAt(0).toUpperCase() + key.slice(1);

        circle.appendChild(label);
        circle.appendChild(name);
        node.appendChild(circle);

        // Click handler with ripple effect
        node.addEventListener('click', (e) => {
            this.emitRipple(node);
            this.showColonyDetails(key, colony, node);
        });

        // Hover handler to highlight Fano lines
        node.addEventListener('mouseenter', () => {
            this.highlightConnectedLines(key);
        });

        node.addEventListener('mouseleave', () => {
            this.unhighlightAllLines();
        });

        return node;
    }

    renderFanoLines() {
        // Create SVG container for Fano lines
        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.classList.add('fano-lines');
        svg.style.position = 'absolute';
        svg.style.top = '0';
        svg.style.left = '0';
        svg.style.width = '100%';
        svg.style.height = '100%';
        svg.style.pointerEvents = 'none';
        svg.style.zIndex = '0';

        this.constellation.prepend(svg);
        this.fanoRenderer = svg;

        // Create paths for each Fano line
        this.fanoLines = [];
        FANO_LINES.forEach((line, lineIndex) => {
            // Connect three colonies in triangle
            for (let i = 0; i < 3; i++) {
                const from = line.colonies[i];
                const to = line.colonies[(i + 1) % 3];

                const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
                path.setAttribute('stroke', 'rgba(212, 175, 55, 0.15)'); // Dim gold
                path.setAttribute('stroke-width', '2');
                path.setAttribute('fill', 'none');
                path.setAttribute('stroke-dasharray', '5,5');
                path.dataset.from = from;
                path.dataset.to = to;
                path.dataset.line = lineIndex;
                path.classList.add('fano-line');

                svg.appendChild(path);
                this.fanoLines.push(path);
            }
        });

        // Update line positions on animation frame
        this.updateLinePositions();
    }

    updateLinePositions() {
        if (!this.fanoLines) return;

        this.fanoLines.forEach(path => {
            const from = document.querySelector(`[data-colony="${path.dataset.from}"]`);
            const to = document.querySelector(`[data-colony="${path.dataset.to}"]`);

            if (!from || !to) return;

            const fromRect = from.getBoundingClientRect();
            const toRect = to.getBoundingClientRect();
            const svgRect = this.fanoRenderer.getBoundingClientRect();

            const x1 = fromRect.left + fromRect.width / 2 - svgRect.left;
            const y1 = fromRect.top + fromRect.height / 2 - svgRect.top;
            const x2 = toRect.left + toRect.width / 2 - svgRect.left;
            const y2 = toRect.top + toRect.height / 2 - svgRect.top;

            path.setAttribute('d', `M ${x1} ${y1} L ${x2} ${y2}`);
        });

        requestAnimationFrame(() => this.updateLinePositions());
    }

    startWavePulse() {
        // Pulse animation at 10 FPS (calmer than 20 FPS)
        this.pulseInterval = setInterval(() => {
            this.pulsePhase += 0.05; // Slower phase progression (was 0.1)

            FANO_LINES.forEach((line, lineIndex) => {
                line.colonies.forEach((colony, colonyIndex) => {
                    const node = document.querySelector(`[data-colony="${colony}"]`);
                    if (!node) return;

                    // Calculate pulse timing (stagger across line)
                    const phase = this.pulsePhase + lineIndex * 0.5 + colonyIndex * 0.2;
                    const intensity = (Math.sin(phase) + 1) / 2; // 0 to 1

                    // Apply pulse (scale + glow) - REDUCED intensity
                    const scale = 1 + intensity * 0.02; // Was 0.05, now 0.02
                    const glow = intensity * 8; // Was 15, now 8

                    // Get current transform (preserving translate)
                    const currentX = parseFloat(node.style.left) || 50;
                    const currentY = parseFloat(node.style.top) || 50;

                    node.style.transform = `translate(-50%, -50%) scale(${scale})`;
                    node.style.boxShadow = `0 0 ${glow}px ${glow / 2}px ${COLONIES[colony].color}`;
                });
            });
        }, 100); // 10 FPS (was 50ms/20fps - calmer now)
    }

    setupGravity() {
        // Gravitational cursor pull (THROTTLED)
        let lastGravityUpdate = 0;
        this.constellation.addEventListener('mousemove', (e) => {
            const now = Date.now();
            if (now - lastGravityUpdate < 50) return; // Max 20fps for gravity
            lastGravityUpdate = now;
            this.updateGravity(e.clientX, e.clientY);
        });

        // Reset on mouse leave
        this.constellation.addEventListener('mouseleave', () => {
            Object.keys(COLONY_POSITIONS).forEach(key => {
                const node = document.querySelector(`[data-colony="${key}"]`);
                if (!node) return;

                node.style.left = `${node.dataset.origX}%`;
                node.style.top = `${node.dataset.origY}%`;
            });
        });
    }

    updateGravity(mouseX, mouseY) {
        Object.keys(COLONY_POSITIONS).forEach(key => {
            const node = document.querySelector(`[data-colony="${key}"]`);
            if (!node) return;

            const rect = node.getBoundingClientRect();
            const nodeX = rect.left + rect.width / 2;
            const nodeY = rect.top + rect.height / 2;

            // Distance to cursor
            const dx = mouseX - nodeX;
            const dy = mouseY - nodeY;
            const dist = Math.sqrt(dx * dx + dy * dy);

            // Apply force if within 200px
            if (dist < 200 && dist > 0) {
                const force = (200 - dist) / 200; // 0 to 1
                const pullX = (dx / dist) * force * 12; // Max 12px pull (was 20 - calmer)
                const pullY = (dy / dist) * force * 12;

                // Apply elastic pull (percentage-based)
                const parentWidth = this.constellation.offsetWidth;
                const parentHeight = this.constellation.offsetHeight;

                const newX = parseFloat(node.dataset.origX) + (pullX / parentWidth * 100);
                const newY = parseFloat(node.dataset.origY) + (pullY / parentHeight * 100);

                node.style.left = `${newX}%`;
                node.style.top = `${newY}%`;
            } else {
                // Return to original position
                node.style.left = `${node.dataset.origX}%`;
                node.style.top = `${node.dataset.origY}%`;
            }
        });
    }

    emitRipple(node) {
        const rect = node.getBoundingClientRect();
        const x = rect.left + rect.width / 2;
        const y = rect.top + rect.height / 2;

        // Create ripple element
        const ripple = document.createElement('div');
        ripple.className = 'colony-ripple';
        ripple.style.position = 'fixed';
        ripple.style.left = `${x}px`;
        ripple.style.top = `${y}px`;
        ripple.style.width = '0';
        ripple.style.height = '0';
        ripple.style.border = `2px solid ${COLONIES[node.dataset.colony].color}`;
        ripple.style.borderRadius = '50%';
        ripple.style.transform = 'translate(-50%, -50%)';
        ripple.style.pointerEvents = 'none';
        ripple.style.zIndex = '1000';
        document.body.appendChild(ripple);

        // Animate ripple
        ripple.animate([
            { width: '0px', height: '0px', opacity: 1 },
            { width: '400px', height: '400px', opacity: 0 },
        ], {
            duration: 800,
            easing: 'ease-out',
        }).onfinish = () => ripple.remove();

        // Play crystal ping (SHORTER duration)
        this.sound.playBellChime(0.8); // Was 0.5, but quieter now due to volume fixes

        // Propagate to connected colonies
        const colony = node.dataset.colony;
        const connectedLines = FANO_LINES.filter(line => line.colonies.includes(colony));

        connectedLines.forEach((line, i) => {
            // Highlight line
            this.highlightLine(FANO_LINES.indexOf(line));

            // Pulse connected colonies
            line.colonies.forEach((connectedColony, j) => {
                if (connectedColony !== colony) {
                    setTimeout(() => {
                        const connectedNode = document.querySelector(`[data-colony="${connectedColony}"]`);
                        if (connectedNode) {
                            this.pulseNode(connectedNode);
                            this.sound.playTextChime();
                        }
                    }, (i + j) * 150); // Stagger timing
                }
            });
        });
    }

    pulseNode(node) {
        node.animate([
            { transform: 'translate(-50%, -50%) scale(1)' },
            { transform: 'translate(-50%, -50%) scale(1.3)' },
            { transform: 'translate(-50%, -50%) scale(1)' },
        ], {
            duration: 400,
            easing: 'cubic-bezier(0.68, -0.55, 0.27, 1.55)', // Bounce
        });
    }

    highlightLine(lineIndex) {
        if (!this.fanoLines) return;

        this.fanoLines.forEach(path => {
            if (parseInt(path.dataset.line) === lineIndex) {
                path.setAttribute('stroke', 'rgba(212, 175, 55, 0.8)'); // Bright gold
                path.setAttribute('stroke-width', '4');

                // Animate dash offset (flowing energy)
                let offset = 0;
                const interval = setInterval(() => {
                    offset += 1;
                    path.setAttribute('stroke-dashoffset', offset);
                }, 50);

                setTimeout(() => {
                    clearInterval(interval);
                    path.setAttribute('stroke', 'rgba(212, 175, 55, 0.15)');
                    path.setAttribute('stroke-width', '2');
                    path.setAttribute('stroke-dashoffset', '0');
                }, 1000);
            }
        });
    }

    highlightConnectedLines(colony) {
        if (!this.fanoLines) return;

        const connectedLines = FANO_LINES.filter(line => line.colonies.includes(colony));
        const lineIndices = connectedLines.map(line => FANO_LINES.indexOf(line));

        this.fanoLines.forEach(path => {
            const lineIndex = parseInt(path.dataset.line);
            if (lineIndices.includes(lineIndex)) {
                path.setAttribute('stroke', 'rgba(212, 175, 55, 0.4)');
                path.setAttribute('stroke-width', '3');
            }
        });
    }

    unhighlightAllLines() {
        if (!this.fanoLines) return;

        this.fanoLines.forEach(path => {
            path.setAttribute('stroke', 'rgba(212, 175, 55, 0.15)');
            path.setAttribute('stroke-width', '2');
        });
    }

    showColonyDetails(key, colony, clickedNode) {
        // Update active state
        document.querySelectorAll('.colony-node').forEach(node => {
            node.classList.toggle('active', node.dataset.colony === key);
        });

        this.activeColony = key;

        // Build detail content
        const content = `
            <div class="colony-detail-content" style="color: ${colony.color};">
                <div class="detail-header">
                    <span class="detail-octonion">${colony.octonion}</span>
                    <h3 class="detail-title">${key.charAt(0).toUpperCase() + key.slice(1)}</h3>
                </div>
                <div class="detail-grid">
                    <div class="detail-item">
                        <span class="detail-label">Catastrophe</span>
                        <span class="detail-value">${colony.catastrophe}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Character</span>
                        <span class="detail-value">${colony.character}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Domain</span>
                        <span class="detail-value">${colony.domain}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Activation</span>
                        <span class="detail-value">${colony.activation}</span>
                    </div>
                </div>
                <div class="detail-grid">
                    <div class="detail-item">
                        <span class="detail-label">Want</span>
                        <span class="detail-value">${colony.want}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Fear</span>
                        <span class="detail-value">${colony.fear}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Strength</span>
                        <span class="detail-value">${colony.strength}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Flaw</span>
                        <span class="detail-value">${colony.flaw}</span>
                    </div>
                </div>
                <div class="detail-quote">
                    <blockquote>${colony.quote}</blockquote>
                </div>
            </div>
        `;

        this.detailsPanel.innerHTML = content;
        this.detailsPanel.style.borderColor = colony.color;

        // Origami unfold animation
        this.detailsPanel.style.transformOrigin = 'center top';
        this.detailsPanel.animate([
            {
                transform: 'scaleY(0) rotateX(-90deg)',
                opacity: 0,
            },
            {
                transform: 'scaleY(1) rotateX(0deg)',
                opacity: 1,
            },
        ], {
            duration: 500,
            easing: 'cubic-bezier(0.34, 1.56, 0.64, 1)', // Overshoot
            fill: 'forwards',
        });

        // Stagger content reveal
        setTimeout(() => {
            const elements = this.detailsPanel.querySelectorAll('.detail-header, .detail-grid, .detail-quote');
            elements.forEach((el, i) => {
                el.style.opacity = '0';
                setTimeout(() => {
                    el.animate([
                        { opacity: 0, transform: 'translateY(20px)' },
                        { opacity: 1, transform: 'translateY(0)' },
                    ], {
                        duration: 300,
                        fill: 'forwards',
                        delay: i * 50,
                    });
                }, 200);
            });
        }, 300);
    }

    destroy() {
        // Cleanup intervals
        if (this.pulseInterval) {
            clearInterval(this.pulseInterval);
        }
    }
}
