/**
 * ═══════════════════════════════════════════════════════════════════════════
 * THE EVENING EDIT — JavaScript
 * ═══════════════════════════════════════════════════════════════════════════
 */

(async function() {
    'use strict';

    const HEARTS_KEY = 'jill_evening_hearts';
    let gallery = null;

    // ═══════════════════════════════════════════════════════════════════════
    // DATA LOADING
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

    // ═══════════════════════════════════════════════════════════════════════
    // HEARTS / FAVORITES
    // ═══════════════════════════════════════════════════════════════════════

    function getHeartedItems() {
        const hearted = localStorage.getItem(HEARTS_KEY);
        return hearted ? new Set(JSON.parse(hearted)) : new Set();
    }

    function saveHeartedItems(heartedSet) {
        localStorage.setItem(HEARTS_KEY, JSON.stringify(Array.from(heartedSet)));
    }

    function toggleHeart(productId) {
        const heartedItems = getHeartedItems();
        if (heartedItems.has(productId)) {
            heartedItems.delete(productId);
        } else {
            heartedItems.add(productId);
        }
        saveHeartedItems(heartedItems);
        updateHeartButtons();
    }

    function updateHeartButtons() {
        const heartedItems = getHeartedItems();
        document.querySelectorAll('.heart-button').forEach(button => {
            const productId = button.dataset.productId;
            if (heartedItems.has(productId)) {
                button.classList.add('hearted');
                button.innerHTML = '❤️';
            } else {
                button.classList.remove('hearted');
                button.innerHTML = '🤍';
            }
        });
    }

    // ═══════════════════════════════════════════════════════════════════════
    // RENDERING
    // ═══════════════════════════════════════════════════════════════════════

    function renderProductCard(product) {
        const heartedItems = getHeartedItems();
        const isHearted = heartedItems.has(product.id);

        return `
            <article class="product-card" data-product-id="${product.id}">
                <button class="heart-button" data-product-id="${product.id}" aria-label="Add to favorites">
                    ${isHearted ? '❤️' : '🤍'}
                </button>
                <a href="${product.product_url}" target="_blank" rel="noopener" class="product-card__link">
                    <div class="product-card__image-container">
                        <img 
                            src="./images/${product.local_image}" 
                            alt="${product.name} by ${product.brand}"
                            class="product-card__image"
                            loading="lazy"
                        >
                        ${product.badge ? `<span class="product-card__badge">${product.badge}</span>` : ''}
                    </div>
                </a>
                <div class="product-card__content">
                    <span class="product-card__brand">${product.brand}</span>
                    <h3 class="product-card__name">${product.name}</h3>
                    <p class="product-card__description">${product.description}</p>
                    <footer class="product-card__footer">
                        <span class="product-card__price">${product.price_display}</span>
                        <a href="${product.product_url}" target="_blank" rel="noopener" class="product-card__cta">
                            View
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

        // Populate grids
        gallery.products.forEach(product => {
            const grid = grids[product.category];
            if (grid) {
                grid.innerHTML += renderProductCard(product);
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

        // Update total investment
        updateTotalInvestment();
    }

    function updateTotalInvestment() {
        const el = document.getElementById('total-investment');
        if (el && gallery && gallery.products) {
            const total = gallery.products.reduce((sum, p) => sum + (p.price || 0), 0);
            el.textContent = `$${total.toLocaleString()}`;
        }
    }

    // ═══════════════════════════════════════════════════════════════════════
    // INITIALIZATION
    // ═══════════════════════════════════════════════════════════════════════

    document.addEventListener('DOMContentLoaded', async () => {
        gallery = await loadGallery();
        if (gallery) {
            renderGallery();
        }
    });

})();
