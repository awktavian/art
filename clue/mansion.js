/* ═══════════════════════════════════════════════════════════════════════════════════════════
   🏛️ THE HOUSE — Interactive Mansion System
   
   For Jill — Product Manager · Clue Enthusiast
   
   Features:
   ├── Candlelight particle system
   ├── Dust motes physics
   ├── Room interactions & modal details
   ├── Secret passage Fano plane visualization
   ├── Multiple endings
   ├── Typed secrets (flames, wadsworth, passage)
   ├── Konami code
   ├── Console API
   └── Evidence counter animations
   
═══════════════════════════════════════════════════════════════════════════════════════════ */

(function() {
'use strict';

// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════

const state = {
    loaded: false,
    visits: parseInt(localStorage.getItem('mansion_visits') || '0') + 1,
    secretsFound: JSON.parse(localStorage.getItem('mansion_secrets') || '[]'),
    currentEnding: null,
    mouse: { x: window.innerWidth / 2, y: window.innerHeight / 2 },
    typed: { buffer: '', timeout: null },
    konami: { sequence: [], target: [38, 38, 40, 40, 37, 39, 37, 39, 66, 65] },
    candles: [],
    dust: [],
    isMobile: /Android|iPhone|iPad|iPod/i.test(navigator.userAgent),
    reducedMotion: window.matchMedia('(prefers-reduced-motion: reduce)').matches
};

localStorage.setItem('mansion_visits', state.visits.toString());

// ═══════════════════════════════════════════════════════════════
// ELEMENTS
// ═══════════════════════════════════════════════════════════════

const $ = sel => document.querySelector(sel);
const $$ = sel => document.querySelectorAll(sel);

const elements = {
    loading: $('#loading'),
    loadingProgress: $('#loading-progress'),
    cursor: $('#cursor'),
    candleCanvas: $('#candlelight-canvas'),
    dustCanvas: $('#dust-canvas'),
    passageCanvas: $('#passage-canvas'),
    floorPlan: $('#floor-plan'),
    fanoPlane: $('#fano-plane'),
    modal: $('#room-modal'),
    modalBody: $('#modal-body'),
    endingContent: $('#ending-content'),
    visitCount: $('#visit-count'),
    wadsworhText: $('#wadsworth-text'),
    sections: $$('section'),
    rooms: $$('.room'),
    structures: $$('.structure'),
    characterCards: $$('.character-card'),
    endingBtns: $$('.ending-btn'),
    passageItems: $$('.passage-item'),
    fanoNodes: $$('.fano-node'),
    evidenceValues: $$('.evidence-value')
};

// ═══════════════════════════════════════════════════════════════
// LOADING
// ═══════════════════════════════════════════════════════════════

function initLoading() {
    let progress = 0;
    const interval = setInterval(() => {
        progress += Math.random() * 15 + 5;
        if (progress >= 100) {
            progress = 100;
            clearInterval(interval);
            setTimeout(finishLoading, 600);
        }
        elements.loadingProgress.style.width = progress + '%';
    }, 150);
}

function finishLoading() {
    elements.loading.classList.add('hidden');
    state.loaded = true;
    initAllSystems();
}

// ═══════════════════════════════════════════════════════════════
// CURSOR
// ═══════════════════════════════════════════════════════════════

function initCursor() {
    if (state.isMobile) return;
    
    document.addEventListener('mousemove', e => {
        state.mouse.x = e.clientX;
        state.mouse.y = e.clientY;
        elements.cursor.style.left = e.clientX + 'px';
        elements.cursor.style.top = e.clientY + 'px';
    });
    
    const hoverables = $$('a, button, .room, .structure, .character-card, .passage-item, .ending-btn, .fano-node, .sig-kanji, .modal-close');
    hoverables.forEach(el => {
        el.addEventListener('mouseenter', () => elements.cursor.classList.add('hovering'));
        el.addEventListener('mouseleave', () => elements.cursor.classList.remove('hovering'));
    });
}

// ═══════════════════════════════════════════════════════════════
// CANDLELIGHT CANVAS
// ═══════════════════════════════════════════════════════════════

function initCandleCanvas() {
    const canvas = elements.candleCanvas;
    const ctx = canvas.getContext('2d');
    
    function resize() {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
    }
    resize();
    window.addEventListener('resize', resize);
    
    // Create candle light sources
    const candleCount = state.reducedMotion ? 3 : 7;
    for (let i = 0; i < candleCount; i++) {
        state.candles.push({
            x: Math.random() * canvas.width,
            y: Math.random() * canvas.height,
            baseRadius: 100 + Math.random() * 150,
            phase: Math.random() * Math.PI * 2,
            speed: 0.02 + Math.random() * 0.02,
            color: Math.random() > 0.5 ? 'rgba(255, 179, 71,' : 'rgba(201, 162, 39,'
        });
    }
    
    function animate() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        state.candles.forEach(candle => {
            candle.phase += candle.speed;
            const flicker = Math.sin(candle.phase) * 0.2 + Math.sin(candle.phase * 2.3) * 0.1;
            const radius = candle.baseRadius * (1 + flicker);
            
            const gradient = ctx.createRadialGradient(
                candle.x, candle.y, 0,
                candle.x, candle.y, radius
            );
            gradient.addColorStop(0, candle.color + '0.15)');
            gradient.addColorStop(0.5, candle.color + '0.05)');
            gradient.addColorStop(1, 'transparent');
            
            ctx.fillStyle = gradient;
            ctx.beginPath();
            ctx.arc(candle.x, candle.y, radius, 0, Math.PI * 2);
            ctx.fill();
        });
        
        if (!state.reducedMotion) {
            requestAnimationFrame(animate);
        }
    }
    animate();
}

// ═══════════════════════════════════════════════════════════════
// DUST CANVAS
// ═══════════════════════════════════════════════════════════════

function initDustCanvas() {
    const canvas = elements.dustCanvas;
    const ctx = canvas.getContext('2d');
    
    function resize() {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
    }
    resize();
    window.addEventListener('resize', resize);
    
    // Create dust particles
    const dustCount = state.reducedMotion ? 20 : 60;
    for (let i = 0; i < dustCount; i++) {
        state.dust.push({
            x: Math.random() * canvas.width,
            y: Math.random() * canvas.height,
            vx: (Math.random() - 0.5) * 0.2,
            vy: (Math.random() - 0.5) * 0.1 - 0.05,
            size: Math.random() * 2 + 0.5,
            opacity: Math.random() * 0.4 + 0.1,
            wobble: Math.random() * Math.PI * 2,
            wobbleSpeed: Math.random() * 0.01 + 0.005
        });
    }
    
    function animate() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        state.dust.forEach(d => {
            d.wobble += d.wobbleSpeed;
            const wobbleX = Math.sin(d.wobble) * 0.3;
            
            // Mouse repulsion
            const dx = state.mouse.x - d.x;
            const dy = state.mouse.y - d.y;
            const dist = Math.sqrt(dx * dx + dy * dy);
            if (dist < 150 && dist > 0) {
                const force = (150 - dist) / 150 * 0.01;
                d.vx -= (dx / dist) * force;
                d.vy -= (dy / dist) * force;
            }
            
            d.x += d.vx + wobbleX;
            d.y += d.vy;
            d.vx *= 0.99;
            d.vy *= 0.99;
            
            // Wrap
            if (d.x < -10) d.x = canvas.width + 10;
            if (d.x > canvas.width + 10) d.x = -10;
            if (d.y < -10) d.y = canvas.height + 10;
            if (d.y > canvas.height + 10) d.y = -10;
            
            ctx.beginPath();
            ctx.arc(d.x, d.y, d.size, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(245, 230, 211, ${d.opacity})`;
            ctx.fill();
        });
        
        if (!state.reducedMotion) {
            requestAnimationFrame(animate);
        }
    }
    animate();
}

// ═══════════════════════════════════════════════════════════════
// SCROLL REVEALS
// ═══════════════════════════════════════════════════════════════

function initScrollReveals() {
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
                
                // Animate evidence counters in reveal section
                if (entry.target.id === 'reveal') {
                    animateEvidenceCounters();
                }
            }
        });
    }, { threshold: 0.15 });
    
    elements.sections.forEach(section => observer.observe(section));
}

// ═══════════════════════════════════════════════════════════════
// EVIDENCE COUNTERS
// ═══════════════════════════════════════════════════════════════

function animateEvidenceCounters() {
    elements.evidenceValues.forEach((el, i) => {
        setTimeout(() => {
            if (el.classList.contains('counted')) return;
            el.classList.add('counted');
            
            const target = parseInt(el.dataset.count);
            const duration = 2000;
            const start = Date.now();
            
            function update() {
                const elapsed = Date.now() - start;
                const progress = Math.min(elapsed / duration, 1);
                const eased = 1 - Math.pow(1 - progress, 3);
                const current = Math.floor(target * eased);
                el.textContent = current.toLocaleString();
                if (progress < 1) requestAnimationFrame(update);
            }
            update();
        }, i * 150);
    });
}

// ═══════════════════════════════════════════════════════════════
// ROOM INTERACTIONS
// ═══════════════════════════════════════════════════════════════

function initRoomInteractions() {
    // Room clicks
    elements.rooms.forEach(room => {
        room.addEventListener('click', () => {
            const roomId = room.dataset.room;
            showRoomDetail(roomId);
        });
    });
    
    // Structure clicks
    elements.structures.forEach(structure => {
        structure.addEventListener('click', () => {
            const roomId = structure.dataset.room;
            showRoomDetail(roomId);
        });
    });
    
    // Character card clicks
    elements.characterCards.forEach(card => {
        card.addEventListener('click', () => {
            const character = card.dataset.character;
            showCharacterDetail(character);
        });
    });
    
    // Modal close
    const modalClose = $('.modal-close');
    const modal = $('.modal');
    if (modalClose) modalClose.addEventListener('click', closeModal);
    if (modal) modal.addEventListener('click', e => {
        if (e.target === modal) closeModal();
    });
    
    document.addEventListener('keydown', e => {
        if (e.key === 'Escape') closeModal();
    });
}

function showRoomDetail(roomId) {
    const room = window.ROOMS[roomId];
    if (!room) return;
    
    const character = room.character ? window.CHARACTERS[room.character] : null;
    
    let html = `
        <div class="modal-room">
            <div style="font-size: 3rem; text-align: center; margin-bottom: 1rem;">${room.icon}</div>
            <h3>${room.name}</h3>
            <p class="modal-subtitle">${room.colony.toUpperCase()} ${character ? `· ${character.name}` : ''}</p>
            <p>${room.description}</p>
            <p><strong>Function:</strong> ${room.function}</p>
            <p><code>${room.codePath}</code></p>
    `;
    
    if (character) {
        const quote = character.quotes[Math.floor(Math.random() * character.quotes.length)];
        html += `<blockquote>"${quote}"</blockquote>`;
    }
    
    html += `</div>`;
    
    elements.modalBody.innerHTML = html;
    elements.modal.classList.add('active');
}

function showCharacterDetail(characterId) {
    const character = window.CHARACTERS[characterId];
    if (!character) return;
    
    const quote = character.quotes[Math.floor(Math.random() * character.quotes.length)];
    
    const html = `
        <div class="modal-character" style="border-left: 3px solid ${character.color};">
            <div style="font-size: 4rem; text-align: center; margin-bottom: 1rem;">${getColonyIcon(character.colony)}</div>
            <h3>${character.name}</h3>
            <p class="modal-subtitle">${character.colony} · ${character.basis} · ${character.catastrophe}</p>
            <p><strong>Room:</strong> ${character.room}</p>
            <p><strong>Role:</strong> ${character.role}</p>
            <blockquote>"${quote}"</blockquote>
            <p>${character.description}</p>
            <p><code>${character.code}</code></p>
        </div>
    `;
    
    elements.modalBody.innerHTML = html;
    elements.modal.classList.add('active');
}

function closeModal() {
    elements.modal.classList.remove('active');
}

function getColonyIcon(colony) {
    const icons = {
        'Spark': '🔥', 'Forge': '⚒️', 'Flow': '🌊', 'Nexus': '🔗',
        'Beacon': '🗼', 'Grove': '🌿', 'Crystal': '💎', 'Kagami': '🏛️'
    };
    return icons[colony] || '✧';
}

// ═══════════════════════════════════════════════════════════════
// FANO PLANE INTERACTIONS
// ═══════════════════════════════════════════════════════════════

function initFanoInteractions() {
    elements.fanoNodes.forEach(node => {
        node.addEventListener('mouseenter', () => {
            const colony = node.dataset.colony;
            highlightColony(colony);
        });
        
        node.addEventListener('mouseleave', () => {
            clearHighlights();
        });
    });
    
    elements.passageItems.forEach(item => {
        item.addEventListener('click', () => {
            const passage = item.dataset.passage;
            showPassageDetail(passage);
        });
    });
}

function highlightColony(colony) {
    // Highlight matching rooms
    elements.rooms.forEach(room => {
        if (room.dataset.colony === colony) {
            room.style.transform = 'scale(1.05)';
            room.style.borderColor = 'var(--mansion-gold)';
        }
    });
    
    // Highlight matching character cards
    elements.characterCards.forEach(card => {
        if (card.dataset.colony === colony) {
            card.style.transform = 'scale(1.02)';
        }
    });
}

function clearHighlights() {
    elements.rooms.forEach(room => {
        room.style.transform = '';
        room.style.borderColor = '';
    });
    
    elements.characterCards.forEach(card => {
        card.style.transform = '';
    });
}

function showPassageDetail(passageId) {
    const [from, to] = passageId.split('-');
    const passage = window.SECRET_PASSAGES.find(p => p.from === from && p.to === to);
    if (!passage) return;
    
    const html = `
        <div class="modal-passage">
            <h3>Secret Passage</h3>
            <p class="modal-subtitle">${window.ROOMS[from].name} ↔ ${window.ROOMS[to].name}</p>
            <p><strong>Fano Line:</strong> (${passage.fanoLine.join(', ')})</p>
            <p><strong>Composition:</strong></p>
            <p style="font-family: var(--font-mono); color: var(--mansion-gold);">
                ${passage.colonies[0]} × ${passage.colonies[1]} = ${passage.result}
            </p>
            <p>${passage.description}</p>
            <blockquote>
                Every pair of colonies lies on exactly one line.<br>
                The third colony completes the work.
            </blockquote>
        </div>
    `;
    
    elements.modalBody.innerHTML = html;
    elements.modal.classList.add('active');
}

// ═══════════════════════════════════════════════════════════════
// ENDINGS
// ═══════════════════════════════════════════════════════════════

function initEndings() {
    elements.endingBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const ending = btn.dataset.ending;
            showEnding(ending);
            
            // Update button states
            elements.endingBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
        });
    });
}

function showEnding(endingId) {
    const ending = window.ENDINGS[endingId];
    if (!ending) return;
    
    state.currentEnding = endingId;
    elements.endingContent.innerHTML = ending.content;
    elements.endingContent.classList.add('visible');
    
    // Update document attribute
    document.documentElement.dataset.ending = endingId;
    
    // Log to console
    console.log(`%c🎬 Ending ${endingId}: ${ending.title}`, 'color: #c9a227; font-size: 1.2em;');
    console.log(`%c"${ending.tagline}"`, 'color: #ffb347; font-style: italic;');
}

// ═══════════════════════════════════════════════════════════════
// SECRETS
// ═══════════════════════════════════════════════════════════════

function initSecrets() {
    // Typed sequences
    document.addEventListener('keydown', e => {
        // Konami code
        state.konami.sequence.push(e.keyCode);
        if (state.konami.sequence.length > 10) state.konami.sequence.shift();
        
        if (state.konami.sequence.join(',') === state.konami.target.join(',')) {
            activateKonami();
        }
        
        // Typed words
        if (e.key.length === 1) {
            clearTimeout(state.typed.timeout);
            state.typed.buffer += e.key.toLowerCase();
            if (state.typed.buffer.length > 20) {
                state.typed.buffer = state.typed.buffer.slice(-20);
            }
            state.typed.timeout = setTimeout(() => state.typed.buffer = '', 2000);
            
            checkTypedSecrets();
        }
    });
}

function checkTypedSecrets() {
    const b = state.typed.buffer;
    
    if (b.includes('flames')) {
        activateFlames();
        state.typed.buffer = '';
    }
    
    if (b.includes('wadsworth')) {
        activateWadsworth();
        state.typed.buffer = '';
    }
    
    if (b.includes('passage')) {
        activatePassages();
        state.typed.buffer = '';
    }
    
    if (b.includes('buttle')) {
        console.log('%c🏛️ "I buttle, sir."', 'color: #c9a227; font-size: 1.5em;');
        state.typed.buffer = '';
    }
    
    // Room names
    if (window.ROOMS) {
        Object.keys(window.ROOMS).forEach(roomId => {
            if (b.includes(roomId)) {
                showRoomDetail(roomId);
                state.typed.buffer = '';
            }
        });
    }
}

function activateKonami() {
    document.body.classList.add('rainbow-mode');
    setTimeout(() => document.body.classList.remove('rainbow-mode'), 5000);
    
    console.log('%c🎮 KONAMI CODE ACTIVATED!', 'color: #ff4444; font-size: 2em;');
    console.log('%cAll secrets revealed. Welcome to the full mansion.', 'color: #c9a227;');
    
    recordSecret('konami');
}

function activateFlames() {
    document.body.classList.add('flames-active');
    setTimeout(() => document.body.classList.remove('flames-active'), 4000);
    
    console.log('%c🔥 "Flames... flames on the side of my face..."', 'color: #ff6b4a; font-size: 1.5em;');
    console.log('%c"...breathing... heaving breaths..."', 'color: #ff6b4a; font-style: italic;');
    
    recordSecret('flames');
}

function activateWadsworth() {
    if (!window.CLUE_QUOTES) return;
    const quotes = window.CLUE_QUOTES.wadsworth;
    let index = 0;
    
    const interval = setInterval(() => {
        if (index >= quotes.length) {
            clearInterval(interval);
            return;
        }
        console.log('%c"' + quotes[index] + '"', 'color: #c9a227;');
        index++;
    }, 1500);
    
    recordSecret('wadsworth');
}

function activatePassages() {
    document.body.classList.add('passage-reveal');
    setTimeout(() => document.body.classList.remove('passage-reveal'), 5000);
    
    console.log('%cSecret passages revealed!', 'color: #228b22; font-size: 1.2em;');
    if (window.SECRET_PASSAGES) {
        window.SECRET_PASSAGES.forEach(p => {
            console.log('%c  ' + p.from + ' <-> ' + p.to + ': ' + p.colonies[0] + ' x ' + p.colonies[1] + ' = ' + p.result, 'color: #c9a227;');
        });
    }
    
    recordSecret('passages');
}

function recordSecret(key) {
    if (!state.secretsFound.includes(key)) {
        state.secretsFound.push(key);
        localStorage.setItem('mansion_secrets', JSON.stringify(state.secretsFound));
    }
}

// ═══════════════════════════════════════════════════════════════
// VISIT COUNT
// ═══════════════════════════════════════════════════════════════

function initVisitCount() {
    const ordinal = n => {
        const s = ['th', 'st', 'nd', 'rd'];
        const v = n % 100;
        return n + (s[(v - 20) % 10] || s[v] || s[0]);
    };
    
    elements.visitCount.textContent = state.visits;
    
    if (state.secretsFound.length > 0) {
        elements.visitCount.textContent += ` · ${state.secretsFound.length} secrets found`;
    }
}

// ═══════════════════════════════════════════════════════════════
// CONSOLE API
// ═══════════════════════════════════════════════════════════════

function initConsole() {
    const banner = [
        '%c',
        '╔══════════════════════════════════════════════════════════════════╗',
        '║  THE HOUSE - A Clue-Themed Architectural Mystery                 ║',
        '║  "Ladies and gentlemen, you all have one thing in common..."     ║',
        '╠══════════════════════════════════════════════════════════════════╣',
        '║  For Jill - Product Manager · Clue Connoisseur                   ║',
        '║  This is how Kagami works. Not as documentation-as experience.   ║',
        '╠══════════════════════════════════════════════════════════════════╣',
        '║  SECRETS:                                                        ║',
        '║  - Type "flames" - Mrs. White\'s moment                           ║',
        '║  - Type "wadsworth" - The butler explains                        ║',
        '║  - Type "passage" - Reveal Fano connections                      ║',
        '║  - Konami Code - You know what this does                         ║',
        '║  CONSOLE API: window.mansion                                     ║',
        '╚══════════════════════════════════════════════════════════════════╝'
    ].join('\n');
    console.log(banner, 'color: #c9a227; font-family: monospace;');
    
    window['🏠'] = window.mansion = {
        // Investigation
        investigate: (room) => {
            if (window.ROOMS[room]) {
                showRoomDetail(room);
                return `Investigating ${window.ROOMS[room].name}...`;
            }
            return `Room "${room}" not found. Try: ${Object.keys(window.ROOMS).join(', ')}`;
        },
        
        // Characters
        suspect: (character) => {
            if (window.CHARACTERS[character]) {
                const c = window.CHARACTERS[character];
                console.log(`%c${c.name} (${c.colony})`, `color: ${c.color}; font-weight: bold;`);
                console.log(`%c"${c.quotes[0]}"`, 'font-style: italic;');
                return c;
            }
            return `Character "${character}" not found.`;
        },
        
        suspects: () => {
            Object.values(window.CHARACTERS).forEach(c => {
                console.log(`%c${c.name}%c — ${c.colony} — ${c.room}`, `color: ${c.color}; font-weight: bold;`, '');
            });
        },
        
        // Passages
        passage: (from, to) => {
            const p = window.SECRET_PASSAGES.find(
                sp => (sp.from === from && sp.to === to) || (sp.from === to && sp.to === from)
            );
            if (p) {
                console.log(`%c🔗 Secret Passage: ${from} ↔ ${to}`, 'color: #228b22;');
                console.log(`%c   ${p.colonies[0]} × ${p.colonies[1]} = ${p.result}`, 'color: #c9a227;');
                return p;
            }
            return 'No passage between those rooms.';
        },
        
        passages: () => {
            window.SECRET_PASSAGES.forEach(p => {
                console.log(`%c${p.from} ↔ ${p.to}: ${p.colonies.join(' × ')} = ${p.result}`, 'color: #c9a227;');
            });
        },
        
        // Endings
        ending: (id) => {
            if (window.ENDINGS[id]) {
                showEnding(id);
                return window.ENDINGS[id].tagline;
            }
            return 'Endings: A, B, or C';
        },
        
        // Wadsworth
        wadsworth: () => {
            activateWadsworth();
            return "Let me explain...";
        },
        
        // Flames
        flames: () => {
            activateFlames();
            return "Flames... flames on the side of my face...";
        },
        
        // Stats
        stats: () => ({
            visits: state.visits,
            secretsFound: state.secretsFound.length,
            currentEnding: state.currentEnding,
            rooms: Object.keys(window.ROOMS).length,
            characters: Object.keys(window.CHARACTERS).length,
            passages: window.SECRET_PASSAGES.length
        }),
        
        // Help
        help: () => {
            console.log(`
🏠.investigate(room)  — Examine a room
🏠.suspect(name)      — Interview a suspect  
🏠.suspects()         — List all suspects
🏠.passage(from, to)  — Reveal a secret passage
🏠.passages()         — Show all passages
🏠.ending('A'|'B'|'C') — Show an ending
🏠.wadsworth()        — Let the butler explain
🏠.flames()           — Mrs. White's moment
🏠.stats()            — Investigation stats
            `);
        },
        
        // Easter egg
        buttle: () => {
            console.log('%c🏛️ "I buttle, sir."', 'color: #c9a227; font-size: 1.5em;');
            return "I'm the butler. I buttle.";
        }
    };
}

// ═══════════════════════════════════════════════════════════════
// INIT
// ═══════════════════════════════════════════════════════════════

function initAllSystems() {
    initCursor();
    initCandleCanvas();
    initDustCanvas();
    initScrollReveals();
    initRoomInteractions();
    initFanoInteractions();
    initEndings();
    initSecrets();
    initVisitCount();
    initConsole();
}

// Start
document.addEventListener('DOMContentLoaded', initLoading);

})();
