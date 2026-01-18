package com.kagami.android.hub

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import javax.inject.Inject

/**
 * 鏡 Hub Screen — Discover and control Kagami Hub
 *
 * Colony: Nexus (e4) — Integration
 *
 * Features:
 * - Hub discovery via mDNS
 * - Status monitoring
 * - Configuration
 * - LED ring control
 * - Voice proxy
 */

// ═══════════════════════════════════════════════════════════════════════════
// ViewModel
// ═══════════════════════════════════════════════════════════════════════════

@HiltViewModel
class HubViewModel @Inject constructor(
    private val hubManager: HubManager
) : ViewModel() {

    val discoveredHubs = hubManager.discoveredHubs
        .stateIn(viewModelScope, SharingStarted.Eagerly, emptyList())

    val connectedHub = hubManager.connectedHub
        .stateIn(viewModelScope, SharingStarted.Eagerly, null)

    val hubStatus = hubManager.hubStatus
        .stateIn(viewModelScope, SharingStarted.Eagerly, null)

    val hubConfig = hubManager.hubConfig
        .stateIn(viewModelScope, SharingStarted.Eagerly, null)

    val isDiscovering = hubManager.isDiscovering
        .stateIn(viewModelScope, SharingStarted.Eagerly, false)

    val isConnecting = hubManager.isConnecting
        .stateIn(viewModelScope, SharingStarted.Eagerly, false)

    val error = hubManager.error
        .stateIn(viewModelScope, SharingStarted.Eagerly, null)

    init {
        // Try to connect to last hub on start
        viewModelScope.launch {
            hubManager.connectToLastHub()
        }
    }

    fun startDiscovery() {
        hubManager.startDiscovery()
    }

    fun stopDiscovery() {
        hubManager.stopDiscovery()
    }

    fun connect(hub: HubDevice) {
        viewModelScope.launch {
            hubManager.connect(hub)
        }
    }

    fun disconnect() {
        hubManager.disconnect()
    }

    fun controlLED(pattern: String, colony: Int? = null, brightness: Float? = null) {
        viewModelScope.launch {
            hubManager.controlLED(pattern, colony, brightness)
        }
    }

    fun testLED() {
        viewModelScope.launch {
            hubManager.testLED()
        }
    }

    fun triggerListen() {
        viewModelScope.launch {
            hubManager.triggerListen()
        }
    }

    fun executeCommand(command: String) {
        viewModelScope.launch {
            hubManager.executeCommand(command)
        }
    }

    fun updateConfig(config: HubConfig) {
        viewModelScope.launch {
            hubManager.updateConfig(config)
        }
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// Main Screen
// ═══════════════════════════════════════════════════════════════════════════

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HubScreen(
    viewModel: HubViewModel = hiltViewModel()
) {
    val connectedHub by viewModel.connectedHub.collectAsState()
    var showSettings by remember { mutableStateOf(false) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Kagami Hub") },
                actions = {
                    if (connectedHub != null) {
                        IconButton(onClick = { showSettings = true }) {
                            Icon(Icons.Default.Settings, "Settings")
                        }
                    }
                }
            )
        }
    ) { padding ->
        Box(modifier = Modifier.padding(padding)) {
            if (connectedHub != null) {
                ConnectedHubContent(viewModel)
            } else {
                HubDiscoveryContent(viewModel)
            }
        }
    }

    if (showSettings) {
        HubSettingsDialog(
            viewModel = viewModel,
            onDismiss = { showSettings = false }
        )
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// Discovery Content
// ═══════════════════════════════════════════════════════════════════════════

@Composable
fun HubDiscoveryContent(viewModel: HubViewModel) {
    val discoveredHubs by viewModel.discoveredHubs.collectAsState()
    val isDiscovering by viewModel.isDiscovering.collectAsState()
    val isConnecting by viewModel.isConnecting.collectAsState()
    val error by viewModel.error.collectAsState()

    var showManualEntry by remember { mutableStateOf(false) }

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        // Scan button
        item {
            OutlinedCard(
                onClick = {
                    if (isDiscovering) viewModel.stopDiscovery()
                    else viewModel.startDiscovery()
                },
                modifier = Modifier.fillMaxWidth()
            ) {
                Row(
                    modifier = Modifier.padding(16.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    if (isDiscovering) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(24.dp),
                            strokeWidth = 2.dp
                        )
                    } else {
                        Icon(
                            Icons.Default.Search,
                            contentDescription = null,
                            tint = MaterialTheme.colorScheme.primary
                        )
                    }
                    Spacer(Modifier.width(12.dp))
                    Text(
                        if (isDiscovering) "Searching..." else "Scan for Hubs",
                        style = MaterialTheme.typography.bodyLarge
                    )
                }
            }
        }

        // Discovered hubs
        if (discoveredHubs.isNotEmpty()) {
            item {
                Text(
                    "Discovered Hubs",
                    style = MaterialTheme.typography.titleMedium,
                    modifier = Modifier.padding(top = 8.dp)
                )
            }

            items(discoveredHubs) { hub ->
                HubCard(
                    hub = hub,
                    isConnecting = isConnecting,
                    onClick = { viewModel.connect(hub) }
                )
            }
        }

        // Manual entry
        item {
            OutlinedCard(
                onClick = { showManualEntry = true },
                modifier = Modifier.fillMaxWidth()
            ) {
                Row(
                    modifier = Modifier.padding(16.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(Icons.Default.Edit, contentDescription = null)
                    Spacer(Modifier.width(12.dp))
                    Text("Enter Address Manually")
                }
            }
        }

        // Error
        error?.let { errorMsg ->
            item {
                Card(
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.errorContainer
                    )
                ) {
                    Text(
                        errorMsg,
                        modifier = Modifier.padding(16.dp),
                        color = MaterialTheme.colorScheme.onErrorContainer
                    )
                }
            }
        }
    }

    if (showManualEntry) {
        ManualEntryDialog(
            onConnect = { host, port ->
                val hub = HubDevice(
                    id = "$host:$port",
                    name = "Manual Hub",
                    location = "Manual",
                    host = host,
                    port = port
                )
                viewModel.connect(hub)
                showManualEntry = false
            },
            onDismiss = { showManualEntry = false }
        )
    }
}

@Composable
fun HubCard(
    hub: HubDevice,
    isConnecting: Boolean,
    onClick: () -> Unit
) {
    Card(
        onClick = onClick,
        enabled = !isConnecting,
        modifier = Modifier.fillMaxWidth()
    ) {
        Row(
            modifier = Modifier.padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Box(
                modifier = Modifier
                    .size(48.dp)
                    .clip(CircleShape)
                    .background(MaterialTheme.colorScheme.primaryContainer),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    Icons.Default.Speaker,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.onPrimaryContainer
                )
            }

            Spacer(Modifier.width(12.dp))

            Column(modifier = Modifier.weight(1f)) {
                Text(
                    hub.name,
                    style = MaterialTheme.typography.titleMedium
                )
                Text(
                    "${hub.host}:${hub.port}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }

            Icon(
                Icons.Default.ChevronRight,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}

@Composable
fun ManualEntryDialog(
    onConnect: (String, Int) -> Unit,
    onDismiss: () -> Unit
) {
    var host by remember { mutableStateOf("") }
    var port by remember { mutableStateOf("8080") }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Enter Hub Address") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedTextField(
                    value = host,
                    onValueChange = { host = it },
                    label = { Text("Host") },
                    placeholder = { Text("192.168.1.100") },
                    singleLine = true
                )
                OutlinedTextField(
                    value = port,
                    onValueChange = { port = it },
                    label = { Text("Port") },
                    singleLine = true
                )
            }
        },
        confirmButton = {
            Button(
                onClick = { onConnect(host, port.toIntOrNull() ?: 8080) },
                enabled = host.isNotBlank()
            ) {
                Text("Connect")
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text("Cancel")
            }
        }
    )
}

// ═══════════════════════════════════════════════════════════════════════════
// Connected Hub Content
// ═══════════════════════════════════════════════════════════════════════════

@Composable
fun ConnectedHubContent(viewModel: HubViewModel) {
    val hubStatus by viewModel.hubStatus.collectAsState()
    val connectedHub by viewModel.connectedHub.collectAsState()

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        // Status card
        item {
            HubStatusCard(hubStatus, connectedHub)
        }

        // Quick actions
        item {
            QuickActionsCard(viewModel)
        }

        // Voice proxy
        item {
            VoiceProxyCard(viewModel)
        }

        // LED control
        item {
            LEDControlCard(viewModel)
        }

        // Disconnect
        item {
            OutlinedButton(
                onClick = { viewModel.disconnect() },
                modifier = Modifier.fillMaxWidth(),
                colors = ButtonDefaults.outlinedButtonColors(
                    contentColor = MaterialTheme.colorScheme.error
                )
            ) {
                Icon(Icons.Default.Close, null)
                Spacer(Modifier.width(8.dp))
                Text("Disconnect")
            }
        }
    }
}

@Composable
fun HubStatusCard(status: HubStatus?, hub: HubDevice?) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp)) {
            // Header
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(
                    modifier = Modifier
                        .size(56.dp)
                        .clip(CircleShape)
                        .background(
                            if (status?.api_connected == true)
                                Color(0xFF4CAF50).copy(alpha = 0.2f)
                            else
                                Color(0xFFFF9800).copy(alpha = 0.2f)
                        ),
                    contentAlignment = Alignment.Center
                ) {
                    Icon(
                        Icons.Default.Speaker,
                        contentDescription = null,
                        tint = if (status?.api_connected == true)
                            Color(0xFF4CAF50) else Color(0xFFFF9800),
                        modifier = Modifier.size(32.dp)
                    )
                }

                Spacer(Modifier.width(12.dp))

                Column {
                    Text(
                        status?.name ?: hub?.name ?: "Hub",
                        style = MaterialTheme.typography.titleLarge
                    )
                    Text(
                        status?.location ?: "Unknown",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    status?.version?.let {
                        Text(
                            "v$it",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }
            }

            Spacer(Modifier.height(16.dp))
            Divider()
            Spacer(Modifier.height(16.dp))

            // Status indicators
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceEvenly
            ) {
                StatusIndicator(
                    icon = Icons.Default.Wifi,
                    label = "API",
                    isActive = status?.api_connected == true
                )
                StatusIndicator(
                    icon = Icons.Default.Hearing,
                    label = "Listening",
                    isActive = status?.is_listening == true
                )
                status?.safety_score?.let { score ->
                    StatusIndicator(
                        icon = Icons.Default.Shield,
                        label = "${(score * 100).toInt()}%",
                        isActive = score >= 0.3
                    )
                }
                status?.current_colony?.let { colony ->
                    StatusIndicator(
                        icon = Icons.Default.Hub,
                        label = colony.replaceFirstChar { it.uppercase() },
                        isActive = true
                    )
                }
            }

            // Uptime
            status?.uptime_seconds?.let { uptime ->
                Spacer(Modifier.height(12.dp))
                Text(
                    "Uptime: ${formatUptime(uptime)}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.align(Alignment.CenterHorizontally)
                )
            }
        }
    }
}

@Composable
fun StatusIndicator(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    label: String,
    isActive: Boolean
) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Icon(
            icon,
            contentDescription = null,
            tint = if (isActive) Color(0xFF4CAF50)
                   else MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.size(24.dp)
        )
        Spacer(Modifier.height(4.dp))
        Text(
            label,
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
    }
}

@Composable
fun QuickActionsCard(viewModel: HubViewModel) {
    val actions = listOf(
        Triple(Icons.Default.Movie, "Movie", "movie mode"),
        Triple(Icons.Default.NightShelter, "Goodnight", "goodnight"),
        Triple(Icons.Default.Home, "Welcome", "welcome home"),
        Triple(Icons.Default.LightMode, "Lights On", "turn on all lights"),
    )

    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(
                "Quick Commands",
                style = MaterialTheme.typography.titleMedium
            )
            Spacer(Modifier.height(12.dp))

            LazyRow(
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                items(actions) { (icon, label, command) ->
                    FilledTonalButton(
                        onClick = { viewModel.executeCommand(command) },
                        contentPadding = PaddingValues(horizontal = 16.dp, vertical = 12.dp)
                    ) {
                        Icon(icon, null, modifier = Modifier.size(20.dp))
                        Spacer(Modifier.width(8.dp))
                        Text(label)
                    }
                }
            }
        }
    }
}

@Composable
fun VoiceProxyCard(viewModel: HubViewModel) {
    var isRecording by remember { mutableStateOf(false) }
    val interactionSource = remember { androidx.compose.foundation.interaction.MutableInteractionSource() }
    val isPressed by interactionSource.collectIsPressedAsState()

    // Start recording when pressed, stop when released
    LaunchedEffect(isPressed) {
        if (isPressed && !isRecording) {
            isRecording = true
            viewModel.triggerListen()
        } else if (!isPressed && isRecording) {
            isRecording = false
            // Voice command is sent when button is released
        }
    }

    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    "Voice Proxy",
                    style = MaterialTheme.typography.titleMedium
                )
                Text(
                    "Use phone as Hub's ears",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }

            Spacer(Modifier.height(12.dp))

            Button(
                onClick = { /* Handled by press gesture */ },
                interactionSource = interactionSource,
                modifier = Modifier.fillMaxWidth(),
                colors = ButtonDefaults.buttonColors(
                    containerColor = if (isRecording)
                        MaterialTheme.colorScheme.error
                    else MaterialTheme.colorScheme.primary
                )
            ) {
                Icon(
                    if (isRecording) Icons.Default.GraphicEq else Icons.Default.Mic,
                    contentDescription = if (isRecording) "Recording in progress" else "Press and hold to speak"
                )
                Spacer(Modifier.width(8.dp))
                Text(if (isRecording) "Recording..." else "Hold to Speak")
            }

            // Hint text
            Text(
                text = "Press and hold to record your voice command",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.6f),
                modifier = Modifier.padding(top = 4.dp)
            )
        }
    }
}

@Composable
fun LEDControlCard(viewModel: HubViewModel) {
    val hubStatus by viewModel.hubStatus.collectAsState()
    var brightness by remember { mutableStateOf(hubStatus?.led_brightness ?: 0.5f) }

    val patterns = listOf(
        "idle" to Icons.Default.Circle,
        "listening" to Icons.Default.Hearing,
        "thinking" to Icons.Default.Psychology,
        "speaking" to Icons.Default.GraphicEq,
        "error" to Icons.Default.Warning,
    )

    val colonyColors = listOf(
        Color(0xFFFF9800), // Spark - Orange
        Color(0xFFF44336), // Forge - Red
        Color(0xFF2196F3), // Flow - Blue
        Color(0xFF9C27B0), // Nexus - Purple
        Color(0xFFFFEB3B), // Beacon - Yellow
        Color(0xFF4CAF50), // Grove - Green
        Color(0xFF00BCD4), // Crystal - Cyan
    )

    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    "LED Ring",
                    style = MaterialTheme.typography.titleMedium
                )
                TextButton(onClick = { viewModel.testLED() }) {
                    Text("Test")
                }
            }

            Spacer(Modifier.height(8.dp))

            // Pattern buttons
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceEvenly
            ) {
                patterns.forEach { (name, icon) ->
                    IconButton(
                        onClick = { viewModel.controlLED(name) }
                    ) {
                        Icon(icon, name)
                    }
                }
            }

            Spacer(Modifier.height(12.dp))

            // Brightness
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(
                    Icons.Default.BrightnessLow,
                    null,
                    tint = MaterialTheme.colorScheme.onSurfaceVariant
                )
                Slider(
                    value = brightness,
                    onValueChange = { brightness = it },
                    onValueChangeFinished = {
                        viewModel.controlLED("idle", brightness = brightness)
                    },
                    modifier = Modifier.weight(1f)
                )
                Icon(
                    Icons.Default.BrightnessHigh,
                    null,
                    tint = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }

            Spacer(Modifier.height(8.dp))

            // Colony colors
            Text(
                "Colony Highlight",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Spacer(Modifier.height(8.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceEvenly
            ) {
                colonyColors.forEachIndexed { index, color ->
                    Box(
                        modifier = Modifier
                            .size(32.dp)
                            .clip(CircleShape)
                            .background(color)
                            .clickable { viewModel.controlLED("colony", colony = index) }
                    )
                }
            }
        }
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// Settings Dialog
// ═══════════════════════════════════════════════════════════════════════════

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HubSettingsDialog(
    viewModel: HubViewModel,
    onDismiss: () -> Unit
) {
    val config by viewModel.hubConfig.collectAsState()

    var name by remember(config) { mutableStateOf(config?.name ?: "") }
    var location by remember(config) { mutableStateOf(config?.location ?: "") }
    var apiUrl by remember(config) { mutableStateOf(config?.api_url ?: "") }
    var wakeWord by remember(config) { mutableStateOf(config?.wake_word ?: "") }
    var ledEnabled by remember(config) { mutableStateOf(config?.led_enabled ?: true) }
    var ttsVolume by remember(config) { mutableStateOf(config?.tts_volume ?: 0.5f) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Hub Settings") },
        text = {
            Column(
                modifier = Modifier.verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                OutlinedTextField(
                    value = name,
                    onValueChange = { name = it },
                    label = { Text("Name") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )

                OutlinedTextField(
                    value = location,
                    onValueChange = { location = it },
                    label = { Text("Location") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )

                OutlinedTextField(
                    value = apiUrl,
                    onValueChange = { apiUrl = it },
                    label = { Text("API URL") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )

                OutlinedTextField(
                    value = wakeWord,
                    onValueChange = { wakeWord = it },
                    label = { Text("Wake Word") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text("LED Enabled")
                    Switch(
                        checked = ledEnabled,
                        onCheckedChange = { ledEnabled = it }
                    )
                }

                Text("TTS Volume")
                Slider(
                    value = ttsVolume,
                    onValueChange = { ttsVolume = it }
                )
            }
        },
        confirmButton = {
            Button(
                onClick = {
                    config?.let { currentConfig ->
                        viewModel.updateConfig(
                            currentConfig.copy(
                                name = name,
                                location = location,
                                api_url = apiUrl,
                                wake_word = wakeWord,
                                led_enabled = ledEnabled,
                                tts_volume = ttsVolume
                            )
                        )
                    }
                    onDismiss()
                }
            ) {
                Text("Save")
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text("Cancel")
            }
        }
    )
}

// ═══════════════════════════════════════════════════════════════════════════
// Utilities
// ═══════════════════════════════════════════════════════════════════════════

private fun formatUptime(seconds: Long): String {
    val hours = seconds / 3600
    val minutes = (seconds % 3600) / 60
    return if (hours > 0) "${hours}h ${minutes}m" else "${minutes}m"
}

@Composable
private fun rememberScrollState() = androidx.compose.foundation.rememberScrollState()

/*
 * 鏡
 */
