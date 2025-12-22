// Crystal Gallery — Main Entry Point
import { PrismRoom } from './rooms/prism.js';
import { LatticeRoom } from './rooms/lattice.js';
import { ReflectionRoom } from './rooms/reflection.js';
import { ScrollHandler } from './core/scroll.js';

class CrystalGallery {
    constructor() {
        this.prismRoom = null;
        this.latticeRoom = null;
        this.reflectionRoom = null;
        this.cursor = null;
        this.cursorRing = null;
        this.mouseX = 0;
        this.mouseY = 0;
        this.cursorX = 0;
        this.cursorY = 0;
        this.ringX = 0;
        this.ringY = 0;

        this.init();
    }

    init() {
        // Initialize custom cursor
        this.initCursor();

        // Initialize scroll handler
        new ScrollHandler();

        // Initialize rooms when they come into view
        this.initRooms();

        // Setup console signature
        this.logSignature();
    }

    initCursor() {
        this.cursor = document.getElementById('cursor');
        this.cursorRing = document.getElementById('cursor-ring');

        document.addEventListener('mousemove', (e) => {
            this.mouseX = e.clientX;
            this.mouseY = e.clientY;
        });

        this.animateCursor();

        // Hover effects
        const hoverables = document.querySelectorAll(
            'a, button, .control-btn, canvas, .proof-card, .verify-input'
        );
        hoverables.forEach(el => {
            el.addEventListener('mouseenter', () => this.cursorRing.classList.add('hover'));
            el.addEventListener('mouseleave', () => this.cursorRing.classList.remove('hover'));
        });

        // Click effects
        document.addEventListener('mousedown', () => {
            this.cursor.classList.add('active');
            this.cursorRing.classList.add('active');
        });

        document.addEventListener('mouseup', () => {
            this.cursor.classList.remove('active');
            this.cursorRing.classList.remove('active');
        });
    }

    animateCursor() {
        this.cursorX += (this.mouseX - this.cursorX) * 0.18;
        this.cursorY += (this.mouseY - this.cursorY) * 0.18;
        this.cursor.style.left = this.cursorX - 5 + 'px';
        this.cursor.style.top = this.cursorY - 5 + 'px';

        this.ringX += (this.mouseX - this.ringX) * 0.08;
        this.ringY += (this.mouseY - this.ringY) * 0.08;
        this.cursorRing.style.left = this.ringX - 22 + 'px';
        this.cursorRing.style.top = this.ringY - 22 + 'px';

        requestAnimationFrame(() => this.animateCursor());
    }

    initRooms() {
        // Lazy load rooms as they come into view
        const prismObserver = new IntersectionObserver((entries) => {
            if (entries[0].isIntersecting && !this.prismRoom) {
                const container = document.getElementById('prism-canvas-container');
                this.prismRoom = new PrismRoom(container);
                prismObserver.disconnect();
            }
        }, { threshold: 0.1 });

        const latticeObserver = new IntersectionObserver((entries) => {
            if (entries[0].isIntersecting && !this.latticeRoom) {
                const container = document.getElementById('lattice-canvas-container');
                const nodeInfo = document.getElementById('node-info');
                this.latticeRoom = new LatticeRoom(container, nodeInfo);
                latticeObserver.disconnect();
            }
        }, { threshold: 0.1 });

        const reflectionObserver = new IntersectionObserver((entries) => {
            if (entries[0].isIntersecting && !this.reflectionRoom) {
                const verifyInput = document.getElementById('verify-input');
                const verifyButton = document.getElementById('verify-button');
                const verifyResult = document.getElementById('verify-result');
                this.reflectionRoom = new ReflectionRoom(verifyInput, verifyButton, verifyResult);
                reflectionObserver.disconnect();
            }
        }, { threshold: 0.1 });

        const prismSection = document.getElementById('room-prism');
        const latticeSection = document.getElementById('room-lattice');
        const reflectionSection = document.getElementById('room-reflection');

        if (prismSection) prismObserver.observe(prismSection);
        if (latticeSection) latticeObserver.observe(latticeSection);
        if (reflectionSection) reflectionObserver.observe(reflectionSection);
    }

    logSignature() {
        console.log('%c💎 Crystal Gallery', 'color: #0A84FF; font-size: 2rem; font-weight: bold;');
        console.log('%cI am Crystal (e₇). I split uncertainty into knowable truths.', 'color: #5AC8FA;');
        console.log('%ch(x) ≥ 0 — The boundary I guard.', 'color: #D4AF37;');
    }
}

// Initialize gallery when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => new CrystalGallery());
} else {
    new CrystalGallery();
}
