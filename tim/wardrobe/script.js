/**
 * The Curator's Wardrobe — Tim
 * Interactive gallery with outfit builder
 *
 * craft(x) → ∞ always
 */

(function() {
    'use strict';

    // ═══════════════════════════════════════════════════════════════
    // OUTFIT DATA
    // ═══════════════════════════════════════════════════════════════

    const outfitFormulas = {
        greenlake: {
            name: 'Green Lake Morning',
            vibe: 'Thoughtful weekend wandering',
            items: [
                { name: 'Howlin\' Fair Isle', price: 116, category: 'Sweater', sale: true, image: 'images/howlin-fairisle.jpg' },
                { name: 'orSlow French Work', price: 225, category: 'Pants', image: 'images/orslow-french.jpg' },
                { name: 'Moonstar Alweather', price: 240, category: 'Footwear', image: 'images/moonstar-alweather.jpg' },
                { name: 'Anonymous Ism', price: 30, category: 'Socks', image: 'images/anonymous-ism.jpg' }
            ]
        },
        creative: {
            name: 'Creative Professional',
            vibe: 'Serious but not stuffy',
            items: [
                { name: 'Gitman Girard', price: 320, category: 'Shirt', image: 'images/gitman-girard.jpg' },
                { name: 'EG Fatigue Pant', price: 324, category: 'Pants', image: 'images/eg-fatigue.jpg' },
                { name: 'Paraboot Michael', price: 475, category: 'Footwear', image: 'images/paraboot-michael.jpg' },
                { name: 'Kapital Bandana', price: 43, category: 'Accessory', image: 'images/kapital-bandana.jpg' }
            ]
        },
        hidden: {
            name: 'Hidden Personality',
            vibe: 'Respectable with a secret',
            items: [
                { name: 'Brain Dead Tee', price: 54, category: 'Base', image: 'images/brain-dead-gits.jpg' },
                { name: 'Arpenteur Travail', price: 195, category: 'Layer', image: 'images/arpenteur-travail.jpg' },
                { name: 'Gramicci G-Pant', price: 88, category: 'Pants', image: 'images/gramicci-gpant.jpg' },
                { name: 'Kapital GOGH', price: 72, category: 'Secret', image: 'images/kapital-vangogh.jpg' }
            ]
        },
        pattern: {
            name: 'Pattern Maximalist',
            vibe: 'I know what I\'m doing',
            items: [
                { name: 'Kardo Ikat', price: 130, category: 'Statement', image: 'images/kardo-ikat.jpg' },
                { name: 'EG Loiter Jacket', price: 297, category: 'Layer', sale: true, image: 'images/eg-loiter.jpg' },
                { name: 'orSlow French Work', price: 225, category: 'Pants', image: 'images/orslow-french.jpg' },
                { name: 'Danner Mountain', price: 470, category: 'Footwear', image: 'images/danner-mountain.jpg' }
            ]
        }
    };

    // ═══════════════════════════════════════════════════════════════
    // STATE
    // ═══════════════════════════════════════════════════════════════

    let currentOutfit = 'greenlake';

    // ═══════════════════════════════════════════════════════════════
    // OUTFIT BUILDER
    // ═══════════════════════════════════════════════════════════════

    function initOutfitBuilder() {
        const presets = document.querySelectorAll('.outfit-preset');
        const itemsContainer = document.getElementById('outfit-items');
        const totalPrice = document.getElementById('outfit-total-price');

        if (!presets.length || !itemsContainer || !totalPrice) return;

        // Render initial outfit
        renderOutfit(currentOutfit);

        // Preset click handlers
        presets.forEach(preset => {
            preset.addEventListener('click', () => {
                const outfitKey = preset.dataset.outfit;
                if (outfitKey === currentOutfit) return;

                // Update active state and aria-pressed
                presets.forEach(p => {
                    p.classList.remove('active');
                    p.setAttribute('aria-pressed', 'false');
                });
                preset.classList.add('active');
                preset.setAttribute('aria-pressed', 'true');

                // Animate out, then in
                itemsContainer.style.opacity = '0';
                itemsContainer.style.transform = 'translateY(10px)';

                setTimeout(() => {
                    currentOutfit = outfitKey;
                    renderOutfit(outfitKey);

                    // Animate in
                    requestAnimationFrame(() => {
                        itemsContainer.style.opacity = '1';
                        itemsContainer.style.transform = 'translateY(0)';
                    });
                }, 233); // Fibonacci timing
            });
        });
    }

    function renderOutfit(outfitKey) {
        const outfit = outfitFormulas[outfitKey];
        const itemsContainer = document.getElementById('outfit-items');
        const totalPrice = document.getElementById('outfit-total-price');

        if (!outfit || !itemsContainer || !totalPrice) return;

        // Clear existing items
        itemsContainer.innerHTML = '';

        // Calculate total
        const total = outfit.items.reduce((sum, item) => sum + item.price, 0);

        // Create item cards with staggered animation
        outfit.items.forEach((item, index) => {
            const itemEl = document.createElement('div');
            itemEl.className = 'outfit-item';
            itemEl.style.opacity = '0';
            itemEl.style.transform = 'translateY(20px) scale(0.95)';
            itemEl.style.transition = `all 377ms cubic-bezier(0.22, 1, 0.36, 1) ${index * 89}ms`;

            // Category label for accessibility
            const categoryLabels = {
                'Sweater': '🧶', 'Pants': '👖', 'Footwear': '👟', 'Socks': '🧦',
                'Shirt': '👔', 'Accessory': '🎀', 'Base': '👕', 'Layer': '🧥',
                'Secret': '✨', 'Statement': '🎨'
            };

            const saleTag = item.sale ? '<span class="outfit-item-sale">Sale</span>' : '';

            itemEl.innerHTML = `
                <div class="outfit-item-image-wrap">
                    <img src="${item.image}" alt="${item.name}" class="outfit-item-image" loading="lazy">
                    <span class="outfit-item-category">${categoryLabels[item.category] || '👕'}</span>
                    ${saleTag}
                </div>
                <div class="outfit-item-details">
                    <div class="outfit-item-name">${item.name}</div>
                    <div class="outfit-item-price">${item.sale ? '<span class="sale-price">' : ''}$${item.price}${item.sale ? '</span>' : ''}</div>
                </div>
            `;

            // Add hover sound effect simulation (visual feedback)
            itemEl.addEventListener('mouseenter', () => {
                itemEl.style.transform = 'translateY(-8px) scale(1.02)';
            });
            itemEl.addEventListener('mouseleave', () => {
                itemEl.style.transform = 'translateY(0) scale(1)';
            });

            itemsContainer.appendChild(itemEl);

            // Trigger animation with spring effect
            requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                    itemEl.style.opacity = '1';
                    itemEl.style.transform = 'translateY(0) scale(1)';
                });
            });
        });

        // Animate total price change with spring
        animateNumber(totalPrice, total);
    }

    function animateNumber(element, target) {
        const prefix = '$';
        const current = parseInt(element.textContent.replace(/[^0-9]/g, '')) || 0;
        const diff = target - current;
        const duration = 610; // Fibonacci
        const steps = 20;
        const increment = diff / steps;
        let step = 0;

        function update() {
            step++;
            const value = Math.round(current + (increment * step));
            element.textContent = prefix + value.toLocaleString();

            if (step < steps) {
                requestAnimationFrame(update);
            } else {
                element.textContent = prefix + target.toLocaleString();
            }
        }

        requestAnimationFrame(update);
    }

    // ═══════════════════════════════════════════════════════════════
    // PRODUCT CARD NAVIGATION
    // ═══════════════════════════════════════════════════════════════

    function initProductCards() {
        const cards = document.querySelectorAll('.product-card[data-href]');

        cards.forEach(card => {
            card.addEventListener('click', (e) => {
                // Don't navigate if clicking on the CTA button directly
                if (e.target.closest('.product-cta')) return;

                const href = card.dataset.href;
                if (href) {
                    window.open(href, '_blank', 'noopener');
                }
            });

            // Keyboard accessibility
            card.setAttribute('tabindex', '0');
            card.setAttribute('role', 'article');

            // Build accessible label from card content
            const brand = card.querySelector('.product-brand')?.textContent || '';
            const name = card.querySelector('.product-name')?.textContent || '';
            const price = card.querySelector('.product-price')?.textContent || '';
            card.setAttribute('aria-label', `${brand} ${name}, ${price}. Click to view product in new window.`);

            card.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    const href = card.dataset.href;
                    if (href) {
                        window.open(href, '_blank', 'noopener');
                    }
                }
            });
        });
    }

    // ═══════════════════════════════════════════════════════════════
    // SMOOTH SCROLL NAVIGATION
    // ═══════════════════════════════════════════════════════════════

    function initSmoothScroll() {
        const navLinks = document.querySelectorAll('.nav-links a');

        navLinks.forEach(link => {
            link.addEventListener('click', (e) => {
                const href = link.getAttribute('href');
                if (href.startsWith('#')) {
                    e.preventDefault();
                    const target = document.querySelector(href);
                    if (target) {
                        const offset = 100; // Account for fixed nav
                        const top = target.getBoundingClientRect().top + window.scrollY - offset;
                        window.scrollTo({ top, behavior: 'smooth' });
                    }
                }
            });
        });
    }

    // ═══════════════════════════════════════════════════════════════
    // SCROLL REVEAL (INTERSECTION OBSERVER)
    // ═══════════════════════════════════════════════════════════════

    function initScrollReveal() {
        const observerOptions = {
            root: null,
            rootMargin: '0px 0px -10% 0px',
            threshold: 0.1
        };

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('revealed');
                    observer.unobserve(entry.target);
                }
            });
        }, observerOptions);

        // Observe collection headers
        document.querySelectorAll('.collection-header').forEach(el => {
            el.classList.add('reveal-on-scroll');
            observer.observe(el);
        });

        // Observe product cards with stagger
        document.querySelectorAll('.product-card').forEach((el, index) => {
            el.classList.add('reveal-on-scroll');
            el.style.transitionDelay = `${(index % 3) * 89}ms`;
            observer.observe(el);
        });
    }

    // ═══════════════════════════════════════════════════════════════
    // NAV SCROLL STATE
    // ═══════════════════════════════════════════════════════════════

    function initNavScrollState() {
        const nav = document.querySelector('.nav');
        if (!nav) return;

        let lastScroll = 0;
        let ticking = false;

        window.addEventListener('scroll', () => {
            if (!ticking) {
                requestAnimationFrame(() => {
                    const currentScroll = window.scrollY;

                    if (currentScroll > 100) {
                        nav.classList.add('scrolled');
                    } else {
                        nav.classList.remove('scrolled');
                    }

                    lastScroll = currentScroll;
                    ticking = false;
                });
                ticking = true;
            }
        });
    }

    // ═══════════════════════════════════════════════════════════════
    // HEART EASTER EGG
    // ═══════════════════════════════════════════════════════════════

    function initHeartEasterEgg() {
        const heart = document.querySelector('.footer-heart');
        if (!heart) return;

        let clickCount = 0;

        function triggerHeart() {
            clickCount++;

            // Add pop animation
            heart.style.transform = 'scale(1.5)';
            setTimeout(() => {
                heart.style.transform = 'scale(1)';
            }, 233);

            // Easter egg after 3 clicks
            if (clickCount === 3) {
                showEasterEgg();
                clickCount = 0;
            }
        }

        heart.addEventListener('click', triggerHeart);

        // Keyboard support
        heart.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                triggerHeart();
            }
        });
    }

    function showEasterEgg() {
        const messages = [
            "Patterns are vocabulary. You speak fluently.",
            "Heritage with humor — that's the secret.",
            "Every crease is autobiography.",
            "British countryside meets Saturday morning cartoons.",
            "Craft is non-negotiable. Humor is mandatory."
        ];

        const message = messages[Math.floor(Math.random() * messages.length)];

        // Create toast (accessible)
        const toast = document.createElement('div');
        toast.className = 'easter-egg-toast';
        toast.setAttribute('role', 'status');
        toast.setAttribute('aria-live', 'polite');
        toast.textContent = message;
        toast.style.cssText = `
            position: fixed;
            bottom: 2rem;
            left: 50%;
            transform: translateX(-50%) translateY(20px);
            background: linear-gradient(135deg, #1C2541 0%, #3A506B 100%);
            color: #F5EFE0;
            padding: 1rem 2rem;
            border-radius: 9999px;
            font-family: 'DM Serif Display', serif;
            font-style: italic;
            font-size: 1rem;
            box-shadow: 0 10px 40px rgba(28, 37, 65, 0.3);
            opacity: 0;
            transition: all 377ms cubic-bezier(0.22, 1, 0.36, 1);
            z-index: 1000;
            white-space: nowrap;
        `;

        document.body.appendChild(toast);

        // Animate in
        requestAnimationFrame(() => {
            toast.style.opacity = '1';
            toast.style.transform = 'translateX(-50%) translateY(0)';
        });

        // Remove after delay
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(-50%) translateY(20px)';
            setTimeout(() => toast.remove(), 377);
        }, 3000);
    }

    // ═══════════════════════════════════════════════════════════════
    // CSS FOR SCROLL REVEAL
    // ═══════════════════════════════════════════════════════════════

    function injectScrollRevealCSS() {
        const style = document.createElement('style');
        style.textContent = `
            .reveal-on-scroll {
                opacity: 0;
                transform: translateY(24px);
                transition: opacity 610ms cubic-bezier(0.22, 1, 0.36, 1),
                            transform 610ms cubic-bezier(0.22, 1, 0.36, 1);
            }

            .reveal-on-scroll.revealed {
                opacity: 1;
                transform: translateY(0);
            }

            .nav.scrolled {
                background: rgba(28, 37, 65, 0.98);
                box-shadow: 0 10px 40px rgba(28, 37, 65, 0.2);
            }

            #outfit-items {
                transition: opacity 233ms ease-out, transform 233ms ease-out;
            }

            @media (prefers-reduced-motion: reduce) {
                .reveal-on-scroll {
                    opacity: 1;
                    transform: none;
                    transition: none;
                }
            }
        `;
        document.head.appendChild(style);
    }

    // ═══════════════════════════════════════════════════════════════
    // HEARTS SYSTEM (Wishlist)
    // ═══════════════════════════════════════════════════════════════

    const HEARTS_KEY = 'tim_wardrobe_hearts';

    function getHeartedItems() {
        try {
            return JSON.parse(localStorage.getItem(HEARTS_KEY)) || [];
        } catch {
            return [];
        }
    }

    function saveHeartedItems(items) {
        try {
            localStorage.setItem(HEARTS_KEY, JSON.stringify(items));
        } catch {
            // Storage unavailable
        }
    }

    function isHearted(productId) {
        return getHeartedItems().some(item => item.id === productId);
    }

    function toggleHeart(productId, productData) {
        const items = getHeartedItems();
        const index = items.findIndex(item => item.id === productId);

        if (index > -1) {
            // Remove
            items.splice(index, 1);
        } else {
            // Add
            items.push({
                id: productId,
                ...productData,
                heartedAt: Date.now()
            });
        }

        saveHeartedItems(items);
        updateNavHeartsCount();
        updateHeartedPanel();

        return index === -1; // Returns true if now hearted
    }

    function initProductHearts() {
        const cards = document.querySelectorAll('.product-card');

        cards.forEach(card => {
            const brand = card.querySelector('.product-brand')?.textContent || '';
            const name = card.querySelector('.product-name')?.textContent || '';
            const price = card.querySelector('.product-price')?.textContent || '';
            const image = card.querySelector('.product-image')?.src || '';
            const href = card.dataset.href || '';

            // Create unique ID from brand + name
            const productId = `${brand}-${name}`.toLowerCase().replace(/[^a-z0-9]+/g, '-');

            // Create heart button
            const heartBtn = document.createElement('button');
            heartBtn.className = 'product-heart' + (isHearted(productId) ? ' hearted' : '');
            heartBtn.setAttribute('aria-label', isHearted(productId) ? 'Remove from wishlist' : 'Add to wishlist');
            heartBtn.setAttribute('aria-pressed', isHearted(productId) ? 'true' : 'false');
            heartBtn.innerHTML = `
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
                </svg>
            `;

            heartBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                const nowHearted = toggleHeart(productId, { brand, name, price, image, href });

                heartBtn.classList.toggle('hearted', nowHearted);
                heartBtn.setAttribute('aria-label', nowHearted ? 'Remove from wishlist' : 'Add to wishlist');
                heartBtn.setAttribute('aria-pressed', nowHearted ? 'true' : 'false');
            });

            // Insert heart button into card
            const imageContainer = card.querySelector('.product-image-container');
            if (imageContainer) {
                imageContainer.appendChild(heartBtn);
            }
        });
    }

    function initNavHearts() {
        const nav = document.querySelector('.nav-links');
        if (!nav) return;

        // Create hearts counter element
        const heartsNav = document.createElement('button');
        heartsNav.className = 'nav-hearts';
        heartsNav.setAttribute('aria-label', 'View wishlist');
        heartsNav.innerHTML = `
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" stroke="none">
                <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
            </svg>
            <span class="nav-hearts-count">${getHeartedItems().length}</span>
        `;

        heartsNav.addEventListener('click', toggleHeartedPanel);

        nav.appendChild(heartsNav);
    }

    function updateNavHeartsCount() {
        const countEl = document.querySelector('.nav-hearts-count');
        if (!countEl) return;

        const count = getHeartedItems().length;
        const oldCount = parseInt(countEl.textContent) || 0;

        if (count !== oldCount) {
            countEl.textContent = count;
            // Micro-animation
            countEl.style.transform = 'scale(1.3)';
            setTimeout(() => {
                countEl.style.transform = 'scale(1)';
            }, 144);
        }
    }

    function initHeartedPanel() {
        // Create overlay
        const overlay = document.createElement('div');
        overlay.className = 'panel-overlay';
        overlay.addEventListener('click', closeHeartedPanel);

        // Create panel
        const panel = document.createElement('aside');
        panel.className = 'hearted-panel';
        panel.setAttribute('aria-label', 'Wishlist');
        panel.innerHTML = `
            <header class="hearted-panel-header">
                <h2>Wishlist</h2>
                <button class="hearted-panel-close" aria-label="Close wishlist">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="18" y1="6" x2="6" y2="18"/>
                        <line x1="6" y1="6" x2="18" y2="18"/>
                    </svg>
                </button>
            </header>
            <div class="hearted-panel-content"></div>
            <footer class="hearted-panel-footer">
                <div class="hearted-panel-total">
                    <span>Total</span>
                    <span class="hearted-panel-total-price">$0</span>
                </div>
            </footer>
        `;

        panel.querySelector('.hearted-panel-close').addEventListener('click', closeHeartedPanel);

        document.body.appendChild(overlay);
        document.body.appendChild(panel);

        updateHeartedPanel();
    }

    function toggleHeartedPanel() {
        const panel = document.querySelector('.hearted-panel');
        const overlay = document.querySelector('.panel-overlay');
        if (!panel || !overlay) return;

        const isOpen = panel.classList.contains('open');

        if (isOpen) {
            closeHeartedPanel();
        } else {
            panel.classList.add('open');
            overlay.classList.add('visible');
            document.body.style.overflow = 'hidden';
        }
    }

    function closeHeartedPanel() {
        const panel = document.querySelector('.hearted-panel');
        const overlay = document.querySelector('.panel-overlay');
        if (!panel || !overlay) return;

        panel.classList.remove('open');
        overlay.classList.remove('visible');
        document.body.style.overflow = '';
    }

    function updateHeartedPanel() {
        const content = document.querySelector('.hearted-panel-content');
        const totalPrice = document.querySelector('.hearted-panel-total-price');
        if (!content) return;

        const items = getHeartedItems();

        if (items.length === 0) {
            content.innerHTML = `
                <div class="hearted-panel-empty">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
                    </svg>
                    <p>Your wishlist is empty</p>
                    <p class="hearted-panel-empty-sub">Heart pieces you love to save them here</p>
                </div>
            `;
            if (totalPrice) totalPrice.textContent = '$0';
            return;
        }

        // Calculate total
        let total = 0;
        items.forEach(item => {
            const priceNum = parseInt(item.price?.replace(/[^0-9]/g, '')) || 0;
            total += priceNum;
        });

        content.innerHTML = items.map(item => `
            <article class="hearted-item" data-id="${item.id}">
                <img src="${item.image}" alt="${item.name}" class="hearted-item-image">
                <div class="hearted-item-info">
                    <span class="hearted-item-brand">${item.brand}</span>
                    <span class="hearted-item-name">${item.name}</span>
                    <span class="hearted-item-price">${item.price}</span>
                </div>
                <button class="hearted-item-remove" aria-label="Remove ${item.name} from wishlist">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="18" y1="6" x2="6" y2="18"/>
                        <line x1="6" y1="6" x2="18" y2="18"/>
                    </svg>
                </button>
            </article>
        `).join('');

        if (totalPrice) totalPrice.textContent = '$' + total.toLocaleString();

        // Add remove handlers
        content.querySelectorAll('.hearted-item-remove').forEach(btn => {
            btn.addEventListener('click', () => {
                const item = btn.closest('.hearted-item');
                const id = item?.dataset.id;
                if (id) {
                    // Animate out
                    item.style.opacity = '0';
                    item.style.transform = 'translateX(20px)';
                    setTimeout(() => {
                        toggleHeart(id, {});
                        // Update product card heart button
                        const cardBtn = document.querySelector(`.product-card .product-heart.hearted`);
                        // Find the right card by matching ID
                        document.querySelectorAll('.product-card').forEach(card => {
                            const brand = card.querySelector('.product-brand')?.textContent || '';
                            const name = card.querySelector('.product-name')?.textContent || '';
                            const cardId = `${brand}-${name}`.toLowerCase().replace(/[^a-z0-9]+/g, '-');
                            if (cardId === id) {
                                const heartBtn = card.querySelector('.product-heart');
                                if (heartBtn) {
                                    heartBtn.classList.remove('hearted');
                                    heartBtn.setAttribute('aria-pressed', 'false');
                                }
                            }
                        });
                    }, 233);
                }
            });
        });
    }

    // ═══════════════════════════════════════════════════════════════
    // MICRODELIGHTS — Scroll Progress Bar
    // ═══════════════════════════════════════════════════════════════

    function initScrollProgress() {
        const progress = document.createElement('div');
        progress.className = 'scroll-progress';
        progress.innerHTML = '<div class="scroll-progress-bar"></div>';
        document.body.appendChild(progress);

        const bar = progress.querySelector('.scroll-progress-bar');

        window.addEventListener('scroll', () => {
            const scrollTop = window.scrollY;
            const docHeight = document.documentElement.scrollHeight - window.innerHeight;
            const scrollPercent = (scrollTop / docHeight) * 100;
            bar.style.width = scrollPercent + '%';
        }, { passive: true });
    }

    // ═══════════════════════════════════════════════════════════════
    // MICRODELIGHTS — Hero Parallax
    // ═══════════════════════════════════════════════════════════════

    function initHeroParallax() {
        const hero = document.querySelector('.hero');
        const heroContent = document.querySelector('.hero-content');
        if (!hero || !heroContent) return;

        window.addEventListener('scroll', () => {
            const scrollY = window.scrollY;
            const heroHeight = hero.offsetHeight;

            if (scrollY < heroHeight) {
                const parallaxY = scrollY * 0.3;
                const opacity = 1 - (scrollY / heroHeight) * 0.6;
                const scale = 1 - (scrollY / heroHeight) * 0.05;

                heroContent.style.transform = `translateY(${parallaxY}px) scale(${scale})`;
                heroContent.style.opacity = opacity;
            }
        }, { passive: true });
    }

    // ═══════════════════════════════════════════════════════════════
    // MICRODELIGHTS — Magnetic Buttons
    // ═══════════════════════════════════════════════════════════════

    function initMagneticButtons() {
        const buttons = document.querySelectorAll('.product-cta, .outfit-preset');

        buttons.forEach(btn => {
            btn.addEventListener('mousemove', (e) => {
                const rect = btn.getBoundingClientRect();
                const x = e.clientX - rect.left - rect.width / 2;
                const y = e.clientY - rect.top - rect.height / 2;

                btn.style.transform = `translate(${x * 0.15}px, ${y * 0.15}px)`;
            });

            btn.addEventListener('mouseleave', () => {
                btn.style.transform = '';
            });
        });
    }

    // ═══════════════════════════════════════════════════════════════
    // MICRODELIGHTS — Staggered Philosophy Cards
    // ═══════════════════════════════════════════════════════════════

    function initPhilosophyReveal() {
        const items = document.querySelectorAll('.philosophy-item');

        const observer = new IntersectionObserver((entries) => {
            entries.forEach((entry, index) => {
                if (entry.isIntersecting) {
                    setTimeout(() => {
                        entry.target.classList.add('revealed');
                    }, index * 144);
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.2 });

        items.forEach(item => {
            item.classList.add('philosophy-reveal');
            observer.observe(item);
        });
    }

    // ═══════════════════════════════════════════════════════════════
    // MICRODELIGHTS — Tilt Cards on Hover
    // ═══════════════════════════════════════════════════════════════

    function initCardTilt() {
        const cards = document.querySelectorAll('.product-card');

        cards.forEach(card => {
            card.addEventListener('mousemove', (e) => {
                const rect = card.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const y = e.clientY - rect.top;
                const centerX = rect.width / 2;
                const centerY = rect.height / 2;

                const rotateX = (y - centerY) / 20;
                const rotateY = (centerX - x) / 20;

                card.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateY(-12px) scale(1.02)`;
            });

            card.addEventListener('mouseleave', () => {
                card.style.transform = '';
                card.style.transition = 'transform 0.5s cubic-bezier(0.22, 1, 0.36, 1)';
            });

            card.addEventListener('mouseenter', () => {
                card.style.transition = 'transform 0.1s ease-out';
            });
        });
    }

    // ═══════════════════════════════════════════════════════════════
    // MICRODELIGHTS — Nav Section Indicator
    // ═══════════════════════════════════════════════════════════════

    function initNavSectionIndicator() {
        const sections = document.querySelectorAll('section[id]');
        const navLinks = document.querySelectorAll('.nav-links a[href^="#"]');

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const id = entry.target.id;
                    navLinks.forEach(link => {
                        link.classList.remove('active');
                        if (link.getAttribute('href') === '#' + id) {
                            link.classList.add('active');
                        }
                    });
                }
            });
        }, { rootMargin: '-50% 0px -50% 0px' });

        sections.forEach(section => observer.observe(section));
    }

    // ═══════════════════════════════════════════════════════════════
    // MICRODELIGHTS — Sparkle on Heart
    // ═══════════════════════════════════════════════════════════════

    function createSparkle(x, y) {
        const sparkle = document.createElement('div');
        sparkle.className = 'sparkle';
        sparkle.style.cssText = `
            position: fixed;
            left: ${x}px;
            top: ${y}px;
            width: 8px;
            height: 8px;
            background: var(--burgundy);
            border-radius: 50%;
            pointer-events: none;
            z-index: 9999;
            animation: sparkleAnim 600ms ease-out forwards;
        `;
        document.body.appendChild(sparkle);
        setTimeout(() => sparkle.remove(), 600);
    }

    function initHeartSparkles() {
        document.addEventListener('click', (e) => {
            if (e.target.closest('.product-heart')) {
                const rect = e.target.getBoundingClientRect();
                const cx = rect.left + rect.width / 2;
                const cy = rect.top + rect.height / 2;

                for (let i = 0; i < 6; i++) {
                    setTimeout(() => {
                        const angle = (i / 6) * Math.PI * 2;
                        const distance = 20 + Math.random() * 15;
                        const x = cx + Math.cos(angle) * distance;
                        const y = cy + Math.sin(angle) * distance;
                        createSparkle(x, y);
                    }, i * 50);
                }
            }
        });
    }

    // ═══════════════════════════════════════════════════════════════
    // MICRODELIGHTS — Number Counter Animation (Enhanced)
    // ═══════════════════════════════════════════════════════════════

    function initStatCounters() {
        const stats = document.querySelectorAll('.stat-value');

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const el = entry.target;
                    const text = el.textContent;
                    const num = parseInt(text);

                    if (!isNaN(num)) {
                        animateCounter(el, 0, num, 1200);
                    }
                    observer.unobserve(el);
                }
            });
        }, { threshold: 0.5 });

        stats.forEach(stat => observer.observe(stat));
    }

    function animateCounter(el, start, end, duration) {
        const startTime = performance.now();

        function update(currentTime) {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);

            // Ease out cubic
            const eased = 1 - Math.pow(1 - progress, 3);
            const current = Math.round(start + (end - start) * eased);

            el.textContent = current;

            if (progress < 1) {
                requestAnimationFrame(update);
            }
        }

        requestAnimationFrame(update);
    }

    // ═══════════════════════════════════════════════════════════════
    // MICRODELIGHTS — Inject All CSS
    // ═══════════════════════════════════════════════════════════════

    function injectMicrodelightCSS() {
        const style = document.createElement('style');
        style.textContent = `
            /* Scroll Progress */
            .scroll-progress {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                height: 3px;
                z-index: 1000;
                background: rgba(28, 37, 65, 0.1);
            }
            .scroll-progress-bar {
                height: 100%;
                width: 0;
                background: linear-gradient(90deg, var(--burgundy), var(--indigo), var(--olive));
                transition: width 50ms ease-out;
            }

            /* Philosophy reveal */
            .philosophy-reveal {
                opacity: 0;
                transform: translateY(40px);
                transition: all 610ms cubic-bezier(0.22, 1, 0.36, 1);
            }
            .philosophy-reveal.revealed {
                opacity: 1;
                transform: translateY(0);
            }

            /* Nav active link */
            .nav-links a.active {
                color: white;
            }
            .nav-links a.active::after {
                transform: scaleX(1);
            }

            /* Sparkle animation */
            @keyframes sparkleAnim {
                0% { transform: scale(0); opacity: 1; }
                50% { transform: scale(1.5); opacity: 0.8; }
                100% { transform: scale(0); opacity: 0; }
            }

            /* Outfit item enhanced styles */
            .outfit-item {
                background: var(--porcelain);
                border-radius: var(--radius-lg);
                padding: 0;
                text-align: center;
                width: 140px;
                transition: all 377ms cubic-bezier(0.34, 1.56, 0.64, 1);
                border: 1px solid var(--ink-whisper);
                cursor: pointer;
                overflow: hidden;
                box-shadow: var(--shadow-sm);
            }

            .outfit-item:hover {
                box-shadow: var(--shadow-xl);
                border-color: var(--burgundy);
            }

            .outfit-item-image-wrap {
                position: relative;
                aspect-ratio: 1;
                overflow: hidden;
                background: var(--linen-warm);
            }

            .outfit-item-image {
                width: 100%;
                height: 100%;
                object-fit: cover;
                transition: transform 377ms ease-out;
            }

            .outfit-item:hover .outfit-item-image {
                transform: scale(1.08);
            }

            .outfit-item-category {
                position: absolute;
                top: 6px;
                right: 6px;
                font-size: 14px;
                background: rgba(255,255,255,0.9);
                border-radius: 50%;
                width: 24px;
                height: 24px;
                display: flex;
                align-items: center;
                justify-content: center;
                box-shadow: var(--shadow-sm);
            }

            .outfit-item-sale {
                position: absolute;
                bottom: 6px;
                left: 6px;
                font-size: 9px;
                font-weight: 700;
                letter-spacing: 0.05em;
                text-transform: uppercase;
                background: linear-gradient(135deg, #FF6B6B, #FF8E8E);
                color: white;
                padding: 2px 6px;
                border-radius: var(--radius-full);
            }

            .outfit-item-details {
                padding: var(--space-3);
            }

            .outfit-item-name {
                font-size: 11px;
                font-weight: 600;
                color: var(--ink);
                margin-bottom: 2px;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }

            .outfit-item-price {
                font-family: var(--font-mono);
                font-size: var(--text-sm);
                font-weight: 600;
                color: var(--navy);
            }

            .outfit-item-price .sale-price {
                color: #FF6B6B;
            }

            /* Outfit items container */
            .outfit-items {
                display: flex;
                gap: var(--space-5);
                justify-content: center;
                flex-wrap: wrap;
                margin-bottom: var(--space-6);
                min-height: 200px;
                align-items: flex-start;
            }

            /* Preset hover enhancement */
            .outfit-preset {
                position: relative;
                overflow: hidden;
            }

            .outfit-preset::before {
                content: '';
                position: absolute;
                inset: 0;
                background: linear-gradient(135deg, var(--burgundy), var(--indigo));
                opacity: 0;
                transition: opacity 233ms ease-out;
            }

            .outfit-preset:hover::before {
                opacity: 0.03;
            }

            .outfit-preset.active::before {
                opacity: 0.06;
            }

            /* Hearts button enhanced */
            .nav-hearts {
                border: none;
                position: relative;
                overflow: hidden;
            }

            .nav-hearts::after {
                content: '';
                position: absolute;
                inset: 0;
                background: radial-gradient(circle at center, var(--burgundy) 0%, transparent 70%);
                opacity: 0;
                transition: opacity 233ms ease-out;
            }

            .nav-hearts:hover::after {
                opacity: 0.3;
            }

            /* Product card image shine effect */
            .product-image-container::before {
                content: '';
                position: absolute;
                top: 0;
                left: -100%;
                width: 50%;
                height: 100%;
                background: linear-gradient(
                    90deg,
                    transparent,
                    rgba(255,255,255,0.2),
                    transparent
                );
                transition: left 600ms ease-out;
                z-index: 2;
                pointer-events: none;
            }

            .product-card:hover .product-image-container::before {
                left: 100%;
            }

            /* Hearted panel header h2 style */
            .hearted-panel-header h2 {
                font-family: var(--font-display);
                font-size: var(--text-xl);
                font-weight: 400;
                margin: 0;
            }

            /* Empty state */
            .hearted-panel-empty {
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                height: 100%;
                text-align: center;
                color: var(--ink-faint);
                padding: var(--space-8);
            }

            .hearted-panel-empty svg {
                margin-bottom: var(--space-4);
                opacity: 0.4;
            }

            .hearted-panel-empty p {
                margin: 0;
                font-size: var(--text-base);
            }

            .hearted-panel-empty-sub {
                font-size: var(--text-sm) !important;
                margin-top: var(--space-2) !important;
                opacity: 0.7;
            }

            /* Hearted item brand */
            .hearted-item-brand {
                display: block;
                font-size: 9px;
                font-weight: 700;
                letter-spacing: 0.1em;
                text-transform: uppercase;
                color: var(--burgundy);
                margin-bottom: 2px;
            }

            /* Total styling */
            .hearted-panel-total {
                display: flex;
                justify-content: space-between;
                align-items: center;
            }

            .hearted-panel-total span:first-child {
                font-size: var(--text-sm);
                color: var(--ink-faint);
                text-transform: uppercase;
                letter-spacing: 0.1em;
            }

            .hearted-panel-total-price {
                font-family: var(--font-display);
                font-size: var(--text-2xl);
                color: var(--navy);
            }

            @media (prefers-reduced-motion: reduce) {
                .scroll-progress-bar {
                    transition: none;
                }
                .philosophy-reveal {
                    opacity: 1;
                    transform: none;
                }
                .product-image-container::before {
                    display: none;
                }
            }
        `;
        document.head.appendChild(style);
    }

    // ═══════════════════════════════════════════════════════════════
    // INIT
    // ═══════════════════════════════════════════════════════════════

    function init() {
        injectScrollRevealCSS();
        injectMicrodelightCSS();
        initOutfitBuilder();
        initProductCards();
        initSmoothScroll();
        initScrollReveal();
        initNavScrollState();
        initHeartEasterEgg();
        initProductHearts();
        initNavHearts();
        initHeartedPanel();
        initScrollProgress();
        initHeroParallax();
        initMagneticButtons();
        initPhilosophyReveal();
        initCardTilt();
        initNavSectionIndicator();
        initHeartSparkles();
        initStatCounters();

        // Log a little curator's note
        console.log(
            '%c The Curator\'s Wardrobe ',
            'background: linear-gradient(135deg, #1C2541, #3A506B); color: #F5EFE0; padding: 8px 16px; border-radius: 4px; font-family: Georgia, serif; font-style: italic;'
        );
        console.log(
            '%c "Patterns are vocabulary. The more you know, the more interesting your sentences become." ',
            'color: #5C677D; font-style: italic;'
        );
    }

    // Run on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
