/**
 * ChronOS Changelog Microinteractions System
 *
 * Implements 12 must-have microinteractions for enhanced user experience:
 * 1. Staggered Cascade Entry
 * 2. Commit Card Elevation
 * 3. Infinite Scroll
 * 4. Skeleton Wave Loading
 * 5. Magnetic Scroll Snapping
 * 6. Compact Mode Toggle
 * 7. Animated Filter Pills
 * 8. Smart Groups Auto-Collapse
 * 9. Accordion Slide
 * 10. Copy Commit Hash Feedback
 * 11. Hero Stats Odometer
 * 12. Scroll to Top Rocket
 *
 * Performance targets: 60fps, <16.67ms per frame
 * Accessibility: ARIA updates, keyboard nav, reduced-motion support
 * Mobile: Touch events, larger tap targets
 */

class ChangelogMicrointeractions {
  constructor(options = {}) {
    this.options = {
      enableStagger: true,
      enableElevation: true,
      enableInfiniteScroll: true,
      enableSkeleton: true,
      enableMagneticSnap: true,
      enableCompactMode: true,
      enableFilters: true,
      enableAutoCollapse: true,
      enableAccordion: true,
      enableCopyFeedback: true,
      enableOdometer: true,
      enableScrollRocket: true,
      ...options
    };

    this.state = {
      isLoading: false,
      loadedBatches: 0,
      totalCommits: 29,
      visibleCommits: 10,
      compactMode: false,
      activeFilters: new Set(),
      expandedGroups: new Set(),
      prefersReducedMotion: window.matchMedia('(prefers-reduced-motion: reduce)').matches
    };

    this.observers = new Map();
    this.rafIds = new Map();

    this.init();
  }

  // === INITIALIZATION ===

  init() {
    if (this.state.prefersReducedMotion) {
      // Disable animations but keep functionality
      this.options.enableStagger = false;
      this.options.enableSkeleton = false;
    }

    // Feature initialization (order matters for dependencies)
    this.setupScrollRocket();        // #12 - Always visible
    this.setupStaggeredEntry();      // #1 - Initial page load
    this.setupCardElevation();       // #2 - Hover effects
    this.setupInfiniteScroll();      // #3 - Progressive loading
    this.setupMagneticSnap();        // #5 - Scroll behavior
    this.setupCompactMode();         // #6 - Toggle control
    this.setupAnimatedFilters();     // #7 - Type/theme filtering
    this.setupSmartGroupCollapse();  // #8 - Auto-collapse
    this.setupAccordionSlide();      // #9 - Details expand
    this.setupCopyFeedback();        // #10 - Hash copy
    this.setupHeroOdometer();        // #11 - Counter animation

    // Keyboard navigation
    this.setupKeyboardNav();

    // Cleanup on page unload
    window.addEventListener('beforeunload', () => this.destroy());
  }

  // === #1: STAGGERED CASCADE ENTRY ===
  // Cards fade in sequentially on page load (50-100ms intervals)

  setupStaggeredEntry() {
    if (!this.options.enableStagger) return;

    const cards = this.selectCards();
    if (!cards.length) return;

    // Add initial hidden state
    cards.forEach(card => {
      card.style.opacity = '0';
      card.style.transform = 'translateY(20px)';
      card.style.transition = 'opacity 0.6s cubic-bezier(0.16, 1, 0.3, 1), transform 0.6s cubic-bezier(0.16, 1, 0.3, 1)';
    });

    // Stagger animation with IntersectionObserver for viewport detection
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry, index) => {
        if (entry.isIntersecting) {
          const delay = entry.target.dataset.staggerIndex * 50; // 50ms intervals
          setTimeout(() => {
            entry.target.style.opacity = '1';
            entry.target.style.transform = 'translateY(0)';
          }, delay);
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.1, rootMargin: '50px' });

    cards.forEach((card, i) => {
      card.dataset.staggerIndex = i;
      observer.observe(card);
    });

    this.observers.set('stagger', observer);
  }

  // === #2: COMMIT CARD ELEVATION ===
  // Hover lift with shadow (4-8px translateY, shadow blur 20-40px)

  setupCardElevation() {
    if (!this.options.enableElevation) return;

    const cards = this.selectCards();
    if (!cards.length) return;

    // Add CSS custom properties for smooth transitions
    cards.forEach(card => {
      card.style.transition = 'transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1), box-shadow 0.3s ease';
      card.style.willChange = 'auto'; // Only enable during interaction

      // Mouse/touch handlers
      const handleEnter = () => {
        card.style.willChange = 'transform, box-shadow';
        card.style.transform = 'translateY(-6px)';
        card.style.boxShadow = '0 20px 40px rgba(0, 0, 0, 0.3), 0 0 20px rgba(212, 175, 55, 0.15)';
      };

      const handleLeave = () => {
        card.style.transform = 'translateY(0)';
        card.style.boxShadow = 'none';
        setTimeout(() => {
          card.style.willChange = 'auto';
        }, 300);
      };

      if ('ontouchstart' in window) {
        card.addEventListener('touchstart', handleEnter, { passive: true });
        card.addEventListener('touchend', handleLeave, { passive: true });
      } else {
        card.addEventListener('mouseenter', handleEnter);
        card.addEventListener('mouseleave', handleLeave);
      }
    });
  }

  // === #3: INFINITE SCROLL ===
  // Progressive loading (10 → 20 → 29 commits)

  setupInfiniteScroll() {
    if (!this.options.enableInfiniteScroll) return;

    const sentinel = this.createSentinel();
    const container = this.getCommitContainer();

    if (!container) return;
    container.appendChild(sentinel);

    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting && !this.state.isLoading && this.state.visibleCommits < this.state.totalCommits) {
          this.loadMoreCommits();
        }
      });
    }, { rootMargin: '200px' }); // Start loading before user reaches bottom

    observer.observe(sentinel);
    this.observers.set('infiniteScroll', observer);
  }

  async loadMoreCommits() {
    this.state.isLoading = true;

    // Show skeleton loaders
    this.showSkeletonLoaders(10);

    // Simulate network delay (150-300ms for realistic feel)
    await this.delay(200);

    // Load next batch
    const nextBatch = Math.min(10, this.state.totalCommits - this.state.visibleCommits);
    const newCommits = this.generateCommitCards(nextBatch);

    // Hide skeletons
    this.hideSkeletonLoaders();

    // Insert new commits with stagger
    newCommits.forEach((commit, i) => {
      setTimeout(() => {
        this.getCommitContainer().appendChild(commit);
        this.setupCardElevation(); // Re-apply to new cards
      }, i * 50);
    });

    this.state.visibleCommits += nextBatch;
    this.state.loadedBatches++;
    this.state.isLoading = false;

    // Update ARIA live region
    this.announceToScreenReader(`Loaded ${nextBatch} more commits. Total: ${this.state.visibleCommits}`);
  }

  // === #4: SKELETON WAVE LOADING ===
  // Shimmer placeholders during load

  showSkeletonLoaders(count = 10) {
    if (!this.options.enableSkeleton) return;

    const container = this.getCommitContainer();
    const skeletonHTML = this.createSkeletonHTML();

    for (let i = 0; i < count; i++) {
      const skeleton = document.createElement('div');
      skeleton.className = 'skeleton-card';
      skeleton.innerHTML = skeletonHTML;
      skeleton.dataset.skeleton = 'true';
      container.appendChild(skeleton);
    }

    // Animate shimmer wave
    this.animateSkeletonWave();
  }

  hideSkeletonLoaders() {
    const skeletons = document.querySelectorAll('[data-skeleton="true"]');
    skeletons.forEach((skeleton, i) => {
      setTimeout(() => {
        skeleton.style.opacity = '0';
        setTimeout(() => skeleton.remove(), 300);
      }, i * 30);
    });
  }

  animateSkeletonWave() {
    const skeletons = document.querySelectorAll('[data-skeleton="true"]');
    let offset = 0;

    const animate = () => {
      if (!document.querySelector('[data-skeleton="true"]')) {
        if (this.rafIds.has('skeletonWave')) {
          cancelAnimationFrame(this.rafIds.get('skeletonWave'));
          this.rafIds.delete('skeletonWave');
        }
        return;
      }

      skeletons.forEach((skeleton, i) => {
        const bars = skeleton.querySelectorAll('.skeleton-bar');
        bars.forEach(bar => {
          const shimmerOffset = (offset + i * 30) % 200;
          bar.style.backgroundPosition = `${shimmerOffset}% 0`;
        });
      });

      offset = (offset + 2) % 200;
      this.rafIds.set('skeletonWave', requestAnimationFrame(animate));
    };

    animate();
  }

  createSkeletonHTML() {
    return `
      <div class="skeleton-bar" style="width: 100%; height: 24px; border-radius: 4px; background: linear-gradient(90deg, rgba(255,255,255,0.03) 0%, rgba(212,175,55,0.08) 50%, rgba(255,255,255,0.03) 100%); background-size: 200% 100%; margin-bottom: 8px;"></div>
      <div class="skeleton-bar" style="width: 80%; height: 16px; border-radius: 4px; background: linear-gradient(90deg, rgba(255,255,255,0.03) 0%, rgba(212,175,55,0.08) 50%, rgba(255,255,255,0.03) 100%); background-size: 200% 100%; margin-bottom: 8px;"></div>
      <div class="skeleton-bar" style="width: 60%; height: 12px; border-radius: 4px; background: linear-gradient(90deg, rgba(255,255,255,0.03) 0%, rgba(212,175,55,0.08) 50%, rgba(255,255,255,0.03) 100%); background-size: 200% 100%;"></div>
    `;
  }

  // === #5: MAGNETIC SCROLL SNAPPING ===
  // Smooth card boundary snapping

  setupMagneticSnap() {
    if (!this.options.enableMagneticSnap) return;

    let scrollTimeout;
    let isScrolling = false;

    const handleScroll = () => {
      isScrolling = true;
      clearTimeout(scrollTimeout);

      scrollTimeout = setTimeout(() => {
        isScrolling = false;
        this.snapToNearestCard();
      }, 150); // Wait for scroll to stop
    };

    const container = this.getScrollContainer();
    if (container) {
      container.addEventListener('scroll', handleScroll, { passive: true });
    }
  }

  snapToNearestCard() {
    const container = this.getScrollContainer();
    const cards = this.selectCards();
    if (!container || !cards.length) return;

    const containerRect = container.getBoundingClientRect();
    const containerCenter = containerRect.top + containerRect.height / 2;

    // Find nearest card to center
    let nearestCard = null;
    let minDistance = Infinity;

    cards.forEach(card => {
      const cardRect = card.getBoundingClientRect();
      const cardCenter = cardRect.top + cardRect.height / 2;
      const distance = Math.abs(cardCenter - containerCenter);

      if (distance < minDistance) {
        minDistance = distance;
        nearestCard = card;
      }
    });

    if (nearestCard && minDistance > 20) { // Only snap if not already close
      nearestCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }

  // === #6: COMPACT MODE TOGGLE ===
  // Collapse cards from 200px → 80px

  setupCompactMode() {
    if (!this.options.enableCompactMode) return;

    const toggle = this.createCompactToggle();
    document.body.appendChild(toggle);

    toggle.addEventListener('click', () => {
      this.state.compactMode = !this.state.compactMode;
      this.applyCompactMode();

      // Update ARIA
      toggle.setAttribute('aria-pressed', this.state.compactMode);
      this.announceToScreenReader(this.state.compactMode ? 'Compact mode enabled' : 'Compact mode disabled');
    });
  }

  createCompactToggle() {
    const toggle = document.createElement('button');
    toggle.className = 'compact-toggle';
    toggle.innerHTML = '<span class="icon">⇅</span>';
    toggle.setAttribute('aria-label', 'Toggle compact mode');
    toggle.setAttribute('aria-pressed', 'false');

    Object.assign(toggle.style, {
      position: 'fixed',
      bottom: '6rem',
      right: '2rem',
      width: '48px',
      height: '48px',
      borderRadius: '50%',
      background: 'rgba(0, 0, 0, 0.6)',
      backdropFilter: 'blur(16px)',
      border: '1px solid rgba(255, 255, 255, 0.1)',
      color: 'var(--gold, #D4AF37)',
      fontSize: '1.5rem',
      cursor: 'pointer',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      transition: 'all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1)',
      zIndex: '99'
    });

    toggle.addEventListener('mouseenter', () => {
      toggle.style.transform = 'scale(1.1)';
      toggle.style.boxShadow = '0 8px 16px rgba(0, 0, 0, 0.3)';
    });

    toggle.addEventListener('mouseleave', () => {
      toggle.style.transform = 'scale(1)';
      toggle.style.boxShadow = 'none';
    });

    return toggle;
  }

  applyCompactMode() {
    const cards = this.selectCards();

    cards.forEach(card => {
      if (this.state.compactMode) {
        card.style.height = '80px';
        card.style.overflow = 'hidden';
        card.classList.add('compact');
      } else {
        card.style.height = 'auto';
        card.style.overflow = 'visible';
        card.classList.remove('compact');
      }
    });
  }

  // === #7: ANIMATED FILTER PILLS ===
  // Interactive type/theme filtering

  setupAnimatedFilters() {
    if (!this.options.enableFilters) return;

    const filterBar = this.createFilterBar();
    const container = document.querySelector('.section') || document.body;

    if (container.firstChild) {
      container.insertBefore(filterBar, container.firstChild);
    } else {
      container.appendChild(filterBar);
    }
  }

  createFilterBar() {
    const filterBar = document.createElement('div');
    filterBar.className = 'filter-bar';

    Object.assign(filterBar.style, {
      display: 'flex',
      gap: '0.75rem',
      padding: '1rem',
      flexWrap: 'wrap',
      justifyContent: 'center',
      position: 'sticky',
      top: '0',
      background: 'rgba(10, 10, 12, 0.8)',
      backdropFilter: 'blur(16px)',
      zIndex: '90',
      borderBottom: '1px solid rgba(255, 255, 255, 0.06)'
    });

    const filters = [
      { label: 'All', type: 'all', color: '#D4AF37' },
      { label: 'feat', type: 'feat', color: '#30D158' },
      { label: 'fix', type: 'fix', color: '#FF2D55' },
      { label: 'perf', type: 'perf', color: '#0A84FF' },
      { label: 'docs', type: 'docs', color: '#FFD60A' },
      { label: 'refactor', type: 'refactor', color: '#AF52DE' },
      { label: 'test', type: 'test', color: '#FF9500' }
    ];

    filters.forEach(filter => {
      const pill = this.createFilterPill(filter);
      filterBar.appendChild(pill);
    });

    return filterBar;
  }

  createFilterPill({ label, type, color }) {
    const pill = document.createElement('button');
    pill.className = 'filter-pill';
    pill.textContent = label;
    pill.dataset.filter = type;
    pill.setAttribute('role', 'button');
    pill.setAttribute('aria-pressed', type === 'all');

    Object.assign(pill.style, {
      padding: '0.5rem 1rem',
      borderRadius: '9999px',
      border: `1px solid ${color}40`,
      background: type === 'all' ? color : 'transparent',
      color: type === 'all' ? '#0A0A0C' : color,
      fontSize: '0.85rem',
      fontFamily: 'var(--font-mono, monospace)',
      cursor: 'pointer',
      transition: 'all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1)',
      fontWeight: type === 'all' ? '500' : '300'
    });

    pill.addEventListener('click', () => {
      if (type === 'all') {
        this.state.activeFilters.clear();
        document.querySelectorAll('.filter-pill').forEach(p => {
          p.style.background = p.dataset.filter === 'all' ? color : 'transparent';
          p.style.color = p.dataset.filter === 'all' ? '#0A0A0C' : p.style.borderColor.replace('40', '');
          p.setAttribute('aria-pressed', p.dataset.filter === 'all');
        });
      } else {
        const isActive = this.state.activeFilters.has(type);

        if (isActive) {
          this.state.activeFilters.delete(type);
          pill.style.background = 'transparent';
          pill.style.color = color;
          pill.setAttribute('aria-pressed', 'false');
        } else {
          this.state.activeFilters.add(type);
          pill.style.background = color;
          pill.style.color = '#0A0A0C';
          pill.setAttribute('aria-pressed', 'true');

          // Deactivate "All"
          const allPill = document.querySelector('[data-filter="all"]');
          if (allPill) {
            allPill.style.background = 'transparent';
            allPill.style.color = '#D4AF37';
            allPill.setAttribute('aria-pressed', 'false');
          }
        }
      }

      this.applyFilters();
    });

    // Hover effect
    pill.addEventListener('mouseenter', () => {
      pill.style.transform = 'scale(1.05) translateY(-2px)';
      pill.style.boxShadow = `0 4px 12px ${color}40`;
    });

    pill.addEventListener('mouseleave', () => {
      pill.style.transform = 'scale(1) translateY(0)';
      pill.style.boxShadow = 'none';
    });

    return pill;
  }

  applyFilters() {
    const cards = this.selectCards();

    cards.forEach(card => {
      const commitType = card.dataset.type || this.extractCommitType(card);
      const shouldShow = this.state.activeFilters.size === 0 || this.state.activeFilters.has(commitType);

      if (shouldShow) {
        card.style.display = '';
        card.style.opacity = '1';
        card.style.transform = 'scale(1)';
      } else {
        card.style.opacity = '0';
        card.style.transform = 'scale(0.95)';
        setTimeout(() => {
          card.style.display = 'none';
        }, 300);
      }
    });

    const visibleCount = Array.from(cards).filter(c => c.style.display !== 'none').length;
    this.announceToScreenReader(`Showing ${visibleCount} of ${cards.length} commits`);
  }

  extractCommitType(card) {
    const typeEl = card.querySelector('.commit-type');
    if (typeEl) return typeEl.textContent.trim();

    const text = card.textContent.toLowerCase();
    if (text.includes('feat:')) return 'feat';
    if (text.includes('fix:')) return 'fix';
    if (text.includes('perf:')) return 'perf';
    if (text.includes('docs:')) return 'docs';
    if (text.includes('refactor:')) return 'refactor';
    if (text.includes('test:')) return 'test';

    return 'other';
  }

  // === #8: SMART GROUPS AUTO-COLLAPSE ===
  // Large groups (>10 items) start collapsed

  setupSmartGroupCollapse() {
    if (!this.options.enableAutoCollapse) return;

    const groups = this.findCommitGroups();

    groups.forEach(group => {
      const itemCount = group.items.length;

      if (itemCount > 10) {
        const collapseBtn = this.createCollapseButton(group);
        group.container.insertBefore(collapseBtn, group.container.firstChild);

        // Start collapsed
        this.collapseGroup(group, false);
      }
    });
  }

  findCommitGroups() {
    // Detect groups by date or type
    const groups = [];
    const containers = document.querySelectorAll('.commit-timeline, .section-flow');

    containers.forEach(container => {
      const items = Array.from(container.querySelectorAll('.commit-item, .commit-content, .feature-item'));

      if (items.length > 10) {
        groups.push({
          container,
          items,
          id: `group-${groups.length}`
        });
      }
    });

    return groups;
  }

  createCollapseButton(group) {
    const btn = document.createElement('button');
    btn.className = 'collapse-btn';
    btn.innerHTML = `<span class="icon">▼</span> <span class="text">Show ${group.items.length} commits</span>`;
    btn.setAttribute('aria-expanded', 'false');
    btn.dataset.groupId = group.id;

    Object.assign(btn.style, {
      width: '100%',
      padding: '0.75rem',
      background: 'rgba(255, 255, 255, 0.02)',
      border: '1px solid rgba(255, 255, 255, 0.06)',
      borderRadius: '8px',
      color: 'var(--text-dim, #f4f1ea)',
      fontSize: '0.9rem',
      cursor: 'pointer',
      transition: 'all 0.3s ease',
      marginBottom: '1rem',
      display: 'flex',
      alignItems: 'center',
      gap: '0.5rem'
    });

    btn.addEventListener('click', () => {
      const isExpanded = btn.getAttribute('aria-expanded') === 'true';
      this.collapseGroup(group, !isExpanded);

      btn.setAttribute('aria-expanded', !isExpanded);
      btn.querySelector('.icon').textContent = isExpanded ? '▼' : '▲';
      btn.querySelector('.text').textContent = isExpanded ? `Show ${group.items.length} commits` : `Hide ${group.items.length} commits`;
    });

    return btn;
  }

  collapseGroup(group, expand = true) {
    group.items.forEach((item, i) => {
      if (expand) {
        setTimeout(() => {
          item.style.display = '';
          item.style.opacity = '1';
          item.style.transform = 'translateY(0)';
        }, i * 30);
      } else {
        item.style.opacity = '0';
        item.style.transform = 'translateY(-10px)';
        setTimeout(() => {
          item.style.display = 'none';
        }, 300);
      }
    });

    if (expand) {
      this.state.expandedGroups.add(group.id);
    } else {
      this.state.expandedGroups.delete(group.id);
    }
  }

  // === #9: ACCORDION SLIDE ===
  // Smooth height animation for details (max-height 0 → 2000px)

  setupAccordionSlide() {
    if (!this.options.enableAccordion) return;

    const accordions = document.querySelectorAll('.commit-content, .impact-card, .phase-card');

    accordions.forEach(accordion => {
      const expandable = accordion.querySelector('.commit-expanded, .card-back, .commit-files');

      if (expandable) {
        expandable.style.maxHeight = '0';
        expandable.style.overflow = 'hidden';
        expandable.style.transition = 'max-height 0.4s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.4s ease';
        expandable.style.opacity = '0';
      }

      accordion.addEventListener('click', (e) => {
        // Don't trigger on button clicks
        if (e.target.tagName === 'BUTTON') return;

        this.toggleAccordion(accordion);
      });
    });
  }

  toggleAccordion(accordion) {
    const expandable = accordion.querySelector('.commit-expanded, .card-back, .commit-files');
    if (!expandable) return;

    const isOpen = expandable.style.maxHeight !== '0px' && expandable.style.maxHeight !== '';

    if (isOpen) {
      expandable.style.maxHeight = '0';
      expandable.style.opacity = '0';
      accordion.classList.remove('open');
      accordion.setAttribute('aria-expanded', 'false');
    } else {
      // Calculate content height
      expandable.style.maxHeight = 'none';
      const height = expandable.scrollHeight;
      expandable.style.maxHeight = '0';

      // Trigger reflow
      expandable.offsetHeight;

      expandable.style.maxHeight = `${height}px`;
      expandable.style.opacity = '1';
      accordion.classList.add('open');
      accordion.setAttribute('aria-expanded', 'true');
    }
  }

  // === #10: COPY COMMIT HASH FEEDBACK ===
  // Ripple + checkmark animation

  setupCopyFeedback() {
    if (!this.options.enableCopyFeedback) return;

    const hashes = document.querySelectorAll('.commit-hash, .commit-meta');

    hashes.forEach(hash => {
      hash.style.cursor = 'pointer';
      hash.style.position = 'relative';
      hash.style.userSelect = 'none';

      hash.addEventListener('click', async (e) => {
        e.stopPropagation();
        const text = hash.textContent.trim().split(' ')[0]; // Extract hash only

        try {
          await navigator.clipboard.writeText(text);
          this.showCopyFeedback(hash);
          this.announceToScreenReader(`Copied ${text} to clipboard`);
        } catch (err) {
          console.error('Failed to copy:', err);
          this.announceToScreenReader('Failed to copy to clipboard');
        }
      });
    });
  }

  showCopyFeedback(element) {
    // Create ripple
    const ripple = document.createElement('div');
    ripple.className = 'copy-ripple';

    Object.assign(ripple.style, {
      position: 'absolute',
      top: '50%',
      left: '50%',
      width: '0',
      height: '0',
      borderRadius: '50%',
      background: 'rgba(212, 175, 55, 0.5)',
      transform: 'translate(-50%, -50%)',
      pointerEvents: 'none',
      zIndex: '10'
    });

    element.appendChild(ripple);

    // Animate ripple
    ripple.animate([
      { width: '0', height: '0', opacity: 1 },
      { width: '100px', height: '100px', opacity: 0 }
    ], {
      duration: 600,
      easing: 'cubic-bezier(0.16, 1, 0.3, 1)'
    }).onfinish = () => ripple.remove();

    // Create checkmark
    const checkmark = document.createElement('div');
    checkmark.innerHTML = '✓';
    checkmark.className = 'copy-checkmark';

    Object.assign(checkmark.style, {
      position: 'absolute',
      top: '-30px',
      left: '50%',
      transform: 'translateX(-50%) scale(0)',
      color: 'var(--green, #30D158)',
      fontSize: '1.5rem',
      fontWeight: 'bold',
      pointerEvents: 'none',
      zIndex: '11'
    });

    element.appendChild(checkmark);

    // Animate checkmark
    checkmark.animate([
      { transform: 'translateX(-50%) translateY(10px) scale(0)', opacity: 0 },
      { transform: 'translateX(-50%) translateY(0) scale(1)', opacity: 1, offset: 0.3 },
      { transform: 'translateX(-50%) translateY(-10px) scale(1)', opacity: 1, offset: 0.7 },
      { transform: 'translateX(-50%) translateY(-20px) scale(0.8)', opacity: 0 }
    ], {
      duration: 1000,
      easing: 'cubic-bezier(0.34, 1.56, 0.64, 1)'
    }).onfinish = () => checkmark.remove();
  }

  // === #11: HERO STATS ODOMETER ===
  // Numbers count up from 0 (easeOutExpo, 1.5-2s duration)

  setupHeroOdometer() {
    if (!this.options.enableOdometer) return;

    const stats = document.querySelectorAll('.stat-value, .hero-counter, .impact-stat');

    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting && !entry.target.dataset.animated) {
          entry.target.dataset.animated = 'true';
          this.animateOdometer(entry.target);
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.5 });

    stats.forEach(stat => observer.observe(stat));
    this.observers.set('odometer', observer);
  }

  animateOdometer(element) {
    const text = element.textContent.trim();
    const match = text.match(/([+-]?)(\d+(?:,\d+)?(?:\.\d+)?)/);

    if (!match) return;

    const prefix = match[1];
    const numberStr = match[2].replace(/,/g, '');
    const targetValue = parseFloat(numberStr);
    const suffix = text.replace(match[0], '').trim();
    const hasDecimal = numberStr.includes('.');
    const hasCommas = match[2].includes(',');

    const duration = 2000;
    const start = performance.now();

    const animate = (time) => {
      const elapsed = time - start;
      const progress = Math.min(elapsed / duration, 1);
      const easedProgress = this.easeOutExpo(progress);

      let currentValue = targetValue * easedProgress;

      // Format number
      let formatted;
      if (hasDecimal) {
        formatted = currentValue.toFixed(1);
      } else {
        formatted = Math.floor(currentValue).toString();
      }

      if (hasCommas) {
        formatted = formatted.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
      }

      element.textContent = `${prefix}${formatted}${suffix}`;

      if (progress < 1) {
        requestAnimationFrame(animate);
      } else {
        element.textContent = text; // Restore original
      }
    };

    requestAnimationFrame(animate);
  }

  // === #12: SCROLL TO TOP ROCKET ===
  // Animated scroll button (appears after 300px scroll)

  setupScrollRocket() {
    if (!this.options.enableScrollRocket) return;

    const rocket = this.createScrollRocket();
    document.body.appendChild(rocket);

    let lastScrollY = 0;
    let ticking = false;

    const handleScroll = () => {
      lastScrollY = window.pageYOffset;

      if (!ticking) {
        requestAnimationFrame(() => {
          if (lastScrollY > 300) {
            rocket.style.opacity = '1';
            rocket.style.transform = 'translateY(0)';
            rocket.style.pointerEvents = 'auto';
          } else {
            rocket.style.opacity = '0';
            rocket.style.transform = 'translateY(20px)';
            rocket.style.pointerEvents = 'none';
          }
          ticking = false;
        });
        ticking = true;
      }
    };

    window.addEventListener('scroll', handleScroll, { passive: true });

    rocket.addEventListener('click', () => {
      // Animate rocket launch
      rocket.style.transform = 'translateY(-1000px) rotate(45deg)';
      rocket.style.transition = 'transform 1s cubic-bezier(0.16, 1, 0.3, 1)';

      window.scrollTo({ top: 0, behavior: 'smooth' });

      setTimeout(() => {
        rocket.style.transition = 'none';
        rocket.style.transform = 'translateY(20px)';

        setTimeout(() => {
          rocket.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
        }, 50);
      }, 1000);
    });
  }

  createScrollRocket() {
    const rocket = document.createElement('button');
    rocket.className = 'scroll-rocket';
    rocket.innerHTML = '🚀';
    rocket.setAttribute('aria-label', 'Scroll to top');

    Object.assign(rocket.style, {
      position: 'fixed',
      bottom: '2rem',
      right: '2rem',
      width: '56px',
      height: '56px',
      borderRadius: '50%',
      background: 'linear-gradient(135deg, rgba(212, 175, 55, 0.9), rgba(212, 175, 55, 0.7))',
      border: '2px solid rgba(212, 175, 55, 0.4)',
      fontSize: '1.8rem',
      cursor: 'pointer',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      opacity: '0',
      transform: 'translateY(20px)',
      transition: 'opacity 0.3s ease, transform 0.3s ease',
      pointerEvents: 'none',
      zIndex: '100',
      boxShadow: '0 8px 24px rgba(212, 175, 55, 0.3)'
    });

    // Hover effect
    rocket.addEventListener('mouseenter', () => {
      rocket.style.transform = 'translateY(-4px) scale(1.05)';
      rocket.style.boxShadow = '0 12px 32px rgba(212, 175, 55, 0.4)';
    });

    rocket.addEventListener('mouseleave', () => {
      rocket.style.transform = 'translateY(0) scale(1)';
      rocket.style.boxShadow = '0 8px 24px rgba(212, 175, 55, 0.3)';
    });

    return rocket;
  }

  // === KEYBOARD NAVIGATION ===

  setupKeyboardNav() {
    document.addEventListener('keydown', (e) => {
      // Escape key: Close all accordions
      if (e.key === 'Escape') {
        const openAccordions = document.querySelectorAll('[aria-expanded="true"]');
        openAccordions.forEach(acc => this.toggleAccordion(acc));
      }

      // C key: Toggle compact mode
      if (e.key === 'c' && !e.ctrlKey && !e.metaKey) {
        const toggle = document.querySelector('.compact-toggle');
        if (toggle) toggle.click();
      }

      // / key: Focus filter bar
      if (e.key === '/') {
        e.preventDefault();
        const firstFilter = document.querySelector('.filter-pill');
        if (firstFilter) firstFilter.focus();
      }

      // Space/Enter on cards
      if (e.key === ' ' || e.key === 'Enter') {
        if (e.target.classList.contains('commit-content') ||
            e.target.classList.contains('impact-card')) {
          e.preventDefault();
          this.toggleAccordion(e.target);
        }
      }
    });
  }

  // === UTILITY METHODS ===

  selectCards() {
    return Array.from(document.querySelectorAll('.commit-item, .commit-content, .impact-card, .stat, .feature-item'));
  }

  getCommitContainer() {
    return document.querySelector('.commit-timeline, .section-flow, .content-wide');
  }

  getScrollContainer() {
    return document.querySelector('.panel-scroll') || window;
  }

  createSentinel() {
    const sentinel = document.createElement('div');
    sentinel.className = 'scroll-sentinel';
    sentinel.style.height = '1px';
    sentinel.style.width = '100%';
    sentinel.style.pointerEvents = 'none';
    return sentinel;
  }

  generateCommitCards(count) {
    // Stub implementation - in production, fetch from API
    const cards = [];
    const types = ['feat', 'fix', 'perf', 'docs', 'refactor', 'test'];
    const colors = {
      feat: '#30D158',
      fix: '#FF2D55',
      perf: '#0A84FF',
      docs: '#FFD60A',
      refactor: '#AF52DE',
      test: '#FF9500'
    };

    for (let i = 0; i < count; i++) {
      const type = types[Math.floor(Math.random() * types.length)];
      const card = document.createElement('div');
      card.className = 'commit-item';
      card.dataset.type = type;
      card.style.setProperty('--commit-color', colors[type]);

      card.innerHTML = `
        <div class="commit-dot"></div>
        <div class="commit-content">
          <span class="commit-type">${type}</span>
          <div class="commit-title">Sample commit ${this.state.visibleCommits + i + 1}</div>
          <div class="commit-meta">abc123${i} • ${new Date().toLocaleTimeString()}</div>
          <div class="commit-stats">
            <span class="commit-stats-add">+${Math.floor(Math.random() * 500)}</span>
            <span class="commit-stats-del">-${Math.floor(Math.random() * 200)}</span>
          </div>
        </div>
      `;

      cards.push(card);
    }

    return cards;
  }

  announceToScreenReader(message) {
    let liveRegion = document.getElementById('sr-live-region');

    if (!liveRegion) {
      liveRegion = document.createElement('div');
      liveRegion.id = 'sr-live-region';
      liveRegion.setAttribute('role', 'status');
      liveRegion.setAttribute('aria-live', 'polite');
      liveRegion.setAttribute('aria-atomic', 'true');
      liveRegion.style.position = 'absolute';
      liveRegion.style.left = '-10000px';
      liveRegion.style.width = '1px';
      liveRegion.style.height = '1px';
      liveRegion.style.overflow = 'hidden';
      document.body.appendChild(liveRegion);
    }

    liveRegion.textContent = message;
  }

  delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  easeOutExpo(t) {
    return t === 1 ? 1 : 1 - Math.pow(2, -10 * t);
  }

  // === CLEANUP ===

  destroy() {
    // Cancel all animation frames
    this.rafIds.forEach(id => cancelAnimationFrame(id));
    this.rafIds.clear();

    // Disconnect all observers
    this.observers.forEach(observer => observer.disconnect());
    this.observers.clear();

    // Remove injected elements
    document.querySelectorAll('.compact-toggle, .scroll-rocket, .filter-bar, .scroll-sentinel, #sr-live-region').forEach(el => el.remove());
  }
}

// === INITIALIZATION ===

// Auto-initialize on DOMContentLoaded
if (typeof document !== 'undefined') {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      window.changelogMicrointeractions = new ChangelogMicrointeractions();
    });
  } else {
    window.changelogMicrointeractions = new ChangelogMicrointeractions();
  }
}

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
  module.exports = ChangelogMicrointeractions;
}
