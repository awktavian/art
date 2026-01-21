/**
 * Le Fabuleux Destin d'Amélie — Gallery Script
 * French cinema warmth meets Japanese artisan soul
 */

// === State ===
let galleryData = null;
let currentCategory = 'all';

// === DOM Ready ===
document.addEventListener('DOMContentLoaded', async () => {
    await loadGalleryData();
    initializeGallery();
    initializeNavigation();
    initializeModal();
    initializeScrollReveal();
    initializeParallax();
    initializeDoubleTapToHeart();
    initializeTouchFeedback();
});

// === Data Loading ===
async function loadGalleryData() {
    try {
        const response = await fetch('./data/gallery.json');
        galleryData = await response.json();
        console.log('🎬 Loaded gallery:', galleryData.meta.name);
        console.log(`   ${galleryData.products.length} products curated for ${galleryData.meta.recipient}`);
    } catch (error) {
        console.error('Failed to load gallery data:', error);
        galleryData = { products: [], outfit_formulas: [], meta: {} };
    }
}

// === Gallery Initialization ===
function initializeGallery() {
    renderProducts();
    renderOutfitFormulas();
    renderLikedItems();
    updateFooterStats();
}

// === Product Rendering ===
function renderProducts() {
    const categories = ['les-pantalons', 'le-style-parisien', 'lartisanat-japonais', 'les-accessoires'];
    
    categories.forEach(category => {
        const grid = document.querySelector(`.products-grid[data-category="${category}"]`);
        if (!grid) return;
        
        const products = galleryData.products.filter(p => p.category === category);
        grid.innerHTML = products.map(product => createProductCard(product)).join('');
    });
}

function createProductCard(product) {
    const isCenterpiece = product.is_centerpiece;
    const isLiked = getLikedStatus(product.id) || product.liked;
    const imagePath = product.local_image
        ? `./images/${product.local_image}`
        : '';

    const badgeHTML = product.badge
        ? `<span class="product-badge ${isLiked ? 'liked' : ''} ${isCenterpiece ? 'centerpiece-badge' : ''}">${product.badge}</span>`
        : '';

    const heartHTML = `<button class="heart-btn ${isLiked ? 'active' : ''}"
        onclick="event.stopPropagation(); toggleHeart('${product.id}')"
        aria-label="${isLiked ? 'Remove from favorites' : 'Add to favorites'}">
        <span class="heart-icon">${isLiked ? '❤️' : '🤍'}</span>
    </button>`;

    const imageHTML = imagePath
        ? `<img class="product-image" src="${imagePath}" alt="${product.name}" loading="lazy">`
        : `<div class="product-image placeholder-image">${getPlaceholderEmoji(product.category)}</div>`;

    // Direct link to product - clickable!
    const productLink = product.product_url
        ? `<a href="${product.product_url}" target="_blank" rel="noopener" class="product-link" onclick="event.stopPropagation()">Voir →</a>`
        : '';

    return `
        <article class="product-card ${isCenterpiece ? 'centerpiece' : ''} ${isLiked ? 'is-liked' : ''} reveal"
                 data-product-id="${product.id}"
                 onclick="openProductModal('${product.id}')">
            <div class="product-image-container">
                ${imageHTML}
                ${badgeHTML}
                ${heartHTML}
            </div>
            <div class="product-content">
                <span class="product-brand">${product.brand}</span>
                <h3 class="product-name">${product.name}</h3>
                <p class="product-description">${product.description}</p>
                <div class="product-footer">
                    <span class="product-price">${product.price_display}</span>
                    ${productLink}
                </div>
            </div>
        </article>
    `;
}

function getPlaceholderEmoji(category) {
    const emojiMap = {
        'les-pantalons': '👖',
        'le-style-parisien': '🇫🇷',
        'lartisanat-japonais': '🇯🇵',
        'les-accessoires': '✨'
    };
    return emojiMap[category] || '🎨';
}

// === Outfit Formulas ===
function renderOutfitFormulas() {
    const grid = document.querySelector('.formulas-grid');
    if (!grid || !galleryData.outfit_formulas) return;
    
    grid.innerHTML = galleryData.outfit_formulas.map(formula => `
        <article class="formula-card reveal">
            <h3 class="formula-name">${formula.name}</h3>
            <p class="formula-description">${formula.description}</p>
            <div class="formula-items">
                ${formula.products.map(productId => {
                    const product = galleryData.products.find(p => p.id === productId);
                    return product 
                        ? `<span class="formula-item">${product.name}</span>`
                        : '';
                }).join('')}
            </div>
            <div class="formula-mood">✦ ${formula.mood}</div>
        </article>
    `).join('');
}

// === Liked Items ===
function renderLikedItems() {
    const grid = document.querySelector('.liked-grid');
    const section = document.querySelector('.liked-section');
    if (!grid || !section) return;

    const likedIds = getLikedItems();
    const likedProducts = galleryData.products.filter(p =>
        likedIds.includes(p.id) || p.liked
    );

    if (likedProducts.length === 0) {
        // Hide the section if no liked items
        section.style.display = 'none';
        return;
    }

    // Show the section and render
    section.style.display = 'block';
    grid.innerHTML = likedProducts.map(product => createProductCard(product)).join('');

    // Re-run scroll reveal on new items
    const revealElements = grid.querySelectorAll('.reveal:not(.visible)');
    revealElements.forEach(el => el.classList.add('visible'));
}

// === Navigation ===
function initializeNavigation() {
    const navLinks = document.querySelectorAll('.nav-categories a');
    
    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const category = link.dataset.category;
            
            // Update active state
            navLinks.forEach(l => l.classList.remove('active'));
            link.classList.add('active');
            
            // Filter or scroll
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
    
    // Update nav on scroll
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
function initializeModal() {
    const modal = document.getElementById('product-modal');
    const backdrop = modal.querySelector('.modal-backdrop');
    const closeBtn = modal.querySelector('.modal-close');

    backdrop.addEventListener('click', closeModal);
    closeBtn.addEventListener('click', closeModal);

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeModal();
        // Arrow key navigation
        if (modal.classList.contains('active')) {
            if (e.key === 'ArrowRight') navigateModal(1);
            if (e.key === 'ArrowLeft') navigateModal(-1);
        }
    });

    // Initialize swipe for modal on mobile
    initializeModalSwipe();
}

function navigateModal(direction) {
    const modal = document.getElementById('product-modal');
    const currentId = modal.dataset.currentProductId;
    if (!currentId) return;

    const currentIndex = galleryData.products.findIndex(p => p.id === currentId);
    const newIndex = (currentIndex + direction + galleryData.products.length) % galleryData.products.length;
    openProductModal(galleryData.products[newIndex].id);
}

function openProductModal(productId) {
    const product = galleryData.products.find(p => p.id === productId);
    if (!product) return;

    const modal = document.getElementById('product-modal');

    // Store current product ID for navigation
    modal.dataset.currentProductId = productId;

    // Populate modal
    modal.querySelector('.modal-brand').textContent = product.brand;
    modal.querySelector('.modal-title').textContent = product.name;
    modal.querySelector('.modal-description').textContent = product.description;
    modal.querySelector('.modal-price').textContent = product.price_display;
    modal.querySelector('.modal-link').href = product.product_url || '#';
    
    // Image
    const imgContainer = modal.querySelector('.modal-image');
    if (product.local_image) {
        imgContainer.src = `./images/${product.local_image}`;
        imgContainer.alt = product.name;
    } else {
        imgContainer.src = '';
        imgContainer.alt = '';
    }
    
    // Meta
    modal.querySelector('.modal-maker').innerHTML = `<strong>Maker:</strong> ${product.maker || 'Unknown'}`;
    modal.querySelector('.modal-material').innerHTML = `<strong>Material:</strong> ${product.material || 'N/A'}`;
    modal.querySelector('.modal-size').innerHTML = `<strong>Size Required:</strong> ${product.size_required || 'Check listing'}`;
    
    // Badges
    const badgesContainer = modal.querySelector('.modal-badges');
    let badgesHTML = '';
    if (product.badge) {
        badgesHTML += `<span class="product-badge">${product.badge}</span>`;
    }
    if (product.liked) {
        badgesHTML += `<span class="product-badge liked">❤️ Jill's Pick</span>`;
    }
    badgesContainer.innerHTML = badgesHTML;
    
    // Show modal
    modal.classList.add('active');
    document.body.style.overflow = 'hidden';
}

function closeModal() {
    const modal = document.getElementById('product-modal');
    modal.classList.remove('active');
    document.body.style.overflow = '';
}

// === Scroll Reveal ===
function initializeScrollReveal() {
    const revealElements = document.querySelectorAll('.reveal');
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry, index) => {
            if (entry.isIntersecting) {
                // Stagger the animations
                setTimeout(() => {
                    entry.target.classList.add('visible');
                }, index * 50);
                observer.unobserve(entry.target);
            }
        });
    }, {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    });
    
    revealElements.forEach(el => observer.observe(el));
}

// === Parallax ===
function initializeParallax() {
    const hero = document.querySelector('.hero');
    
    window.addEventListener('scroll', () => {
        const scrolled = window.pageYOffset;
        const heroHeight = hero.offsetHeight;
        
        if (scrolled < heroHeight) {
            const opacity = 1 - (scrolled / heroHeight) * 0.5;
            const translateY = scrolled * 0.3;
            
            hero.style.opacity = opacity;
            hero.querySelector('.hero-content').style.transform = `translateY(${translateY}px)`;
        }
    });
}

// === Hearts Wishlist System with localStorage ===
const LIKED_STORAGE_KEY = 'amelie-liked-products';

function getLikedItems() {
    try {
        return JSON.parse(localStorage.getItem(LIKED_STORAGE_KEY)) || [];
    } catch {
        return [];
    }
}

function saveLikedItems(likedIds) {
    localStorage.setItem(LIKED_STORAGE_KEY, JSON.stringify(likedIds));
}

function getLikedStatus(productId) {
    return getLikedItems().includes(productId);
}

function toggleHeart(productId) {
    const product = galleryData.products.find(p => p.id === productId);
    if (!product) return;

    const likedIds = getLikedItems();
    const isCurrentlyLiked = likedIds.includes(productId);

    if (isCurrentlyLiked) {
        // Remove from liked
        const index = likedIds.indexOf(productId);
        likedIds.splice(index, 1);
    } else {
        // Add to liked
        likedIds.push(productId);
    }

    saveLikedItems(likedIds);

    // Update UI with animation
    const card = document.querySelector(`[data-product-id="${productId}"]`);
    if (card) {
        const heartBtn = card.querySelector('.heart-btn');
        const heartIcon = card.querySelector('.heart-icon');

        if (isCurrentlyLiked) {
            card.classList.remove('is-liked');
            heartBtn.classList.remove('active');
            heartIcon.textContent = '🤍';
            heartBtn.setAttribute('aria-label', 'Add to favorites');
        } else {
            card.classList.add('is-liked');
            heartBtn.classList.add('active');
            heartIcon.textContent = '❤️';
            heartBtn.setAttribute('aria-label', 'Remove from favorites');

            // Microdelight: Confetti burst animation
            createHeartBurst(heartBtn);
        }
    }

    // Re-render liked section
    renderLikedItems();

    // Update footer count
    updateFooterStats();

    console.log(`${!isCurrentlyLiked ? '❤️' : '💔'} ${product.name}`);
}

// Microdelight: Heart burst animation
function createHeartBurst(element) {
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

// Update footer with dynamic stats
function updateFooterStats() {
    const footer = document.getElementById('footer-details');
    if (!footer || !galleryData) return;

    const totalProducts = galleryData.products.length;
    const likedCount = getLikedItems().length;

    footer.textContent = `${totalProducts} pieces • ${likedCount > 0 ? `${likedCount} ❤️ • ` : ''}Paris meets Tokyo • Sizing: Pants 6, Tops XS-S, Shoes US 8`;
}

// === Utility Functions ===
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// === Double-Tap to Heart (Mobile) ===
function initializeDoubleTapToHeart() {
    const DOUBLE_TAP_DELAY = 300; // ms
    let lastTapTime = 0;
    let lastTapTarget = null;

    // Use event delegation on the gallery container
    document.addEventListener('touchend', (e) => {
        const card = e.target.closest('.product-card');
        if (!card) return;

        const currentTime = Date.now();
        const productId = card.dataset.productId;

        // Check for double tap on the same card
        if (lastTapTarget === productId && currentTime - lastTapTime < DOUBLE_TAP_DELAY) {
            // Double tap detected!
            e.preventDefault();
            e.stopPropagation();

            // Trigger heart with visual feedback
            toggleHeart(productId);

            // Show big heart animation on the image
            showDoubleTapHeart(card);

            // Reset
            lastTapTime = 0;
            lastTapTarget = null;
        } else {
            lastTapTime = currentTime;
            lastTapTarget = productId;
        }
    }, { passive: false });

    // Prevent context menu on long press (mobile)
    document.addEventListener('contextmenu', (e) => {
        if (e.target.closest('.product-card')) {
            e.preventDefault();
        }
    });
}

// Big heart animation on double-tap (Instagram-style)
function showDoubleTapHeart(card) {
    const imageContainer = card.querySelector('.product-image-container');
    if (!imageContainer) return;

    // Create the big heart overlay
    const heartOverlay = document.createElement('div');
    heartOverlay.className = 'double-tap-heart';
    heartOverlay.innerHTML = '❤️';

    imageContainer.appendChild(heartOverlay);

    // Remove after animation
    setTimeout(() => heartOverlay.remove(), 1000);
}

// === Touch Feedback for Mobile ===
function initializeTouchFeedback() {
    // Add active state on touch
    document.addEventListener('touchstart', (e) => {
        const card = e.target.closest('.product-card');
        if (card) {
            card.classList.add('touch-active');
        }

        const link = e.target.closest('.product-link, .nav-categories a');
        if (link) {
            link.classList.add('touch-active');
        }
    }, { passive: true });

    document.addEventListener('touchend', () => {
        // Remove all touch-active classes
        document.querySelectorAll('.touch-active').forEach(el => {
            el.classList.remove('touch-active');
        });
    }, { passive: true });

    document.addEventListener('touchcancel', () => {
        document.querySelectorAll('.touch-active').forEach(el => {
            el.classList.remove('touch-active');
        });
    }, { passive: true });

    // Improve scroll performance
    document.addEventListener('touchmove', () => {
        document.querySelectorAll('.touch-active').forEach(el => {
            el.classList.remove('touch-active');
        });
    }, { passive: true });
}

// === Swipe Navigation for Modal (Mobile) ===
let touchStartX = 0;
let touchEndX = 0;

function initializeModalSwipe() {
    const modal = document.getElementById('product-modal');
    if (!modal) return;

    modal.addEventListener('touchstart', (e) => {
        touchStartX = e.changedTouches[0].screenX;
    }, { passive: true });

    modal.addEventListener('touchend', (e) => {
        touchEndX = e.changedTouches[0].screenX;
        handleModalSwipe();
    }, { passive: true });
}

function handleModalSwipe() {
    const swipeThreshold = 50;
    const diff = touchStartX - touchEndX;

    if (Math.abs(diff) < swipeThreshold) return;

    // Get current product index
    const modal = document.getElementById('product-modal');
    const currentId = modal.dataset.currentProductId;
    const currentIndex = galleryData.products.findIndex(p => p.id === currentId);

    if (diff > 0) {
        // Swipe left - next product
        const nextIndex = (currentIndex + 1) % galleryData.products.length;
        openProductModal(galleryData.products[nextIndex].id);
    } else {
        // Swipe right - previous product
        const prevIndex = (currentIndex - 1 + galleryData.products.length) % galleryData.products.length;
        openProductModal(galleryData.products[prevIndex].id);
    }
}

// === Console Art ===
console.log(`
  ╔═══════════════════════════════════════════════╗
  ║                                               ║
  ║   Le Fabuleux Destin d'Amélie                 ║
  ║   ─────────────────────────────               ║
  ║                                               ║
  ║   French cinema warmth meets                  ║
  ║   Japanese artisan soul                       ║
  ║                                               ║
  ║   Pour Jill ❤️                                 ║
  ║                                               ║
  ║   📱 Double-tap to ❤️                          ║
  ║                                               ║
  ╚═══════════════════════════════════════════════╝
`);
