/**
 * Kagami Gallery Core — Unified Gallery System
 *
 * A shared component library for all Tim & Jill galleries.
 * Handles: data loading, rendering, hearts, navigation, modals, mobile interactions.
 *
 * Usage:
 *   import { KagamiGallery } from './shared/gallery/gallery-core.js';
 *   const gallery = new KagamiGallery({
 *     dataUrl: './data/gallery.json',
 *     storageKey: 'gallery-name-likes'
 *   });
 *   gallery.init();
 */

// === Configuration ===
const DEFAULT_CONFIG = {
    dataUrl: './data/gallery.json',
    imagesPath: './images/',
    storageKey: 'kagami-gallery-likes',
    doubleTapDelay: 300,
    animationDurations: {
        quick: 233,
        medium: 377,
        slow: 610
    },
    selectors: {
        gallery: '.gallery',
        productsGrid: '.products-grid',
        modal: '#product-modal',
        likedSection: '.liked-section',
        likedGrid: '.liked-grid',
        footerDetails: '#footer-details'
    }
};

// === KagamiGallery Class ===
class KagamiGallery {
    constructor(config = {}) {
        this.config = { ...DEFAULT_CONFIG, ...config };
        this.data = null;
        this.currentCategory = 'all';
        this.lastTapTime = 0;
        this.lastTapTarget = null;
    }

    // === Initialization ===
    async init() {
        await this.loadData();
        this.renderProducts();
        this.renderLikedItems();
        this.initializeNavigation();
        this.initializeModal();
        this.initializeDoubleTap();
        this.initializeTouchFeedback();
        this.initializeScrollReveal();
        this.updateFooterStats();

        console.log(`🎨 Kagami Gallery initialized: ${this.data?.meta?.name || 'Unknown'}`);
        console.log(`   ${this.data?.products?.length || 0} products for ${this.data?.meta?.recipient || 'Unknown'}`);
    }

    // === Data Loading ===
    async loadData() {
        try {
            const response = await fetch(this.config.dataUrl);
            this.data = await response.json();
        } catch (error) {
            console.error('Failed to load gallery data:', error);
            this.data = { products: [], meta: {}, categories: [] };
        }
    }

    // === Rendering ===
    renderProducts() {
        const categories = this.data.categories || [];

        categories.forEach(category => {
            const grid = document.querySelector(`${this.config.selectors.productsGrid}[data-category="${category}"]`);
            if (!grid) return;

            const products = this.data.products.filter(p => p.category === category);
            grid.innerHTML = products.map(p => this.createProductCard(p)).join('');
        });
    }

    createProductCard(product) {
        const isLiked = this.getLikedStatus(product.id) || product.liked;
        const isCenterpiece = product.is_centerpiece;
        const imagePath = product.local_image
            ? `${this.config.imagesPath}${product.local_image}`
            : '';

        const badgeHTML = product.badge
            ? `<span class="product-badge ${isCenterpiece ? 'centerpiece-badge' : ''}">${product.badge}</span>`
            : '';

        const heartHTML = `
            <button class="heart-btn ${isLiked ? 'active' : ''}"
                data-action="heart"
                data-product-id="${product.id}"
                aria-label="${isLiked ? 'Remove from favorites' : 'Add to favorites'}">
                <span class="heart-icon">${isLiked ? '❤️' : '🤍'}</span>
            </button>`;

        const imageHTML = imagePath
            ? `<img class="product-image" src="${imagePath}" alt="${product.name}" loading="lazy">`
            : `<div class="product-image placeholder-image">${this.getPlaceholderEmoji(product.category)}</div>`;

        const productLink = product.product_url
            ? `<a href="${product.product_url}" target="_blank" rel="noopener" class="product-link">View →</a>`
            : '';

        return `
            <article class="product-card ${isCenterpiece ? 'centerpiece' : ''} ${isLiked ? 'is-liked' : ''} reveal"
                     data-product-id="${product.id}">
                <div class="product-image-container">
                    ${imageHTML}
                    ${badgeHTML}
                    ${heartHTML}
                </div>
                <div class="product-content">
                    <span class="product-brand">${product.brand}</span>
                    <h3 class="product-name">${product.name}</h3>
                    <p class="product-description">${product.description || ''}</p>
                    <div class="product-footer">
                        <span class="product-price">${product.price_display || ''}</span>
                        ${productLink}
                    </div>
                </div>
            </article>
        `;
    }

    getPlaceholderEmoji(category) {
        const emojiMap = {
            'les-pantalons': '👖',
            'le-style-parisien': '🇫🇷',
            'lartisanat-japonais': '🇯🇵',
            'les-accessoires': '✨',
            'bottoms': '👖',
            'tops': '👕',
            'outerwear': '🧥',
            'footwear': '👟',
            'accessories': '✨',
            'knitwear': '🧶',
            'dresses': '👗'
        };
        return emojiMap[category] || '🎨';
    }

    // === Liked Items ===
    renderLikedItems() {
        const grid = document.querySelector(this.config.selectors.likedGrid);
        const section = document.querySelector(this.config.selectors.likedSection);
        if (!grid || !section) return;

        const likedIds = this.getLikedItems();
        const likedProducts = this.data.products.filter(p =>
            likedIds.includes(p.id) || p.liked
        );

        if (likedProducts.length === 0) {
            section.style.display = 'none';
            return;
        }

        section.style.display = 'block';
        grid.innerHTML = likedProducts.map(p => this.createProductCard(p)).join('');

        // Reveal animations
        grid.querySelectorAll('.reveal:not(.visible)').forEach(el => {
            el.classList.add('visible');
        });
    }

    // === Hearts / Likes System ===
    getLikedItems() {
        try {
            return JSON.parse(localStorage.getItem(this.config.storageKey)) || [];
        } catch {
            return [];
        }
    }

    saveLikedItems(likedIds) {
        localStorage.setItem(this.config.storageKey, JSON.stringify(likedIds));
    }

    getLikedStatus(productId) {
        return this.getLikedItems().includes(productId);
    }

    toggleHeart(productId) {
        const product = this.data.products.find(p => p.id === productId);
        if (!product) return;

        const likedIds = this.getLikedItems();
        const isCurrentlyLiked = likedIds.includes(productId);

        if (isCurrentlyLiked) {
            const index = likedIds.indexOf(productId);
            likedIds.splice(index, 1);
        } else {
            likedIds.push(productId);
        }

        this.saveLikedItems(likedIds);
        this.updateHeartUI(productId, !isCurrentlyLiked);
        this.renderLikedItems();
        this.updateFooterStats();

        console.log(`${!isCurrentlyLiked ? '❤️' : '💔'} ${product.name}`);
    }

    updateHeartUI(productId, isLiked) {
        // Update all cards with this product ID (may appear in multiple places)
        document.querySelectorAll(`[data-product-id="${productId}"]`).forEach(card => {
            const heartBtn = card.querySelector('.heart-btn');
            const heartIcon = card.querySelector('.heart-icon');

            if (isLiked) {
                card.classList.add('is-liked');
                heartBtn?.classList.add('active');
                if (heartIcon) heartIcon.textContent = '❤️';
                heartBtn?.setAttribute('aria-label', 'Remove from favorites');
                this.createHeartBurst(heartBtn);
            } else {
                card.classList.remove('is-liked');
                heartBtn?.classList.remove('active');
                if (heartIcon) heartIcon.textContent = '🤍';
                heartBtn?.setAttribute('aria-label', 'Add to favorites');
            }
        });
    }

    createHeartBurst(element) {
        if (!element) return;
        const rect = element.getBoundingClientRect();
        const hearts = ['❤️', '💕', '💗', '💖', '✨'];

        for (let i = 0; i < 8; i++) {
            const heart = document.createElement('span');
            heart.className = 'heart-particle';
            heart.textContent = hearts[Math.floor(Math.random() * hearts.length)];
            heart.style.cssText = `
                position: fixed;
                left: ${rect.left + rect.width / 2}px;
                top: ${rect.top + rect.height / 2}px;
                font-size: 16px;
                pointer-events: none;
                z-index: 9999;
                animation: heartBurst 0.8s ease-out forwards;
                --angle: ${(i * 45) + (Math.random() * 20 - 10)}deg;
                --distance: ${40 + Math.random() * 30}px;
            `;
            document.body.appendChild(heart);
            setTimeout(() => heart.remove(), 800);
        }
    }

    // === Double-Tap to Heart ===
    initializeDoubleTap() {
        document.addEventListener('touchend', (e) => {
            const card = e.target.closest('.product-card');
            if (!card) return;

            // Don't trigger on heart button clicks
            if (e.target.closest('.heart-btn') || e.target.closest('.product-link')) return;

            const currentTime = Date.now();
            const productId = card.dataset.productId;

            if (this.lastTapTarget === productId &&
                currentTime - this.lastTapTime < this.config.doubleTapDelay) {
                e.preventDefault();
                e.stopPropagation();
                this.toggleHeart(productId);
                this.showDoubleTapHeart(card);
                this.lastTapTime = 0;
                this.lastTapTarget = null;
            } else {
                this.lastTapTime = currentTime;
                this.lastTapTarget = productId;
            }
        }, { passive: false });

        // Prevent context menu
        document.addEventListener('contextmenu', (e) => {
            if (e.target.closest('.product-card')) {
                e.preventDefault();
            }
        });
    }

    showDoubleTapHeart(card) {
        const container = card.querySelector('.product-image-container');
        if (!container) return;

        const heartOverlay = document.createElement('div');
        heartOverlay.className = 'double-tap-heart';
        heartOverlay.innerHTML = '❤️';
        container.appendChild(heartOverlay);
        setTimeout(() => heartOverlay.remove(), 1000);
    }

    // === Touch Feedback ===
    initializeTouchFeedback() {
        document.addEventListener('touchstart', (e) => {
            const card = e.target.closest('.product-card');
            if (card) card.classList.add('touch-active');

            const link = e.target.closest('.product-link, .nav-categories a');
            if (link) link.classList.add('touch-active');
        }, { passive: true });

        ['touchend', 'touchcancel', 'touchmove'].forEach(event => {
            document.addEventListener(event, () => {
                document.querySelectorAll('.touch-active').forEach(el => {
                    el.classList.remove('touch-active');
                });
            }, { passive: true });
        });
    }

    // === Navigation ===
    initializeNavigation() {
        const navLinks = document.querySelectorAll('.nav-categories a');

        navLinks.forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const category = link.dataset.category;

                navLinks.forEach(l => l.classList.remove('active'));
                link.classList.add('active');

                if (category === 'all') {
                    document.querySelectorAll('.category-section').forEach(s => {
                        s.style.display = 'block';
                    });
                } else {
                    const target = document.getElementById(category);
                    if (target) {
                        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    }
                }
            });
        });

        // Scroll spy
        const sections = document.querySelectorAll('.category-section');
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const id = entry.target.id;
                    navLinks.forEach(link => {
                        link.classList.toggle('active', link.dataset.category === id);
                    });
                }
            });
        }, { threshold: 0.3 });

        sections.forEach(section => observer.observe(section));
    }

    // === Modal ===
    initializeModal() {
        const modal = document.querySelector(this.config.selectors.modal);
        if (!modal) return;

        // Click handlers
        modal.querySelector('.modal-backdrop')?.addEventListener('click', () => this.closeModal());
        modal.querySelector('.modal-close')?.addEventListener('click', () => this.closeModal());

        // Keyboard
        document.addEventListener('keydown', (e) => {
            if (!modal.classList.contains('active')) return;
            if (e.key === 'Escape') this.closeModal();
            if (e.key === 'ArrowRight') this.navigateModal(1);
            if (e.key === 'ArrowLeft') this.navigateModal(-1);
        });

        // Card click to open
        document.addEventListener('click', (e) => {
            const card = e.target.closest('.product-card');
            if (!card) return;
            if (e.target.closest('.heart-btn') || e.target.closest('.product-link')) return;
            this.openModal(card.dataset.productId);
        });

        // Mobile swipe
        let touchStartX = 0;
        modal.addEventListener('touchstart', (e) => {
            touchStartX = e.changedTouches[0].screenX;
        }, { passive: true });

        modal.addEventListener('touchend', (e) => {
            const diff = touchStartX - e.changedTouches[0].screenX;
            if (Math.abs(diff) > 50) {
                this.navigateModal(diff > 0 ? 1 : -1);
            }
        }, { passive: true });
    }

    openModal(productId) {
        const product = this.data.products.find(p => p.id === productId);
        if (!product) return;

        const modal = document.querySelector(this.config.selectors.modal);
        modal.dataset.currentProductId = productId;

        // Populate
        const setContent = (selector, content) => {
            const el = modal.querySelector(selector);
            if (el) el.textContent = content;
        };

        setContent('.modal-brand', product.brand);
        setContent('.modal-title', product.name);
        setContent('.modal-description', product.description || '');
        setContent('.modal-price', product.price_display || '');

        const link = modal.querySelector('.modal-link');
        if (link) link.href = product.product_url || '#';

        const img = modal.querySelector('.modal-image');
        if (img && product.local_image) {
            img.src = `${this.config.imagesPath}${product.local_image}`;
            img.alt = product.name;
        }

        // Meta
        const setMeta = (selector, label, value) => {
            const el = modal.querySelector(selector);
            if (el) el.innerHTML = `<strong>${label}:</strong> ${value || 'N/A'}`;
        };

        setMeta('.modal-maker', 'Maker', product.maker);
        setMeta('.modal-material', 'Material', product.material);
        setMeta('.modal-size', 'Size', product.size_required);

        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
    }

    closeModal() {
        const modal = document.querySelector(this.config.selectors.modal);
        modal?.classList.remove('active');
        document.body.style.overflow = '';
    }

    navigateModal(direction) {
        const modal = document.querySelector(this.config.selectors.modal);
        const currentId = modal?.dataset.currentProductId;
        if (!currentId) return;

        const currentIndex = this.data.products.findIndex(p => p.id === currentId);
        const newIndex = (currentIndex + direction + this.data.products.length) % this.data.products.length;
        this.openModal(this.data.products[newIndex].id);
    }

    // === Scroll Reveal ===
    initializeScrollReveal() {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach((entry, index) => {
                if (entry.isIntersecting) {
                    setTimeout(() => {
                        entry.target.classList.add('visible');
                    }, index * 50);
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.1, rootMargin: '0px 0px -50px 0px' });

        document.querySelectorAll('.reveal').forEach(el => observer.observe(el));
    }

    // === Footer Stats ===
    updateFooterStats() {
        const footer = document.querySelector(this.config.selectors.footerDetails);
        if (!footer || !this.data) return;

        const total = this.data.products.length;
        const liked = this.getLikedItems().length;
        const recipient = this.data.meta?.recipient || 'You';

        const likedText = liked > 0 ? ` • ${liked} ❤️` : '';
        footer.textContent = `${total} pieces${likedText} • Curated for ${recipient}`;
    }
}

// === Export ===
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { KagamiGallery, DEFAULT_CONFIG };
}

// Global export for non-module usage
window.KagamiGallery = KagamiGallery;
