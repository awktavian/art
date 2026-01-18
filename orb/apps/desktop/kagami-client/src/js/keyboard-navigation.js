/**
 * KEYBOARD NAVIGATION MODULE
 * Full keyboard navigation support for Kagami Desktop
 *
 * Focus:
 *
 * Features:
 * 1. Command palette (Cmd+K / Ctrl+K)
 * 2. Global keyboard shortcuts
 * 3. Focus management
 * 4. Skip links and landmarks
 * 5. Vim-like navigation (optional)
 *
 *
 */

// ================================================================
// 1. KEYBOARD SHORTCUT REGISTRY
// ================================================================

const shortcuts = new Map();
const modifiers = {
  ctrl: 'ctrlKey',
  cmd: 'metaKey',
  alt: 'altKey',
  shift: 'shiftKey',
};

/**
 * Parse a shortcut string into components
 * @param {string} shortcut - e.g., "cmd+k", "ctrl+shift+p"
 * @returns {Object} Parsed shortcut object
 */
function parseShortcut(shortcut) {
  const parts = shortcut.toLowerCase().split('+');
  const key = parts.pop();
  const mods = new Set(parts);

  return {
    key,
    ctrl: mods.has('ctrl'),
    cmd: mods.has('cmd'),
    alt: mods.has('alt'),
    shift: mods.has('shift'),
    // Platform-aware: cmd on macOS, ctrl on others
    mod: mods.has('mod'),
  };
}

/**
 * Check if event matches shortcut
 * @param {KeyboardEvent} event
 * @param {Object} shortcut - Parsed shortcut
 * @returns {boolean}
 */
function matchesShortcut(event, shortcut) {
  const isMac = navigator.platform.includes('Mac');

  // Handle platform-agnostic 'mod' key
  const modKey = shortcut.mod
    ? (isMac ? event.metaKey : event.ctrlKey)
    : true;

  const ctrlMatch = shortcut.ctrl ? event.ctrlKey : !event.ctrlKey || shortcut.mod;
  const cmdMatch = shortcut.cmd ? event.metaKey : !event.metaKey || shortcut.mod;

  return (
    event.key.toLowerCase() === shortcut.key &&
    (shortcut.mod ? modKey : (ctrlMatch && cmdMatch)) &&
    (shortcut.alt ? event.altKey : !event.altKey) &&
    (shortcut.shift ? event.shiftKey : !event.shiftKey)
  );
}

/**
 * Register a keyboard shortcut
 * @param {string} shortcut - Shortcut string (e.g., "mod+k")
 * @param {Function} handler - Handler function
 * @param {Object} options - Options
 */
function registerShortcut(shortcut, handler, options = {}) {
  const parsed = parseShortcut(shortcut);
  const id = options.id || shortcut;

  shortcuts.set(id, {
    shortcut: parsed,
    handler,
    description: options.description || '',
    category: options.category || 'General',
    enabled: options.enabled !== false,
  });
}

/**
 * Unregister a keyboard shortcut
 * @param {string} id - Shortcut ID or string
 */
function unregisterShortcut(id) {
  shortcuts.delete(id);
}

/**
 * Get all registered shortcuts (for help display)
 * @returns {Array} List of shortcuts with descriptions
 */
function getShortcuts() {
  const result = [];
  shortcuts.forEach((value, key) => {
    if (value.enabled) {
      result.push({
        id: key,
        shortcut: key,
        description: value.description,
        category: value.category,
      });
    }
  });
  return result;
}

// ================================================================
// 2. GLOBAL KEYBOARD HANDLER
// ================================================================

let keyboardNavEnabled = true;

function handleGlobalKeydown(event) {
  if (!keyboardNavEnabled) return;

  // Don't intercept when typing in inputs (unless it's a global shortcut)
  const isInput = event.target.matches('input, textarea, [contenteditable]');

  for (const [id, registration] of shortcuts) {
    if (!registration.enabled) continue;
    if (!matchesShortcut(event, registration.shortcut)) continue;

    // Allow input typing unless it's explicitly a global shortcut
    if (isInput && !registration.shortcut.mod && !registration.shortcut.ctrl) {
      continue;
    }

    event.preventDefault();
    event.stopPropagation();
    registration.handler(event);
    return;
  }
}

// ================================================================
// 3. COMMAND PALETTE
// ================================================================

let commandPaletteOpen = false;
let commandPaletteElement = null;
let commands = [];
let filteredCommands = [];
let selectedIndex = 0;

/**
 * Register a command for the command palette
 * @param {Object} command - Command definition
 */
function registerCommand(command) {
  commands.push({
    id: command.id,
    title: command.title,
    description: command.description || '',
    category: command.category || 'General',
    icon: command.icon || null,
    shortcut: command.shortcut || null,
    handler: command.handler,
    enabled: command.enabled !== false,
  });
}

/**
 * Open the command palette
 */
function openCommandPalette() {
  if (commandPaletteOpen) return;

  commandPaletteOpen = true;
  filteredCommands = commands.filter(c => c.enabled);
  selectedIndex = 0;

  // Create or show the palette
  createCommandPaletteUI();

  // Announce to screen readers
  if (window.Accessibility) {
    window.Accessibility.announce('Command palette opened. Type to search commands.');
  }
}

/**
 * Close the command palette
 */
function closeCommandPalette() {
  if (!commandPaletteOpen) return;

  commandPaletteOpen = false;
  if (commandPaletteElement) {
    commandPaletteElement.classList.remove('visible');
    setTimeout(() => {
      if (commandPaletteElement && !commandPaletteOpen) {
        commandPaletteElement.remove();
        commandPaletteElement = null;
      }
    }, 200); // Match animation duration
  }

  if (window.Accessibility) {
    window.Accessibility.announce('Command palette closed.');
  }
}

/**
 * Toggle command palette
 */
function toggleCommandPalette() {
  if (commandPaletteOpen) {
    closeCommandPalette();
  } else {
    openCommandPalette();
  }
}

/**
 * Create the command palette UI
 */
function createCommandPaletteUI() {
  if (commandPaletteElement) {
    commandPaletteElement.classList.add('visible');
    const input = commandPaletteElement.querySelector('.command-palette__input');
    if (input) {
      input.focus();
      input.select();
    }
    return;
  }

  // Create backdrop
  const backdrop = document.createElement('div');
  backdrop.className = 'command-palette-backdrop';
  backdrop.addEventListener('click', closeCommandPalette);

  // Create palette container
  const palette = document.createElement('div');
  palette.className = 'command-palette visible';
  palette.setAttribute('role', 'dialog');
  palette.setAttribute('aria-modal', 'true');
  palette.setAttribute('aria-label', 'Command palette');

  palette.innerHTML = `
    <div class="command-palette__header">
      <svg class="command-palette__search-icon" width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
        <path d="M11.742 10.344a6.5 6.5 0 1 0-1.397 1.398h-.001c.03.04.062.078.098.115l3.85 3.85a1 1 0 0 0 1.415-1.414l-3.85-3.85a1.007 1.007 0 0 0-.115-.1zM12 6.5a5.5 5.5 0 1 1-11 0 5.5 5.5 0 0 1 11 0z"/>
      </svg>
      <input
        type="text"
        class="command-palette__input"
        placeholder="Type a command..."
        aria-label="Search commands"
        autocomplete="off"
        autocapitalize="off"
        spellcheck="false"
      />
      <kbd class="command-palette__hint">ESC</kbd>
    </div>
    <div class="command-palette__list" role="listbox" aria-label="Commands"></div>
    <div class="command-palette__footer">
      <span class="command-palette__footer-hint">
        <kbd>↑↓</kbd> navigate
        <kbd>↵</kbd> select
        <kbd>esc</kbd> close
      </span>
    </div>
  `;

  // Add event listeners
  const input = palette.querySelector('.command-palette__input');
  const list = palette.querySelector('.command-palette__list');

  input.addEventListener('input', (e) => {
    filterCommands(e.target.value);
    renderCommandList(list);
  });

  input.addEventListener('keydown', (e) => {
    handleCommandPaletteKeydown(e, list);
  });

  // Prevent backdrop click from bubbling
  palette.addEventListener('click', (e) => e.stopPropagation());

  document.body.appendChild(backdrop);
  document.body.appendChild(palette);
  commandPaletteElement = palette;

  // Render initial list
  renderCommandList(list);

  // Focus input
  input.focus();

  // Set up focus trap
  if (window.Accessibility) {
    const trap = window.Accessibility.createFocusTrap(palette);
    trap.activate();
    palette._focusTrap = trap;
  }
}

/**
 * Filter commands based on query
 * @param {string} query
 */
function filterCommands(query) {
  const q = query.toLowerCase().trim();
  if (!q) {
    filteredCommands = commands.filter(c => c.enabled);
  } else {
    filteredCommands = commands.filter(c => {
      if (!c.enabled) return false;
      const titleMatch = c.title.toLowerCase().includes(q);
      const descMatch = c.description.toLowerCase().includes(q);
      const catMatch = c.category.toLowerCase().includes(q);
      return titleMatch || descMatch || catMatch;
    });
  }
  selectedIndex = 0;
}

/**
 * Render command list
 * @param {HTMLElement} container
 */
function renderCommandList(container) {
  if (!filteredCommands.length) {
    container.innerHTML = `
      <div class="command-palette__empty">
        No commands found
      </div>
    `;
    return;
  }

  // Group by category
  const grouped = {};
  filteredCommands.forEach(cmd => {
    if (!grouped[cmd.category]) {
      grouped[cmd.category] = [];
    }
    grouped[cmd.category].push(cmd);
  });

  let html = '';
  let globalIndex = 0;

  for (const [category, cmds] of Object.entries(grouped)) {
    html += `<div class="command-palette__category">${category}</div>`;
    for (const cmd of cmds) {
      const isSelected = globalIndex === selectedIndex;
      html += `
        <div
          class="command-palette__item ${isSelected ? 'selected' : ''}"
          role="option"
          aria-selected="${isSelected}"
          data-index="${globalIndex}"
          data-command-id="${cmd.id}"
        >
          ${cmd.icon ? `<span class="command-palette__icon">${cmd.icon}</span>` : ''}
          <span class="command-palette__title">${cmd.title}</span>
          ${cmd.description ? `<span class="command-palette__description">${cmd.description}</span>` : ''}
          ${cmd.shortcut ? `<kbd class="command-palette__shortcut">${formatShortcut(cmd.shortcut)}</kbd>` : ''}
        </div>
      `;
      globalIndex++;
    }
  }

  container.innerHTML = html;

  // Add click handlers
  container.querySelectorAll('.command-palette__item').forEach(item => {
    item.addEventListener('click', () => {
      const idx = parseInt(item.dataset.index, 10);
      executeCommand(idx);
    });
  });

  // Scroll selected into view
  const selected = container.querySelector('.command-palette__item.selected');
  if (selected) {
    selected.scrollIntoView({ block: 'nearest' });
  }
}

/**
 * Format shortcut for display
 * @param {string} shortcut
 * @returns {string}
 */
function formatShortcut(shortcut) {
  const isMac = navigator.platform.includes('Mac');
  return shortcut
    .replace(/mod/gi, isMac ? '⌘' : 'Ctrl')
    .replace(/ctrl/gi, isMac ? '⌃' : 'Ctrl')
    .replace(/alt/gi, isMac ? '⌥' : 'Alt')
    .replace(/shift/gi, isMac ? '⇧' : 'Shift')
    .replace(/\+/g, ' ');
}

/**
 * Handle command palette keyboard navigation
 * @param {KeyboardEvent} event
 * @param {HTMLElement} list
 */
function handleCommandPaletteKeydown(event, list) {
  switch (event.key) {
    case 'ArrowDown':
      event.preventDefault();
      selectedIndex = Math.min(selectedIndex + 1, filteredCommands.length - 1);
      renderCommandList(list);
      break;

    case 'ArrowUp':
      event.preventDefault();
      selectedIndex = Math.max(selectedIndex - 1, 0);
      renderCommandList(list);
      break;

    case 'Enter':
      event.preventDefault();
      executeCommand(selectedIndex);
      break;

    case 'Escape':
      event.preventDefault();
      closeCommandPalette();
      break;

    case 'Tab':
      // Trap focus within palette
      event.preventDefault();
      break;
  }
}

/**
 * Execute selected command
 * @param {number} index
 */
function executeCommand(index) {
  const command = filteredCommands[index];
  if (command && command.handler) {
    closeCommandPalette();
    command.handler();
  }
}

// ================================================================
// 4. FOCUS INDICATORS
// ================================================================

/**
 * Enhanced focus indicator styles
 */
function injectFocusStyles() {
  const styleId = 'kagami-focus-styles';
  if (document.getElementById(styleId)) return;

  const style = document.createElement('style');
  style.id = styleId;
  style.textContent = `
    /* Enhanced focus indicators for keyboard navigation */
    .keyboard-nav :focus-visible {
      outline: 2px solid var(--prism-crystal, #64D2FF);
      outline-offset: 2px;
      border-radius: 4px;
    }

    .keyboard-nav :focus-visible:not(:focus) {
      outline: none;
    }

    /* Skip link */
    .skip-link {
      position: fixed;
      top: -100px;
      left: var(--space-4, 16px);
      z-index: var(--prism-z-toast, 600);
      padding: var(--space-2, 8px) var(--space-4, 16px);
      background: var(--surface-raised, #18181B);
      color: var(--text-primary, #FFFFFF);
      border-radius: var(--radius-sm, 8px);
      text-decoration: none;
      font-weight: var(--prism-weight-medium, 500);
      transition: top var(--prism-dur-fast, 144ms) var(--prism-ease-cusp);
    }

    .skip-link:focus {
      top: var(--space-4, 16px);
    }

    /* Focus ring animation */
    @keyframes focusPulse {
      0%, 100% {
        outline-color: var(--prism-crystal, #64D2FF);
      }
      50% {
        outline-color: color-mix(in srgb, var(--prism-crystal, #64D2FF) 70%, white);
      }
    }

    .keyboard-nav .focus-pulse:focus-visible {
      animation: focusPulse 1.5s ease-in-out infinite;
    }
  `;

  document.head.appendChild(style);
}

// ================================================================
// 5. INITIALIZATION
// ================================================================

/**
 * Initialize keyboard navigation
 */
function initKeyboardNavigation() {
  // Inject focus styles
  injectFocusStyles();

  // Add global keyboard handler
  document.addEventListener('keydown', handleGlobalKeydown);

  // Register default shortcuts
  registerDefaultShortcuts();

  // Register default commands
  registerDefaultCommands();

  // Add skip link if not present
  addSkipLink();

  console.log('%c[KeyboardNav] Initialized', 'color: #64D2FF;');
}

/**
 * Register default keyboard shortcuts
 */
function registerDefaultShortcuts() {
  // Command palette
  registerShortcut('mod+k', toggleCommandPalette, {
    id: 'command-palette',
    description: 'Open command palette',
    category: 'Navigation',
  });

  // Alternative shortcut
  registerShortcut('mod+p', toggleCommandPalette, {
    id: 'command-palette-alt',
    description: 'Open command palette (alt)',
    category: 'Navigation',
  });

  // Theme toggle
  registerShortcut('mod+shift+t', () => {
    const html = document.documentElement;
    const current = html.getAttribute('data-theme');
    html.setAttribute('data-theme', current === 'light' ? 'dark' : 'light');
    if (window.Accessibility) {
      window.Accessibility.announce(`Theme switched to ${current === 'light' ? 'dark' : 'light'} mode`);
    }
  }, {
    id: 'theme-toggle',
    description: 'Toggle light/dark theme',
    category: 'Appearance',
  });

  // Focus search/input
  registerShortcut('/', () => {
    const input = document.querySelector('.composer-input, .command-input, input[type="text"]');
    if (input) {
      input.focus();
    }
  }, {
    id: 'focus-search',
    description: 'Focus search input',
    category: 'Navigation',
  });

  // Escape to close modals
  registerShortcut('Escape', () => {
    // Close command palette if open
    if (commandPaletteOpen) {
      closeCommandPalette();
      return;
    }
    // Close other modals
    const modal = document.querySelector('.modal.visible, [role="dialog"][aria-modal="true"]');
    if (modal) {
      modal.dispatchEvent(new CustomEvent('close-request'));
    }
  }, {
    id: 'close-modal',
    description: 'Close modal/palette',
    category: 'Navigation',
  });
}

/**
 * Register default commands for command palette
 */
function registerDefaultCommands() {
  registerCommand({
    id: 'toggle-theme',
    title: 'Toggle Theme',
    description: 'Switch between light and dark mode',
    category: 'Appearance',
    shortcut: 'mod+shift+T',
    handler: () => {
      const html = document.documentElement;
      const current = html.getAttribute('data-theme');
      html.setAttribute('data-theme', current === 'light' ? 'dark' : 'light');
    },
  });

  registerCommand({
    id: 'reload',
    title: 'Reload Window',
    description: 'Refresh the application',
    category: 'System',
    handler: () => window.location.reload(),
  });

  registerCommand({
    id: 'dev-tools',
    title: 'Toggle Developer Tools',
    description: 'Open browser developer tools',
    category: 'Developer',
    shortcut: 'mod+shift+I',
    handler: () => {
      // Tauri-specific dev tools toggle
      if (window.__TAURI__) {
        window.__TAURI__.invoke('toggle_devtools');
      }
    },
  });

  registerCommand({
    id: 'keyboard-shortcuts',
    title: 'Keyboard Shortcuts',
    description: 'View all keyboard shortcuts',
    category: 'Help',
    shortcut: 'mod+/',
    handler: () => {
      // Show shortcuts help modal
      showShortcutsHelp();
    },
  });

  registerCommand({
    id: 'focus-main',
    title: 'Focus Main Content',
    description: 'Jump to main content area',
    category: 'Navigation',
    handler: () => {
      const main = document.querySelector('main, [role="main"], #main-content');
      if (main) {
        main.focus();
        main.scrollIntoView({ behavior: 'smooth' });
      }
    },
  });
}

/**
 * Add skip link for screen reader users
 */
function addSkipLink() {
  if (document.querySelector('.skip-link')) return;

  const skipLink = document.createElement('a');
  skipLink.className = 'skip-link';
  skipLink.href = '#main-content';
  skipLink.textContent = 'Skip to main content';

  skipLink.addEventListener('click', (e) => {
    e.preventDefault();
    const main = document.querySelector('main, [role="main"], #main-content');
    if (main) {
      main.focus();
      main.scrollIntoView({ behavior: 'smooth' });
    }
  });

  document.body.insertBefore(skipLink, document.body.firstChild);
}

/**
 * Show keyboard shortcuts help modal
 */
function showShortcutsHelp() {
  const shortcuts = getShortcuts();
  const grouped = {};

  shortcuts.forEach(s => {
    if (!grouped[s.category]) {
      grouped[s.category] = [];
    }
    grouped[s.category].push(s);
  });

  let html = '<div class="shortcuts-help">';
  html += '<h2>Keyboard Shortcuts</h2>';

  for (const [category, items] of Object.entries(grouped)) {
    html += `<div class="shortcuts-category">`;
    html += `<h3>${category}</h3>`;
    html += '<ul>';
    items.forEach(item => {
      html += `<li><kbd>${formatShortcut(item.shortcut)}</kbd> ${item.description}</li>`;
    });
    html += '</ul></div>';
  }

  html += '</div>';

  // Create modal
  const modal = document.createElement('div');
  modal.className = 'prism-modal shortcuts-modal visible';
  modal.setAttribute('role', 'dialog');
  modal.setAttribute('aria-modal', 'true');
  modal.setAttribute('aria-label', 'Keyboard shortcuts');
  modal.innerHTML = html;

  const backdrop = document.createElement('div');
  backdrop.className = 'prism-modal-backdrop visible';
  backdrop.addEventListener('click', () => {
    modal.remove();
    backdrop.remove();
  });

  document.body.appendChild(backdrop);
  document.body.appendChild(modal);

  modal.focus();
}

// ================================================================
// EXPORTS
// ================================================================

export const KeyboardNavigation = {
  // Shortcut management
  registerShortcut,
  unregisterShortcut,
  getShortcuts,

  // Command palette
  registerCommand,
  openCommandPalette,
  closeCommandPalette,
  toggleCommandPalette,

  // State
  isCommandPaletteOpen: () => commandPaletteOpen,
  setEnabled: (enabled) => { keyboardNavEnabled = enabled; },
  isEnabled: () => keyboardNavEnabled,

  // Init
  init: initKeyboardNavigation,
};

// Also expose globally
window.KeyboardNavigation = KeyboardNavigation;

// Auto-initialize on DOM ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initKeyboardNavigation);
} else {
  initKeyboardNavigation();
}

/*
 * Keyboard navigation is not optional. It is essential.
 *
 */
