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
    const isLiked = product.liked;
    const imagePath = product.local_image 
        ? `./images/${product.local_image}` 
        : '';
    
    const badgeHTML = product.badge 
        ? `<span class="product-badge ${isLiked ? 'liked' : ''} ${isCenterpiece ? 'centerpiece-badge' : ''}">${product.badge}</span>` 
        : '';
    
    const heartHTML = isLiked 
        ? '<span class="product-heart">❤️</span>' 
        : '';
    
    const imageHTML = imagePath
        ? `<img class="product-image" src="${imagePath}" alt="${product.name}" loading="lazy">`
        : `<div class="product-image placeholder-image">${getPlaceholderEmoji(product.category)}</div>`;
    
    return `
        <article class="product-card ${isCenterpiece ? 'centerpiece' : ''} reveal" 
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
                    <span class="product-origin">${product.origin}</span>
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
    if (!grid) return;
    
    const likedProducts = galleryData.products.filter(p => p.liked);
    
    if (likedProducts.length === 0) {
        // Hide the section if no liked items
        const section = document.querySelector('.liked-section');
        if (section) section.style.display = 'none';
        return;
    }
    
    grid.innerHTML = likedProducts.map(product => createProductCard(product)).join('');
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
    });
}

function openProductModal(productId) {
    const product = galleryData.products.find(p => p.id === productId);
    if (!product) return;
    
    const modal = document.getElementById('product-modal');
    
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

// === Hearts Wishlist System ===
function toggleHeart(productId) {
    const product = galleryData.products.find(p => p.id === productId);
    if (!product) return;
    
    product.liked = !product.liked;
    
    // Update UI
    const card = document.querySelector(`[data-product-id="${productId}"]`);
    if (card) {
        const heartEl = card.querySelector('.product-heart');
        if (product.liked && !heartEl) {
            const container = card.querySelector('.product-image-container');
            container.insertAdjacentHTML('beforeend', '<span class="product-heart">❤️</span>');
        } else if (!product.liked && heartEl) {
            heartEl.remove();
        }
    }
    
    // Re-render liked section
    renderLikedItems();
    
    // Could save to localStorage here
    console.log(`${product.liked ? '❤️' : '💔'} ${product.name}`);
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
  ╚═══════════════════════════════════════════════╝
`);
