/**
 * For Jill — The Curated Wardrobe
 * Hearts, microdelights, and perfect experiences
 *
 * Every interaction feels intentional.
 * Every animation tells a story.
 * With love, from Kagami.
 */

// ═══════════════════════════════════════════════════════════════
// PRODUCT DATA
// ═══════════════════════════════════════════════════════════════

const products = {
    // Knitwear
    'jenni-kayne-cocoon': { 
        name: 'Cashmere Cocoon Cardigan', 
        brand: 'Jenni Kayne',
        price: 445, 
        image: 'images/jenni-kayne-cocoon.jpg',
        category: 'knitwear'
    },
    'la-ligne-marin': { 
        name: 'Marin Stripe Sweater', 
        brand: 'La Ligne',
        price: 395, 
        image: 'images/la-ligne-marin.jpg',
        category: 'knitwear'
    },
    'white-warren-wrap': { 
        name: 'Cashmere Travel Wrap', 
        brand: 'White + Warren',
        price: 398, 
        image: 'images/white-warren-wrap.jpg',
        category: 'knitwear'
    },
    
    // Essentials
    'saint-james-breton': { 
        name: 'Minquidame Breton Shirt', 
        brand: 'Saint James',
        price: 115, 
        image: 'images/saint-james-breton.jpg',
        category: 'essentials'
    },
    'cuyana-silk': { 
        name: 'Silk Leather Cuff Shirt', 
        brand: 'Cuyana',
        price: 178, 
        image: 'images/cuyana-silk.jpg',
        category: 'essentials'
    },
    'barbour-beadnell': { 
        name: 'Cropped Beadnell Waxed Jacket', 
        brand: 'Barbour',
        price: 425, 
        image: 'images/barbour-beadnell.jpg',
        category: 'outerwear'
    },
    'jenni-kayne-blazer': { 
        name: 'Brentwood Blazer', 
        brand: 'Jenni Kayne',
        price: 495, 
        image: 'images/jenni-kayne-blazer.jpg',
        category: 'essentials'
    },
    'margaux-demi': { 
        name: 'The Demi Ballet Flat', 
        brand: 'Margaux',
        price: 275, 
        image: 'images/margaux-demi.jpg',
        category: 'footwear'
    },
    
    // Eyewear
    'cubitts-bespoke': { 
        name: 'Bespoke Spectacles', 
        brand: 'Cubitts',
        price: 350, 
        image: 'images/cubitts-bespoke.jpg',
        category: 'eyewear'
    },
    'ahlem-custom': { 
        name: 'One of One Custom Frames', 
        brand: 'AHLEM',
        price: 650, 
        image: 'images/ahlem-custom.jpg',
        category: 'eyewear'
    },
    
    // Jewelry
    'catbird-threadbare': { 
        name: 'Threadbare Ring', 
        brand: 'Catbird',
        price: 48, 
        image: 'images/catbird-threadbare.jpg',
        category: 'jewelry'
    },
    'wwake-earrings': { 
        name: 'Sapphire Eclipse Earrings', 
        brand: 'WWAKE',
        price: 590, 
        image: 'images/wwake-earrings.jpg',
        category: 'jewelry'
    },
    'mounser-polaris': { 
        name: 'Polaris Earrings', 
        brand: 'MOUNSER',
        price: 295, 
        image: 'images/mounser-polaris.jpg',
        category: 'jewelry'
    },
    
    // Accessories
    'sezane-scarf': { 
        name: 'Eli Scarf', 
        brand: 'Sézane',
        price: 115, 
        image: 'images/sezane-scarf.jpg',
        category: 'accessories'
    }
};

// Outfit combinations
const outfits = {
    weekend: {
        name: 'Weekend',
        desc: 'Green Lake mornings',
        items: ['saint-james-breton', 'jenni-kayne-cocoon', 'margaux-demi', 'cubitts-bespoke', 'catbird-threadbare']
    },
    workday: {
        name: 'Workday',
        desc: 'Polished confidence',
        items: ['cuyana-silk', 'jenni-kayne-blazer', 'margaux-demi', 'ahlem-custom', 'wwake-earrings']
    },
    evening: {
        name: 'Evening',
        desc: 'Dinner reservations',
        items: ['la-ligne-marin', 'mounser-polaris', 'sezane-scarf', 'margaux-demi', 'ahlem-custom']
    },
    outdoor: {
        name: 'Outdoor',
        desc: 'PNW adventures',
        items: ['saint-james-breton', 'barbour-beadnell', 'white-warren-wrap', 'cubitts-bespoke', 'catbird-threadbare']
    }
};

// ═══════════════════════════════════════════════════════════════
// HEARTS SYSTEM — API-first with localStorage fallback
// ═══════════════════════════════════════════════════════════════

// Legacy keys for migration
const HEARTS_KEY = 'jill_wardrobe_hearts';
const HEARTS_HISTORY_KEY = 'jill_wardrobe_hearts_history';

// Use CommerceClient if available (loaded from shared/commerce-client.js)
const useCommerceClient = typeof CommerceClient !== 'undefined';

/**
 * Initialize commerce client (call on DOMContentLoaded)
 */
async function initCommerceClient() {
    if (useCommerceClient) {
        await CommerceClient.initialize();
        // Migrate old hearts to new system
        _migrateOldHearts();
        console.log('✅ Commerce client initialized');
    }
}

/**
 * Migrate old localStorage hearts to new system
 */
function _migrateOldHearts() {
    if (!useCommerceClient) return;
    try {
        const oldHearts = localStorage.getItem(HEARTS_KEY);
        if (oldHearts) {
            const hearts = JSON.parse(oldHearts);
            hearts.forEach(productId => {
                const product = products[productId];
                if (product && !CommerceClient.isWishlisted(productId)) {
                    CommerceClient.addToWishlist({
                        product_id: productId,
                        brand: product.brand,
                        name: product.name,
                        price: product.price,
                        image: product.image,
                        source_gallery: 'wardrobe',
                    });
                }
            });
            // Clear old storage after migration
            // localStorage.removeItem(HEARTS_KEY);
            console.log(`Migrated ${hearts.length} hearts to commerce client`);
        }
    } catch (e) {
        console.warn('Hearts migration failed:', e);
    }
}

/**
 * Get hearted items — uses CommerceClient or localStorage
 */
function getHeartedItems() {
    if (useCommerceClient) {
        return CommerceClient.getWishlist();
    }
    try {
        const stored = localStorage.getItem(HEARTS_KEY);
        return stored ? JSON.parse(stored) : [];
    } catch (e) {
        return [];
    }
}

/**
 * Save hearted items to localStorage (legacy)
 */
function saveHeartedItems(items) {
    try {
        localStorage.setItem(HEARTS_KEY, JSON.stringify(items));
        // Also save to history with timestamp for future recommendations
        const history = getHeartsHistory();
        history.push({
            items: [...items],
            timestamp: Date.now()
        });
        // Keep last 50 snapshots
        if (history.length > 50) history.shift();
        localStorage.setItem(HEARTS_HISTORY_KEY, JSON.stringify(history));
    } catch (e) {
        console.warn('Could not save hearts:', e);
    }
}

/**
 * Get hearts history for recommendation engine
 */
function getHeartsHistory() {
    try {
        const stored = localStorage.getItem(HEARTS_HISTORY_KEY);
        return stored ? JSON.parse(stored) : [];
    } catch (e) {
        return [];
    }
}

/**
 * Toggle heart on a product — uses CommerceClient or localStorage
 */
async function toggleHeart(productId) {
    const product = products[productId];
    
    if (useCommerceClient) {
        const wasHearted = CommerceClient.isWishlisted(productId);
        await CommerceClient.toggleWishlist({
            product_id: productId,
            brand: product?.brand,
            name: product?.name,
            price: product?.price,
            image: product?.image,
            source_gallery: 'wardrobe',
        });
        updateAllHeartStates();
        updateNavHeartsCount();
        updateHeartedPanel();
        return !wasHearted;
    }
    
    // Fallback to localStorage
    const hearts = getHeartedItems();
    const index = hearts.indexOf(productId);
    
    if (index === -1) {
        hearts.push(productId);
    } else {
        hearts.splice(index, 1);
    }
    
    saveHeartedItems(hearts);
    updateAllHeartStates();
    updateNavHeartsCount();
    updateHeartedPanel();
    
    return index === -1;
}

/**
 * Check if a product is hearted
 */
function isHearted(productId) {
    if (useCommerceClient) {
        return CommerceClient.isWishlisted(productId);
    }
    return getHeartedItems().includes(productId);
}

/**
 * Update all heart button states on the page
 */
function updateAllHeartStates() {
    document.querySelectorAll('.product-heart').forEach(btn => {
        const productId = btn.dataset.productId;
        if (isHearted(productId)) {
            btn.classList.add('hearted');
        } else {
            btn.classList.remove('hearted');
        }
    });
}

/**
 * Update hearts count in nav
 */
function updateNavHeartsCount() {
    const count = getHeartedItems().length;
    const countEl = document.querySelector('.nav-hearts-count');
    if (countEl) {
        countEl.textContent = count;
        
        // Micro-animation on change
        countEl.style.transform = 'scale(1.3)';
        setTimeout(() => {
            countEl.style.transform = 'scale(1)';
        }, 150);
    }
}

// ═══════════════════════════════════════════════════════════════
// HEARTED PANEL
// ═══════════════════════════════════════════════════════════════

/**
 * Toggle the hearted panel
 */
function toggleHeartedPanel() {
    const panel = document.querySelector('.hearted-panel');
    const overlay = document.querySelector('.panel-overlay');
    
    if (panel && overlay) {
        const isOpen = panel.classList.contains('open');
        
        if (isOpen) {
            panel.classList.remove('open');
            overlay.classList.remove('visible');
            document.body.style.overflow = '';
        } else {
            panel.classList.add('open');
            overlay.classList.add('visible');
            document.body.style.overflow = 'hidden';
            updateHeartedPanel();
        }
    }
}

/**
 * Update hearted panel content
 */
function updateHeartedPanel() {
    const content = document.querySelector('.hearted-panel-content');
    const footer = document.querySelector('.hearted-panel-footer');
    if (!content) return;
    
    const hearts = getHeartedItems();
    
    if (hearts.length === 0) {
        content.innerHTML = `
            <div class="hearted-empty">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
                </svg>
                <p>Your hearted pieces will appear here. Tap the heart on any item to save it.</p>
            </div>
        `;
        if (footer) footer.style.display = 'none';
        return;
    }
    
    let total = 0;
    let html = '';
    
    hearts.forEach(productId => {
        const product = products[productId];
        if (!product) return;
        
        total += product.price;
        html += `
            <div class="hearted-item" data-product-id="${productId}">
                <img src="${product.image}" alt="${product.name}" class="hearted-item-image" onerror="this.style.background='var(--blush)'">
                <div class="hearted-item-info">
                    <div class="hearted-item-name">${product.name}</div>
                    <div class="hearted-item-price">$${product.price}</div>
                </div>
                <button class="hearted-item-remove" aria-label="Remove from hearts">×</button>
            </div>
        `;
    });
    
    content.innerHTML = html;
    
    // Add remove handlers
    content.querySelectorAll('.hearted-item-remove').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const item = btn.closest('.hearted-item');
            const productId = item.dataset.productId;
            
            // Animate out
            item.style.transform = 'translateX(100%)';
            item.style.opacity = '0';
            
            setTimeout(() => {
                toggleHeart(productId);
            }, 200);
        });
    });
    
    // Update footer
    if (footer) {
        footer.style.display = 'block';
        const totalEl = footer.querySelector('.hearted-total-value');
        if (totalEl) {
            animateNumber(totalEl, total);
        }
    }
}

// ═══════════════════════════════════════════════════════════════
// OUTFIT BUILDER
// ═══════════════════════════════════════════════════════════════

let currentOutfit = 'weekend';

/**
 * Render outfit items with staggered animation
 */
function renderOutfit(outfitName) {
    currentOutfit = outfitName;
    const container = document.getElementById('outfit-items');
    const outfit = outfits[outfitName];
    
    if (!container || !outfit) return;
    
    // Fade out
    container.style.opacity = '0';
    container.style.transform = 'translateY(8px)';
    
    setTimeout(() => {
        container.innerHTML = '';
        let total = 0;
        
        outfit.items.forEach((id, index) => {
            const product = products[id];
            if (!product) return;
            
            total += product.price;
            
            const item = document.createElement('div');
            item.className = 'outfit-item';
            item.dataset.productId = id;
            item.style.opacity = '0';
            item.style.transform = 'translateY(12px) scale(0.95)';
            item.innerHTML = `
                <img src="${product.image}" alt="${product.name}" class="outfit-item-image" onerror="this.style.background='var(--blush)'">
                <div class="outfit-item-name">${product.brand}</div>
                <div class="outfit-item-price">$${product.price}</div>
            `;
            
            // Click to heart
            item.addEventListener('click', () => {
                const hearted = toggleHeart(id);
                if (hearted) {
                    // Mini celebration
                    item.style.transform = 'translateY(-8px) scale(1.05)';
                    setTimeout(() => {
                        item.style.transform = '';
                    }, 300);
                }
            });
            
            container.appendChild(item);
            
            // Staggered reveal
            setTimeout(() => {
                item.style.transition = 'all 0.35s cubic-bezier(0.22, 1, 0.36, 1)';
                item.style.opacity = '1';
                item.style.transform = 'translateY(0) scale(1)';
            }, 50 * index);
        });
        
        // Reveal container
        container.style.transition = 'all 0.25s ease';
        container.style.opacity = '1';
        container.style.transform = 'translateY(0)';
        
        // Animate total
        const totalEl = document.getElementById('outfit-total-price');
        if (totalEl) {
            animateNumber(totalEl, total);
        }
        
    }, 180);
}

/**
 * Initialize outfit builder
 */
function initOutfitBuilder() {
    const presets = document.querySelectorAll('.outfit-preset');
    
    presets.forEach(preset => {
        preset.addEventListener('click', () => {
            // Update active state with micro-animation
            presets.forEach(p => {
                p.classList.remove('active');
                p.style.transform = '';
            });
            preset.classList.add('active');
            
            // Small bounce
            preset.style.transform = 'scale(0.98)';
            setTimeout(() => {
                preset.style.transform = '';
            }, 100);
            
            // Render new outfit
            const outfitName = preset.dataset.outfit;
            renderOutfit(outfitName);
        });
    });
    
    // Initial render
    renderOutfit('weekend');
}

// ═══════════════════════════════════════════════════════════════
// ANIMATIONS & UTILITIES
// ═══════════════════════════════════════════════════════════════

/**
 * Animate a number with count-up effect
 */
function animateNumber(element, target, prefix = '$') {
    const duration = 500;
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

/**
 * Scroll reveal with IntersectionObserver
 */
function initScrollReveal() {
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
                observer.unobserve(entry.target);
            }
        });
    }, {
        threshold: 0.1,
        rootMargin: '0px 0px -40px 0px'
    });
    
    document.querySelectorAll('.reveal').forEach(el => {
        observer.observe(el);
    });
}

/**
 * Smooth navigation scrolling
 */
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

/**
 * Navigation behavior on scroll
 */
function initNavScroll() {
    const nav = document.querySelector('.nav');
    if (!nav) return;
    
    let lastScroll = 0;
    let ticking = false;
    
    window.addEventListener('scroll', () => {
        if (!ticking) {
            requestAnimationFrame(() => {
                const currentScroll = window.scrollY;
                
                if (currentScroll > 100) {
                    // Subtle fade when scrolling down
                    nav.style.opacity = currentScroll > lastScroll ? '0.85' : '1';
                    nav.style.transform = `translateX(-50%) scale(${currentScroll > lastScroll ? 0.98 : 1})`;
                } else {
                    nav.style.opacity = '1';
                    nav.style.transform = 'translateX(-50%) scale(1)';
                }
                
                lastScroll = currentScroll;
                ticking = false;
            });
            ticking = true;
        }
    }, { passive: true });
}

/**
 * Add heart buttons to all product cards
 */
function initProductHearts() {
    document.querySelectorAll('.product-card').forEach(card => {
        const container = card.querySelector('.product-image-container');
        if (!container) return;
        
        // Get product ID from data attribute or generate from name
        const name = card.querySelector('.product-name')?.textContent || '';
        const brand = card.querySelector('.product-brand')?.textContent || '';
        
        // Find matching product ID
        let productId = null;
        for (const [id, product] of Object.entries(products)) {
            if (product.name === name || 
                (brand.toLowerCase().includes(product.brand.toLowerCase()) && 
                 name.toLowerCase().includes(product.name.split(' ')[0].toLowerCase()))) {
                productId = id;
                break;
            }
        }
        
        // Try matching by brand and partial name
        if (!productId) {
            for (const [id, product] of Object.entries(products)) {
                if (brand.toLowerCase().includes(product.brand.toLowerCase())) {
                    productId = id;
                    break;
                }
            }
        }
        
        if (!productId) return;
        
        // Create heart button
        const heartBtn = document.createElement('button');
        heartBtn.className = 'product-heart';
        heartBtn.dataset.productId = productId;
        heartBtn.setAttribute('aria-label', 'Add to favorites');
        heartBtn.innerHTML = `
            <svg viewBox="0 0 24 24">
                <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
            </svg>
        `;
        
        // Set initial state
        if (isHearted(productId)) {
            heartBtn.classList.add('hearted');
        }
        
        // Click handler
        heartBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            toggleHeart(productId);
        });
        
        container.appendChild(heartBtn);
    });
}

/**
 * Make product cards easy to open:
 * - click anywhere on the card (except hearts/links/buttons)
 * - hit Enter/Space when focused
 */
function initProductCardNavigation() {
    document.querySelectorAll('.product-card[data-href]').forEach(card => {
        const href = card.dataset.href;
        if (!href) return;

        // accessibility
        card.setAttribute('tabindex', '0');
        card.setAttribute('role', 'link');
        card.setAttribute('aria-label', `Open product page`);

        const shouldIgnore = (el) => {
            if (!el) return false;
            return Boolean(el.closest('a, button, .product-heart, .hearted-item-remove'));
        };

        card.addEventListener('click', (e) => {
            if (shouldIgnore(e.target)) return;
            window.open(href, '_blank', 'noopener');
        });

        card.addEventListener('keydown', (e) => {
            if (e.key !== 'Enter' && e.key !== ' ') return;
            if (shouldIgnore(e.target)) return;
            e.preventDefault();
            window.open(href, '_blank', 'noopener');
        });
    });
}

/**
 * Create nav hearts counter
 */
function initNavHearts() {
    const nav = document.querySelector('.nav');
    if (!nav) return;
    
    const heartsEl = document.createElement('div');
    heartsEl.className = 'nav-hearts';
    heartsEl.innerHTML = `
        <svg viewBox="0 0 24 24">
            <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
        </svg>
        <span class="nav-hearts-count">${getHeartedItems().length}</span>
    `;
    
    heartsEl.addEventListener('click', toggleHeartedPanel);
    nav.appendChild(heartsEl);
}

/**
 * Create hearted panel
 */
function initHeartedPanel() {
    // Create overlay
    const overlay = document.createElement('div');
    overlay.className = 'panel-overlay';
    overlay.addEventListener('click', toggleHeartedPanel);
    document.body.appendChild(overlay);
    
    // Create panel
    const panel = document.createElement('div');
    panel.className = 'hearted-panel';
    panel.innerHTML = `
        <div class="hearted-panel-header">
            <div class="hearted-panel-title">
                <svg viewBox="0 0 24 24">
                    <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
                </svg>
                Your Favorites
            </div>
            <button class="hearted-panel-close" aria-label="Close panel">×</button>
        </div>
        <div class="hearted-panel-content"></div>
        <div class="hearted-panel-footer">
            <div class="hearted-total">
                <span class="hearted-total-label">Total</span>
                <span class="hearted-total-value">$0</span>
            </div>
        </div>
    `;
    
    // Close button
    panel.querySelector('.hearted-panel-close').addEventListener('click', toggleHeartedPanel);
    
    document.body.appendChild(panel);
    
    // Initial content
    updateHeartedPanel();
}

// ═══════════════════════════════════════════════════════════════
// MICRODELIGHTS
// ═══════════════════════════════════════════════════════════════

/**
 * Add subtle hover effects to philosophy cards
 */
function initPhilosophyCards() {
    document.querySelectorAll('.philosophy-item').forEach(card => {
        card.addEventListener('mouseenter', () => {
            // Subtle tilt based on mouse position
            card.style.transition = 'transform 0.1s ease';
        });
        
        card.addEventListener('mousemove', (e) => {
            const rect = card.getBoundingClientRect();
            const x = (e.clientX - rect.left) / rect.width;
            const y = (e.clientY - rect.top) / rect.height;
            
            const tiltX = (y - 0.5) * 4;
            const tiltY = (x - 0.5) * -4;
            
            card.style.transform = `translateY(-8px) perspective(1000px) rotateX(${tiltX}deg) rotateY(${tiltY}deg)`;
        });
        
        card.addEventListener('mouseleave', () => {
            card.style.transition = 'transform 0.4s cubic-bezier(0.22, 1, 0.36, 1)';
            // Return to original stagger position
            const index = Array.from(card.parentElement.children).indexOf(card);
            const staggers = [0, 24, -12, 32];
            card.style.transform = `translateY(${staggers[index % 4]}px)`;
        });
    });
}

/**
 * Product card 3D tilt effect
 */
function initProductCardTilt() {
    document.querySelectorAll('.product-card').forEach(card => {
        card.addEventListener('mousemove', (e) => {
            const rect = card.getBoundingClientRect();
            const x = (e.clientX - rect.left) / rect.width;
            const y = (e.clientY - rect.top) / rect.height;
            
            const tiltX = (y - 0.5) * 6;
            const tiltY = (x - 0.5) * -6;
            
            card.style.transform = `translateY(-12px) perspective(1000px) rotateX(${tiltX}deg) rotateY(${tiltY}deg)`;
        });
        
        card.addEventListener('mouseleave', () => {
            card.style.transform = '';
        });
    });
}

// ═══════════════════════════════════════════════════════════════
// INITIALIZATION
// ═══════════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', async () => {
    // Initialize commerce client first
    await initCommerceClient();
    
    // Core functionality
    initProductHearts();
    initProductCardNavigation();
    initNavHearts();
    initHeartedPanel();
    initOutfitBuilder();
    
    // Navigation & scroll
    initSmoothScroll();
    initNavScroll();
    initScrollReveal();
    
    // Microdelights
    initPhilosophyCards();
    initProductCardTilt();
    
    // Log commerce state for debugging
    console.log('💕 Jill\'s Wardrobe initialized');
    if (useCommerceClient) {
        console.log('Commerce state:', CommerceClient.getState());
    } else {
        console.log('Hearts history:', getHeartsHistory());
    }
});

// ═══════════════════════════════════════════════════════════════
// REDUCED MOTION
// ═══════════════════════════════════════════════════════════════

if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    document.documentElement.style.setProperty('--dur-instant', '0ms');
    document.documentElement.style.setProperty('--dur-quick', '0ms');
    document.documentElement.style.setProperty('--dur-normal', '0ms');
    document.documentElement.style.setProperty('--dur-slow', '0ms');
    document.documentElement.style.setProperty('--dur-glacial', '0ms');
    document.documentElement.style.setProperty('--dur-epic', '0ms');
}

// ═══════════════════════════════════════════════════════════════
// RECOMMENDATION ENGINE (Future feature scaffold)
// ═══════════════════════════════════════════════════════════════

/**
 * Analyze hearts history for future recommendations
 * This data persists and can inform future curations
 */
function analyzePreferences() {
    const hearts = getHeartedItems();
    const history = getHeartsHistory();
    
    // Category preferences
    const categories = {};
    hearts.forEach(id => {
        const product = products[id];
        if (product) {
            categories[product.category] = (categories[product.category] || 0) + 1;
        }
    });
    
    // Brand preferences
    const brands = {};
    hearts.forEach(id => {
        const product = products[id];
        if (product) {
            brands[product.brand] = (brands[product.brand] || 0) + 1;
        }
    });
    
    // Price range
    const prices = hearts.map(id => products[id]?.price || 0).filter(p => p > 0);
    const avgPrice = prices.length ? prices.reduce((a, b) => a + b, 0) / prices.length : 0;
    
    return {
        topCategories: Object.entries(categories).sort((a, b) => b[1] - a[1]).slice(0, 3),
        topBrands: Object.entries(brands).sort((a, b) => b[1] - a[1]).slice(0, 3),
        avgPrice: Math.round(avgPrice),
        totalHearted: hearts.length,
        historySnapshots: history.length
    };
}

// Export for console debugging
window.jillWardrobe = {
    products,
    outfits,
    getHeartedItems,
    analyzePreferences,
    getHeartsHistory
};
