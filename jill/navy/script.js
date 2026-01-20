/**
 * ═══════════════════════════════════════════════════════════════════════════
 * TRUE BLUE — Jill's Navy Wardrobe
 * ═══════════════════════════════════════════════════════════════════════════
 *
 * Navy isn't safe—it's signature.
 * Orders persist across galleries.
 * Hearts sync because love persists.
 *
 * — Kagami, January 2026
 */

(function() {
    'use strict';

    // Boot marker
    window.__true_blue_boot = Date.now();

    // ═══════════════════════════════════════════════════════════════════════
    // HEARTS PERSISTENCE — Synced across galleries
    // ═══════════════════════════════════════════════════════════════════════

    const HEARTS_KEYS = {
        navy: 'jill_navy_hearts',
        evening: 'jill_evening_hearts',
        wardrobe: 'jill_wardrobe_hearts',
        history: 'jill_hearts_history'
    };

    function getHeartedItems() {
        const all = new Set();
        Object.values(HEARTS_KEYS).forEach(key => {
            try {
                const hearts = JSON.parse(localStorage.getItem(key) || '[]');
                if (Array.isArray(hearts)) hearts.forEach(h => all.add(h));
            } catch {}
        });
        return all;
    }

    function saveHeartedItem(productId) {
        const hearts = getHeartedItems();
        hearts.add(productId);
        localStorage.setItem(HEARTS_KEYS.navy, JSON.stringify([...hearts]));
    }

    function removeHeartedItem(productId) {
        const hearts = getHeartedItems();
        hearts.delete(productId);
        localStorage.setItem(HEARTS_KEYS.navy, JSON.stringify([...hearts]));
    }

    function isHearted(productId) {
        return getHeartedItems().has(productId);
    }

    // ═══════════════════════════════════════════════════════════════════════
    // ORDER STATE — Shared across Jill galleries
    // ═══════════════════════════════════════════════════════════════════════

    const ORDER_STATE_KEY = 'jill_order_state_v1';

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

    // ═══════════════════════════════════════════════════════════════════════
    // BADGES — Notification counts
    // ═══════════════════════════════════════════════════════════════════════

    const BADGE_KEY = 'jill_badges_v1';

    function loadBadges() {
        try { 
            return JSON.parse(localStorage.getItem(BADGE_KEY) || '{"favorites":0,"orders":0}'); 
        } catch { 
            return { favorites: 0, orders: 0 }; 
        }
    }

    function saveBadges(badges) {
        try { localStorage.setItem(BADGE_KEY, JSON.stringify(badges)); } catch {}
    }

    function bumpBadge(kind, delta = 1) {
        const b = loadBadges();
        b[kind] = Math.max(0, (b[kind] || 0) + delta);
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
        const favBadge = document.getElementById('favorites-count');
        const ordersBadge = document.getElementById('orders-count');
        
        if (favBadge) {
            favBadge.textContent = b.favorites || '';
            favBadge.style.display = b.favorites > 0 ? 'inline-flex' : 'none';
        }
        if (ordersBadge) {
            ordersBadge.textContent = b.orders || '';
            ordersBadge.style.display = b.orders > 0 ? 'inline-flex' : 'none';
        }
    }

    // ═══════════════════════════════════════════════════════════════════════
    // REAL ORDER DATA — From Jill's Wardrobe Update (January 19, 2026)
    // ═══════════════════════════════════════════════════════════════════════
    // Confirmed: $1,950.32 | Pending Custom: ~$975 | Total Investment: ~$2,925
    // ═══════════════════════════════════════════════════════════════════════

    const JILL_ORDERS = {
        confirmed: [
            { brand: 'Jenni Kayne', item: 'Brentwood Blazer + Cashmere Cocoon Cardigan', size: '2 / XS', price: '$765.56', img: '../wardrobe/images/jenni-kayne-blazer.jpg' },
            { brand: 'La Ligne', item: 'Marin Stripe Sweater', size: 'XS', price: '$397.83', img: '../wardrobe/images/la-ligne-marin.jpg' },
            { brand: 'Sézane', item: 'Eli Scarf Navy + FREE Mon Amour Totebag 💙', size: '—', price: '$135.98', img: '../wardrobe/images/sezane-scarf.jpg' },
            { brand: 'Barbour', item: 'Cropped Beadnell Waxed Jacket', size: 'US 6', price: '$469.84', img: '../wardrobe/images/barbour-beadnell.jpg' },
            { brand: 'Saint James', item: 'Minquidame Breton Striped Shirt', size: '2', price: '$97.00', img: '../wardrobe/images/saint-james-breton.jpg' },
            { brand: 'Catbird', item: 'Threadbare Ring 14K Gold', size: '7', price: '$84.01', img: '../wardrobe/images/catbird-threadbare.jpg' },
        ],
        pending_custom: [
            {
                brand: 'Margaux',
                item: 'The Demi Ballet Flat',
                subtitle: 'Personalized made-to-order',
                img: '../wardrobe/images/margaux-demi.jpg',
                specs: 'Ivory Nappa · Light Blue lining 💙 · JSH · Size 38 (US 8) · Medium',
                price: '$325',
                status: 'Contact submitted'
            },
            {
                brand: 'Ahlem',
                item: 'One of One Bespoke Frames',
                subtitle: 'French handcrafted eyewear',
                img: '../wardrobe/images/ahlem-custom.jpg',
                specs: 'One of One Custom · MOF-certified artisan',
                price: '~$650',
                status: 'Consultation drafted'
            },
        ],
        summary: {
            confirmed_total: '$1,950.32',
            pending_total: '~$975.00',
            grand_total: '~$2,925'
        }
    };

    // ═══════════════════════════════════════════════════════════════════════
    // GALLERY STATE
    // ═══════════════════════════════════════════════════════════════════════

    let gallery = null;

    async function loadGallery() {
        try {
            const response = await fetch('data/gallery.json');
            if (!response.ok) throw new Error('Failed to load gallery');
            return await response.json();
        } catch (error) {
            console.error('Error loading gallery:', error);
            return null;
        }
    }

    // ═══════════════════════════════════════════════════════════════════════
    // RENDER FUNCTIONS
    // ═══════════════════════════════════════════════════════════════════════

    // Fibonacci delays for staggered animations
    const FIBONACCI_DELAYS = [0, 89, 144, 233, 377, 610, 987, 1597];

    function renderPhilosophy() {
        const grid = document.getElementById('philosophy-grid');
        if (!gallery?.philosophy || !grid) return;

        grid.innerHTML = gallery.philosophy.map((p, i) => `
            <div class="philosophy-card" style="animation-delay: ${FIBONACCI_DELAYS[i] || i * 144}ms">
                <div class="philosophy-icon">${p.icon}</div>
                <h3 class="philosophy-title">${p.title}</h3>
                <p class="philosophy-text">${p.description}</p>
            </div>
        `).join('');
    }

    function renderGallery() {
        const content = document.getElementById('gallery-content');
        if (!gallery?.products || !content) return;
        
        const categories = {
            pants: { title: 'Pants', subtitle: 'The Foundation — 8 styles for every moment', products: [] },
            dresses: { title: 'Dresses', subtitle: 'Every Occasion — From boardroom to evening', products: [] },
            outerwear: { title: 'Outerwear', subtitle: 'Including her asks', products: [] },
            accessories: { title: 'Accessories', subtitle: 'Bags, shoes, and finishing touches', products: [] },
            joy: { title: 'Joy Pieces', subtitle: 'Novelty and delight — life\'s too short for boring', products: [] }
        };
        
        gallery.products.forEach(product => {
            const cat = categories[product.category];
            if (cat) cat.products.push(product);
        });
        
        let html = '';
        
        Object.entries(categories).forEach(([key, cat]) => {
            if (cat.products.length === 0) return;
            
            html += `
                <section class="category-section" data-category="${key}">
                    <div class="category-header">
                        <p class="category-eyebrow">${cat.products.length} Pieces</p>
                        <h2 class="category-title">${cat.title}</h2>
                        <p class="category-subtitle">${cat.subtitle}</p>
                    </div>
                    <div class="product-grid">
                        ${cat.products.map(renderProductCard).join('')}
                    </div>
                </section>
            `;
        });
        
        content.innerHTML = html;
        updateHeartButtons();
    }

    function renderProductCard(product) {
        const hearted = isHearted(product.id);
        const badgeClass = product.badge === 'Her Ask' ? 'her-ask' : 
                           product.badge === 'Hearted' ? 'hearted' : '';
        
        return `
            <article class="product-card ${product.is_centerpiece ? 'centerpiece' : ''}" 
                     data-product-id="${product.id}"
                     tabindex="0"
                     role="button"
                     aria-label="${product.brand} ${product.name}, ${product.price_display}"
                     onclick="window.handleProductClick(event, '${product.product_url}')"
                     onkeydown="window.handleProductKeydown(event, '${product.product_url}')">
                <div class="product-image-wrap">
                    <img class="product-image" 
                         src="images/${product.local_image}" 
                         alt="${product.name}"
                         loading="lazy"
                         onerror="this.src='https://via.placeholder.com/400x500/E0E5EC/415A77?text=Navy'">
                    ${product.badge ? `<span class="product-badge ${badgeClass}">${product.badge}</span>` : ''}
                    <button class="heart-button ${hearted ? 'active' : ''}" 
                            onclick="window.toggleHeart(event, '${product.id}')"
                            aria-label="${hearted ? 'Remove from favorites' : 'Add to favorites'}">
                        <svg viewBox="0 0 24 24">
                            <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
                        </svg>
                    </button>
                </div>
                <div class="product-info">
                    <p class="product-brand">${product.brand}</p>
                    <h3 class="product-name">${product.name}</h3>
                    <p class="product-description">${product.description}</p>
                    <div class="product-meta">
                        <span class="product-price">${product.price_display}</span>
                        <span class="product-occasion">${product.occasion || product.subcategory}</span>
                    </div>
                    <a href="${product.product_url}" target="_blank" rel="noopener" class="product-link" onclick="event.stopPropagation()">
                        View piece →
                    </a>
                </div>
            </article>
        `;
    }

    function renderOutfits() {
        const grid = document.getElementById('outfits-grid');
        if (!gallery?.outfits || !grid) return;
        
        grid.innerHTML = gallery.outfits.map(outfit => {
            const products = outfit.products.map(id => 
                gallery.products.find(p => p.id === id)
            ).filter(Boolean);
            
            return `
                <div class="outfit-card">
                    <h3 class="outfit-name">${outfit.name}</h3>
                    <p class="outfit-description">${outfit.description}</p>
                    <div class="outfit-products">
                        ${products.map(p => `
                            <img class="outfit-product-thumb" 
                                 src="images/${p.local_image}" 
                                 alt="${p.name}"
                                 title="${p.brand} ${p.name}"
                                 onerror="this.src='https://via.placeholder.com/60x60/E0E5EC/415A77?text=N'">
                        `).join('')}
                    </div>
                </div>
            `;
        }).join('');
    }

    // ═══════════════════════════════════════════════════════════════════════
    // ORDERS DRAWER
    // ═══════════════════════════════════════════════════════════════════════

    function renderOrdersDrawer() {
        const root = document.getElementById('orders-content');
        if (!root) return;

        function confirmedRow(order) {
            return `
              <div class="order-card">
                <img class="order-card__img" src="${order.img}" alt="${order.item}"
                     onerror="this.src='https://via.placeholder.com/70x70/E0E5EC/415A77?text=·'">
                <div class="order-card__body">
                  <div class="order-card__brand">${order.brand}</div>
                  <div class="order-card__name">${order.item}</div>
                  <div class="order-card__meta">
                    <span class="order-card__size">Size ${order.size}</span>
                    ${order.price ? `<span class="order-card__price">${order.price}</span>` : ''}
                  </div>
                </div>
                <div class="order-card__status order-card__status--confirmed">✓</div>
              </div>
            `;
        }

        function customRow(order) {
            return `
              <div class="order-card order-card--custom">
                <img class="order-card__img" src="${order.img}" alt="${order.item}"
                     onerror="this.src='https://via.placeholder.com/70x70/E0E5EC/415A77?text=·'">
                <div class="order-card__body">
                  <div class="order-card__brand">${order.brand} <span class="order-card__status order-card__status--pending">${order.status}</span></div>
                  <div class="order-card__name">${order.item}</div>
                  <div class="order-card__subtitle">${order.subtitle}</div>
                  <div class="order-card__specs">${order.specs}</div>
                  ${order.price ? `<div class="order-card__price">${order.price}</div>` : ''}
                </div>
              </div>
            `;
        }

        root.innerHTML = `
          <!-- Order Summary -->
          <div class="orders-summary">
            <div class="orders-summary__row">
              <span>Confirmed Orders</span>
              <span class="orders-summary__value">${JILL_ORDERS.summary.confirmed_total}</span>
            </div>
            <div class="orders-summary__row">
              <span>Pending Custom</span>
              <span class="orders-summary__value orders-summary__value--pending">${JILL_ORDERS.summary.pending_total}</span>
            </div>
            <div class="orders-summary__row orders-summary__row--total">
              <span>Total Investment</span>
              <span class="orders-summary__value orders-summary__value--total">${JILL_ORDERS.summary.grand_total}</span>
            </div>
          </div>

          <section class="orders-group">
            <h3 class="orders-group__title">✓ Confirmed (${JILL_ORDERS.confirmed.length})</h3>
            <div class="orders-group__list">
              ${JILL_ORDERS.confirmed.map(confirmedRow).join('')}
            </div>
          </section>

          <section class="orders-group orders-group--custom">
            <h3 class="orders-group__title">⏳ Pending Custom (${JILL_ORDERS.pending_custom.length})</h3>
            <div class="orders-group__list">
              ${JILL_ORDERS.pending_custom.map(customRow).join('')}
            </div>
          </section>
        `;
    }

    // ═══════════════════════════════════════════════════════════════════════
    // FAVORITES DRAWER
    // ═══════════════════════════════════════════════════════════════════════

    function renderFavoritesDrawer() {
        const content = document.getElementById('favorites-content');
        if (!content || !gallery?.products) return;
        
        const hearts = getHeartedItems();
        const heartedProducts = gallery.products.filter(p => hearts.has(p.id));
        
        if (heartedProducts.length === 0) {
            content.innerHTML = `
                <div class="drawer-empty">
                    <p>No favorites yet</p>
                    <p style="font-size: var(--text-sm); margin-top: var(--space-2);">Heart pieces you love</p>
                </div>
            `;
            return;
        }
        
        content.innerHTML = heartedProducts.map(p => `
            <div class="drawer-item">
                <img class="drawer-item-image" 
                     src="images/${p.local_image}" 
                     alt="${p.name}"
                     onerror="this.src='https://via.placeholder.com/70x70/E0E5EC/415A77?text=N'">
                <div class="drawer-item-info">
                    <p class="drawer-item-brand">${p.brand}</p>
                    <p class="drawer-item-name">${p.name}</p>
                    <p class="drawer-item-price">${p.price_display}</p>
                </div>
            </div>
        `).join('');
    }

    // ═══════════════════════════════════════════════════════════════════════
    // STATS
    // ═══════════════════════════════════════════════════════════════════════

    function updateStats() {
        if (!gallery?.products) return;
        
        const total = gallery.products.reduce((sum, p) => sum + (p.price || 0), 0);
        const pants = gallery.products.filter(p => p.category === 'pants').length;
        const dresses = gallery.products.filter(p => p.category === 'dresses').length;
        const hearted = getHeartedItems().size;
        
        const el = id => document.getElementById(id);
        
        if (el('stat-pieces')) el('stat-pieces').textContent = gallery.products.length;
        if (el('stat-pants')) el('stat-pants').textContent = pants;
        if (el('stat-dresses')) el('stat-dresses').textContent = dresses;
        if (el('stat-total')) el('stat-total').textContent = `$${total.toLocaleString()}`;
        if (el('footer-hearted')) el('footer-hearted').textContent = hearted;
        if (el('footer-total')) el('footer-total').textContent = `$${total.toLocaleString()}`;
    }

    // ═══════════════════════════════════════════════════════════════════════
    // HEART INTERACTIONS
    // ═══════════════════════════════════════════════════════════════════════

    window.toggleHeart = function(event, productId) {
        event.stopPropagation();
        
        const button = event.currentTarget;
        const wasHearted = isHearted(productId);
        
        if (wasHearted) {
            removeHeartedItem(productId);
            button.classList.remove('active');
        } else {
            saveHeartedItem(productId);
            button.classList.add('active');
            bumpBadge('favorites', 1);
            createHeartParticles(button);
        }
        
        updateStats();
    };

    window.handleProductClick = function(event, url) {
        if (event.target.closest('.heart-button')) return;
        if (url) window.open(url, '_blank', 'noopener');
    };

    // Keyboard handler for product cards (WCAG 2.1.1)
    window.handleProductKeydown = function(event, url) {
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            if (event.target.closest('.heart-button')) return;
            if (url) window.open(url, '_blank', 'noopener');
        }
    };

    function updateHeartButtons() {
        document.querySelectorAll('.heart-button').forEach(button => {
            const card = button.closest('.product-card');
            const productId = card?.dataset.productId;
            if (productId) {
                button.classList.toggle('active', isHearted(productId));
            }
        });
    }

    function createHeartParticles(button) {
        const rect = button.getBoundingClientRect();
        const centerX = rect.left + rect.width / 2;
        const centerY = rect.top + rect.height / 2;
        
        for (let i = 0; i < 8; i++) {
            const particle = document.createElement('div');
            particle.style.cssText = `
                position: fixed;
                left: ${centerX}px;
                top: ${centerY}px;
                width: 6px;
                height: 6px;
                background: var(--heart);
                border-radius: 50%;
                pointer-events: none;
                z-index: 9999;
            `;
            document.body.appendChild(particle);
            
            const angle = (i / 8) * Math.PI * 2;
            const distance = 30 + Math.random() * 20;
            const dx = Math.cos(angle) * distance;
            const dy = Math.sin(angle) * distance;
            
            particle.animate([
                { transform: 'translate(-50%, -50%) scale(1)', opacity: 1 },
                { transform: `translate(calc(-50% + ${dx}px), calc(-50% + ${dy}px)) scale(0)`, opacity: 0 }
            ], {
                duration: 500,
                easing: 'cubic-bezier(0.34, 1.56, 0.64, 1)'
            }).onfinish = () => particle.remove();
        }
    }

    // ═══════════════════════════════════════════════════════════════════════
    // DRAWER CONTROLS
    // ═══════════════════════════════════════════════════════════════════════

    // Track which button opened drawer for focus restoration
    let lastFocusedDrawerTrigger = null;

    function openDrawer(kind) {
        const overlay = document.querySelector('.drawer-overlay');
        const drawer = document.getElementById(`${kind}-drawer`);
        const button = document.getElementById(`${kind}-btn`);

        // Save trigger for focus restoration
        lastFocusedDrawerTrigger = button;

        if (overlay) overlay.classList.add('active');
        if (drawer) {
            drawer.classList.add('active');
            drawer.removeAttribute('hidden');
            drawer.setAttribute('aria-hidden', 'false');
        }
        if (button) button.setAttribute('aria-expanded', 'true');

        // Prevent body scroll while drawer is open
        document.body.style.overflow = 'hidden';

        // Clear badge on open
        clearBadge(kind);

        // Render content
        if (kind === 'favorites') renderFavoritesDrawer();
        if (kind === 'orders') renderOrdersDrawer();

        // Focus trap - focus first focusable element
        setTimeout(() => {
            const closeBtn = drawer?.querySelector('.drawer-close');
            if (closeBtn) closeBtn.focus();
        }, 100);

        // Set up focus trap within drawer
        if (drawer) {
            drawer.addEventListener('keydown', trapFocus);
        }
    }

    function closeDrawers() {
        document.querySelector('.drawer-overlay')?.classList.remove('active');
        document.querySelectorAll('.drawer').forEach(d => {
            d.classList.remove('active');
            d.setAttribute('hidden', '');
            d.setAttribute('aria-hidden', 'true');
            d.removeEventListener('keydown', trapFocus);
        });

        // Restore body scroll
        document.body.style.overflow = '';

        // Reset aria-expanded on buttons
        document.getElementById('favorites-btn')?.setAttribute('aria-expanded', 'false');
        document.getElementById('orders-btn')?.setAttribute('aria-expanded', 'false');

        // Restore focus to trigger button (WCAG 2.4.3)
        if (lastFocusedDrawerTrigger) {
            lastFocusedDrawerTrigger.focus();
            lastFocusedDrawerTrigger = null;
        }
    }

    // Focus trap helper (WCAG 2.1.2)
    function trapFocus(event) {
        if (event.key !== 'Tab') return;

        const drawer = event.currentTarget;
        const focusable = drawer.querySelectorAll(
            'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        const first = focusable[0];
        const last = focusable[focusable.length - 1];

        if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
        }
    }

    function setupDrawers() {
        // Favorites
        const favBtn = document.getElementById('favorites-btn');
        favBtn?.addEventListener('click', () => openDrawer('favorites'));
        
        // Orders
        const ordersBtn = document.getElementById('orders-btn');
        ordersBtn?.addEventListener('click', () => openDrawer('orders'));
        
        // Overlay click closes
        const overlay = document.querySelector('.drawer-overlay');
        overlay?.addEventListener('click', closeDrawers);
        
        // Close buttons
        document.querySelectorAll('.drawer-close').forEach(btn => {
            btn.addEventListener('click', closeDrawers);
        });
        
        // ESC key closes
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') closeDrawers();
        });
    }

    // ═══════════════════════════════════════════════════════════════════════
    // INITIALIZATION
    // ═══════════════════════════════════════════════════════════════════════

    async function boot() {
        // Load gallery
        gallery = await loadGallery();
        
        if (!gallery) {
            console.error('Failed to load gallery');
            return;
        }
        
        // Render everything
        renderPhilosophy();
        renderGallery();
        renderOutfits();
        updateStats();
        renderBadges();
        setupDrawers();
        
        console.log('🔵 True Blue loaded — Navy is her signature');
        console.log('💕 Hearts:', Array.from(getHeartedItems()));
        console.log('📦 Orders:', JILL_ORDERS.confirmed.length + JILL_ORDERS.pending_custom.length, 'items');
    }

    // Run on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', boot);
    } else {
        boot();
    }

})();
