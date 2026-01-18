/**
 * HTTP Client Factory - Single OkHttpClient Provider
 *
 * Colony: Nexus (e4) - Integration
 *
 * Provides a centralized, singleton OkHttpClient with:
 * - Connection pooling
 * - Certificate pinning (production only)
 * - Logging interceptors
 * - Network security enforcement
 */

package com.kagami.android.network

import com.kagami.android.BuildConfig
import okhttp3.CertificatePinner
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import java.util.concurrent.TimeUnit
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Factory for creating and managing OkHttpClient instances.
 * Ensures a single shared client is used across the app.
 */
@Singleton
class HttpClientFactory @Inject constructor(
    private val certificatePinner: CertificatePinner
) {

    companion object {
        // Timeouts
        const val CONNECT_TIMEOUT_SECONDS = 10L
        const val READ_TIMEOUT_SECONDS = 10L
        const val WRITE_TIMEOUT_SECONDS = 10L
        const val WEBSOCKET_PING_INTERVAL_SECONDS = 30L
    }

    /**
     * Create the primary OkHttpClient for API calls.
     */
    fun createApiClient(): OkHttpClient {
        return OkHttpClient.Builder()
            .connectTimeout(CONNECT_TIMEOUT_SECONDS, TimeUnit.SECONDS)
            .readTimeout(READ_TIMEOUT_SECONDS, TimeUnit.SECONDS)
            .writeTimeout(WRITE_TIMEOUT_SECONDS, TimeUnit.SECONDS)
            .applyCertificatePinning()
            .addInterceptor(createLoggingInterceptor())
            .addNetworkInterceptor(createSecurityInterceptor())
            .build()
    }

    /**
     * Create an OkHttpClient optimized for WebSocket connections.
     * Includes ping interval for keep-alive.
     */
    fun createWebSocketClient(): OkHttpClient {
        return OkHttpClient.Builder()
            .connectTimeout(CONNECT_TIMEOUT_SECONDS, TimeUnit.SECONDS)
            .readTimeout(0, TimeUnit.SECONDS) // No read timeout for WebSocket
            .writeTimeout(WRITE_TIMEOUT_SECONDS, TimeUnit.SECONDS)
            .pingInterval(WEBSOCKET_PING_INTERVAL_SECONDS, TimeUnit.SECONDS)
            .applyCertificatePinning()
            .build()
    }

    /**
     * Create a minimal OkHttpClient for background services.
     * No logging to reduce overhead.
     */
    fun createBackgroundClient(): OkHttpClient {
        return OkHttpClient.Builder()
            .connectTimeout(CONNECT_TIMEOUT_SECONDS, TimeUnit.SECONDS)
            .readTimeout(READ_TIMEOUT_SECONDS, TimeUnit.SECONDS)
            .writeTimeout(WRITE_TIMEOUT_SECONDS, TimeUnit.SECONDS)
            .applyCertificatePinning()
            .build()
    }

    private fun OkHttpClient.Builder.applyCertificatePinning(): OkHttpClient.Builder {
        return if (!BuildConfig.DEBUG) {
            certificatePinner(certificatePinner)
        } else {
            this
        }
    }

    private fun createLoggingInterceptor(): HttpLoggingInterceptor {
        return HttpLoggingInterceptor().apply {
            level = if (BuildConfig.DEBUG) {
                HttpLoggingInterceptor.Level.BODY
            } else {
                HttpLoggingInterceptor.Level.HEADERS
            }
        }
    }

    private fun createSecurityInterceptor(): okhttp3.Interceptor {
        return okhttp3.Interceptor { chain ->
            val request = chain.request()
            val response = chain.proceed(request)
            // Enforce HTTPS in production
            if (!BuildConfig.DEBUG && request.url.scheme != "https") {
                throw SecurityException("HTTPS required for API calls in production")
            }
            response
        }
    }
}

/*
 * Mirror
 * h(x) >= 0. Always.
 */
