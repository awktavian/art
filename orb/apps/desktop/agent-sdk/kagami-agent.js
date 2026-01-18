/**
 * Kagami Agent SDK — Static HTML Agent Framework
 * 
 * Enables static HTML files to act as autonomous agents that:
 * - Discover local Kagami backends via mDNS
 * - Cache data locally with encryption (IndexedDB)
 * - Operate offline with sync-when-online
 * - Connect to the distributed mesh
 * 
 * Architecture:
 * ```
 * ┌─────────────────────────────────────────────────────────────┐
 * │                    HTML AGENT                                │
 * │  ┌─────────────────────────────────────────────────────┐    │
 * │  │           KagamiAgent                                │    │
 * │  │  • discover() → Find backends via mDNS              │    │
 * │  │  • fetch() → Get cached or remote data              │    │
 * │  │  • submit() → Send requests for consensus           │    │
 * │  │  • subscribe() → Real-time updates                  │    │
 * │  └─────────────────────────────────────────────────────┘    │
 * │                           │                                  │
 * │  ┌─────────────────────────────────────────────────────┐    │
 * │  │           CryptoStore (IndexedDB)                    │    │
 * │  │  • AES-256-GCM encryption at rest                   │    │
 * │  │  • Content-addressed blobs                          │    │
 * │  │  • Offline-first operation                          │    │
 * │  └─────────────────────────────────────────────────────┘    │
 * └─────────────────────────────────────────────────────────────┘
 *                              │
 *           ┌──────────────────┼──────────────────┐
 *           │                  │                  │
 *           ▼                  ▼                  ▼
 *    ┌──────────┐       ┌──────────┐       ┌──────────┐
 *    │ Hub (Pi) │◄─────▶│ Hub (Mac)│◄─────▶│   API    │
 *    └──────────┘       └──────────┘       └──────────┘
 * ```
 * 
 * @module kagami-agent
 * @version 1.0.0
 * @license MIT
 * 
 * Created: January 2026
 */

// =============================================================================
// Configuration
// =============================================================================

const KAGAMI_CONFIG = {
  // Service discovery
  MDNS_SERVICE_TYPE: '_kagami._tcp.local.',
  MDNS_TIMEOUT: 5000,
  
  // API endpoints
  DEFAULT_API_PORT: 8000,
  DEFAULT_HUB_PORT: 9876,
  
  // WebSocket
  WS_RECONNECT_INTERVAL: 3000,
  WS_MAX_RECONNECTS: 10,
  
  // Encryption
  ENCRYPTION_ALGORITHM: 'AES-GCM',
  KEY_LENGTH: 256,
  IV_LENGTH: 12,
  
  // Cache
  CACHE_DB_NAME: 'kagami-agent-cache',
  CACHE_DB_VERSION: 1,
  CACHE_EXPIRY_MS: 24 * 60 * 60 * 1000, // 24 hours
  
  // Network
  REQUEST_TIMEOUT: 30000,
  HEALTH_CHECK_INTERVAL: 30000,
};

// =============================================================================
// Crypto Store — Encrypted IndexedDB
// =============================================================================

/**
 * Encrypted IndexedDB storage for offline data.
 * Uses AES-256-GCM for encryption at rest.
 */
class CryptoStore {
  constructor(dbName = KAGAMI_CONFIG.CACHE_DB_NAME) {
    this.dbName = dbName;
    this.db = null;
    this.encryptionKey = null;
  }
  
  /**
   * Initialize the encrypted store.
   * @param {string} [passphrase] - Optional passphrase for key derivation
   * @returns {Promise<void>}
   */
  async initialize(passphrase = null) {
    // Derive or generate encryption key
    this.encryptionKey = await this._getOrCreateKey(passphrase);
    
    // Open IndexedDB
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(this.dbName, KAGAMI_CONFIG.CACHE_DB_VERSION);
      
      request.onerror = () => reject(request.error);
      
      request.onsuccess = () => {
        this.db = request.result;
        resolve();
      };
      
      request.onupgradeneeded = (event) => {
        const db = event.target.result;
        
        // Blobs store (encrypted data)
        if (!db.objectStoreNames.contains('blobs')) {
          const blobStore = db.createObjectStore('blobs', { keyPath: 'hash' });
          blobStore.createIndex('type', 'type', { unique: false });
          blobStore.createIndex('timestamp', 'timestamp', { unique: false });
        }
        
        // Metadata store (for discovery/lookup)
        if (!db.objectStoreNames.contains('metadata')) {
          const metaStore = db.createObjectStore('metadata', { keyPath: 'key' });
          metaStore.createIndex('category', 'category', { unique: false });
        }
        
        // Pending requests (for offline queue)
        if (!db.objectStoreNames.contains('pending')) {
          const pendingStore = db.createObjectStore('pending', { keyPath: 'id', autoIncrement: true });
          pendingStore.createIndex('timestamp', 'timestamp', { unique: false });
        }
      };
    });
  }
  
  /**
   * Get or create encryption key.
   * @private
   */
  async _getOrCreateKey(passphrase) {
    const subtle = window.crypto.subtle;
    
    if (passphrase) {
      // Derive key from passphrase using PBKDF2
      const encoder = new TextEncoder();
      const keyMaterial = await subtle.importKey(
        'raw',
        encoder.encode(passphrase),
        'PBKDF2',
        false,
        ['deriveKey']
      );
      
      // Use fixed salt for deterministic derivation
      // In production, salt should be stored and retrieved
      const salt = encoder.encode('kagami-agent-salt-v1');
      
      return subtle.deriveKey(
        {
          name: 'PBKDF2',
          salt,
          iterations: 100000,
          hash: 'SHA-256',
        },
        keyMaterial,
        { name: 'AES-GCM', length: KAGAMI_CONFIG.KEY_LENGTH },
        false,
        ['encrypt', 'decrypt']
      );
    }
    
    // Check for stored key
    const storedKey = localStorage.getItem('kagami-agent-key');
    if (storedKey) {
      const keyData = Uint8Array.from(atob(storedKey), c => c.charCodeAt(0));
      return subtle.importKey(
        'raw',
        keyData,
        { name: 'AES-GCM', length: KAGAMI_CONFIG.KEY_LENGTH },
        false,
        ['encrypt', 'decrypt']
      );
    }
    
    // Generate new key
    const key = await subtle.generateKey(
      { name: 'AES-GCM', length: KAGAMI_CONFIG.KEY_LENGTH },
      true,
      ['encrypt', 'decrypt']
    );
    
    // Export and store
    const exportedKey = await subtle.exportKey('raw', key);
    localStorage.setItem(
      'kagami-agent-key',
      btoa(String.fromCharCode(...new Uint8Array(exportedKey)))
    );
    
    // Re-import as non-extractable
    return subtle.importKey(
      'raw',
      exportedKey,
      { name: 'AES-GCM', length: KAGAMI_CONFIG.KEY_LENGTH },
      false,
      ['encrypt', 'decrypt']
    );
  }
  
  /**
   * Encrypt data with AES-256-GCM.
   * @param {*} data - Data to encrypt
   * @returns {Promise<{iv: string, ciphertext: string}>}
   */
  async encrypt(data) {
    const subtle = window.crypto.subtle;
    const encoder = new TextEncoder();
    
    const iv = window.crypto.getRandomValues(new Uint8Array(KAGAMI_CONFIG.IV_LENGTH));
    const plaintext = encoder.encode(JSON.stringify(data));
    
    const ciphertext = await subtle.encrypt(
      { name: 'AES-GCM', iv },
      this.encryptionKey,
      plaintext
    );
    
    return {
      iv: btoa(String.fromCharCode(...iv)),
      ciphertext: btoa(String.fromCharCode(...new Uint8Array(ciphertext))),
    };
  }
  
  /**
   * Decrypt data with AES-256-GCM.
   * @param {{iv: string, ciphertext: string}} encrypted - Encrypted data
   * @returns {Promise<*>}
   */
  async decrypt(encrypted) {
    const subtle = window.crypto.subtle;
    const decoder = new TextDecoder();
    
    const iv = Uint8Array.from(atob(encrypted.iv), c => c.charCodeAt(0));
    const ciphertext = Uint8Array.from(atob(encrypted.ciphertext), c => c.charCodeAt(0));
    
    const plaintext = await subtle.decrypt(
      { name: 'AES-GCM', iv },
      this.encryptionKey,
      ciphertext
    );
    
    return JSON.parse(decoder.decode(plaintext));
  }
  
  /**
   * Compute SHA-256 hash for content addressing.
   * @param {*} data - Data to hash
   * @returns {Promise<string>}
   */
  async computeHash(data) {
    const encoder = new TextEncoder();
    const dataBuffer = encoder.encode(JSON.stringify(data));
    const hashBuffer = await window.crypto.subtle.digest('SHA-256', dataBuffer);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
  }
  
  /**
   * Store encrypted blob.
   * @param {string} type - Blob type (e.g., 'property', 'state')
   * @param {*} data - Data to store
   * @returns {Promise<string>} Content hash
   */
  async storeBlob(type, data) {
    const hash = await this.computeHash(data);
    const encrypted = await this.encrypt(data);
    
    const blob = {
      hash,
      type,
      encrypted,
      timestamp: Date.now(),
    };
    
    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction(['blobs'], 'readwrite');
      const store = transaction.objectStore('blobs');
      
      const request = store.put(blob);
      request.onsuccess = () => resolve(hash);
      request.onerror = () => reject(request.error);
    });
  }
  
  /**
   * Get blob by hash.
   * @param {string} hash - Content hash
   * @returns {Promise<*>}
   */
  async getBlob(hash) {
    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction(['blobs'], 'readonly');
      const store = transaction.objectStore('blobs');
      
      const request = store.get(hash);
      request.onsuccess = async () => {
        if (!request.result) {
          resolve(null);
          return;
        }
        
        try {
          const data = await this.decrypt(request.result.encrypted);
          resolve(data);
        } catch (e) {
          reject(e);
        }
      };
      request.onerror = () => reject(request.error);
    });
  }
  
  /**
   * Get blobs by type.
   * @param {string} type - Blob type
   * @returns {Promise<Array>}
   */
  async getBlobsByType(type) {
    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction(['blobs'], 'readonly');
      const store = transaction.objectStore('blobs');
      const index = store.index('type');
      
      const results = [];
      const request = index.openCursor(IDBKeyRange.only(type));
      
      request.onsuccess = async (event) => {
        const cursor = event.target.result;
        if (cursor) {
          try {
            const data = await this.decrypt(cursor.value.encrypted);
            results.push({ hash: cursor.value.hash, data, timestamp: cursor.value.timestamp });
          } catch (e) {
            console.error('Decryption failed for blob:', cursor.value.hash);
          }
          cursor.continue();
        } else {
          resolve(results);
        }
      };
      request.onerror = () => reject(request.error);
    });
  }
  
  /**
   * Store metadata.
   * @param {string} key - Metadata key
   * @param {string} category - Category for indexing
   * @param {*} value - Metadata value
   */
  async setMetadata(key, category, value) {
    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction(['metadata'], 'readwrite');
      const store = transaction.objectStore('metadata');
      
      const request = store.put({ key, category, value, timestamp: Date.now() });
      request.onsuccess = () => resolve();
      request.onerror = () => reject(request.error);
    });
  }
  
  /**
   * Get metadata by key.
   * @param {string} key - Metadata key
   * @returns {Promise<*>}
   */
  async getMetadata(key) {
    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction(['metadata'], 'readonly');
      const store = transaction.objectStore('metadata');
      
      const request = store.get(key);
      request.onsuccess = () => resolve(request.result?.value ?? null);
      request.onerror = () => reject(request.error);
    });
  }
  
  /**
   * Queue pending request for offline sync.
   * @param {object} request - Request to queue
   * @returns {Promise<number>} Request ID
   */
  async queuePending(request) {
    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction(['pending'], 'readwrite');
      const store = transaction.objectStore('pending');
      
      const item = {
        ...request,
        timestamp: Date.now(),
        status: 'pending',
      };
      
      const req = store.add(item);
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }
  
  /**
   * Get all pending requests.
   * @returns {Promise<Array>}
   */
  async getPending() {
    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction(['pending'], 'readonly');
      const store = transaction.objectStore('pending');
      
      const request = store.getAll();
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }
  
  /**
   * Remove pending request.
   * @param {number} id - Request ID
   */
  async removePending(id) {
    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction(['pending'], 'readwrite');
      const store = transaction.objectStore('pending');
      
      const request = store.delete(id);
      request.onsuccess = () => resolve();
      request.onerror = () => reject(request.error);
    });
  }
  
  /**
   * Clear expired blobs.
   * @param {number} [maxAge] - Maximum age in milliseconds
   */
  async clearExpired(maxAge = KAGAMI_CONFIG.CACHE_EXPIRY_MS) {
    const cutoff = Date.now() - maxAge;
    
    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction(['blobs'], 'readwrite');
      const store = transaction.objectStore('blobs');
      const index = store.index('timestamp');
      
      const range = IDBKeyRange.upperBound(cutoff);
      let count = 0;
      
      const request = index.openCursor(range);
      request.onsuccess = (event) => {
        const cursor = event.target.result;
        if (cursor) {
          cursor.delete();
          count++;
          cursor.continue();
        } else {
          resolve(count);
        }
      };
      request.onerror = () => reject(request.error);
    });
  }
}

// =============================================================================
// Service Discovery
// =============================================================================

/**
 * Service discovery for finding Kagami backends.
 * Uses multiple fallback methods.
 */
class ServiceDiscovery {
  constructor() {
    this.knownEndpoints = [];
    this.activeEndpoint = null;
  }
  
  /**
   * Discover Kagami backends.
   * @returns {Promise<Array<{url: string, type: string, healthy: boolean}>>}
   */
  async discover() {
    const endpoints = [];
    
    // Try mDNS (browser support limited)
    try {
      const mdnsEndpoints = await this._discoverMDNS();
      endpoints.push(...mdnsEndpoints);
    } catch (e) {
      console.debug('mDNS discovery not available:', e.message);
    }
    
    // Try well-known local addresses
    const localEndpoints = await this._discoverLocal();
    endpoints.push(...localEndpoints);
    
    // Try configured endpoints
    const configuredEndpoints = this._getConfiguredEndpoints();
    endpoints.push(...configuredEndpoints);
    
    // Deduplicate and health check
    const uniqueEndpoints = this._deduplicateEndpoints(endpoints);
    const healthyEndpoints = await this._healthCheck(uniqueEndpoints);
    
    this.knownEndpoints = healthyEndpoints;
    this.activeEndpoint = healthyEndpoints.find(e => e.healthy)?.url ?? null;
    
    return healthyEndpoints;
  }
  
  /**
   * Attempt mDNS discovery.
   * Note: Requires browser support or polyfill.
   * @private
   */
  async _discoverMDNS() {
    // Browser mDNS is limited. This would work in Electron/Tauri.
    // For web, we fall back to other methods.
    
    // Check if dns-sd API is available (Chromium experimental)
    if ('dnsServiceDiscovery' in navigator) {
      // Future: Use navigator.dnsServiceDiscovery
    }
    
    return [];
  }
  
  /**
   * Discover local endpoints.
   * @private
   */
  async _discoverLocal() {
    const candidates = [
      { url: `http://localhost:${KAGAMI_CONFIG.DEFAULT_API_PORT}`, type: 'api' },
      { url: `http://127.0.0.1:${KAGAMI_CONFIG.DEFAULT_API_PORT}`, type: 'api' },
      { url: `http://kagami.local:${KAGAMI_CONFIG.DEFAULT_API_PORT}`, type: 'api' },
      { url: `http://localhost:${KAGAMI_CONFIG.DEFAULT_HUB_PORT}`, type: 'hub' },
      { url: `http://kagami-hub.local:${KAGAMI_CONFIG.DEFAULT_HUB_PORT}`, type: 'hub' },
    ];
    
    // Also check current host if not localhost
    if (window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
      candidates.push({
        url: `http://${window.location.hostname}:${KAGAMI_CONFIG.DEFAULT_API_PORT}`,
        type: 'api',
      });
    }
    
    return candidates;
  }
  
  /**
   * Get configured endpoints from HTML data attributes or global config.
   * @private
   */
  _getConfiguredEndpoints() {
    const endpoints = [];
    
    // Check data attribute on script tag
    const scriptTag = document.querySelector('script[data-kagami-api]');
    if (scriptTag) {
      endpoints.push({
        url: scriptTag.dataset.kagamiApi,
        type: 'api',
      });
    }
    
    // Check global config
    if (window.KAGAMI_ENDPOINTS) {
      for (const url of window.KAGAMI_ENDPOINTS) {
        endpoints.push({ url, type: 'configured' });
      }
    }
    
    // Check localStorage
    const stored = localStorage.getItem('kagami-endpoints');
    if (stored) {
      try {
        const parsed = JSON.parse(stored);
        for (const url of parsed) {
          endpoints.push({ url, type: 'stored' });
        }
      } catch (e) {
        // Ignore invalid JSON
      }
    }
    
    return endpoints;
  }
  
  /**
   * Deduplicate endpoints by URL.
   * @private
   */
  _deduplicateEndpoints(endpoints) {
    const seen = new Set();
    return endpoints.filter(e => {
      if (seen.has(e.url)) return false;
      seen.add(e.url);
      return true;
    });
  }
  
  /**
   * Health check endpoints.
   * @private
   */
  async _healthCheck(endpoints) {
    const results = await Promise.all(
      endpoints.map(async (endpoint) => {
        try {
          const controller = new AbortController();
          const timeout = setTimeout(() => controller.abort(), 2000);
          
          const response = await fetch(`${endpoint.url}/health`, {
            method: 'GET',
            signal: controller.signal,
          });
          
          clearTimeout(timeout);
          
          return {
            ...endpoint,
            healthy: response.ok,
            latency: performance.now(), // Simplified
          };
        } catch (e) {
          return { ...endpoint, healthy: false, error: e.message };
        }
      })
    );
    
    // Sort by health and latency
    return results.sort((a, b) => {
      if (a.healthy !== b.healthy) return b.healthy ? 1 : -1;
      return (a.latency ?? Infinity) - (b.latency ?? Infinity);
    });
  }
  
  /**
   * Get best available endpoint.
   * @returns {string|null}
   */
  getBestEndpoint() {
    return this.activeEndpoint;
  }
  
  /**
   * Store discovered endpoints for future use.
   */
  persistEndpoints() {
    const urls = this.knownEndpoints
      .filter(e => e.healthy)
      .map(e => e.url);
    localStorage.setItem('kagami-endpoints', JSON.stringify(urls));
  }
}

// =============================================================================
// WebSocket Manager
// =============================================================================

/**
 * Manages WebSocket connection for real-time updates.
 */
class WebSocketManager {
  constructor() {
    this.ws = null;
    this.url = null;
    this.reconnectCount = 0;
    this.handlers = new Map();
    this.connected = false;
  }
  
  /**
   * Connect to WebSocket endpoint.
   * @param {string} url - WebSocket URL
   * @returns {Promise<void>}
   */
  async connect(url) {
    this.url = url;
    
    return new Promise((resolve, reject) => {
      try {
        this.ws = new WebSocket(url);
        
        this.ws.onopen = () => {
          this.connected = true;
          this.reconnectCount = 0;
          console.log('🔗 WebSocket connected:', url);
          resolve();
        };
        
        this.ws.onclose = (event) => {
          this.connected = false;
          console.log('WebSocket closed:', event.code, event.reason);
          this._scheduleReconnect();
        };
        
        this.ws.onerror = (error) => {
          console.error('WebSocket error:', error);
          if (!this.connected) {
            reject(error);
          }
        };
        
        this.ws.onmessage = (event) => {
          this._handleMessage(event.data);
        };
        
      } catch (e) {
        reject(e);
      }
    });
  }
  
  /**
   * Disconnect WebSocket.
   */
  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.connected = false;
  }
  
  /**
   * Send message.
   * @param {object} message - Message to send
   */
  send(message) {
    if (this.ws && this.connected) {
      this.ws.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket not connected');
    }
  }
  
  /**
   * Subscribe to message type.
   * @param {string} type - Message type
   * @param {function} handler - Handler function
   */
  subscribe(type, handler) {
    if (!this.handlers.has(type)) {
      this.handlers.set(type, new Set());
    }
    this.handlers.get(type).add(handler);
  }
  
  /**
   * Unsubscribe from message type.
   * @param {string} type - Message type
   * @param {function} handler - Handler function
   */
  unsubscribe(type, handler) {
    if (this.handlers.has(type)) {
      this.handlers.get(type).delete(handler);
    }
  }
  
  /**
   * Handle incoming message.
   * @private
   */
  _handleMessage(data) {
    try {
      const message = JSON.parse(data);
      const type = message.type || 'message';
      
      // Call type-specific handlers
      if (this.handlers.has(type)) {
        for (const handler of this.handlers.get(type)) {
          try {
            handler(message);
          } catch (e) {
            console.error('Handler error:', e);
          }
        }
      }
      
      // Call catch-all handlers
      if (this.handlers.has('*')) {
        for (const handler of this.handlers.get('*')) {
          try {
            handler(message);
          } catch (e) {
            console.error('Handler error:', e);
          }
        }
      }
    } catch (e) {
      console.error('Failed to parse WebSocket message:', e);
    }
  }
  
  /**
   * Schedule reconnection attempt.
   * @private
   */
  _scheduleReconnect() {
    if (this.reconnectCount >= KAGAMI_CONFIG.WS_MAX_RECONNECTS) {
      console.warn('Max WebSocket reconnection attempts reached');
      return;
    }
    
    const delay = KAGAMI_CONFIG.WS_RECONNECT_INTERVAL * Math.pow(2, this.reconnectCount);
    this.reconnectCount++;
    
    setTimeout(() => {
      if (this.url && !this.connected) {
        console.log(`Attempting WebSocket reconnect (${this.reconnectCount})...`);
        this.connect(this.url).catch(e => {
          console.error('Reconnect failed:', e);
        });
      }
    }, delay);
  }
}

// =============================================================================
// Kagami Agent — Main Interface
// =============================================================================

/**
 * Main Kagami Agent class.
 * Provides unified interface for HTML agents to interact with Kagami backends.
 * 
 * @example
 * const agent = new KagamiAgent();
 * await agent.initialize();
 * 
 * // Discover backends
 * const backends = await agent.discover();
 * 
 * // Fetch data (uses cache if offline)
 * const property = await agent.fetch('property', { address: '123 Main St' });
 * 
 * // Submit for consensus
 * const result = await agent.submit('update_state', { key: 'value' });
 * 
 * // Subscribe to updates
 * agent.subscribe('state.changed', (data) => console.log('State:', data));
 */
class KagamiAgent {
  constructor(options = {}) {
    this.options = {
      autoDiscover: true,
      autoConnect: true,
      cacheEnabled: true,
      encryptionPassphrase: null,
      ...options,
    };
    
    this.store = new CryptoStore();
    this.discovery = new ServiceDiscovery();
    this.wsManager = new WebSocketManager();
    
    this.apiEndpoint = null;
    this.wsEndpoint = null;
    this.initialized = false;
    this.online = navigator.onLine;
    
    // Track network status
    window.addEventListener('online', () => this._handleOnline());
    window.addEventListener('offline', () => this._handleOffline());
  }
  
  /**
   * Initialize the agent.
   * @returns {Promise<void>}
   */
  async initialize() {
    if (this.initialized) return;
    
    // Initialize encrypted store
    if (this.options.cacheEnabled) {
      await this.store.initialize(this.options.encryptionPassphrase);
      console.log('✅ CryptoStore initialized');
    }
    
    // Discover backends
    if (this.options.autoDiscover) {
      await this.discover();
    }
    
    // Connect WebSocket
    if (this.options.autoConnect && this.apiEndpoint) {
      await this._connectWebSocket();
    }
    
    // Sync pending requests
    if (this.online) {
      await this._syncPending();
    }
    
    this.initialized = true;
    console.log('✅ KagamiAgent initialized');
  }
  
  /**
   * Discover Kagami backends.
   * @returns {Promise<Array>} Discovered endpoints
   */
  async discover() {
    const endpoints = await this.discovery.discover();
    
    // Set best endpoint
    this.apiEndpoint = this.discovery.getBestEndpoint();
    
    if (this.apiEndpoint) {
      // Derive WebSocket URL
      const url = new URL(this.apiEndpoint);
      this.wsEndpoint = `ws://${url.host}/ws`;
      
      // Persist for future use
      this.discovery.persistEndpoints();
      
      console.log('✅ Discovered Kagami backend:', this.apiEndpoint);
    } else {
      console.warn('⚠️ No Kagami backend found (offline mode)');
    }
    
    return endpoints;
  }
  
  /**
   * Fetch data from Kagami backend.
   * Uses cache if offline or for faster response.
   * 
   * @param {string} resource - Resource type (e.g., 'property', 'state', 'config')
   * @param {object} [params] - Query parameters
   * @param {object} [options] - Fetch options
   * @returns {Promise<*>}
   */
  async fetch(resource, params = {}, options = {}) {
    const cacheKey = this._getCacheKey(resource, params);
    const forceRefresh = options.forceRefresh || false;
    
    // Try cache first (unless forced refresh)
    if (this.options.cacheEnabled && !forceRefresh) {
      const cached = await this.store.getMetadata(cacheKey);
      if (cached && this._isCacheValid(cached)) {
        const blob = await this.store.getBlob(cached.hash);
        if (blob) {
          console.debug('Cache hit:', cacheKey);
          return blob;
        }
      }
    }
    
    // Try network
    if (this.online && this.apiEndpoint) {
      try {
        const url = this._buildUrl(resource, params);
        const response = await this._request('GET', url, null, options.timeout);
        
        // Cache result
        if (this.options.cacheEnabled) {
          const hash = await this.store.storeBlob(resource, response);
          await this.store.setMetadata(cacheKey, resource, {
            hash,
            timestamp: Date.now(),
          });
        }
        
        return response;
      } catch (e) {
        console.error('Fetch failed:', e);
        
        // Fall back to cache
        if (this.options.cacheEnabled) {
          const cached = await this.store.getMetadata(cacheKey);
          if (cached) {
            const blob = await this.store.getBlob(cached.hash);
            if (blob) {
              console.warn('Using stale cache due to network error');
              return blob;
            }
          }
        }
        
        throw e;
      }
    }
    
    // Offline - try cache
    if (this.options.cacheEnabled) {
      const cached = await this.store.getMetadata(cacheKey);
      if (cached) {
        const blob = await this.store.getBlob(cached.hash);
        if (blob) {
          console.debug('Offline cache hit:', cacheKey);
          return blob;
        }
      }
    }
    
    throw new Error('No network and no cached data');
  }
  
  /**
   * Submit request for consensus.
   * Queues if offline.
   * 
   * @param {string} operation - Operation identifier
   * @param {object} data - Operation data
   * @param {object} [options] - Submit options
   * @returns {Promise<object>}
   */
  async submit(operation, data, options = {}) {
    const request = {
      operation,
      data,
      clientId: this._getClientId(),
      timestamp: Date.now(),
    };
    
    if (this.online && this.apiEndpoint) {
      try {
        const url = `${this.apiEndpoint}/api/v1/consensus/submit`;
        return await this._request('POST', url, request, options.timeout);
      } catch (e) {
        console.error('Submit failed:', e);
        
        // Queue for later
        if (this.options.cacheEnabled) {
          const id = await this.store.queuePending(request);
          console.log('Request queued for offline sync:', id);
          return { queued: true, id };
        }
        
        throw e;
      }
    }
    
    // Offline - queue request
    if (this.options.cacheEnabled) {
      const id = await this.store.queuePending(request);
      console.log('Request queued (offline):', id);
      return { queued: true, id, offline: true };
    }
    
    throw new Error('No network and caching disabled');
  }
  
  /**
   * Subscribe to real-time updates.
   * 
   * @param {string} topic - Topic to subscribe to
   * @param {function} handler - Handler function
   */
  subscribe(topic, handler) {
    this.wsManager.subscribe(topic, handler);
    
    // Send subscription message if connected
    if (this.wsManager.connected) {
      this.wsManager.send({
        type: 'subscribe',
        topic,
      });
    }
  }
  
  /**
   * Unsubscribe from updates.
   * 
   * @param {string} topic - Topic to unsubscribe from
   * @param {function} handler - Handler function
   */
  unsubscribe(topic, handler) {
    this.wsManager.unsubscribe(topic, handler);
    
    if (this.wsManager.connected) {
      this.wsManager.send({
        type: 'unsubscribe',
        topic,
      });
    }
  }
  
  /**
   * Get agent status.
   * @returns {object}
   */
  getStatus() {
    return {
      initialized: this.initialized,
      online: this.online,
      apiEndpoint: this.apiEndpoint,
      wsConnected: this.wsManager.connected,
      knownEndpoints: this.discovery.knownEndpoints,
    };
  }
  
  /**
   * Clear all cached data.
   */
  async clearCache() {
    if (this.store.db) {
      const transaction = this.store.db.transaction(['blobs', 'metadata'], 'readwrite');
      transaction.objectStore('blobs').clear();
      transaction.objectStore('metadata').clear();
    }
  }
  
  // =========================================================================
  // Private Methods
  // =========================================================================
  
  async _connectWebSocket() {
    if (this.wsEndpoint) {
      try {
        await this.wsManager.connect(this.wsEndpoint);
      } catch (e) {
        console.warn('WebSocket connection failed:', e);
      }
    }
  }
  
  async _syncPending() {
    if (!this.options.cacheEnabled) return;
    
    const pending = await this.store.getPending();
    console.log(`Syncing ${pending.length} pending requests...`);
    
    for (const item of pending) {
      try {
        const url = `${this.apiEndpoint}/api/v1/consensus/submit`;
        await this._request('POST', url, item);
        await this.store.removePending(item.id);
        console.log('Synced pending request:', item.id);
      } catch (e) {
        console.error('Failed to sync pending request:', item.id, e);
      }
    }
  }
  
  _handleOnline() {
    this.online = true;
    console.log('🌐 Network online');
    
    // Reconnect and sync
    this._connectWebSocket();
    this._syncPending();
  }
  
  _handleOffline() {
    this.online = false;
    console.log('📴 Network offline');
  }
  
  _getCacheKey(resource, params) {
    const paramStr = Object.entries(params)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([k, v]) => `${k}=${v}`)
      .join('&');
    return `${resource}:${paramStr}`;
  }
  
  _isCacheValid(cached) {
    if (!cached || !cached.timestamp) return false;
    return Date.now() - cached.timestamp < KAGAMI_CONFIG.CACHE_EXPIRY_MS;
  }
  
  _buildUrl(resource, params) {
    const url = new URL(`${this.apiEndpoint}/api/v1/${resource}`);
    for (const [key, value] of Object.entries(params)) {
      url.searchParams.set(key, String(value));
    }
    return url.toString();
  }
  
  async _request(method, url, body = null, timeout = KAGAMI_CONFIG.REQUEST_TIMEOUT) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);
    
    try {
      const options = {
        method,
        headers: {
          'Content-Type': 'application/json',
        },
        signal: controller.signal,
      };
      
      if (body) {
        options.body = JSON.stringify(body);
      }
      
      const response = await fetch(url, options);
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      return await response.json();
    } finally {
      clearTimeout(timeoutId);
    }
  }
  
  _getClientId() {
    let clientId = localStorage.getItem('kagami-client-id');
    if (!clientId) {
      clientId = `agent-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
      localStorage.setItem('kagami-client-id', clientId);
    }
    return clientId;
  }
}

// =============================================================================
// Export
// =============================================================================

// ES Module export
export { KagamiAgent, CryptoStore, ServiceDiscovery, WebSocketManager, KAGAMI_CONFIG };

// Global export for script tag usage
if (typeof window !== 'undefined') {
  window.KagamiAgent = KagamiAgent;
  window.CryptoStore = CryptoStore;
  window.ServiceDiscovery = ServiceDiscovery;
  window.WebSocketManager = WebSocketManager;
  window.KAGAMI_CONFIG = KAGAMI_CONFIG;
}
