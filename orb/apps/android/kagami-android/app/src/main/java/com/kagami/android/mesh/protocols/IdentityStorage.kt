package com.kagami.android.mesh.protocols

import android.content.Context
import android.content.SharedPreferences
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import java.security.KeyStore

/**
 * Identity Storage — Platform-agnostic credential storage interface
 *
 * Defines the interface for secure credential storage. Android implements
 * using EncryptedSharedPreferences backed by Android Keystore.
 *
 * This interface mirrors the Rust SDK's IdentityStorage trait.
 *
 * 鏡 h(x) >= 0. Always.
 */

// ═══════════════════════════════════════════════════════════════════════════
// Storage Keys
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Consistent storage key names across platforms.
 */
object IdentityStorageKeys {
    /** Primary Ed25519 identity. */
    const val MESH_IDENTITY = "kagami.mesh.identity"
    /** X25519 keypair for encryption. */
    const val X25519_KEYPAIR = "kagami.mesh.x25519"
    /** Hub shared key for local communication. */
    const val HUB_SHARED_KEY = "kagami.mesh.hub_key"  // pragma: allowlist secret
    /** Cloud API authentication token. */
    const val CLOUD_AUTH_TOKEN = "kagami.cloud.auth_token"
    /** Device registration info. */
    const val DEVICE_REGISTRATION = "kagami.device.registration"
}

// ═══════════════════════════════════════════════════════════════════════════
// Data Classes
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Complete identity data for mesh network participation.
 */
@Serializable
data class StoredIdentity(
    /** Ed25519 identity as base64-encoded secret key. */
    val ed25519Identity: String,
    /** X25519 secret key as hex for key exchange. */
    val x25519SecretKey: String? = null,
    /** X25519 public key as hex. */
    val x25519PublicKey: String? = null,
    /** Peer ID (derived from Ed25519 public key). */
    val peerId: String,
    /** Human-readable device name. */
    val deviceName: String? = null,
    /** Creation timestamp (Unix epoch seconds). */
    val createdAt: Long = System.currentTimeMillis() / 1000,
    /** Last used timestamp. */
    val lastUsedAt: Long? = null
)

/**
 * Result of an identity load operation.
 */
sealed class IdentityLoadResult {
    /** Identity loaded successfully. */
    data class Loaded(val identity: StoredIdentity) : IdentityLoadResult()
    /** No identity exists yet. */
    object NotFound : IdentityLoadResult()
    /** Identity exists but is inaccessible. */
    data class Inaccessible(val reason: String) : IdentityLoadResult()
    /** Identity data is corrupted. */
    data class Corrupted(val reason: String) : IdentityLoadResult()
}

/**
 * Errors that can occur during identity storage operations.
 */
sealed class IdentityStorageError : Exception() {
    data class KeyNotFound(val key: String) : IdentityStorageError()
    data class StorageUnavailable(val reason: String) : IdentityStorageError()
    data class AccessDenied(val reason: String) : IdentityStorageError()
    data class SerializationFailed(val reason: String) : IdentityStorageError()
    data class CorruptionDetected(val reason: String) : IdentityStorageError()
    data class PlatformError(val code: Int, override val message: String) : IdentityStorageError()
}

/**
 * Configuration for identity storage.
 */
data class IdentityStorageConfig(
    /** Preference file name. */
    val preferenceName: String = "kagami_secure_prefs",
    /** Whether to use encrypted storage. */
    val useEncryption: Boolean = true,
    /** Master key alias for encryption. */
    val masterKeyAlias: String = "kagami_master_key"
)

// ═══════════════════════════════════════════════════════════════════════════
// Identity Storage Interface
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Interface for identity storage implementations.
 *
 * Platforms implement this interface to provide secure credential storage.
 * The default Android implementation uses EncryptedSharedPreferences.
 */
interface IdentityStorage {
    /** The storage configuration. */
    val config: IdentityStorageConfig

    /** Store an identity securely. */
    @Throws(IdentityStorageError::class)
    fun storeIdentity(identity: StoredIdentity)

    /** Load the stored identity. */
    fun loadIdentity(): IdentityLoadResult

    /** Delete the stored identity. */
    @Throws(IdentityStorageError::class)
    fun deleteIdentity()

    /** Check if an identity exists. */
    fun identityExists(): Boolean

    /** Store a raw string value. */
    @Throws(IdentityStorageError::class)
    fun storeString(key: String, value: String)

    /** Load a raw string value. */
    @Throws(IdentityStorageError::class)
    fun loadString(key: String): String?

    /** Delete a specific key. */
    @Throws(IdentityStorageError::class)
    fun deleteKey(key: String)

    /** Store binary data (as Base64). */
    @Throws(IdentityStorageError::class)
    fun storeData(key: String, data: ByteArray)

    /** Load binary data. */
    @Throws(IdentityStorageError::class)
    fun loadData(key: String): ByteArray?

    /** Clear all stored data. */
    @Throws(IdentityStorageError::class)
    fun clearAll()
}

// ═══════════════════════════════════════════════════════════════════════════
// Encrypted SharedPreferences Implementation
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Android EncryptedSharedPreferences-based identity storage implementation.
 *
 * Uses AndroidX Security library with Android Keystore backing.
 */
class EncryptedIdentityStorage(
    private val context: Context,
    override val config: IdentityStorageConfig = IdentityStorageConfig()
) : IdentityStorage {

    private val json = Json { ignoreUnknownKeys = true }

    private val preferences: SharedPreferences by lazy {
        if (config.useEncryption) {
            createEncryptedPreferences()
        } else {
            context.getSharedPreferences(config.preferenceName, Context.MODE_PRIVATE)
        }
    }

    private fun createEncryptedPreferences(): SharedPreferences {
        val masterKey = MasterKey.Builder(context, config.masterKeyAlias)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()

        return EncryptedSharedPreferences.create(
            context,
            config.preferenceName,
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
        )
    }

    override fun storeIdentity(identity: StoredIdentity) {
        try {
            val jsonString = json.encodeToString(StoredIdentity.serializer(), identity)
            storeString(IdentityStorageKeys.MESH_IDENTITY, jsonString)
        } catch (e: Exception) {
            throw IdentityStorageError.SerializationFailed(e.message ?: "Unknown error")
        }
    }

    override fun loadIdentity(): IdentityLoadResult {
        return try {
            val jsonString = loadString(IdentityStorageKeys.MESH_IDENTITY)
                ?: return IdentityLoadResult.NotFound

            val identity = json.decodeFromString(StoredIdentity.serializer(), jsonString)
            IdentityLoadResult.Loaded(identity)
        } catch (e: IdentityStorageError.KeyNotFound) {
            IdentityLoadResult.NotFound
        } catch (e: IdentityStorageError.AccessDenied) {
            IdentityLoadResult.Inaccessible(e.reason)
        } catch (e: Exception) {
            IdentityLoadResult.Corrupted(e.message ?: "Unknown error")
        }
    }

    override fun deleteIdentity() {
        deleteKey(IdentityStorageKeys.MESH_IDENTITY)
    }

    override fun identityExists(): Boolean {
        return preferences.contains(IdentityStorageKeys.MESH_IDENTITY)
    }

    override fun storeString(key: String, value: String) {
        try {
            preferences.edit().putString(key, value).apply()
        } catch (e: Exception) {
            throw IdentityStorageError.PlatformError(-1, e.message ?: "Unknown error")
        }
    }

    override fun loadString(key: String): String? {
        return try {
            preferences.getString(key, null)
        } catch (e: Exception) {
            throw IdentityStorageError.PlatformError(-1, e.message ?: "Unknown error")
        }
    }

    override fun deleteKey(key: String) {
        try {
            preferences.edit().remove(key).apply()
        } catch (e: Exception) {
            throw IdentityStorageError.PlatformError(-1, e.message ?: "Unknown error")
        }
    }

    override fun storeData(key: String, data: ByteArray) {
        val base64 = android.util.Base64.encodeToString(data, android.util.Base64.NO_WRAP)
        storeString(key, base64)
    }

    override fun loadData(key: String): ByteArray? {
        val base64 = loadString(key) ?: return null
        return try {
            android.util.Base64.decode(base64, android.util.Base64.NO_WRAP)
        } catch (e: Exception) {
            throw IdentityStorageError.CorruptionDetected("Invalid Base64 data")
        }
    }

    override fun clearAll() {
        try {
            preferences.edit().clear().apply()
        } catch (e: Exception) {
            throw IdentityStorageError.PlatformError(-1, e.message ?: "Unknown error")
        }
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// In-Memory Storage (for testing)
// ═══════════════════════════════════════════════════════════════════════════

/**
 * In-memory storage for testing purposes.
 */
class InMemoryIdentityStorage(
    override val config: IdentityStorageConfig = IdentityStorageConfig()
) : IdentityStorage {

    private val storage = mutableMapOf<String, ByteArray>()
    private val json = Json { ignoreUnknownKeys = true }

    override fun storeIdentity(identity: StoredIdentity) {
        val jsonString = json.encodeToString(StoredIdentity.serializer(), identity)
        storeData(IdentityStorageKeys.MESH_IDENTITY, jsonString.toByteArray(Charsets.UTF_8))
    }

    override fun loadIdentity(): IdentityLoadResult {
        val data = storage[IdentityStorageKeys.MESH_IDENTITY]
            ?: return IdentityLoadResult.NotFound

        return try {
            val jsonString = String(data, Charsets.UTF_8)
            val identity = json.decodeFromString(StoredIdentity.serializer(), jsonString)
            IdentityLoadResult.Loaded(identity)
        } catch (e: Exception) {
            IdentityLoadResult.Corrupted(e.message ?: "Unknown error")
        }
    }

    override fun deleteIdentity() {
        deleteKey(IdentityStorageKeys.MESH_IDENTITY)
    }

    override fun identityExists(): Boolean {
        return storage.containsKey(IdentityStorageKeys.MESH_IDENTITY)
    }

    override fun storeString(key: String, value: String) {
        storage[key] = value.toByteArray(Charsets.UTF_8)
    }

    override fun loadString(key: String): String? {
        return storage[key]?.let { String(it, Charsets.UTF_8) }
    }

    override fun deleteKey(key: String) {
        storage.remove(key)
    }

    override fun storeData(key: String, data: ByteArray) {
        storage[key] = data.copyOf()
    }

    override fun loadData(key: String): ByteArray? {
        return storage[key]?.copyOf()
    }

    override fun clearAll() {
        storage.clear()
    }
}

/*
 * 鏡 Kagami Mesh Identity Storage
 * h(x) >= 0. Always.
 */
