/**
 * ═══════════════════════════════════════════════════════════════════════════
 * THE MIDNIGHT ATELIER — JavaScript
 * ═══════════════════════════════════════════════════════════════════════════
 * 
 * Features:
 * - Loads gallery data from JSON
 * - Renders product cards
 * - Heart functionality with local storage
 * - Dynamic total investment calculation
 */

(async function() {
    'use strict';

    // ═══════════════════════════════════════════════════════════════════════
    // GALLERY DATA
    // ═══════════════════════════════════════════════════════════════════════

    let gallery = null;
    const HEARTS_KEY = 'jill_narnia_hearts';

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

    // ═══════════════════════════════════════════════════════════════════════
    // HEARTS (Local Storage)
    // ═══════════════════════════════════════════════════════════════════════

    function getHearts() {
        try {
            return JSON.parse(localStorage.getItem(HEARTS_KEY)) || [];
        } catch {
            return [];
        }
    }

    function saveHearts(hearts) {
        localStorage.setItem(HEARTS_KEY, JSON.stringify(hearts));
    }

    function toggleHeart(productId) {
        const hearts = getHearts();
        const index = hearts.indexOf(productId);
        
        if (index === -1) {
            hearts.push(productId);
        } else {
            hearts.splice(index, 1);
        }
        
        saveHearts(hearts);
        return hearts.includes(productId);
    }

    function isHearted(productId) {
        return getHearts().includes(productId);
    }

    // ═══════════════════════════════════════════════════════════════════════
    // PRODUCT CARD RENDERING
    // ═══════════════════════════════════════════════════════════════════════

    function createProductCard(product) {
        const card = document.createElement('article');
        card.className = `product-card${product.is_centerpiece ? ' product-card--centerpiece' : ''}`;
        card.dataset.productId = product.id;

        const hearted = isHearted(product.id);
        const priceDisplay = product.price_display || `$${product.price}`;
        
        // Determine image source
        let imageHtml = '';
        if (product.local_image) {
            imageHtml = `<img class="product-card__image" src="./images/${product.local_image}" alt="${product.name}" loading="lazy">`;
        } else {
            // Placeholder with brand initial
            const initial = product.brand ? product.brand[0] : '✦';
            imageHtml = `<div class="product-card__placeholder">${initial}</div>`;
        }

        card.innerHTML = `
            <a href="${product.product_url}" class="product-card__link-overlay" target="_blank" rel="noopener" aria-label="View ${product.name} on ${product.brand} website"></a>
            <div class="product-card__media">
                ${imageHtml}
                ${product.badge ? `<span class="product-card__badge">${product.badge}</span>` : ''}
                <button class="product-card__heart ${hearted ? 'is-hearted' : ''}" aria-label="Add to favorites">
                    <span class="heart-icon">${hearted ? '♥' : '♡'}</span>
                </button>
            </div>
            <div class="product-card__body">
                <header class="product-card__header">
                    <span class="product-card__brand">${product.brand}</span>
                    <h3 class="product-card__name">${product.name}</h3>
                </header>
                <p class="product-card__description">${product.description}</p>
                ${product.maker ? `<p class="product-card__maker">${product.maker}</p>` : ''}
                <footer class="product-card__footer">
                    <span class="product-card__price">${priceDisplay}</span>
                    <a href="${product.product_url}" class="product-card__cta" target="_blank" rel="noopener">View piece ↗</a>
                </footer>
            </div>
        `;

        // Heart button event
        const heartBtn = card.querySelector('.product-card__heart');
        heartBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            
            const isNowHearted = toggleHeart(product.id);
            heartBtn.classList.toggle('is-hearted', isNowHearted);
            heartBtn.querySelector('.heart-icon').textContent = isNowHearted ? '♥' : '♡';
            
            updateTotalInvestment();
        });

        return card;
    }

    // ═══════════════════════════════════════════════════════════════════════
    // RENDER PRODUCTS
    // ═══════════════════════════════════════════════════════════════════════

    function renderProducts() {
        if (!gallery || !gallery.products) return;

        const categories = ['dresses', 'pants', 'footwear', 'accessories'];

        categories.forEach(category => {
            const grid = document.querySelector(`.products-grid[data-category="${category}"]`);
            if (!grid) return;

            const products = gallery.products.filter(p => p.category === category);
            grid.innerHTML = '';
            
            products.forEach(product => {
                const card = createProductCard(product);
                grid.appendChild(card);
            });
        });
    }

    // ═══════════════════════════════════════════════════════════════════════
    // TOTAL INVESTMENT
    // ═══════════════════════════════════════════════════════════════════════

    function updateTotalInvestment() {
        if (!gallery || !gallery.products) return;

        const hearts = getHearts();
        let total = 0;

        // If no hearts, show full gallery total
        if (hearts.length === 0) {
            total = gallery.products.reduce((sum, p) => sum + (p.price || 0), 0);
        } else {
            // Show only hearted items total
            total = gallery.products
                .filter(p => hearts.includes(p.id))
                .reduce((sum, p) => sum + (p.price || 0), 0);
        }

        const totalEl = document.getElementById('total-investment');
        if (totalEl) {
            totalEl.textContent = `$${total.toLocaleString()}`;
        }
    }

    // ═══════════════════════════════════════════════════════════════════════
    // SCROLL ANIMATIONS (Intersection Observer)
    // ═══════════════════════════════════════════════════════════════════════

    function initScrollAnimations() {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('is-visible');
                    observer.unobserve(entry.target);
                }
            });
        }, {
            threshold: 0.1,
            rootMargin: '0px 0px -50px 0px'
        });

        document.querySelectorAll('.philosophy-card, .collection-header').forEach(el => {
            observer.observe(el);
        });
    }

    // ═══════════════════════════════════════════════════════════════════════
    // INITIALIZATION
    // ═══════════════════════════════════════════════════════════════════════

    async function init() {
        await loadGallery();
        renderProducts();
        updateTotalInvestment();
        initScrollAnimations();

        console.log('🌙 The Midnight Atelier initialized');
        console.log(`📦 ${gallery?.products?.length || 0} pieces loaded`);
        console.log(`💖 ${getHearts().length} items hearted`);
    }

    // Start
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
