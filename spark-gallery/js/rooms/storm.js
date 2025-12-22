// ═══════════════════════════════════════════════════════════════════════════
// ROOM II: THE STORM
// Ideas swirl, collide, and combine. Chaos is the process.
// ═══════════════════════════════════════════════════════════════════════════

import { CONFIG, IDEA_BANK } from '../config.js';

export class StormRoom {
    constructor(container, soundSystem = null) {
        this.container = container;
        this.sound = soundSystem;
        this.canvas = document.getElementById('storm-canvas');
        this.ctx = this.canvas ? this.canvas.getContext('2d') : null;
        this.ideaCloud = document.getElementById('idea-cloud');
        this.ideaCountEl = document.getElementById('idea-count');
        this.collisionCountEl = document.getElementById('collision-count');
        
        this.ideas = [];
        this.ideaCount = 0;
        this.collisionCount = 0;
        this.vortexAngle = 0;
        this.animationId = null;
        this.autoSpawnInterval = null;
        
        this.init();
    }
    
    init() {
        this.resizeCanvas();
        window.addEventListener('resize', () => this.resizeCanvas());
        
        // Button listeners
        const spawnBtn = document.getElementById('spawn-ideas');
        const clearBtn = document.getElementById('clear-storm');
        
        if (spawnBtn) {
            spawnBtn.addEventListener('click', () => this.spawnIdeas(10));
        }
        
        if (clearBtn) {
            clearBtn.addEventListener('click', () => this.clearStorm());
        }
        
        // Click to spawn individual ideas
        if (this.canvas) {
            this.canvas.addEventListener('click', (e) => {
                const rect = this.canvas.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const y = e.clientY - rect.top;
                this.spawnIdeaAt(x, y);
            });
        }
        
        // Start animation
        this.startAnimation();
        
        // Auto-spawn ideas periodically
        this.startAutoSpawn();
    }
    
    resizeCanvas() {
        if (this.canvas) {
            const container = this.canvas.parentElement;
            this.canvas.width = container.clientWidth;
            this.canvas.height = container.clientHeight;
        }
    }
    
    spawnIdeas(count = 5) {
        for (let i = 0; i < count; i++) {
            setTimeout(() => {
                const x = Math.random() * this.canvas.width;
                const y = Math.random() * this.canvas.height;
                this.spawnIdeaAt(x, y);
            }, i * 100);
        }
    }
    
    spawnIdeaAt(x, y) {
        if (this.ideas.length >= CONFIG.STORM.MAX_IDEAS) {
            // Remove oldest idea
            this.removeIdea(0);
        }
        
        const text = IDEA_BANK[Math.floor(Math.random() * IDEA_BANK.length)];
        const colorClass = CONFIG.STORM.COLORS[Math.floor(Math.random() * CONFIG.STORM.COLORS.length)];
        const size = 0.8 + Math.random() * 1.5;
        
        // Calculate vortex velocity (spiral motion)
        const centerX = this.canvas.width / 2;
        const centerY = this.canvas.height / 2;
        const angle = Math.atan2(y - centerY, x - centerX);
        const tangent = angle + Math.PI / 2;
        const speed = 0.5 + Math.random() * 1.5;
        
        const idea = {
            id: this.ideaCount++,
            text: text,
            x: x,
            y: y,
            vx: Math.cos(tangent) * speed + (Math.random() - 0.5) * 0.5,
            vy: Math.sin(tangent) * speed + (Math.random() - 0.5) * 0.5,
            size: size,
            colorClass: colorClass,
            opacity: 0,
            life: 10000 + Math.random() * 5000,
            element: null,
        };
        
        // Create DOM element
        const el = document.createElement('div');
        el.className = `idea-word ${colorClass}`;
        el.textContent = text;
        el.style.cssText = `
            --idea-size: ${size}rem;
            left: ${x}px;
            top: ${y}px;
            font-size: ${size}rem;
        `;
        this.ideaCloud.appendChild(el);
        idea.element = el;
        
        this.ideas.push(idea);
        this.updateStats();
        
        // Play spawn sound
        if (this.sound) {
            this.sound.playSpawn();
        }
        
        // Fade in
        requestAnimationFrame(() => {
            el.style.opacity = '0.8';
        });
    }
    
    removeIdea(index) {
        const idea = this.ideas[index];
        if (idea.element) {
            idea.element.remove();
        }
        this.ideas.splice(index, 1);
    }
    
    clearStorm() {
        // Remove all ideas with animation
        this.ideas.forEach((idea, i) => {
            setTimeout(() => {
                if (idea.element) {
                    idea.element.classList.add('collision');
                    setTimeout(() => idea.element.remove(), 500);
                }
            }, i * 50);
        });
        
        this.ideas = [];
        this.ideaCount = 0;
        this.collisionCount = 0;
        this.updateStats();
    }
    
    checkCollisions() {
        for (let i = 0; i < this.ideas.length; i++) {
            for (let j = i + 1; j < this.ideas.length; j++) {
                const a = this.ideas[i];
                const b = this.ideas[j];
                
                const dx = a.x - b.x;
                const dy = a.y - b.y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                const minDist = (a.size + b.size) * 20;
                
                if (dist < minDist) {
                    // Collision!
                    this.collisionCount++;
                    this.updateStats();
                    
                    // Play collision sound
                    if (this.sound) {
                        this.sound.playCollision();
                    }
                    
                    // Bounce
                    const angle = Math.atan2(dy, dx);
                    const force = 2;
                    a.vx += Math.cos(angle) * force;
                    a.vy += Math.sin(angle) * force;
                    b.vx -= Math.cos(angle) * force;
                    b.vy -= Math.sin(angle) * force;
                    
                    // Visual feedback
                    if (a.element) a.element.style.transform = 'scale(1.3)';
                    if (b.element) b.element.style.transform = 'scale(1.3)';
                    setTimeout(() => {
                        if (a.element) a.element.style.transform = '';
                        if (b.element) b.element.style.transform = '';
                    }, 200);
                }
            }
        }
    }
    
    startAnimation() {
        const animate = () => {
            this.animationId = requestAnimationFrame(animate);
            
            if (!this.ctx) return;
            
            const width = this.canvas.width;
            const height = this.canvas.height;
            const centerX = width / 2;
            const centerY = height / 2;
            
            // Clear
            this.ctx.fillStyle = 'rgba(10, 10, 10, 0.1)';
            this.ctx.fillRect(0, 0, width, height);
            
            // Draw vortex
            this.vortexAngle += 0.01;
            this.drawVortex(centerX, centerY);
            
            // Update ideas
            for (let i = this.ideas.length - 1; i >= 0; i--) {
                const idea = this.ideas[i];
                
                // Vortex force
                const dx = idea.x - centerX;
                const dy = idea.y - centerY;
                const dist = Math.sqrt(dx * dx + dy * dy);
                const angle = Math.atan2(dy, dx);
                const tangent = angle + Math.PI / 2;
                
                // Spiral inward slightly
                const spiralForce = 0.001;
                const tangentForce = 0.02;
                
                idea.vx += Math.cos(tangent) * tangentForce - dx * spiralForce / Math.max(dist, 1);
                idea.vy += Math.sin(tangent) * tangentForce - dy * spiralForce / Math.max(dist, 1);
                
                // Apply velocity
                idea.x += idea.vx;
                idea.y += idea.vy;
                
                // Friction
                idea.vx *= 0.99;
                idea.vy *= 0.99;
                
                // Boundary wrapping
                if (idea.x < 0) idea.x = width;
                if (idea.x > width) idea.x = 0;
                if (idea.y < 0) idea.y = height;
                if (idea.y > height) idea.y = 0;
                
                // Update DOM position
                if (idea.element) {
                    idea.element.style.left = `${idea.x}px`;
                    idea.element.style.top = `${idea.y}px`;
                }
                
                // Age
                idea.life -= 16;
                if (idea.life <= 0) {
                    this.removeIdea(i);
                    this.updateStats();
                }
            }
            
            // Check collisions
            this.checkCollisions();
        };
        
        animate();
    }
    
    drawVortex(cx, cy) {
        const ctx = this.ctx;
        
        // Draw spiral arms
        for (let arm = 0; arm < 3; arm++) {
            ctx.beginPath();
            const armOffset = (arm / 3) * Math.PI * 2;
            
            for (let i = 0; i < 200; i++) {
                const angle = this.vortexAngle + armOffset + i * 0.1;
                const radius = 10 + i * 2;
                const x = cx + Math.cos(angle) * radius;
                const y = cy + Math.sin(angle) * radius;
                
                if (i === 0) {
                    ctx.moveTo(x, y);
                } else {
                    ctx.lineTo(x, y);
                }
            }
            
            ctx.strokeStyle = `rgba(255, 69, 0, ${0.1 - arm * 0.03})`;
            ctx.lineWidth = 2;
            ctx.stroke();
        }
    }
    
    startAutoSpawn() {
        this.autoSpawnInterval = setInterval(() => {
            if (this.ideas.length < CONFIG.STORM.MAX_IDEAS / 2) {
                const x = this.canvas.width * (0.2 + Math.random() * 0.6);
                const y = this.canvas.height * (0.2 + Math.random() * 0.6);
                this.spawnIdeaAt(x, y);
            }
        }, CONFIG.STORM.SPAWN_RATE * 2);
    }
    
    updateStats() {
        if (this.ideaCountEl) {
            this.ideaCountEl.textContent = this.ideas.length;
        }
        if (this.collisionCountEl) {
            this.collisionCountEl.textContent = this.collisionCount;
        }
    }
    
    destroy() {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
        }
        if (this.autoSpawnInterval) {
            clearInterval(this.autoSpawnInterval);
        }
    }
}

