/**
 * Auth Manager - Authentication Token Management
 *
 * Colony: Nexus (e4) - Integration
 *
 * Handles secure storage and retrieval of:
 * - Access tokens
 * - Refresh tokens
 * - Server URLs
 */

package com.kagami.android.services

import android.content.SharedPreferences
import javax.inject.Inject
import javax.inject.Named
import javax.inject.Singleton

/**
 * Manages authentication tokens using encrypted storage.
 */
@Singleton
class AuthManager @Inject constructor(
    @Named("encrypted") private val encryptedPrefs: SharedPreferences
) {

    companion object {
        // Preference keys
        private const val KEY_ACCESS_TOKEN = "access_token"
        private const val KEY_REFRESH_TOKEN = "refresh_token"
        private const val KEY_SERVER_URL = "server_url"
        private const val KEY_TOKEN_STORED_AT = "token_stored_at"
    }

    /**
     * Get the stored access token.
     */
    fun getAccessToken(): String? = encryptedPrefs.getString(KEY_ACCESS_TOKEN, null)

    /**
     * Get the stored refresh token.
     */
    fun getRefreshToken(): String? = encryptedPrefs.getString(KEY_REFRESH_TOKEN, null)

    /**
     * Get the stored server URL.
     */
    fun getServerUrl(): String? = encryptedPrefs.getString(KEY_SERVER_URL, null)

    /**
     * Store authentication tokens.
     *
     * @param serverUrl The server URL
     * @param accessToken The access token
     * @param refreshToken Optional refresh token
     */
    fun storeAuthTokens(serverUrl: String, accessToken: String, refreshToken: String?) {
        encryptedPrefs.edit()
            .putString(KEY_SERVER_URL, serverUrl)
            .putString(KEY_ACCESS_TOKEN, accessToken)
            .putString(KEY_REFRESH_TOKEN, refreshToken)
            .putLong(KEY_TOKEN_STORED_AT, System.currentTimeMillis())
            .apply()
    }

    /**
     * Clear all authentication tokens.
     */
    fun clearAuthTokens() {
        encryptedPrefs.edit()
            .remove(KEY_ACCESS_TOKEN)
            .remove(KEY_REFRESH_TOKEN)
            .remove(KEY_TOKEN_STORED_AT)
            .apply()
    }

    /**
     * Check if user is authenticated.
     */
    fun isAuthenticated(): Boolean = !getAccessToken().isNullOrBlank()

    /**
     * Get the timestamp when tokens were stored.
     */
    fun getTokenStoredAt(): Long = encryptedPrefs.getLong(KEY_TOKEN_STORED_AT, 0)
}

/*
 * Mirror
 * h(x) >= 0. Always.
 */
