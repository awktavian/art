// Scroll Management & Room Navigation

export class ScrollManager {
    constructor() {
        this.rooms = Array.from(document.querySelectorAll('.room'));
        this.navLinks = Array.from(document.querySelectorAll('.nav-links a'));
        this.currentRoom = null;

        this.init();
    }

    init() {
        // Intersection Observer for room transitions
        this.observer = new IntersectionObserver(
            this.onIntersect.bind(this),
            {
                threshold: 0.5,
                rootMargin: '-20% 0px'
            }
        );

        this.rooms.forEach(room => this.observer.observe(room));

        // Smooth scroll for nav links
        this.navLinks.forEach(link => {
            link.addEventListener('click', this.onNavClick.bind(this));
        });

        // Update on scroll
        window.addEventListener('scroll', this.onScroll.bind(this), { passive: true });
    }

    onIntersect(entries) {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const room = entry.target;
                this.setActiveRoom(room);

                // Trigger room-specific animations
                this.animateRoom(room);
            }
        });
    }

    setActiveRoom(room) {
        if (this.currentRoom === room) return;

        this.currentRoom = room;
        const roomName = room.dataset.room;

        // Update nav
        this.navLinks.forEach(link => {
            if (link.dataset.room === roomName) {
                link.classList.add('active');
            } else {
                link.classList.remove('active');
            }
        });

        // Emit event
        window.dispatchEvent(new CustomEvent('roomchange', {
            detail: { room: roomName }
        }));
    }

    animateRoom(room) {
        // Add fade-in class to elements
        const elements = room.querySelectorAll('.room-content > *');
        elements.forEach((el, index) => {
            setTimeout(() => {
                el.classList.add('fade-in');
            }, index * 100);
        });
    }

    onNavClick(e) {
        e.preventDefault();
        const target = e.currentTarget;
        const roomName = target.dataset.room;
        const room = document.getElementById(roomName);

        if (room) {
            room.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }

    onScroll() {
        // Could add scroll progress indicator here
    }
}
