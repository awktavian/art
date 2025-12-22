// ═══════════════════════════════════════════════════════════════════════════
// ROOM III: THE RECOVERY
// Error healing visualization
// Crystal-verified: Bug spawning, healing animation, debug log
// ═══════════════════════════════════════════════════════════════════════════

import { CONFIG, ERROR_TYPES, DEBUG_MESSAGES } from '../config.js';

export class RecoveryRoom {
    constructor(container, soundSystem = null) {
        this.container = container;
        this.sound = soundSystem;
        this.canvas = document.getElementById('recovery-canvas');
        this.ctx = this.canvas ? this.canvas.getContext('2d') : null;
        
        this.errors = [];
        this.healingWaves = [];
        this.animationId = null;
        this.time = 0;
        
        // UI elements
        this.spawnBtn = document.getElementById('spawn-error-btn');
        this.healBtn = document.getElementById('heal-btn');
        this.debugLog = document.getElementById('debug-log');
        this.errorPool = document.getElementById('error-pool');
        
        this.init();
    }
    
    init() {
        this.resizeCanvas();
        window.addEventListener('resize', () => this.resizeCanvas());
        
        // Button controls
        if (this.spawnBtn) {
            this.spawnBtn.addEventListener('click', () => this.spawnError());
        }
        
        if (this.healBtn) {
            this.healBtn.addEventListener('click', () => this.healAll());
        }
        
        // Start animation
        this.startAnimation();
        
        // Auto-spawn bugs periodically
        this.startAutoSpawn();
        
        console.log('💧 Recovery room initialized');
    }
    
    resizeCanvas() {
        if (this.canvas) {
            this.canvas.width = this.canvas.parentElement?.clientWidth || 800;
            this.canvas.height = 350;
        }
    }
    
    spawnError() {
        if (this.errors.length >= CONFIG.RECOVERY.MAX_ERRORS) {
            this.addLogEntry('[WARN] Error pool at capacity!', 'warn');
            return;
        }
        
        const errorType = ERROR_TYPES[Math.floor(Math.random() * ERROR_TYPES.length)];
        const x = 100 + Math.random() * ((this.canvas?.width || 600) - 200);
        const y = 100 + Math.random() * ((this.canvas?.height || 300) - 200);
        
        const error = {
            id: Date.now() + Math.random(),
            x: x,
            y: y,
            vx: (Math.random() - 0.5) * 2,
            vy: (Math.random() - 0.5) * 2,
            size: 15 + errorType.severity * 5,
            type: errorType,
            healing: false,
            healProgress: 0,
            wobble: Math.random() * Math.PI * 2,
        };
        
        this.errors.push(error);
        
        this.addLogEntry(`[ERROR] ${errorType.type} spawned at (${Math.round(x)}, ${Math.round(y)})`, 'error');
        
        if (this.sound && this.sound.initialized) {
            this.sound.playError();
        }
        
        // Add DOM element for the error
        this.createErrorElement(error);
    }
    
    createErrorElement(error) {
        if (!this.errorPool) return;
        
        const el = document.createElement('div');
        el.className = `error-bug severity-${error.type.severity}`;
        el.id = `error-${error.id}`;
        el.innerHTML = `<span class="bug-icon">🐛</span><span class="bug-label">${error.type.type}</span>`;
        el.style.cssText = `
            position: absolute;
            left: ${error.x}px;
            top: ${error.y}px;
            transform: translate(-50%, -50%);
            padding: 8px 12px;
            background: rgba(0, 0, 0, 0.8);
            border: 2px solid ${error.type.color};
            border-radius: 8px;
            color: ${error.type.color};
            font-family: 'Fira Code', monospace;
            font-size: 11px;
            cursor: pointer;
            transition: all 0.3s ease;
            box-shadow: 0 0 15px ${error.type.color}40;
        `;
        
        el.addEventListener('click', () => this.healError(error));
        
        this.errorPool.appendChild(el);
    }
    
    healError(error) {
        if (error.healing) return;
        
        error.healing = true;
        
        this.addLogEntry(`[HEAL] Fixing ${error.type.type}...`, 'heal');
        
        // Create healing wave
        this.healingWaves.push({
            x: error.x,
            y: error.y,
            radius: 0,
            maxRadius: 100,
            color: CONFIG.COLORS.HEALING_GREEN,
        });
        
        if (this.sound && this.sound.initialized) {
            this.sound.playHeal();
        }
        
        // Animate DOM element
        const el = document.getElementById(`error-${error.id}`);
        if (el) {
            el.style.borderColor = CONFIG.COLORS.HEALING_GREEN;
            el.style.color = CONFIG.COLORS.HEALING_GREEN;
            el.style.transform = 'translate(-50%, -50%) scale(0)';
            el.style.opacity = '0';
            
            setTimeout(() => {
                el.remove();
            }, 300);
        }
        
        // Remove from array after animation
        setTimeout(() => {
            const index = this.errors.indexOf(error);
            if (index > -1) {
                this.errors.splice(index, 1);
            }
            this.addLogEntry(`[SUCCESS] ${error.type.type} resolved.`, 'success');
        }, 300);
    }
    
    healAll() {
        if (this.errors.length === 0) {
            this.addLogEntry('[INFO] No errors to heal.', 'info');
            return;
        }
        
        this.addLogEntry('[HEAL] Initiating mass recovery...', 'heal');
        
        // Create central healing wave
        const centerX = (this.canvas?.width || 800) / 2;
        const centerY = (this.canvas?.height || 350) / 2;
        
        this.healingWaves.push({
            x: centerX,
            y: centerY,
            radius: 0,
            maxRadius: Math.max(this.canvas?.width || 800, this.canvas?.height || 350),
            color: CONFIG.COLORS.HEALING_GREEN,
        });
        
        if (this.sound && this.sound.initialized) {
            this.sound.playFlow();
        }
        
        // Heal all with delay
        [...this.errors].forEach((error, i) => {
            setTimeout(() => {
                this.healError(error);
            }, i * 100);
        });
    }
    
    addLogEntry(message, type = 'info') {
        if (!this.debugLog) return;
        
        const entry = document.createElement('div');
        entry.className = `log-entry ${type}`;
        entry.textContent = message;
        
        this.debugLog.appendChild(entry);
        this.debugLog.scrollTop = this.debugLog.scrollHeight;
        
        // Limit log entries
        while (this.debugLog.children.length > 50) {
            this.debugLog.removeChild(this.debugLog.firstChild);
        }
    }
    
    startAutoSpawn() {
        setInterval(() => {
            if (this.errors.length < 3 && Math.random() < 0.3) {
                this.spawnError();
            }
        }, CONFIG.RECOVERY.SPAWN_INTERVAL);
        
        // Random debug messages
        setInterval(() => {
            if (Math.random() < 0.2) {
                const msg = DEBUG_MESSAGES[Math.floor(Math.random() * DEBUG_MESSAGES.length)];
                this.addLogEntry(msg, 'debug');
            }
        }, 3000);
    }
    
    startAnimation() {
        const animate = () => {
            this.animationId = requestAnimationFrame(animate);
            this.time += 0.016;
            
            if (!this.ctx || !this.canvas) return;
            
            const ctx = this.ctx;
            const width = this.canvas.width;
            const height = this.canvas.height;
            
            if (width === 0 || height === 0) return;
            
            // Clear with fade
            ctx.fillStyle = 'rgba(10, 10, 15, 0.15)';
            ctx.fillRect(0, 0, width, height);
            
            // Draw flowing background
            ctx.strokeStyle = 'rgba(0, 206, 209, 0.03)';
            ctx.lineWidth = 1;
            
            for (let i = 0; i < 10; i++) {
                ctx.beginPath();
                const y = (i / 10) * height;
                const offset = Math.sin(this.time * 0.5 + i * 0.5) * 15;
                
                ctx.moveTo(0, y + offset);
                for (let x = 0; x <= width; x += 30) {
                    ctx.lineTo(x, y + offset + Math.sin(this.time + x * 0.02 + i) * 8);
                }
                ctx.stroke();
            }
            
            // Update error positions (subtle drift)
            this.errors.forEach(error => {
                if (!error.healing) {
                    error.wobble += 0.05;
                    error.x += Math.sin(error.wobble) * 0.5;
                    error.y += Math.cos(error.wobble * 0.7) * 0.3;
                    
                    // Update DOM element position
                    const el = document.getElementById(`error-${error.id}`);
                    if (el) {
                        el.style.left = `${error.x}px`;
                        el.style.top = `${error.y}px`;
                    }
                }
            });
            
            // Draw healing waves
            for (let i = this.healingWaves.length - 1; i >= 0; i--) {
                const wave = this.healingWaves[i];
                wave.radius += 5;
                
                const alpha = 1 - (wave.radius / wave.maxRadius);
                
                ctx.beginPath();
                ctx.arc(wave.x, wave.y, wave.radius, 0, Math.PI * 2);
                ctx.strokeStyle = this.hexToRgba(wave.color, alpha * 0.6);
                ctx.lineWidth = 3;
                ctx.stroke();
                
                // Inner glow
                const gradient = ctx.createRadialGradient(
                    wave.x, wave.y, wave.radius * 0.8,
                    wave.x, wave.y, wave.radius
                );
                gradient.addColorStop(0, 'transparent');
                gradient.addColorStop(1, this.hexToRgba(wave.color, alpha * 0.2));
                ctx.fillStyle = gradient;
                ctx.fill();
                
                if (wave.radius >= wave.maxRadius) {
                    this.healingWaves.splice(i, 1);
                }
            }
            
            // Draw connection lines between errors (bug network)
            if (this.errors.length > 1) {
                ctx.strokeStyle = 'rgba(255, 107, 107, 0.1)';
                ctx.lineWidth = 1;
                
                for (let i = 0; i < this.errors.length; i++) {
                    for (let j = i + 1; j < this.errors.length; j++) {
                        const e1 = this.errors[i];
                        const e2 = this.errors[j];
                        const dist = Math.hypot(e2.x - e1.x, e2.y - e1.y);
                        
                        if (dist < 200) {
                            ctx.beginPath();
                            ctx.moveTo(e1.x, e1.y);
                            ctx.lineTo(e2.x, e2.y);
                            ctx.stroke();
                        }
                    }
                }
            }
        };
        
        animate();
    }
    
    hexToRgba(hex, alpha) {
        const r = parseInt(hex.slice(1, 3), 16);
        const g = parseInt(hex.slice(3, 5), 16);
        const b = parseInt(hex.slice(5, 7), 16);
        return `rgba(${r}, ${g}, ${b}, ${alpha})`;
    }
    
    destroy() {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
        }
    }
}

