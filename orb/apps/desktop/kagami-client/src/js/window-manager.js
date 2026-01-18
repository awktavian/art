/**
 * WINDOW MANAGER MODULE
 * Desktop window management for Kagami
 *
 * Focus:
 *
 * Features:
 * 1. Floating/companion window mode
 * 2. Window state persistence
 * 3. Multi-window support
 * 4. Snap to edges
 * 5. Always on top toggle
 *
 *
 */

// ================================================================
// 1. CONSTANTS
// ================================================================

const STORAGE_KEY = 'kagami-window-state';
const MIN_WIDTH = 320;
const MIN_HEIGHT = 240;
const SNAP_THRESHOLD = 20;

const WindowMode = {
  NORMAL: 'normal',
  FLOATING: 'floating',
  COMPACT: 'compact',
  FULLSCREEN: 'fullscreen',
};

// ================================================================
// 2. STATE
// ================================================================

let currentState = {
  mode: WindowMode.NORMAL,
  position: { x: 100, y: 100 },
  size: { width: 800, height: 600 },
  alwaysOnTop: false,
  opacity: 1.0,
  lastNormalState: null,
};

let isDragging = false;
let isResizing = false;
let dragOffset = { x: 0, y: 0 };
let resizeHandle = null;

// ================================================================
// 3. WINDOW STATE PERSISTENCE
// ================================================================

/**
 * Save window state to localStorage
 */
function saveState() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(currentState));
  } catch (e) {
    console.warn('[WindowManager] Failed to save state:', e);
  }
}

/**
 * Load window state from localStorage
 */
function loadState() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
      const parsed = JSON.parse(saved);
      currentState = { ...currentState, ...parsed };
      return true;
    }
  } catch (e) {
    console.warn('[WindowManager] Failed to load state:', e);
  }
  return false;
}

/**
 * Reset window state to defaults
 */
function resetState() {
  currentState = {
    mode: WindowMode.NORMAL,
    position: { x: 100, y: 100 },
    size: { width: 800, height: 600 },
    alwaysOnTop: false,
    opacity: 1.0,
    lastNormalState: null,
  };
  saveState();
}

// ================================================================
// 4. TAURI WINDOW API INTEGRATION
// ================================================================

/**
 * Get the Tauri window API
 */
function getTauriWindow() {
  return window.__TAURI__?.window;
}

/**
 * Apply current state to window
 */
async function applyState() {
  const tauri = getTauriWindow();
  if (!tauri) {
    console.warn('[WindowManager] Tauri window API not available');
    return;
  }

  try {
    const appWindow = tauri.getCurrent();

    // Set position
    await appWindow.setPosition(new tauri.LogicalPosition(
      currentState.position.x,
      currentState.position.y
    ));

    // Set size
    await appWindow.setSize(new tauri.LogicalSize(
      currentState.size.width,
      currentState.size.height
    ));

    // Set always on top
    await appWindow.setAlwaysOnTop(currentState.alwaysOnTop);

    // Apply mode-specific settings
    switch (currentState.mode) {
      case WindowMode.FLOATING:
        await applyFloatingMode(appWindow);
        break;
      case WindowMode.COMPACT:
        await applyCompactMode(appWindow);
        break;
      case WindowMode.FULLSCREEN:
        await appWindow.setFullscreen(true);
        break;
      default:
        await appWindow.setDecorations(true);
        await appWindow.setFullscreen(false);
    }
  } catch (e) {
    console.error('[WindowManager] Failed to apply state:', e);
  }
}

/**
 * Apply floating window mode
 */
async function applyFloatingMode(appWindow) {
  await appWindow.setDecorations(false);
  await appWindow.setAlwaysOnTop(true);
  document.body.classList.add('window-floating');
  document.body.classList.remove('window-compact', 'window-normal');
}

/**
 * Apply compact window mode
 */
async function applyCompactMode(appWindow) {
  await appWindow.setDecorations(false);
  await appWindow.setSize(new window.__TAURI__.window.LogicalSize(400, 60));
  document.body.classList.add('window-compact');
  document.body.classList.remove('window-floating', 'window-normal');
}

// ================================================================
// 5. WINDOW MODE SWITCHING
// ================================================================

/**
 * Switch to floating (companion) mode
 */
async function enterFloatingMode() {
  // Save current normal state for restoration
  currentState.lastNormalState = {
    position: { ...currentState.position },
    size: { ...currentState.size },
  };

  currentState.mode = WindowMode.FLOATING;
  currentState.size = { width: 400, height: 500 };
  currentState.alwaysOnTop = true;

  await applyState();
  saveState();

  // Announce to screen readers
  if (window.Accessibility) {
    window.Accessibility.announce('Switched to floating companion mode');
  }

  dispatchWindowEvent('mode-change', { mode: WindowMode.FLOATING });
}

/**
 * Switch to compact mode (minimal bar)
 */
async function enterCompactMode() {
  // Save current state for restoration
  if (currentState.mode === WindowMode.NORMAL) {
    currentState.lastNormalState = {
      position: { ...currentState.position },
      size: { ...currentState.size },
    };
  }

  currentState.mode = WindowMode.COMPACT;
  currentState.size = { width: 400, height: 60 };
  currentState.alwaysOnTop = true;

  await applyState();
  saveState();

  if (window.Accessibility) {
    window.Accessibility.announce('Switched to compact mode');
  }

  dispatchWindowEvent('mode-change', { mode: WindowMode.COMPACT });
}

/**
 * Switch to normal mode
 */
async function enterNormalMode() {
  const tauri = getTauriWindow();

  // Restore previous normal state if available
  if (currentState.lastNormalState) {
    currentState.position = currentState.lastNormalState.position;
    currentState.size = currentState.lastNormalState.size;
  } else {
    currentState.size = { width: 800, height: 600 };
  }

  currentState.mode = WindowMode.NORMAL;
  currentState.alwaysOnTop = false;

  document.body.classList.remove('window-floating', 'window-compact');
  document.body.classList.add('window-normal');

  await applyState();
  saveState();

  if (window.Accessibility) {
    window.Accessibility.announce('Switched to normal mode');
  }

  dispatchWindowEvent('mode-change', { mode: WindowMode.NORMAL });
}

/**
 * Toggle fullscreen mode
 */
async function toggleFullscreen() {
  const tauri = getTauriWindow();
  if (!tauri) return;

  try {
    const appWindow = tauri.getCurrent();
    const isFullscreen = await appWindow.isFullscreen();

    if (isFullscreen) {
      await enterNormalMode();
    } else {
      if (currentState.mode === WindowMode.NORMAL) {
        currentState.lastNormalState = {
          position: { ...currentState.position },
          size: { ...currentState.size },
        };
      }
      currentState.mode = WindowMode.FULLSCREEN;
      await appWindow.setFullscreen(true);
      saveState();
    }
  } catch (e) {
    console.error('[WindowManager] Failed to toggle fullscreen:', e);
  }
}

/**
 * Toggle always on top
 */
async function toggleAlwaysOnTop() {
  const tauri = getTauriWindow();
  if (!tauri) return;

  try {
    currentState.alwaysOnTop = !currentState.alwaysOnTop;
    const appWindow = tauri.getCurrent();
    await appWindow.setAlwaysOnTop(currentState.alwaysOnTop);
    saveState();

    if (window.Accessibility) {
      window.Accessibility.announce(
        currentState.alwaysOnTop ? 'Window pinned on top' : 'Window unpinned'
      );
    }

    dispatchWindowEvent('always-on-top-change', { alwaysOnTop: currentState.alwaysOnTop });
  } catch (e) {
    console.error('[WindowManager] Failed to toggle always on top:', e);
  }
}

// ================================================================
// 6. WINDOW DRAGGING (Floating Mode)
// ================================================================

/**
 * Start dragging the window
 */
function startDrag(event) {
  if (currentState.mode !== WindowMode.FLOATING && currentState.mode !== WindowMode.COMPACT) {
    return;
  }

  // Only start drag from title bar or drag handle
  const target = event.target;
  if (!target.closest('.window-title-bar, .drag-handle, [data-tauri-drag-region]')) {
    return;
  }

  event.preventDefault();
  isDragging = true;

  dragOffset = {
    x: event.clientX,
    y: event.clientY,
  };

  document.addEventListener('mousemove', onDrag);
  document.addEventListener('mouseup', stopDrag);
  document.body.style.cursor = 'grabbing';
}

/**
 * Handle drag movement
 */
async function onDrag(event) {
  if (!isDragging) return;

  const tauri = getTauriWindow();
  if (!tauri) return;

  const dx = event.clientX - dragOffset.x;
  const dy = event.clientY - dragOffset.y;

  const newX = currentState.position.x + dx;
  const newY = currentState.position.y + dy;

  // Apply snap to edges
  const snapped = snapToEdges(newX, newY, currentState.size.width, currentState.size.height);

  currentState.position = { x: snapped.x, y: snapped.y };

  try {
    const appWindow = tauri.getCurrent();
    await appWindow.setPosition(new tauri.LogicalPosition(snapped.x, snapped.y));
  } catch (e) {
    console.error('[WindowManager] Failed to move window:', e);
  }

  dragOffset = { x: event.clientX, y: event.clientY };
}

/**
 * Stop dragging
 */
function stopDrag() {
  if (!isDragging) return;

  isDragging = false;
  document.removeEventListener('mousemove', onDrag);
  document.removeEventListener('mouseup', stopDrag);
  document.body.style.cursor = '';

  saveState();
}

// ================================================================
// 7. SNAP TO EDGES
// ================================================================

/**
 * Snap window position to screen edges
 */
function snapToEdges(x, y, width, height) {
  const screen = {
    width: window.screen.availWidth,
    height: window.screen.availHeight,
  };

  let snappedX = x;
  let snappedY = y;

  // Snap to left edge
  if (Math.abs(x) < SNAP_THRESHOLD) {
    snappedX = 0;
  }

  // Snap to right edge
  if (Math.abs(x + width - screen.width) < SNAP_THRESHOLD) {
    snappedX = screen.width - width;
  }

  // Snap to top edge
  if (Math.abs(y) < SNAP_THRESHOLD) {
    snappedY = 0;
  }

  // Snap to bottom edge
  if (Math.abs(y + height - screen.height) < SNAP_THRESHOLD) {
    snappedY = screen.height - height;
  }

  return { x: snappedX, y: snappedY };
}

// ================================================================
// 8. WINDOW RESIZING
// ================================================================

/**
 * Start resizing the window
 */
function startResize(event, handle) {
  if (currentState.mode !== WindowMode.FLOATING) return;

  event.preventDefault();
  isResizing = true;
  resizeHandle = handle;

  document.addEventListener('mousemove', onResize);
  document.addEventListener('mouseup', stopResize);
}

/**
 * Handle resize movement
 */
async function onResize(event) {
  if (!isResizing) return;

  const tauri = getTauriWindow();
  if (!tauri) return;

  let newWidth = currentState.size.width;
  let newHeight = currentState.size.height;
  let newX = currentState.position.x;
  let newY = currentState.position.y;

  // Calculate new dimensions based on handle
  switch (resizeHandle) {
    case 'se': // Bottom-right
      newWidth = Math.max(MIN_WIDTH, event.clientX - currentState.position.x);
      newHeight = Math.max(MIN_HEIGHT, event.clientY - currentState.position.y);
      break;
    case 'e': // Right
      newWidth = Math.max(MIN_WIDTH, event.clientX - currentState.position.x);
      break;
    case 's': // Bottom
      newHeight = Math.max(MIN_HEIGHT, event.clientY - currentState.position.y);
      break;
    // Add other handles as needed
  }

  currentState.size = { width: newWidth, height: newHeight };

  try {
    const appWindow = tauri.getCurrent();
    await appWindow.setSize(new tauri.LogicalSize(newWidth, newHeight));
  } catch (e) {
    console.error('[WindowManager] Failed to resize window:', e);
  }
}

/**
 * Stop resizing
 */
function stopResize() {
  if (!isResizing) return;

  isResizing = false;
  resizeHandle = null;
  document.removeEventListener('mousemove', onResize);
  document.removeEventListener('mouseup', stopResize);

  saveState();
}

// ================================================================
// 9. CUSTOM TITLE BAR (Floating Mode)
// ================================================================

/**
 * Create custom title bar for floating mode
 */
function createFloatingTitleBar() {
  const existing = document.querySelector('.window-title-bar');
  if (existing) return existing;

  const titleBar = document.createElement('div');
  titleBar.className = 'window-title-bar';
  titleBar.setAttribute('data-tauri-drag-region', '');
  titleBar.innerHTML = `
    <div class="window-title-bar__left">
      <span class="window-title-bar__icon">鏡</span>
      <span class="window-title-bar__title">Kagami</span>
    </div>
    <div class="window-title-bar__controls">
      <button class="window-control window-control--pin" title="Toggle always on top" aria-label="Toggle pin">
        <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor">
          <path d="M9.828.722a.5.5 0 0 1 .354.146l4.95 4.95a.5.5 0 0 1 0 .707c-.48.48-1.072.588-1.503.588-.177 0-.335-.018-.46-.039l-3.134 3.134a5.927 5.927 0 0 1 .16 1.013c.046.702-.032 1.687-.72 2.375a.5.5 0 0 1-.707 0l-2.829-2.828-3.182 3.182c-.195.195-1.219.902-1.414.707-.195-.195.512-1.22.707-1.414l3.182-3.182-2.828-2.829a.5.5 0 0 1 0-.707c.688-.688 1.673-.767 2.375-.72a5.922 5.922 0 0 1 1.013.16l3.134-3.133a2.772 2.772 0 0 1-.04-.461c0-.43.108-1.022.589-1.503a.5.5 0 0 1 .353-.146z"/>
        </svg>
      </button>
      <button class="window-control window-control--mode" title="Switch to normal mode" aria-label="Switch to normal mode">
        <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor">
          <path d="M1.5 1a.5.5 0 0 0-.5.5v4a.5.5 0 0 1-1 0v-4A1.5 1.5 0 0 1 1.5 0h4a.5.5 0 0 1 0 1h-4zM10 .5a.5.5 0 0 1 .5-.5h4A1.5 1.5 0 0 1 16 1.5v4a.5.5 0 0 1-1 0v-4a.5.5 0 0 0-.5-.5h-4a.5.5 0 0 1-.5-.5zM.5 10a.5.5 0 0 1 .5.5v4a.5.5 0 0 0 .5.5h4a.5.5 0 0 1 0 1h-4A1.5 1.5 0 0 1 0 14.5v-4a.5.5 0 0 1 .5-.5zm15 0a.5.5 0 0 1 .5.5v4a1.5 1.5 0 0 1-1.5 1.5h-4a.5.5 0 0 1 0-1h4a.5.5 0 0 0 .5-.5v-4a.5.5 0 0 1 .5-.5z"/>
        </svg>
      </button>
      <button class="window-control window-control--close" title="Close" aria-label="Close window">
        <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor">
          <path d="M2.146 2.854a.5.5 0 1 1 .708-.708L8 7.293l5.146-5.147a.5.5 0 0 1 .708.708L8.707 8l5.147 5.146a.5.5 0 0 1-.708.708L8 8.707l-5.146 5.147a.5.5 0 0 1-.708-.708L7.293 8 2.146 2.854Z"/>
        </svg>
      </button>
    </div>
  `;

  // Add event listeners
  titleBar.querySelector('.window-control--pin').addEventListener('click', toggleAlwaysOnTop);
  titleBar.querySelector('.window-control--mode').addEventListener('click', enterNormalMode);
  titleBar.querySelector('.window-control--close').addEventListener('click', async () => {
    const tauri = getTauriWindow();
    if (tauri) {
      const appWindow = tauri.getCurrent();
      await appWindow.close();
    }
  });

  // Dragging
  titleBar.addEventListener('mousedown', startDrag);

  document.body.insertBefore(titleBar, document.body.firstChild);

  return titleBar;
}

/**
 * Remove custom title bar
 */
function removeFloatingTitleBar() {
  const titleBar = document.querySelector('.window-title-bar');
  if (titleBar) {
    titleBar.remove();
  }
}

// ================================================================
// 10. EVENT DISPATCHING
// ================================================================

/**
 * Dispatch a window manager event
 */
function dispatchWindowEvent(type, detail) {
  window.dispatchEvent(new CustomEvent(`kagami:window:${type}`, { detail }));
}

// ================================================================
// 11. INITIALIZATION
// ================================================================

/**
 * Initialize window manager
 */
async function initWindowManager() {
  // Load saved state
  const hasState = loadState();

  // Listen for Tauri window events
  const tauri = getTauriWindow();
  if (tauri) {
    const appWindow = tauri.getCurrent();

    // Track position changes
    appWindow.onMoved(({ payload }) => {
      currentState.position = { x: payload.x, y: payload.y };
      saveState();
    });

    // Track size changes
    appWindow.onResized(({ payload }) => {
      currentState.size = { width: payload.width, height: payload.height };
      saveState();
    });

    // Apply saved state if we have one
    if (hasState) {
      await applyState();
    }
  }

  // Register keyboard shortcuts
  if (window.KeyboardNavigation) {
    window.KeyboardNavigation.registerShortcut('mod+shift+f', toggleFullscreen, {
      id: 'toggle-fullscreen',
      description: 'Toggle fullscreen',
      category: 'Window',
    });

    window.KeyboardNavigation.registerShortcut('mod+shift+c', () => {
      if (currentState.mode === WindowMode.FLOATING) {
        enterNormalMode();
      } else {
        enterFloatingMode();
      }
    }, {
      id: 'toggle-floating',
      description: 'Toggle floating mode',
      category: 'Window',
    });

    window.KeyboardNavigation.registerShortcut('mod+shift+m', () => {
      if (currentState.mode === WindowMode.COMPACT) {
        enterNormalMode();
      } else {
        enterCompactMode();
      }
    }, {
      id: 'toggle-compact',
      description: 'Toggle compact mode',
      category: 'Window',
    });

    window.KeyboardNavigation.registerShortcut('mod+shift+p', toggleAlwaysOnTop, {
      id: 'toggle-pin',
      description: 'Toggle always on top',
      category: 'Window',
    });

    // Register commands
    window.KeyboardNavigation.registerCommand({
      id: 'window-floating',
      title: 'Floating Window Mode',
      description: 'Switch to floating companion window',
      category: 'Window',
      handler: enterFloatingMode,
    });

    window.KeyboardNavigation.registerCommand({
      id: 'window-compact',
      title: 'Compact Window Mode',
      description: 'Switch to minimal compact bar',
      category: 'Window',
      handler: enterCompactMode,
    });

    window.KeyboardNavigation.registerCommand({
      id: 'window-normal',
      title: 'Normal Window Mode',
      description: 'Switch to normal window',
      category: 'Window',
      handler: enterNormalMode,
    });

    window.KeyboardNavigation.registerCommand({
      id: 'window-fullscreen',
      title: 'Toggle Fullscreen',
      description: 'Enter or exit fullscreen mode',
      category: 'Window',
      shortcut: 'mod+shift+F',
      handler: toggleFullscreen,
    });

    window.KeyboardNavigation.registerCommand({
      id: 'window-pin',
      title: 'Pin Window on Top',
      description: 'Toggle always on top',
      category: 'Window',
      shortcut: 'mod+shift+P',
      handler: toggleAlwaysOnTop,
    });
  }

  console.log('%c[WindowManager] Initialized', 'color: #64D2FF;');
}

// ================================================================
// EXPORTS
// ================================================================

export const WindowManager = {
  // Mode switching
  enterFloatingMode,
  enterCompactMode,
  enterNormalMode,
  toggleFullscreen,
  toggleAlwaysOnTop,

  // State
  getState: () => ({ ...currentState }),
  getMode: () => currentState.mode,
  isFloating: () => currentState.mode === WindowMode.FLOATING,
  isCompact: () => currentState.mode === WindowMode.COMPACT,
  isAlwaysOnTop: () => currentState.alwaysOnTop,

  // State management
  saveState,
  loadState,
  resetState,

  // Constants
  WindowMode,

  // Init
  init: initWindowManager,
};

// Expose globally
window.WindowManager = WindowManager;

// Auto-initialize
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initWindowManager);
} else {
  initWindowManager();
}

/*
 * The window is a frame. The frame shapes what you see.
 *
 */
