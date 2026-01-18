/**
 * Kagami Login Module
 *
 * Handles user authentication for the Kagami desktop client.
 * Features:
 * - Server URL input with auto-discovery via mDNS
 * - Login form with JWT token authentication
 * - Secure token storage
 * - Redirect to main app after successful login
 *
 * Focus:
 *
 *
 */

// ═══════════════════════════════════════════════════════════════════════════
// CONSTANTS
// ═══════════════════════════════════════════════════════════════════════════

const DEFAULT_SERVER_URL = 'http://kagami.local:8001';
const TOKEN_STORAGE_KEY = 'kagami-auth-token';
const REFRESH_TOKEN_STORAGE_KEY = 'kagami-refresh-token';
const SERVER_URL_STORAGE_KEY = 'kagami-server-url';
const MDNS_SERVICE_TYPE = '_kagami._tcp';
const DISCOVERY_TIMEOUT_MS = 5000;

// ═══════════════════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════════════════

let isDiscovering = false;
let discoveredServers = [];
let isTauri = false;
let invoke = null;

// ═══════════════════════════════════════════════════════════════════════════
// INITIALIZATION
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Initialize the login module
 */
async function init() {
    console.log('[Login] Initializing...');

    // Check if running in Tauri
    isTauri = window.__TAURI_INTERNALS__ !== undefined;

    if (isTauri) {
        try {
            const tauriCore = await import('@tauri-apps/api/core');
            invoke = tauriCore.invoke;
            console.log('[Login] Running in Tauri environment');
        } catch (e) {
            console.warn('[Login] Failed to import Tauri API:', e);
        }
    } else {
        console.log('[Login] Running in browser environment');
    }

    // Check for existing valid session
    if (await checkExistingSession()) {
        console.log('[Login] Valid session found, redirecting...');
        redirectToApp();
        return;
    }

    // Restore saved server URL
    const savedUrl = localStorage.getItem(SERVER_URL_STORAGE_KEY);
    if (savedUrl) {
        document.getElementById('server-url').value = savedUrl;
    }

    // Set up event listeners
    setupEventListeners();

    console.log('[Login] Ready');
}

/**
 * Check if user has an existing valid session
 * @returns {Promise<boolean>}
 */
async function checkExistingSession() {
    const token = getStoredToken();
    const serverUrl = localStorage.getItem(SERVER_URL_STORAGE_KEY);

    if (!token || !serverUrl) {
        return false;
    }

    try {
        // Validate token by calling /api/user/me
        const response = await fetch(`${serverUrl}/api/user/me`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            signal: AbortSignal.timeout(5000)
        });

        if (response.ok) {
            return true;
        }

        // Token might be expired, try refresh
        const refreshToken = localStorage.getItem(REFRESH_TOKEN_STORAGE_KEY);
        if (refreshToken) {
            const refreshed = await refreshAccessToken(serverUrl, refreshToken);
            return refreshed;
        }

        return false;
    } catch (e) {
        console.warn('[Login] Session check failed:', e);
        return false;
    }
}

/**
 * Set up DOM event listeners
 */
function setupEventListeners() {
    // Form submission
    const form = document.getElementById('login-form');
    form.addEventListener('submit', handleLogin);

    // Server discovery
    const discoverBtn = document.getElementById('discover-btn');
    discoverBtn.addEventListener('click', handleDiscover);

    // Password visibility toggle
    const passwordToggle = document.getElementById('password-toggle');
    passwordToggle.addEventListener('click', togglePasswordVisibility);

    // Server URL changes - clear server list when manually edited
    const serverUrlInput = document.getElementById('server-url');
    serverUrlInput.addEventListener('input', () => {
        hideServerList();
    });

    // Keyboard navigation for server list
    const serverList = document.getElementById('server-list');
    serverList.addEventListener('keydown', handleServerListKeydown);

    // Focus management
    document.getElementById('username').focus();
}

// ═══════════════════════════════════════════════════════════════════════════
// SERVER DISCOVERY
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Handle discover button click
 */
async function handleDiscover() {
    if (isDiscovering) return;

    const discoverBtn = document.getElementById('discover-btn');
    const discoverText = document.getElementById('discover-text');
    const serverList = document.getElementById('server-list');

    isDiscovering = true;
    discoverBtn.disabled = true;
    discoverText.innerHTML = '<span class="spinner"></span>';

    try {
        discoveredServers = await discoverServers();

        if (discoveredServers.length > 0) {
            renderServerList(discoveredServers);
            showServerList();
        } else {
            // Try common local addresses as fallback
            discoveredServers = await probeCommonAddresses();
            if (discoveredServers.length > 0) {
                renderServerList(discoveredServers);
                showServerList();
            } else {
                serverList.innerHTML = `
                    <div class="server-list-empty">
                        No servers found. Enter address manually.
                    </div>
                `;
                showServerList();
            }
        }
    } catch (e) {
        console.error('[Login] Discovery failed:', e);
        serverList.innerHTML = `
            <div class="server-list-empty">
                Discovery failed. Enter address manually.
            </div>
        `;
        showServerList();
    } finally {
        isDiscovering = false;
        discoverBtn.disabled = false;
        discoverText.textContent = 'Discover';
    }
}

/**
 * Discover Kagami servers using mDNS (via Tauri) or fallback probing
 * @returns {Promise<Array>}
 */
async function discoverServers() {
    const servers = [];

    // Try Tauri mDNS discovery if available
    if (isTauri && invoke) {
        try {
            const mdnsServers = await invoke('discover_servers', {
                serviceType: MDNS_SERVICE_TYPE,
                timeoutMs: DISCOVERY_TIMEOUT_MS
            });

            if (Array.isArray(mdnsServers)) {
                servers.push(...mdnsServers);
            }
        } catch (e) {
            console.warn('[Login] Tauri mDNS discovery not available:', e);
        }
    }

    return servers;
}

/**
 * Probe common local addresses for Kagami servers
 * @returns {Promise<Array>}
 */
async function probeCommonAddresses() {
    const commonAddresses = [
        'http://kagami.local:8001',
        'http://localhost:8001',
        'http://127.0.0.1:8001',
        'http://192.168.1.100:8001',
        'http://192.168.0.100:8001',
        'http://10.0.0.100:8001'
    ];

    const servers = [];
    const probePromises = commonAddresses.map(async (url) => {
        try {
            const response = await fetch(`${url}/health`, {
                method: 'GET',
                signal: AbortSignal.timeout(2000)
            });

            if (response.ok) {
                const health = await response.json();
                servers.push({
                    name: health.name || 'Kagami Server',
                    address: url,
                    healthy: health.status === 'healthy'
                });
            }
        } catch (e) {
            // Server not reachable at this address
        }
    });

    await Promise.allSettled(probePromises);
    return servers;
}

/**
 * Render the discovered servers list
 * @param {Array} servers
 */
function renderServerList(servers) {
    const serverList = document.getElementById('server-list');

    if (servers.length === 0) {
        serverList.innerHTML = `
            <div class="server-list-empty">
                No servers found
            </div>
        `;
        return;
    }

    serverList.innerHTML = servers.map((server, index) => `
        <div class="server-list-item"
             role="option"
             tabindex="0"
             data-url="${server.address}"
             aria-selected="false"
             data-index="${index}">
            <div>
                <div class="server-name">${escapeHtml(server.name)}</div>
                <div class="server-address">${escapeHtml(server.address)}</div>
            </div>
            <div class="server-status" title="${server.healthy ? 'Online' : 'Offline'}"
                 style="${server.healthy ? '' : 'background: var(--prism-spark);'}"></div>
        </div>
    `).join('');

    // Add click handlers
    serverList.querySelectorAll('.server-list-item').forEach(item => {
        item.addEventListener('click', () => selectServer(item.dataset.url));
        item.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                selectServer(item.dataset.url);
            }
        });
    });
}

/**
 * Select a server from the list
 * @param {string} url
 */
function selectServer(url) {
    document.getElementById('server-url').value = url;
    hideServerList();
    document.getElementById('username').focus();
}

/**
 * Show the server list
 */
function showServerList() {
    const serverList = document.getElementById('server-list');
    serverList.classList.add('visible');
}

/**
 * Hide the server list
 */
function hideServerList() {
    const serverList = document.getElementById('server-list');
    serverList.classList.remove('visible');
}

/**
 * Handle keyboard navigation in server list
 * @param {KeyboardEvent} e
 */
function handleServerListKeydown(e) {
    const items = document.querySelectorAll('.server-list-item');
    const currentIndex = Array.from(items).findIndex(item => item === document.activeElement);

    switch (e.key) {
        case 'ArrowDown':
            e.preventDefault();
            if (currentIndex < items.length - 1) {
                items[currentIndex + 1].focus();
            }
            break;
        case 'ArrowUp':
            e.preventDefault();
            if (currentIndex > 0) {
                items[currentIndex - 1].focus();
            }
            break;
        case 'Escape':
            hideServerList();
            document.getElementById('server-url').focus();
            break;
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// LOGIN HANDLING
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Handle login form submission
 * @param {Event} e
 */
async function handleLogin(e) {
    e.preventDefault();

    const serverUrl = document.getElementById('server-url').value.trim();
    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;

    // Validation
    if (!serverUrl) {
        showError('Please enter a server URL');
        return;
    }

    if (!username) {
        showError('Please enter your username');
        document.getElementById('username').focus();
        return;
    }

    if (!password) {
        showError('Please enter your password');
        document.getElementById('password').focus();
        return;
    }

    // Normalize server URL
    const normalizedUrl = normalizeUrl(serverUrl);

    // Show loading state
    setLoading(true);
    hideError();

    try {
        // Attempt login
        const tokens = await login(normalizedUrl, username, password);

        // Store tokens securely
        storeTokens(tokens.access_token, tokens.refresh_token);

        // Store server URL
        localStorage.setItem(SERVER_URL_STORAGE_KEY, normalizedUrl);

        console.log('[Login] Login successful');

        // Show success state briefly
        showSuccess();

        // Redirect to main app
        setTimeout(() => {
            redirectToApp();
        }, 500);

    } catch (error) {
        console.error('[Login] Login failed:', error);
        showError(error.message || 'Login failed. Please check your credentials.');
        document.getElementById('password').focus();
    } finally {
        setLoading(false);
    }
}

/**
 * Perform login request to API
 * @param {string} serverUrl
 * @param {string} username
 * @param {string} password
 * @returns {Promise<{access_token: string, refresh_token: string, expires_in: number}>}
 */
async function login(serverUrl, username, password) {
    const response = await fetch(`${serverUrl}/api/user/token`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            username: username,
            password: password,
            grant_type: 'password'
        }),
        signal: AbortSignal.timeout(10000)
    });

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));

        if (response.status === 401) {
            throw new Error('Invalid username or password');
        } else if (response.status === 429) {
            throw new Error('Too many login attempts. Please wait and try again.');
        } else if (response.status === 403) {
            throw new Error('Account locked. Please contact administrator.');
        } else {
            throw new Error(errorData.detail || `Server error: ${response.status}`);
        }
    }

    return await response.json();
}

/**
 * Refresh access token using refresh token
 * @param {string} serverUrl
 * @param {string} refreshToken
 * @returns {Promise<boolean>}
 */
async function refreshAccessToken(serverUrl, refreshToken) {
    try {
        const response = await fetch(`${serverUrl}/api/user/refresh`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                refresh_token: refreshToken,
                grant_type: 'refresh_token'
            }),
            signal: AbortSignal.timeout(5000)
        });

        if (response.ok) {
            const tokens = await response.json();
            storeTokens(tokens.access_token, tokens.refresh_token || refreshToken);
            return true;
        }

        // Refresh failed, clear tokens
        clearTokens();
        return false;
    } catch (e) {
        console.warn('[Login] Token refresh failed:', e);
        return false;
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// TOKEN STORAGE
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Store authentication tokens securely
 * Uses Tauri's secure storage if available, otherwise localStorage
 * @param {string} accessToken
 * @param {string} refreshToken
 */
function storeTokens(accessToken, refreshToken) {
    if (isTauri && invoke) {
        // Use Tauri's secure storage
        invoke('store_auth_token', { token: accessToken }).catch(e => {
            console.warn('[Login] Tauri secure storage failed, using localStorage:', e);
            localStorage.setItem(TOKEN_STORAGE_KEY, accessToken);
        });

        if (refreshToken) {
            invoke('store_refresh_token', { token: refreshToken }).catch(e => {
                console.warn('[Login] Tauri secure storage failed for refresh token:', e);
                localStorage.setItem(REFRESH_TOKEN_STORAGE_KEY, refreshToken);
            });
        }
    } else {
        // Fallback to localStorage (less secure but works in browser)
        localStorage.setItem(TOKEN_STORAGE_KEY, accessToken);
        if (refreshToken) {
            localStorage.setItem(REFRESH_TOKEN_STORAGE_KEY, refreshToken);
        }
    }
}

/**
 * Get stored access token
 * @returns {string|null}
 */
function getStoredToken() {
    // Try Tauri secure storage first
    if (isTauri && invoke) {
        // Note: This is async in real Tauri, but we sync-check localStorage as fallback
        const localToken = localStorage.getItem(TOKEN_STORAGE_KEY);
        if (localToken) return localToken;
    }

    return localStorage.getItem(TOKEN_STORAGE_KEY);
}

/**
 * Clear all stored tokens
 */
function clearTokens() {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    localStorage.removeItem(REFRESH_TOKEN_STORAGE_KEY);

    if (isTauri && invoke) {
        invoke('clear_auth_tokens').catch(e => {
            console.warn('[Login] Failed to clear Tauri tokens:', e);
        });
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// UI HELPERS
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Toggle password visibility
 */
function togglePasswordVisibility() {
    const passwordInput = document.getElementById('password');
    const toggleBtn = document.getElementById('password-toggle');
    const eyeIcon = document.getElementById('eye-icon');

    if (passwordInput.type === 'password') {
        passwordInput.type = 'text';
        toggleBtn.setAttribute('aria-pressed', 'true');
        toggleBtn.setAttribute('aria-label', 'Hide password');
        eyeIcon.innerHTML = `
            <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/>
            <line x1="1" y1="1" x2="23" y2="23"/>
        `;
    } else {
        passwordInput.type = 'password';
        toggleBtn.setAttribute('aria-pressed', 'false');
        toggleBtn.setAttribute('aria-label', 'Show password');
        eyeIcon.innerHTML = `
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
            <circle cx="12" cy="12" r="3"/>
        `;
    }
}

/**
 * Show error message
 * @param {string} message
 */
function showError(message) {
    const errorEl = document.getElementById('login-error');
    const messageEl = document.getElementById('error-message');

    messageEl.textContent = message;
    errorEl.classList.add('visible');

    // Announce to screen readers
    errorEl.setAttribute('aria-live', 'assertive');
}

/**
 * Hide error message
 */
function hideError() {
    const errorEl = document.getElementById('login-error');
    errorEl.classList.remove('visible');
}

/**
 * Set loading state on submit button
 * @param {boolean} loading
 */
function setLoading(loading) {
    const submitBtn = document.getElementById('submit-btn');
    const submitText = document.getElementById('submit-text');

    if (loading) {
        submitBtn.classList.add('prism-btn--loading');
        submitBtn.disabled = true;
        submitText.textContent = 'Signing in...';
    } else {
        submitBtn.classList.remove('prism-btn--loading');
        submitBtn.disabled = false;
        submitText.textContent = 'Sign In';
    }
}

/**
 * Show success state
 */
function showSuccess() {
    const submitBtn = document.getElementById('submit-btn');
    const submitText = document.getElementById('submit-text');

    submitBtn.classList.remove('prism-btn--loading');
    submitBtn.classList.add('prism-btn--success');
    submitText.textContent = 'Success!';
}

/**
 * Redirect to main application or onboarding
 */
function redirectToApp() {
    // Check if onboarding has been completed
    const hasCompletedOnboarding = localStorage.getItem('hasCompletedOnboarding');

    if (hasCompletedOnboarding === 'true') {
        // Already onboarded, go to dashboard
        window.location.href = 'index.html';
    } else {
        // Needs onboarding
        window.location.href = 'onboarding.html';
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// UTILITIES
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Normalize URL (ensure protocol, remove trailing slash)
 * @param {string} url
 * @returns {string}
 */
function normalizeUrl(url) {
    let normalized = url.trim();

    // Add protocol if missing
    if (!normalized.startsWith('http://') && !normalized.startsWith('https://')) {
        normalized = 'http://' + normalized;
    }

    // Remove trailing slash
    if (normalized.endsWith('/')) {
        normalized = normalized.slice(0, -1);
    }

    return normalized;
}

/**
 * Escape HTML to prevent XSS
 * @param {string} str
 * @returns {string}
 */
function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// ═══════════════════════════════════════════════════════════════════════════
// EXPORTS
// ═══════════════════════════════════════════════════════════════════════════

// Export for external use
window.KagamiLogin = {
    getStoredToken,
    clearTokens,
    refreshAccessToken,
    getServerUrl: () => localStorage.getItem(SERVER_URL_STORAGE_KEY)
};

// Initialize on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}

/*
 * 鏡
 *
 */
