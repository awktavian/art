/**
 * Kagami Documentation JavaScript
 *
 * Interactivity for the documentation site.
 * Search, copy-to-clipboard, theme toggle, and more.
 *
 * 鏡
 */

(function() {
  'use strict';

  // ═══════════════════════════════════════════════════════════════════════════
  // SIDEBAR NAVIGATION
  // ═══════════════════════════════════════════════════════════════════════════

  const sidebar = document.querySelector('.prism-docs__sidebar');
  const menuBtn = document.querySelector('.prism-docs__menu-btn');

  if (menuBtn && sidebar) {
    menuBtn.addEventListener('click', () => {
      sidebar.classList.toggle('prism-docs__sidebar--open');
      menuBtn.setAttribute('aria-expanded',
        sidebar.classList.contains('prism-docs__sidebar--open'));
    });

    // Close sidebar when clicking outside on mobile
    document.addEventListener('click', (e) => {
      if (window.innerWidth <= 768 &&
          !sidebar.contains(e.target) &&
          !menuBtn.contains(e.target)) {
        sidebar.classList.remove('prism-docs__sidebar--open');
        menuBtn.setAttribute('aria-expanded', 'false');
      }
    });
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // SEARCH FUNCTIONALITY
  // ═══════════════════════════════════════════════════════════════════════════

  const searchInput = document.querySelector('.prism-docs__search-input');
  const navLinks = document.querySelectorAll('.prism-docs__nav-link');

  if (searchInput && navLinks.length) {
    searchInput.addEventListener('input', (e) => {
      const query = e.target.value.toLowerCase().trim();

      navLinks.forEach(link => {
        const text = link.textContent.toLowerCase();
        const item = link.closest('.prism-docs__nav-item');

        if (query === '' || text.includes(query)) {
          if (item) item.style.display = '';
        } else {
          if (item) item.style.display = 'none';
        }
      });
    });

    // Keyboard shortcut: / to focus search
    document.addEventListener('keydown', (e) => {
      if (e.key === '/' &&
          document.activeElement.tagName !== 'INPUT' &&
          document.activeElement.tagName !== 'TEXTAREA') {
        e.preventDefault();
        searchInput.focus();
      }
    });
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // COPY TO CLIPBOARD
  // ═══════════════════════════════════════════════════════════════════════════

  function copyToClipboard(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text);
    }

    // Fallback for older browsers
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand('copy');
    document.body.removeChild(textarea);
    return Promise.resolve();
  }

  // Copy code blocks
  document.querySelectorAll('.prism-docs__code-copy').forEach(btn => {
    btn.addEventListener('click', async () => {
      const codeBlock = btn.closest('.prism-docs__code');
      const code = codeBlock.querySelector('code');

      if (code) {
        try {
          await copyToClipboard(code.textContent);
          btn.textContent = 'Copied!';
          btn.classList.add('prism-docs__code-copy--copied');

          setTimeout(() => {
            btn.textContent = 'Copy';
            btn.classList.remove('prism-docs__code-copy--copied');
          }, 2000);
        } catch (err) {
          console.error('Failed to copy:', err);
        }
      }
    });
  });

  // Copy token values
  document.querySelectorAll('.prism-docs__token').forEach(token => {
    token.addEventListener('click', async () => {
      const tokenName = token.querySelector('.prism-docs__token-name');
      const copyHint = token.querySelector('.prism-docs__token-copy');

      if (tokenName) {
        try {
          await copyToClipboard(tokenName.textContent);
          if (copyHint) {
            const originalText = copyHint.textContent;
            copyHint.textContent = 'Copied!';
            copyHint.style.opacity = '1';

            setTimeout(() => {
              copyHint.textContent = originalText;
              copyHint.style.opacity = '';
            }, 2000);
          }
        } catch (err) {
          console.error('Failed to copy:', err);
        }
      }
    });
  });

  // Copy color cards
  document.querySelectorAll('.prism-docs__color-card').forEach(card => {
    card.addEventListener('click', async () => {
      const hex = card.querySelector('.prism-docs__color-hex');

      if (hex) {
        try {
          await copyToClipboard(hex.textContent);

          // Visual feedback
          const originalBg = card.style.background;
          card.style.outline = '2px solid var(--prism-nexus)';

          setTimeout(() => {
            card.style.outline = '';
          }, 500);
        } catch (err) {
          console.error('Failed to copy:', err);
        }
      }
    });
  });

  // ═══════════════════════════════════════════════════════════════════════════
  // THEME TOGGLE
  // ═══════════════════════════════════════════════════════════════════════════

  const themeToggle = document.querySelector('.prism-docs__theme-toggle');
  const docsRoot = document.querySelector('.prism-docs');

  function setTheme(theme) {
    if (theme === 'light') {
      docsRoot.classList.add('prism-docs--light');
      localStorage.setItem('prism-docs-theme', 'light');
    } else {
      docsRoot.classList.remove('prism-docs--light');
      localStorage.setItem('prism-docs-theme', 'dark');
    }
    updateThemeToggleText();
  }

  function updateThemeToggleText() {
    if (themeToggle) {
      const isLight = docsRoot.classList.contains('prism-docs--light');
      themeToggle.innerHTML = isLight ?
        '<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/></svg> Dark' :
        '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg> Light';
    }
  }

  if (themeToggle && docsRoot) {
    // Load saved theme
    const savedTheme = localStorage.getItem('prism-docs-theme');
    if (savedTheme) {
      setTheme(savedTheme);
    }
    updateThemeToggleText();

    themeToggle.addEventListener('click', () => {
      const isLight = docsRoot.classList.contains('prism-docs--light');
      setTheme(isLight ? 'dark' : 'light');
    });
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // PLATFORM PREVIEW TOGGLE
  // ═══════════════════════════════════════════════════════════════════════════

  const platformTabs = document.querySelectorAll('.prism-docs__platform-tab');
  const platformPreviews = document.querySelectorAll('[data-platform]');

  if (platformTabs.length && platformPreviews.length) {
    platformTabs.forEach(tab => {
      tab.addEventListener('click', () => {
        const platform = tab.dataset.platform;

        // Update active tab
        platformTabs.forEach(t => t.classList.remove('prism-docs__platform-tab--active'));
        tab.classList.add('prism-docs__platform-tab--active');

        // Show/hide platform-specific content
        platformPreviews.forEach(preview => {
          if (preview.dataset.platform === platform || preview.dataset.platform === 'all') {
            preview.style.display = '';
          } else {
            preview.style.display = 'none';
          }
        });
      });
    });
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // STATE TOGGLING FOR PREVIEWS
  // ═══════════════════════════════════════════════════════════════════════════

  document.querySelectorAll('[data-state-toggle]').forEach(toggle => {
    toggle.addEventListener('click', () => {
      const targetId = toggle.dataset.stateToggle;
      const target = document.getElementById(targetId);
      const state = toggle.dataset.state;

      if (target && state) {
        // Remove all state classes
        const stateClasses = target.className.split(' ')
          .filter(c => c.includes('--'));
        stateClasses.forEach(c => target.classList.remove(c));

        // Add new state
        if (state !== 'default') {
          target.classList.add(`${target.classList[0]}--${state}`);
        }

        // Update toggle buttons
        const siblings = toggle.parentElement.querySelectorAll('[data-state-toggle]');
        siblings.forEach(s => s.classList.remove('prism-docs__platform-tab--active'));
        toggle.classList.add('prism-docs__platform-tab--active');
      }
    });
  });

  // ═══════════════════════════════════════════════════════════════════════════
  // INTERACTIVE COMPONENT DEMOS
  // ═══════════════════════════════════════════════════════════════════════════

  // Button ripple effect
  document.querySelectorAll('.prism-button').forEach(button => {
    button.addEventListener('click', function(e) {
      // Only add ripple if the button doesn't already have custom click handling
      if (!this.dataset.noRipple) {
        const rect = this.getBoundingClientRect();
        const ripple = document.createElement('span');
        ripple.className = 'prism-ripple__wave';
        ripple.style.left = (e.clientX - rect.left) + 'px';
        ripple.style.top = (e.clientY - rect.top) + 'px';
        ripple.style.width = ripple.style.height = Math.max(rect.width, rect.height) + 'px';

        this.appendChild(ripple);

        setTimeout(() => ripple.remove(), 800);
      }
    });
  });

  // Modal demo
  document.querySelectorAll('[data-modal-trigger]').forEach(trigger => {
    trigger.addEventListener('click', () => {
      const modalId = trigger.dataset.modalTrigger;
      const modal = document.getElementById(modalId);
      if (modal) {
        modal.classList.add('prism-modal-backdrop--open');
      }
    });
  });

  document.querySelectorAll('.prism-modal-backdrop').forEach(backdrop => {
    backdrop.addEventListener('click', (e) => {
      if (e.target === backdrop) {
        backdrop.classList.remove('prism-modal-backdrop--open');
      }
    });
  });

  document.querySelectorAll('.prism-modal__close').forEach(closeBtn => {
    closeBtn.addEventListener('click', () => {
      const backdrop = closeBtn.closest('.prism-modal-backdrop');
      if (backdrop) {
        backdrop.classList.remove('prism-modal-backdrop--open');
      }
    });
  });

  // Escape key closes modals
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      document.querySelectorAll('.prism-modal-backdrop--open').forEach(modal => {
        modal.classList.remove('prism-modal-backdrop--open');
      });
    }
  });

  // ═══════════════════════════════════════════════════════════════════════════
  // SMOOTH SCROLL FOR ANCHOR LINKS
  // ═══════════════════════════════════════════════════════════════════════════

  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
      const targetId = this.getAttribute('href');
      if (targetId === '#') return;

      const target = document.querySelector(targetId);
      if (target) {
        e.preventDefault();
        target.scrollIntoView({
          behavior: 'smooth',
          block: 'start'
        });

        // Update URL without jumping
        history.pushState(null, null, targetId);
      }
    });
  });

  // ═══════════════════════════════════════════════════════════════════════════
  // ACTIVE NAV LINK HIGHLIGHTING
  // ═══════════════════════════════════════════════════════════════════════════

  function updateActiveNavLink() {
    const currentPath = window.location.pathname;

    document.querySelectorAll('.prism-docs__nav-link').forEach(link => {
      link.classList.remove('prism-docs__nav-link--active');

      const href = link.getAttribute('href');
      if (href && currentPath.endsWith(href.replace('./', ''))) {
        link.classList.add('prism-docs__nav-link--active');
      }
    });
  }

  updateActiveNavLink();

  // ═══════════════════════════════════════════════════════════════════════════
  // CODE SYNTAX HIGHLIGHTING (Basic)
  // ═══════════════════════════════════════════════════════════════════════════

  function highlightCode() {
    document.querySelectorAll('.prism-docs__code code').forEach(block => {
      let html = block.innerHTML;

      // HTML tags
      html = html.replace(/(&lt;\/?[\w-]+)/g, '<span class="token-tag">$1</span>');

      // Attributes
      html = html.replace(/\s([\w-]+)=/g, ' <span class="token-attr">$1</span>=');

      // Strings
      html = html.replace(/"([^"]*)"/g, '<span class="token-string">"$1"</span>');

      // Comments
      html = html.replace(/(\/\*[\s\S]*?\*\/|\/\/.*)/g, '<span class="token-comment">$1</span>');

      // CSS properties
      html = html.replace(/(--[\w-]+)/g, '<span class="token-keyword">$1</span>');

      block.innerHTML = html;
    });
  }

  highlightCode();

  // ═══════════════════════════════════════════════════════════════════════════
  // GLOBAL SEARCH (Cmd/Ctrl + K)
  // ═══════════════════════════════════════════════════════════════════════════

  document.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
      e.preventDefault();
      const searchInput = document.querySelector('.prism-docs__search-input');
      if (searchInput) {
        searchInput.focus();
        searchInput.select();
      }
    }
  });

  // ═══════════════════════════════════════════════════════════════════════════
  // INITIALIZATION COMPLETE
  // ═══════════════════════════════════════════════════════════════════════════

  console.log('Kagami Docs initialized');

})();
