/**
 * The Gentleman Scientist — Tim
 * Data-driven gallery, phase filtering, outfit builder, hearts
 *
 * h(x) >= 0 always
 */

(function() {
    'use strict';

    // ═══════════════════════════════════════════════════════════════
    // OUTFIT FORMULAS
    // ═══════════════════════════════════════════════════════════════

    const outfitFormulas = {
        'morning-study': {
            name: 'Morning Study',
            vibe: 'Reading proofs at dawn',
            items: [
                { id: 'william-lockie-cardigan', category: 'Cardigan' },
                { id: 'kamakura-oxford-white', category: 'Shirt' },
                { id: 'stan-ray-moleskin-tobacco', category: 'Trousers' },
                { id: 'derek-rose-dressing-gown', category: 'Robe', fallback: { name: 'Derek Rose Gown', price: 400, image: '' } }
            ]
        },
        'lecture-day': {
            name: 'Lecture Day',
            vibe: 'Scholarly but not stuffy',
            items: [
                { id: 'drakes-navy-hopsack', category: 'Sport Coat' },
                { id: 'kamakura-oxford-blue', category: 'Shirt' },
                { id: 'drakes-cavalry-twill', category: 'Trousers', fallback: { name: "Drake's Cavalry Twill", price: 350, image: '' } },
                { id: 'alden-penny-loafer', category: 'Shoes', fallback: { name: 'Alden Loafer', price: 700, image: '' } }
            ]
        },
        'weekend-scholar': {
            name: 'Weekend Scholar',
            vibe: 'Bookshop to dinner',
            items: [
                { id: 'howlin-shetland-heather', category: 'Sweater', fallback: { name: "Howlin' Shetland", price: 195, image: '' } },
                { id: 'orslow-corduroy', category: 'Trousers', fallback: { name: 'orSlow Cord', price: 275, image: '' } },
                { id: 'paraboot-michael', category: 'Shoes', fallback: { name: 'Paraboot Michael', price: 475, image: '' } },
                { id: 'begg-scarf', category: 'Scarf', fallback: { name: 'Begg & Co Scarf', price: 275, image: '' } }
            ]
        },
        'pattern-don': {
            name: 'Pattern Don',
            vibe: "I know what I'm doing",
            items: [
                { id: 'ring-jacket-tweed', category: 'Sport Coat', fallback: { name: 'Ring Jacket Tweed', price: 1050, image: '' } },
                { id: 'gitman-liberty', category: 'Shirt', fallback: { name: 'Gitman Liberty', price: 225, image: '' } },
                { id: 'stan-ray-moleskin-olive', category: 'Trousers' },
                { id: 'yuketen-camp-moc', category: 'Shoes', fallback: { name: 'Yuketen Moc', price: 325, image: '' } }
            ]
        }
    };

    // ═══════════════════════════════════════════════════════════════
    // CATEGORY METADATA
    // ═══════════════════════════════════════════════════════════════

    const categoryMeta = {
        tailoring: { eyebrow: "The Scholar's Armor", subtitle: 'Soft shoulder, unstructured, textured cloth', alt: true },
        shirting: { eyebrow: 'The Foundation', subtitle: 'Oxford cloth, linen, brushed cotton', alt: false },
        knitwear: { eyebrow: "The Scholar's Signature", subtitle: 'Where the transformation lives', alt: true },
        trousers: { eyebrow: 'The Upgrade', subtitle: 'Moleskin, corduroy, cavalry twill', alt: false },
        footwear: { eyebrow: 'The Foundation', subtitle: 'Leather for daily, boots for weather', alt: true },
        leisure: { eyebrow: 'At Home, Still Dressed', subtitle: 'A gentleman at home is still a gentleman', alt: false },
        accessories: { eyebrow: 'The Details That Signal', subtitle: 'A gentleman is identified by his accessories', alt: true }
    };

    // ═══════════════════════════════════════════════════════════════
    // STATE
    // ═══════════════════════════════════════════════════════════════

    let galleryData = null;
    let productMap = {};
    let hearted = JSON.parse(localStorage.getItem('gs-hearted') || '[]');
    let currentPhase = 'all';
    let currentOutfit = 'morning-study';

    // ═══════════════════════════════════════════════════════════════
    // INIT
    // ═══════════════════════════════════════════════════════════════

    async function init() {
        try {
            const res = await fetch('data/gallery.json');
            galleryData = await res.json();

            // Build product lookup map
            galleryData.products.forEach(p => { productMap[p.id] = p; });

            renderNav();
            renderHeroStats();
            renderCollections();
            renderBudget();
            initPhaseFilter();
            initOutfitBuilder();
            initHearts();
            initScrollReveal();
            initSmoothScroll();
            initProductCards();
        } catch (e) {
            console.error('Failed to load gallery data:', e);
            document.getElementById('collections-container').innerHTML =
                '<p style="text-align:center;padding:4rem;color:#888;">Loading gallery data...</p>';
        }
    }

    // ═══════════════════════════════════════════════════════════════
    // RENDER NAVIGATION
    // ═══════════════════════════════════════════════════════════════

    function renderNav() {
        const navLinks = document.getElementById('nav-links');
        const cats = galleryData.categories || Object.keys(categoryMeta);
        navLinks.innerHTML = cats.map(cat =>
            `<a href="#${cat}">${cat.charAt(0).toUpperCase() + cat.slice(1)}</a>`
        ).join('');
    }

    // ═══════════════════════════════════════════════════════════════
    // RENDER HERO STATS
    // ═══════════════════════════════════════════════════════════════

    function renderHeroStats() {
        const stats = document.getElementById('hero-stats');
        const products = galleryData.products;
        const countries = new Set(products.map(p => p.origin).filter(Boolean));
        const brands = new Set(products.map(p => p.brand));

        stats.innerHTML = `
            <div class="stat">
                <span class="stat-value">${products.length}</span>
                <span class="stat-label">Curated Pieces</span>
            </div>
            <div class="stat">
                <span class="stat-value">${countries.size}</span>
                <span class="stat-label">Countries</span>
            </div>
            <div class="stat">
                <span class="stat-value">${brands.size}</span>
                <span class="stat-label">Makers</span>
            </div>
            <div class="stat">
                <span class="stat-value">4</span>
                <span class="stat-label">Phases</span>
            </div>
        `;
    }

    // ═══════════════════════════════════════════════════════════════
    // RENDER COLLECTIONS
    // ═══════════════════════════════════════════════════════════════

    function renderCollections() {
        const container = document.getElementById('collections-container');
        const cats = galleryData.categories || Object.keys(categoryMeta);

        container.innerHTML = cats.map(cat => {
            const meta = categoryMeta[cat] || { eyebrow: cat, subtitle: '', alt: false };
            const products = galleryData.products.filter(p => p.category === cat);
            if (!products.length) return '';

            const altClass = meta.alt ? ' collection-alt' : '';

            return `
                <section id="${cat}" class="collection${altClass}">
                    <header class="collection-header">
                        <span class="collection-eyebrow">${meta.eyebrow}</span>
                        <h2 class="collection-title">${cat.charAt(0).toUpperCase() + cat.slice(1)}</h2>
                        <p class="collection-subtitle">${meta.subtitle}</p>
                    </header>
                    <div class="product-grid">
                        ${products.map(p => renderProductCard(p)).join('')}
                    </div>
                </section>
            `;
        }).join('');
    }

    function renderProductCard(p) {
        const isHearted = hearted.includes(p.id);
        // Try jpg first, fall back to svg placeholder
        const imgBase = p.local_image ? p.local_image.replace('.jpg', '') : '';
        const imgSrc = imgBase ? `images/${imgBase}.jpg` : (p.image_url || '');
        const badgeClass = getBadgeClass(p);
        const phaseClass = p.phase ? `product-phase--${p.phase}` : '';

        return `
            <article class="product-card${p.is_centerpiece ? ' product-card--featured' : ''}"
                     data-href="${p.product_url || '#'}"
                     data-id="${p.id}"
                     data-phase="${p.phase || 'all'}">

                <div class="product-image-container">
                    <button class="product-heart${isHearted ? ' hearted' : ''}" data-id="${p.id}" aria-label="Heart ${p.name}">
                        <svg viewBox="0 0 24 24"><path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/></svg>
                    </button>
                    ${p.phase ? `<span class="product-phase ${phaseClass}">Phase ${p.phase}</span>` : ''}
                    <img src="${imgSrc}" alt="${p.brand} ${p.name}" class="product-image" loading="lazy"
                         onerror="this.onerror=null; var svg='images/${imgBase}.svg'; if(this.src.indexOf('.svg')===-1){this.src=svg}else{this.style.display='none';this.parentElement.insertAdjacentHTML('beforeend','<div class=\\'image-placeholder\\'>${p.brand}</div>')}">
                    ${p.badge ? `<span class="product-badge ${badgeClass}">${p.badge}</span>` : ''}
                </div>

                <div class="product-info">
                    <span class="product-brand">${p.brand}</span>
                    <h3 class="product-name">${p.name}</h3>
                    ${p.description ? `<p class="product-description">${p.description}</p>` : ''}
                    <p class="product-details">${p.maker || ''} ${p.material ? '· ' + p.material : ''}</p>
                    <div class="product-meta">
                        <span class="product-price">${p.price_display || ('$' + p.price)}</span>
                        <a href="${p.product_url || '#'}" target="_blank" rel="noopener" class="product-cta">View piece</a>
                    </div>
                </div>
            </article>
        `;
    }

    function getBadgeClass(p) {
        if (!p.badge) return '';
        const b = p.badge.toLowerCase();
        if (b.includes('japan') || b.includes('kojima')) return 'product-badge--japanese';
        if (b.includes('scottish') || b.includes('shetland') || b.includes('scotland')) return 'product-badge--scottish';
        if (b.includes('heritage') || b.includes('french')) return 'product-badge--heritage';
        if (b.includes('artisan') || b.includes('handmade') || b.includes('hand')) return 'product-badge--artisan';
        if (p.is_centerpiece) return 'product-badge--centerpiece';
        return '';
    }

    // ═══════════════════════════════════════════════════════════════
    // PHASE FILTER
    // ═══════════════════════════════════════════════════════════════

    function initPhaseFilter() {
        const buttons = document.querySelectorAll('.phase-btn');
        buttons.forEach(btn => {
            btn.addEventListener('click', () => {
                const phase = btn.dataset.phase;
                currentPhase = phase;

                buttons.forEach(b => {
                    b.classList.remove('active');
                    b.setAttribute('aria-pressed', 'false');
                });
                btn.classList.add('active');
                btn.setAttribute('aria-pressed', 'true');

                filterByPhase(phase);
            });
        });
    }

    function filterByPhase(phase) {
        const cards = document.querySelectorAll('.product-card');
        cards.forEach(card => {
            const cardPhase = card.dataset.phase;
            if (phase === 'all' || cardPhase === phase) {
                card.classList.remove('hidden-by-phase');
                card.style.opacity = '1';
                card.style.transform = 'translateY(0)';
            } else {
                card.classList.add('hidden-by-phase');
            }
        });

        // Update hero stats for filtered view
        if (phase === 'all') {
            renderHeroStats();
        } else {
            const filtered = galleryData.products.filter(p => String(p.phase) === phase);
            const total = filtered.reduce((sum, p) => sum + (p.price || 0), 0);
            const statsEl = document.getElementById('hero-stats');
            statsEl.innerHTML = `
                <div class="stat">
                    <span class="stat-value">${filtered.length}</span>
                    <span class="stat-label">Phase ${phase} Pieces</span>
                </div>
                <div class="stat">
                    <span class="stat-value">$${total.toLocaleString()}</span>
                    <span class="stat-label">Estimated Total</span>
                </div>
            `;
        }
    }

    // ═══════════════════════════════════════════════════════════════
    // OUTFIT BUILDER
    // ═══════════════════════════════════════════════════════════════

    function initOutfitBuilder() {
        const presets = document.querySelectorAll('.outfit-preset');
        presets.forEach(preset => {
            preset.addEventListener('click', () => {
                const key = preset.dataset.outfit;
                if (key === currentOutfit) return;

                presets.forEach(p => {
                    p.classList.remove('active');
                    p.setAttribute('aria-pressed', 'false');
                });
                preset.classList.add('active');
                preset.setAttribute('aria-pressed', 'true');

                const container = document.getElementById('outfit-items');
                container.style.opacity = '0';
                container.style.transform = 'translateY(10px)';

                setTimeout(() => {
                    currentOutfit = key;
                    renderOutfit(key);
                    requestAnimationFrame(() => {
                        container.style.opacity = '1';
                        container.style.transform = 'translateY(0)';
                    });
                }, 233);
            });
        });

        renderOutfit(currentOutfit);
    }

    function renderOutfit(key) {
        const formula = outfitFormulas[key];
        const container = document.getElementById('outfit-items');
        const totalEl = document.getElementById('outfit-total-price');
        if (!formula || !container) return;

        container.innerHTML = '';
        let total = 0;

        const categoryIcons = {
            'Sport Coat': '🧥', 'Cardigan': '🧶', 'Sweater': '🧶', 'Shirt': '👔',
            'Trousers': '👖', 'Shoes': '👞', 'Scarf': '🧣', 'Robe': '🥋',
            'Accessory': '✨'
        };

        formula.items.forEach((item, index) => {
            const product = productMap[item.id] || item.fallback || { name: item.id, price: 0, image: '' };
            const price = product.price || 0;
            total += price;

            const imgSrc = product.local_image ? `images/${product.local_image}` : (product.image_url || '');

            const el = document.createElement('div');
            el.className = 'outfit-item';
            el.style.opacity = '0';
            el.style.transform = 'translateY(20px) scale(0.95)';
            el.style.transition = `all 377ms cubic-bezier(0.22, 1, 0.36, 1) ${index * 89}ms`;

            el.innerHTML = `
                <div class="outfit-item-image-wrap">
                    ${imgSrc ? `<img src="${imgSrc}" alt="${product.name || item.id}" class="outfit-item-image" loading="lazy">` : ''}
                    <span class="outfit-item-category">${categoryIcons[item.category] || '👔'}</span>
                </div>
                <div class="outfit-item-details">
                    <div class="outfit-item-name">${product.name || item.id}</div>
                    <div class="outfit-item-price">$${price.toLocaleString()}</div>
                </div>
            `;

            el.addEventListener('mouseenter', () => { el.style.transform = 'translateY(-8px) scale(1.02)'; });
            el.addEventListener('mouseleave', () => { el.style.transform = 'translateY(0) scale(1)'; });

            container.appendChild(el);

            requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                    el.style.opacity = '1';
                    el.style.transform = 'translateY(0) scale(1)';
                });
            });
        });

        animateNumber(totalEl, total);
    }

    function animateNumber(el, target) {
        const current = parseInt(el.textContent.replace(/[^0-9]/g, '')) || 0;
        const diff = target - current;
        const steps = 20;
        const increment = diff / steps;
        let step = 0;

        function update() {
            step++;
            el.textContent = '$' + Math.round(current + increment * step).toLocaleString();
            if (step < steps) requestAnimationFrame(update);
            else el.textContent = '$' + target.toLocaleString();
        }
        requestAnimationFrame(update);
    }

    // ═══════════════════════════════════════════════════════════════
    // HEARTS
    // ═══════════════════════════════════════════════════════════════

    function initHearts() {
        updateHeartCount();

        document.addEventListener('click', (e) => {
            const btn = e.target.closest('.product-heart');
            if (!btn) return;
            e.stopPropagation();

            const id = btn.dataset.id;
            if (hearted.includes(id)) {
                hearted = hearted.filter(h => h !== id);
                btn.classList.remove('hearted');
            } else {
                hearted.push(id);
                btn.classList.add('hearted');
                btn.style.transform = 'scale(1.3)';
                setTimeout(() => { btn.style.transform = 'scale(1)'; }, 233);
            }

            localStorage.setItem('gs-hearted', JSON.stringify(hearted));
            updateHeartCount();
        });
    }

    function updateHeartCount() {
        const countEl = document.querySelector('.nav-hearts-count');
        if (countEl) countEl.textContent = hearted.length;
    }

    // ═══════════════════════════════════════════════════════════════
    // BUDGET
    // ═══════════════════════════════════════════════════════════════

    function renderBudget() {
        const grid = document.getElementById('budget-grid');
        const phases = [
            { num: 1, label: 'Foundation', time: 'Month 1' },
            { num: 2, label: 'Expansion', time: 'Months 2-3' },
            { num: 3, label: 'Signature', time: 'Months 4-6' },
            { num: 4, label: 'Refinement', time: 'Ongoing' }
        ];

        grid.innerHTML = phases.map(phase => {
            const items = galleryData.products.filter(p => p.phase === phase.num);
            const total = items.reduce((sum, p) => sum + (p.price || 0), 0);

            return `
                <div class="budget-phase">
                    <span class="budget-phase-label">Phase ${phase.num}</span>
                    <span class="budget-phase-time">${phase.time}</span>
                    <span class="budget-phase-amount">$${total.toLocaleString()}</span>
                    <span class="budget-phase-items">${items.length} pieces</span>
                </div>
            `;
        }).join('');
    }

    // ═══════════════════════════════════════════════════════════════
    // PRODUCT CARD NAVIGATION
    // ═══════════════════════════════════════════════════════════════

    function initProductCards() {
        document.addEventListener('click', (e) => {
            if (e.target.closest('.product-heart') || e.target.closest('.product-cta')) return;
            const card = e.target.closest('.product-card[data-href]');
            if (card) window.open(card.dataset.href, '_blank', 'noopener');
        });
    }

    // ═══════════════════════════════════════════════════════════════
    // SMOOTH SCROLL
    // ═══════════════════════════════════════════════════════════════

    function initSmoothScroll() {
        document.addEventListener('click', (e) => {
            const link = e.target.closest('.nav-links a');
            if (!link) return;
            const href = link.getAttribute('href');
            if (href && href.startsWith('#')) {
                e.preventDefault();
                const target = document.querySelector(href);
                if (target) {
                    const top = target.getBoundingClientRect().top + window.scrollY - 100;
                    window.scrollTo({ top, behavior: 'smooth' });
                }
            }
        });
    }

    // ═══════════════════════════════════════════════════════════════
    // SCROLL REVEAL
    // ═══════════════════════════════════════════════════════════════

    function initScrollReveal() {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('revealed');
                    observer.unobserve(entry.target);
                }
            });
        }, { rootMargin: '0px 0px -10% 0px', threshold: 0.1 });

        document.querySelectorAll('.collection-header').forEach(el => {
            el.classList.add('reveal-on-scroll');
            observer.observe(el);
        });

        document.querySelectorAll('.product-card').forEach((el, i) => {
            el.classList.add('reveal-on-scroll');
            el.style.transitionDelay = `${(i % 3) * 89}ms`;
            observer.observe(el);
        });

        document.querySelectorAll('.philosophy-item').forEach((el, i) => {
            el.classList.add('reveal-on-scroll');
            el.style.transitionDelay = `${i * 89}ms`;
            observer.observe(el);
        });
    }

    // ═══════════════════════════════════════════════════════════════
    // LAUNCH
    // ═══════════════════════════════════════════════════════════════

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
