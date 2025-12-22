// ═══════════════════════════════════════════════════════════════════════════
// ROOM IV: THE CONSTRUCT
// Forge's psychology and the art of building
// Crystal-verified: Psychological profile, code rain effect
// ═══════════════════════════════════════════════════════════════════════════

import { CONFIG, CODE_FRAGMENTS } from '../config.js';

export class ConstructRoom {
    constructor(container, soundSystem = null) {
        this.container = container;
        this.sound = soundSystem;
        this.animationId = null;
        this.time = 0;
        
        // Code rain effect
        this.codeRain = [];
        
        this.init();
    }
    
    init() {
        // Animate psychology cards on scroll
        this.setupScrollAnimations();
        
        // Trait hover effects
        this.setupTraitEffects();
        
        // Start code rain background
        this.startCodeRain();
        
        console.log('🏗️ Construct room initialized');
    }
    
    setupScrollAnimations() {
        const cards = this.container?.querySelectorAll('.psych-card');
        
        if (!cards || cards.length === 0) return;
        
        const observer = new IntersectionObserver((entries) => {
            entries.forEach((entry, index) => {
                if (entry.isIntersecting) {
                    setTimeout(() => {
                        entry.target.classList.add('visible');
                    }, index * 150);
                }
            });
        }, { threshold: 0.2 });
        
        cards.forEach(card => observer.observe(card));
    }
    
    setupTraitEffects() {
        const traits = this.container?.querySelectorAll('.trait');
        
        if (!traits || traits.length === 0) return;
        
        traits.forEach(trait => {
            trait.addEventListener('mouseenter', () => {
                if (this.sound && this.sound.initialized) {
                    this.sound.playCuspTransition(Math.random() * 2 - 1);
                }
            });
        });
    }
    
    startCodeRain() {
        // Create floating code fragments
        const container = this.container?.querySelector('.construct-content');
        if (!container) return;
        
        // Create canvas for code rain
        const canvas = document.createElement('canvas');
        canvas.className = 'code-rain-canvas';
        canvas.style.cssText = `
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            opacity: 0.15;
        `;
        container.style.position = 'relative';
        container.insertBefore(canvas, container.firstChild);
        
        const ctx = canvas.getContext('2d');
        
        const resize = () => {
            canvas.width = container.clientWidth;
            canvas.height = container.clientHeight;
        };
        resize();
        window.addEventListener('resize', resize);
        
        // Initialize code drops
        const columns = Math.floor(canvas.width / 20);
        const drops = [];
        
        for (let i = 0; i < columns; i++) {
            drops[i] = Math.random() * -100;
        }
        
        const animate = () => {
            this.animationId = requestAnimationFrame(animate);
            
            if (canvas.width === 0 || canvas.height === 0) return;
            
            // Fade effect
            ctx.fillStyle = 'rgba(10, 10, 10, 0.05)';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            
            ctx.fillStyle = CONFIG.COLORS.MOLTEN;
            ctx.font = '14px "JetBrains Mono", monospace';
            
            for (let i = 0; i < drops.length; i++) {
                // Random character from code fragments
                const fragment = CODE_FRAGMENTS[Math.floor(Math.random() * CODE_FRAGMENTS.length)];
                const char = fragment[Math.floor(Math.random() * fragment.length)];
                
                const x = i * 20;
                const y = drops[i] * 20;
                
                ctx.fillText(char, x, y);
                
                // Reset drop
                if (y > canvas.height && Math.random() > 0.975) {
                    drops[i] = 0;
                }
                drops[i]++;
            }
        };
        
        animate();
    }
    
    destroy() {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
        }
    }
}

