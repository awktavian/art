/**
 * Commerce Client — wishlist and orders for Jill's galleries
 *
 * STORE OF RECORD: localStorage. Not a fallback — the declared source.
 *
 * This file used to hardcode `https://api.kagami.ai/api/commerce` and treat
 * localStorage as what it degraded to when that host failed. Measured
 * 2026-09-04: api.kagami.ai serves no such vhost (TLS handshake fails,
 * "tlsv1 unrecognized name") and resolves to the same parked addresses as
 * via.placeholder.com. There is no commerce backend. So every page load ran a
 * doomed 5s fetch, swallowed the failure, printed "🔌 Commerce: Offline mode",
 * and carried a `_isOnline` flag that could never become true — and every
 * write silently accumulated in a sync queue nothing would ever drain.
 *
 * The remote layer is now OPT-IN and named. Set, before this script loads:
 *
 *   <script>window.KAGAMI_COMMERCE_API = 'https://commerce.example/api/commerce';</script>
 *
 * With no base configured, `remoteStatus()` reports `not_configured` and no
 * network call is attempted. With one configured, a failure reports
 * `unreachable` with the error text and the URL that was tried — it does not
 * silently pretend the write landed.
 *
 * Created: January 20, 2026
 * Author: Kagami (鏡)
 */

const CommerceClient = (() => {
  // Configuration. No default host: a hardcoded one that answers nothing is
  // worse than none, because it looks like the feature exists.
  const API_BASE = (typeof window !== 'undefined' && window.KAGAMI_COMMERCE_API) || null;
  const IDENTITY_ID = 'jill';
  const TIMEOUT_MS = 5000;

  // Local storage keys (fallback)
  const LS_HEARTS_KEY = 'jill_hearts_v2';
  const LS_ORDERS_KEY = 'jill_orders_v3';
  const LS_SYNC_QUEUE_KEY = 'jill_sync_queue';

  // State
  let _isOnline = false;
  // 'not_configured' | 'unreachable' | 'online'; plus the last failure text.
  let _remoteStatus = API_BASE ? 'unreachable' : 'not_configured';
  let _remoteDetail = API_BASE
    ? 'no request attempted yet'
    : 'window.KAGAMI_COMMERCE_API is unset — localStorage is the store of record';
  let _hearts = new Set();
  let _orders = [];
  let _syncQueue = [];
  let _initialized = false;

  // =========================================================================
  // INITIALIZATION
  // =========================================================================

  async function initialize() {
    if (_initialized) return;

    // localStorage is the store of record, so it is read first and always.
    _loadFromLocalStorage();

    if (!API_BASE) {
      // Not a degraded mode: no backend was ever configured. Say so once,
      // truthfully, instead of printing "Offline mode" about a service that
      // does not exist.
      _isOnline = false;
      _remoteStatus = 'not_configured';
      _remoteDetail = 'window.KAGAMI_COMMERCE_API is unset — localStorage is the store of record';
    } else {
      const url = `${API_BASE}/sync/state?identity_id=${IDENTITY_ID}`;
      try {
        const state = await _fetchWithTimeout(url);
        if (state && state.wishlist) {
          _hearts = new Set(state.wishlist.map(w => w.product_id));
          _orders = state.orders || [];
          _isOnline = true;
          _remoteStatus = 'online';
          _remoteDetail = API_BASE;
          _saveToLocalStorage();
        } else {
          _isOnline = false;
          _remoteStatus = 'unreachable';
          _remoteDetail = `${url} answered without a wishlist field`;
          console.warn(`Commerce: ${_remoteDetail}`);
        }
      } catch (e) {
        _isOnline = false;
        _remoteStatus = 'unreachable';
        _remoteDetail = `${url} — ${e.message}`;
        console.warn(`Commerce: backend unreachable — ${_remoteDetail}`);
      }
    }

    // Process any queued operations
    if (_isOnline) {
      await _processQueue();
    }

    _initialized = true;
    return { online: _isOnline, hearts: [..._hearts], orders: _orders };
  }

  // =========================================================================
  // WISHLIST (HEARTS)
  // =========================================================================

  async function addToWishlist(productData) {
    const productId = productData.product_id || productData.id;
    _hearts.add(productId);
    _saveToLocalStorage();

    if (_isOnline) {
      try {
        await _fetchWithTimeout(`${API_BASE}/wishlist`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            identity_id: IDENTITY_ID,
            product_id: productId,
            brand: productData.brand,
            item_name: productData.name || productData.item_name,
            price_cents: productData.price ? productData.price * 100 : null,
            product_url: productData.product_url,
            image_url: productData.image_url || productData.image,
            source_gallery: productData.source_gallery || window.location.pathname.split('/').pop(),
          }),
        });
      } catch (e) {
        _queueOperation({ action: 'wishlist_add', data: productData });
      }
    } else {
      _queueOperation({ action: 'wishlist_add', data: productData });
    }

    return true;
  }

  async function removeFromWishlist(productId) {
    _hearts.delete(productId);
    _saveToLocalStorage();

    if (_isOnline) {
      try {
        await _fetchWithTimeout(
          `${API_BASE}/wishlist/${encodeURIComponent(productId)}?identity_id=${IDENTITY_ID}`,
          { method: 'DELETE' }
        );
      } catch (e) {
        _queueOperation({ action: 'wishlist_remove', data: { product_id: productId } });
      }
    } else {
      _queueOperation({ action: 'wishlist_remove', data: { product_id: productId } });
    }

    return true;
  }

  async function toggleWishlist(productData) {
    const productId = productData.product_id || productData.id;
    if (_hearts.has(productId)) {
      await removeFromWishlist(productId);
      return false;
    } else {
      await addToWishlist(productData);
      return true;
    }
  }

  function isWishlisted(productId) {
    return _hearts.has(productId);
  }

  function getWishlist() {
    return [..._hearts];
  }

  // =========================================================================
  // ORDERS
  // =========================================================================

  async function getOrders() {
    if (_isOnline) {
      try {
        const orders = await _fetchWithTimeout(`${API_BASE}/orders?identity_id=${IDENTITY_ID}`);
        _orders = orders || [];
        _saveToLocalStorage();
        return _orders;
      } catch (e) {
        _isOnline = false;
        _remoteStatus = 'unreachable';
        _remoteDetail = `${API_BASE}/orders — ${e.message}`;
        console.warn(`Commerce: order fetch failed, serving the local store — ${_remoteDetail}`);
      }
    }
    return _orders;
  }

  async function updateOrderStatus(orderId, newStatus, options = {}) {
    // Update locally
    const order = _orders.find(o => o.id === orderId);
    if (order) {
      order.status = newStatus;
      order.updated_at = new Date().toISOString();
      if (options.tracking_number) order.tracking_number = options.tracking_number;
      if (options.carrier) order.carrier = options.carrier;
    }
    _saveToLocalStorage();

    // Sync to API
    if (_isOnline) {
      try {
        await _fetchWithTimeout(`${API_BASE}/orders/${orderId}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            status: newStatus,
            ...options,
          }),
        });
      } catch (e) {
        _queueOperation({ action: 'order_update', data: { order_id: orderId, status: newStatus, ...options } });
      }
    } else {
      _queueOperation({ action: 'order_update', data: { order_id: orderId, status: newStatus, ...options } });
    }

    return order;
  }

  // =========================================================================
  // SYNC
  // =========================================================================

  async function syncToBackend() {
    if (!API_BASE) {
      return { success: false, reason: 'not_configured', detail: _remoteDetail };
    }
    if (!_isOnline) {
      try {
        const response = await _fetchWithTimeout(`${API_BASE}/sync/state?identity_id=${IDENTITY_ID}`);
        if (response) {
          _isOnline = true;
        }
      } catch (e) {
        _remoteStatus = 'unreachable';
        _remoteDetail = `${API_BASE}/sync/state — ${e.message}`;
        return { success: false, reason: 'unreachable', detail: _remoteDetail };
      }
    }

    await _processQueue();

    try {
      await _fetchWithTimeout(`${API_BASE}/sync`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          identity_id: IDENTITY_ID,
          hearts: [..._hearts],
          orders: _orders.map(o => ({ id: o.id, status: o.status })),
        }),
      });
      return { success: true };
    } catch (e) {
      return { success: false, reason: e.message };
    }
  }

  async function hydrateFromBackend() {
    if (!API_BASE) return null;
    try {
      const data = await _fetchWithTimeout(
        `${API_BASE}/sync/hydrate?identity_id=${IDENTITY_ID}&gallery=${window.location.pathname.split('/').pop()}`
      );
      if (data) {
        _hearts = new Set(data.hearts || []);
        _orders = data.orders || [];
        _isOnline = true;
        _saveToLocalStorage();
        return data;
      }
    } catch (e) {
      console.warn('Hydration from backend failed:', e);
    }
    return null;
  }

  // =========================================================================
  // INTERNAL HELPERS
  // =========================================================================

  function _loadFromLocalStorage() {
    try {
      const hearts = localStorage.getItem(LS_HEARTS_KEY);
      _hearts = hearts ? new Set(JSON.parse(hearts)) : new Set();

      const orders = localStorage.getItem(LS_ORDERS_KEY);
      _orders = orders ? JSON.parse(orders) : [];

      const queue = localStorage.getItem(LS_SYNC_QUEUE_KEY);
      _syncQueue = queue ? JSON.parse(queue) : [];
    } catch (e) {
      console.warn('Failed to load from localStorage:', e);
    }
  }

  function _saveToLocalStorage() {
    try {
      localStorage.setItem(LS_HEARTS_KEY, JSON.stringify([..._hearts]));
      localStorage.setItem(LS_ORDERS_KEY, JSON.stringify(_orders));
      localStorage.setItem(LS_SYNC_QUEUE_KEY, JSON.stringify(_syncQueue));
    } catch (e) {
      console.warn('Failed to save to localStorage:', e);
    }
  }

  function _queueOperation(op) {
    // Queueing against a backend that was never configured grows an unbounded
    // localStorage list nothing can ever drain — the write is already durable
    // in the local store, which is the store of record. Only queue when there
    // is a configured base that a later sync could actually reach.
    if (!API_BASE) return;
    op.queued_at = Date.now();
    _syncQueue.push(op);
    _saveToLocalStorage();
  }

  async function _processQueue() {
    if (_syncQueue.length === 0) return;

    const queue = [..._syncQueue];
    _syncQueue = [];
    _saveToLocalStorage();

    for (const op of queue) {
      try {
        switch (op.action) {
          case 'wishlist_add':
            await addToWishlist(op.data);
            break;
          case 'wishlist_remove':
            await removeFromWishlist(op.data.product_id);
            break;
          case 'order_update':
            await updateOrderStatus(op.data.order_id, op.data.status, op.data);
            break;
        }
      } catch (e) {
        // Re-queue failed operations
        _syncQueue.push(op);
      }
    }
    _saveToLocalStorage();
  }

  async function _fetchWithTimeout(url, options = {}) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), TIMEOUT_MS);

    try {
      const response = await fetch(url, {
        ...options,
        signal: controller.signal,
      });
      clearTimeout(timeoutId);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      return await response.json();
    } catch (e) {
      clearTimeout(timeoutId);
      throw e;
    }
  }

  // =========================================================================
  // PUBLIC API
  // =========================================================================

  return {
    initialize,
    // Wishlist
    addToWishlist,
    removeFromWishlist,
    toggleWishlist,
    isWishlisted,
    getWishlist,
    // Orders
    getOrders,
    updateOrderStatus,
    // Sync
    syncToBackend,
    hydrateFromBackend,
    // State
    isOnline: () => _isOnline,
    /** Typed backend availability — never a bare boolean that hides WHY. */
    remoteStatus: () => ({ base: API_BASE, status: _remoteStatus, detail: _remoteDetail }),
    getState: () => ({
      hearts: [..._hearts],
      orders: _orders,
      online: _isOnline,
      remote: { base: API_BASE, status: _remoteStatus, detail: _remoteDetail },
    }),
  };
})();

// Export for modules
if (typeof module !== 'undefined' && module.exports) {
  module.exports = CommerceClient;
}

// Make available globally
window.CommerceClient = CommerceClient;
