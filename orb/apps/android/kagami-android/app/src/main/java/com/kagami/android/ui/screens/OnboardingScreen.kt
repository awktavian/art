/**
 * Kagami Onboarding Wizard - Complete First Launch Experience for Android
 *
 * Colony: Beacon (e5) - Planning
 *
 * Streamlined 4-Step Flow:
 * 1. Welcome - Kagami branding and feature highlights
 * 2. Server Setup - Connection with auto-discovery
 * 3. Permissions - Notifications and location (optional)
 * 4. Tour - Quick feature walkthrough and get started
 *
 * Accessibility:
 * - TalkBack content descriptions for all interactive elements
 * - Minimum 48dp touch targets
 * - Reduced motion support
 * - Font scaling support (200%)
 * - High contrast mode support
 *
 * Integration and room configuration moved to post-onboarding settings.
 */

package com.kagami.android.ui.screens

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.view.HapticFeedbackConstants
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.*
import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.VolumeUp
import androidx.compose.material.icons.filled.*
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.semantics.*
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.kagami.android.ui.LocalAccessibilityConfig
import com.kagami.android.ui.MinTouchTargetSize
import com.kagami.android.ui.minTouchTarget
import com.kagami.android.ui.theme.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.TimeUnit

// =============================================================================
// ONBOARDING STATE
// =============================================================================

data class OnboardingState(
    val currentPage: Int = 0,
    // Server connection
    val serverUrl: String = "",
    val isDiscovering: Boolean = false,
    val discoveredServers: List<String> = emptyList(),
    val isTestingConnection: Boolean = false,
    val connectionSuccess: Boolean? = null,
    val connectionError: String? = null,
    // Smart home integrations
    val selectedIntegration: SmartHomeIntegration? = null,
    val integrationCredentials: Map<String, String> = emptyMap(),
    val isConnectingIntegration: Boolean = false,
    val integrationConnected: Boolean = false,
    val integrationError: String? = null,
    // Room configuration
    val availableRooms: List<RoomConfig> = emptyList(),
    val selectedRooms: Set<String> = emptySet(),
    val isLoadingRooms: Boolean = false,
    // Permissions
    val notificationPermissionGranted: Boolean = false,
    val locationPermissionGranted: Boolean = false,
    // Completion
    val isComplete: Boolean = false
)

data class RoomConfig(
    val id: String,
    val name: String,
    val floor: String,
    val hasLights: Boolean = false,
    val hasShades: Boolean = false,
    val hasClimate: Boolean = false
)

enum class SmartHomeIntegration(
    val displayName: String,
    val description: String,
    val icon: ImageVector,
    val color: Color,
    val requiredFields: List<IntegrationField>
) {
    CONTROL4(
        displayName = "Control4",
        description = "Professional home automation",
        icon = Icons.Default.Home,
        color = Color(0xFF1E88E5),
        requiredFields = listOf(
            IntegrationField("host", "Controller IP", "192.168.1.100"),
            IntegrationField("port", "Port", "8750")
        )
    ),
    LUTRON(
        displayName = "Lutron",
        description = "Smart lighting & shades",
        icon = Icons.Default.LightMode,
        color = Color(0xFFFFC107),
        requiredFields = listOf(
            IntegrationField("host", "Bridge IP", "192.168.1.x"),
            IntegrationField("username", "Username", ""),
            IntegrationField("password", "Password", "", isPassword = true)
        )
    ),
    SMARTTHINGS(
        displayName = "SmartThings",
        description = "Samsung smart home platform",
        icon = Icons.Default.Devices,
        color = Color(0xFF00BCD4),
        requiredFields = listOf(
            IntegrationField("token", "Personal Access Token", "")
        )
    ),
    GOOGLE_HOME(
        displayName = "Google Home",
        description = "Google smart home ecosystem",
        icon = Icons.Default.Assistant,
        color = Color(0xFF4285F4),
        requiredFields = listOf(
            IntegrationField("project_id", "Project ID", ""),
            IntegrationField("device_access_token", "Device Access Token", "")
        )
    )
}

data class IntegrationField(
    val key: String,
    val label: String,
    val placeholder: String,
    val isPassword: Boolean = false
)

// =============================================================================
// ONBOARDING VIEW MODEL
// =============================================================================

class OnboardingViewModel : ViewModel() {

    private val _state = MutableStateFlow(OnboardingState())
    val state: StateFlow<OnboardingState> = _state.asStateFlow()

    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(10, TimeUnit.SECONDS)
        .build()

    companion object {
        private val JSON_MEDIA_TYPE = "application/json".toMediaType()
        private val DEFAULT_SERVERS = listOf(
            "http://kagami.local:8001",
            "http://192.168.1.100:8001",
            "http://192.168.1.50:8001",
            "http://10.0.0.100:8001"
        )
        const val PREFS_NAME = "kagami_onboarding"
        const val KEY_SERVER_URL = "server_url"
        const val KEY_CURRENT_PAGE = "current_page"
        const val KEY_INTEGRATION = "selected_integration"
        const val KEY_SELECTED_ROOMS = "selected_rooms"
    }

    fun loadProgress(context: Context) {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val serverUrl = prefs.getString(KEY_SERVER_URL, "") ?: ""
        val currentPage = prefs.getInt(KEY_CURRENT_PAGE, 0)
        val integrationName = prefs.getString(KEY_INTEGRATION, null)
        val selectedRoomsJson = prefs.getString(KEY_SELECTED_ROOMS, "[]") ?: "[]"

        val selectedRooms = try {
            val array = JSONArray(selectedRoomsJson)
            (0 until array.length()).map { array.getString(it) }.toSet()
        } catch (e: Exception) {
            emptySet()
        }

        val integration = integrationName?.let {
            try { SmartHomeIntegration.valueOf(it) } catch (e: Exception) { null }
        }

        _state.value = _state.value.copy(
            serverUrl = serverUrl,
            currentPage = currentPage,
            selectedIntegration = integration,
            selectedRooms = selectedRooms,
            notificationPermissionGranted = checkNotificationPermission(context),
            locationPermissionGranted = checkLocationPermission(context)
        )
    }

    fun saveProgress(context: Context) {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val currentState = _state.value

        prefs.edit()
            .putString(KEY_SERVER_URL, currentState.serverUrl)
            .putInt(KEY_CURRENT_PAGE, currentState.currentPage)
            .putString(KEY_INTEGRATION, currentState.selectedIntegration?.name)
            .putString(KEY_SELECTED_ROOMS, JSONArray(currentState.selectedRooms.toList()).toString())
            .apply()
    }

    fun clearProgress(context: Context) {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        prefs.edit().clear().apply()
    }

    private fun checkNotificationPermission(context: Context): Boolean {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            ContextCompat.checkSelfPermission(
                context,
                Manifest.permission.POST_NOTIFICATIONS
            ) == PackageManager.PERMISSION_GRANTED
        } else {
            true
        }
    }

    private fun checkLocationPermission(context: Context): Boolean {
        return ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.ACCESS_FINE_LOCATION
        ) == PackageManager.PERMISSION_GRANTED
    }

    fun setPage(page: Int) {
        _state.value = _state.value.copy(currentPage = page)
    }

    fun updateServerUrl(url: String) {
        _state.value = _state.value.copy(
            serverUrl = url,
            connectionSuccess = null,
            connectionError = null
        )
    }

    fun discoverServers() {
        viewModelScope.launch {
            _state.value = _state.value.copy(isDiscovering = true, connectionError = null)

            val discovered = mutableListOf<String>()
            withContext(Dispatchers.IO) {
                for (candidate in DEFAULT_SERVERS) {
                    if (testConnection(candidate)) {
                        discovered.add(candidate)
                    }
                }
            }

            _state.value = _state.value.copy(
                isDiscovering = false,
                discoveredServers = discovered,
                connectionError = if (discovered.isEmpty()) "No Kagami servers found" else null
            )

            // Auto-select if only one found
            if (discovered.size == 1) {
                _state.value = _state.value.copy(serverUrl = discovered.first())
            }
        }
    }

    private fun testConnection(url: String): Boolean {
        return try {
            val request = Request.Builder().url("$url/health").build()
            val response = client.newCall(request).execute()
            response.isSuccessful
        } catch (e: Exception) {
            false
        }
    }

    fun testServerConnection() {
        val url = _state.value.serverUrl.trimEnd('/')
        if (url.isBlank()) {
            _state.value = _state.value.copy(connectionError = "Please enter a server URL")
            return
        }

        viewModelScope.launch {
            _state.value = _state.value.copy(
                isTestingConnection = true,
                connectionSuccess = null,
                connectionError = null
            )

            val success = withContext(Dispatchers.IO) { testConnection(url) }

            _state.value = _state.value.copy(
                isTestingConnection = false,
                connectionSuccess = success,
                connectionError = if (!success) "Could not connect to server" else null
            )
        }
    }

    fun selectIntegration(integration: SmartHomeIntegration?) {
        _state.value = _state.value.copy(
            selectedIntegration = integration,
            integrationCredentials = emptyMap(),
            integrationConnected = false,
            integrationError = null
        )
    }

    fun updateIntegrationCredential(key: String, value: String) {
        val current = _state.value.integrationCredentials.toMutableMap()
        current[key] = value
        _state.value = _state.value.copy(integrationCredentials = current)
    }

    fun connectIntegration() {
        val integration = _state.value.selectedIntegration ?: return
        val credentials = _state.value.integrationCredentials
        val serverUrl = _state.value.serverUrl.trimEnd('/')

        // Validate required fields
        val missingFields = integration.requiredFields.filter {
            credentials[it.key].isNullOrBlank()
        }
        if (missingFields.isNotEmpty()) {
            _state.value = _state.value.copy(
                integrationError = "Please fill in: ${missingFields.joinToString { it.label }}"
            )
            return
        }

        viewModelScope.launch {
            _state.value = _state.value.copy(
                isConnectingIntegration = true,
                integrationError = null
            )

            val result = withContext(Dispatchers.IO) {
                try {
                    val body = JSONObject().apply {
                        put("integration_type", integration.name.lowercase())
                        put("credentials", JSONObject(credentials))
                    }

                    val request = Request.Builder()
                        .url("$serverUrl/api/user/smart-home/connect")
                        .post(body.toString().toRequestBody(JSON_MEDIA_TYPE))
                        .build()

                    val response = client.newCall(request).execute()
                    if (response.isSuccessful) {
                        Result.success(Unit)
                    } else {
                        val errorBody = response.body?.string()
                        val errorJson = try { JSONObject(errorBody ?: "{}") } catch (e: Exception) { null }
                        val detail = errorJson?.optString("detail") ?: "Connection failed"
                        Result.failure(Exception(detail))
                    }
                } catch (e: Exception) {
                    Result.failure(e)
                }
            }

            result.fold(
                onSuccess = {
                    _state.value = _state.value.copy(
                        isConnectingIntegration = false,
                        integrationConnected = true
                    )
                    // Load rooms after successful connection
                    loadRooms()
                },
                onFailure = {
                    _state.value = _state.value.copy(
                        isConnectingIntegration = false,
                        integrationError = it.message ?: "Unknown error"
                    )
                }
            )
        }
    }

    fun loadRooms() {
        val serverUrl = _state.value.serverUrl.trimEnd('/')

        viewModelScope.launch {
            _state.value = _state.value.copy(isLoadingRooms = true)

            val rooms = withContext(Dispatchers.IO) {
                try {
                    val request = Request.Builder()
                        .url("$serverUrl/home/rooms")
                        .build()

                    val response = client.newCall(request).execute()
                    if (response.isSuccessful) {
                        val body = response.body?.string()
                        val json = JSONObject(body ?: "{}")
                        val roomsArray = json.optJSONArray("rooms") ?: JSONArray()

                        (0 until roomsArray.length()).map { i ->
                            val room = roomsArray.getJSONObject(i)
                            RoomConfig(
                                id = room.optString("id"),
                                name = room.optString("name"),
                                floor = room.optString("floor", "Main"),
                                hasLights = room.optJSONArray("lights")?.length() ?: 0 > 0,
                                hasShades = room.optJSONArray("shades")?.length() ?: 0 > 0,
                                hasClimate = room.has("thermostat")
                            )
                        }
                    } else {
                        emptyList()
                    }
                } catch (e: Exception) {
                    emptyList()
                }
            }

            _state.value = _state.value.copy(
                isLoadingRooms = false,
                availableRooms = rooms,
                selectedRooms = rooms.map { it.id }.toSet() // Select all by default
            )
        }
    }

    fun toggleRoom(roomId: String) {
        val current = _state.value.selectedRooms.toMutableSet()
        if (roomId in current) {
            current.remove(roomId)
        } else {
            current.add(roomId)
        }
        _state.value = _state.value.copy(selectedRooms = current)
    }

    fun selectAllRooms() {
        _state.value = _state.value.copy(
            selectedRooms = _state.value.availableRooms.map { it.id }.toSet()
        )
    }

    fun deselectAllRooms() {
        _state.value = _state.value.copy(selectedRooms = emptySet())
    }

    fun updateNotificationPermission(granted: Boolean) {
        _state.value = _state.value.copy(notificationPermissionGranted = granted)
    }

    fun updateLocationPermission(granted: Boolean) {
        _state.value = _state.value.copy(locationPermissionGranted = granted)
    }

    fun markComplete() {
        _state.value = _state.value.copy(isComplete = true)
    }
}

// =============================================================================
// ONBOARDING SCREEN COMPOSABLE
// =============================================================================

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun OnboardingScreen(
    onComplete: () -> Unit,
    viewModel: OnboardingViewModelDI
) {
    val context = LocalContext.current
    val view = LocalView.current
    val scope = rememberCoroutineScope()
    val state by viewModel.state.collectAsState()
    val accessibilityConfig = LocalAccessibilityConfig.current

    // Total pages: Welcome, Server Setup, Permissions, Tour (4 steps per audit)
    val totalPages = 4
    val pagerState = rememberPagerState(
        initialPage = state.currentPage.coerceIn(0, totalPages - 1),
        pageCount = { totalPages }
    )

    // Save progress when page changes
    LaunchedEffect(pagerState.currentPage) {
        viewModel.setPage(pagerState.currentPage)
    }

    // Handle completion
    LaunchedEffect(state.isComplete) {
        if (state.isComplete) {
            onComplete()
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Void)
            .systemBarsPadding()
    ) {
        // Progress indicator
        OnboardingProgressBar(
            currentPage = pagerState.currentPage,
            totalPages = totalPages,
            modifier = Modifier.padding(horizontal = 24.dp, vertical = 16.dp)
        )

        // Pager content - 4 steps: Welcome, Server Setup, Permissions, Tour
        HorizontalPager(
            state = pagerState,
            modifier = Modifier.weight(1f),
            userScrollEnabled = false // Disable swipe to prevent skipping required steps
        ) { page ->
            when (page) {
                0 -> WelcomePage()
                1 -> ServerConnectionPage(
                    state = state,
                    onServerUrlChange = viewModel::updateServerUrl,
                    onDiscover = viewModel::discoverServers,
                    onTestConnection = viewModel::testServerConnection,
                    onSelectServer = viewModel::updateServerUrl
                )
                2 -> PermissionsPage(
                    state = state,
                    onNotificationPermissionResult = viewModel::updateNotificationPermission,
                    onLocationPermissionResult = viewModel::updateLocationPermission
                )
                3 -> TourPage(
                    onComplete = {
                        viewModel.markComplete()
                    }
                )
            }
        }

        // Navigation buttons
        OnboardingNavigation(
            currentPage = pagerState.currentPage,
            totalPages = totalPages,
            canProceed = canProceedFromPage(pagerState.currentPage, state),
            isOptionalStep = isOptionalStep(pagerState.currentPage),
            onBack = {
                view.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
                scope.launch {
                    pagerState.animateScrollToPage(pagerState.currentPage - 1)
                }
            },
            onNext = {
                view.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
                scope.launch {
                    pagerState.animateScrollToPage(pagerState.currentPage + 1)
                }
            },
            onSkip = {
                view.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
                scope.launch {
                    pagerState.animateScrollToPage(pagerState.currentPage + 1)
                }
            }
        )
    }
}

private fun canProceedFromPage(page: Int, state: OnboardingState): Boolean {
    return when (page) {
        0 -> true // Welcome - always can proceed
        1 -> state.connectionSuccess == true // Server - must be connected
        2 -> true // Permissions - optional
        3 -> true // Tour - always can complete
        else -> true
    }
}

private fun isOptionalStep(page: Int): Boolean {
    return when (page) {
        2 -> true // Permissions are optional
        else -> false
    }
}

// =============================================================================
// PROGRESS BAR
// =============================================================================

@Composable
private fun OnboardingProgressBar(
    currentPage: Int,
    totalPages: Int,
    modifier: Modifier = Modifier
) {
    val progress = (currentPage + 1).toFloat() / totalPages

    Column(modifier = modifier) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Text(
                text = "Step ${currentPage + 1} of $totalPages",
                style = MaterialTheme.typography.labelSmall,
                color = Color.White.copy(alpha = 0.6f)
            )
            Text(
                text = "${(progress * 100).toInt()}%",
                style = MaterialTheme.typography.labelSmall,
                color = Crystal
            )
        }
        Spacer(modifier = Modifier.height(8.dp))
        LinearProgressIndicator(
            progress = { progress },
            modifier = Modifier
                .fillMaxWidth()
                .height(4.dp)
                .clip(RoundedCornerShape(2.dp))
                .semantics {
                    contentDescription = "Setup progress: ${(progress * 100).toInt()} percent complete"
                },
            color = Crystal,
            trackColor = VoidLight
        )
    }
}

// =============================================================================
// NAVIGATION BUTTONS
// =============================================================================

@Composable
private fun OnboardingNavigation(
    currentPage: Int,
    totalPages: Int,
    canProceed: Boolean,
    isOptionalStep: Boolean,
    onBack: () -> Unit,
    onNext: () -> Unit,
    onSkip: () -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(24.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        // Back button
        if (currentPage > 0) {
            TextButton(
                onClick = onBack,
                modifier = Modifier
                    .minTouchTarget()
                    .semantics {
                        contentDescription = "Go back to previous step"
                        role = Role.Button
                    }
            ) {
                Icon(
                    Icons.Default.ArrowBack,
                    contentDescription = null,
                    modifier = Modifier.size(18.dp)
                )
                Spacer(modifier = Modifier.width(4.dp))
                Text("Back", color = Color.White.copy(alpha = 0.6f))
            }
        } else {
            Spacer(modifier = Modifier.width(80.dp))
        }

        // Skip button (for optional steps)
        if (isOptionalStep && currentPage < totalPages - 1) {
            TextButton(
                onClick = onSkip,
                modifier = Modifier
                    .minTouchTarget()
                    .semantics {
                        contentDescription = "Skip this optional step"
                        role = Role.Button
                    }
            ) {
                Text("Skip", color = Color.White.copy(alpha = 0.4f))
            }
        }

        // Next/Continue button
        if (currentPage < totalPages - 1) {
            Button(
                onClick = onNext,
                enabled = canProceed,
                colors = ButtonDefaults.buttonColors(
                    containerColor = Crystal,
                    contentColor = Void,
                    disabledContainerColor = Crystal.copy(alpha = 0.3f),
                    disabledContentColor = Void.copy(alpha = 0.5f)
                ),
                modifier = Modifier
                    .minTouchTarget()
                    .semantics {
                        contentDescription = if (canProceed) "Continue to next step" else "Complete current step to continue"
                        role = Role.Button
                    }
            ) {
                Text(
                    text = if (currentPage == 0) "Get Started" else "Continue",
                    fontWeight = FontWeight.Medium
                )
                Spacer(modifier = Modifier.width(4.dp))
                Icon(
                    Icons.Default.ArrowForward,
                    contentDescription = null,
                    modifier = Modifier.size(18.dp)
                )
            }
        }
    }
}

// =============================================================================
// PAGE 1: WELCOME
// =============================================================================

@Composable
private fun WelcomePage() {
    val infiniteTransition = rememberInfiniteTransition(label = "welcome")
    val pulseAlpha by infiniteTransition.animateFloat(
        initialValue = 0.6f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(2584, easing = EaseInOutSine),
            repeatMode = RepeatMode.Reverse
        ),
        label = "pulse"
    )

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp)
            .semantics(mergeDescendants = true) {
                contentDescription = "Welcome to Kagami, your personal home intelligence. Kagami connects your smart home devices and learns your preferences to create a seamless living experience. Swipe or tap Get Started to begin setup."
            },
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        // Animated logo
        Box(
            modifier = Modifier
                .size(120.dp)
                .clip(CircleShape)
                .background(
                    Brush.radialGradient(
                        colors = listOf(
                            Crystal.copy(alpha = 0.3f * pulseAlpha),
                            Crystal.copy(alpha = 0.1f * pulseAlpha),
                            Color.Transparent
                        )
                    )
                ),
            contentAlignment = Alignment.Center
        ) {
            Icon(
                imageVector = Icons.Default.AutoAwesome,
                contentDescription = null,
                tint = Crystal,
                modifier = Modifier.size(64.dp)
            )
        }

        Spacer(modifier = Modifier.height(40.dp))

        Text(
            text = "Welcome to Kagami",
            style = MaterialTheme.typography.headlineLarge,
            fontWeight = FontWeight.Bold,
            color = Color.White,
            textAlign = TextAlign.Center,
            modifier = Modifier.semantics { heading() }
        )

        Spacer(modifier = Modifier.height(8.dp))

        Text(
            text = "Your Personal Home Intelligence",
            style = MaterialTheme.typography.titleMedium,
            color = Crystal,
            textAlign = TextAlign.Center
        )

        Spacer(modifier = Modifier.height(32.dp))

        Text(
            text = "Kagami connects your smart home devices and learns your preferences to create a seamless living experience.",
            style = MaterialTheme.typography.bodyLarge,
            color = Color.White.copy(alpha = 0.7f),
            textAlign = TextAlign.Center,
            lineHeight = 24.sp
        )

        Spacer(modifier = Modifier.height(48.dp))

        // Feature highlights
        Column(
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            WelcomeFeature(
                icon = Icons.Default.Home,
                title = "Smart Home Control",
                description = "Control lights, shades, climate, and more"
            )
            WelcomeFeature(
                icon = Icons.Default.Mic,
                title = "Voice Commands",
                description = "Natural language for effortless control"
            )
            WelcomeFeature(
                icon = Icons.Default.Security,
                title = "Safety First",
                description = "Every action respects your safety"
            )
        }
    }
}

@Composable
private fun WelcomeFeature(
    icon: ImageVector,
    title: String,
    description: String
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clearAndSetSemantics { },
        verticalAlignment = Alignment.CenterVertically
    ) {
        Box(
            modifier = Modifier
                .size(44.dp)
                .clip(RoundedCornerShape(12.dp))
                .background(Crystal.copy(alpha = 0.1f)),
            contentAlignment = Alignment.Center
        ) {
            Icon(
                imageVector = icon,
                contentDescription = null,
                tint = Crystal,
                modifier = Modifier.size(24.dp)
            )
        }
        Spacer(modifier = Modifier.width(16.dp))
        Column {
            Text(
                text = title,
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.Medium,
                color = Color.White
            )
            Text(
                text = description,
                style = MaterialTheme.typography.bodySmall,
                color = Color.White.copy(alpha = 0.6f)
            )
        }
    }
}

// =============================================================================
// PAGE 2: SERVER CONNECTION
// =============================================================================

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ServerConnectionPage(
    state: OnboardingState,
    onServerUrlChange: (String) -> Unit,
    onDiscover: () -> Unit,
    onTestConnection: () -> Unit,
    onSelectServer: (String) -> Unit
) {
    val view = LocalView.current

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp)
            .verticalScroll(rememberScrollState()),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Icon(
            imageVector = Icons.Default.Cloud,
            contentDescription = null,
            tint = Beacon,
            modifier = Modifier.size(48.dp)
        )

        Spacer(modifier = Modifier.height(24.dp))

        Text(
            text = "Connect to Kagami",
            style = MaterialTheme.typography.headlineSmall,
            fontWeight = FontWeight.Bold,
            color = Color.White,
            modifier = Modifier.semantics { heading() }
        )

        Spacer(modifier = Modifier.height(8.dp))

        Text(
            text = "Enter your Kagami server address or discover it automatically",
            style = MaterialTheme.typography.bodyMedium,
            color = Color.White.copy(alpha = 0.6f),
            textAlign = TextAlign.Center
        )

        Spacer(modifier = Modifier.height(32.dp))

        // Server URL input
        OutlinedTextField(
            value = state.serverUrl,
            onValueChange = onServerUrlChange,
            label = { Text("Server URL") },
            placeholder = { Text("http://kagami.local:8001") },
            singleLine = true,
            leadingIcon = {
                Icon(
                    Icons.Default.Cloud,
                    contentDescription = null,
                    tint = Color.White.copy(alpha = 0.6f)
                )
            },
            trailingIcon = {
                IconButton(
                    onClick = {
                        view.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
                        onDiscover()
                    },
                    enabled = !state.isDiscovering,
                    modifier = Modifier.semantics {
                        contentDescription = "Discover Kagami servers on your network"
                        role = Role.Button
                    }
                ) {
                    if (state.isDiscovering) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(20.dp),
                            color = Beacon,
                            strokeWidth = 2.dp
                        )
                    } else {
                        Icon(
                            Icons.Default.Search,
                            contentDescription = null,
                            tint = Beacon
                        )
                    }
                }
            },
            colors = kagamiTextFieldColors(),
            modifier = Modifier
                .fillMaxWidth()
                .semantics {
                    contentDescription = "Server URL. Enter your Kagami server address."
                }
        )

        // Discovered servers
        if (state.discoveredServers.isNotEmpty()) {
            Spacer(modifier = Modifier.height(16.dp))
            Text(
                text = "Found ${state.discoveredServers.size} server(s):",
                style = MaterialTheme.typography.labelMedium,
                color = Color.White.copy(alpha = 0.6f),
                modifier = Modifier.fillMaxWidth()
            )
            Spacer(modifier = Modifier.height(8.dp))

            state.discoveredServers.forEach { server ->
                Card(
                    onClick = { onSelectServer(server) },
                    colors = CardDefaults.cardColors(
                        containerColor = if (state.serverUrl == server) Crystal.copy(alpha = 0.2f) else VoidLight
                    ),
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 4.dp)
                        .semantics {
                            contentDescription = "Select server $server"
                            role = Role.Button
                        }
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(12.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(
                            Icons.Default.Cloud,
                            contentDescription = null,
                            tint = if (state.serverUrl == server) Crystal else Beacon,
                            modifier = Modifier.size(20.dp)
                        )
                        Spacer(modifier = Modifier.width(12.dp))
                        Text(
                            text = server,
                            style = MaterialTheme.typography.bodyMedium,
                            color = Color.White
                        )
                        if (state.serverUrl == server) {
                            Spacer(modifier = Modifier.weight(1f))
                            Icon(
                                Icons.Default.Check,
                                contentDescription = null,
                                tint = Crystal,
                                modifier = Modifier.size(20.dp)
                            )
                        }
                    }
                }
            }
        }

        Spacer(modifier = Modifier.height(24.dp))

        // Connection test button
        Button(
            onClick = {
                view.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
                onTestConnection()
            },
            enabled = state.serverUrl.isNotBlank() && !state.isTestingConnection,
            colors = ButtonDefaults.buttonColors(
                containerColor = when {
                    state.connectionSuccess == true -> SafetyOk
                    state.connectionSuccess == false -> SafetyViolation.copy(alpha = 0.8f)
                    else -> Beacon
                },
                contentColor = Void
            ),
            modifier = Modifier
                .fillMaxWidth()
                .defaultMinSize(minHeight = MinTouchTargetSize)
                .semantics {
                    contentDescription = when {
                        state.connectionSuccess == true -> "Connected successfully"
                        state.connectionSuccess == false -> "Connection failed. Tap to retry."
                        else -> "Test connection to server"
                    }
                    role = Role.Button
                }
        ) {
            if (state.isTestingConnection) {
                CircularProgressIndicator(
                    modifier = Modifier.size(20.dp),
                    color = Void,
                    strokeWidth = 2.dp
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text("Connecting...")
            } else {
                Icon(
                    imageVector = when {
                        state.connectionSuccess == true -> Icons.Default.Check
                        state.connectionSuccess == false -> Icons.Default.Refresh
                        else -> Icons.Default.Wifi
                    },
                    contentDescription = null,
                    modifier = Modifier.size(20.dp)
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = when {
                        state.connectionSuccess == true -> "Connected!"
                        state.connectionSuccess == false -> "Retry Connection"
                        else -> "Test Connection"
                    }
                )
            }
        }

        // Error message
        if (state.connectionError != null) {
            Spacer(modifier = Modifier.height(16.dp))
            Card(
                colors = CardDefaults.cardColors(
                    containerColor = SafetyViolation.copy(alpha = 0.15f)
                ),
                modifier = Modifier
                    .fillMaxWidth()
                    .semantics {
                        contentDescription = "Error: ${state.connectionError}"
                    }
            ) {
                Row(
                    modifier = Modifier.padding(12.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(
                        Icons.Default.Warning,
                        contentDescription = null,
                        tint = SafetyViolation,
                        modifier = Modifier.size(20.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = state.connectionError,
                        style = MaterialTheme.typography.bodySmall,
                        color = SafetyViolation
                    )
                }
            }
        }

        // Success message
        if (state.connectionSuccess == true) {
            Spacer(modifier = Modifier.height(16.dp))
            Card(
                colors = CardDefaults.cardColors(
                    containerColor = SafetyOk.copy(alpha = 0.15f)
                ),
                modifier = Modifier.fillMaxWidth()
            ) {
                Row(
                    modifier = Modifier.padding(12.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(
                        Icons.Default.CheckCircle,
                        contentDescription = null,
                        tint = SafetyOk,
                        modifier = Modifier.size(20.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = "Successfully connected to Kagami!",
                        style = MaterialTheme.typography.bodySmall,
                        color = SafetyOk
                    )
                }
            }
        }
    }
}

// =============================================================================
// PAGE 3: INTEGRATION SELECTION
// =============================================================================

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun IntegrationSelectionPage(
    state: OnboardingState,
    onSelectIntegration: (SmartHomeIntegration?) -> Unit,
    onCredentialChange: (String, String) -> Unit,
    onConnect: () -> Unit
) {
    val view = LocalView.current

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp)
            .verticalScroll(rememberScrollState()),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Icon(
            imageVector = Icons.Default.Devices,
            contentDescription = null,
            tint = Nexus,
            modifier = Modifier.size(48.dp)
        )

        Spacer(modifier = Modifier.height(24.dp))

        Text(
            text = "Smart Home Integration",
            style = MaterialTheme.typography.headlineSmall,
            fontWeight = FontWeight.Bold,
            color = Color.White,
            modifier = Modifier.semantics { heading() }
        )

        Spacer(modifier = Modifier.height(8.dp))

        Text(
            text = "Connect your smart home platform to Kagami",
            style = MaterialTheme.typography.bodyMedium,
            color = Color.White.copy(alpha = 0.6f),
            textAlign = TextAlign.Center
        )

        Spacer(modifier = Modifier.height(24.dp))

        // Integration options
        SmartHomeIntegration.entries.forEach { integration ->
            val isSelected = state.selectedIntegration == integration

            Card(
                onClick = {
                    view.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
                    onSelectIntegration(if (isSelected) null else integration)
                },
                colors = CardDefaults.cardColors(
                    containerColor = if (isSelected) integration.color.copy(alpha = 0.15f) else VoidLight
                ),
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = 4.dp)
                    .then(
                        if (isSelected) Modifier.border(
                            1.dp,
                            integration.color.copy(alpha = 0.5f),
                            RoundedCornerShape(12.dp)
                        ) else Modifier
                    )
                    .semantics {
                        contentDescription = "${integration.displayName}. ${integration.description}. ${if (isSelected) "Selected" else "Tap to select"}"
                        role = Role.Button
                    }
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Box(
                        modifier = Modifier
                            .size(44.dp)
                            .clip(RoundedCornerShape(12.dp))
                            .background(integration.color.copy(alpha = 0.2f)),
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(
                            imageVector = integration.icon,
                            contentDescription = null,
                            tint = integration.color,
                            modifier = Modifier.size(24.dp)
                        )
                    }
                    Spacer(modifier = Modifier.width(16.dp))
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            text = integration.displayName,
                            style = MaterialTheme.typography.titleSmall,
                            fontWeight = FontWeight.Medium,
                            color = Color.White
                        )
                        Text(
                            text = integration.description,
                            style = MaterialTheme.typography.bodySmall,
                            color = Color.White.copy(alpha = 0.6f)
                        )
                    }
                    if (isSelected) {
                        Icon(
                            Icons.Default.CheckCircle,
                            contentDescription = null,
                            tint = integration.color,
                            modifier = Modifier.size(24.dp)
                        )
                    }
                }

                // Show credentials form if selected
                AnimatedVisibility(visible = isSelected && !state.integrationConnected) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 16.dp)
                            .padding(bottom = 16.dp)
                    ) {
                        Divider(color = Color.White.copy(alpha = 0.1f))
                        Spacer(modifier = Modifier.height(16.dp))

                        integration.requiredFields.forEach { field ->
                            OutlinedTextField(
                                value = state.integrationCredentials[field.key] ?: "",
                                onValueChange = { onCredentialChange(field.key, it) },
                                label = { Text(field.label) },
                                placeholder = { Text(field.placeholder) },
                                singleLine = true,
                                visualTransformation = if (field.isPassword) {
                                    androidx.compose.ui.text.input.PasswordVisualTransformation()
                                } else {
                                    androidx.compose.ui.text.input.VisualTransformation.None
                                },
                                colors = kagamiTextFieldColors(),
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(vertical = 4.dp)
                            )
                        }

                        Spacer(modifier = Modifier.height(16.dp))

                        Button(
                            onClick = {
                                view.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
                                onConnect()
                            },
                            enabled = !state.isConnectingIntegration,
                            colors = ButtonDefaults.buttonColors(
                                containerColor = integration.color,
                                contentColor = Color.White
                            ),
                            modifier = Modifier
                                .fillMaxWidth()
                                .defaultMinSize(minHeight = MinTouchTargetSize)
                        ) {
                            if (state.isConnectingIntegration) {
                                CircularProgressIndicator(
                                    modifier = Modifier.size(20.dp),
                                    color = Color.White,
                                    strokeWidth = 2.dp
                                )
                                Spacer(modifier = Modifier.width(8.dp))
                                Text("Connecting...")
                            } else {
                                Text("Connect ${integration.displayName}")
                            }
                        }
                    }
                }

                // Show success state
                AnimatedVisibility(visible = isSelected && state.integrationConnected) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(16.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(
                            Icons.Default.CheckCircle,
                            contentDescription = null,
                            tint = SafetyOk,
                            modifier = Modifier.size(20.dp)
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            text = "Connected successfully!",
                            style = MaterialTheme.typography.bodySmall,
                            color = SafetyOk
                        )
                    }
                }
            }
        }

        // Error message
        if (state.integrationError != null) {
            Spacer(modifier = Modifier.height(16.dp))
            Card(
                colors = CardDefaults.cardColors(
                    containerColor = SafetyViolation.copy(alpha = 0.15f)
                ),
                modifier = Modifier.fillMaxWidth()
            ) {
                Row(
                    modifier = Modifier.padding(12.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(
                        Icons.Default.Warning,
                        contentDescription = null,
                        tint = SafetyViolation,
                        modifier = Modifier.size(20.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = state.integrationError,
                        style = MaterialTheme.typography.bodySmall,
                        color = SafetyViolation
                    )
                }
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        // Skip option note
        Text(
            text = "You can skip this step and configure integrations later in Settings",
            style = MaterialTheme.typography.bodySmall,
            color = Color.White.copy(alpha = 0.4f),
            textAlign = TextAlign.Center
        )
    }
}

// =============================================================================
// PAGE 4: ROOM CONFIGURATION
// =============================================================================

@Composable
private fun RoomConfigurationPage(
    state: OnboardingState,
    onToggleRoom: (String) -> Unit,
    onSelectAll: () -> Unit,
    onDeselectAll: () -> Unit,
    onLoadRooms: () -> Unit
) {
    val view = LocalView.current

    // Load rooms on first display
    LaunchedEffect(Unit) {
        if (state.availableRooms.isEmpty() && !state.isLoadingRooms) {
            onLoadRooms()
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Icon(
            imageVector = Icons.Default.MeetingRoom,
            contentDescription = null,
            tint = Grove,
            modifier = Modifier.size(48.dp)
        )

        Spacer(modifier = Modifier.height(24.dp))

        Text(
            text = "Configure Rooms",
            style = MaterialTheme.typography.headlineSmall,
            fontWeight = FontWeight.Bold,
            color = Color.White,
            modifier = Modifier.semantics { heading() }
        )

        Spacer(modifier = Modifier.height(8.dp))

        Text(
            text = "Select which rooms you want to control with Kagami",
            style = MaterialTheme.typography.bodyMedium,
            color = Color.White.copy(alpha = 0.6f),
            textAlign = TextAlign.Center
        )

        if (state.isLoadingRooms) {
            Spacer(modifier = Modifier.height(48.dp))
            CircularProgressIndicator(color = Grove)
            Spacer(modifier = Modifier.height(16.dp))
            Text(
                text = "Loading rooms...",
                style = MaterialTheme.typography.bodyMedium,
                color = Color.White.copy(alpha = 0.6f)
            )
        } else if (state.availableRooms.isEmpty()) {
            Spacer(modifier = Modifier.height(48.dp))
            Icon(
                Icons.Outlined.Home,
                contentDescription = null,
                tint = Color.White.copy(alpha = 0.3f),
                modifier = Modifier.size(64.dp)
            )
            Spacer(modifier = Modifier.height(16.dp))
            Text(
                text = "No rooms found",
                style = MaterialTheme.typography.titleMedium,
                color = Color.White.copy(alpha = 0.6f)
            )
            Text(
                text = "Connect a smart home integration to discover your rooms",
                style = MaterialTheme.typography.bodySmall,
                color = Color.White.copy(alpha = 0.4f),
                textAlign = TextAlign.Center
            )
        } else {
            Spacer(modifier = Modifier.height(16.dp))

            // Select all / Deselect all buttons
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                OutlinedButton(
                    onClick = {
                        view.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
                        onSelectAll()
                    },
                    modifier = Modifier
                        .weight(1f)
                        .minTouchTarget(),
                    colors = ButtonDefaults.outlinedButtonColors(
                        contentColor = Grove
                    ),
                    border = ButtonDefaults.outlinedButtonBorder.copy(
                        brush = androidx.compose.ui.graphics.SolidColor(Grove.copy(alpha = 0.5f))
                    )
                ) {
                    Text("Select All")
                }
                OutlinedButton(
                    onClick = {
                        view.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
                        onDeselectAll()
                    },
                    modifier = Modifier
                        .weight(1f)
                        .minTouchTarget(),
                    colors = ButtonDefaults.outlinedButtonColors(
                        contentColor = Color.White.copy(alpha = 0.6f)
                    )
                ) {
                    Text("Deselect All")
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // Room count
            Text(
                text = "${state.selectedRooms.size} of ${state.availableRooms.size} rooms selected",
                style = MaterialTheme.typography.labelMedium,
                color = Grove
            )

            Spacer(modifier = Modifier.height(8.dp))

            // Room list
            LazyColumn(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                // Group by floor
                val roomsByFloor = state.availableRooms.groupBy { it.floor }

                roomsByFloor.forEach { (floor, rooms) ->
                    item {
                        Text(
                            text = floor,
                            style = MaterialTheme.typography.labelMedium,
                            color = Color.White.copy(alpha = 0.5f),
                            modifier = Modifier.padding(vertical = 8.dp)
                        )
                    }

                    items(rooms) { room ->
                        val isSelected = room.id in state.selectedRooms

                        Card(
                            onClick = {
                                view.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
                                onToggleRoom(room.id)
                            },
                            colors = CardDefaults.cardColors(
                                containerColor = if (isSelected) Grove.copy(alpha = 0.15f) else VoidLight
                            ),
                            modifier = Modifier
                                .fillMaxWidth()
                                .semantics {
                                    contentDescription = "${room.name}. ${if (isSelected) "Selected" else "Not selected"}. ${buildRoomCapabilities(room)}"
                                    role = Role.Checkbox
                                    stateDescription = if (isSelected) "Checked" else "Unchecked"
                                }
                        ) {
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(12.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Checkbox(
                                    checked = isSelected,
                                    onCheckedChange = { onToggleRoom(room.id) },
                                    colors = CheckboxDefaults.colors(
                                        checkedColor = Grove,
                                        uncheckedColor = Color.White.copy(alpha = 0.4f)
                                    )
                                )
                                Spacer(modifier = Modifier.width(12.dp))
                                Column(modifier = Modifier.weight(1f)) {
                                    Text(
                                        text = room.name,
                                        style = MaterialTheme.typography.titleSmall,
                                        color = Color.White
                                    )
                                    Row(
                                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                                    ) {
                                        if (room.hasLights) {
                                            RoomCapabilityChip(
                                                icon = Icons.Outlined.LightMode,
                                                label = "Lights"
                                            )
                                        }
                                        if (room.hasShades) {
                                            RoomCapabilityChip(
                                                icon = Icons.Outlined.Blinds,
                                                label = "Shades"
                                            )
                                        }
                                        if (room.hasClimate) {
                                            RoomCapabilityChip(
                                                icon = Icons.Outlined.Thermostat,
                                                label = "Climate"
                                            )
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun RoomCapabilityChip(
    icon: ImageVector,
    label: String
) {
    Row(
        modifier = Modifier
            .clip(RoundedCornerShape(4.dp))
            .background(Color.White.copy(alpha = 0.1f))
            .padding(horizontal = 6.dp, vertical = 2.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(
            imageVector = icon,
            contentDescription = null,
            tint = Color.White.copy(alpha = 0.5f),
            modifier = Modifier.size(12.dp)
        )
        Spacer(modifier = Modifier.width(4.dp))
        Text(
            text = label,
            style = MaterialTheme.typography.labelSmall,
            color = Color.White.copy(alpha = 0.5f)
        )
    }
}

private fun buildRoomCapabilities(room: RoomConfig): String {
    val capabilities = mutableListOf<String>()
    if (room.hasLights) capabilities.add("lights")
    if (room.hasShades) capabilities.add("shades")
    if (room.hasClimate) capabilities.add("climate control")
    return if (capabilities.isEmpty()) "No devices" else "Has ${capabilities.joinToString(", ")}"
}

// =============================================================================
// PAGE 5: PERMISSIONS
// =============================================================================

@Composable
private fun PermissionsPage(
    state: OnboardingState,
    onNotificationPermissionResult: (Boolean) -> Unit,
    onLocationPermissionResult: (Boolean) -> Unit
) {
    val context = LocalContext.current
    val view = LocalView.current

    // Permission launchers
    val notificationPermissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        onNotificationPermissionResult(granted)
        if (granted) {
            view.performHapticFeedback(HapticFeedbackConstants.CONFIRM)
        }
    }

    val locationPermissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        onLocationPermissionResult(granted)
        if (granted) {
            view.performHapticFeedback(HapticFeedbackConstants.CONFIRM)
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp)
            .verticalScroll(rememberScrollState()),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Icon(
            imageVector = Icons.Default.Security,
            contentDescription = null,
            tint = Crystal,
            modifier = Modifier.size(48.dp)
        )

        Spacer(modifier = Modifier.height(24.dp))

        Text(
            text = "Permissions",
            style = MaterialTheme.typography.headlineSmall,
            fontWeight = FontWeight.Bold,
            color = Color.White,
            modifier = Modifier.semantics { heading() }
        )

        Spacer(modifier = Modifier.height(8.dp))

        Text(
            text = "Grant permissions for the best Kagami experience",
            style = MaterialTheme.typography.bodyMedium,
            color = Color.White.copy(alpha = 0.6f),
            textAlign = TextAlign.Center
        )

        Spacer(modifier = Modifier.height(32.dp))

        // Notification Permission
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            PermissionCard(
                icon = Icons.Default.Notifications,
                title = "Notifications",
                description = "Receive alerts about your home, safety warnings, and scene activations",
                isGranted = state.notificationPermissionGranted,
                onRequest = {
                    view.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
                    notificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
                }
            )

            Spacer(modifier = Modifier.height(16.dp))
        }

        // Location Permission
        PermissionCard(
            icon = Icons.Default.LocationOn,
            title = "Location",
            description = "Enable presence detection and location-based automations",
            isGranted = state.locationPermissionGranted,
            onRequest = {
                view.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
                locationPermissionLauncher.launch(Manifest.permission.ACCESS_FINE_LOCATION)
            }
        )

        Spacer(modifier = Modifier.height(32.dp))

        // Privacy note
        Card(
            colors = CardDefaults.cardColors(
                containerColor = Crystal.copy(alpha = 0.1f)
            ),
            modifier = Modifier.fillMaxWidth()
        ) {
            Row(
                modifier = Modifier.padding(16.dp),
                verticalAlignment = Alignment.Top
            ) {
                Icon(
                    Icons.Default.Shield,
                    contentDescription = null,
                    tint = Crystal,
                    modifier = Modifier.size(24.dp)
                )
                Spacer(modifier = Modifier.width(12.dp))
                Column {
                    Text(
                        text = "Your Privacy Matters",
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.Medium,
                        color = Color.White
                    )
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = "All data stays on your local network. Kagami never sends personal information to external servers. Safety first.",
                        style = MaterialTheme.typography.bodySmall,
                        color = Color.White.copy(alpha = 0.7f)
                    )
                }
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        Text(
            text = "These permissions are optional. You can enable them later in Settings.",
            style = MaterialTheme.typography.bodySmall,
            color = Color.White.copy(alpha = 0.4f),
            textAlign = TextAlign.Center
        )
    }
}

@Composable
private fun PermissionCard(
    icon: ImageVector,
    title: String,
    description: String,
    isGranted: Boolean,
    onRequest: () -> Unit
) {
    Card(
        colors = CardDefaults.cardColors(
            containerColor = if (isGranted) SafetyOk.copy(alpha = 0.1f) else VoidLight
        ),
        modifier = Modifier
            .fillMaxWidth()
            .semantics {
                contentDescription = "$title permission. $description. ${if (isGranted) "Granted" else "Not granted"}"
            }
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Box(
                modifier = Modifier
                    .size(44.dp)
                    .clip(RoundedCornerShape(12.dp))
                    .background(if (isGranted) SafetyOk.copy(alpha = 0.2f) else Crystal.copy(alpha = 0.1f)),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = if (isGranted) Icons.Default.Check else icon,
                    contentDescription = null,
                    tint = if (isGranted) SafetyOk else Crystal,
                    modifier = Modifier.size(24.dp)
                )
            }
            Spacer(modifier = Modifier.width(16.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = title,
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Medium,
                    color = Color.White
                )
                Text(
                    text = description,
                    style = MaterialTheme.typography.bodySmall,
                    color = Color.White.copy(alpha = 0.6f)
                )
            }
            Spacer(modifier = Modifier.width(8.dp))
            if (isGranted) {
                Text(
                    text = "Granted",
                    style = MaterialTheme.typography.labelMedium,
                    color = SafetyOk
                )
            } else {
                Button(
                    onClick = onRequest,
                    colors = ButtonDefaults.buttonColors(
                        containerColor = Crystal,
                        contentColor = Void
                    ),
                    modifier = Modifier.minTouchTarget()
                ) {
                    Text("Allow")
                }
            }
        }
    }
}

// =============================================================================
// PAGE 6: COMPLETION
// =============================================================================

@Composable
private fun CompletionPage(
    onComplete: () -> Unit
) {
    val view = LocalView.current
    var showConfetti by remember { mutableStateOf(false) }

    val infiniteTransition = rememberInfiniteTransition(label = "celebration")
    val scale by infiniteTransition.animateFloat(
        initialValue = 1f,
        targetValue = 1.1f,
        animationSpec = infiniteRepeatable(
            animation = tween(987, easing = EaseInOutSine),
            repeatMode = RepeatMode.Reverse
        ),
        label = "scale"
    )

    LaunchedEffect(Unit) {
        delay(500)
        showConfetti = true
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp)
            .semantics(mergeDescendants = true) {
                contentDescription = "Setup complete! Kagami is ready to control your home. Tap Start Using Kagami to begin."
            },
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        // Celebration icon
        Box(
            modifier = Modifier
                .size(120.dp)
                .scale(scale)
                .clip(CircleShape)
                .background(
                    Brush.radialGradient(
                        colors = listOf(
                            SafetyOk.copy(alpha = 0.3f),
                            SafetyOk.copy(alpha = 0.1f),
                            Color.Transparent
                        )
                    )
                ),
            contentAlignment = Alignment.Center
        ) {
            Icon(
                imageVector = Icons.Default.Celebration,
                contentDescription = null,
                tint = SafetyOk,
                modifier = Modifier.size(64.dp)
            )
        }

        Spacer(modifier = Modifier.height(40.dp))

        Text(
            text = "You're All Set!",
            style = MaterialTheme.typography.headlineLarge,
            fontWeight = FontWeight.Bold,
            color = Color.White,
            textAlign = TextAlign.Center,
            modifier = Modifier.semantics { heading() }
        )

        Spacer(modifier = Modifier.height(8.dp))

        Text(
            text = "Kagami is ready to control your home",
            style = MaterialTheme.typography.titleMedium,
            color = SafetyOk,
            textAlign = TextAlign.Center
        )

        Spacer(modifier = Modifier.height(32.dp))

        Text(
            text = "Your smart home is now connected. Use voice commands, tap controls, or automate with scenes to make your home work for you.",
            style = MaterialTheme.typography.bodyLarge,
            color = Color.White.copy(alpha = 0.7f),
            textAlign = TextAlign.Center,
            lineHeight = 24.sp
        )

        Spacer(modifier = Modifier.height(48.dp))

        // Completion summary
        Card(
            colors = CardDefaults.cardColors(
                containerColor = VoidLight
            ),
            modifier = Modifier.fillMaxWidth()
        ) {
            Column(
                modifier = Modifier.padding(16.dp)
            ) {
                Text(
                    text = "What's Next",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Medium,
                    color = Color.White,
                    modifier = Modifier.padding(bottom = 12.dp)
                )
                CompletionNextStep(
                    icon = Icons.Default.Mic,
                    text = "Try saying \"Turn on the lights\""
                )
                CompletionNextStep(
                    icon = Icons.Default.AutoAwesome,
                    text = "Explore Scenes for one-tap control"
                )
                CompletionNextStep(
                    icon = Icons.Default.Widgets,
                    text = "Add Kagami widgets to your home screen"
                )
            }
        }

        Spacer(modifier = Modifier.weight(1f))

        // Start button
        Button(
            onClick = {
                view.performHapticFeedback(HapticFeedbackConstants.CONFIRM)
                onComplete()
            },
            colors = ButtonDefaults.buttonColors(
                containerColor = SafetyOk,
                contentColor = Void
            ),
            modifier = Modifier
                .fillMaxWidth()
                .defaultMinSize(minHeight = 56.dp)
                .semantics {
                    contentDescription = "Start using Kagami"
                    role = Role.Button
                }
        ) {
            Text(
                text = "Start Using Kagami",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold
            )
        }

        Spacer(modifier = Modifier.height(16.dp))

        Text(
            text = "Safety first. Always.",
            style = MaterialTheme.typography.bodySmall,
            color = Crystal.copy(alpha = 0.5f)
        )
    }
}

@Composable
private fun CompletionNextStep(
    icon: ImageVector,
    text: String
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(
            imageVector = icon,
            contentDescription = null,
            tint = Crystal,
            modifier = Modifier.size(20.dp)
        )
        Spacer(modifier = Modifier.width(12.dp))
        Text(
            text = text,
            style = MaterialTheme.typography.bodyMedium,
            color = Color.White.copy(alpha = 0.8f)
        )
    }
}

// =============================================================================
// PAGE 4: TOUR (4-Step Flow Final Page)
// =============================================================================

@Composable
private fun TourPage(onComplete: () -> Unit) {
    val view = LocalView.current
    val scrollState = rememberScrollState()

    val infiniteTransition = rememberInfiniteTransition(label = "tour_animation")
    val heroScale by infiniteTransition.animateFloat(
        initialValue = 1f,
        targetValue = 1.05f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 1597, easing = EaseInOutSine),
            repeatMode = RepeatMode.Reverse
        ),
        label = "hero_scale"
    )

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp)
            .verticalScroll(scrollState),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Spacer(modifier = Modifier.height(16.dp))

        // Animated home icon
        Box(
            modifier = Modifier
                .size(100.dp)
                .scale(heroScale)
                .clip(CircleShape)
                .background(
                    Brush.radialGradient(
                        colors = listOf(
                            Crystal.copy(alpha = 0.3f),
                            Crystal.copy(alpha = 0.1f),
                            Color.Transparent
                        )
                    )
                ),
            contentAlignment = Alignment.Center
        ) {
            Icon(
                imageVector = Icons.Default.Home,
                contentDescription = null,
                tint = Crystal,
                modifier = Modifier.size(56.dp)
            )
        }

        Spacer(modifier = Modifier.height(24.dp))

        Text(
            text = "Welcome to Kagami",
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Bold,
            color = Color.White,
            textAlign = TextAlign.Center,
            modifier = Modifier.semantics { heading() }
        )

        Spacer(modifier = Modifier.height(8.dp))

        Text(
            text = "Your smart home is ready. Here's a quick tour.",
            style = MaterialTheme.typography.bodyLarge,
            color = Color.White.copy(alpha = 0.7f),
            textAlign = TextAlign.Center
        )

        Spacer(modifier = Modifier.height(32.dp))

        // Tour feature cards
        TourFeatureCard(
            stepNumber = 1,
            icon = Icons.Default.Lightbulb,
            title = "Control Your Home",
            description = "Tap rooms to control lights and devices. Use the quick actions at the top for one-tap scenes."
        )

        Spacer(modifier = Modifier.height(12.dp))

        TourFeatureCard(
            stepNumber = 2,
            icon = Icons.Default.Mic,
            title = "Voice Commands",
            description = "Say \"Hey Google, turn on movie mode\" or use the in-app voice button for hands-free control."
        )

        Spacer(modifier = Modifier.height(12.dp))

        TourFeatureCard(
            stepNumber = 3,
            icon = Icons.Default.Widgets,
            title = "Home Screen Widgets",
            description = "Long-press your home screen and add Kagami widgets for instant access to scenes and room controls."
        )

        Spacer(modifier = Modifier.height(12.dp))

        TourFeatureCard(
            stepNumber = 4,
            icon = Icons.Default.Watch,
            title = "Wear OS Support",
            description = "Add Kagami tiles to your watch for quick access. Complications show your home's safety status."
        )

        Spacer(modifier = Modifier.height(24.dp))

        // Safety reminder card
        Card(
            colors = CardDefaults.cardColors(
                containerColor = SafetyOk.copy(alpha = 0.1f)
            ),
            modifier = Modifier
                .fillMaxWidth()
                .semantics {
                    contentDescription = "Safety feature: All actions are protected by safety constraints. h of x is always greater than or equal to zero."
                }
        ) {
            Row(
                modifier = Modifier.padding(16.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Icon(
                    imageVector = Icons.Default.Shield,
                    contentDescription = null,
                    tint = SafetyOk,
                    modifier = Modifier.size(24.dp)
                )
                Spacer(modifier = Modifier.width(12.dp))
                Column {
                    Text(
                        text = "Safety First. Always.",
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.Medium,
                        color = SafetyOk
                    )
                    Text(
                        text = "Your home is protected by safety constraints",
                        style = MaterialTheme.typography.bodySmall,
                        color = Color.White.copy(alpha = 0.6f)
                    )
                }
            }
        }

        Spacer(modifier = Modifier.weight(1f))

        // Get Started button
        Button(
            onClick = {
                view.performHapticFeedback(HapticFeedbackConstants.CONFIRM)
                onComplete()
            },
            colors = ButtonDefaults.buttonColors(
                containerColor = Crystal,
                contentColor = Void
            ),
            modifier = Modifier
                .fillMaxWidth()
                .defaultMinSize(minHeight = MinTouchTargetSize)
                .semantics {
                    contentDescription = "Get started with Kagami"
                    role = Role.Button
                }
        ) {
            Icon(
                Icons.Default.Rocket,
                contentDescription = null,
                modifier = Modifier.size(20.dp)
            )
            Spacer(modifier = Modifier.width(8.dp))
            Text("Get Started", fontWeight = FontWeight.Medium)
        }

        Spacer(modifier = Modifier.height(16.dp))
    }
}

@Composable
private fun TourFeatureCard(
    stepNumber: Int,
    icon: ImageVector,
    title: String,
    description: String
) {
    Card(
        colors = CardDefaults.cardColors(containerColor = VoidLight),
        modifier = Modifier
            .fillMaxWidth()
            .semantics(mergeDescendants = true) {
                contentDescription = "Step $stepNumber: $title. $description"
            }
    ) {
        Row(
            modifier = Modifier.padding(16.dp),
            verticalAlignment = Alignment.Top
        ) {
            // Step number badge
            Box(
                modifier = Modifier
                    .size(28.dp)
                    .clip(RoundedCornerShape(8.dp))
                    .background(Crystal.copy(alpha = 0.2f)),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = "$stepNumber",
                    style = MaterialTheme.typography.labelMedium,
                    fontWeight = FontWeight.Bold,
                    color = Crystal
                )
            }

            Spacer(modifier = Modifier.width(12.dp))

            Column(modifier = Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        imageVector = icon,
                        contentDescription = null,
                        tint = Crystal,
                        modifier = Modifier.size(18.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = title,
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.Medium,
                        color = Color.White
                    )
                }
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = description,
                    style = MaterialTheme.typography.bodySmall,
                    color = Color.White.copy(alpha = 0.7f),
                    lineHeight = 18.sp
                )
            }
        }
    }
}

// =============================================================================
// HELPER COMPOSABLES
// =============================================================================

@Composable
private fun kagamiTextFieldColors() = OutlinedTextFieldDefaults.colors(
    focusedTextColor = Color.White,
    unfocusedTextColor = Color.White,
    focusedBorderColor = Crystal,
    unfocusedBorderColor = Color.White.copy(alpha = 0.3f),
    focusedLabelColor = Crystal,
    unfocusedLabelColor = Color.White.copy(alpha = 0.5f),
    cursorColor = Crystal,
    focusedPlaceholderColor = Color.White.copy(alpha = 0.4f),
    unfocusedPlaceholderColor = Color.White.copy(alpha = 0.3f),
    focusedLeadingIconColor = Crystal,
    unfocusedLeadingIconColor = Color.White.copy(alpha = 0.6f)
)

/*
 * Mirror
 * h(x) >= 0. Always.
 */
