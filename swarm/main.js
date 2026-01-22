/**
 * The Swarm — Main Application Logic
 * 
 * Handles:
 * - Section reveal animations
 * - Interactive demos
 * - Counter animations
 * - Race simulation
 * - Self-healing demo
 * - Economic agent simulation
 */

document.addEventListener('DOMContentLoaded', () => {
    // Remove loading state
    setTimeout(() => {
        document.body.classList.remove('loading');
    }, 100);
    
    // Initialize all modules
    initSectionObserver();
    initCounterAnimations();
    initRaceDemo();
    initHealingDemo();
    initEconomicDemo();
    initPipelineAnimation();
});

// ═══════════════════════════════════════════════════════════════════════════
// SECTION OBSERVER — Reveal on scroll
// ═══════════════════════════════════════════════════════════════════════════

function initSectionObserver() {
    const sections = document.querySelectorAll('.section');
    const primitiveCards = document.querySelectorAll('.primitive-card');
    const pipelineSteps = document.querySelectorAll('.pipeline-step');
    
    const observerOptions = {
        threshold: 0.15,
        rootMargin: '0px 0px -10% 0px'
    };
    
    const sectionObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
            }
        });
    }, observerOptions);
    
    sections.forEach(section => sectionObserver.observe(section));
    
    // Staggered reveal for cards
    const cardObserver = new IntersectionObserver((entries) => {
        entries.forEach((entry, index) => {
            if (entry.isIntersecting) {
                setTimeout(() => {
                    entry.target.classList.add('visible');
                }, index * 100);
            }
        });
    }, observerOptions);
    
    primitiveCards.forEach(card => cardObserver.observe(card));
    
    // Pipeline steps
    const pipelineObserver = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
            if (entry.isIntersecting) {
                const step = parseInt(entry.target.dataset.step);
                setTimeout(() => {
                    entry.target.classList.add('visible');
                }, (step - 1) * 200);
            }
        });
    }, observerOptions);
    
    pipelineSteps.forEach(step => pipelineObserver.observe(step));
}

// ═══════════════════════════════════════════════════════════════════════════
// COUNTER ANIMATIONS
// ═══════════════════════════════════════════════════════════════════════════

function initCounterAnimations() {
    const counters = document.querySelectorAll('[data-count]');
    
    const counterObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                animateCounter(entry.target);
                counterObserver.unobserve(entry.target);
            }
        });
    }, { threshold: 0.5 });
    
    counters.forEach(counter => counterObserver.observe(counter));
    
    // Revenue counter
    const revenueCounter = document.getElementById('revenue-counter');
    if (revenueCounter) {
        const revenueObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    animateValue(revenueCounter, 0, 8158, 2000, (val) => val.toLocaleString());
                    revenueObserver.unobserve(entry.target);
                }
            });
        }, { threshold: 0.5 });
        
        revenueObserver.observe(revenueCounter);
    }
}

function animateCounter(element) {
    const target = parseInt(element.dataset.count);
    const duration = 1500;
    const start = performance.now();
    
    function update(currentTime) {
        const elapsed = currentTime - start;
        const progress = Math.min(elapsed / duration, 1);
        const eased = easeOutExpo(progress);
        const current = Math.floor(eased * target);
        
        element.textContent = current;
        
        if (progress < 1) {
            requestAnimationFrame(update);
        } else {
            element.textContent = target;
        }
    }
    
    requestAnimationFrame(update);
}

function animateValue(element, start, end, duration, formatter = (v) => v) {
    const startTime = performance.now();
    
    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const eased = easeOutExpo(progress);
        const current = Math.floor(start + (end - start) * eased);
        
        element.textContent = formatter(current);
        
        if (progress < 1) {
            requestAnimationFrame(update);
        } else {
            element.textContent = formatter(end);
        }
    }
    
    requestAnimationFrame(update);
}

function easeOutExpo(x) {
    return x === 1 ? 1 : 1 - Math.pow(2, -10 * x);
}

// ═══════════════════════════════════════════════════════════════════════════
// RACE DEMO — 1 Browser vs 25 Browsers
// ═══════════════════════════════════════════════════════════════════════════

function initRaceDemo() {
    const singleTasks = document.getElementById('single-tasks');
    const swarmTasks = document.getElementById('swarm-tasks');
    const singleStatus = document.getElementById('single-status');
    const swarmStatus = document.getElementById('swarm-status');
    const speedupDisplay = document.getElementById('speedup-display');
    const speedupValue = document.getElementById('speedup-value');
    const startBtn = document.getElementById('race-start');
    
    if (!singleTasks || !swarmTasks) return;
    
    const taskCount = 25;
    let isRacing = false;
    
    // Create task bars
    function createTasks(container, count) {
        container.innerHTML = '';
        for (let i = 0; i < count; i++) {
            const task = document.createElement('div');
            task.className = 'race-task';
            task.innerHTML = `
                <div class="task-bar">
                    <div class="task-progress" data-task="${i}"></div>
                </div>
                <span class="task-label">${i + 1}</span>
            `;
            container.appendChild(task);
        }
    }
    
    createTasks(singleTasks, taskCount);
    createTasks(swarmTasks, taskCount);
    
    startBtn.addEventListener('click', () => {
        if (isRacing) return;
        isRacing = true;
        startBtn.textContent = 'Racing...';
        startBtn.disabled = true;
        speedupDisplay.style.opacity = '0';
        
        // Reset progress
        document.querySelectorAll('.task-progress').forEach(p => {
            p.style.width = '0%';
            p.classList.remove('complete');
        });
        
        singleStatus.textContent = 'Running';
        singleStatus.classList.add('running');
        swarmStatus.textContent = 'Running';
        swarmStatus.classList.add('running');
        
        // Single browser: sequential
        let singleComplete = 0;
        const singleTaskTime = 200; // ms per task
        
        function runSingleTask(index) {
            if (index >= taskCount) {
                singleStatus.textContent = 'Complete';
                singleStatus.classList.remove('running');
                singleStatus.classList.add('complete');
                return;
            }
            
            const progress = singleTasks.querySelector(`[data-task="${index}"]`);
            let p = 0;
            
            const interval = setInterval(() => {
                p += 10;
                progress.style.width = p + '%';
                
                if (p >= 100) {
                    clearInterval(interval);
                    progress.classList.add('complete');
                    singleComplete++;
                    runSingleTask(index + 1);
                }
            }, singleTaskTime / 10);
        }
        
        // Swarm: parallel (all 25 at once)
        let swarmComplete = 0;
        const swarmTaskTime = 200; // Same time per task, but parallel
        
        function runSwarmTasks() {
            const progressBars = swarmTasks.querySelectorAll('.task-progress');
            let p = 0;
            
            const interval = setInterval(() => {
                p += 10;
                progressBars.forEach(bar => {
                    bar.style.width = p + '%';
                });
                
                if (p >= 100) {
                    clearInterval(interval);
                    progressBars.forEach(bar => bar.classList.add('complete'));
                    swarmComplete = taskCount;
                    
                    swarmStatus.textContent = 'Complete';
                    swarmStatus.classList.remove('running');
                    swarmStatus.classList.add('complete');
                    
                    // Show speedup
                    setTimeout(() => {
                        speedupDisplay.style.opacity = '1';
                        animateValue(speedupValue, 1, 25, 1000, (v) => v + 'x');
                    }, 300);
                }
            }, swarmTaskTime / 10);
        }
        
        // Start both
        runSingleTask(0);
        runSwarmTasks();
        
        // Reset button after single browser finishes
        setTimeout(() => {
            isRacing = false;
            startBtn.textContent = 'Race Again';
            startBtn.disabled = false;
        }, taskCount * singleTaskTime + 500);
    });
}

// ═══════════════════════════════════════════════════════════════════════════
// HEALING DEMO
// ═══════════════════════════════════════════════════════════════════════════

function initHealingDemo() {
    const browser = document.getElementById('healing-browser');
    const status = document.getElementById('healing-status');
    const healCount = document.getElementById('heal-count');
    const triggerBtn = document.getElementById('trigger-error');
    
    if (!browser || !triggerBtn) return;
    
    let count = 847;
    
    triggerBtn.addEventListener('click', () => {
        if (browser.classList.contains('error') || browser.classList.contains('healing')) {
            return;
        }
        
        // Error state
        browser.classList.add('error');
        status.textContent = 'Error: Selector not found';
        browser.querySelector('.healing-icon').textContent = '❌';
        
        // Healing state
        setTimeout(() => {
            browser.classList.remove('error');
            browser.classList.add('healing');
            status.textContent = 'Self-healing...';
            browser.querySelector('.healing-icon').textContent = '🔄';
        }, 800);
        
        // Healed state
        setTimeout(() => {
            browser.classList.remove('healing');
            browser.classList.add('healed');
            status.textContent = 'Healed!';
            browser.querySelector('.healing-icon').textContent = '✅';
            
            // Increment counter
            count++;
            healCount.textContent = count;
            
            // Emit particles
            if (window.particleSystem) {
                const rect = browser.getBoundingClientRect();
                window.particleSystem.emit(
                    rect.left + rect.width / 2,
                    rect.top + rect.height / 2,
                    15,
                    'amber'
                );
            }
        }, 2000);
        
        // Reset to stable
        setTimeout(() => {
            browser.classList.remove('healed');
            status.textContent = 'Stable';
            browser.querySelector('.healing-icon').textContent = '🌐';
        }, 3500);
    });
}

// ═══════════════════════════════════════════════════════════════════════════
// ECONOMIC AGENT DEMO
// ═══════════════════════════════════════════════════════════════════════════

function initEconomicDemo() {
    const freelancerJobs = document.getElementById('freelancer-jobs');
    const indeedJobs = document.getElementById('indeed-jobs');
    
    if (!freelancerJobs || !indeedJobs) return;
    
    const freelancerData = [
        { title: 'Python API Development', budget: '$500', bids: '12' },
        { title: 'React Dashboard UI', budget: '$800', bids: '8' },
        { title: 'Data Scraping Script', budget: '$200', bids: '15' },
        { title: 'AWS Lambda Functions', budget: '$350', bids: '6' },
        { title: 'ML Model Training', budget: '$1,200', bids: '4' }
    ];
    
    const indeedData = [
        { title: 'Remote Backend Engineer', company: 'TechCorp', type: 'Contract' },
        { title: 'Full Stack Developer', company: 'StartupXYZ', type: 'Remote' },
        { title: 'DevOps Specialist', company: 'CloudInc', type: 'Part-time' }
    ];
    
    // Populate Freelancer jobs with stagger
    freelancerData.forEach((job, index) => {
        setTimeout(() => {
            const item = document.createElement('div');
            item.className = 'job-item';
            item.innerHTML = `
                <div class="job-title">${job.title}</div>
                <div class="job-meta">
                    <span>${job.budget}</span>
                    <span>${job.bids} bids</span>
                </div>
            `;
            freelancerJobs.appendChild(item);
            
            // Animate in
            setTimeout(() => item.classList.add('visible'), 50);
            
            // Simulate evaluation
            setTimeout(() => {
                item.classList.add('evaluating');
                setTimeout(() => {
                    item.classList.remove('evaluating');
                    if (index % 2 === 0) {
                        item.classList.add('bidding');
                        setTimeout(() => {
                            item.classList.remove('bidding');
                            if (index === 0) item.classList.add('won');
                        }, 1500);
                    }
                }, 1000);
            }, 2000 + index * 500);
        }, index * 300);
    });
    
    // Populate Indeed jobs
    indeedData.forEach((job, index) => {
        setTimeout(() => {
            const item = document.createElement('div');
            item.className = 'job-item';
            item.innerHTML = `
                <div class="job-title">${job.title}</div>
                <div class="job-meta">
                    <span>${job.company}</span>
                    <span>${job.type}</span>
                </div>
            `;
            indeedJobs.appendChild(item);
            setTimeout(() => item.classList.add('visible'), 50);
        }, 500 + index * 400);
    });
}

// ═══════════════════════════════════════════════════════════════════════════
// PIPELINE ANIMATION
// ═══════════════════════════════════════════════════════════════════════════

function initPipelineAnimation() {
    const steps = document.querySelectorAll('.pipeline-step');
    
    if (steps.length === 0) return;
    
    // Cycle through highlighting steps
    let currentStep = 0;
    
    function highlightStep() {
        steps.forEach(s => s.classList.remove('active'));
        steps[currentStep].classList.add('active');
        currentStep = (currentStep + 1) % steps.length;
    }
    
    // Start animation when section is visible
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                setInterval(highlightStep, 2000);
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.3 });
    
    observer.observe(document.getElementById('language'));
}

// ═══════════════════════════════════════════════════════════════════════════
// KONAMI CODE EASTER EGG
// ═══════════════════════════════════════════════════════════════════════════

(function() {
    const konamiCode = ['ArrowUp', 'ArrowUp', 'ArrowDown', 'ArrowDown', 
                        'ArrowLeft', 'ArrowRight', 'ArrowLeft', 'ArrowRight', 
                        'KeyB', 'KeyA'];
    let konamiIndex = 0;
    
    document.addEventListener('keydown', (e) => {
        if (e.code === konamiCode[konamiIndex]) {
            konamiIndex++;
            if (konamiIndex === konamiCode.length) {
                activateMaximumSwarm();
                konamiIndex = 0;
            }
        } else {
            konamiIndex = 0;
        }
    });
    
    function activateMaximumSwarm() {
        // Flash all nodes
        if (window.swarmViz) {
            window.swarmViz.nodes.forEach((node, i) => {
                setTimeout(() => {
                    node.classList.add('active');
                    
                    if (window.particleSystem) {
                        const rect = node.getBoundingClientRect();
                        window.particleSystem.emit(
                            rect.left + rect.width / 2,
                            rect.top + rect.height / 2,
                            20,
                            'magenta'
                        );
                    }
                }, i * 50);
            });
        }
        
        // Create burst effect
        if (window.particleSystem) {
            for (let i = 0; i < 100; i++) {
                setTimeout(() => {
                    window.particleSystem.emit(
                        window.innerWidth / 2 + (Math.random() - 0.5) * 200,
                        window.innerHeight / 2 + (Math.random() - 0.5) * 200,
                        5,
                        ['cyan', 'magenta', 'violet', 'amber'][Math.floor(Math.random() * 4)]
                    );
                }, i * 20);
            }
        }
        
        console.log('🕸️ MAXIMUM SWARM ACTIVATED 🕸️');
    }
})();
