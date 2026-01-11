/**
 * Kagami Orb — The Floating Mirror
 * Interactive showcase JavaScript
 */

// ==================== CURSOR ====================
const cursor = document.querySelector('.cursor');
const cursorDot = document.querySelector('.cursor-dot');
let mouseX = 0, mouseY = 0, cursorX = 0, cursorY = 0;

document.addEventListener('mousemove', e => {
    mouseX = e.clientX;
    mouseY = e.clientY;
});

function animateCursor() {
    cursorX += (mouseX - cursorX) * 0.1;
    cursorY += (mouseY - cursorY) * 0.1;
    cursor.style.left = cursorX - 16 + 'px';
    cursor.style.top = cursorY - 16 + 'px';
    cursorDot.style.left = mouseX - 2 + 'px';
    cursorDot.style.top = mouseY - 2 + 'px';
    requestAnimationFrame(animateCursor);
}
animateCursor();

// Cursor hover states
const interactives = document.querySelectorAll('a, button, .colony-node, .nav-dot, .feature-card, .doc-card');
interactives.forEach(el => {
    el.addEventListener('mouseenter', () => cursor.classList.add('hover'));
    el.addEventListener('mouseleave', () => cursor.classList.remove('hover'));
});

// ==================== PROGRESS BAR ====================
const progressBar = document.querySelector('.progress-bar');
window.addEventListener('scroll', () => {
    const progress = (window.scrollY / (document.documentElement.scrollHeight - window.innerHeight)) * 100;
    progressBar.style.width = progress + '%';
});

// ==================== NAVIGATION ====================
const sections = document.querySelectorAll('section');
const navDots = document.querySelectorAll('.nav-dot');

const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.querySelector('.section-content')?.classList.add('visible');
            navDots.forEach(dot => {
                dot.classList.toggle('active', dot.dataset.section === entry.target.id);
            });
        }
    });
}, { threshold: 0.3 });

sections.forEach(s => observer.observe(s));

// Trigger hero immediately
setTimeout(() => {
    const heroContent = document.querySelector('#hero .section-content');
    if (heroContent) heroContent.classList.add('visible');
}, 100);

navDots.forEach(dot => {
    dot.addEventListener('click', () => {
        document.getElementById(dot.dataset.section)?.scrollIntoView({ behavior: 'smooth' });
    });
});

// ==================== COLONY COLORS ====================
const COLONY_COLORS = {
    spark: { hex: '#FF6B35', name: 'Phoenix Orange' },
    forge: { hex: '#FFB347', name: 'Forge Amber' },
    flow: { hex: '#4ECDC4', name: 'Ocean Teal' },
    nexus: { hex: '#9B59B6', name: 'Bridge Purple' },
    beacon: { hex: '#D4AF37', name: 'Tower Gold' },
    grove: { hex: '#27AE60', name: 'Forest Green' },
    crystal: { hex: '#E0E0E0', name: 'Diamond White' }
};

const colonyNodes = document.querySelectorAll('.colony-node');
const colonyDetail = document.getElementById('colony-detail');

colonyNodes.forEach(node => {
    node.addEventListener('mouseenter', () => {
        const colony = node.dataset.colony;
        const color = COLONY_COLORS[colony];
        if (color && colonyDetail) {
            colonyDetail.querySelector('.colony-detail-color').style.background = color.hex;
            colonyDetail.querySelector('.colony-detail-name').textContent = `${colony.charAt(0).toUpperCase() + colony.slice(1)} — ${color.name}`;
            colonyDetail.querySelector('.colony-detail-hex').textContent = color.hex;
        }
    });
});

// ==================== CANVAS SETUP ====================
function setupCanvas(id) {
    const canvas = document.getElementById(id);
    if (!canvas) return null;
    const ctx = canvas.getContext('2d');
    const resize = () => {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
    };
    resize();
    window.addEventListener('resize', resize);
    return { canvas, ctx };
}

const colonyColors = ['#ff6b35', '#ffb347', '#4ecdc4', '#9b59b6', '#d4af37', '#27ae60', '#e0e0e0'];

// ==================== HERO CANVAS: Infinity tunnel ====================
const hero = setupCanvas('canvas-hero');
if (hero) {
    const { canvas, ctx } = hero;
    
    function draw(t) {
        ctx.fillStyle = 'rgba(7, 7, 10, 0.08)';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        
        const cx = canvas.width / 2;
        const cy = canvas.height / 2;
        
        // Nested circles receding (infinity mirror effect)
        for (let i = 0; i < 25; i++) {
            const depth = i + (t * 0.0002) % 1;
            const scale = Math.pow(0.88, depth);
            ctx.strokeStyle = `rgba(212, 175, 55, ${scale * 0.5})`;
            ctx.lineWidth = Math.max(0.5, 2 * scale);
            ctx.beginPath();
            ctx.arc(cx, cy, 180 * scale, 0, Math.PI * 2);
            ctx.stroke();
        }
        
        // Colony color ring
        const colorIndex = Math.floor((t * 0.0003) % colonyColors.length);
        const ringRadius = 70;
        const gradient = ctx.createRadialGradient(cx, cy, ringRadius - 15, cx, cy, ringRadius + 35);
        gradient.addColorStop(0, 'rgba(212, 175, 55, 0)');
        gradient.addColorStop(0.5, colonyColors[colorIndex] + '40');
        gradient.addColorStop(1, 'rgba(212, 175, 55, 0)');
        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.arc(cx, cy, ringRadius + 35, 0, Math.PI * 2);
        ctx.fill();
        
        // Central glow
        const pulse = 8 + Math.sin(t * 0.003) * 3;
        const glow = ctx.createRadialGradient(cx, cy, 0, cx, cy, pulse * 10);
        glow.addColorStop(0, 'rgba(212, 175, 55, 0.6)');
        glow.addColorStop(1, 'rgba(212, 175, 55, 0)');
        ctx.fillStyle = glow;
        ctx.beginPath();
        ctx.arc(cx, cy, pulse * 10, 0, Math.PI * 2);
        ctx.fill();
        
        ctx.fillStyle = '#d4af37';
        ctx.beginPath();
        ctx.arc(cx, cy, pulse, 0, Math.PI * 2);
        ctx.fill();
        
        requestAnimationFrame(draw);
    }
    draw(0);
}

// ==================== VISION CANVAS: Particles converging ====================
const vision = setupCanvas('canvas-vision');
if (vision) {
    const { canvas, ctx } = vision;
    const particles = [];
    for (let i = 0; i < 80; i++) {
        const angle = Math.random() * Math.PI * 2;
        const dist = 250 + Math.random() * 350;
        particles.push({
            x: Math.cos(angle) * dist,
            y: Math.sin(angle) * dist,
            speed: 0.2 + Math.random() * 0.4,
            size: 1 + Math.random() * 2
        });
    }
    
    function draw(t) {
        ctx.fillStyle = 'rgba(7, 7, 10, 0.05)';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        
        const cx = canvas.width / 2;
        const cy = canvas.height / 2;
        
        particles.forEach(p => {
            const dist = Math.sqrt(p.x * p.x + p.y * p.y);
            if (dist > 10) {
                p.x *= (1 - p.speed * 0.006);
                p.y *= (1 - p.speed * 0.006);
            } else {
                const angle = Math.random() * Math.PI * 2;
                const d = 280 + Math.random() * 220;
                p.x = Math.cos(angle) * d;
                p.y = Math.sin(angle) * d;
            }
            
            const alpha = Math.min(1, dist / 120) * 0.6;
            ctx.fillStyle = `rgba(212, 175, 55, ${alpha})`;
            ctx.beginPath();
            ctx.arc(cx + p.x, cy + p.y, p.size, 0, Math.PI * 2);
            ctx.fill();
        });
        
        // Central point
        const pulse = 8 + Math.sin(t * 0.003) * 3;
        ctx.fillStyle = '#d4af37';
        ctx.beginPath();
        ctx.arc(cx, cy, pulse, 0, Math.PI * 2);
        ctx.fill();
        
        requestAnimationFrame(draw);
    }
    draw(0);
}

// ==================== INFINITY CANVAS: Diminishing bars ====================
const infinity = setupCanvas('canvas-infinity');
if (infinity) {
    const { canvas, ctx } = infinity;
    
    function draw(t) {
        ctx.fillStyle = 'rgba(7, 7, 10, 0.06)';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        
        const cx = canvas.width / 2;
        const cy = canvas.height / 2;
        const barCount = 18;
        const spacing = 32;
        const startY = cy - (barCount * spacing) / 2;
        
        for (let i = 0; i < barCount; i++) {
            const brightness = Math.pow(0.82, i);
            const width = 280 * brightness;
            const y = startY + i * spacing;
            const colorIndex = (Math.floor(t * 0.001) + i) % colonyColors.length;
            
            ctx.fillStyle = `rgba(${hexToRgb(colonyColors[colorIndex])}, ${brightness * 0.5})`;
            ctx.fillRect(cx - width / 2, y - 1, width, 3);
        }
        
        // Light traveling down
        const lightPos = (t * 0.0008) % 1;
        const lightY = startY + lightPos * barCount * spacing;
        const lightBrightness = Math.pow(0.82, lightPos * barCount);
        ctx.fillStyle = `rgba(255, 255, 255, ${lightBrightness * 0.8})`;
        ctx.beginPath();
        ctx.arc(cx, lightY, 5, 0, Math.PI * 2);
        ctx.fill();
        
        requestAnimationFrame(draw);
    }
    draw(0);
}

// ==================== COLONIES CANVAS: Orbiting points ====================
const colonies = setupCanvas('canvas-colonies');
if (colonies) {
    const { canvas, ctx } = colonies;
    
    function draw(t) {
        ctx.fillStyle = 'rgba(7, 7, 10, 0.04)';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        
        const cx = canvas.width / 2;
        const cy = canvas.height / 2;
        const radius = Math.min(canvas.width, canvas.height) * 0.28;
        
        // Seven orbiting colony points
        for (let i = 0; i < 7; i++) {
            const angle = (i / 7) * Math.PI * 2 + t * 0.0002;
            const x = cx + Math.cos(angle) * radius;
            const y = cy + Math.sin(angle) * radius;
            
            // Trail
            for (let j = 0; j < 15; j++) {
                const ta = angle - j * 0.02;
                const tx = cx + Math.cos(ta) * radius;
                const ty = cy + Math.sin(ta) * radius;
                const alpha = (15 - j) / 15 * 0.2;
                ctx.fillStyle = `rgba(${hexToRgb(colonyColors[i])}, ${alpha})`;
                ctx.beginPath();
                ctx.arc(tx, ty, 2, 0, Math.PI * 2);
                ctx.fill();
            }
            
            // Point
            ctx.fillStyle = colonyColors[i];
            ctx.beginPath();
            ctx.arc(x, y, 6, 0, Math.PI * 2);
            ctx.fill();
            
            // Glow
            const glow = ctx.createRadialGradient(x, y, 0, x, y, 20);
            glow.addColorStop(0, colonyColors[i] + '40');
            glow.addColorStop(1, 'transparent');
            ctx.fillStyle = glow;
            ctx.beginPath();
            ctx.arc(x, y, 20, 0, Math.PI * 2);
            ctx.fill();
        }
        
        // Center observer point
        const pulse = 10 + Math.sin(t * 0.003) * 3;
        const centerGlow = ctx.createRadialGradient(cx, cy, 0, cx, cy, pulse * 3);
        centerGlow.addColorStop(0, 'rgba(212, 175, 55, 0.5)');
        centerGlow.addColorStop(1, 'rgba(212, 175, 55, 0)');
        ctx.fillStyle = centerGlow;
        ctx.beginPath();
        ctx.arc(cx, cy, pulse * 3, 0, Math.PI * 2);
        ctx.fill();
        
        ctx.fillStyle = '#d4af37';
        ctx.beginPath();
        ctx.arc(cx, cy, pulse, 0, Math.PI * 2);
        ctx.fill();
        
        requestAnimationFrame(draw);
    }
    draw(0);
}

// ==================== EXPERIENCE CANVAS: Breathing ====================
const experience = setupCanvas('canvas-experience');
if (experience) {
    const { canvas, ctx } = experience;
    
    function draw(t) {
        ctx.fillStyle = 'rgba(7, 7, 10, 0.05)';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        
        const cx = canvas.width * 0.75;
        const cy = canvas.height / 2;
        
        // Breathing orb
        const breathe = Math.sin(t * 0.002) * 0.3 + 0.7;
        
        for (let i = 10; i >= 0; i--) {
            const scale = Math.pow(0.85, i);
            const radius = 80 * scale * breathe;
            const alpha = scale * 0.3;
            
            ctx.strokeStyle = `rgba(78, 205, 196, ${alpha})`;
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.arc(cx, cy, radius, 0, Math.PI * 2);
            ctx.stroke();
        }
        
        // Center
        const pulse = 6 + Math.sin(t * 0.003) * 2;
        ctx.fillStyle = '#4ecdc4';
        ctx.beginPath();
        ctx.arc(cx, cy, pulse, 0, Math.PI * 2);
        ctx.fill();
        
        requestAnimationFrame(draw);
    }
    draw(0);
}

// ==================== SPECS CANVAS: Grid ====================
const specs = setupCanvas('canvas-specs');
if (specs) {
    const { canvas, ctx } = specs;
    
    function draw(t) {
        ctx.fillStyle = 'rgba(7, 7, 10, 0.04)';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        
        ctx.strokeStyle = 'rgba(212, 175, 55, 0.03)';
        ctx.lineWidth = 1;
        
        const gridSize = 60;
        const offset = (t * 0.02) % gridSize;
        
        for (let x = -gridSize + offset; x < canvas.width + gridSize; x += gridSize) {
            ctx.beginPath();
            ctx.moveTo(x, 0);
            ctx.lineTo(x, canvas.height);
            ctx.stroke();
        }
        
        for (let y = -gridSize + offset; y < canvas.height + gridSize; y += gridSize) {
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(canvas.width, y);
            ctx.stroke();
        }
        
        requestAnimationFrame(draw);
    }
    draw(0);
}

// ==================== TIMELINE CANVAS: Particles down ====================
const timeline = setupCanvas('canvas-timeline');
if (timeline) {
    const { canvas, ctx } = timeline;
    
    function draw(t) {
        ctx.fillStyle = 'rgba(7, 7, 10, 0.04)';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        
        const x = canvas.width * 0.15;
        const particleY = (t * 0.1) % canvas.height;
        
        for (let i = 0; i < 20; i++) {
            const y = (particleY + i * 30) % canvas.height;
            const alpha = (20 - i) / 20 * 0.3;
            ctx.fillStyle = `rgba(212, 175, 55, ${alpha})`;
            ctx.beginPath();
            ctx.arc(x, y, 3, 0, Math.PI * 2);
            ctx.fill();
        }
        
        requestAnimationFrame(draw);
    }
    draw(0);
}

// ==================== DOCS CANVAS: Network ====================
const docs = setupCanvas('canvas-docs');
if (docs) {
    const { canvas, ctx } = docs;
    const nodes = [];
    for (let i = 0; i < 40; i++) {
        nodes.push({
            x: Math.random() * canvas.width,
            y: Math.random() * canvas.height,
            vx: (Math.random() - 0.5) * 0.3,
            vy: (Math.random() - 0.5) * 0.3
        });
    }
    
    function draw(t) {
        ctx.fillStyle = 'rgba(7, 7, 10, 0.05)';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        
        nodes.forEach(n => {
            n.x += n.vx;
            n.y += n.vy;
            if (n.x < 0 || n.x > canvas.width) n.vx *= -1;
            if (n.y < 0 || n.y > canvas.height) n.vy *= -1;
        });
        
        ctx.strokeStyle = 'rgba(212, 175, 55, 0.08)';
        ctx.lineWidth = 1;
        
        for (let i = 0; i < nodes.length; i++) {
            for (let j = i + 1; j < nodes.length; j++) {
                const dx = nodes[i].x - nodes[j].x;
                const dy = nodes[i].y - nodes[j].y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (dist < 150) {
                    ctx.globalAlpha = (150 - dist) / 150 * 0.15;
                    ctx.beginPath();
                    ctx.moveTo(nodes[i].x, nodes[i].y);
                    ctx.lineTo(nodes[j].x, nodes[j].y);
                    ctx.stroke();
                }
            }
        }
        
        ctx.globalAlpha = 1;
        nodes.forEach(n => {
            ctx.fillStyle = 'rgba(212, 175, 55, 0.4)';
            ctx.beginPath();
            ctx.arc(n.x, n.y, 2, 0, Math.PI * 2);
            ctx.fill();
        });
        
        requestAnimationFrame(draw);
    }
    draw(0);
}

// ==================== CTA CANVAS: Lemniscate ====================
const cta = setupCanvas('canvas-cta');
if (cta) {
    const { canvas, ctx } = cta;
    
    function draw(t) {
        ctx.fillStyle = 'rgba(7, 7, 10, 0.03)';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        
        const cx = canvas.width / 2;
        const cy = canvas.height / 2;
        
        // Lemniscate (infinity)
        ctx.strokeStyle = 'rgba(212, 175, 55, 0.15)';
        ctx.lineWidth = 2;
        ctx.beginPath();
        
        const scale = Math.min(canvas.width, canvas.height) * 0.12;
        for (let angle = 0; angle <= Math.PI * 2; angle += 0.02) {
            const cos = Math.cos(angle);
            const sin = Math.sin(angle);
            const denom = 1 + sin * sin;
            const x = cx + (scale * 2 * cos) / denom;
            const y = cy + (scale * sin * cos) / denom;
            
            if (angle === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        }
        ctx.closePath();
        ctx.stroke();
        
        // Point traveling the loop
        const angle = (t * 0.0005) % (Math.PI * 2);
        const cos = Math.cos(angle);
        const sin = Math.sin(angle);
        const denom = 1 + sin * sin;
        const px = cx + (scale * 2 * cos) / denom;
        const py = cy + (scale * sin * cos) / denom;
        
        // Trail
        for (let i = 0; i < 25; i++) {
            const ta = ((t * 0.0005) - i * 0.025) % (Math.PI * 2);
            const tc = Math.cos(ta);
            const ts = Math.sin(ta);
            const td = 1 + ts * ts;
            const tx = cx + (scale * 2 * tc) / td;
            const ty = cy + (scale * ts * tc) / td;
            
            const alpha = (25 - i) / 25 * 0.4;
            ctx.fillStyle = `rgba(212, 175, 55, ${alpha})`;
            ctx.beginPath();
            ctx.arc(tx, ty, 2, 0, Math.PI * 2);
            ctx.fill();
        }
        
        ctx.fillStyle = '#d4af37';
        ctx.beginPath();
        ctx.arc(px, py, 5, 0, Math.PI * 2);
        ctx.fill();
        
        requestAnimationFrame(draw);
    }
    draw(0);
}

// ==================== HELPERS ====================
function hexToRgb(hex) {
    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    return result
        ? `${parseInt(result[1], 16)}, ${parseInt(result[2], 16)}, ${parseInt(result[3], 16)}`
        : '255, 255, 255';
}

console.log('🔮 Kagami Orb — The Floating Mirror');
console.log('鏡 h(x) ≥ 0. Always.');
