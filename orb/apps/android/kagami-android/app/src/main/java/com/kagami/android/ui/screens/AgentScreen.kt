/**
 * Agent Screen — WebView Container for HTML Agents
 *
 * Renders HTML agents with native bridge support.
 * Enables agent websites to use Android capabilities via JavaScript.
 *
 * Colony: Nexus (e4) — Integration
 * h(x) >= 0. Always.
 */

package com.kagami.android.ui.screens

import android.annotation.SuppressLint
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import android.webkit.JavascriptInterface
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import com.kagami.android.services.DeviceControlService
import com.kagami.android.services.SceneService
import com.kagami.android.ui.theme.KagamiColors
import dagger.hilt.android.lifecycle.HiltViewModel
import androidx.lifecycle.ViewModel
import androidx.hilt.navigation.compose.hiltViewModel
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import javax.inject.Inject

// ============================================================================
// Agent Data Model
// ============================================================================

@Serializable
data class AgentInfo(
    val id: String,
    val name: String,
    val description: String,
    val colony: String
)

// ============================================================================
// Kagami Native Bridge (JavaScript Interface)
// ============================================================================

/**
 * JavaScript interface for HTML agents to call native Android capabilities.
 *
 * Usage in JavaScript:
 * ```javascript
 * // Haptic feedback
 * window.KagamiBridge.haptic('medium');
 *
 * // Clipboard
 * window.KagamiBridge.clipboard('text to copy');
 *
 * // Device control
 * window.KagamiBridge.setLights(50, ['Living Room']);
 * window.KagamiBridge.executeScene('movie_mode');
 * ```
 */
class KagamiBridge(
    private val context: Context,
    private val webView: WebView,
    private val deviceControl: DeviceControlService,
    private val sceneService: SceneService
) {
    private val json = Json { ignoreUnknownKeys = true }
    private val scope = CoroutineScope(Dispatchers.Main)

    @JavascriptInterface
    fun haptic(style: String) {
        val vibrator = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            val manager = context.getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as VibratorManager
            manager.defaultVibrator
        } else {
            @Suppress("DEPRECATION")
            context.getSystemService(Context.VIBRATOR_SERVICE) as Vibrator
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val effect = when (style) {
                "light" -> VibrationEffect.createOneShot(30, VibrationEffect.DEFAULT_AMPLITUDE)
                "medium" -> VibrationEffect.createOneShot(50, VibrationEffect.DEFAULT_AMPLITUDE)
                "heavy" -> VibrationEffect.createOneShot(100, VibrationEffect.DEFAULT_AMPLITUDE)
                "success" -> VibrationEffect.createWaveform(longArrayOf(0, 50, 50, 50), -1)
                "error" -> VibrationEffect.createWaveform(longArrayOf(0, 100, 50, 100), -1)
                else -> VibrationEffect.createOneShot(50, VibrationEffect.DEFAULT_AMPLITUDE)
            }
            vibrator.vibrate(effect)
        } else {
            @Suppress("DEPRECATION")
            vibrator.vibrate(50)
        }
    }

    @JavascriptInterface
    fun clipboard(text: String): Boolean {
        return try {
            val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
            val clip = ClipData.newPlainText("Kagami", text)
            clipboard.setPrimaryClip(clip)
            true
        } catch (e: Exception) {
            false
        }
    }

    @JavascriptInterface
    fun share(text: String?, url: String?) {
        val shareText = buildString {
            text?.let { append(it) }
            if (text != null && url != null) append("\n\n")
            url?.let { append(it) }
        }

        if (shareText.isNotEmpty()) {
            val intent = Intent(Intent.ACTION_SEND).apply {
                type = "text/plain"
                putExtra(Intent.EXTRA_TEXT, shareText)
            }
            context.startActivity(Intent.createChooser(intent, "Share"))
        }
    }

    @JavascriptInterface
    fun setLights(level: Int, roomsJson: String?): String {
        return try {
            scope.launch {
                val rooms = roomsJson?.let {
                    json.decodeFromString<List<String>>(it)
                }
                deviceControl.setLights(level, rooms)
            }
            json.encodeToString(mapOf("success" to true))
        } catch (e: Exception) {
            json.encodeToString(mapOf("success" to false, "error" to e.message))
        }
    }

    @JavascriptInterface
    fun executeScene(sceneName: String): String {
        return try {
            scope.launch {
                sceneService.executeScene(sceneName)
            }
            json.encodeToString(mapOf("success" to true))
        } catch (e: Exception) {
            json.encodeToString(mapOf("success" to false, "error" to e.message))
        }
    }

    @JavascriptInterface
    fun getPlatformInfo(): String {
        return json.encodeToString(mapOf(
            "platform" to "android",
            "version" to Build.VERSION.SDK_INT.toString(),
            "model" to Build.MODEL,
            "capabilities" to listOf(
                "haptic",
                "clipboard",
                "share",
                "device_control",
                "scenes"
            )
        ))
    }

    /**
     * Sends a callback response to JavaScript.
     */
    fun sendCallback(callbackId: Int, success: Boolean, result: Any? = null, error: String? = null) {
        val response = json.encodeToString(mapOf(
            "id" to callbackId,
            "success" to success,
            "result" to result?.toString(),
            "error" to error
        ))

        webView.post {
            webView.evaluateJavascript(
                "window.kagamiBridgeCallback($callbackId, $response)",
                null
            )
        }
    }
}

// ============================================================================
// Agent WebView Composable
// ============================================================================

@SuppressLint("SetJavaScriptEnabled")
@Composable
fun AgentWebView(
    agentId: String,
    modifier: Modifier = Modifier,
    deviceControl: DeviceControlService,
    sceneService: SceneService
) {
    val context = LocalContext.current

    // Build URL for agent
    val baseUrl = "http://kagami.local:8000" // TODO: Get from config
    val agentUrl = "$baseUrl/agents/$agentId.html"

    AndroidView(
        modifier = modifier.fillMaxSize(),
        factory = { ctx ->
            WebView(ctx).apply {
                settings.apply {
                    javaScriptEnabled = true
                    domStorageEnabled = true
                    databaseEnabled = true
                    allowFileAccess = false
                    allowContentAccess = false
                }

                // Create and add bridge
                val bridge = KagamiBridge(ctx, this, deviceControl, sceneService)
                addJavascriptInterface(bridge, "KagamiBridge")

                // Inject setup script on page load
                webViewClient = object : WebViewClient() {
                    override fun onPageFinished(view: WebView?, url: String?) {
                        super.onPageFinished(view, url)

                        // Inject bridge setup script
                        val setupScript = """
                        (function() {
                            window.__KAGAMI_BRIDGE__ = {
                                platform: 'android',
                                capabilities: ['haptic', 'clipboard', 'share', 'device_control', 'scenes'],

                                invoke: function(action, params) {
                                    // Android uses direct method calls via @JavascriptInterface
                                    // This is a compatibility layer
                                    switch(action) {
                                        case 'haptic':
                                            return Promise.resolve(KagamiBridge.haptic(params.style || 'medium'));
                                        case 'clipboard':
                                            return Promise.resolve(KagamiBridge.clipboard(params.text));
                                        case 'share':
                                            return Promise.resolve(KagamiBridge.share(params.text, params.url));
                                        case 'setLights':
                                            return Promise.resolve(JSON.parse(
                                                KagamiBridge.setLights(
                                                    params.level,
                                                    JSON.stringify(params.rooms)
                                                )
                                            ));
                                        case 'executeScene':
                                            return Promise.resolve(JSON.parse(
                                                KagamiBridge.executeScene(params.scene)
                                            ));
                                        case 'getPlatformInfo':
                                            return Promise.resolve(JSON.parse(
                                                KagamiBridge.getPlatformInfo()
                                            ));
                                        default:
                                            return Promise.reject(new Error('Unknown action: ' + action));
                                    }
                                },

                                // Convenience methods
                                haptic: function(style) {
                                    return this.invoke('haptic', { style: style || 'medium' });
                                },
                                setLights: function(level, rooms) {
                                    return this.invoke('setLights', { level, rooms });
                                },
                                executeScene: function(scene) {
                                    return this.invoke('executeScene', { scene });
                                }
                            };

                            console.log('✅ Kagami Native Bridge ready (Android)');
                        })();
                        """.trimIndent()

                        view?.evaluateJavascript(setupScript, null)
                    }

                    override fun shouldOverrideUrlLoading(
                        view: WebView?,
                        request: WebResourceRequest?
                    ): Boolean {
                        val url = request?.url ?: return false

                        // Handle kagami:// scheme
                        if (url.scheme == "kagami") {
                            // Handle internally
                            return true
                        }

                        // Allow local URLs
                        if (url.scheme == "file" ||
                            url.host == "localhost" ||
                            url.host?.endsWith(".local") == true
                        ) {
                            return false
                        }

                        // Open external URLs in browser
                        if (url.scheme == "https" || url.scheme == "http") {
                            context.startActivity(Intent(Intent.ACTION_VIEW, url))
                            return true
                        }

                        return false
                    }
                }

                // Set dark background
                setBackgroundColor(android.graphics.Color.parseColor("#07060B"))

                // Load the agent
                loadUrl(agentUrl)
            }
        }
    )
}

// ============================================================================
// Agent ViewModel
// ============================================================================

@HiltViewModel
class AgentsViewModel @Inject constructor(
    val deviceControlService: DeviceControlService,
    val sceneService: SceneService
) : ViewModel()

// ============================================================================
// Agent Browser Screen
// ============================================================================

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AgentsScreen(
    onBack: (() -> Unit)? = null,
    viewModel: AgentsViewModel = hiltViewModel()
) {
    var agents by remember { mutableStateOf<List<AgentInfo>>(emptyList()) }
    var isLoading by remember { mutableStateOf(true) }
    var selectedAgent by remember { mutableStateOf<AgentInfo?>(null) }

    // Load agents
    LaunchedEffect(Unit) {
        isLoading = true
        // TODO: Fetch from API
        agents = listOf(
            AgentInfo("dashboard", "Dashboard", "Home overview and quick actions", "nexus"),
            AgentInfo("rooms", "Rooms", "Per-room device control", "beacon"),
            AgentInfo("scenes", "Scenes", "Scene activation", "forge")
        )
        isLoading = false
    }

    // Handle selected agent in sheet
    selectedAgent?.let { agent ->
        ModalBottomSheet(
            onDismissRequest = { selectedAgent = null }
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(600.dp)
            ) {
                TopAppBar(
                    title = { Text(agent.name) },
                    actions = {
                        IconButton(onClick = { /* TODO: Refresh */ }) {
                            Icon(Icons.Default.Refresh, contentDescription = "Refresh")
                        }
                    }
                )
                AgentWebView(
                    agentId = agent.id,
                    modifier = Modifier.fillMaxSize(),
                    deviceControl = viewModel.deviceControlService,
                    sceneService = viewModel.sceneService
                )
            }
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Agents") },
                navigationIcon = {
                    if (onBack != null) {
                        IconButton(onClick = onBack) {
                            Icon(
                                Icons.AutoMirrored.Filled.ArrowBack,
                                contentDescription = "Back"
                            )
                        }
                    }
                }
            )
        }
    ) { padding ->
        if (isLoading) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                contentAlignment = Alignment.Center
            ) {
                CircularProgressIndicator(color = KagamiColors.crystal)
            }
        } else if (agents.isEmpty()) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = "No agents available",
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        } else {
            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                items(agents) { agent ->
                    AgentCard(
                        agent = agent,
                        onClick = { selectedAgent = agent }
                    )
                }
            }
        }
    }
}

@Composable
private fun AgentCard(
    agent: AgentInfo,
    onClick: () -> Unit
) {
    val colonyColor = when (agent.colony) {
        "spark" -> KagamiColors.spark
        "forge" -> KagamiColors.forge
        "flow" -> KagamiColors.flow
        "nexus" -> KagamiColors.nexus
        "beacon" -> KagamiColors.beacon
        "grove" -> KagamiColors.grove
        "crystal" -> KagamiColors.crystal
        else -> KagamiColors.crystal
    }

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .semantics {
                contentDescription = "${agent.name}. ${agent.description}. Tap to open."
            },
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant
        )
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            // Colony indicator
            Box(
                modifier = Modifier
                    .size(48.dp)
                    .clip(CircleShape)
                    .background(colonyColor.copy(alpha = 0.2f)),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = agent.name.first().toString(),
                    style = MaterialTheme.typography.titleMedium,
                    color = colonyColor
                )
            }

            Spacer(modifier = Modifier.width(16.dp))

            // Name and description
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = agent.name,
                    style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.onSurface
                )
                Text(
                    text = agent.description,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
            }

            // Chevron
            Icon(
                Icons.Default.ChevronRight,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}

/*
 * 鏡
 * h(x) >= 0. Always.
 */
