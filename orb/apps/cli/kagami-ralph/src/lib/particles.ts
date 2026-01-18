/**
 * Particle effects for 111/100 Crystal polish
 * 
 * Adds visual delight on Byzantine consensus.
 */

export interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  life: number;
  maxLife: number;
  color: string;
  size: number;
}

export class ParticleSystem {
  private particles: Particle[] = [];
  private canvas: HTMLCanvasElement | null = null;
  private ctx: CanvasRenderingContext2D | null = null;
  private animationFrame: number | null = null;
  
  constructor() {
    this.createCanvas();
  }
  
  private createCanvas(): void {
    this.canvas = document.createElement('canvas');
    this.canvas.style.position = 'fixed';
    this.canvas.style.top = '0';
    this.canvas.style.left = '0';
    this.canvas.style.width = '100%';
    this.canvas.style.height = '100%';
    this.canvas.style.pointerEvents = 'none';
    this.canvas.style.zIndex = '9999';
    
    document.body.appendChild(this.canvas);
    
    this.ctx = this.canvas.getContext('2d');
    this.resize();
    
    window.addEventListener('resize', () => this.resize());
  }
  
  private resize(): void {
    if (!this.canvas) return;
    this.canvas.width = window.innerWidth;
    this.canvas.height = window.innerHeight;
  }
  
  /**
   * Emit particles at consensus moment
   */
  emitConsensusParticles(x: number, y: number, approved: boolean): void {
    const color = approved ? '#00FF88' : '#FF4444';
    const count = approved ? 50 : 30;
    
    for (let i = 0; i < count; i++) {
      const angle = (Math.PI * 2 * i) / count;
      const speed = 2 + Math.random() * 3;
      
      this.particles.push({
        x,
        y,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed,
        life: 1.0,
        maxLife: 1.0,
        color,
        size: 2 + Math.random() * 3,
      });
    }
    
    if (!this.animationFrame) {
      this.animate();
    }
  }
  
  /**
   * Emit sparkles for agent activity
   */
  emitAgentSparkle(x: number, y: number, status: string): void {
    const colors: Record<string, string> = {
      success: '#00FF88',
      thinking: '#FFD700',
      running: '#67D4E4',
      error: '#FF4444',
    };
    
    const color = colors[status] || '#67D4E4';
    
    for (let i = 0; i < 5; i++) {
      this.particles.push({
        x: x + (Math.random() - 0.5) * 20,
        y: y + (Math.random() - 0.5) * 20,
        vx: (Math.random() - 0.5) * 2,
        vy: -Math.random() * 2,
        life: 1.0,
        maxLife: 1.0,
        color,
        size: 1 + Math.random() * 2,
      });
    }
    
    if (!this.animationFrame) {
      this.animate();
    }
  }
  
  private animate(): void {
    if (!this.ctx || !this.canvas) return;
    
    // Clear
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    
    // Update and draw particles
    this.particles = this.particles.filter((p) => {
      // Update physics
      p.x += p.vx;
      p.y += p.vy;
      p.vy += 0.1; // Gravity
      p.life -= 0.02;
      
      // Draw
      if (this.ctx && p.life > 0) {
        this.ctx.fillStyle = p.color;
        this.ctx.globalAlpha = p.life;
        this.ctx.beginPath();
        this.ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        this.ctx.fill();
      }
      
      return p.life > 0;
    });
    
    // Continue if particles remain
    if (this.particles.length > 0) {
      this.animationFrame = requestAnimationFrame(() => this.animate());
    } else {
      this.animationFrame = null;
    }
  }
  
  destroy(): void {
    if (this.animationFrame) {
      cancelAnimationFrame(this.animationFrame);
    }
    if (this.canvas) {
      this.canvas.remove();
    }
  }
}
