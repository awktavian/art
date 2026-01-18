/**
 * Kagami API Client — Frontend Integration
 *
 * Communicates with the Tauri backend and Kagami API.
 *
 * Focus:
 */

// Check if running in Tauri
const isTauri = window.__TAURI_INTERNALS__ !== undefined;

// Import Tauri API if available
let invoke = null;
if (isTauri) {
    import('@tauri-apps/api/core').then(module => {
        invoke = module.invoke;
        initializeAPI();
    });
} else {
    // Fallback for browser preview
    invoke = async (cmd, args) => {
        console.log(`[Mock] invoke: ${cmd}`, args);
        return mockResponse(cmd, args);
    };
    initializeAPI();
}

// Mock responses for browser preview
function mockResponse(cmd, args) {
    switch (cmd) {
        case 'get_api_status':
            return {
                running: true,
                health: {
                    status: 'healthy',
                    safety_score: 0.85,
                    uptime_ms: 8100000,
                },
                uptime_formatted: '2h 15m',
            };

        case 'get_system_info':
            return {
                cpu_percent: 32.5,
                memory_gb: 8.2,
                memory_percent: 51.3,
                python_processes: 3,
                gpu_status: 'MPS (Apple Silicon)',
            };

        case 'get_home_status':
            return {
                initialized: true,
                integrations: { control4: true, unifi: true, denon: true },
                rooms: 26,
                occupiedRooms: 3,
                movieMode: false,
                avgTemp: 68.5,
            };

        case 'get_rooms':
            return {
                rooms: [
                    {
                        id: 'living_room',
                        name: 'Living Room',
                        floor: 'Main',
                        lights: [{ id: 239, name: 'Cans', level: 75 }],
                        shades: [{ id: 235, name: 'South', position: 100 }, { id: 237, name: 'East', position: 100 }],
                        occupied: true,
                    },
                    {
                        id: 'kitchen',
                        name: 'Kitchen',
                        floor: 'Main',
                        lights: [{ id: 255, name: 'Cans', level: 100 }, { id: 257, name: 'Pendants', level: 50 }],
                        shades: [],
                        occupied: true,
                    },
                    {
                        id: 'primary_bed',
                        name: 'Primary Bedroom',
                        floor: 'Upper',
                        lights: [{ id: 70, name: 'Cans', level: 0 }],
                        shades: [{ id: 66, name: 'North', position: 0 }, { id: 68, name: 'West', position: 0 }],
                        occupied: false,
                    },
                    {
                        id: 'office',
                        name: 'Office',
                        floor: 'Upper',
                        lights: [{ id: 205, name: 'Cans', level: 80 }],
                        shades: [],
                        occupied: true,
                    },
                ],
                count: 26,
            };

        case 'get_devices':
            return {
                lights: [],
                shades: [],
                audioZones: [],
                locks: [
                    { name: 'Entry', isLocked: true, doorState: 'closed' },
                    { name: 'Game Room', isLocked: true, doorState: 'closed' },
                ],
                fireplace: { isOn: false, remainingMinutes: null },
                tvMount: { position: 'up', preset: null },
            };

        default:
            return { success: true };
    }
}

// ═══════════════════════════════════════════════════════════════
// LOADING STATE MANAGEMENT
// ═══════════════════════════════════════════════════════════════

/**
 * Track active loading operations
 * @type {Set<string>}
 */
const activeOperations = new Set();

/**
 * Show loading indicator for an operation
 * @param {string} operationId - Unique identifier for the operation
 * @param {string} message - Loading message to display
 */
function showLoading(operationId, message = 'Loading...') {
    activeOperations.add(operationId);

    // Announce to screen readers
    if (window.Accessibility) {
        window.Accessibility.announceLoading(true, message.replace('Loading...', '').trim());
    }

    // Show global loading indicator
    let loadingBar = document.getElementById('global-loading-bar');
    if (!loadingBar) {
        loadingBar = document.createElement('div');
        loadingBar.id = 'global-loading-bar';
        loadingBar.setAttribute('role', 'progressbar');
        loadingBar.setAttribute('aria-valuetext', 'Loading');
        loadingBar.setAttribute('aria-busy', 'true');
        loadingBar.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 3px;
            background: linear-gradient(90deg, transparent, var(--crystal, #67d4e4), transparent);
            background-size: 200% 100%;
            animation: loadingSlide 1.5s ease-in-out infinite;
            z-index: 10000;
            pointer-events: none;
        `;
        document.body.appendChild(loadingBar);

        // Add animation keyframes if not already present
        if (!document.getElementById('loading-animations')) {
            const style = document.createElement('style');
            style.id = 'loading-animations';
            style.textContent = `
                @keyframes loadingSlide {
                    0% { background-position: 200% 0; }
                    100% { background-position: -200% 0; }
                }
            `;
            document.head.appendChild(style);
        }
    }

    loadingBar.style.display = 'block';

    // Update status text if available
    const statusEl = document.getElementById('status-text');
    if (statusEl) {
        statusEl.textContent = message;
    }
}

/**
 * Hide loading indicator for an operation
 * @param {string} operationId - Unique identifier for the operation
 */
function hideLoading(operationId) {
    activeOperations.delete(operationId);

    // Only hide global indicator if no operations are active
    if (activeOperations.size === 0) {
        const loadingBar = document.getElementById('global-loading-bar');
        if (loadingBar) {
            loadingBar.style.display = 'none';
        }

        // Announce completion to screen readers
        if (window.Accessibility) {
            window.Accessibility.announceLoading(false, '');
        }

        // Reset status text
        const statusEl = document.getElementById('status-text');
        if (statusEl) {
            statusEl.textContent = 'Ready';
        }
    }
}

/**
 * Execute an operation with loading state
 * @param {string} operationId - Unique identifier
 * @param {string} loadingMessage - Message to show during loading
 * @param {Function} operation - Async function to execute
 * @returns {Promise<any>} Result of the operation
 */
async function withLoading(operationId, loadingMessage, operation) {
    showLoading(operationId, loadingMessage);
    try {
        const result = await operation();
        return result;
    } finally {
        hideLoading(operationId);
    }
}

// ═══════════════════════════════════════════════════════════════
// API STATUS POLLING
// ═══════════════════════════════════════════════════════════════

let statusInterval = null;

async function initializeAPI() {
    console.log('🌐 Initializing Kagami API client...');

    // Initial status check
    await withLoading('init-status', 'Connecting...', updateStatus);

    // Initial rooms load
    await withLoading('init-rooms', 'Loading rooms...', loadRooms);

    // Poll every 3 seconds
    statusInterval = setInterval(updateStatus, 3000);

    // Refresh rooms every 10 seconds
    setInterval(loadRooms, 10000);
}

// ═══════════════════════════════════════════════════════════════
// ROOMS UI
// ═══════════════════════════════════════════════════════════════

async function loadRooms() {
    const grid = document.getElementById('rooms-grid');
    if (!grid) return;

    // Set aria-busy for accessibility
    grid.setAttribute('aria-busy', 'true');

    try {
        const data = await invoke('get_rooms');
        renderRooms(data.rooms, grid);
        grid.setAttribute('aria-busy', 'false');

        // Update footer stats
        const roomsStat = document.getElementById('rooms-stat');
        const devicesStat = document.getElementById('devices-stat');

        if (roomsStat) {
            roomsStat.textContent = `${data.rooms.length} rooms`;
        }

        if (devicesStat) {
            const totalLights = data.rooms.reduce((sum, r) => sum + (r.lights?.length || 0), 0);
            const totalShades = data.rooms.reduce((sum, r) => sum + (r.shades?.length || 0), 0);
            devicesStat.textContent = `${totalLights + totalShades} devices`;
        }
    } catch (e) {
        console.error('Failed to load rooms:', e);
        grid.innerHTML = `
            <div class="room-card error">
                <div class="room-name">Error loading rooms</div>
                <div class="room-light-label">${e.message || 'Connection failed'}</div>
            </div>
        `;
    }
}

function renderRooms(rooms, container) {
    // Update aria-busy state
    container.setAttribute('aria-busy', 'false');

    if (!rooms || rooms.length === 0) {
        container.innerHTML = `
            <div class="room-card" role="listitem">
                <div class="room-name">No rooms found</div>
                <div class="room-light-label">Check API connection</div>
            </div>
        `;
        // Announce to screen readers
        if (window.Accessibility) {
            window.Accessibility.announce('No rooms found. Check API connection.');
        }
        return;
    }

    // Announce room count to screen readers
    if (window.Accessibility) {
        window.Accessibility.announce(`${rooms.length} rooms loaded.`);
    }

    container.innerHTML = rooms.map((room, index) => {
        const avgLight = room.lights && room.lights.length > 0
            ? Math.round(room.lights.reduce((sum, l) => sum + l.level, 0) / room.lights.length)
            : 0;

        const lightState = avgLight === 0 ? 'off' : avgLight < 50 ? 'dim' : 'on';
        const lightStateText = lightState === 'off' ? 'lights off' : `lights at ${avgLight} percent`;
        const hasShades = room.shades && room.shades.length > 0;
        const occupancyText = room.occupied ? ', occupied' : '';
        const roomId = `room-${room.id}`;

        return `
            <div class="room-card ${room.occupied ? 'occupied' : ''}"
                 data-room-id="${room.id}"
                 data-room-name="${room.name}"
                 role="listitem"
                 tabindex="${index === 0 ? '0' : '-1'}"
                 aria-labelledby="${roomId}-name"
                 aria-describedby="${roomId}-status">
                <div class="room-header">
                    <div class="room-name" id="${roomId}-name">${room.name}</div>
                    <div class="room-floor">${room.floor}</div>
                </div>
                <div class="room-status" id="${roomId}-status">
                    <div class="room-indicator ${lightState}" aria-hidden="true"></div>
                    <span class="room-light-label">
                        ${lightState === 'off' ? 'Off' : `${avgLight}%`}
                    </span>
                    <span class="sr-only">${lightStateText}${occupancyText}</span>
                </div>
                <div class="room-brightness" role="progressbar" aria-valuenow="${avgLight}" aria-valuemin="0" aria-valuemax="100" aria-label="Light brightness">
                    <div class="room-brightness-bar" style="width: ${avgLight}%"></div>
                </div>
                <div class="room-controls" role="group" aria-label="Controls for ${room.name}">
                    <button class="room-control-btn" data-action="lights-on" aria-label="Turn lights on in ${room.name}">
                        <span aria-hidden="true">💡</span>
                    </button>
                    <button class="room-control-btn" data-action="lights-off" aria-label="Turn lights off in ${room.name}">
                        <span aria-hidden="true">🌙</span>
                    </button>
                    ${hasShades ? `
                        <button class="room-control-btn" data-action="shades-open" aria-label="Open shades in ${room.name}">
                            <span aria-hidden="true">☀️</span>
                        </button>
                        <button class="room-control-btn" data-action="shades-close" aria-label="Close shades in ${room.name}">
                            <span aria-hidden="true">🌑</span>
                        </button>
                    ` : ''}
                </div>
            </div>
        `;
    }).join('');

    // Attach event listeners to control buttons
    container.querySelectorAll('.room-control-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.stopPropagation();
            const card = btn.closest('.room-card');
            const roomId = card.dataset.roomId;
            const roomName = card.dataset.roomName;
            const action = btn.dataset.action;

            try {
                btn.disabled = true;
                btn.style.opacity = '0.5';

                switch (action) {
                    case 'lights-on':
                        await invoke('set_lights', { level: 100, rooms: [roomId] });
                        showNotification(`💡 ${roomName} lights on`);
                        break;
                    case 'lights-off':
                        await invoke('set_lights', { level: 0, rooms: [roomId] });
                        showNotification(`🌙 ${roomName} lights off`);
                        break;
                    case 'shades-open':
                        await invoke('control_shades', { action: 'open', rooms: [roomId] });
                        showNotification(`☀️ ${roomName} shades opening`);
                        break;
                    case 'shades-close':
                        await invoke('control_shades', { action: 'close', rooms: [roomId] });
                        showNotification(`🌑 ${roomName} shades closing`);
                        break;
                }

                // Refresh rooms after action (987ms delay)
                setTimeout(loadRooms, 987);
            } catch (err) {
                showNotification(`❌ Failed: ${err.message}`, 'error');
            } finally {
                btn.disabled = false;
                btn.style.opacity = '1';
            }
        });
    });
}

async function updateStatus() {
    try {
        // Get API status
        const apiStatus = await invoke('get_api_status');
        updateAPIDisplay(apiStatus);

        // Get system info
        const systemInfo = await invoke('get_system_info');
        updateSystemDisplay(systemInfo);

    } catch (e) {
        console.error('Status update failed:', e);
        updateAPIDisplay({ running: false });
    }
}

// Track previous connection state for announcements
let previousConnectionState = null;

function updateAPIDisplay(status) {
    const statusEl = document.getElementById('api-status');
    const healthEl = document.getElementById('api-health');

    // Update status card
    if (statusEl) {
        if (status.running) {
            statusEl.textContent = `Running (${status.uptime_formatted || '--'})`;
            statusEl.classList.add('running');

            // Announce reconnection to screen readers (only on state change)
            if (previousConnectionState === false && window.Accessibility) {
                window.Accessibility.announce('API connection restored');
            }
        } else {
            statusEl.textContent = 'Stopped';
            statusEl.classList.remove('running');

            // Announce disconnection to screen readers (only on state change)
            if (previousConnectionState === true && window.Accessibility) {
                window.Accessibility.announceError('API connection lost');
            }
        }
        previousConnectionState = status.running;
    }

    // Update health display
    let hx = null;
    if (healthEl && status.health) {
        hx = status.health.safety_score;
        if (hx !== null && hx !== undefined) {
            healthEl.textContent = hx >= 0.5 ? '● Good' : hx >= 0 ? '● Caution' : '● Alert';

            // Update safety display in status grid
            const safetyEl = document.getElementById('safety-value');
            if (safetyEl) {
                if (hx >= 0.5) {
                    safetyEl.textContent = 'All Good';
                    safetyEl.className = 'stat-value safety-ok';
                } else if (hx >= 0) {
                    safetyEl.textContent = 'Attention';
                    safetyEl.className = 'stat-value safety-caution';
                } else {
                    safetyEl.textContent = 'Alert';
                    safetyEl.className = 'stat-value safety-violation';
                }
            }
        }
    }

    // Update footer connection status
    const connIndicator = document.getElementById('conn-indicator');
    const connLabel = document.getElementById('conn-label');
    const safetyStat = document.getElementById('safety-stat');

    if (connIndicator && connLabel) {
        if (status.running) {
            connIndicator.classList.add('connected');
            connIndicator.classList.remove('disconnected');
            connLabel.textContent = 'Connected';
        } else {
            connIndicator.classList.remove('connected');
            connIndicator.classList.add('disconnected');
            connLabel.textContent = 'Disconnected';
        }
    }

    if (safetyStat && hx !== null) {
        safetyStat.textContent = hx >= 0.5 ? 'Good' : hx >= 0 ? 'Caution' : 'Alert';
    }
}

function updateSystemDisplay(info) {
    // Could update system stats display here
}

// ═══════════════════════════════════════════════════════════════
// OFFLINE BANNER
// ═══════════════════════════════════════════════════════════════

let isOnline = true;

function initOfflineBanner() {
    const banner = document.getElementById('offline-banner');
    const retryBtn = document.getElementById('offline-retry');

    if (!banner || !retryBtn) return;

    retryBtn.addEventListener('click', async () => {
        retryBtn.textContent = 'Retrying...';
        retryBtn.disabled = true;

        try {
            await checkConnection();
            if (isOnline) {
                hideOfflineBanner();
            }
        } catch (e) {
            // Still offline
        } finally {
            retryBtn.textContent = 'Retry';
            retryBtn.disabled = false;
        }
    });
}

function showOfflineBanner() {
    const banner = document.getElementById('offline-banner');
    if (banner && isOnline) {
        isOnline = false;
        banner.style.display = 'flex';
    }
}

function hideOfflineBanner() {
    const banner = document.getElementById('offline-banner');
    if (banner && !isOnline) {
        isOnline = true;
        banner.style.display = 'none';
    }
}

async function checkConnection() {
    try {
        const apiUrl = getApiUrl();
        const response = await fetch(`${apiUrl}/health`, {
            headers: getAuthHeaders(),
            signal: AbortSignal.timeout(5000)
        });
        if (response.ok) {
            hideOfflineBanner();
            return true;
        }
    } catch (e) {
        showOfflineBanner();
    }
    return false;
}

/**
 * Get the configured API URL
 * @returns {string}
 */
function getApiUrl() {
    return localStorage.getItem('kagami-server-url') ||
           localStorage.getItem('kagami-api-url') ||
           'http://kagami.local:8001';
}

/**
 * Get authentication headers for API requests
 * @returns {Object}
 */
function getAuthHeaders() {
    const token = localStorage.getItem('kagami-auth-token');
    const headers = {
        'Content-Type': 'application/json'
    };

    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    return headers;
}

/**
 * Make an authenticated API request
 * @param {string} endpoint - API endpoint (e.g., '/api/user/me')
 * @param {Object} options - Fetch options
 * @returns {Promise<Response>}
 */
async function authenticatedFetch(endpoint, options = {}) {
    const apiUrl = getApiUrl();
    const url = endpoint.startsWith('http') ? endpoint : `${apiUrl}${endpoint}`;

    const response = await fetch(url, {
        ...options,
        headers: {
            ...getAuthHeaders(),
            ...options.headers
        }
    });

    // Handle 401 - token might be expired
    if (response.status === 401) {
        const refreshToken = localStorage.getItem('kagami-refresh-token');
        if (refreshToken) {
            const refreshed = await refreshAccessToken(apiUrl, refreshToken);
            if (refreshed) {
                // Retry with new token
                return fetch(url, {
                    ...options,
                    headers: {
                        ...getAuthHeaders(),
                        ...options.headers
                    }
                });
            }
        }

        // Refresh failed, redirect to login
        console.warn('[KagamiAPI] Authentication failed, redirecting to login...');
        clearAuthTokens();
        window.location.href = 'login.html';
    }

    return response;
}

/**
 * Refresh the access token
 * @param {string} apiUrl
 * @param {string} refreshToken
 * @returns {Promise<boolean>}
 */
async function refreshAccessToken(apiUrl, refreshToken) {
    try {
        const response = await fetch(`${apiUrl}/api/user/refresh`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                refresh_token: refreshToken,
                grant_type: 'refresh_token'
            }),
            signal: AbortSignal.timeout(5000)
        });

        if (response.ok) {
            const tokens = await response.json();
            localStorage.setItem('kagami-auth-token', tokens.access_token);
            if (tokens.refresh_token) {
                localStorage.setItem('kagami-refresh-token', tokens.refresh_token);
            }
            return true;
        }

        return false;
    } catch (e) {
        console.warn('[KagamiAPI] Token refresh failed:', e);
        return false;
    }
}

/**
 * Clear all authentication tokens
 */
function clearAuthTokens() {
    localStorage.removeItem('kagami-auth-token');
    localStorage.removeItem('kagami-refresh-token');
}

/**
 * Logout the current user
 */
async function logout() {
    try {
        const apiUrl = getApiUrl();
        await fetch(`${apiUrl}/api/user/logout`, {
            method: 'POST',
            headers: getAuthHeaders()
        });
    } catch (e) {
        console.warn('[KagamiAPI] Logout request failed:', e);
    } finally {
        clearAuthTokens();
        window.location.href = 'login.html';
    }
}

// ═══════════════════════════════════════════════════════════════
// CONTEXT-AWARE HERO ACTION
// ═══════════════════════════════════════════════════════════════

function initHeroAction() {
    const greetingEl = document.getElementById('hero-greeting');
    const btnEl = document.getElementById('hero-action-btn');
    const iconEl = document.getElementById('hero-action-icon');
    const labelEl = document.getElementById('hero-action-label');

    if (!greetingEl || !btnEl) return;

    // Get time-based context
    const hour = new Date().getHours();
    let greeting, action, icon, label;

    if (hour >= 5 && hour < 12) {
        greeting = 'Good morning';
        action = 'welcome_home';
        icon = '☀️';
        label = 'Start Your Day';
    } else if (hour >= 12 && hour < 17) {
        greeting = 'Good afternoon';
        action = 'welcome_home';
        icon = '🏠';
        label = 'Welcome Home';
    } else if (hour >= 17 && hour < 21) {
        greeting = 'Good evening';
        action = 'movie_mode';
        icon = '🎬';
        label = 'Movie Mode';
    } else {
        greeting = 'Good night';
        action = 'goodnight';
        icon = '🌙';
        label = 'Goodnight';
    }

    // Update UI
    greetingEl.textContent = greeting;
    iconEl.textContent = icon;
    labelEl.textContent = label;
    btnEl.dataset.action = action;

    // Add click handler
    btnEl.addEventListener('click', async () => {
        btnEl.classList.add('executing');

        try {
            switch (action) {
                case 'movie_mode':
                    await invoke('execute_scene', { scene: 'movie_mode' });
                    showNotification('🎬 Movie Mode activated');
                    break;
                case 'goodnight':
                    await invoke('execute_scene', { scene: 'goodnight' });
                    showNotification('🌙 Goodnight executed');
                    break;
                case 'welcome_home':
                    await invoke('execute_scene', { scene: 'welcome_home' });
                    showNotification('🏠 Welcome Home!');
                    break;
            }

            btnEl.classList.add('success');
            setTimeout(() => {
                btnEl.classList.remove('success');
            }, 2000);
        } catch (e) {
            console.error(`Hero action failed:`, e);
            showNotification(`❌ Action failed: ${e}`, 'error');
        } finally {
            btnEl.classList.remove('executing');
        }
    });
}

// ═══════════════════════════════════════════════════════════════
// ACTION HANDLERS
// ═══════════════════════════════════════════════════════════════

// ═══════════════════════════════════════════════════════════════
// CONFIRMATION DIALOG
// ═══════════════════════════════════════════════════════════════

/**
 * Show a confirmation dialog for destructive actions
 * @param {string} title - Dialog title
 * @param {string} message - Confirmation message
 * @returns {Promise<boolean>} Whether user confirmed
 */
async function showConfirmDialog(title, message) {
    return new Promise((resolve) => {
        // Check if dialog already exists
        let dialog = document.getElementById('confirm-dialog');
        if (!dialog) {
            dialog = document.createElement('dialog');
            dialog.id = 'confirm-dialog';
            dialog.setAttribute('role', 'alertdialog');
            dialog.setAttribute('aria-modal', 'true');
            dialog.style.cssText = `
                position: fixed;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                background: var(--obsidian, #1a1a1a);
                border: 1px solid var(--border-default, rgba(255,255,255,0.1));
                border-radius: var(--radius-lg, 16px);
                padding: 24px;
                min-width: 320px;
                max-width: 400px;
                box-shadow: 0 16px 48px rgba(0, 0, 0, 0.4);
                color: var(--text, #e5e5e5);
                font-family: var(--font-sans, -apple-system, system-ui, sans-serif);
            `;
            document.body.appendChild(dialog);
        }

        dialog.innerHTML = `
            <h3 style="margin: 0 0 12px 0; font-size: 18px; font-weight: 600;">${title}</h3>
            <p style="margin: 0 0 24px 0; color: var(--text-secondary, rgba(255,255,255,0.7)); font-size: 14px;">${message}</p>
            <div style="display: flex; gap: 12px; justify-content: flex-end;">
                <button id="confirm-cancel" style="
                    padding: 8px 16px;
                    background: transparent;
                    border: 1px solid var(--border-default, rgba(255,255,255,0.1));
                    border-radius: 8px;
                    color: var(--text-secondary, rgba(255,255,255,0.7));
                    cursor: pointer;
                    font-size: 14px;
                ">Cancel</button>
                <button id="confirm-ok" style="
                    padding: 8px 16px;
                    background: var(--warn, #f59e0b);
                    border: none;
                    border-radius: 8px;
                    color: #000;
                    cursor: pointer;
                    font-weight: 500;
                    font-size: 14px;
                ">Confirm</button>
            </div>
        `;

        dialog.setAttribute('aria-labelledby', 'confirm-title');
        dialog.querySelector('h3').id = 'confirm-title';

        const cleanup = () => {
            dialog.close();
            dialog.remove();
        };

        dialog.querySelector('#confirm-cancel').onclick = () => {
            cleanup();
            resolve(false);
        };

        dialog.querySelector('#confirm-ok').onclick = () => {
            cleanup();
            resolve(true);
        };

        // Handle Escape key
        dialog.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                cleanup();
                resolve(false);
            }
        });

        dialog.showModal();

        // Focus the cancel button for safety
        dialog.querySelector('#confirm-cancel').focus();

        // Announce to screen readers
        if (window.Accessibility) {
            window.Accessibility.announce(`${title}. ${message}`, { assertive: true });
        }
    });
}

/**
 * Destructive actions that require confirmation
 */
const DESTRUCTIVE_ACTIONS = new Set(['goodnight', 'all_off', 'lights_off_all']);

// Attach handlers to action buttons
document.addEventListener('DOMContentLoaded', () => {
    // Check for authentication first
    const authToken = localStorage.getItem('kagami-auth-token');
    const isLoginPage = window.location.pathname.includes('login');
    const isOnboardingPage = window.location.pathname.includes('onboarding');

    // Redirect to login if not authenticated (unless already on login/onboarding page)
    if (!authToken && !isLoginPage && !isOnboardingPage) {
        console.log('[KagamiAPI] No auth token found, redirecting to login...');
        window.location.href = 'login.html';
        return;
    }

    // Check for onboarding (only after authentication check)
    if (!localStorage.getItem('hasCompletedOnboarding') && !isOnboardingPage && !isLoginPage) {
        window.location.href = 'onboarding.html';
        return;
    }

    // Initialize context-aware hero action
    initHeroAction();

    // Initialize offline banner
    initOfflineBanner();

    document.querySelectorAll('.action-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            const action = btn.dataset.action;
            if (!action) return;

            // Require confirmation for destructive actions
            if (DESTRUCTIVE_ACTIONS.has(action)) {
                const confirmed = await showConfirmDialog(
                    'Confirm Action',
                    action === 'goodnight'
                        ? 'This will turn off all lights, lock doors, and set the house to sleep mode. Continue?'
                        : 'This will turn off all lights in the house. Continue?'
                );
                if (!confirmed) {
                    if (window.Accessibility) {
                        window.Accessibility.announce('Action cancelled');
                    }
                    return;
                }
            }

            // Show loading state on button
            const originalContent = btn.innerHTML;
            btn.disabled = true;
            btn.setAttribute('aria-busy', 'true');
            btn.innerHTML = '<span class="loading-spinner" aria-hidden="true"></span> Working...';

            try {
                console.log(`Executing action: ${action}`);

                await withLoading(`action-${action}`, `Executing ${action}...`, async () => {
                    switch (action) {
                        case 'movie_mode':
                            await invoke('execute_scene', { scene: 'movie_mode' });
                            showNotification('🎬 Movie Mode activated');
                            break;

                        case 'goodnight':
                            await invoke('execute_scene', { scene: 'goodnight' });
                            showNotification('🌙 Goodnight executed');
                            break;

                        case 'welcome_home':
                            await invoke('execute_scene', { scene: 'welcome_home' });
                            showNotification('🏡 Welcome Home!');
                            break;

                        case 'fireplace':
                            // Toggle - would need to track state
                            await invoke('toggle_fireplace', { on: true });
                            showNotification('🔥 Fireplace toggled');
                            break;

                        case 'focus':
                            // Focus mode: lights up, shades open
                            await invoke('set_lights', { level: 80 });
                            await invoke('control_shades', { action: 'open' });
                            showNotification('🎯 Focus Mode activated');
                            break;

                        case 'relax':
                            // Relax mode: dim lights, fireplace on
                            await invoke('set_lights', { level: 30 });
                            await invoke('toggle_fireplace', { on: true });
                            showNotification('🧘 Relax mode activated');
                            break;

                        case 'coffee':
                            // Coffee time: bright kitchen lights
                            await invoke('set_lights', { level: 100, rooms: ['Kitchen'] });
                            showNotification('☕ Coffee time!');
                            break;

                        case 'all_off':
                        case 'lights_off_all':
                            await invoke('set_lights', { level: 0 });
                            showNotification('💡 All lights off');
                            break;

                        default:
                            console.log(`Unknown action: ${action}`);
                    }
                });
            } catch (e) {
                console.error(`Action ${action} failed:`, e);
                showNotification(`❌ ${action} failed: ${e}`, 'error');
            } finally {
                // Restore button state
                btn.disabled = false;
                btn.removeAttribute('aria-busy');
                btn.innerHTML = originalContent;
            }
        });
    });

    // Logout button handler
    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', async () => {
            if (confirm('Are you sure you want to logout?')) {
                await logout();
            }
        });
    }
});

// ═══════════════════════════════════════════════════════════════
// NOTIFICATIONS
// ═══════════════════════════════════════════════════════════════

function showNotification(message, type = 'success') {
    // Announce to screen readers
    if (window.Accessibility) {
        if (type === 'error') {
            window.Accessibility.announceError(message);
        } else {
            window.Accessibility.announce(message);
        }
    }

    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.setAttribute('role', 'alert');
    notification.setAttribute('aria-live', type === 'error' ? 'assertive' : 'polite');
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        padding: 12px 20px;
        background: var(--obsidian);
        border: 1px solid ${type === 'error' ? 'var(--fail)' : 'var(--crystal)'};
        border-radius: var(--radius-md);
        font-family: var(--font-mono);
        font-size: 0.85rem;
        color: var(--text);
        z-index: 9999;
        animation: notification-in 0.3s ease;
    `;

    document.body.appendChild(notification);

    // Remove after 3 seconds
    setTimeout(() => {
        notification.style.animation = 'notification-out 0.233s ease';
        setTimeout(() => notification.remove(), 233);
    }, 3000);
}

// Add notification animations
const style = document.createElement('style');
style.textContent = `
    @keyframes notification-in {
        from {
            opacity: 0;
            transform: translateX(20px);
        }
        to {
            opacity: 1;
            transform: translateX(0);
        }
    }

    @keyframes notification-out {
        from {
            opacity: 1;
            transform: translateX(0);
        }
        to {
            opacity: 0;
            transform: translateX(20px);
        }
    }
`;
document.head.appendChild(style);

// ═══════════════════════════════════════════════════════════════
// HOME API FUNCTIONS (Real data from /home/* endpoints)
// ═══════════════════════════════════════════════════════════════

/**
 * Fetch all rooms with their current state
 * @returns {Promise<{rooms: Array, count: number}>}
 */
async function fetchRooms() {
    try {
        const response = await invoke('get_rooms');
        return response;
    } catch (e) {
        console.error('Failed to fetch rooms:', e);
        throw e;
    }
}

/**
 * Fetch home status overview
 * @returns {Promise<Object>}
 */
async function fetchHomeStatus() {
    try {
        const response = await invoke('get_home_status');
        return response;
    } catch (e) {
        console.error('Failed to fetch home status:', e);
        throw e;
    }
}

/**
 * Fetch all devices (lights, shades, audio, locks, fireplace, TV)
 * @returns {Promise<Object>}
 */
async function fetchDevices() {
    try {
        const response = await invoke('get_devices');
        return response;
    } catch (e) {
        console.error('Failed to fetch devices:', e);
        throw e;
    }
}

/**
 * Set light level in specific room
 * @param {string} roomId - Room identifier
 * @param {number} level - 0-100
 */
async function setRoomLights(roomId, level) {
    try {
        await invoke('set_lights', { level, rooms: [roomId] });
        showNotification(`💡 ${roomId} lights set to ${level}%`);
    } catch (e) {
        console.error('Failed to set lights:', e);
        showNotification(`❌ Failed to set lights`, 'error');
        throw e;
    }
}

/**
 * Control shades in specific room
 * @param {string} roomId - Room identifier
 * @param {string} action - 'open' | 'close' | 'stop'
 */
async function setRoomShades(roomId, action) {
    try {
        await invoke('control_shades', { action, rooms: [roomId] });
        const icon = action === 'open' ? '☀️' : '🌙';
        showNotification(`${icon} ${roomId} shades ${action}`);
    } catch (e) {
        console.error('Failed to control shades:', e);
        showNotification(`❌ Failed to control shades`, 'error');
        throw e;
    }
}

// ═══════════════════════════════════════════════════════════════
// EXPORTS
// ═══════════════════════════════════════════════════════════════

window.KagamiAPI = {
    invoke,
    updateStatus,
    showNotification,

    // Loading state management
    showLoading,
    hideLoading,
    withLoading,

    // Confirmation dialogs
    showConfirmDialog,

    // Home data fetching
    fetchRooms,
    fetchHomeStatus,
    fetchDevices,

    // Room controls
    setRoomLights,
    setRoomShades,

    // Scene shortcuts
    movieMode: () => invoke('execute_scene', { scene: 'movie_mode' }),
    goodnight: () => invoke('execute_scene', { scene: 'goodnight' }),
    welcomeHome: () => invoke('execute_scene', { scene: 'welcome_home' }),
    fireplace: (on) => invoke('toggle_fireplace', { on }),
    lights: (level, rooms) => invoke('set_lights', { level, rooms }),
    shades: (action, rooms) => invoke('control_shades', { action, rooms }),
    tv: (action, preset) => invoke('control_tv', { action, preset }),
    announce: (text, rooms, colony) => invoke('announce', { text, rooms, colony }),

    // Authentication
    getApiUrl,
    getAuthHeaders,
    authenticatedFetch,
    logout,
    isAuthenticated: () => !!localStorage.getItem('kagami-auth-token'),
    getAuthToken: () => localStorage.getItem('kagami-auth-token'),
};

console.log('%c🌐 KagamiAPI ready. Try: KagamiAPI.fetchRooms()', 'color: #67d4e4;');

/*
 * 鏡
 */
