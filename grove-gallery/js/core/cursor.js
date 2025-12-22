// Custom Cursor System

import { CONFIG, COLORS } from '../config.js';

export class CustomCursor {
    constructor() {
        this.element = document.getElementById('custom-cursor');
        this.core = this.element?.querySelector('.cursor-core');
        this.glow = this.element?.querySelector('.cursor-glow');

        this.position = { x: 0, y: 0 };
        this.targetPosition = { x: 0, y: 0 };
        this.velocity = { x: 0, y: 0 };

        this.isHovering = false;
        this.isClicking = false;
        this.currentColony = null;

        this.init();
    }

    init() {
        if (!this.element) return;

        // Hide native cursor only on pointer devices
        if (window.matchMedia('(pointer: fine)').matches) {
            document.body.style.cursor = 'none';
        }

        // Mouse events
        document.addEventListener('mousemove', this.onMouseMove.bind(this));
        document.addEventListener('mousedown', this.onMouseDown.bind(this));
        document.addEventListener('mouseup', this.onMouseUp.bind(this));

        // Hover detection
        document.addEventListener('mouseover', this.onMouseOver.bind(this), true);
        document.addEventListener('mouseout', this.onMouseOut.bind(this), true);

        // Start animation loop
        this.animate();
    }

    onMouseMove(e) {
        this.targetPosition.x = e.clientX;
        this.targetPosition.y = e.clientY;
    }

    onMouseDown() {
        this.isClicking = true;
        this.element.classList.add('clicking');
    }

    onMouseUp() {
        this.isClicking = false;
        this.element.classList.remove('clicking');
    }

    onMouseOver(e) {
        const target = e.target;

        // Check if hovering over interactive element
        if (
            target.tagName === 'A' ||
            target.tagName === 'BUTTON' ||
            target.classList.contains('colony-node') ||
            target.classList.contains('fano-line-card') ||
            target.closest('a, button, .colony-node, .fano-line-card')
        ) {
            this.isHovering = true;
            this.element.classList.add('hovering');
        }

        // Check for colony-specific elements
        const colonyEl = target.closest('[data-colony]');
        if (colonyEl) {
            const colony = colonyEl.dataset.colony;
            this.setColony(colony);
        }
    }

    onMouseOut(e) {
        const target = e.target;
        const relatedTarget = e.relatedTarget;

        // Check if leaving interactive element
        if (
            target.tagName === 'A' ||
            target.tagName === 'BUTTON' ||
            target.classList.contains('colony-node') ||
            target.classList.contains('fano-line-card')
        ) {
            // Only remove hover state if not moving to another interactive element
            if (
                !relatedTarget ||
                (
                    relatedTarget.tagName !== 'A' &&
                    relatedTarget.tagName !== 'BUTTON' &&
                    !relatedTarget.classList.contains('colony-node') &&
                    !relatedTarget.classList.contains('fano-line-card') &&
                    !relatedTarget.closest('a, button, .colony-node, .fano-line-card')
                )
            ) {
                this.isHovering = false;
                this.element.classList.remove('hovering');
            }
        }

        // Clear colony if leaving colony element
        const colonyEl = target.closest('[data-colony]');
        if (colonyEl && !relatedTarget?.closest('[data-colony]')) {
            this.clearColony();
        }
    }

    setColony(colony) {
        if (this.currentColony !== colony) {
            this.currentColony = colony;
            this.element.dataset.colony = colony;
        }
    }

    clearColony() {
        this.currentColony = null;
        delete this.element.dataset.colony;
    }

    animate() {
        // Smooth follow with easing
        const ease = 0.15;

        this.position.x += (this.targetPosition.x - this.position.x) * ease;
        this.position.y += (this.targetPosition.y - this.position.y) * ease;

        // Calculate velocity
        this.velocity.x = this.targetPosition.x - this.position.x;
        this.velocity.y = this.targetPosition.y - this.position.y;

        // Update position
        if (this.core && this.glow) {
            this.core.style.left = `${this.position.x}px`;
            this.core.style.top = `${this.position.y}px`;
            this.glow.style.left = `${this.position.x}px`;
            this.glow.style.top = `${this.position.y}px`;
        }

        requestAnimationFrame(this.animate.bind(this));
    }

    getPosition() {
        return { ...this.position };
    }

    getVelocity() {
        return { ...this.velocity };
    }

    hide() {
        this.element?.classList.add('hidden');
    }

    show() {
        this.element?.classList.remove('hidden');
    }
}
