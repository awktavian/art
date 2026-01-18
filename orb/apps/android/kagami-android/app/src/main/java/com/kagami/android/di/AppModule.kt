/**
 * Kagami Android - Hilt Application Module
 *
 * Colony: Nexus (e4) - Integration
 *
 * Provides application-wide dependencies via Hilt DI.
 */

package com.kagami.android.di

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import com.google.android.gms.wearable.Wearable
import com.google.android.gms.wearable.DataClient
import com.google.android.gms.wearable.MessageClient
import com.google.android.play.core.review.ReviewManager
import com.google.android.play.core.review.ReviewManagerFactory
import com.google.firebase.analytics.FirebaseAnalytics
import com.google.firebase.crashlytics.FirebaseCrashlytics
import com.kagami.android.data.local.CommandQueueDao
import com.kagami.android.data.local.KagamiDatabase
import com.kagami.android.data.local.RoomDao
import com.kagami.android.data.local.SceneDao
import com.kagami.android.network.ApiConfig
import com.kagami.android.network.HttpClientFactory
import com.kagami.android.services.*
import com.kagami.android.ui.components.ContextualHintEngine
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import okhttp3.CertificatePinner
import okhttp3.OkHttpClient
import javax.inject.Named
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object AppModule {

    // ==================== Security ====================

    @Provides
    @Singleton
    fun provideMasterKey(@ApplicationContext context: Context): MasterKey {
        return MasterKey.Builder(context)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()
    }

    @Provides
    @Singleton
    @Named("encrypted")
    fun provideEncryptedSharedPreferences(
        @ApplicationContext context: Context,
        masterKey: MasterKey
    ): SharedPreferences {
        return EncryptedSharedPreferences.create(
            context,
            "kagami_secure_prefs",
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
        )
    }

    @Provides
    @Singleton
    @Named("regular")
    fun provideSharedPreferences(@ApplicationContext context: Context): SharedPreferences {
        return context.getSharedPreferences("kagami_prefs", Context.MODE_PRIVATE)
    }

    // ==================== Network ====================

    @Provides
    @Singleton
    fun provideCertificatePinner(): CertificatePinner {
        // Certificate pinning for Kagami API server
        // Pins are SHA-256 hashes of the public key (SPKI)
        //
        // Generate certificate hash with:
        //    openssl s_client -connect kagami.local:443 2>/dev/null | \
        //      openssl x509 -pubkey -noout | \
        //      openssl pkey -pubin -outform der | \
        //      openssl dgst -sha256 -binary | \
        //      openssl enc -base64
        //
        // WARNING: Incorrect pins will cause complete connection failure.
        // Test thoroughly in staging before deploying to production.
        //
        return CertificatePinner.Builder()
            // Primary pin for kagami.local server certificate
            // SHA-256 hash of the server's public key (SPKI)
            .add("kagami.local", "sha256/Vjs8r4z+80wjNcr1YKepWQboSIRi63WsWXhIMN+eWys=")
            .add("*.kagami.local", "sha256/Vjs8r4z+80wjNcr1YKepWQboSIRi63WsWXhIMN+eWys=")
            // Backup pin for certificate rotation (pre-generated backup key)
            // This allows seamless certificate rotation without app updates
            .add("kagami.local", "sha256/jQJTbIh0grw0/1TkHSumWb+Fs0Ggogr621gT3PvPKG0=")
            .add("*.kagami.local", "sha256/jQJTbIh0grw0/1TkHSumWb+Fs0Ggogr621gT3PvPKG0=")
            // Let's Encrypt ISRG Root X1 (if using LE certificates for external access)
            .add("kagami.local", "sha256/C5+lpZ7tcVwmwQIMcRtPbsQtWLABXhQzejna0wHFr8M=")
            .add("*.kagami.local", "sha256/C5+lpZ7tcVwmwQIMcRtPbsQtWLABXhQzejna0wHFr8M=")
            .build()
    }

    @Provides
    @Singleton
    fun provideHttpClientFactory(certificatePinner: CertificatePinner): HttpClientFactory {
        return HttpClientFactory(certificatePinner)
    }

    @Provides
    @Singleton
    @Named("api")
    fun provideApiOkHttpClient(factory: HttpClientFactory): OkHttpClient {
        return factory.createApiClient()
    }

    @Provides
    @Singleton
    @Named("websocket")
    fun provideWebSocketOkHttpClient(factory: HttpClientFactory): OkHttpClient {
        return factory.createWebSocketClient()
    }

    @Provides
    @Singleton
    @Named("background")
    fun provideBackgroundOkHttpClient(factory: HttpClientFactory): OkHttpClient {
        return factory.createBackgroundClient()
    }

    // Legacy: Provide default OkHttpClient for backward compatibility
    @Provides
    @Singleton
    fun provideOkHttpClient(@Named("api") apiClient: OkHttpClient): OkHttpClient {
        return apiClient
    }

    // ==================== API Configuration ====================

    @Provides
    @Singleton
    fun provideApiConfig(
        @Named("encrypted") encryptedPrefs: SharedPreferences
    ): ApiConfig {
        return ApiConfig(encryptedPrefs)
    }

    // ==================== Services ====================

    @Provides
    @Singleton
    fun provideAuthManager(
        @Named("encrypted") encryptedPrefs: SharedPreferences
    ): AuthManager {
        return AuthManager(encryptedPrefs)
    }

    @Provides
    @Singleton
    fun provideWebSocketService(
        @Named("websocket") wsClient: OkHttpClient,
        apiConfig: ApiConfig
    ): WebSocketService {
        return WebSocketService(wsClient, apiConfig)
    }

    @Provides
    @Singleton
    fun provideSceneService(
        @Named("api") client: OkHttpClient,
        apiConfig: ApiConfig,
        authManager: AuthManager
    ): SceneService {
        return SceneService(client, apiConfig, authManager)
    }

    @Provides
    @Singleton
    fun provideDeviceControlService(
        @Named("api") client: OkHttpClient,
        apiConfig: ApiConfig,
        authManager: AuthManager,
        meshRouter: MeshCommandRouter
    ): DeviceControlService {
        return DeviceControlService(client, apiConfig, authManager, meshRouter)
    }

    @Provides
    @Singleton
    fun provideSensoryUploadService(
        @Named("api") client: OkHttpClient,
        apiConfig: ApiConfig,
        authManager: AuthManager
    ): SensoryUploadService {
        return SensoryUploadService(client, apiConfig, authManager)
    }

    @Provides
    @Singleton
    fun provideMeshService(
        @Named("encrypted") encryptedPrefs: SharedPreferences
    ): MeshService {
        return MeshService(encryptedPrefs)
    }

    @Provides
    @Singleton
    fun provideMeshTransport(
        @Named("websocket") wsClient: OkHttpClient,
        meshService: MeshService
    ): MeshTransport {
        return MeshTransport(wsClient, meshService)
    }

    @Provides
    @Singleton
    fun provideHubDiscoveryService(
        @ApplicationContext context: Context,
        @Named("api") httpClient: OkHttpClient
    ): HubDiscoveryService {
        return HubDiscoveryService(context, httpClient)
    }

    @Provides
    @Singleton
    fun provideMeshCommandRouter(
        meshService: MeshService,
        meshTransport: MeshTransport,
        hubDiscoveryService: HubDiscoveryService
    ): MeshCommandRouter {
        return MeshCommandRouter(meshService, meshTransport, hubDiscoveryService)
    }

    @Provides
    @Singleton
    fun provideKagamiApiService(
        @Named("api") client: OkHttpClient,
        apiConfig: ApiConfig,
        authManager: AuthManager,
        webSocketService: WebSocketService,
        sceneService: SceneService,
        deviceControlService: DeviceControlService,
        sensoryUploadService: SensoryUploadService
    ): KagamiApiService {
        return KagamiApiService(
            client,
            apiConfig,
            authManager,
            webSocketService,
            sceneService,
            deviceControlService,
            sensoryUploadService
        )
    }

    // ==================== Firebase ====================

    @Provides
    @Singleton
    fun provideFirebaseCrashlytics(): FirebaseCrashlytics {
        return FirebaseCrashlytics.getInstance()
    }

    @Provides
    @Singleton
    fun provideFirebaseAnalytics(@ApplicationContext context: Context): FirebaseAnalytics {
        return FirebaseAnalytics.getInstance(context)
    }

    // ==================== Database ====================

    @Provides
    @Singleton
    fun provideDatabase(@ApplicationContext context: Context): KagamiDatabase {
        return KagamiDatabase.getInstance(context)
    }

    @Provides
    fun provideRoomDao(database: KagamiDatabase): RoomDao {
        return database.roomDao()
    }

    @Provides
    fun provideSceneDao(database: KagamiDatabase): SceneDao {
        return database.sceneDao()
    }

    @Provides
    fun provideCommandQueueDao(database: KagamiDatabase): CommandQueueDao {
        return database.commandQueueDao()
    }

    // ==================== Wearable ====================

    @Provides
    @Singleton
    fun provideDataClient(@ApplicationContext context: Context): DataClient {
        return Wearable.getDataClient(context)
    }

    @Provides
    @Singleton
    fun provideMessageClient(@ApplicationContext context: Context): MessageClient {
        return Wearable.getMessageClient(context)
    }

    // ==================== In-App Review ====================

    @Provides
    @Singleton
    fun provideReviewManager(@ApplicationContext context: Context): ReviewManager {
        return ReviewManagerFactory.create(context)
    }

    // ==================== UI Components ====================

    @Provides
    @Singleton
    fun provideContextualHintEngine(@ApplicationContext context: Context): ContextualHintEngine {
        return ContextualHintEngine().apply {
            initialize(context)
        }
    }
}
