/**
 * Mesh Service - Kagami Mesh Network SDK Integration
 *
 * Colony: Nexus (e4) - Integration
 *
 * Provides a clean Kotlin API for the UniFFI-generated mesh SDK bindings:
 * - Ed25519 identity management for peer authentication
 * - Connection state management with circuit breaker pattern
 * - XChaCha20-Poly1305 encryption/decryption
 * - CRDT helpers (vector clocks, G-counters)
 * - X25519 Diffie-Hellman key exchange
 *
 * h(x) >= 0. Always.
 */

package com.kagami.android.services

import android.content.SharedPreferences
import android.util.Log
import com.kagami.android.data.Result
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import uniffi.kagami_mesh_sdk.*
import javax.inject.Inject
import javax.inject.Named
import javax.inject.Singleton

/**
 * Connection state for the mesh network.
 */
enum class MeshConnectionState {
    /** Not connected to any peer */
    DISCONNECTED,
    /** Attempting to connect */
    CONNECTING,
    /** Connected and authenticated */
    CONNECTED,
    /** Circuit breaker is open - waiting for recovery */
    CIRCUIT_OPEN,
    /** Testing recovery after circuit breaker timeout */
    HALF_OPEN
}

/**
 * Vector clock comparison result.
 */
enum class VectorClockOrdering {
    /** This clock happened before the other */
    BEFORE,
    /** This clock happened after the other */
    AFTER,
    /** Clocks are concurrent (no causal relationship) */
    CONCURRENT,
    /** Clocks are equal */
    EQUAL
}

/**
 * Service for mesh network operations.
 *
 * Wraps the UniFFI-generated bindings with a clean, idiomatic Kotlin API
 * that integrates with the existing Android app patterns.
 *
 * Usage:
 * ```kotlin
 * @Inject lateinit var meshService: MeshService
 *
 * // Initialize with stored or new identity
 * meshService.initialize()
 *
 * // Sign and verify messages
 * val signature = meshService.sign(message)
 * val isValid = meshService.verify(peerId, message, signature)
 *
 * // Encrypt/decrypt data
 * val ciphertext = meshService.encrypt(key, plaintext)
 * val plaintext = meshService.decrypt(key, ciphertext)
 * ```
 */
@Singleton
class MeshService @Inject constructor(
    @Named("encrypted") private val encryptedPrefs: SharedPreferences
) {
    companion object {
        private const val TAG = "MeshService"

        // Preference keys for identity persistence
        private const val KEY_IDENTITY_BASE64 = "mesh_identity_base64"
        private const val KEY_PEER_ID = "mesh_peer_id"
    }

    // Thread-safe state management
    private val mutex = Mutex()

    // Identity state
    private var identity: MeshIdentity? = null
    private var _peerId: String? = null

    // Connection state (using UniFFI MeshConnection for circuit breaker)
    private var connection: MeshConnection? = null

    private val _connectionState = MutableStateFlow(MeshConnectionState.DISCONNECTED)
    val connectionState: StateFlow<MeshConnectionState> = _connectionState

    private val _isInitialized = MutableStateFlow(false)
    val isInitialized: StateFlow<Boolean> = _isInitialized

    /**
     * Get the local peer ID (hex-encoded public key).
     */
    val peerId: String?
        get() = _peerId

    /**
     * Initialize the mesh service.
     *
     * Loads an existing identity from secure storage or generates a new one.
     * Also initializes the connection state tracker.
     */
    suspend fun initialize(): Result<String> = withContext(Dispatchers.IO) {
        mutex.withLock {
            try {
                // Initialize connection tracker
                connection = MeshConnection()

                // Try to load existing identity
                val storedIdentity = encryptedPrefs.getString(KEY_IDENTITY_BASE64, null)

                identity = if (storedIdentity != null) {
                    try {
                        MeshIdentity.fromBase64(storedIdentity)
                    } catch (e: MeshSdkException) {
                        Log.w(TAG, "Failed to load stored identity, generating new one", e)
                        createAndStoreNewIdentity()
                    }
                } else {
                    createAndStoreNewIdentity()
                }

                _peerId = identity?.peerId()
                _isInitialized.value = true

                Log.i(TAG, "Mesh service initialized with peer ID: $_peerId")
                Result.success(_peerId!!)
            } catch (e: Exception) {
                Log.e(TAG, "Failed to initialize mesh service", e)
                Result.error(e)
            }
        }
    }

    private fun createAndStoreNewIdentity(): MeshIdentity {
        val newIdentity = MeshIdentity()
        val base64 = newIdentity.toBase64()

        encryptedPrefs.edit()
            .putString(KEY_IDENTITY_BASE64, base64)
            .putString(KEY_PEER_ID, newIdentity.peerId())
            .apply()

        Log.i(TAG, "Generated and stored new mesh identity")
        return newIdentity
    }

    /**
     * Sign a message with the local identity.
     *
     * @param message The message bytes to sign
     * @return Hex-encoded signature, or error if not initialized
     */
    suspend fun sign(message: ByteArray): Result<String> = withContext(Dispatchers.IO) {
        mutex.withLock {
            val id = identity
            if (id == null) {
                return@withContext Result.error("Mesh service not initialized")
            }

            try {
                val signature = id.sign(message)
                Result.success(signature)
            } catch (e: MeshSdkException) {
                Log.e(TAG, "Failed to sign message", e)
                Result.error(e)
            }
        }
    }

    /**
     * Verify a signature from a peer.
     *
     * @param publicKeyHex The peer's public key (hex-encoded)
     * @param message The original message bytes
     * @param signatureHex The signature to verify (hex-encoded)
     * @return True if signature is valid
     */
    suspend fun verify(
        publicKeyHex: String,
        message: ByteArray,
        signatureHex: String
    ): Result<Boolean> = withContext(Dispatchers.IO) {
        try {
            val isValid = verifySignature(publicKeyHex, message, signatureHex)
            Result.success(isValid)
        } catch (e: MeshSdkException) {
            Log.e(TAG, "Failed to verify signature", e)
            Result.error(e)
        }
    }

    /**
     * Verify a signature using the local identity's public key.
     */
    suspend fun verifyLocal(
        message: ByteArray,
        signatureHex: String
    ): Result<Boolean> = withContext(Dispatchers.IO) {
        mutex.withLock {
            val id = identity
            if (id == null) {
                return@withContext Result.error("Mesh service not initialized")
            }

            try {
                val isValid = id.verify(message, signatureHex)
                Result.success(isValid)
            } catch (e: MeshSdkException) {
                Log.e(TAG, "Failed to verify signature", e)
                Result.error(e)
            }
        }
    }

    // ==================== Encryption ====================

    /**
     * Generate a new random encryption key.
     *
     * @return Hex-encoded 256-bit key for XChaCha20-Poly1305
     */
    fun generateKey(): String {
        return generateCipherKey()
    }

    /**
     * Encrypt data with XChaCha20-Poly1305.
     *
     * @param keyHex Hex-encoded 256-bit key
     * @param plaintext Data to encrypt
     * @return Hex-encoded ciphertext (includes nonce)
     */
    suspend fun encrypt(keyHex: String, plaintext: ByteArray): Result<String> =
        withContext(Dispatchers.IO) {
            try {
                val ciphertext = encryptData(keyHex, plaintext)
                Result.success(ciphertext)
            } catch (e: MeshSdkException) {
                Log.e(TAG, "Encryption failed", e)
                Result.error(e)
            }
        }

    /**
     * Decrypt data with XChaCha20-Poly1305.
     *
     * @param keyHex Hex-encoded 256-bit key
     * @param ciphertextHex Hex-encoded ciphertext (includes nonce)
     * @return Decrypted plaintext
     */
    suspend fun decrypt(keyHex: String, ciphertextHex: String): Result<ByteArray> =
        withContext(Dispatchers.IO) {
            try {
                val plaintext = decryptData(keyHex, ciphertextHex)
                Result.success(plaintext)
            } catch (e: MeshSdkException) {
                Log.e(TAG, "Decryption failed", e)
                Result.error(e)
            }
        }

    // ==================== Key Exchange ====================

    /**
     * Generate an X25519 key pair for Diffie-Hellman key exchange.
     *
     * @return Pair of (secretKeyHex, publicKeyHex)
     */
    fun generateX25519KeyPair(): Pair<String, String> {
        val keyPair = generateX25519Keypair()
        return Pair(keyPair.secretKeyHex, keyPair.publicKeyHex)
    }

    /**
     * Derive a shared encryption key using X25519 Diffie-Hellman.
     *
     * @param secretKeyHex Our secret key (hex-encoded)
     * @param peerPublicKeyHex Peer's public key (hex-encoded)
     * @return Derived encryption key (hex-encoded)
     */
    suspend fun deriveSharedKey(
        secretKeyHex: String,
        peerPublicKeyHex: String
    ): Result<String> = withContext(Dispatchers.IO) {
        try {
            val sharedKey = x25519DeriveKey(secretKeyHex, peerPublicKeyHex)
            Result.success(sharedKey)
        } catch (e: MeshSdkException) {
            Log.e(TAG, "Key derivation failed", e)
            Result.error(e)
        }
    }

    // ==================== Connection State (Circuit Breaker) ====================

    /**
     * Signal that a connection attempt is starting.
     */
    suspend fun onConnecting(): Result<Unit> = withContext(Dispatchers.IO) {
        mutex.withLock {
            val conn = connection
            if (conn == null) {
                return@withContext Result.error("Mesh service not initialized")
            }

            try {
                conn.onConnect()
                updateConnectionState()
                Result.success(Unit)
            } catch (e: MeshSdkException) {
                Log.e(TAG, "Failed to signal connecting", e)
                Result.error(e)
            }
        }
    }

    /**
     * Signal that connection succeeded.
     */
    suspend fun onConnected(): Result<Unit> = withContext(Dispatchers.IO) {
        mutex.withLock {
            val conn = connection
            if (conn == null) {
                return@withContext Result.error("Mesh service not initialized")
            }

            try {
                conn.onConnected()
                updateConnectionState()
                Result.success(Unit)
            } catch (e: MeshSdkException) {
                Log.e(TAG, "Failed to signal connected", e)
                Result.error(e)
            }
        }
    }

    /**
     * Signal that connection failed.
     */
    suspend fun onConnectionFailed(reason: String): Result<Unit> = withContext(Dispatchers.IO) {
        mutex.withLock {
            val conn = connection
            if (conn == null) {
                return@withContext Result.error("Mesh service not initialized")
            }

            try {
                conn.onFailure(reason)
                updateConnectionState()
                Result.success(Unit)
            } catch (e: MeshSdkException) {
                Log.e(TAG, "Failed to signal failure", e)
                Result.error(e)
            }
        }
    }

    /**
     * Signal disconnection.
     */
    suspend fun onDisconnected(reason: String): Result<Unit> = withContext(Dispatchers.IO) {
        mutex.withLock {
            val conn = connection
            if (conn == null) {
                return@withContext Result.error("Mesh service not initialized")
            }

            try {
                conn.onDisconnect(reason)
                updateConnectionState()
                Result.success(Unit)
            } catch (e: MeshSdkException) {
                Log.e(TAG, "Failed to signal disconnect", e)
                Result.error(e)
            }
        }
    }

    /**
     * Check if circuit breaker allows a connection attempt.
     */
    fun shouldAttemptConnection(): Boolean {
        val conn = connection ?: return true
        return conn.shouldAttemptRecovery() || conn.isConnected()
    }

    /**
     * Get the current backoff time in milliseconds.
     */
    fun getBackoffMs(): Long {
        val conn = connection ?: return 0
        return conn.backoffMs().toLong()
    }

    /**
     * Get the current failure count.
     */
    fun getFailureCount(): Int {
        val conn = connection ?: return 0
        return conn.failureCount().toInt()
    }

    /**
     * Reset the connection state machine.
     */
    suspend fun resetConnection() = withContext(Dispatchers.IO) {
        mutex.withLock {
            connection?.reset()
            updateConnectionState()
        }
    }

    private fun updateConnectionState() {
        val conn = connection ?: return
        val stateString = conn.state()

        _connectionState.value = when (stateString) {
            "disconnected" -> MeshConnectionState.DISCONNECTED
            "connecting" -> MeshConnectionState.CONNECTING
            "connected" -> MeshConnectionState.CONNECTED
            "circuit_open" -> MeshConnectionState.CIRCUIT_OPEN
            "half_open" -> MeshConnectionState.HALF_OPEN
            else -> MeshConnectionState.DISCONNECTED
        }
    }

    // ==================== CRDT: Vector Clocks ====================

    /**
     * Create a new vector clock for a node.
     *
     * @param nodeId The node identifier
     * @return JSON representation of the vector clock
     */
    fun createVectorClock(nodeId: String): String {
        return vectorClockNew(nodeId)
    }

    /**
     * Increment a vector clock for a node.
     *
     * @param clockJson JSON representation of the vector clock
     * @param nodeId The node to increment
     * @return Updated vector clock JSON
     */
    suspend fun incrementVectorClock(clockJson: String, nodeId: String): Result<String> =
        withContext(Dispatchers.IO) {
            try {
                val updated = vectorClockIncrement(clockJson, nodeId)
                Result.success(updated)
            } catch (e: MeshSdkException) {
                Log.e(TAG, "Failed to increment vector clock", e)
                Result.error(e)
            }
        }

    /**
     * Merge two vector clocks.
     *
     * @param clock1Json First vector clock JSON
     * @param clock2Json Second vector clock JSON
     * @return Merged vector clock JSON
     */
    suspend fun mergeVectorClocks(clock1Json: String, clock2Json: String): Result<String> =
        withContext(Dispatchers.IO) {
            try {
                val merged = vectorClockMerge(clock1Json, clock2Json)
                Result.success(merged)
            } catch (e: MeshSdkException) {
                Log.e(TAG, "Failed to merge vector clocks", e)
                Result.error(e)
            }
        }

    /**
     * Compare two vector clocks.
     *
     * @param clock1Json First vector clock JSON
     * @param clock2Json Second vector clock JSON
     * @return Ordering relationship between the clocks
     */
    suspend fun compareVectorClocks(
        clock1Json: String,
        clock2Json: String
    ): Result<VectorClockOrdering> = withContext(Dispatchers.IO) {
        try {
            val result = vectorClockCompare(clock1Json, clock2Json)
            val ordering = when (result) {
                "before" -> VectorClockOrdering.BEFORE
                "after" -> VectorClockOrdering.AFTER
                "concurrent" -> VectorClockOrdering.CONCURRENT
                "equal" -> VectorClockOrdering.EQUAL
                else -> VectorClockOrdering.CONCURRENT
            }
            Result.success(ordering)
        } catch (e: MeshSdkException) {
            Log.e(TAG, "Failed to compare vector clocks", e)
            Result.error(e)
        }
    }

    // ==================== CRDT: G-Counter ====================

    /**
     * Create a new G-Counter (grow-only counter).
     *
     * @return JSON representation of the counter
     */
    fun createGCounter(): String {
        return gCounterNew()
    }

    /**
     * Increment a G-Counter for a node.
     *
     * @param counterJson JSON representation of the counter
     * @param nodeId The node incrementing the counter
     * @return Updated counter JSON
     */
    suspend fun incrementGCounter(counterJson: String, nodeId: String): Result<String> =
        withContext(Dispatchers.IO) {
            try {
                val updated = gCounterIncrement(counterJson, nodeId)
                Result.success(updated)
            } catch (e: MeshSdkException) {
                Log.e(TAG, "Failed to increment G-counter", e)
                Result.error(e)
            }
        }

    /**
     * Merge two G-Counters.
     *
     * @param counter1Json First counter JSON
     * @param counter2Json Second counter JSON
     * @return Merged counter JSON
     */
    suspend fun mergeGCounters(counter1Json: String, counter2Json: String): Result<String> =
        withContext(Dispatchers.IO) {
            try {
                val merged = gCounterMerge(counter1Json, counter2Json)
                Result.success(merged)
            } catch (e: MeshSdkException) {
                Log.e(TAG, "Failed to merge G-counters", e)
                Result.error(e)
            }
        }

    /**
     * Get the value of a G-Counter.
     *
     * @param counterJson JSON representation of the counter
     * @return The total count across all nodes
     */
    suspend fun getGCounterValue(counterJson: String): Result<Long> =
        withContext(Dispatchers.IO) {
            try {
                val value = gCounterValue(counterJson)
                Result.success(value.toLong())
            } catch (e: MeshSdkException) {
                Log.e(TAG, "Failed to get G-counter value", e)
                Result.error(e)
            }
        }

    // ==================== Lifecycle ====================

    /**
     * Clean up resources.
     */
    fun destroy() {
        try {
            identity?.destroy()
            identity = null
            connection?.destroy()
            connection = null
            _isInitialized.value = false
            _connectionState.value = MeshConnectionState.DISCONNECTED
            Log.i(TAG, "Mesh service destroyed")
        } catch (e: Exception) {
            Log.e(TAG, "Error during mesh service destruction", e)
        }
    }

    /**
     * Export identity for backup (use with caution!).
     *
     * The returned base64 string contains the secret key.
     * Store securely if used for backup.
     */
    fun exportIdentity(): String? {
        return identity?.toBase64()
    }

    /**
     * Import identity from backup.
     *
     * @param base64 Base64-encoded identity (from exportIdentity)
     */
    suspend fun importIdentity(base64: String): Result<String> = withContext(Dispatchers.IO) {
        mutex.withLock {
            try {
                // Destroy existing identity
                identity?.destroy()

                // Import new identity
                identity = MeshIdentity.fromBase64(base64)
                _peerId = identity?.peerId()

                // Persist
                encryptedPrefs.edit()
                    .putString(KEY_IDENTITY_BASE64, base64)
                    .putString(KEY_PEER_ID, _peerId)
                    .apply()

                Log.i(TAG, "Imported mesh identity with peer ID: $_peerId")
                Result.success(_peerId!!)
            } catch (e: MeshSdkException) {
                Log.e(TAG, "Failed to import identity", e)
                Result.error(e)
            }
        }
    }
}

/*
 * Mirror
 * h(x) >= 0. Always.
 *
 * The mesh service provides the cryptographic foundation for
 * peer-to-peer communication in the Kagami household mesh.
 *
 * Ed25519 provides identity and authenticity.
 * XChaCha20-Poly1305 provides confidentiality.
 * Vector clocks provide causality ordering.
 * The circuit breaker provides resilience.
 */
