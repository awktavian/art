/* ═══════════════════════════════════════════════════════════════
   THE CURATED WARDROBE — Interactive Features
   Outfit builder, scroll reveals, and micro-interactions
   ═══════════════════════════════════════════════════════════════ */

// Product data with local images
const products = {
    // Essentials
    ladywhite: { name: "Lady White Co T-Shirt", price: 90, image: "images/ladywhite-tshirt.jpg", category: "tops" },
    sunspel: { name: "Sunspel Riviera Polo", price: 115, image: "images/sunspel-riviera.jpg", category: "tops" },
    drakes: { name: "Drake's Oxford Shirt", price: 295, image: "images/drakes-oxford.jpg", category: "tops" },
    lucafaloni: { name: "Luca Faloni Cashmere", price: 395, image: "images/lucafaloni-cashmere.jpg", category: "knitwear" },
    ironheart: { name: "Iron Heart Denim", price: 395, image: "images/ironheart-denim.jpg", category: "bottoms" },
    
    // Outerwear
    burberry: { name: "Burberry Harrington", price: 1290, image: "images/burberry-trench.jpg", category: "outerwear" },
    schott: { name: "Schott Perfecto 618", price: 900, image: "images/schott-perfecto.jpg", category: "outerwear" },
    barbour: { name: "Barbour Bedale", price: 450, image: "images/barbour-bedale.jpg", category: "outerwear" },
    
    // Footwear
    cp: { name: "Common Projects Achilles", price: 450, image: "images/cp-achilles.jpg", category: "footwear" },
    alden: { name: "Alden 990 Cordovan", price: 799, image: "images/alden-990.jpg", category: "footwear" },
    edwardgreen: { name: "Edward Green Oxford", price: 1495, image: "images/edwardgreen-chelsea.jpg", category: "footwear" },
    
    // Accessories
    grandseiko: { name: "Grand Seiko Snowflake", price: 5800, image: "images/grandseiko-snowflake.jpg", category: "accessories" },
    persol: { name: "Persol 714", price: 340, image: "images/persol-714.jpg", category: "accessories" },
    andersons: { name: "Anderson's Belt", price: 195, image: "images/andersons-belt.jpg", category: "accessories" },
    frankclegg: { name: "Frank Clegg Messenger", price: 1100, image: "images/frankclegg-briefcase.jpg", category: "accessories" }
};

// Outfit presets
const outfits = {
    casual: ['ladywhite', 'ironheart', 'cp', 'persol', 'andersons'],
    business: ['drakes', 'ironheart', 'alden', 'grandseiko', 'frankclegg'],
    evening: ['lucafaloni', 'ironheart', 'edwardgreen', 'grandseiko', 'andersons'],
    outdoor: ['sunspel', 'ironheart', 'barbour', 'cp', 'persol']
};

// DOM elements
const outfitItemsContainer = document.getElementById('outfit-items');
const outfitTotalPrice = document.getElementById('outfit-total-price');
const outfitPresets = document.querySelectorAll('.outfit-preset');

// Render outfit items
function renderOutfit(outfitName) {
    const items = outfits[outfitName];
    let total = 0;
    
    outfitItemsContainer.innerHTML = '';
    
    items.forEach((productKey, index) => {
        const product = products[productKey];
        total += product.price;
        
        const itemEl = document.createElement('div');
        itemEl.className = 'outfit-item';
        itemEl.style.animationDelay = `${index * 100}ms`;
        itemEl.innerHTML = `
            <img src="${product.image}" alt="${product.name}" class="outfit-item-image">
            <div class="outfit-item-info">
                <div class="outfit-item-name">${product.name}</div>
                <div class="outfit-item-price">$${product.price.toLocaleString()}</div>
            </div>
        `;
        
        outfitItemsContainer.appendChild(itemEl);
        
        // Animate in
        requestAnimationFrame(() => {
            itemEl.style.opacity = '0';
            itemEl.style.transform = 'translateY(20px)';
            requestAnimationFrame(() => {
                itemEl.style.transition = 'all 0.4s cubic-bezier(0.22, 1, 0.36, 1)';
                itemEl.style.transitionDelay = `${index * 80}ms`;
                itemEl.style.opacity = '1';
                itemEl.style.transform = 'translateY(0)';
            });
        });
    });
    
    // Animate total
    animateTotal(total);
}

// Animate price counter
function animateTotal(target) {
    const duration = 600;
    const start = parseInt(outfitTotalPrice.textContent.replace(/[$,]/g, '')) || 0;
    const startTime = performance.now();
    
    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        
        // Ease out cubic
        const easeOut = 1 - Math.pow(1 - progress, 3);
        const current = Math.round(start + (target - start) * easeOut);
        
        outfitTotalPrice.textContent = `$${current.toLocaleString()}`;
        
        if (progress < 1) {
            requestAnimationFrame(update);
        }
    }
    
    requestAnimationFrame(update);
}

// Outfit preset click handlers
outfitPresets.forEach(preset => {
    preset.addEventListener('click', () => {
        // Update active state
        outfitPresets.forEach(p => p.classList.remove('active'));
        preset.classList.add('active');
        
        // Render outfit
        const outfitName = preset.dataset.outfit;
        renderOutfit(outfitName);
    });
});

// Initialize with casual outfit
document.addEventListener('DOMContentLoaded', () => {
    renderOutfit('casual');
    initScrollReveal();
    initParallax();
});

// Scroll reveal animation
function initScrollReveal() {
    const reveals = document.querySelectorAll('.product-card, .philosophy-item');
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
                observer.unobserve(entry.target);
            }
        });
    }, {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    });
    
    reveals.forEach((el, index) => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(30px)';
        el.style.transition = `all 0.6s cubic-bezier(0.22, 1, 0.36, 1) ${index * 50}ms`;
        observer.observe(el);
    });
}

// Subtle parallax on hero
function initParallax() {
    const hero = document.querySelector('.hero-content');
    
    window.addEventListener('scroll', () => {
        const scrolled = window.pageYOffset;
        const rate = scrolled * 0.3;
        
        if (hero && scrolled < window.innerHeight) {
            hero.style.transform = `translateY(${rate}px)`;
            hero.style.opacity = 1 - (scrolled / window.innerHeight);
        }
    }, { passive: true });
}

// Smooth scroll for nav links
document.querySelectorAll('.nav-links a').forEach(link => {
    link.addEventListener('click', (e) => {
        e.preventDefault();
        const targetId = link.getAttribute('href');
        const targetEl = document.querySelector(targetId);
        
        if (targetEl) {
            targetEl.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    });
});

// Product card hover sound effect (optional - visual only for now)
document.querySelectorAll('.product-card').forEach(card => {
    card.addEventListener('mouseenter', () => {
        card.style.zIndex = '10';
    });
    
    card.addEventListener('mouseleave', () => {
        card.style.zIndex = '';
    });
});
