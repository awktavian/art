/* ═══════════════════════════════════════════════════════════════════════════
   OCTONI-ON or OCTONI-OFF? — Interactive Scrollytelling
   
   Features:
   - Animated loading screen with octonion assembly
   - Advanced particle system with physics
   - Scroll progress tracking
   - Chapter navigation with keyboard support
   - Interactive demos (fiber bundle decomposition)
   - Easter eggs (Konami code, triple-click)
   - Accessibility (reduced motion, keyboard nav)
   
   h(x) ≥ 0 always
═══════════════════════════════════════════════════════════════════════════ */

(function() {
    'use strict';

    // =========================================================================
    // CONSTANTS
    // =========================================================================
    
    const OCTO_COLORS = {
        purple: '#8E44AD',
        purpleBright: '#A855F7',
        coral: '#FF6B6B',
        gold: '#D4AF37',
        teal: '#4ECDC4',
        green: '#22C55E',
        blue: '#3498DB',
        violet: '#9B59B6'
    };
    
    const PARTICLE_COLORS = [
        'rgba(142, 68, 173, 0.6)',  // octo-purple
        'rgba(168, 85, 247, 0.5)',  // purple-bright
        'rgba(255, 107, 107, 0.5)', // s15-coral
        'rgba(212, 175, 55, 0.4)',  // s8-gold
        'rgba(78, 205, 196, 0.5)',  // s7-teal
    ];
    
    const FIBONACCI = [89, 144, 233, 377, 610, 987, 1597];
    
    // Konami code sequence
    const KONAMI_CODE = ['ArrowUp', 'ArrowUp', 'ArrowDown', 'ArrowDown', 
                         'ArrowLeft', 'ArrowRight', 'ArrowLeft', 'ArrowRight', 
                         'b', 'a'];
    
    // =========================================================================
    // STATE
    // =========================================================================
    
    const state = {
        loaded: false,
        prefersReducedMotion: false,
        mouseX: 0,
        mouseY: 0,
        scrollY: 0,
        currentChapter: 0,
        konamiIndex: 0,
        particles: [],
        spheres: [],
        connections: [],
        flashes: [],
        milestones: [],
        s15Count: 0,
        s7Count: 0,
        experimentData: null  // Will hold loaded experiment results
    };
    
    // =========================================================================
    // DATA LOADING
    // =========================================================================
    
    async function loadExperimentData() {
        try {
            const response = await fetch('data/experiment_results.json');
            if (!response.ok) {
                console.warn('No experiment data found, using placeholder');
                return;
            }
            
            state.experimentData = await response.json();
            console.log('Loaded experiment data:', state.experimentData);
            
            // Populate the page with real data
            populateExperimentData();
            
        } catch (error) {
            console.warn('Could not load experiment data:', error);
        }
    }
    
    function populateExperimentData() {
        const data = state.experimentData;
        if (!data || !data.analysis) return;
        
        const analysis = data.analysis;
        
        // Update summary stats
        updateElement('s7-mean', formatNumber(analysis.recon.s7_mean, 6));
        updateElement('s7-std', formatNumber(analysis.recon.s7_std, 6));
        updateElement('s15-mean', formatNumber(analysis.recon.s15_mean, 6));
        updateElement('s15-std', formatNumber(analysis.recon.s15_std, 6));
        
        // Update statistical results
        updateElement('welch-t', formatNumber(analysis.recon.welch_t, 3));
        updateElement('welch-p', formatNumber(analysis.recon.welch_p, 6));
        updateElement('cohens-d', formatNumber(analysis.recon.cohens_d, 3));
        updateElement('effect-magnitude', analysis.recon.effect_magnitude.toUpperCase());
        updateElement('ci-lower', formatNumber(analysis.recon.ci_95_lower, 6));
        updateElement('ci-upper', formatNumber(analysis.recon.ci_95_upper, 6));
        
        // Update improvement percentage
        const improvement = analysis.recon.percent_improvement;
        updateElement('percent-improvement', `${improvement > 0 ? '+' : ''}${formatNumber(improvement, 2)}%`);
        
        // Update significance status
        const sigStatus = analysis.recon.significant_bonferroni === true || analysis.recon.significant_bonferroni === 'True';
        updateElement('sig-status', sigStatus ? 'SIGNIFICANT' : 'NOT SIGNIFICANT');
        
        // Update sample info
        updateElement('sample-n-s7', analysis.sample.n_s7);
        updateElement('sample-n-s15', analysis.sample.n_s15);
        
        // Update training overhead
        updateElement('s7-time', formatNumber(analysis.overhead.s7_mean_time, 1));
        updateElement('s15-time', formatNumber(analysis.overhead.s15_mean_time, 1));
        updateElement('overhead-ratio', formatNumber(analysis.overhead.ratio, 2));
        
        // Update methodology badges
        updateElement('methodology', data.methodology || 'DreamerV3');
        updateElement('benchmark', data.benchmark || 'Crafter');
        
        // Populate raw data table
        populateRawDataTable();
        
        // Update conclusion based on real results
        updateConclusion();
        
        console.log('Page populated with real experiment data');
    }
    
    function updateElement(id, value) {
        const el = document.getElementById(id);
        if (el) {
            el.textContent = value;
        }
    }
    
    function formatNumber(num, decimals) {
        if (num === null || num === undefined || isNaN(num)) return 'N/A';
        return Number(num).toFixed(decimals);
    }
    
    function populateRawDataTable() {
        const tbody = document.getElementById('raw-data-tbody');
        if (!tbody || !state.experimentData) return;
        
        tbody.innerHTML = '';
        
        const allResults = [
            ...(state.experimentData.s7_results || []),
            ...(state.experimentData.s15_results || [])
        ];
        
        allResults.forEach(result => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${result.condition}</td>
                <td>${result.seed}</td>
                <td>${formatNumber(result.final_recon_loss, 6)}</td>
                <td>${formatNumber(result.final_kl_loss, 6)}</td>
                <td>${formatNumber(result.final_total_loss, 6)}</td>
                <td>${formatNumber(result.training_time_seconds, 1)}</td>
            `;
            tbody.appendChild(tr);
        });
    }
    
    function updateConclusion() {
        const conclusionEl = document.getElementById('conclusion-text');
        if (!conclusionEl || !state.experimentData) return;
        
        const analysis = state.experimentData.analysis;
        const recon = analysis.recon;
        
        const isSig = recon.significant_bonferroni === true || recon.significant_bonferroni === 'True';
        const isImprovement = recon.percent_improvement > 0;
        
        let conclusion;
        if (isSig && isImprovement) {
            conclusion = `S15 encoding shows STATISTICALLY SIGNIFICANT improvement over S7 (p = ${formatNumber(recon.welch_p, 6)}, d = ${formatNumber(recon.cohens_d, 2)} [${recon.effect_magnitude}]). The octonionic Hopf fibration provides measurable benefit.`;
        } else if (isSig && !isImprovement) {
            conclusion = `S15 encoding shows STATISTICALLY SIGNIFICANT difference, but performs WORSE than S7 (p = ${formatNumber(recon.welch_p, 6)}, d = ${formatNumber(recon.cohens_d, 2)}). The octonionic encoding adds complexity without benefit in this benchmark.`;
        } else {
            conclusion = `Results are NOT statistically significant at Bonferroni-corrected α=0.0125 (p = ${formatNumber(recon.welch_p, 6)}, d = ${formatNumber(recon.cohens_d, 2)} [${recon.effect_magnitude}]). The difference between S15 and S7 may be due to chance, or the effect size may be smaller than detectable with n=${analysis.sample.n_s7} per condition.`;
        }
        
        conclusionEl.textContent = conclusion;
    }
    
    // =========================================================================
    // INITIALIZATION
    // =========================================================================
    
    function init() {
        // Check reduced motion preference
        state.prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        
        // Load experiment data first
        loadExperimentData();
        
        // Initialize systems
        initLoadingScreen();
        initParticleCanvas();
        initScrollProgress();
        initChapterNavigation();
        initRevealAnimations();
        initInteractiveCanvas();
        initCopyButton();
        initKeyboardNavigation();
        initEasterEggs();
        initSignificanceMeter();
        initMetricBars();
        initDownloadCSV();
        
        // Track mouse position
        document.addEventListener('mousemove', (e) => {
            state.mouseX = e.clientX;
            state.mouseY = e.clientY;
        });
        
        // Track scroll position
        window.addEventListener('scroll', () => {
            state.scrollY = window.scrollY;
        }, { passive: true });
    }
    
    // =========================================================================
    // LOADING SCREEN
    // =========================================================================
    
    function initLoadingScreen() {
        const loadingScreen = document.getElementById('loading-screen');
        const progressBar = document.getElementById('loading-progress-bar');
        
        if (!loadingScreen || !progressBar) return;
        
        let progress = 0;
        const duration = 1500;
        const startTime = performance.now();
        
        function updateProgress(currentTime) {
            const elapsed = currentTime - startTime;
            progress = Math.min((elapsed / duration) * 100, 100);
            progressBar.style.width = `${progress}%`;
            
            if (progress < 100) {
                requestAnimationFrame(updateProgress);
            } else {
                setTimeout(hideLoadingScreen, 300);
            }
        }
        
        requestAnimationFrame(updateProgress);
    }
    
    function hideLoadingScreen() {
        const loadingScreen = document.getElementById('loading-screen');
        const body = document.body;
        
        if (!loadingScreen) return;
        
        loadingScreen.classList.add('hidden');
        
        setTimeout(() => {
            body.classList.remove('loading');
            state.loaded = true;
        }, 100);
        
        setTimeout(() => {
            if (loadingScreen.parentNode) {
                loadingScreen.remove();
            }
        }, 700);
    }
    
    // =========================================================================
    // PARTICLE CANVAS SYSTEM
    // =========================================================================
    
    let particleCanvas, particleCtx;
    let particleWidth, particleHeight;
    let particleAnimationFrame;
    
    function initParticleCanvas() {
        particleCanvas = document.getElementById('particle-canvas');
        if (!particleCanvas) return;
        
        particleCtx = particleCanvas.getContext('2d');
        
        resizeParticleCanvas();
        createParticles();
        animateParticles();
        
        window.addEventListener('resize', resizeParticleCanvas);
    }
    
    function resizeParticleCanvas() {
        particleWidth = particleCanvas.width = window.innerWidth;
        particleHeight = particleCanvas.height = window.innerHeight;
        
        // Reinitialize particles on resize
        if (state.particles.length > 0) {
            createParticles();
        }
    }
    
    function createParticles() {
        const count = state.prefersReducedMotion ? 0 : (window.innerWidth < 768 ? 25 : 50);
        state.particles = [];
        
        for (let i = 0; i < count; i++) {
            state.particles.push({
                x: Math.random() * particleWidth,
                y: Math.random() * particleHeight,
                vx: (Math.random() - 0.5) * 0.4,
                vy: (Math.random() - 0.5) * 0.4,
                radius: Math.random() * 2.5 + 1,
                color: PARTICLE_COLORS[Math.floor(Math.random() * PARTICLE_COLORS.length)],
                pulsePhase: Math.random() * Math.PI * 2,
                pulseSpeed: 0.02 + Math.random() * 0.02,
                parallaxFactor: 0.5 + Math.random() * 0.5
            });
        }
    }
    
    function animateParticles() {
        if (state.prefersReducedMotion) return;
        
        particleCtx.clearRect(0, 0, particleWidth, particleHeight);
        
        // Update and draw particles
        for (const p of state.particles) {
            // Update pulse
            p.pulsePhase += p.pulseSpeed;
            const pulseScale = 0.8 + 0.4 * Math.sin(p.pulsePhase);
            
            // Mouse parallax (within 200px radius)
            const dx = state.mouseX - p.x;
            const dy = state.mouseY - p.y;
            const dist = Math.sqrt(dx * dx + dy * dy);
            
            if (dist < 200) {
                const force = (200 - dist) / 200 * 0.02 * p.parallaxFactor;
                p.vx -= dx * force * 0.01;
                p.vy -= dy * force * 0.01;
            }
            
            // Scroll-based upward drift
            p.vy -= state.scrollY * 0.00001;
            
            // Update position
            p.x += p.vx;
            p.y += p.vy;
            
            // Damping
            p.vx *= 0.99;
            p.vy *= 0.99;
            
            // Wrap around edges
            if (p.x < -10) p.x = particleWidth + 10;
            if (p.x > particleWidth + 10) p.x = -10;
            if (p.y < -10) p.y = particleHeight + 10;
            if (p.y > particleHeight + 10) p.y = -10;
            
            // Draw particle with glow
            const currentRadius = p.radius * pulseScale;
            
            // Glow
            const gradient = particleCtx.createRadialGradient(
                p.x, p.y, 0,
                p.x, p.y, currentRadius * 3
            );
            gradient.addColorStop(0, p.color);
            gradient.addColorStop(1, 'transparent');
            
            particleCtx.beginPath();
            particleCtx.arc(p.x, p.y, currentRadius * 3, 0, Math.PI * 2);
            particleCtx.fillStyle = gradient;
            particleCtx.fill();
            
            // Core
            particleCtx.beginPath();
            particleCtx.arc(p.x, p.y, currentRadius, 0, Math.PI * 2);
            particleCtx.fillStyle = p.color;
            particleCtx.fill();
        }
        
        // Draw connections between nearby particles
        for (let i = 0; i < state.particles.length; i++) {
            for (let j = i + 1; j < state.particles.length; j++) {
                const p1 = state.particles[i];
                const p2 = state.particles[j];
                const dx = p1.x - p2.x;
                const dy = p1.y - p2.y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                
                if (dist < 150) {
                    const alpha = (150 - dist) / 150 * 0.15;
                    particleCtx.beginPath();
                    particleCtx.moveTo(p1.x, p1.y);
                    particleCtx.lineTo(p2.x, p2.y);
                    particleCtx.strokeStyle = `rgba(142, 68, 173, ${alpha})`;
                    particleCtx.lineWidth = 1;
                    particleCtx.stroke();
                }
            }
        }
        
        particleAnimationFrame = requestAnimationFrame(animateParticles);
    }
    
    // =========================================================================
    // SCROLL PROGRESS
    // =========================================================================
    
    function initScrollProgress() {
        const progressBar = document.getElementById('scroll-progress-bar');
        if (!progressBar) return;
        
        function updateProgress() {
            const scrollHeight = document.documentElement.scrollHeight - window.innerHeight;
            const progress = (window.scrollY / scrollHeight) * 100;
            progressBar.style.width = `${progress}%`;
            
            // Update ARIA
            progressBar.parentElement.setAttribute('aria-valuenow', Math.round(progress));
        }
        
        window.addEventListener('scroll', updateProgress, { passive: true });
        updateProgress();
    }
    
    // =========================================================================
    // CHAPTER NAVIGATION
    // =========================================================================
    
    function initChapterNavigation() {
        const nav = document.getElementById('chapter-nav');
        const dots = nav?.querySelectorAll('.chapter-dot');
        const chapters = document.querySelectorAll('[data-chapter]');
        
        if (!nav || !dots || !chapters.length) return;
        
        // Click handlers for dots
        dots.forEach(dot => {
            dot.addEventListener('click', () => {
                const chapterIndex = parseInt(dot.dataset.chapter);
                const target = document.querySelector(`[data-chapter="${chapterIndex}"]`);
                if (target) {
                    target.scrollIntoView({ behavior: 'smooth' });
                }
            });
        });
        
        // Update active dot based on scroll
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const chapterIndex = parseInt(entry.target.dataset.chapter);
                    state.currentChapter = chapterIndex;
                    
                    dots.forEach(dot => {
                        const dotChapter = parseInt(dot.dataset.chapter);
                        dot.classList.toggle('active', dotChapter === chapterIndex);
                        dot.setAttribute('aria-current', dotChapter === chapterIndex ? 'true' : 'false');
                    });
                }
            });
        }, {
            threshold: 0.3,
            rootMargin: '-20% 0px -20% 0px'
        });
        
        chapters.forEach(chapter => observer.observe(chapter));
    }
    
    // =========================================================================
    // REVEAL ANIMATIONS
    // =========================================================================
    
    function initRevealAnimations() {
        const reveals = document.querySelectorAll('.reveal');
        
        if (state.prefersReducedMotion) {
            reveals.forEach(el => el.classList.add('visible'));
            return;
        }
        
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('visible');
                    observer.unobserve(entry.target);
                }
            });
        }, {
            threshold: 0.1,
            rootMargin: '0px 0px -50px 0px'
        });
        
        reveals.forEach(el => observer.observe(el));
    }
    
    // =========================================================================
    // INTERACTIVE CANVAS (FIBER BUNDLE DEMO)
    // =========================================================================
    
    let interactiveCanvas, interactiveCtx;
    let canvasWidth, canvasHeight;
    let canvasAnimationFrame;
    
    function initInteractiveCanvas() {
        interactiveCanvas = document.getElementById('interactive-canvas');
        if (!interactiveCanvas) return;
        
        interactiveCtx = interactiveCanvas.getContext('2d');
        
        resizeInteractiveCanvas();
        
        // Event handlers
        interactiveCanvas.addEventListener('click', (e) => {
            const rect = interactiveCanvas.getBoundingClientRect();
            spawnS15Decomposition(e.clientX - rect.left, e.clientY - rect.top);
        });
        
        interactiveCanvas.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            const rect = interactiveCanvas.getBoundingClientRect();
            spawnS7Point(e.clientX - rect.left, e.clientY - rect.top);
        });
        
        window.addEventListener('resize', resizeInteractiveCanvas);
        
        animateInteractiveCanvas();
    }
    
    function resizeInteractiveCanvas() {
        if (!interactiveCanvas) return;
        const container = interactiveCanvas.parentElement;
        canvasWidth = interactiveCanvas.width = container.clientWidth;
        canvasHeight = interactiveCanvas.height = 400;
    }
    
    function spawnFlash(x, y, color) {
        state.flashes.push({
            x, y,
            radius: 10,
            maxRadius: 100,
            life: 400,
            maxLife: 400,
            color: color || 'rgba(142, 68, 173, 0.6)'
        });
    }
    
    function shakeCanvas() {
        if (state.prefersReducedMotion) return;
        interactiveCanvas.classList.add('shake');
        setTimeout(() => interactiveCanvas.classList.remove('shake'), 150);
    }
    
    function spawnS15Decomposition(x, y) {
        state.s15Count++;
        updateCanvasStats();
        
        spawnFlash(x, y, 'rgba(142, 68, 173, 0.6)');
        
        // Milestone celebration
        if (state.s15Count % 5 === 0) {
            shakeCanvas();
            state.milestones.push({
                text: `${state.s15Count} S¹⁵!`,
                x, y: y - 40,
                life: 1500,
                maxLife: 1500
            });
        }
        
        // Base point (S8) - gold, goes up-left
        const baseAngle = -Math.PI * 0.75;
        state.spheres.push({
            x, y,
            vx: Math.cos(baseAngle) * 4 + (Math.random() - 0.5) * 2,
            vy: Math.sin(baseAngle) * 4 - 2,
            emoji: '🎯',
            label: 'S⁸',
            size: 28,
            life: 3000,
            maxLife: 3000,
            type: 's8',
            color: OCTO_COLORS.gold,
            gravity: 0.03,
            rotation: 0,
            rotationSpeed: 0.02
        });
        
        // Fiber points (S7) - 7 points explode in a circle
        const fiberColors = [
            OCTO_COLORS.teal, OCTO_COLORS.purple, OCTO_COLORS.coral,
            OCTO_COLORS.green, OCTO_COLORS.blue, OCTO_COLORS.violet,
            OCTO_COLORS.purpleBright
        ];
        
        const newFibers = [];
        for (let i = 0; i < 7; i++) {
            const angle = (Math.PI * 2 * i) / 7 - Math.PI / 2;
            const speed = 3 + Math.random() * 2;
            
            const fiber = {
                x, y,
                vx: Math.cos(angle) * speed,
                vy: Math.sin(angle) * speed - 1,
                emoji: '🌀',
                label: `e${i}`,
                size: 20 + Math.random() * 8,
                life: 2500 + Math.random() * 500,
                maxLife: 3000,
                type: 's7-fiber',
                color: fiberColors[i],
                gravity: 0.04,
                rotation: 0,
                rotationSpeed: (Math.random() - 0.5) * 0.1,
                fiberIndex: i
            };
            
            newFibers.push(fiber);
            state.spheres.push(fiber);
        }
        
        // Create connections between fibers
        for (let i = 0; i < newFibers.length; i++) {
            state.connections.push({
                a: newFibers[i],
                b: newFibers[(i + 1) % newFibers.length],
                life: 800,
                maxLife: 800
            });
        }
    }
    
    function spawnS7Point(x, y) {
        state.s7Count++;
        updateCanvasStats();
        
        const angle = Math.random() * Math.PI * 2;
        const speed = 1.5 + Math.random() * 1.5;
        
        state.spheres.push({
            x, y,
            vx: Math.cos(angle) * speed,
            vy: Math.sin(angle) * speed,
            emoji: '🌀',
            label: 'S⁷',
            size: 18,
            life: 1500,
            maxLife: 1500,
            type: 's7-lonely',
            color: OCTO_COLORS.teal,
            gravity: 0.08,
            rotation: 0,
            rotationSpeed: (Math.random() - 0.5) * 0.05,
            brightness: 0.5
        });
    }
    
    function updateCanvasStats() {
        const s15El = document.getElementById('s15-count');
        const s7El = document.getElementById('s7-count');
        if (s15El) s15El.textContent = state.s15Count;
        if (s7El) s7El.textContent = state.s7Count;
    }
    
    function animateInteractiveCanvas() {
        if (!interactiveCtx) {
            canvasAnimationFrame = requestAnimationFrame(animateInteractiveCanvas);
            return;
        }
        
        // Fade trail
        interactiveCtx.fillStyle = 'rgba(13, 12, 26, 0.15)';
        interactiveCtx.fillRect(0, 0, canvasWidth, canvasHeight);
        
        // Draw flashes
        for (let i = state.flashes.length - 1; i >= 0; i--) {
            const f = state.flashes[i];
            f.life -= 16;
            f.radius += 5;
            
            if (f.life <= 0) {
                state.flashes.splice(i, 1);
                continue;
            }
            
            const alpha = (f.life / f.maxLife) * 0.6;
            const gradient = interactiveCtx.createRadialGradient(f.x, f.y, 0, f.x, f.y, f.radius);
            gradient.addColorStop(0, `rgba(255, 255, 255, ${alpha})`);
            gradient.addColorStop(0.4, f.color);
            gradient.addColorStop(1, 'transparent');
            
            interactiveCtx.beginPath();
            interactiveCtx.arc(f.x, f.y, f.radius, 0, Math.PI * 2);
            interactiveCtx.fillStyle = gradient;
            interactiveCtx.fill();
        }
        
        // Draw connections
        for (let i = state.connections.length - 1; i >= 0; i--) {
            const conn = state.connections[i];
            conn.life -= 16;
            
            if (conn.life <= 0) {
                state.connections.splice(i, 1);
                continue;
            }
            
            const alpha = (conn.life / conn.maxLife) * 0.5;
            interactiveCtx.beginPath();
            interactiveCtx.moveTo(conn.a.x, conn.a.y);
            interactiveCtx.lineTo(conn.b.x, conn.b.y);
            interactiveCtx.strokeStyle = `rgba(78, 205, 196, ${alpha})`;
            interactiveCtx.lineWidth = 2;
            interactiveCtx.stroke();
        }
        
        // Draw spheres
        for (let i = state.spheres.length - 1; i >= 0; i--) {
            const s = state.spheres[i];
            
            // Physics
            s.x += s.vx;
            s.y += s.vy;
            s.vy += s.gravity;
            s.vx *= 0.99;
            s.rotation += s.rotationSpeed;
            s.life -= 16;
            
            if (s.life <= 0 || s.y > canvasHeight + 50) {
                state.spheres.splice(i, 1);
                continue;
            }
            
            // Bounce off walls
            if (s.x < 20 || s.x > canvasWidth - 20) {
                s.vx *= -0.7;
                s.x = Math.max(20, Math.min(canvasWidth - 20, s.x));
            }
            
            const lifeRatio = s.life / s.maxLife;
            const alpha = Math.pow(lifeRatio, 0.5) * (s.brightness || 1);
            const size = s.size * (0.7 + 0.3 * lifeRatio);
            
            interactiveCtx.save();
            interactiveCtx.translate(s.x, s.y);
            interactiveCtx.rotate(s.rotation);
            interactiveCtx.globalAlpha = alpha;
            interactiveCtx.font = `${size}px Arial`;
            interactiveCtx.textAlign = 'center';
            interactiveCtx.textBaseline = 'middle';
            
            // Glow based on type
            if (s.type === 's8') {
                interactiveCtx.shadowBlur = 25;
                interactiveCtx.shadowColor = 'rgba(212, 175, 55, 0.8)';
            } else if (s.type === 's7-fiber') {
                interactiveCtx.shadowBlur = 15;
                interactiveCtx.shadowColor = 'rgba(78, 205, 196, 0.7)';
            } else {
                interactiveCtx.shadowBlur = 8;
                interactiveCtx.shadowColor = 'rgba(78, 205, 196, 0.3)';
            }
            
            interactiveCtx.fillText(s.emoji, 0, 0);
            
            // Draw label
            if (s.label && lifeRatio > 0.3) {
                interactiveCtx.font = '10px "IBM Plex Mono", monospace';
                interactiveCtx.fillStyle = s.type === 's8' ? OCTO_COLORS.gold : OCTO_COLORS.teal;
                interactiveCtx.shadowBlur = 0;
                interactiveCtx.fillText(s.label, 0, size / 2 + 12);
            }
            
            interactiveCtx.restore();
        }
        
        // Draw milestones
        for (let i = state.milestones.length - 1; i >= 0; i--) {
            const m = state.milestones[i];
            m.life -= 16;
            m.y -= 0.5;
            
            if (m.life <= 0) {
                state.milestones.splice(i, 1);
                continue;
            }
            
            const alpha = m.life / m.maxLife;
            interactiveCtx.save();
            interactiveCtx.globalAlpha = alpha;
            interactiveCtx.font = 'bold 32px "Space Grotesk", sans-serif';
            interactiveCtx.textAlign = 'center';
            interactiveCtx.fillStyle = OCTO_COLORS.purple;
            interactiveCtx.shadowBlur = 20;
            interactiveCtx.shadowColor = 'rgba(142, 68, 173, 0.8)';
            interactiveCtx.fillText(m.text, m.x, m.y);
            interactiveCtx.restore();
        }
        
        // Hint text when empty
        if (state.spheres.length === 0 && state.s15Count === 0) {
            interactiveCtx.fillStyle = 'rgba(142, 68, 173, 0.4)';
            interactiveCtx.font = '16px "IBM Plex Mono", monospace';
            interactiveCtx.textAlign = 'center';
            interactiveCtx.fillText('CLICK TO DECOMPOSE S¹⁵', canvasWidth / 2, canvasHeight / 2 - 20);
            interactiveCtx.font = '11px "IBM Plex Mono", monospace';
            interactiveCtx.fillStyle = 'rgba(142, 68, 173, 0.25)';
            interactiveCtx.fillText('left click = S¹⁵ → S⁸ + S⁷  |  right click = lonely S⁷', canvasWidth / 2, canvasHeight / 2 + 10);
        }
        
        canvasAnimationFrame = requestAnimationFrame(animateInteractiveCanvas);
    }
    
    // =========================================================================
    // COPY BUTTON
    // =========================================================================
    
    function initCopyButton() {
        const copyBtn = document.getElementById('copy-cta');
        if (!copyBtn) return;
        
        async function handleCopy() {
            const code = copyBtn.querySelector('code').textContent;
            const hint = copyBtn.querySelector('.footer-code-hint');
            
            try {
                await navigator.clipboard.writeText(code);
                copyBtn.classList.add('copied');
                hint.textContent = 'Copied! Now go forth and OCTONI-ON';
                
                setTimeout(() => {
                    copyBtn.classList.remove('copied');
                    hint.textContent = 'click to copy';
                }, 2000);
            } catch (err) {
                // Fallback
                const textArea = document.createElement('textarea');
                textArea.value = code;
                document.body.appendChild(textArea);
                textArea.select();
                document.execCommand('copy');
                document.body.removeChild(textArea);
                
                copyBtn.classList.add('copied');
                hint.textContent = 'Copied!';
                
                setTimeout(() => {
                    copyBtn.classList.remove('copied');
                    hint.textContent = 'click to copy';
                }, 2000);
            }
        }
        
        copyBtn.addEventListener('click', handleCopy);
        copyBtn.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                handleCopy();
            }
        });
    }
    
    // =========================================================================
    // METRIC BAR ANIMATIONS
    // =========================================================================
    
    function initMetricBars() {
        const bars = document.querySelectorAll('.metric-bar-fill');
        
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const bar = entry.target;
                    const target = bar.dataset.target;
                    if (target) {
                        setTimeout(() => {
                            bar.style.width = `${target}%`;
                        }, 200);
                    }
                    observer.unobserve(bar);
                }
            });
        }, { threshold: 0.3 });
        
        bars.forEach(bar => {
            bar.style.width = '0%';
            observer.observe(bar);
        });
    }
    
    // =========================================================================
    // CSV DOWNLOAD
    // =========================================================================
    
    function initDownloadCSV() {
        const downloadBtn = document.getElementById('download-csv');
        if (!downloadBtn) return;
        
        downloadBtn.addEventListener('click', (e) => {
            e.preventDefault();
            
            let csvContent = 'Condition,Seed,Recon_Loss,KL_Loss,Total_Loss,Training_Time_Sec\n';
            
            // Use real data if available, otherwise fallback
            if (state.experimentData) {
                const allResults = [
                    ...(state.experimentData.s7_results || []),
                    ...(state.experimentData.s15_results || [])
                ];
                
                allResults.forEach(r => {
                    csvContent += `${r.condition},${r.seed},${r.final_recon_loss.toFixed(6)},${r.final_kl_loss.toFixed(6)},${r.final_total_loss.toFixed(6)},${r.training_time_seconds.toFixed(1)}\n`;
                });
            } else {
                // Fallback placeholder
                csvContent += 'No experiment data loaded - run the experiment first\n';
            }
            
            const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = 'octoni-on-experiment-data.csv';
            link.click();
            URL.revokeObjectURL(url);
            
            downloadBtn.textContent = '✓ Downloaded!';
            setTimeout(() => {
                downloadBtn.innerHTML = '📥 Download Raw Data (CSV)';
            }, 2000);
        });
    }
    
    // =========================================================================
    // KEYBOARD NAVIGATION
    // =========================================================================
    
    function initKeyboardNavigation() {
        document.addEventListener('keydown', (e) => {
            // j/k for chapter navigation
            if (e.key === 'j' || e.key === 'k') {
                e.preventDefault();
                const chapters = document.querySelectorAll('[data-chapter]');
                const direction = e.key === 'j' ? 1 : -1;
                const nextChapter = Math.max(0, Math.min(chapters.length - 1, state.currentChapter + direction));
                
                if (nextChapter !== state.currentChapter) {
                    chapters[nextChapter].scrollIntoView({ behavior: 'smooth' });
                }
            }
            
            // Check for Konami code
            if (e.key === KONAMI_CODE[state.konamiIndex]) {
                state.konamiIndex++;
                if (state.konamiIndex === KONAMI_CODE.length) {
                    activateKonamiCode();
                    state.konamiIndex = 0;
                }
            } else {
                state.konamiIndex = 0;
            }
        });
    }
    
    // =========================================================================
    // EASTER EGGS
    // =========================================================================
    
    function initEasterEggs() {
        // Bill Nye seal click
        const seal = document.getElementById('bill-nye-seal');
        if (seal) {
            seal.addEventListener('click', () => {
                const meter = document.getElementById('significance-meter');
                if (meter) {
                    meter.classList.remove('celebrating');
                    void meter.offsetWidth; // Trigger reflow
                    meter.classList.add('celebrating');
                }
            });
            
            seal.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    seal.click();
                }
            });
        }
        
        // Triple-click title for night mode
        const title = document.querySelector('.overture-title');
        let clickCount = 0;
        let clickTimer;
        
        if (title) {
            title.addEventListener('click', () => {
                clickCount++;
                clearTimeout(clickTimer);
                
                if (clickCount === 3) {
                    document.body.classList.toggle('night-mode');
                    clickCount = 0;
                } else {
                    clickTimer = setTimeout(() => clickCount = 0, 500);
                }
            });
        }
    }
    
    function activateKonamiCode() {
        document.body.classList.add('konami-active');
        
        // Create confetti explosion
        for (let i = 0; i < 50; i++) {
            setTimeout(() => {
                if (interactiveCanvas) {
                    const x = Math.random() * canvasWidth;
                    const y = Math.random() * canvasHeight;
                    spawnS15Decomposition(x, y);
                }
            }, i * 50);
        }
        
        // Remove after 10 seconds
        setTimeout(() => {
            document.body.classList.remove('konami-active');
        }, 10000);
        
        console.log(`
    🎉 KONAMI CODE ACTIVATED!
    
    You found the secret. Here's your reward:
    
    The octonionic Hopf fibration is the only
    fibration of spheres that exists in dimension > 7.
    
    After S¹⁵, there are no more. The math ends here.
    
    That's not a limitation. That's a boundary condition
    on reality itself.
    
    h(x) ≥ 0 always
        `);
    }
    
    // =========================================================================
    // SIGNIFICANCE METER ANIMATION
    // =========================================================================
    
    function initSignificanceMeter() {
        const meter = document.getElementById('significance-meter');
        if (!meter) return;
        
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting && !state.prefersReducedMotion) {
                    setTimeout(() => {
                        meter.classList.add('celebrating');
                    }, 500);
                    observer.unobserve(meter);
                }
            });
        }, { threshold: 0.5 });
        
        observer.observe(meter);
    }
    
    // =========================================================================
    // SCROLL INDICATOR
    // =========================================================================
    
    const scrollIndicator = document.querySelector('.scroll-indicator');
    if (scrollIndicator) {
        scrollIndicator.addEventListener('click', () => {
            const chapter1 = document.getElementById('chapter-1');
            if (chapter1) {
                chapter1.scrollIntoView({ behavior: 'smooth' });
            }
        });
    }
    
    // =========================================================================
    // CONSOLE EASTER EGG
    // =========================================================================
    
    console.log(`
    🔮 OCTONI-ON or OCTONI-OFF?
    
    The octonionic Hopf fibration: S⁷ → S¹⁵ → S⁸
    
    When you encode to S¹⁵ and decompose:
    - Base (S⁸): What you're thinking about
    - Fiber (S⁷): Where to route it
    
    use_s15_encoder: bool = True  # Join us
    
    Keyboard shortcuts:
    - j/k: Navigate chapters
    - Konami code: Special surprise
    - Triple-click title: Night mode
    
    h(x) ≥ 0 always
    `);
    
    // =========================================================================
    // START
    // =========================================================================
    
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
    
})();
