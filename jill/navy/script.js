/**
 * True Blue — Jill's Navy Wardrobe
 * Navy isn't safe—it's signature.
 */

// ═══════════════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════════════

let gallery = null;
const HEARTS_KEY = 'jill_navy_hearts_v1';
const SHARED_HEARTS_KEYS = ['jill_wardrobe_hearts_v1', 'jill_evening_hearts_v1', 'jill_navy_hearts_v1'];

// ═══════════════════════════════════════════════════════════════════════
// LOCAL STORAGE HELPERS (shared with other galleries)
// ═══════════════════════════════════════════════════════════════════════

function getHeartedItems() {
    // Merge hearts from all galleries for a unified experience
    const allHearts = new Set();
    SHARED_HEARTS_KEYS.forEach(key => {
        try {
            const hearts = JSON.parse(localStorage.getItem(key) || '[]');
            hearts.forEach(h => allHearts.add(h));
        } catch (e) {
            console.warn(`Failed to load hearts from ${key}:`, e);
        }
    });
    return allHearts;
}

function saveHeartedItem(productId) {
    const hearts = getHeartedItems();
    hearts.add(productId);
    // Save to current gallery's key
    localStorage.setItem(HEARTS_KEY, JSON.stringify([...hearts]));
}

function removeHeartedItem(productId) {
    const hearts = getHeartedItems();
    hearts.delete(productId);
    localStorage.setItem(HEARTS_KEY, JSON.stringify([...hearts]));
}

function isHearted(productId) {
    return getHeartedItems().has(productId);
}

// ═══════════════════════════════════════════════════════════════════════
// GALLERY LOADING
// ═══════════════════════════════════════════════════════════════════════

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

function renderPhilosophy() {
    const grid = document.getElementById('philosophy-grid');
    if (!gallery?.philosophy || !grid) return;
    
    grid.innerHTML = gallery.philosophy.map((p, i) => `
        <div class="philosophy-card" style="animation-delay: ${i * 100}ms">
            <div class="philosophy-icon">${p.icon}</div>
            <h3 class="philosophy-title">${p.title}</h3>
            <p class="philosophy-text">${p.description}</p>
        </div>
    `).join('');
}

function renderGallery() {
    const content = document.getElementById('gallery-content');
    if (!gallery?.products || !content) return;
    
    // Group products by category
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
                 onclick="handleProductClick(event, '${product.product_url}')">
            <div class="product-image-wrap">
                <img class="product-image" 
                     src="images/${product.local_image}" 
                     alt="${product.name}"
                     loading="lazy"
                     onerror="this.src='https://via.placeholder.com/400x500/E0E5EC/415A77?text=Navy'">
                ${product.badge ? `<span class="product-badge ${badgeClass}">${product.badge}</span>` : ''}
                <button class="heart-button ${hearted ? 'active' : ''}" 
                        onclick="toggleHeart(event, '${product.id}')"
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
        createHeartParticles(button);
    }
    
    updateFavoritesCount();
    updateFavoritesDrawer();
    updateStats();
};

window.handleProductClick = function(event, url) {
    // Don't navigate if clicking heart button
    if (event.target.closest('.heart-button')) return;
    if (url) window.open(url, '_blank', 'noopener');
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
// DRAWERS
// ═══════════════════════════════════════════════════════════════════════

function updateFavoritesCount() {
    const count = getHeartedItems().size;
    const badge = document.getElementById('favorites-count');
    if (badge) {
        badge.textContent = count;
        badge.style.display = count > 0 ? 'inline' : 'none';
    }
}

function updateFavoritesDrawer() {
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

function setupDrawers() {
    // Favorites
    const favBtn = document.getElementById('favorites-btn');
    const favOverlay = document.getElementById('favorites-overlay');
    const favDrawer = document.getElementById('favorites-drawer');
    const favClose = document.getElementById('favorites-close');
    
    const openFavorites = () => {
        favOverlay?.classList.add('active');
        favDrawer?.classList.add('active');
        updateFavoritesDrawer();
    };
    
    const closeFavorites = () => {
        favOverlay?.classList.remove('active');
        favDrawer?.classList.remove('active');
    };
    
    favBtn?.addEventListener('click', openFavorites);
    favOverlay?.addEventListener('click', closeFavorites);
    favClose?.addEventListener('click', closeFavorites);
    
    // Orders
    const ordersBtn = document.getElementById('orders-btn');
    const ordersOverlay = document.getElementById('orders-overlay');
    const ordersDrawer = document.getElementById('orders-drawer');
    const ordersClose = document.getElementById('orders-close');
    
    const openOrders = () => {
        ordersOverlay?.classList.add('active');
        ordersDrawer?.classList.add('active');
    };
    
    const closeOrders = () => {
        ordersOverlay?.classList.remove('active');
        ordersDrawer?.classList.remove('active');
    };
    
    ordersBtn?.addEventListener('click', openOrders);
    ordersOverlay?.addEventListener('click', closeOrders);
    ordersClose?.addEventListener('click', closeOrders);
    
    // ESC key closes all drawers
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeFavorites();
            closeOrders();
        }
    });
}

// ═══════════════════════════════════════════════════════════════════════
// INITIALIZATION
// ═══════════════════════════════════════════════════════════════════════

async function init() {
    gallery = await loadGallery();
    
    if (!gallery) {
        console.error('Failed to load gallery');
        return;
    }
    
    renderPhilosophy();
    renderGallery();
    renderOutfits();
    updateStats();
    updateFavoritesCount();
    setupDrawers();
    
    console.log('🔵 True Blue loaded — Navy is her signature');
}

// Run on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
