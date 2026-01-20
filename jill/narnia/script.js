/**
 * ═══════════════════════════════════════════════════════════════════════════
 * THE EVENING EDIT — For Jill
 * ═══════════════════════════════════════════════════════════════════════════
 *
 * Every interaction is intentional.
 * Every animation tells a story.
 * Hearts sync across galleries because love persists.
 *
 * — Kagami, January 2026
 */

(function() {
    'use strict';

    // Boot marker (debug + sanity check)
    window.__evening_edit_boot = Date.now();

    // ═══════════════════════════════════════════════════════════════════════
    // HEARTS PERSISTENCE — Synced across galleries
    // ═══════════════════════════════════════════════════════════════════════

    const HEARTS_KEYS = {
        evening: 'jill_evening_hearts',
        wardrobe: 'jill_wardrobe_hearts',
        history: 'jill_hearts_history'
    };

    // Shared state across Jill galleries
    const ORDER_STATE_KEY = 'jill_order_state_v1';
    // Values: 'wishlisted' | 'considering' | 'ordered' | 'purchased' | 'owned' | 'returned'

    function loadOrderState() {
        try {
            return JSON.parse(localStorage.getItem(ORDER_STATE_KEY) || '{}');
        } catch {
            return {};
        }
    }

    function saveOrderState(state) {
        try {
            localStorage.setItem(ORDER_STATE_KEY, JSON.stringify(state));
        } catch (e) {
            console.warn('Could not save order state:', e);
        }
    }

    function getItemStatus(productId) {
        const state = loadOrderState();
        return state[productId]?.status || null;
    }

    function setItemStatus(productId, status) {
        const state = loadOrderState();
        state[productId] = {
            status,
            updated_at: Date.now(),
        };
        saveOrderState(state);
    }

    const LAST_ACTION_KEY = 'jill_last_order_action_v1';

    function setLastAction(action) {
        try {
            localStorage.setItem(LAST_ACTION_KEY, JSON.stringify({ ...action, at: Date.now() }));
        } catch {}
    }

    function getLastAction() {
        try {
            return JSON.parse(localStorage.getItem(LAST_ACTION_KEY) || 'null');
        } catch {
            return null;
        }
    }


    // Badges: persist unseen counts; clear on drawer open
    const BADGE_KEY = 'jill_badges_v1';

    function loadBadges() {
        try { return JSON.parse(localStorage.getItem(BADGE_KEY) || '{"favorites":0,"orders":0}'); }
        catch { return { favorites: 0, orders: 0 }; }
    }

    function saveBadges(b) {
        try { localStorage.setItem(BADGE_KEY, JSON.stringify(b)); } catch {}
    }

    function bumpBadge(kind, by = 1) {
        const b = loadBadges();
        b[kind] = Math.max(0, (b[kind] || 0) + by);
        saveBadges(b);
        renderBadges();
    }

    function clearBadge(kind) {
        const b = loadBadges();
        b[kind] = 0;
        saveBadges(b);
        renderBadges();
    }

    function renderBadges() {
        const b = loadBadges();
        document.querySelectorAll('.nav-action__badge').forEach(el => {
            const kind = el.dataset.badge;
            const val = Number(b[kind] || 0);
            el.textContent = val > 9 ? '9+' : String(val);
            el.classList.toggle('is-visible', val > 0);
        });
    }

    // Drawers
    function openDrawer(kind) {
        const overlay = document.querySelector('.drawer-overlay');
        const drawer = document.getElementById(`drawer-${kind}`);
        if (!overlay || !drawer) return;

        overlay.hidden = false;
        drawer.classList.add('is-open');
        drawer.setAttribute('aria-hidden','false');
        document.body.style.overflow = 'hidden';

        if (kind === 'favorites') renderFavoritesDrawer();
        if (kind === 'orders') renderOrdersDrawer();

        // Always clear badges in localStorage when opened
        clearBadge(kind);
    }

    function closeDrawers() {
        const overlay = document.querySelector('.drawer-overlay');
        document.querySelectorAll('.drawer.is-open').forEach(d => {
            d.classList.remove('is-open');
            d.setAttribute('aria-hidden','true');
        });
        if (overlay) overlay.hidden = true;
        document.body.style.overflow = '';
    }



    // Product ID mappings between galleries (same product, different IDs)
    const PRODUCT_MAPPINGS = {
        'margaux-demi': 'margaux-demi', // Same in both
        'catbird-cygnet': 'catbird-threadbare' // Similar product type
    };

    let gallery = null;

    /**
     * Get hearted items from both galleries (union)
     */
    function getHeartedItems() {
        try {
            const evening = JSON.parse(localStorage.getItem(HEARTS_KEYS.evening) || '[]');
            const wardrobe = JSON.parse(localStorage.getItem(HEARTS_KEYS.wardrobe) || '[]');
            
            // Merge both sets
            const allHearts = new Set([...evening]);
            
            // Map wardrobe hearts to evening IDs where applicable
            wardrobe.forEach(id => {
                if (PRODUCT_MAPPINGS[id]) {
                    allHearts.add(PRODUCT_MAPPINGS[id]);
                }
                allHearts.add(id);
            });
            
            return allHearts;
        } catch (e) {
            return new Set();
        }
    }

    /**
     * Save hearted item to evening storage + history
     */
    function saveHeartedItems(heartedSet) {
        try {
            const hearts = Array.from(heartedSet);
            localStorage.setItem(HEARTS_KEYS.evening, JSON.stringify(hearts));
            
            // Also save to history with timestamp
            const history = JSON.parse(localStorage.getItem(HEARTS_KEYS.history) || '[]');
            history.push({
                gallery: 'evening',
                items: hearts,
                timestamp: Date.now()
            });
            if (history.length > 100) history.shift();
            localStorage.setItem(HEARTS_KEYS.history, JSON.stringify(history));
        } catch (e) {
            console.warn('Could not save hearts:', e);
        }
    }

    /**
     * Toggle heart on a product
     */
    function toggleHeart(productId) {
        const hearts = getHeartedItems();
        
        if (hearts.has(productId)) {
            hearts.delete(productId);
        } else {
            hearts.add(productId);
            bumpBadge('favorites', 1);
            // Celebration particles
            createHeartParticles(document.querySelector(`[data-product-id="${productId}"]`));
        }
        
        saveHeartedItems(hearts);
        updateHeartButtons();
        updateStats();
        
        return hearts.has(productId);
    }

    /**
     * Update all heart button states
     */
    function updateHeartButtons() {
        const hearts = getHeartedItems();
        document.querySelectorAll('.heart-button').forEach(btn => {
            const productId = btn.dataset.productId;
            const isHearted = hearts.has(productId);
            
            btn.classList.toggle('hearted', isHearted);
            btn.innerHTML = isHearted ? '❤️' : '🤍';
            btn.setAttribute('aria-pressed', isHearted);
        });
    }

    // ═══════════════════════════════════════════════════════════════════════
    // MICRODELIGHTS — Heart celebration particles
    // ═══════════════════════════════════════════════════════════════════════

    function createHeartParticles(element) {
        if (!element) return;
        
        const rect = element.getBoundingClientRect();
        const x = rect.left + rect.width / 2;
        const y = rect.top + rect.height / 2;
        
        const particles = ['✨', '💫', '⭐', '💕'];
        
        for (let i = 0; i < 6; i++) {
            const particle = document.createElement('span');
            particle.className = 'heart-particle';
            particle.textContent = particles[Math.floor(Math.random() * particles.length)];
            particle.style.cssText = `
                position: fixed;
                left: ${x}px;
                top: ${y}px;
                font-size: 16px;
                pointer-events: none;
                z-index: 9999;
                opacity: 1;
                transform: translate(-50%, -50%);
                animation: particle-float 0.8s ease-out forwards;
                --dx: ${(Math.random() - 0.5) * 100}px;
                --dy: ${-30 - Math.random() * 60}px;
            `;
            document.body.appendChild(particle);
            
            setTimeout(() => particle.remove(), 800);
        }
    }

    // ═══════════════════════════════════════════════════════════════════════
    // DATA & RENDERING
    // ═══════════════════════════════════════════════════════════════════════

    async function loadGallery() {
        try {
            const response = await fetch('./data/gallery.json');
            gallery = await response.json();
            return gallery;
        } catch (error) {
            console.error('Failed to load gallery:', error);
            return null;
        }
    }

    function renderProductCard(product, index) {
        const hearts = getHeartedItems();
        const isHearted = hearts.has(product.id);
        const delay = index * 0.1;
        
        return `
            <article class="product-card" data-product-id="${product.id}" style="--delay: ${delay}s">
                <button 
                    class="heart-button ${isHearted ? 'hearted' : ''}" 
                    data-product-id="${product.id}" 
                    aria-label="Add ${product.name} to favorites"
                    aria-pressed="${isHearted}"
                >
                    ${isHearted ? '❤️' : '🤍'}
                </button>
                <a href="${product.product_url}" target="_blank" rel="noopener" class="product-card__link" aria-label="View ${product.name} on ${product.brand}">
                    <div class="product-card__image-container">
                        <img 
                            src="./images/${product.local_image}" 
                            alt="${product.name} by ${product.brand}"
                            class="product-card__image"
                            loading="lazy"
                        >
                        <div class="product-card__shimmer"></div>
                        ${product.badge ? `<span class="product-card__badge">${product.badge}</span>` : ''}
                    </div>
                </a>
                <div class="product-card__content">
                    <div class="product-card__header">
                        <span class="product-card__brand">${product.brand}</span>
                        <span class="product-card__origin">${product.maker || ''}</span>
                    </div>
                    <h3 class="product-card__name">${product.name}</h3>
                    <p class="product-card__description">${product.description}</p>
                    <footer class="product-card__footer">
                        <div class="product-card__status" data-status="${getItemStatus(product.id) || ''}">
                          <button class="status-button" type="button" data-product-id="${product.id}" aria-label="Set status for ${product.name}">
                            <span class="status-dot"></span>
                            <span class="status-label">${getItemStatus(product.id) || 'Just looking'}</span>
                          </button>
                          <div class="status-menu" role="menu" aria-hidden="true">
                            ${['wishlisted','considering','ordered','purchased','owned','returned','cancelled'].map(st => `
                              <button class="status-option" type="button" role="menuitem" data-status="${st}" data-product-id="${product.id}">${st}</button>`).join('')}
                          </div>
                        </div>
                        <div class="product-card__price-container">
                            <span class="product-card__price">${product.price_display}</span>
                            ${product.material ? `<span class="product-card__material">${product.material}</span>` : ''}
                        </div>
                        <a href="${product.product_url}" target="_blank" rel="noopener" class="product-card__cta">
                            <span>View</span>
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M7 17L17 7M17 7H7M17 7V17"/>
                            </svg>
                        </a>
                    </footer>
                </div>
            </article>
        `;
    }

    function renderGallery() {
        if (!gallery) return;

        const grids = {
            dresses: document.getElementById('dresses-grid'),
            pants: document.getElementById('pants-grid'),
            footwear: document.getElementById('footwear-grid'),
            accessories: document.getElementById('accessories-grid')
        };

        // Clear grids
        Object.values(grids).forEach(grid => {
            if (grid) grid.innerHTML = '';
        });

        // Count products per category for animation delays
        const categoryIndex = { dresses: 0, pants: 0, footwear: 0, accessories: 0 };

        // Populate grids
        gallery.products.forEach(product => {
            const grid = grids[product.category];
            if (grid) {
                grid.innerHTML += renderProductCard(product, categoryIndex[product.category]++);
            }
        });

        // Attach heart button listeners
        document.querySelectorAll('.heart-button').forEach(button => {
            button.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                toggleHeart(button.dataset.productId);
            });
        });

        // Add tilt effect to cards
        initCardTilt();
        
        // Update stats
        updateStats();
        
        // Trigger entrance animations
        requestAnimationFrame(() => {
            document.querySelectorAll('.product-card').forEach(card => {
                card.classList.add('visible');
            });
        });
    }

    function updateStats() {
        const totalEl = document.getElementById('total-investment');
        const countEl = document.getElementById('hearted-count');
        
        if (totalEl && gallery && gallery.products) {
            const total = gallery.products.reduce((sum, p) => sum + (p.price || 0), 0);
            animateNumber(totalEl, total, '$');
        }
        
        if (countEl) {
            const count = getHeartedItems().size;
            countEl.textContent = count;
        }
    }

    // ═══════════════════════════════════════════════════════════════════════
    // ANIMATIONS & INTERACTIONS
    // ═══════════════════════════════════════════════════════════════════════

    function animateNumber(element, target, prefix = '') {
        const duration = 600;
        const startTime = performance.now();
        const startValue = parseInt(element.textContent.replace(/[^0-9]/g, '')) || 0;
        
        function update(currentTime) {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            
            // Cubic ease-out
            const eased = 1 - Math.pow(1 - progress, 3);
            const current = Math.round(startValue + (target - startValue) * eased);
            
            element.textContent = `${prefix}${current.toLocaleString()}`;
            
            if (progress < 1) {
                requestAnimationFrame(update);
            }
        }
        
        requestAnimationFrame(update);
    }

    function initCardTilt() {
        const canTilt = window.matchMedia && window.matchMedia('(hover: hover) and (pointer: fine)').matches && !document.documentElement.classList.contains('reduced-motion');
        if (!canTilt) return;

        document.querySelectorAll('.product-card').forEach(card => {
            card.addEventListener('mousemove', (e) => {
                const rect = card.getBoundingClientRect();
                const x = (e.clientX - rect.left) / rect.width;
                const y = (e.clientY - rect.top) / rect.height;
                
                const tiltX = (y - 0.5) * 3;
                const tiltY = (x - 0.5) * -3;
                
                card.style.transform = `
                    translateY(-12px) 
                    perspective(1000px) 
                    rotateX(${tiltX}deg) 
                    rotateY(${tiltY}deg)
                    scale(1.01)
                `;
                
                // Move shimmer
                const shimmer = card.querySelector('.product-card__shimmer');
                if (shimmer) {
                    shimmer.style.setProperty('--shimmer-x', `${x * 100}%`);
                    shimmer.style.setProperty('--shimmer-y', `${y * 100}%`);
                }
            });
            
            card.addEventListener('mouseleave', () => {
                card.style.transform = '';
            });
        });
    }

    function initScrollReveal() {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('revealed');
                }
            });
        }, {
            threshold: 0.1,
            rootMargin: '0px 0px -50px 0px'
        });

        document.querySelectorAll('.collection-section, .philosophy-card').forEach(el => {
            observer.observe(el);
        });
    }

    function initSmoothScroll() {
        document.querySelectorAll('a[href^="#"]').forEach(link => {
            link.addEventListener('click', (e) => {
                const targetId = link.getAttribute('href');
                const target = document.querySelector(targetId);
                
                if (target) {
                    e.preventDefault();
                    const navHeight = 80;
                    const targetPosition = target.getBoundingClientRect().top + window.scrollY - navHeight;
                    
                    window.scrollTo({
                        top: targetPosition,
                        behavior: 'smooth'
                    });
                }
            });
        });
    }

    function initNavHighlight() {
        const sections = document.querySelectorAll('.collection-section');
        const navLinks = document.querySelectorAll('.nav-links a');
        
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const id = entry.target.id;
                    navLinks.forEach(link => {
                        link.classList.toggle('active', link.getAttribute('href') === `#${id}`);
                    });
                }
            });
        }, {
            threshold: 0.3,
            rootMargin: '-20% 0px -60% 0px'
        });

        sections.forEach(section => observer.observe(section));
    }



    function initStatusControls() {
        // toggle menus
        document.querySelectorAll('.status-button').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                const wrapper = btn.closest('.product-card__status');
                const menu = wrapper?.querySelector('.status-menu');
                if (!menu) return;

                const isOpen = menu.classList.contains('open');
                document.querySelectorAll('.status-menu.open').forEach(m => m.classList.remove('open'));
                menu.classList.toggle('open', !isOpen);
                menu.setAttribute('aria-hidden', isOpen ? 'true' : 'false');
            });
        });

        // select option
        document.querySelectorAll('.status-option').forEach(opt => {
            opt.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                const productId = opt.dataset.productId;
                const status = opt.dataset.status;
                if (!productId || !status) return;

                setItemStatus(productId, status);
                if (['ordered','purchased','owned','returned'].includes(status)) bumpBadge('orders', 1);

                // Update UI in-place
                const card = document.querySelector(`.product-card[data-product-id="${productId}"]`);
                const wrapper = card?.querySelector('.product-card__status');
                if (wrapper) {
                    wrapper.dataset.status = status;
                    const label = wrapper.querySelector('.status-label');
                    if (label) label.textContent = status;
                    const menu = wrapper.querySelector('.status-menu');
                    if (menu) {
                        menu.classList.remove('open');
                        menu.setAttribute('aria-hidden','true');
                    }
                }
            });
        });

        // close on outside click
        document.addEventListener('click', () => {
            document.querySelectorAll('.status-menu.open').forEach(m => {
                m.classList.remove('open');
                m.setAttribute('aria-hidden','true');
            });
        });
    }

    

    function categorizeProducts(ids) {
        const byCat = { dresses: [], pants: [], footwear: [], accessories: [], other: [] };
        const productById = new Map((gallery?.products || []).map(p => [p.id, p]));
        ids.forEach(id => {
            const p = productById.get(id);
            const cat = p?.category || 'other';
            (byCat[cat] || byCat.other).push(p || { id, name: id, brand: '', price_display: '', local_image: '', category: 'other' });
        });
        return byCat;
    }

    function statusDot(status) {
        const map = {
            wishlisted: '#d4a574',
            considering: '#e8c49a',
            ordered: '#8aa7ff',
            purchased: '#7fd3b7',
            owned: '#59d38a',
            returned: '#ff8a8a',
            cancelled: '#c6a6ff',
        };
        return map[status] || 'rgba(255,255,255,0.22)';
    }

    function renderFavoritesDrawer() {
        const root = document.querySelector('[data-drawer-content="favorites"]');
        if (!root) return;
        const hearts = Array.from(getHeartedItems());
        const productById = new Map((gallery?.products || []).map(p => [p.id, p]));
        const inThisGallery = hearts.filter(id => productById.has(id));

        if (!inThisGallery.length) {
            root.innerHTML = `<div class="drawer-empty">No favorites yet. Tap ♥ on any piece — it syncs with your Wardrobe favorites.</div>`;
            return;
        }

        const cats = categorizeProducts(inThisGallery);
        const order = [ ['dresses','Dresses'], ['pants','Pants'], ['footwear','Footwear'], ['accessories','Accessories'], ['other','Other'] ];
        root.innerHTML = order.map(([key,label]) => {
            const items = cats[key];
            if (!items.length) return '';
            return `
              <section class="drawer__section">
                <div class="drawer__section-title">${label}</div>
                ${items.map(p => {
                    const st = getItemStatus(p.id) || '';
                    return `
                      <div class="drawer-item" data-product-id="${p.id}">
                        <img class="drawer-item__img" src="./images/${p.local_image}" alt="${p.name}">
                        <div>
                          <div class="drawer-item__name">${p.name}</div>
                          <div class="drawer-item__meta">${p.brand} · ${p.price_display || ''}</div>
                        </div>
                        <div class="drawer-item__right">
                          <div class="drawer-pill"><span class="drawer-pill__dot" style="background:${statusDot(st)}"></span>${st || 'Just looking'}</div>
                          <a class="product-card__cta" href="${p.product_url}" target="_blank" rel="noopener"><span>View</span><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M7 17L17 7M17 7H7M17 7V17"/></svg></a>
                        </div>
                      </div>
                    `;
                }).join('')}
              </section>
            `;
        }).join('');
    }

    function renderOrdersDrawer() {
        const root = document.querySelector('[data-drawer-content="orders"]');
        if (!root) return;

        const state = loadOrderState();
        const productById = new Map((gallery?.products || []).map(p => [p.id, p]));

        const orderedLike = ['ordered','purchased'];
        const activeIds = Object.keys(state).filter(id => orderedLike.includes(state[id]?.status) && productById.has(id));
        const pastIds = Object.keys(state).filter(id => ['owned','returned','cancelled'].includes(state[id]?.status) && productById.has(id));

        const last = getLastAction();
        const banner = last ? `
          <div class="drawer-empty" style="border-style:solid;border-color:rgba(212,165,116,0.25)">
            <strong>Last update:</strong> ${last.verb} <em>${last.name}</em> → <strong>${last.status}</strong>
          </div>
        ` : '';

        if (!activeIds.length && !pastIds.length) {
            root.innerHTML = banner + `<div class="drawer-empty">No orders tracked yet. Use the status pill on any card to mark <strong>Ordered</strong> / <strong>Purchased</strong> / <strong>Owned</strong>.</div>`;
            return;
        }

        function itemRow(p) {
            const st = state[p.id]?.status || '';
            const canCancel = st === 'ordered';
            const canReturn = st === 'purchased' || st === 'owned';

            return `
              <div class="drawer-item" data-product-id="${p.id}">
                <img class="drawer-item__img" src="./images/${p.local_image}" alt="${p.name}">
                <div>
                  <div class="drawer-item__name">${p.name}</div>
                  <div class="drawer-item__meta">${p.brand} · ${p.price_display || ''}</div>
                  <div class="drawer-item__meta">Status: <strong>${st}</strong></div>
                </div>
                <div class="drawer-item__right">
                  <div class="drawer-pill"><span class="drawer-pill__dot" style="background:${statusDot(st)}"></span>${st}</div>
                  <div style="display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end;">
                    ${canCancel ? `<button class="order-action order-action--cancel" type="button" data-action="cancel" data-product-id="${p.id}">Cancel</button>` : ''}
                    ${canReturn ? `<button class="order-action order-action--return" type="button" data-action="return" data-product-id="${p.id}">Return</button>` : ''}
                  </div>
                  <a class="product-card__cta" href="${p.product_url}" target="_blank" rel="noopener"><span>View</span><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M7 17L17 7M17 7H7M17 7V17"/></svg></a>
                </div>
              </div>
            `;
        }

        const activeHtml = activeIds
          .map(id => productById.get(id))
          .filter(Boolean)
          .map(itemRow)
          .join('');

        const pastHtml = pastIds
          .map(id => productById.get(id))
          .filter(Boolean)
          .map(itemRow)
          .join('');

        root.innerHTML = banner + `
          ${activeHtml ? `<section class="drawer__section"><div class="drawer__section-title">Active orders</div>${activeHtml}</section>` : ''}
          ${pastHtml ? `<section class="drawer__section"><div class="drawer__section-title">Past</div>${pastHtml}</section>` : ''}
        `;

        // Wire actions
        root.querySelectorAll('.order-action').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                const productId = btn.dataset.productId;
                const action = btn.dataset.action;
                const p = productById.get(productId);
                if (!p) return;

                if (action === 'cancel') {
                    setItemStatus(productId, 'cancelled');
                    setLastAction({ verb: 'Cancelled', name: p.name, status: 'cancelled', productId });
                }
                if (action === 'return') {
                    setItemStatus(productId, 'returned');
                    setLastAction({ verb: 'Marked return', name: p.name, status: 'returned', productId });
                }

                // Rerender immediately so it’s screenshot-debuggable
                renderOrdersDrawer();
            });
        });
    }



    // ═══════════════════════════════════════════════════════════════════════
    // INITIALIZATION
    // ═══════════════════════════════════════════════════════════════════════

    document.addEventListener('DOMContentLoaded', async () => {
        // Add particle animation keyframes
        const style = document.createElement('style');
        style.textContent = `
            @keyframes particle-float {
                0% {
                    opacity: 1;
                    transform: translate(-50%, -50%) scale(1);
                }
                100% {
                    opacity: 0;
                    transform: translate(calc(-50% + var(--dx)), calc(-50% + var(--dy))) scale(0.5);
                }
            }
        `;
        document.head.appendChild(style);
        
        // Load and render gallery
        gallery = await loadGallery();
        if (gallery) {
            renderGallery();
        }
        
        // Initialize interactions
        initScrollReveal();
        initSmoothScroll();
        initNavHighlight();
        initStatusControls();

        // Drawers + badges
        renderBadges();
        document.querySelectorAll('.nav-action').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                openDrawer(btn.dataset.panel);
            });
        });
        const overlay = document.querySelector('.drawer-overlay');
        if (overlay) overlay.addEventListener('click', closeDrawers);
        document.querySelectorAll('.drawer__close').forEach(b => b.addEventListener('click', closeDrawers));
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') closeDrawers();
        });

        // Log for debugging
        console.log('✨ The Evening Edit initialized');
        console.log('💕 Hearts:', Array.from(getHeartedItems()));
    });

    // ═══════════════════════════════════════════════════════════════════════
    // REDUCED MOTION
    // ═══════════════════════════════════════════════════════════════════════

    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        document.documentElement.classList.add('reduced-motion');
    }

    // Export for debugging
    window.eveningEdit = {
        getHeartedItems: () => Array.from(getHeartedItems()),
        toggleHeart,
        gallery: () => gallery
    };

})();
