// ═══════════════════════════════════════════════════════════════════════════
// Spring 2026 Gallery — For Jill
// Navy anchors. Linen breathes. Spring arrives.
//
// Every interaction is intentional. Every transition earns its milliseconds.
// ═══════════════════════════════════════════════════════════════════════════

const HEARTS_KEY = 'jill_spring_hearts';
const HEART_SVG = '<svg viewBox="0 0 24 24"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>';

// Product data built from DOM
const PRODUCTS = {};


document.addEventListener('DOMContentLoaded', () => {

    // ═══════════════════════════════════════════════════════════════
    // Build product data index
    // ═══════════════════════════════════════════════════════════════

    document.querySelectorAll('.product-card').forEach(card => {
        const id = card.querySelector('[data-id]')?.dataset.id
            || card.dataset.category + '-'
            + (card.querySelector('.product-card__title')?.textContent || '')
                .toLowerCase().replace(/\s+/g, '-').slice(0, 30);

        const name = card.querySelector('.product-card__title')?.textContent || '';
        const price = parseInt(
            (card.querySelector('.product-card__price')?.textContent || '0')
                .replace(/[^0-9]/g, ''),
        );
        const maker = card.querySelector('.product-card__maker')?.textContent || '';
        const img = card.querySelector('.product-card__image img');
        const imageSrc = img?.getAttribute('src') || '';

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

    // Init everything
    initScrollProgress();
    initRevealObserver();
    initHearts();
    initFilters();
    initParallax();
    initCardTilt();
});


// ═══════════════════════════════════════════════════════════════════════════
// SCROLL PROGRESS BAR
// ═══════════════════════════════════════════════════════════════════════════

function initScrollProgress() {
    const bar = document.createElement('div');
    bar.className = 'scroll-progress';
    document.body.prepend(bar);

    let ticking = false;
    window.addEventListener('scroll', () => {
        if (ticking) return;
        ticking = true;
        requestAnimationFrame(() => {
            const scrollTop = window.scrollY;
            const docHeight = document.documentElement.scrollHeight - window.innerHeight;
            const progress = docHeight > 0 ? scrollTop / docHeight : 0;
            bar.style.transform = `scaleX(${progress})`;
            ticking = false;
        });
    }, { passive: true });
}


// ═══════════════════════════════════════════════════════════════════════════
// INTERSECTION OBSERVER — Reveal on Scroll
// ═══════════════════════════════════════════════════════════════════════════

function initRevealObserver() {
    const observer = new IntersectionObserver(
        (entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('revealed');
                    // Don't unobserve — keeps the ref, but 'revealed' only fires once
                    observer.unobserve(entry.target);
                }
            });
        },
        { threshold: 0.1, rootMargin: '0px 0px -40px 0px' },
    );

    // Hero elements — staggered
    document.querySelectorAll(
        '.hero-eyebrow, .hero-title, .hero-subtitle, .stat',
    ).forEach(el => observer.observe(el));

    // Philosophy
    const philH2 = document.querySelector('.philosophy h2');
    if (philH2) observer.observe(philH2);
    document.querySelectorAll('.philosophy-item').forEach(el => observer.observe(el));

    // Centerpiece
    const centerpiece = document.querySelector('.centerpiece');
    if (centerpiece) observer.observe(centerpiece);

    // Product cards — stagger via CSS custom property
    let cardIdx = 0;
    document.querySelectorAll('.product-card').forEach(card => {
        card.style.setProperty('--reveal-delay', `${cardIdx * 0.07}s`);
        observer.observe(card);
        cardIdx++;
    });
}


// ═══════════════════════════════════════════════════════════════════════════
// HERO PARALLAX
// ═══════════════════════════════════════════════════════════════════════════

function initParallax() {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    const hero = document.querySelector('.hero');
    if (!hero) return;

    let ticking = false;
    window.addEventListener('scroll', () => {
        if (ticking) return;
        ticking = true;
        requestAnimationFrame(() => {
            const y = window.scrollY;
            if (y < window.innerHeight * 1.2) {
                const ratio = y / window.innerHeight;
                hero.style.transform = `translateY(${y * 0.1}px)`;
                hero.style.opacity = Math.max(0, 1 - ratio * 0.8);
            }
            ticking = false;
        });
    }, { passive: true });
}


// ═══════════════════════════════════════════════════════════════════════════
// CARD TILT — subtle 3D perspective on hover
// ═══════════════════════════════════════════════════════════════════════════

function initCardTilt() {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    if (window.matchMedia('(hover: none)').matches) return; // no tilt on touch

    document.querySelectorAll('.product-card').forEach(card => {
        card.addEventListener('mousemove', e => {
            const rect = card.getBoundingClientRect();
            const x = (e.clientX - rect.left) / rect.width - 0.5;
            const y = (e.clientY - rect.top) / rect.height - 0.5;
            card.style.transform =
                `translateY(-4px) perspective(800px) rotateX(${-y * 3}deg) rotateY(${x * 3}deg)`;
        });

        card.addEventListener('mouseleave', () => {
            card.style.transform = '';
            card.style.transition = 'transform 0.4s cubic-bezier(0.22, 1, 0.36, 1), box-shadow 0.4s cubic-bezier(0.22, 1, 0.36, 1), border-color 0.23s cubic-bezier(0.22, 1, 0.36, 1)';
            setTimeout(() => { card.style.transition = ''; }, 400);
        });
    });
}


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
    const adding = idx === -1;

    if (adding) hearts.push(id);
    else hearts.splice(idx, 1);

    saveHearts(hearts);
    updateAllHeartStates(adding ? id : null);
    updateNavCount();
    updatePanel();

    return adding;
}

function updateAllHeartStates(justHeartedId) {
    document.querySelectorAll('.product-heart').forEach(btn => {
        const id = btn.dataset.productId;
        const hearted = isHearted(id);
        btn.classList.toggle('hearted', hearted);

        // Pop animation for newly hearted
        if (id === justHeartedId && hearted) {
            btn.classList.add('just-hearted');
            setTimeout(() => btn.classList.remove('just-hearted'), 700);
        }
    });
}

function updateNavCount() {
    const el = document.querySelector('.nav-hearts-count');
    if (!el) return;
    const count = getHearts().length;

    // Bounce animation
    el.style.transform = 'scale(1.4)';
    setTimeout(() => {
        el.textContent = count;
        el.style.transform = 'scale(1)';
    }, 80);
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

        imageEl.appendChild(btn);
    });

    // Nav counter (fixed top-right)
    const counter = document.createElement('div');
    counter.className = 'nav-hearts';
    counter.setAttribute('role', 'button');
    counter.setAttribute('aria-label', 'Open favorites');
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
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-label', 'Your favorites');
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

    // Escape key closes panel
    document.addEventListener('keydown', e => {
        if (e.key === 'Escape') {
            const panel = document.querySelector('.hearted-panel');
            if (panel?.classList.contains('open')) togglePanel();
        }
    });

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
    hearts.forEach((id, i) => {
        const p = PRODUCTS[id];
        if (!p) return;
        total += p.price;
        html += `
            <div class="hearted-item" data-product-id="${id}" style="animation-delay: ${i * 40}ms">
                <img src="${p.image}" alt="${p.name}" class="hearted-item-image"
                     onerror="this.style.background='var(--paper-shadow)';this.src=''">
                <div class="hearted-item-info">
                    <div class="hearted-item-name">${p.name}</div>
                    <div class="hearted-item-price">$${p.price.toLocaleString()}</div>
                </div>
                <button class="hearted-item-remove" aria-label="Remove ${p.name}">×</button>
            </div>
        `;
    });

    content.innerHTML = html;

    // Wire up remove buttons with slide-out animation
    content.querySelectorAll('.hearted-item-remove').forEach(btn => {
        btn.addEventListener('click', e => {
            e.stopPropagation();
            const item = btn.closest('.hearted-item');
            item.style.transform = 'translateX(100%)';
            item.style.opacity = '0';
            item.style.transition = 'all 0.3s cubic-bezier(0.22, 1, 0.36, 1)';
            setTimeout(() => toggleHeart(item.dataset.productId), 280);
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
    if (start === target) { el.textContent = '$' + target.toLocaleString(); return; }

    const startTime = performance.now();
    const duration = 350;

    function tick(now) {
        const t = Math.min((now - startTime) / duration, 1);
        // Ease-out cubic
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

            // Update active state
            buttons.forEach(b => {
                b.classList.remove('active');
                b.setAttribute('aria-selected', 'false');
            });
            button.classList.add('active');
            button.setAttribute('aria-selected', 'true');

            // Filter with staggered re-reveal
            let visibleIdx = 0;
            cards.forEach(card => {
                const cat = card.dataset.category;
                const show = filter === 'all' || cat === filter;

                if (show) {
                    card.removeAttribute('data-hidden');
                    card.style.setProperty('--reveal-delay', `${visibleIdx * 0.05}s`);

                    // Re-trigger reveal animation
                    card.classList.remove('revealed');
                    card.style.opacity = '0';
                    card.style.transform = 'translateY(16px)';

                    // Force reflow then re-reveal
                    requestAnimationFrame(() => {
                        requestAnimationFrame(() => {
                            card.classList.add('revealed');
                        });
                    });

                    visibleIdx++;
                } else {
                    card.setAttribute('data-hidden', 'true');
                }
            });
        });
    });
}
