/**
 * Master of Puppets — Canvas Background
 * 
 * Particle system with audio reactivity
 * 
 * h(x) ≥ 0
 */

(function() {
    'use strict';

    const canvas = document.getElementById('fantasia-canvas');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    let width, height;
    let particles = [];
    let time = 0;
    let currentMovement = 0;

    // Movement colors (hue values)
    const MOVEMENT_HUES = [45, 0, 35, 30, 200];

    // =========================================================================
    // RESIZE
    // =========================================================================
    
    function resize() {
        width = canvas.width = window.innerWidth;
        height = canvas.height = window.innerHeight;
        initParticles();
    }

    // =========================================================================
    // PARTICLE CLASS
    // =========================================================================
    
    class Particle {
        constructor() {
            this.reset();
        }

        reset() {
            this.x = Math.random() * width;
            this.y = Math.random() * height;
            this.size = Math.random() * 2 + 0.5;
            this.speedX = (Math.random() - 0.5) * 0.3;
            this.speedY = (Math.random() - 0.5) * 0.3;
            this.opacity = Math.random() * 0.5 + 0.1;
            this.pulseSpeed = Math.random() * 0.02 + 0.01;
            this.pulseOffset = Math.random() * Math.PI * 2;
        }

        update() {
            this.x += this.speedX;
            this.y += this.speedY;

            // Wrap around screen
            if (this.x < 0) this.x = width;
            if (this.x > width) this.x = 0;
            if (this.y < 0) this.y = height;
            if (this.y > height) this.y = 0;
        }

        draw() {
            const pulse = Math.sin(time * this.pulseSpeed + this.pulseOffset) * 0.3 + 0.7;
            const hue = MOVEMENT_HUES[currentMovement] || 45;

            ctx.beginPath();
            ctx.arc(this.x, this.y, this.size * pulse, 0, Math.PI * 2);
            ctx.fillStyle = `hsla(${hue}, 70%, 60%, ${this.opacity * pulse})`;
            ctx.fill();
        }
    }

    // =========================================================================
    // INIT PARTICLES
    // =========================================================================
    
    function initParticles() {
        particles = [];
        const count = Math.min(100, Math.floor((width * height) / 20000));
        for (let i = 0; i < count; i++) {
            particles.push(new Particle());
        }
    }

    // =========================================================================
    // ANIMATION LOOP
    // =========================================================================
    
    function animate() {
        ctx.clearRect(0, 0, width, height);

        particles.forEach(p => {
            p.update();
            p.draw();
        });

        time++;
        requestAnimationFrame(animate);
    }

    // =========================================================================
    // TRACK CURRENT MOVEMENT
    // =========================================================================
    
    function updateMovement() {
        const movements = document.querySelectorAll('.movement, .overture');
        let newMovement = 0;

        movements.forEach((m, i) => {
            const rect = m.getBoundingClientRect();
            if (rect.top < window.innerHeight * 0.5) {
                newMovement = i;
            }
        });

        currentMovement = newMovement;
    }

    window.addEventListener('scroll', updateMovement, { passive: true });

    // =========================================================================
    // INIT
    // =========================================================================
    
    resize();
    window.addEventListener('resize', resize);

    // Only animate if user doesn't prefer reduced motion
    if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        animate();
    }

    console.log('✨ Canvas background initialized');

})();
