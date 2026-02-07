// Spring 2026 Gallery — For Jill
// Navy anchors. Linen breathes. Spring arrives.

document.addEventListener('DOMContentLoaded', () => {
    // ═══════════════════════════════════════════════════════════════
    // Category Filtering
    // ═══════════════════════════════════════════════════════════════
    const filterButtons = document.querySelectorAll('.filter-pill');
    const cards = document.querySelectorAll('.product-card');

    filterButtons.forEach(button => {
        button.addEventListener('click', () => {
            const filter = button.dataset.filter;

            // Update active state
            filterButtons.forEach(b => {
                b.classList.remove('active');
                b.setAttribute('aria-selected', 'false');
            });
            button.classList.add('active');
            button.setAttribute('aria-selected', 'true');

            // Filter cards with staggered animation
            let visibleIndex = 0;
            cards.forEach(card => {
                const category = card.dataset.category;
                const shouldShow = filter === 'all' || category === filter;

                if (shouldShow) {
                    card.removeAttribute('data-hidden');
                    card.style.setProperty('--reveal-delay', `${visibleIndex * 0.06}s`);
                    card.style.animation = 'none';
                    card.offsetHeight; // Trigger reflow
                    card.style.animation = '';
                    visibleIndex++;
                } else {
                    card.setAttribute('data-hidden', 'true');
                }
            });
        });
    });

    // ═══════════════════════════════════════════════════════════════
    // Scroll Reveal
    // ═══════════════════════════════════════════════════════════════
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('revealed');
            }
        });
    }, { threshold: 0.08, rootMargin: '40px' });

    document.querySelectorAll(
        '.product-card, .centerpiece, .philosophy-item'
    ).forEach(el => observer.observe(el));

    // ═══════════════════════════════════════════════════════════════
    // Subtle parallax on hero
    // ═══════════════════════════════════════════════════════════════
    const hero = document.querySelector('.hero');
    if (hero && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        window.addEventListener('scroll', () => {
            const y = window.scrollY;
            if (y < window.innerHeight) {
                hero.style.transform = `translateY(${y * 0.15}px)`;
                hero.style.opacity = 1 - (y / (window.innerHeight * 1.2));
            }
        }, { passive: true });
    }
});
