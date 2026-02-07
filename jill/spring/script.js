// ═══════════════════════════════════════════════════════════════════════════
// Spring 2026 Gallery — For Jill
// Navy anchors. Linen breathes. Spring arrives.
// ═══════════════════════════════════════════════════════════════════════════

const HEARTS_KEY = 'jill_spring_hearts';
const HEART_SVG = '<svg viewBox="0 0 24 24"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>';

// Product data for the hearted panel
const PRODUCTS = {};

document.addEventListener('DOMContentLoaded', () => {

    // ═══════════════════════════════════════════════════════════════
    // Build product data from DOM
    // ═══════════════════════════════════════════════════════════════
    document.querySelectorAll('.product-card').forEach(card => {
        const id = card.querySelector('[data-id]')?.dataset.id
            || card.dataset.category + '-' + (card.querySelector('.product-card__title')?.textContent || '').toLowerCase().replace(/\s+/g, '-').slice(0, 30);

        const name = card.querySelector('.product-card__title')?.textContent || '';
        const price = parseInt((card.querySelector('.product-card__price')?.textContent || '0').replace(/[^0-9]/g, ''));
        const maker = card.querySelector('.product-card__maker')?.textContent || '';
        const img = card.querySelector('.product-card__image img');
        const imageSrc = img?.getAttribute('src') || '';

        // Store an ID on the card
        card.dataset.productId = id;

        PRODUCTS[id] = { name, price, maker, image: imageSrc };
    });

    // Also index the centerpiece
    const cp = document.querySelector('.centerpiece');
    if (cp) {
        const name = cp.querySelector('.centerpiece__title')?.textContent || '';
        const img = cp.querySelector('.centerpiece__image img')?.getAttribute('src') || '';
        PRODUCTS['centerpiece'] = { name, price: 650, maker: 'Lotuff Leather', image: img };
    }

    initHearts();
    initFilters();
    initScrollEffects();
});


// ═══════════════════════════════════════════════════════════════════════════
// HEARTS SYSTEM
// ═══════════════════════════════════════════════════════════════════════════

function getHearts() {
    try { return JSON.parse(localStorage.getItem(HEARTS_KEY)) || []; }
    catch { return []; }
}

function saveHearts(hearts) {
    localStorage.setItem(HEARTS_KEY, JSON.stringify(hearts));
}

function isHearted(id) { return getHearts().includes(id); }

function toggleHeart(id) {
    const hearts = getHearts();
    const idx = hearts.indexOf(id);
    if (idx === -1) hearts.push(id);
    else hearts.splice(idx, 1);
    saveHearts(hearts);
    updateAllHeartStates();
    updateNavCount();
    updatePanel();
    return idx === -1; // returns true if newly hearted
}

function updateAllHeartStates() {
    document.querySelectorAll('.product-heart').forEach(btn => {
        btn.classList.toggle('hearted', isHearted(btn.dataset.productId));
    });
}

function updateNavCount() {
    const el = document.querySelector('.nav-hearts-count');
    if (!el) return;
    const count = getHearts().length;
    el.textContent = count;
    el.style.transform = 'scale(1.3)';
    setTimeout(() => { el.style.transform = 'scale(1)'; }, 150);
}

function initHearts() {
    // Add heart buttons to product cards
    document.querySelectorAll('.product-card').forEach(card => {
        const imageEl = card.querySelector('.product-card__image');
        if (!imageEl) return;

        const id = card.dataset.productId;
        const btn = document.createElement('button');
        btn.className = 'product-heart' + (isHearted(id) ? ' hearted' : '');
        btn.dataset.productId = id;
        btn.setAttribute('aria-label', 'Add to favorites');
        btn.innerHTML = HEART_SVG;

        btn.addEventListener('click', e => {
            e.preventDefault();
            e.stopPropagation();
            toggleHeart(id);
        });

        imageEl.style.position = 'relative';
        imageEl.appendChild(btn);
    });

    // Nav counter
    const counter = document.createElement('div');
    counter.className = 'nav-hearts';
    counter.innerHTML = `${HEART_SVG}<span class="nav-hearts-count">${getHearts().length}</span>`;
    counter.addEventListener('click', togglePanel);
    document.body.appendChild(counter);

    // Panel overlay
    const overlay = document.createElement('div');
    overlay.className = 'panel-overlay';
    overlay.addEventListener('click', togglePanel);
    document.body.appendChild(overlay);

    // Panel
    const panel = document.createElement('div');
    panel.className = 'hearted-panel';
    panel.innerHTML = `
        <div class="hearted-panel-header">
            <div class="hearted-panel-title">${HEART_SVG} Your Favorites</div>
            <button class="hearted-panel-close" aria-label="Close">×</button>
        </div>
        <div class="hearted-panel-content"></div>
        <div class="hearted-panel-footer">
            <div class="hearted-total">
                <span class="hearted-total-label">Total</span>
                <span class="hearted-total-value">$0</span>
            </div>
        </div>
    `;
    panel.querySelector('.hearted-panel-close').addEventListener('click', togglePanel);
    document.body.appendChild(panel);

    updatePanel();
}

function togglePanel() {
    const panel = document.querySelector('.hearted-panel');
    const overlay = document.querySelector('.panel-overlay');
    if (!panel) return;
    const open = panel.classList.toggle('open');
    overlay?.classList.toggle('visible', open);
    document.body.style.overflow = open ? 'hidden' : '';
    if (open) updatePanel();
}

function updatePanel() {
    const content = document.querySelector('.hearted-panel-content');
    const footer = document.querySelector('.hearted-panel-footer');
    if (!content) return;

    const hearts = getHearts();

    if (hearts.length === 0) {
        content.innerHTML = `
            <div class="hearted-empty">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
                </svg>
                <p>Tap the heart on any piece to save it here.</p>
            </div>
        `;
        if (footer) footer.style.display = 'none';
        return;
    }

    let total = 0;
    let html = '';
    hearts.forEach(id => {
        const p = PRODUCTS[id];
        if (!p) return;
        total += p.price;
        html += `
            <div class="hearted-item" data-product-id="${id}">
                <img src="${p.image}" alt="${p.name}" class="hearted-item-image"
                     onerror="this.style.background='var(--paper-shadow)';this.src=''">
                <div class="hearted-item-info">
                    <div class="hearted-item-name">${p.name}</div>
                    <div class="hearted-item-price">$${p.price.toLocaleString()}</div>
                </div>
                <button class="hearted-item-remove" aria-label="Remove">×</button>
            </div>
        `;
    });

    content.innerHTML = html;

    content.querySelectorAll('.hearted-item-remove').forEach(btn => {
        btn.addEventListener('click', e => {
            e.stopPropagation();
            const item = btn.closest('.hearted-item');
            item.style.transform = 'translateX(100%)';
            item.style.opacity = '0';
            setTimeout(() => toggleHeart(item.dataset.productId), 200);
        });
    });

    if (footer) {
        footer.style.display = '';
        const totalEl = footer.querySelector('.hearted-total-value');
        if (totalEl) animateNumber(totalEl, total);
    }
}

function animateNumber(el, target) {
    const start = parseInt(el.textContent.replace(/[^0-9]/g, '')) || 0;
    const startTime = performance.now();
    const duration = 400;
    function tick(now) {
        const t = Math.min((now - startTime) / duration, 1);
        const eased = 1 - Math.pow(1 - t, 3);
        el.textContent = '$' + Math.round(start + (target - start) * eased).toLocaleString();
        if (t < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
}


// ═══════════════════════════════════════════════════════════════════════════
// CATEGORY FILTERING
// ═══════════════════════════════════════════════════════════════════════════

function initFilters() {
    const buttons = document.querySelectorAll('.filter-pill');
    const cards = document.querySelectorAll('.product-card');

    buttons.forEach(button => {
        button.addEventListener('click', () => {
            const filter = button.dataset.filter;

            buttons.forEach(b => {
                b.classList.remove('active');
                b.setAttribute('aria-selected', 'false');
            });
            button.classList.add('active');
            button.setAttribute('aria-selected', 'true');

            let idx = 0;
            cards.forEach(card => {
                const cat = card.dataset.category;
                const show = filter === 'all' || cat === filter;
                if (show) {
                    card.removeAttribute('data-hidden');
                    card.style.setProperty('--reveal-delay', `${idx * 0.06}s`);
                    card.style.animation = 'none';
                    card.offsetHeight;
                    card.style.animation = '';
                    idx++;
                } else {
                    card.setAttribute('data-hidden', 'true');
                }
            });
        });
    });
}


// ═══════════════════════════════════════════════════════════════════════════
// SCROLL EFFECTS
// ═══════════════════════════════════════════════════════════════════════════

function initScrollEffects() {
    // Intersection observer for reveals
    const observer = new IntersectionObserver(entries => {
        entries.forEach(entry => {
            if (entry.isIntersecting) entry.target.classList.add('revealed');
        });
    }, { threshold: 0.08, rootMargin: '40px' });

    document.querySelectorAll('.product-card, .centerpiece, .philosophy-item').forEach(
        el => observer.observe(el)
    );

    // Subtle hero parallax
    const hero = document.querySelector('.hero');
    if (hero && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        let ticking = false;
        window.addEventListener('scroll', () => {
            if (!ticking) {
                requestAnimationFrame(() => {
                    const y = window.scrollY;
                    if (y < window.innerHeight) {
                        hero.style.transform = `translateY(${y * 0.12}px)`;
                        hero.style.opacity = Math.max(0, 1 - (y / (window.innerHeight * 1.1)));
                    }
                    ticking = false;
                });
                ticking = true;
            }
        }, { passive: true });
    }
}
