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
                            <span class="status-label">${getItemStatus(product.id) || 'No status'}</span>
                          </button>
                          <div class="status-menu" role="menu" aria-hidden="true">
                            ${['wishlisted','considering','ordered','purchased','owned','returned'].map(st => `
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
        document.querySelectorAll('.product-card').forEach(card => {
            card.addEventListener('mousemove', (e) => {
                const rect = card.getBoundingClientRect();
                const x = (e.clientX - rect.left) / rect.width;
                const y = (e.clientY - rect.top) / rect.height;
                
                const tiltX = (y - 0.5) * 8;
                const tiltY = (x - 0.5) * -8;
                
                card.style.transform = `
                    translateY(-12px) 
                    perspective(1000px) 
                    rotateX(${tiltX}deg) 
                    rotateY(${tiltY}deg)
                    scale(1.02)
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
