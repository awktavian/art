/**
 * TRUE BLUE — Jill's Navy Wardrobe
 *
 * Navy isn't safe—it's signature.
 * Orders persist across galleries.
 * Hearts sync because love persists.
 *
 * — Kagami, January 2026
 *
 * v2.0 Updates:
 * - Fixed event listener memory leaks in drawer management
 * - Added error UI when gallery fails to load
 * - Orders now loaded from gallery.json instead of hardcoded
 * - Improved focus trap lifecycle management
 * - Replaced inline handlers with event delegation
 */

(function() {
    'use strict';

    // HEARTS PERSISTENCE
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

    // ORDER STATE
    const ORDER_STATE_KEY = 'jill_order_state_v1';

    function loadOrderState() {
        try { return JSON.parse(localStorage.getItem(ORDER_STATE_KEY) || '{}'); }
        catch { return {}; }
    }

    function saveOrderState(state) {
        try { localStorage.setItem(ORDER_STATE_KEY, JSON.stringify(state)); }
        catch (e) { console.warn('Could not save order state:', e); }
    }

    // BADGES
    const BADGE_KEY = 'jill_badges_v1';

    function loadBadges() {
        try { return JSON.parse(localStorage.getItem(BADGE_KEY) || '{"favorites":0,"orders":0}'); }
        catch { return { favorites: 0, orders: 0 }; }
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

    // GALLERY STATE
    let gallery = null;
    const drawerHandlers = new WeakMap();

    async function loadGallery() {
        try {
            const response = await fetch('data/gallery.json');
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error('Error loading gallery:', error);
            return null;
        }
    }

    // ERROR STATE
    function renderErrorState() {
        const content = document.getElementById('gallery-content');
        if (!content) return;
        content.innerHTML = `
            <div class="error-state">
                <div class="error-state__icon">⚓</div>
                <h2 class="error-state__title">Gallery couldn't load</h2>
                <p class="error-state__message">There was a problem loading the collection. Please refresh the page to try again.</p>
                <button class="error-state__button" id="error-refresh-btn">Refresh Page</button>
            </div>`;
        document.querySelector('.stats-bar')?.style.setProperty('display', 'none');
        document.querySelector('.philosophy-section')?.style.setProperty('display', 'none');
        document.querySelector('.outfits-section')?.style.setProperty('display', 'none');
        document.getElementById('error-refresh-btn')?.addEventListener('click', () => location.reload());
    }

    // RENDER FUNCTIONS
    const FIBONACCI_DELAYS = [0, 89, 144, 233, 377, 610, 987, 1597];

    function renderPhilosophy() {
        const grid = document.getElementById('philosophy-grid');
        if (!gallery?.philosophy || !grid) return;
        grid.innerHTML = gallery.philosophy.map((p, i) => `
            <div class="philosophy-card" style="animation-delay: ${FIBONACCI_DELAYS[i] || i * 144}ms">
                <div class="philosophy-icon">${p.icon}</div>
                <h3 class="philosophy-title">${p.title}</h3>
                <p class="philosophy-text">${p.description}</p>
            </div>`).join('');
    }

    function renderGallery() {
        const content = document.getElementById('gallery-content');
        if (!gallery?.products || !content) return;

        const categories = {
            pants: { title: 'Pants', subtitle: 'The Foundation — styles for every moment', products: [] },
            dresses: { title: 'Dresses', subtitle: 'Every Occasion — From boardroom to evening', products: [] },
            outerwear: { title: 'Outerwear', subtitle: 'Including her asks', products: [] },
            accessories: { title: 'Accessories', subtitle: 'Shoes and finishing touches', products: [] },
            joy: { title: 'Joy Pieces', subtitle: "Novelty and delight", products: [] }
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
                </section>`;
        });

        content.innerHTML = html;
        setupProductCardEvents(content);
        updateHeartButtons();

        content.querySelectorAll('.product-image').forEach(img => {
            const wrap = img.closest('.product-image-wrap');
            if (img.complete) wrap?.classList.add('loaded');
            else img.addEventListener('load', () => wrap?.classList.add('loaded'), { once: true });
        });
    }

    function renderProductCard(product) {
        const hearted = isHearted(product.id);
        const badgeClass = product.badge === 'Her Ask' ? 'her-ask' : product.badge === 'Hearted' ? 'hearted' : '';
        return `
            <article class="product-card ${product.is_centerpiece ? 'centerpiece' : ''}"
                     data-product-id="${product.id}"
                     data-product-url="${encodeURIComponent(product.product_url)}"
                     tabindex="0" role="button"
                     aria-label="${product.brand} ${product.name}, ${product.price_display}">
                <div class="product-image-wrap">
                    <img class="product-image" src="images/${product.local_image}" alt="${product.brand} ${product.name}"
                         loading="lazy" onerror="this.src='https://via.placeholder.com/400x500/E0E5EC/415A77?text=Navy'">
                    ${product.badge ? `<span class="product-badge ${badgeClass}">${product.badge}</span>` : ''}
                    <button class="heart-button ${hearted ? 'active' : ''}" data-product-id="${product.id}"
                            aria-label="${hearted ? 'Remove from favorites' : 'Add to favorites'}">
                        <svg viewBox="0 0 24 24"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>
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
                    <a href="${product.product_url}" target="_blank" rel="noopener" class="product-link" aria-label="View ${product.brand} ${product.name} (opens in new window)">View piece <span aria-hidden="true">↗</span></a>
                </div>
            </article>`;
    }

    function setupProductCardEvents(container) {
        container.addEventListener('click', (event) => {
            const heartButton = event.target.closest('.heart-button');
            if (heartButton) {
                event.stopPropagation();
                const productId = heartButton.dataset.productId;
                if (productId) toggleHeart(heartButton, productId);
                return;
            }
            if (event.target.closest('.product-link')) return;
            const card = event.target.closest('.product-card');
            if (card) {
                const url = card.dataset.productUrl;
                if (url) window.open(decodeURIComponent(url), '_blank', 'noopener');
            }
        });
        container.addEventListener('keydown', (event) => {
            if (event.key !== 'Enter' && event.key !== ' ') return;
            const card = event.target.closest('.product-card');
            if (card && !event.target.closest('.heart-button') && !event.target.closest('.product-link')) {
                event.preventDefault();
                const url = card.dataset.productUrl;
                if (url) window.open(decodeURIComponent(url), '_blank', 'noopener');
            }
        });
    }

    function renderOutfits() {
        const grid = document.getElementById('outfits-grid');
        if (!gallery?.outfits || !grid) return;
        grid.innerHTML = gallery.outfits.map(outfit => {
            const products = outfit.products.map(id => gallery.products.find(p => p.id === id)).filter(Boolean);
            return `
                <div class="outfit-card">
                    <h3 class="outfit-name">${outfit.name}</h3>
                    <p class="outfit-description">${outfit.description}</p>
                    <div class="outfit-products">
                        ${products.map(p => `<img class="outfit-product-thumb" src="images/${p.local_image}" alt="${p.name}" title="${p.brand} ${p.name}" onerror="this.src='https://via.placeholder.com/60x60/E0E5EC/415A77?text=N'">`).join('')}
                    </div>
                </div>`;
        }).join('');
    }

    // ORDERS DRAWER - NOW FROM gallery.json
    function renderOrdersDrawer() {
        const root = document.getElementById('orders-content');
        if (!root) return;
        const orders = gallery?.orders || { confirmed: [], pending_custom: [] };
        const confirmedWithDetails = orders.confirmed.map(order => {
            const product = gallery?.products?.find(p => p.id === order.product_id);
            return { ...order, product };
        });

        function confirmedRow(order) {
            const p = order.product;
            return `<div class="order-card">
                <img class="order-card__img" src="${p ? `images/${p.local_image}` : 'https://via.placeholder.com/70x70/E0E5EC/415A77?text=·'}" alt="${p?.name || order.product_id}" onerror="this.src='https://via.placeholder.com/70x70/E0E5EC/415A77?text=·'">
                <div class="order-card__body">
                    <div class="order-card__brand">${p?.brand || 'Unknown'}</div>
                    <div class="order-card__name">${p?.name || order.product_id}</div>
                    <div class="order-card__meta">${order.notes ? `<span class="order-card__notes">${order.notes}</span>` : ''}${p?.price_display ? `<span class="order-card__price">${p.price_display}</span>` : ''}</div>
                </div>
                <div class="order-card__status order-card__status--confirmed">✓</div>
            </div>`;
        }

        function customRow(order) {
            return `<div class="order-card order-card--custom">
                <div class="order-card__body">
                    <div class="order-card__brand">Custom <span class="order-card__status order-card__status--pending">${order.status}</span></div>
                    <div class="order-card__name">${order.description}</div>
                    ${order.notes ? `<div class="order-card__notes">${order.notes}</div>` : ''}
                </div>
            </div>`;
        }

        const confirmedTotal = confirmedWithDetails.reduce((sum, o) => sum + (o.product?.price || 0), 0);

        root.innerHTML = `
            <div class="orders-summary">
                <div class="orders-summary__row"><span>Confirmed Orders</span><span class="orders-summary__value">$${confirmedTotal.toLocaleString()}</span></div>
                <div class="orders-summary__row"><span>Pending Custom</span><span class="orders-summary__value orders-summary__value--pending">${orders.pending_custom.length} items</span></div>
            </div>
            ${confirmedWithDetails.length > 0 ? `<section class="orders-group"><h3 class="orders-group__title">✓ Confirmed (${confirmedWithDetails.length})</h3><div class="orders-group__list">${confirmedWithDetails.map(confirmedRow).join('')}</div></section>` : ''}
            ${orders.pending_custom.length > 0 ? `<section class="orders-group orders-group--custom"><h3 class="orders-group__title">⏳ Pending (${orders.pending_custom.length})</h3><div class="orders-group__list">${orders.pending_custom.map(customRow).join('')}</div></section>` : ''}
            ${confirmedWithDetails.length === 0 && orders.pending_custom.length === 0 ? `<div class="drawer-empty"><p>No orders yet</p><p class="drawer-empty__hint">Orders will appear here when placed</p></div>` : ''}`;
    }

    function renderFavoritesDrawer() {
        const content = document.getElementById('favorites-content');
        if (!content || !gallery?.products) return;
        const hearts = getHeartedItems();
        const heartedProducts = gallery.products.filter(p => hearts.has(p.id));
        if (heartedProducts.length === 0) {
            content.innerHTML = `<div class="drawer-empty"><p>No favorites yet</p><p class="drawer-empty__hint">Heart pieces you love</p></div>`;
            return;
        }
        content.innerHTML = heartedProducts.map(p => `
            <div class="drawer-item">
                <img class="drawer-item-image" src="images/${p.local_image}" alt="${p.name}" onerror="this.src='https://via.placeholder.com/70x70/E0E5EC/415A77?text=N'">
                <div class="drawer-item-info">
                    <p class="drawer-item-brand">${p.brand}</p>
                    <p class="drawer-item-name">${p.name}</p>
                    <p class="drawer-item-price">${p.price_display}</p>
                </div>
            </div>`).join('');
    }

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

    // HEARTS
    function toggleHeart(button, productId) {
        const wasHearted = isHearted(productId);
        if (wasHearted) {
            removeHeartedItem(productId);
            button.classList.remove('active');
            button.setAttribute('aria-label', 'Add to favorites');
        } else {
            saveHeartedItem(productId);
            button.classList.add('active');
            button.setAttribute('aria-label', 'Remove from favorites');
            bumpBadge('favorites', 1);
            createHeartParticles(button);
        }
        updateStats();
    }

    function updateHeartButtons() {
        document.querySelectorAll('.heart-button').forEach(button => {
            const productId = button.dataset.productId;
            if (productId) {
                const hearted = isHearted(productId);
                button.classList.toggle('active', hearted);
                button.setAttribute('aria-label', hearted ? 'Remove from favorites' : 'Add to favorites');
            }
        });
    }

    function createHeartParticles(button) {
        const rect = button.getBoundingClientRect();
        const centerX = rect.left + rect.width / 2;
        const centerY = rect.top + rect.height / 2;
        for (let i = 0; i < 8; i++) {
            const particle = document.createElement('div');
            particle.style.cssText = `position:fixed;left:${centerX}px;top:${centerY}px;width:6px;height:6px;background:var(--heart);border-radius:50%;pointer-events:none;z-index:9999;`;
            document.body.appendChild(particle);
            const angle = (i / 8) * Math.PI * 2;
            const distance = 30 + Math.random() * 20;
            const dx = Math.cos(angle) * distance;
            const dy = Math.sin(angle) * distance;
            particle.animate([
                { transform: 'translate(-50%, -50%) scale(1)', opacity: 1 },
                { transform: `translate(calc(-50% + ${dx}px), calc(-50% + ${dy}px)) scale(0)`, opacity: 0 }
            ], { duration: 377, easing: 'cubic-bezier(0.34, 1.56, 0.64, 1)' }).onfinish = () => particle.remove();
        }
        if (typeof navigator !== 'undefined' && typeof navigator.vibrate === 'function') {
            try { navigator.vibrate(50); } catch {}
        }
    }

    // DRAWERS - Fixed event listener lifecycle
    let lastFocusedDrawerTrigger = null;

    function openDrawer(kind) {
        const overlay = document.querySelector('.drawer-overlay');
        const drawer = document.getElementById(`${kind}-drawer`);
        const button = document.getElementById(`${kind}-btn`);
        if (!drawer) return;
        lastFocusedDrawerTrigger = button;
        if (overlay) overlay.classList.add('active');
        drawer.classList.add('active');
        drawer.removeAttribute('hidden');
        drawer.setAttribute('aria-hidden', 'false');
        if (button) button.setAttribute('aria-expanded', 'true');
        document.body.style.overflow = 'hidden';
        clearBadge(kind);
        if (kind === 'favorites') renderFavoritesDrawer();
        if (kind === 'orders') renderOrdersDrawer();
        setTimeout(() => { drawer.querySelector('.drawer-close')?.focus(); }, 100);
        const boundHandler = trapFocus.bind(null, drawer);
        drawerHandlers.set(drawer, boundHandler);
        drawer.addEventListener('keydown', boundHandler);
    }

    function closeDrawers() {
        document.querySelector('.drawer-overlay')?.classList.remove('active');
        document.querySelectorAll('.drawer').forEach(drawer => {
            drawer.classList.remove('active');
            drawer.setAttribute('hidden', '');
            drawer.setAttribute('aria-hidden', 'true');
            const handler = drawerHandlers.get(drawer);
            if (handler) { drawer.removeEventListener('keydown', handler); drawerHandlers.delete(drawer); }
        });
        document.body.style.overflow = '';
        document.getElementById('favorites-btn')?.setAttribute('aria-expanded', 'false');
        document.getElementById('orders-btn')?.setAttribute('aria-expanded', 'false');
        if (lastFocusedDrawerTrigger) { lastFocusedDrawerTrigger.focus(); lastFocusedDrawerTrigger = null; }
    }

    function trapFocus(drawer, event) {
        if (event.key !== 'Tab') return;
        const focusable = drawer.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }

    function setupDrawers() {
        document.getElementById('favorites-btn')?.addEventListener('click', () => openDrawer('favorites'));
        document.getElementById('orders-btn')?.addEventListener('click', () => openDrawer('orders'));
        document.querySelector('.drawer-overlay')?.addEventListener('click', closeDrawers);
        document.querySelectorAll('.drawer-close').forEach(btn => btn.addEventListener('click', closeDrawers));
        document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeDrawers(); });
    }

    // LOADING STATE
    function showLoadingState() {
        const content = document.getElementById('gallery-content');
        if (!content) return;
        content.innerHTML = `
            <div class="loading-state">
                <div class="loading-state__icon">⚓</div>
                <p class="loading-state__text">Curating your navy collection...</p>
            </div>`;
    }

    // Initialize footer hearts from localStorage before gallery load
    function initFooterHearts() {
        const hearts = getHeartedItems();
        const footerHearted = document.getElementById('footer-hearted');
        if (footerHearted) footerHearted.textContent = hearts.size;
    }

    // BOOT
    async function boot() {
        initFooterHearts();
        showLoadingState();
        gallery = await loadGallery();
        if (!gallery) { console.error('Failed to load gallery'); renderErrorState(); return; }
        renderPhilosophy();
        renderGallery();
        renderOutfits();
        updateStats();
        renderBadges();
        setupDrawers();
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
    else boot();
})();
