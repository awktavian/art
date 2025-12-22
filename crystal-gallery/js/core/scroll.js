// Scroll reveal and smooth scroll handling
export class ScrollHandler {
    constructor() {
        this.reveals = document.querySelectorAll('.reveal');
        this.init();
    }

    init() {
        // Intersection Observer for scroll reveals
        const revealObserver = new IntersectionObserver(
            (entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        entry.target.classList.add('visible');
                    }
                });
            },
            {
                threshold: 0.1,
                rootMargin: '0px 0px -80px 0px'
            }
        );

        this.reveals.forEach(el => revealObserver.observe(el));

        // Smooth scroll for navigation
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {
            anchor.addEventListener('click', (e) => {
                e.preventDefault();
                const target = document.querySelector(anchor.getAttribute('href'));
                if (target) {
                    target.scrollIntoView({
                        behavior: 'smooth',
                        block: 'center'
                    });
                }
            });
        });
    }
}
