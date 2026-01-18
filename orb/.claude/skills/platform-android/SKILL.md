# Android Platform Skill

**100/100 Quality by Default** - Patterns for production-ready Android apps.

## When to Use

- Creating or modifying Android apps in `apps/android/`
- Ensuring Android-specific quality standards
- Byzantine audit remediation for Android

## Required Files (P0)

Every Android app MUST have these files implemented (not empty):

```
app/src/main/java/com/kagami/android/
├── KagamiApp.kt                    # Application class with Hilt
├── MainActivity.kt                  # Entry point
├── ui/
│   ├── screens/
│   │   ├── HomeScreen.kt           # Main dashboard (CRITICAL)
│   │   ├── RoomsScreen.kt          # Room controls
│   │   ├── ScenesScreen.kt         # Scene activation
│   │   ├── SettingsScreen.kt       # Settings (CRITICAL)
│   │   └── LoginScreen.kt          # Authentication
│   ├── theme/
│   │   ├── Theme.kt                # Material 3 theming
│   │   ├── Color.kt                # Colony-aware colors
│   │   └── DesignSystem.kt         # Design tokens
│   └── Navigation.kt               # NavHost setup
├── data/
│   └── Result.kt                   # Sealed Result class (CRITICAL)
├── services/
│   ├── KagamiApiService.kt         # API client facade
│   ├── AuthManager.kt              # Token management
│   └── WebSocketService.kt         # Real-time updates
├── di/
│   └── AppModule.kt                # Hilt modules
└── network/
    └── HttpClientFactory.kt        # OkHttp with pinning
```

## Critical Patterns

### 1. Result Sealed Class (MANDATORY)

```kotlin
sealed class Result<out T> {
    data class Success<out T>(val data: T) : Result<T>()
    data class Error(
        val message: String? = null,
        val exception: Throwable? = null
    ) : Result<Nothing>()

    val isSuccess: Boolean get() = this is Success
    val isError: Boolean get() = this is Error

    fun getOrNull(): T? = when (this) {
        is Success -> data
        is Error -> null
    }

    inline fun <R> map(transform: (T) -> R): Result<R> = when (this) {
        is Success -> Success(transform(data))
        is Error -> Error(message, exception)
    }

    companion object {
        fun <T> success(data: T): Result<T> = Success(data)
        fun <T> error(message: String, exception: Throwable? = null): Result<T> =
            Error(message, exception)
        inline fun <T> runCatching(block: () -> T): Result<T> = try {
            Success(block())
        } catch (e: Throwable) {
            Error(e.message, e)
        }
    }
}
```

### 2. HomeScreen Pattern (MANDATORY)

```kotlin
@Composable
fun HomeScreen(
    viewModel: HomeViewModel = hiltViewModel(),
    onNavigateToRooms: () -> Unit,
    onNavigateToScenes: () -> Unit,
    onNavigateToSettings: () -> Unit
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    Scaffold(
        topBar = {
            KagamiTopAppBar(
                title = "Kagami",
                onSettingsClick = onNavigateToSettings
            )
        },
        bottomBar = {
            KagamiBottomNavigation(
                currentRoute = "home",
                onNavigate = { route ->
                    when (route) {
                        "rooms" -> onNavigateToRooms()
                        "scenes" -> onNavigateToScenes()
                    }
                }
            )
        }
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            // Safety Score Card
            item {
                SafetyScoreCard(
                    score = uiState.safetyScore,
                    modifier = Modifier.padding(KagamiSpacing.medium)
                )
            }

            // Quick Actions
            item {
                QuickActionsRow(
                    onMovieMode = viewModel::activateMovieMode,
                    onGoodnight = viewModel::activateGoodnight,
                    onWelcomeHome = viewModel::activateWelcomeHome
                )
            }

            // Room Status Cards
            items(uiState.rooms) { room ->
                RoomStatusCard(
                    room = room,
                    onClick = { onNavigateToRooms() }
                )
            }
        }
    }
}
```

### 3. Design System Tokens (MANDATORY)

```kotlin
object KagamiSpacing {
    val xxSmall = 2.dp   // 2
    val xSmall = 4.dp    // Fibonacci
    val small = 8.dp     // 8
    val medium = 16.dp   // 13 rounded
    val large = 24.dp    // 21 rounded
    val xLarge = 40.dp   // 34 rounded
    val xxLarge = 64.dp  // 55 rounded
}

object KagamiAnimation {
    val instant = 89      // Fibonacci ms
    val fast = 144
    val normal = 233
    val slow = 377
    val slower = 610
}

object KagamiRadius {
    val small = 4.dp
    val medium = 8.dp
    val large = 16.dp
    val pill = 999.dp
}

// Colony Colors (WCAG AA compliant)
object ColonyColors {
    val sparkPrimary = Color(0xFFFF6B35)    // Warm orange
    val forgePrimary = Color(0xFF2196F3)    // Blue
    val flowPrimary = Color(0xFF4CAF50)     // Green
    val guardPrimary = Color(0xFFF44336)    // Red
}
```

### 4. Accessibility (MANDATORY)

```kotlin
// Minimum touch target: 48dp
@Composable
fun MinTouchTargetSize(content: @Composable () -> Unit) {
    Box(
        modifier = Modifier.sizeIn(minWidth = 48.dp, minHeight = 48.dp),
        contentAlignment = Alignment.Center
    ) {
        content()
    }
}

// All interactive elements need semantics
@Composable
fun AccessibleButton(
    onClick: () -> Unit,
    contentDescription: String,
    enabled: Boolean = true,
    content: @Composable () -> Unit
) {
    Button(
        onClick = onClick,
        enabled = enabled,
        modifier = Modifier.semantics {
            this.contentDescription = contentDescription
            this.role = Role.Button
        }
    ) {
        content()
    }
}
```

### 5. Hilt Dependency Injection (MANDATORY)

```kotlin
@HiltAndroidApp
class KagamiApp : Application()

@Module
@InstallIn(SingletonComponent::class)
object AppModule {
    @Provides
    @Singleton
    fun provideOkHttpClient(): OkHttpClient {
        return OkHttpClient.Builder()
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            // Certificate pinning for production
            .certificatePinner(
                CertificatePinner.Builder()
                    .add("kagami.local", "sha256/XXXXX...")
                    .build()
            )
            .build()
    }

    @Provides
    @Singleton
    fun provideKagamiApiService(
        okHttpClient: OkHttpClient
    ): KagamiApiService {
        return KagamiApiService(okHttpClient)
    }
}
```

## Testing Requirements

### Unit Tests (Required)

```kotlin
// Every service needs tests
class KagamiApiServiceTest {
    private lateinit var mockWebServer: MockWebServer
    private lateinit var apiService: KagamiApiService

    @Before
    fun setup() {
        mockWebServer = MockWebServer()
        // Setup with mock server
    }

    @Test
    fun `health check returns success when server available`() = runTest {
        mockWebServer.enqueue(MockResponse().setBody(healthJson))
        val result = apiService.healthCheck()
        assertTrue(result.isSuccess)
    }

    @Test
    fun `health check returns error on network failure`() = runTest {
        mockWebServer.shutdown()
        val result = apiService.healthCheck()
        assertTrue(result.isError)
    }
}
```

### Integration Tests (Required)

```kotlin
class MainFlowsIntegrationTest {
    @Test
    fun `login flow completes successfully`() = runTest {
        // Test full login flow
    }

    @Test
    fun `scene activation works end to end`() = runTest {
        // Test scene activation
    }

    @Test
    fun `room control updates UI correctly`() = runTest {
        // Test room controls
    }
}
```

### E2E Tests with Maestro (Required)

```yaml
# .maestro/onboarding_flow.yaml
appId: com.kagami.android
---
- launchApp
- assertVisible: "Welcome to Kagami"
- tapOn: "Get Started"
- assertVisible: "Connect to Hub"
```

## Security Requirements

1. **EncryptedSharedPreferences** for token storage
2. **Certificate pinning** in production builds
3. **No hardcoded secrets**
4. **ProGuard/R8** rules for release builds
5. **Network security config** XML

### ProGuard Rules (Required for Release)

```proguard
# proguard-rules.pro
-keep class com.kagami.android.data.** { *; }
-keep class com.kagami.android.services.** { *; }

# Retrofit
-keepattributes Signature
-keepattributes RuntimeVisibleAnnotations

# OkHttp
-dontwarn okhttp3.**
-dontwarn okio.**

# Hilt
-keep class dagger.hilt.** { *; }
```

## Build Verification

```bash
# Verify Android build passes
cd apps/android/kagami-android

# Debug build
./gradlew assembleDebug

# Run tests
./gradlew test

# Run lint
./gradlew lint

# Run Maestro E2E
maestro test .maestro/
```

## Quality Checklist

Before any Android commit:

- [ ] `Result.kt` exists and is not empty
- [ ] `HomeScreen.kt` renders full dashboard
- [ ] `SettingsScreen.kt` has logout/server config
- [ ] All services use Hilt injection
- [ ] Minimum 48dp touch targets
- [ ] All interactive elements have contentDescription
- [ ] ProGuard rules exist for release
- [ ] Unit tests pass
- [ ] `./gradlew lint` passes
- [ ] No hardcoded secrets

## Common Issues & Fixes

### Empty Files
- **Symptom**: Compilation fails with "unresolved reference"
- **Fix**: Create proper implementations, never commit empty files

### Missing DI
- **Symptom**: `UninitializedPropertyAccessException`
- **Fix**: Ensure all ViewModels use `@HiltViewModel`

### Touch Target Too Small
- **Symptom**: Accessibility scanner fails
- **Fix**: Wrap in `MinTouchTargetSize` composable

---

*100/100 or don't ship.*
