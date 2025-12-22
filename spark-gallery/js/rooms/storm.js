// ═══════════════════════════════════════════════════════════════════════════
// ROOM II: THE STORM
// Ideas colliding, combining, mutating in chaos
// Crystal-verified: DOM particles, collision detection, vortex visualization
// ═══════════════════════════════════════════════════════════════════════════

import { CONFIG, IDEA_BANK } from '../config.js';

export class StormRoom {
    constructor(container, soundSystem = null) {
        this.container = container;
        this.sound = soundSystem;
        this.canvas = document.getElementById('storm-canvas');
        this.ctx = this.canvas ? this.canvas.getContext('2d') : null;
        this.ideaCloud = document.getElementById('idea-cloud');
        
        this.ideas = [];
        this.collisionCount = 0;
        this.fusionCount = 0;
        this.animationId = null;
        this.autoSpawnInterval = null;
        this.isVisible = false;
        
        this.init();
    }
    
    init() {
        this.resizeCanvas();
        window.addEventListener('resize', () => this.resizeCanvas());
        
        // IntersectionObserver for visibility
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                this.isVisible = entry.isIntersecting;
                if (this.isVisible && this.ideas.length === 0) {
                    // Auto-spawn some ideas when first visible
                    setTimeout(() => this.spawnIdeas(8), 500);
                }
            });
        }, { threshold: 0.3 });
        
        if (this.container) {
            observer.observe(this.container);
        }
        
        // Button listeners
        const spawnBtn = document.getElementById('spawn-btn');
        const clearBtn = document.getElementById('clear-btn');
        
        if (spawnBtn) {
            spawnBtn.addEventListener('click', () => this.spawnIdeas(5));
        }
        
        if (clearBtn) {
            clearBtn.addEventListener('click', () => this.clearStorm());
        }
        
        // Click on canvas to spawn ideas at location
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
        this.startAutoSpawn();
        
        console.log('⚡ Storm room initialized');
    }
    
    resizeCanvas() {
        if (this.canvas) {
            const container = this.canvas.parentElement;
            this.canvas.width = Math.max(container?.clientWidth || 800, 400);
            this.canvas.height = 500;
        }
    }
    
    spawnIdeas(count = 5) {
        if (!this.canvas) return;
        
        for (let i = 0; i < count; i++) {
            // Remove oldest if at capacity
            if (this.ideas.length >= CONFIG.STORM.MAX_IDEAS) {
                this.removeIdea(0);
            }
            
            const x = 100 + Math.random() * (this.canvas.width - 200);
            const y = 100 + Math.random() * (this.canvas.height - 200);
            
            this.spawnIdeaAt(x, y);
        }
        
        if (this.sound && this.sound.initialized) {
            this.sound.playSpawn();
        }
    }
    
    spawnIdeaAt(x, y) {
        if (!this.ideaCloud) return;
        
        // Remove oldest if at capacity
        if (this.ideas.length >= CONFIG.STORM.MAX_IDEAS) {
            this.removeIdea(0);
        }
        
        const word = IDEA_BANK[Math.floor(Math.random() * IDEA_BANK.length)];
        
        const idea = {
            x: x,
            y: y,
            vx: (Math.random() - 0.5) * CONFIG.STORM.BASE_VELOCITY * 2,
            vy: (Math.random() - 0.5) * CONFIG.STORM.BASE_VELOCITY * 2,
            word: word,
            element: null,
            radius: 30 + word.length * 3,
            color: this.getRandomColor(),
            age: 0,
        };
        
        // Create DOM element
        const el = document.createElement('span');
        el.className = 'idea-word';
        el.textContent = word;
        el.style.left = x + 'px';
        el.style.top = y + 'px';
        el.style.color = idea.color;
        el.style.fontSize = (0.9 + Math.random() * 0.6) + 'rem';
        el.style.textShadow = `0 0 15px ${idea.color}`;
        
        this.ideaCloud.appendChild(el);
        idea.element = el;
        
        // Entry animation
        el.style.opacity = '0';
        el.style.transform = 'scale(0.3)';
        requestAnimationFrame(() => {
            el.style.transition = 'opacity 0.4s ease-out, transform 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275)';
            el.style.opacity = '1';
            el.style.transform = 'scale(1)';
        });
        
        this.ideas.push(idea);
        this.updateStats();
    }
    
    removeIdea(index) {
        const idea = this.ideas[index];
        if (idea && idea.element) {
            idea.element.style.transition = 'opacity 0.3s, transform 0.3s';
            idea.element.style.opacity = '0';
            idea.element.style.transform = 'scale(0.5)';
            setTimeout(() => {
                idea.element.remove();
            }, 300);
        }
        this.ideas.splice(index, 1);
    }
    
    clearStorm() {
        // Animate all ideas out
        this.ideas.forEach((idea, i) => {
            if (idea.element) {
                idea.element.style.transition = 'all 0.5s cubic-bezier(0.55, 0.085, 0.68, 0.53)';
                idea.element.style.opacity = '0';
                idea.element.style.transform = `scale(0) translateY(${-50 - i * 10}px)`;
            }
        });
        
        setTimeout(() => {
            this.ideas.forEach(idea => {
                if (idea.element) {
                    idea.element.remove();
                }
            });
            this.ideas = [];
            this.collisionCount = 0;
            this.fusionCount = 0;
            this.updateStats();
        }, 500);
    }
    
    getRandomColor() {
        const colors = [
            CONFIG.COLORS.FLAME,
            CONFIG.COLORS.GOLD,
            CONFIG.COLORS.YELLOW,
            CONFIG.COLORS.ELECTRIC,
            CONFIG.COLORS.PLASMA,
        ];
        return colors[Math.floor(Math.random() * colors.length)];
    }
    
    checkCollisions() {
        for (let i = 0; i < this.ideas.length; i++) {
            for (let j = i + 1; j < this.ideas.length; j++) {
                const a = this.ideas[i];
                const b = this.ideas[j];
                
                const dx = b.x - a.x;
                const dy = b.y - a.y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                const minDist = (a.radius + b.radius) * 0.6;
                
                if (dist < minDist && dist > 0) {
                    // Collision!
                    this.collisionCount++;
                    this.updateStats();
                    
                    // Bounce physics
                    const angle = Math.atan2(dy, dx);
                    const speed = Math.sqrt(a.vx * a.vx + a.vy * a.vy);
                    
                    a.vx = -Math.cos(angle) * speed * 1.1;
                    a.vy = -Math.sin(angle) * speed * 1.1;
                    b.vx = Math.cos(angle) * speed * 1.1;
                    b.vy = Math.sin(angle) * speed * 1.1;
                    
                    // Visual feedback
                    if (a.element) {
                        a.element.classList.add('colliding');
                        setTimeout(() => a.element?.classList.remove('colliding'), 300);
                    }
                    if (b.element) {
                        b.element.classList.add('colliding');
                        setTimeout(() => b.element?.classList.remove('colliding'), 300);
                    }
                    
                    // Play collision sound
                    if (this.sound && this.sound.initialized && Math.random() < 0.3) {
                        this.sound.playCollision();
                    }
                    
                    // Chance of fusion
                    if (Math.random() < 0.05) {
                        this.fusionCount++;
                        // Fusion visual: flash white
                        if (a.element) {
                            a.element.style.color = CONFIG.COLORS.WHITE_HOT;
                            a.element.style.textShadow = `0 0 30px ${CONFIG.COLORS.WHITE_HOT}`;
                            setTimeout(() => {
                                if (a.element) {
                                    a.element.style.color = a.color;
                                    a.element.style.textShadow = `0 0 15px ${a.color}`;
                                }
                            }, 400);
                        }
                    }
                }
            }
        }
    }
    
    startAnimation() {
        const animate = () => {
            this.animationId = requestAnimationFrame(animate);
            
            if (!this.ctx || !this.canvas || !this.isVisible) return;
            
            const ctx = this.ctx;
            const width = this.canvas.width;
            const height = this.canvas.height;
            
            if (width === 0 || height === 0) return;
            
            // Clear
            ctx.fillStyle = 'rgba(5, 5, 5, 0.15)';
            ctx.fillRect(0, 0, width, height);
            
            // Draw vortex center
            const cx = width / 2;
            const cy = height / 2;
            this.drawVortex(ctx, cx, cy, width, height);
            
            // Update idea positions
            this.ideas.forEach((idea, index) => {
                idea.age++;
                
                // Vortex attraction (gentle spiral)
                const dx = cx - idea.x;
                const dy = cy - idea.y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                
                if (dist > 50) {
                    const attraction = 0.0004;
                    idea.vx += dx * attraction;
                    idea.vy += dy * attraction;
                    
                    // Tangential force for spiral
                    const tangent = 0.0002;
                    idea.vx += -dy * tangent;
                    idea.vy += dx * tangent;
                }
                
                // Apply velocity
                idea.x += idea.vx;
                idea.y += idea.vy;
                
                // Damping
                idea.vx *= 0.995;
                idea.vy *= 0.995;
                
                // Bounce off walls
                const margin = 50;
                if (idea.x < margin) { idea.x = margin; idea.vx *= -0.8; }
                if (idea.x > width - margin) { idea.x = width - margin; idea.vx *= -0.8; }
                if (idea.y < margin) { idea.y = margin; idea.vy *= -0.8; }
                if (idea.y > height - margin) { idea.y = height - margin; idea.vy *= -0.8; }
                
                // Update DOM position
                if (idea.element) {
                    idea.element.style.left = idea.x + 'px';
                    idea.element.style.top = idea.y + 'px';
                }
            });
            
            // Check collisions
            this.checkCollisions();
        };
        
        animate();
    }
    
    drawVortex(ctx, cx, cy, width, height) {
        const time = Date.now() / 1000;
        
        // Multiple spiral arms
        for (let arm = 0; arm < 4; arm++) {
            const armOffset = (Math.PI * 2 * arm) / 4;
            
            ctx.beginPath();
            ctx.strokeStyle = `rgba(255, 69, 0, ${0.08 + arm * 0.02})`;
            ctx.lineWidth = 1.5;
            
            for (let i = 0; i < 120; i++) {
                const angle = i * 0.1 + time * 0.3 + armOffset;
                const radius = 10 + i * 2.5;
                const x = cx + Math.cos(angle) * radius;
                const y = cy + Math.sin(angle) * radius;
                
                if (i === 0) {
                    ctx.moveTo(x, y);
                } else {
                    ctx.lineTo(x, y);
                }
            }
            
            ctx.stroke();
        }
        
        // Center glow
        const gradient = ctx.createRadialGradient(cx, cy, 0, cx, cy, 80);
        gradient.addColorStop(0, 'rgba(255, 69, 0, 0.15)');
        gradient.addColorStop(0.5, 'rgba(255, 215, 0, 0.05)');
        gradient.addColorStop(1, 'transparent');
        
        ctx.beginPath();
        ctx.arc(cx, cy, 80, 0, Math.PI * 2);
        ctx.fillStyle = gradient;
        ctx.fill();
        
        // Pulsing core
        const pulse = 1 + Math.sin(time * 3) * 0.2;
        ctx.beginPath();
        ctx.arc(cx, cy, 8 * pulse, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(255, 215, 0, ${0.4 + Math.sin(time * 3) * 0.2})`;
        ctx.fill();
    }
    
    startAutoSpawn() {
        // Periodically spawn new ideas
        this.autoSpawnInterval = setInterval(() => {
            if (this.isVisible && this.ideas.length < CONFIG.STORM.MAX_IDEAS * 0.6) {
                this.spawnIdeas(1);
            }
        }, 4000);
    }
    
    updateStats() {
        const ideaCountEl = document.getElementById('idea-count');
        const collisionCountEl = document.getElementById('collision-count');
        const fusionCountEl = document.getElementById('fusion-count');
        
        if (ideaCountEl) ideaCountEl.textContent = this.ideas.length;
        if (collisionCountEl) collisionCountEl.textContent = this.collisionCount;
        if (fusionCountEl) fusionCountEl.textContent = this.fusionCount;
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
