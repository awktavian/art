/**
 * The Swarm — Main Application Logic
 * 
 * FIXES APPLIED:
 * - All intervals properly tracked and cleared
 * - Null checks before DOM operations
 * - Sound engine integration
 * - Enhanced Konami code easter egg
 * - Magnetic button effects
 * - Idle animation triggers
 */

document.addEventListener('DOMContentLoaded', function() {
    setTimeout(function() {
        document.body.classList.remove('loading');
    }, 100);
    
    initSoundEngine();
    initSectionObserver();
    initCounterAnimations();
    initRaceDemo();
    initHealingDemo();
    initEconomicDemo();
    initPipelineAnimation();
    initMagneticButtons();
    initIdleDetection();
});

// ═══════════════════════════════════════════════════════════════════════════
// SOUND ENGINE — Web Audio API for microdelights
// ═══════════════════════════════════════════════════════════════════════════

function initSoundEngine() {
    var SoundEngine = function() {
        this.ctx = null;
        this.masterGain = null;
        this.enabled = !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        this.initialized = false;
    };
    
    SoundEngine.prototype.init = function() {
        if (this.initialized || !this.enabled) return;
        try {
            this.ctx = new (window.AudioContext || window.webkitAudioContext)();
            this.masterGain = this.ctx.createGain();
            this.masterGain.connect(this.ctx.destination);
            this.masterGain.gain.value = 0.15;
            this.initialized = true;
        } catch (e) {
            this.enabled = false;
        }
    };
    
    SoundEngine.prototype.click = function() {
        if (!this.enabled) return;
        this.init();
        if (!this.ctx) return;
        
        var osc = this.ctx.createOscillator();
        var gain = this.ctx.createGain();
        osc.connect(gain);
        gain.connect(this.masterGain);
        osc.frequency.setValueAtTime(880, this.ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(440, this.ctx.currentTime + 0.08);
        gain.gain.setValueAtTime(0.3, this.ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, this.ctx.currentTime + 0.1);
        osc.start();
        osc.stop(this.ctx.currentTime + 0.1);
    };
    
    SoundEngine.prototype.boot = function(isCenter) {
        if (!this.enabled) return;
        this.init();
        if (!this.ctx) return;
        
        var osc = this.ctx.createOscillator();
        var gain = this.ctx.createGain();
        osc.connect(gain);
        gain.connect(this.masterGain);
        osc.frequency.value = isCenter ? 220 : 110;
        osc.type = 'sine';
        gain.gain.setValueAtTime(0.1, this.ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, this.ctx.currentTime + 0.15);
        osc.start();
        osc.stop(this.ctx.currentTime + 0.15);
    };
    
    SoundEngine.prototype.ready = function() {
        if (!this.enabled) return;
        this.init();
        if (!this.ctx) return;
        
        var notes = [523.25, 659.25, 783.99];
        var self = this;
        notes.forEach(function(freq, i) {
            setTimeout(function() {
                var osc = self.ctx.createOscillator();
                var gain = self.ctx.createGain();
                osc.connect(gain);
                gain.connect(self.masterGain);
                osc.frequency.value = freq;
                gain.gain.setValueAtTime(0.15, self.ctx.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.01, self.ctx.currentTime + 0.25);
                osc.start();
                osc.stop(self.ctx.currentTime + 0.25);
            }, i * 89);
        });
    };
    
    SoundEngine.prototype.success = function() {
        if (!this.enabled) return;
        this.init();
        if (!this.ctx) return;
        
        var notes = [659.25, 783.99, 1046.5];
        var self = this;
        notes.forEach(function(freq, i) {
            setTimeout(function() {
                var osc = self.ctx.createOscillator();
                var gain = self.ctx.createGain();
                osc.connect(gain);
                gain.connect(self.masterGain);
                osc.frequency.value = freq;
                gain.gain.setValueAtTime(0.2, self.ctx.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.01, self.ctx.currentTime + 0.3);
                osc.start();
                osc.stop(self.ctx.currentTime + 0.3);
            }, i * 100);
        });
    };
    
    SoundEngine.prototype.fanfare = function() {
        if (!this.enabled) return;
        this.init();
        if (!this.ctx) return;
        
        var notes = [523.25, 659.25, 783.99, 1046.5, 1318.5];
        var self = this;
        notes.forEach(function(freq, i) {
            setTimeout(function() {
                var osc = self.ctx.createOscillator();
                var gain = self.ctx.createGain();
                osc.connect(gain);
                gain.connect(self.masterGain);
                osc.frequency.value = freq;
                osc.type = i === 4 ? 'triangle' : 'sine';
                gain.gain.setValueAtTime(0.25, self.ctx.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.01, self.ctx.currentTime + (i === 4 ? 0.8 : 0.2));
                osc.start();
                osc.stop(self.ctx.currentTime + (i === 4 ? 0.8 : 0.2));
            }, i * 80);
        });
    };
    
    window.soundEngine = new SoundEngine();
}

// ═══════════════════════════════════════════════════════════════════════════
// SECTION OBSERVER — Reveal on scroll
// ═══════════════════════════════════════════════════════════════════════════

function initSectionObserver() {
    var sections = document.querySelectorAll('.section');
    var primitiveCards = document.querySelectorAll('.primitive-card');
    var pipelineSteps = document.querySelectorAll('.pipeline-step');
    
    var observerOptions = {
        threshold: 0.15,
        rootMargin: '0px 0px -10% 0px'
    };
    
    var sectionObserver = new IntersectionObserver(function(entries) {
        entries.forEach(function(entry) {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
            }
        });
    }, observerOptions);
    
    sections.forEach(function(section) { sectionObserver.observe(section); });
    
    var cardObserver = new IntersectionObserver(function(entries) {
        entries.forEach(function(entry, entryIdx) {
            if (entry.isIntersecting) {
                setTimeout(function() {
                    entry.target.classList.add('visible');
                }, entryIdx * 100);
            }
        });
    }, observerOptions);
    
    primitiveCards.forEach(function(card) { cardObserver.observe(card); });
    
    var pipelineObserver = new IntersectionObserver(function(entries) {
        entries.forEach(function(entry) {
            if (entry.isIntersecting) {
                var step = parseInt(entry.target.dataset.step);
                setTimeout(function() {
                    entry.target.classList.add('visible');
                }, (step - 1) * 200);
            }
        });
    }, observerOptions);
    
    pipelineSteps.forEach(function(step) { pipelineObserver.observe(step); });
}

// ═══════════════════════════════════════════════════════════════════════════
// COUNTER ANIMATIONS
// ═══════════════════════════════════════════════════════════════════════════

function initCounterAnimations() {
    var counters = document.querySelectorAll('[data-count]');
    
    var counterObserver = new IntersectionObserver(function(entries) {
        entries.forEach(function(entry) {
            if (entry.isIntersecting) {
                animateCounter(entry.target);
                counterObserver.unobserve(entry.target);
            }
        });
    }, { threshold: 0.5 });
    
    counters.forEach(function(counter) { counterObserver.observe(counter); });
    
    var revenueCounter = document.getElementById('revenue-counter');
    if (revenueCounter) {
        var revenueObserver = new IntersectionObserver(function(entries) {
            entries.forEach(function(entry) {
                if (entry.isIntersecting) {
                    animateValue(revenueCounter, 0, 8158, 2000, function(val) { return val.toLocaleString(); });
                    revenueObserver.unobserve(entry.target);
                }
            });
        }, { threshold: 0.5 });
        
        revenueObserver.observe(revenueCounter);
    }
}

function animateCounter(element) {
    var target = parseInt(element.dataset.count);
    if (isNaN(target)) {
        console.warn('Invalid data-count:', element.dataset.count);
        return;
    }
    
    var duration = 1500;
    var start = performance.now();
    
    function update(currentTime) {
        var elapsed = currentTime - start;
        var progress = Math.min(elapsed / duration, 1);
        var eased = easeOutExpo(progress);
        var current = Math.floor(eased * target);
        
        element.textContent = current;
        
        if (progress < 1) {
            requestAnimationFrame(update);
        } else {
            element.textContent = target;
        }
    }
    
    requestAnimationFrame(update);
}

function animateValue(element, start, end, duration, formatter) {
    formatter = formatter || function(v) { return v; };
    var startTime = performance.now();
    
    function update(currentTime) {
        var elapsed = currentTime - startTime;
        var progress = Math.min(elapsed / duration, 1);
        var eased = easeOutExpo(progress);
        var current = Math.floor(start + (end - start) * eased);
        
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

var raceIntervals = [];

function initRaceDemo() {
    var singleTasks = document.getElementById('single-tasks');
    var swarmTasks = document.getElementById('swarm-tasks');
    var singleStatus = document.getElementById('single-status');
    var swarmStatus = document.getElementById('swarm-status');
    var speedupDisplay = document.getElementById('speedup-display');
    var speedupValue = document.getElementById('speedup-value');
    var startBtn = document.getElementById('race-start');
    
    if (!singleTasks || !swarmTasks || !startBtn) return;
    
    var taskCount = 25;
    var isRacing = false;
    
    function createTasks(container, count) {
        container.innerHTML = '';
        for (var i = 0; i < count; i++) {
            var task = document.createElement('div');
            task.className = 'race-task';
            task.innerHTML = '<div class="task-bar"><div class="task-progress" data-task="' + i + '"></div></div><span class="task-label">' + (i + 1) + '</span>';
            container.appendChild(task);
        }
    }
    
    createTasks(singleTasks, taskCount);
    createTasks(swarmTasks, taskCount);
    
    startBtn.addEventListener('click', function() {
        if (isRacing) return;
        isRacing = true;
        startBtn.textContent = 'Racing...';
        startBtn.disabled = true;
        startBtn.style.cursor = 'wait';
        if (speedupDisplay) speedupDisplay.style.opacity = '0';
        
        // Clear any existing intervals
        raceIntervals.forEach(function(id) { clearInterval(id); });
        raceIntervals = [];
        
        // Reset progress
        document.querySelectorAll('.task-progress').forEach(function(p) {
            p.style.width = '0%';
            p.classList.remove('complete');
        });
        
        if (singleStatus) {
            singleStatus.textContent = 'Running';
            singleStatus.classList.add('running');
            singleStatus.classList.remove('complete');
        }
        if (swarmStatus) {
            swarmStatus.textContent = 'Running';
            swarmStatus.classList.add('running');
            swarmStatus.classList.remove('complete');
        }
        
        var singleComplete = 0;
        var singleTaskTime = 200;
        
        function runSingleTask(taskIdx) {
            if (taskIdx >= taskCount) {
                if (singleStatus) {
                    singleStatus.textContent = 'Complete';
                    singleStatus.classList.remove('running');
                    singleStatus.classList.add('complete');
                }
                return;
            }
            
            var progress = singleTasks.querySelector('[data-task="' + taskIdx + '"]');
            if (!progress) return;
            
            var p = 0;
            
            var interval = setInterval(function() {
                p += 10;
                progress.style.width = p + '%';
                
                if (p >= 100) {
                    clearInterval(interval);
                    var idx = raceIntervals.indexOf(interval);
                    if (idx > -1) raceIntervals.splice(idx, 1);
                    
                    progress.classList.add('complete');
                    singleComplete++;
                    runSingleTask(taskIdx + 1);
                }
            }, singleTaskTime / 10);
            
            raceIntervals.push(interval);
        }
        
        var swarmComplete = 0;
        var swarmTaskTime = 200;
        
        function runSwarmTasks() {
            var progressBars = swarmTasks.querySelectorAll('.task-progress');
            var p = 0;
            
            var interval = setInterval(function() {
                p += 10;
                progressBars.forEach(function(bar) {
                    bar.style.width = p + '%';
                });
                
                if (p >= 100) {
                    clearInterval(interval);
                    var idx = raceIntervals.indexOf(interval);
                    if (idx > -1) raceIntervals.splice(idx, 1);
                    
                    progressBars.forEach(function(bar) { bar.classList.add('complete'); });
                    swarmComplete = taskCount;
                    
                    if (swarmStatus) {
                        swarmStatus.textContent = 'Complete';
                        swarmStatus.classList.remove('running');
                        swarmStatus.classList.add('complete');
                    }
                    
                    // Play success sound
                    if (window.soundEngine) {
                        window.soundEngine.success();
                    }
                    
                    // Show speedup with confetti
                    setTimeout(function() {
                        if (speedupDisplay) speedupDisplay.style.opacity = '1';
                        if (speedupValue) animateValue(speedupValue, 1, 25, 1000, function(v) { return v + 'x'; });
                        
                        // Confetti burst
                        createConfetti();
                    }, 300);
                }
            }, swarmTaskTime / 10);
            
            raceIntervals.push(interval);
        }
        
        runSingleTask(0);
        runSwarmTasks();
        
        setTimeout(function() {
            isRacing = false;
            startBtn.textContent = 'Race Again';
            startBtn.disabled = false;
            startBtn.style.cursor = '';
        }, taskCount * singleTaskTime + 500);
    });
}

function createConfetti() {
    var colors = ['#00F5D4', '#F15BB5', '#9B5DE5', '#FEE440'];
    var container = document.body;
    
    for (var i = 0; i < 50; i++) {
        (function(idx) {
            setTimeout(function() {
                var confetti = document.createElement('div');
                confetti.style.cssText = 'position:fixed;width:10px;height:10px;background:' + colors[idx % 4] + ';pointer-events:none;z-index:9999;border-radius:50%;left:' + (window.innerWidth / 2 + (Math.random() - 0.5) * 200) + 'px;top:' + (window.innerHeight / 2) + 'px;opacity:1;transition:all 1.5s ease-out;';
                container.appendChild(confetti);
                
                requestAnimationFrame(function() {
                    confetti.style.transform = 'translate(' + ((Math.random() - 0.5) * 400) + 'px, ' + (Math.random() * 400 + 100) + 'px) rotate(' + (Math.random() * 720) + 'deg)';
                    confetti.style.opacity = '0';
                });
                
                setTimeout(function() { confetti.remove(); }, 1500);
            }, idx * 20);
        })(i);
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// HEALING DEMO
// ═══════════════════════════════════════════════════════════════════════════

function initHealingDemo() {
    var browser = document.getElementById('healing-browser');
    var status = document.getElementById('healing-status');
    var healCount = document.getElementById('heal-count');
    var triggerBtn = document.getElementById('trigger-error');
    
    if (!browser || !triggerBtn) return;
    
    var count = 847;
    
    triggerBtn.addEventListener('click', function() {
        if (browser.classList.contains('error') || browser.classList.contains('healing')) {
            return;
        }
        
        var icon = browser.querySelector('.healing-icon');
        
        // Error state
        browser.classList.add('error');
        if (status) status.textContent = 'Error: Selector not found';
        if (icon) icon.textContent = '❌';
        
        // Healing state
        setTimeout(function() {
            browser.classList.remove('error');
            browser.classList.add('healing');
            if (status) status.textContent = 'Self-healing...';
            if (icon) icon.textContent = '🔄';
        }, 800);
        
        // Healed state
        setTimeout(function() {
            browser.classList.remove('healing');
            browser.classList.add('healed');
            if (status) status.textContent = 'Healed!';
            if (icon) icon.textContent = '✅';
            
            count++;
            if (healCount) healCount.textContent = count;
            
            if (window.soundEngine) {
                window.soundEngine.success();
            }
            
            if (window.particleSystem) {
                var rect = browser.getBoundingClientRect();
                window.particleSystem.emit(rect.left + rect.width / 2, rect.top + rect.height / 2, 15, 'amber');
            }
        }, 2000);
        
        // Reset to stable
        setTimeout(function() {
            browser.classList.remove('healed');
            if (status) status.textContent = 'Stable';
            if (icon) icon.textContent = '🌐';
        }, 3500);
    });
}

// ═══════════════════════════════════════════════════════════════════════════
// ECONOMIC AGENT DEMO
// ═══════════════════════════════════════════════════════════════════════════

function initEconomicDemo() {
    var freelancerJobs = document.getElementById('freelancer-jobs');
    var indeedJobs = document.getElementById('indeed-jobs');
    
    if (!freelancerJobs || !indeedJobs) return;
    
    var freelancerData = [
        { title: 'Python API Development', budget: '$500', bids: '12' },
        { title: 'React Dashboard UI', budget: '$800', bids: '8' },
        { title: 'Data Scraping Script', budget: '$200', bids: '15' },
        { title: 'AWS Lambda Functions', budget: '$350', bids: '6' },
        { title: 'ML Model Training', budget: '$1,200', bids: '4' }
    ];
    
    var indeedData = [
        { title: 'Remote Backend Engineer', company: 'TechCorp', type: 'Contract' },
        { title: 'Full Stack Developer', company: 'StartupXYZ', type: 'Remote' },
        { title: 'DevOps Specialist', company: 'CloudInc', type: 'Part-time' }
    ];
    
    freelancerData.forEach(function(job, jobIdx) {
        setTimeout(function() {
            var item = document.createElement('div');
            item.className = 'job-item';
            item.innerHTML = '<div class="job-title">' + job.title + '</div><div class="job-meta"><span>' + job.budget + '</span><span>' + job.bids + ' bids</span></div>';
            freelancerJobs.appendChild(item);
            
            setTimeout(function() { item.classList.add('visible'); }, 50);
            
            setTimeout(function() {
                item.classList.add('evaluating');
                setTimeout(function() {
                    item.classList.remove('evaluating');
                    if (jobIdx % 2 === 0) {
                        item.classList.add('bidding');
                        setTimeout(function() {
                            item.classList.remove('bidding');
                            if (jobIdx === 0) item.classList.add('won');
                        }, 1500);
                    }
                }, 1000);
            }, 2000 + jobIdx * 500);
        }, jobIdx * 300);
    });
    
    indeedData.forEach(function(job, jobIdx) {
        setTimeout(function() {
            var item = document.createElement('div');
            item.className = 'job-item';
            item.innerHTML = '<div class="job-title">' + job.title + '</div><div class="job-meta"><span>' + job.company + '</span><span>' + job.type + '</span></div>';
            indeedJobs.appendChild(item);
            setTimeout(function() { item.classList.add('visible'); }, 50);
        }, 500 + jobIdx * 400);
    });
}

// ═══════════════════════════════════════════════════════════════════════════
// PIPELINE ANIMATION
// ═══════════════════════════════════════════════════════════════════════════

var pipelineIntervalId = null;

function initPipelineAnimation() {
    var steps = document.querySelectorAll('.pipeline-step');
    var languageSection = document.getElementById('language');
    
    if (steps.length === 0 || !languageSection) return;
    
    var currentStep = 0;
    
    function highlightStep() {
        steps.forEach(function(s) { s.classList.remove('active'); });
        steps[currentStep].classList.add('active');
        currentStep = (currentStep + 1) % steps.length;
    }
    
    var observer = new IntersectionObserver(function(entries) {
        entries.forEach(function(entry) {
            if (entry.isIntersecting) {
                // Clear any existing interval
                if (pipelineIntervalId) clearInterval(pipelineIntervalId);
                pipelineIntervalId = setInterval(highlightStep, 2000);
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.3 });
    
    observer.observe(languageSection);
    
    // Clean up on page unload
    window.addEventListener('beforeunload', function() {
        if (pipelineIntervalId) clearInterval(pipelineIntervalId);
    });
}

// ═══════════════════════════════════════════════════════════════════════════
// MAGNETIC BUTTONS
// ═══════════════════════════════════════════════════════════════════════════

function initMagneticButtons() {
    var buttons = document.querySelectorAll('.btn, #race-start, #trigger-error');
    
    buttons.forEach(function(btn) {
        btn.addEventListener('mousemove', function(e) {
            var rect = btn.getBoundingClientRect();
            var x = e.clientX - rect.left - rect.width / 2;
            var y = e.clientY - rect.top - rect.height / 2;
            btn.style.transform = 'translate(' + (x * 0.15) + 'px, ' + (y * 0.15) + 'px)';
        });
        
        btn.addEventListener('mouseleave', function() {
            btn.style.transform = '';
        });
        
        btn.addEventListener('mousedown', function() {
            if (window.soundEngine) {
                window.soundEngine.click();
            }
        });
    });
}

// ═══════════════════════════════════════════════════════════════════════════
// IDLE DETECTION
// ═══════════════════════════════════════════════════════════════════════════

var idleTimer = null;
var idleTriggered = false;

function initIdleDetection() {
    function resetIdleTimer() {
        if (idleTimer) clearTimeout(idleTimer);
        idleTriggered = false;
        idleTimer = setTimeout(triggerIdleAnimation, 30000);
    }
    
    function triggerIdleAnimation() {
        if (idleTriggered) return;
        idleTriggered = true;
        
        if (window.swarmViz && window.swarmViz.nodes.length) {
            window.swarmViz.nodes.forEach(function(node, i) {
                setTimeout(function() {
                    node.classList.add('idle-pulse');
                    setTimeout(function() { node.classList.remove('idle-pulse'); }, 1000);
                }, i * 100);
            });
        }
    }
    
    ['mousemove', 'keydown', 'scroll', 'touchstart'].forEach(function(event) {
        document.addEventListener(event, resetIdleTimer, { passive: true });
    });
    
    resetIdleTimer();
}

// ═══════════════════════════════════════════════════════════════════════════
// KONAMI CODE EASTER EGG — ENHANCED
// ═══════════════════════════════════════════════════════════════════════════

(function() {
    var konamiCode = ['ArrowUp', 'ArrowUp', 'ArrowDown', 'ArrowDown', 
                      'ArrowLeft', 'ArrowRight', 'ArrowLeft', 'ArrowRight', 
                      'KeyB', 'KeyA'];
    var konamiIndex = 0;
    
    document.addEventListener('keydown', function(e) {
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
        // Sound fanfare
        if (window.soundEngine) {
            window.soundEngine.fanfare();
        }
        
        // Haptic feedback
        if (navigator.vibrate) {
            navigator.vibrate([100, 50, 100, 50, 200]);
        }
        
        // Create achievement modal
        var modal = document.createElement('div');
        modal.className = 'achievement-modal';
        modal.innerHTML = '<div class="achievement-content"><div class="achievement-icon">🏆</div><h3>MAXIMUM SWARM UNLOCKED</h3><p>You discovered the Konami code!</p><code style="display:block;background:#020810;padding:12px;border-radius:8px;margin:16px 0;color:#00F5D4;font-size:14px;">SWARM-EARLY-2026</code><p style="font-size:12px;color:rgba(255,255,255,0.5);">Click anywhere to dismiss</p></div>';
        modal.style.cssText = 'position:fixed;inset:0;background:rgba(2,8,16,0.95);display:flex;align-items:center;justify-content:center;z-index:10000;opacity:0;transition:opacity 0.3s ease-out;';
        
        var content = modal.querySelector('.achievement-content');
        content.style.cssText = 'text-align:center;padding:48px;background:linear-gradient(135deg,rgba(0,245,212,0.1),rgba(241,91,181,0.1));border:2px solid rgba(0,245,212,0.5);border-radius:24px;max-width:400px;transform:scale(0.9);transition:transform 0.3s ease-out;';
        
        document.body.appendChild(modal);
        
        requestAnimationFrame(function() {
            modal.style.opacity = '1';
            content.style.transform = 'scale(1)';
        });
        
        // Flash all nodes
        if (window.swarmViz) {
            window.swarmViz.flashAll();
        }
        
        // Massive particle explosion
        if (window.particleSystem) {
            for (var i = 0; i < 100; i++) {
                (function(idx) {
                    setTimeout(function() {
                        var colors = ['cyan', 'magenta', 'violet', 'amber'];
                        window.particleSystem.emit(
                            window.innerWidth / 2 + (Math.random() - 0.5) * 300,
                            window.innerHeight / 2 + (Math.random() - 0.5) * 300,
                            5,
                            colors[idx % 4]
                        );
                    }, idx * 15);
                })(i);
            }
        }
        
        // Dismiss modal on click
        modal.addEventListener('click', function() {
            modal.style.opacity = '0';
            content.style.transform = 'scale(0.9)';
            setTimeout(function() { modal.remove(); }, 300);
        });
        
        console.log('%c🕸️ MAXIMUM SWARM ACTIVATED 🕸️', 'font-size: 24px; color: #00F5D4; text-shadow: 0 0 10px #00F5D4;');
        console.log('%cUse code SWARM-EARLY-2026 for early access!', 'font-size: 14px; color: #F15BB5;');
    }
})();
