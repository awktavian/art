/**
 * Kagami Voice Command Screen - Voice Interface for Android
 *
 * Colony: Spark (e1) - Ideation
 *
 * Design Philosophy:
 *   - Hold to record
 *   - Visual feedback during recording
 *   - Instant command execution
 *   - Natural language processing
 *
 * Accessibility (Phase 2):
 * - TalkBack content descriptions for all interactive elements
 * - Minimum 48dp touch targets (record button is 80dp)
 * - Reduced motion support
 * - High contrast mode support
 * - Font scaling support (200%)
 */

package com.kagami.android.ui.screens

import android.Manifest
import android.content.Intent
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.view.HapticFeedbackConstants
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.google.accompanist.permissions.ExperimentalPermissionsApi
import com.google.accompanist.permissions.isGranted
import com.google.accompanist.permissions.rememberPermissionState
import androidx.hilt.navigation.compose.hiltViewModel
import com.kagami.android.ui.LocalAccessibilityConfig
import com.kagami.android.ui.MinTouchTargetSize
import com.kagami.android.ui.buildRecordButtonDescription
import com.kagami.android.ui.components.ModelSelector
import com.kagami.android.ui.components.ModelSelection
import com.kagami.android.ui.components.UserModelKey
import com.kagami.android.ui.minTouchTarget
import com.kagami.android.ui.theme.*
import kotlinx.coroutines.launch

enum class CommandStatus {
    IDLE, LISTENING, PROCESSING, SUCCESS, ERROR
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalPermissionsApi::class)
@Composable
fun VoiceCommandScreen(
    onBack: () -> Unit,
    viewModel: VoiceCommandViewModel = hiltViewModel()
) {
    val context = LocalContext.current
    val view = LocalView.current
    val scope = rememberCoroutineScope()
    val accessibilityConfig = LocalAccessibilityConfig.current

    // Permission
    val micPermission = rememberPermissionState(Manifest.permission.RECORD_AUDIO)

    // State
    var isRecording by remember { mutableStateOf(false) }
    var transcript by remember { mutableStateOf("") }
    var lastCommand by remember { mutableStateOf("") }
    var commandStatus by remember { mutableStateOf(CommandStatus.IDLE) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    var selectedModel by remember { mutableStateOf(ModelSelection.getSelectedModel(context)) }

    // Speech recognizer
    val speechRecognizer = remember { SpeechRecognizer.createSpeechRecognizer(context) }

    DisposableEffect(Unit) {
        speechRecognizer.setRecognitionListener(object : RecognitionListener {
            override fun onReadyForSpeech(params: Bundle?) {
                commandStatus = CommandStatus.LISTENING
            }

            override fun onBeginningOfSpeech() {}
            override fun onRmsChanged(rmsdB: Float) {}
            override fun onBufferReceived(buffer: ByteArray?) {}
            override fun onEndOfSpeech() {}

            override fun onError(error: Int) {
                isRecording = false
                commandStatus = CommandStatus.ERROR
                errorMessage = when (error) {
                    SpeechRecognizer.ERROR_NO_MATCH -> "No speech detected"
                    SpeechRecognizer.ERROR_NETWORK -> "Network error"
                    else -> "Recognition failed"
                }
            }

            override fun onResults(results: Bundle?) {
                val matches = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                val result = matches?.firstOrNull() ?: ""
                transcript = result
                isRecording = false

                if (result.isNotEmpty()) {
                    lastCommand = result
                    commandStatus = CommandStatus.PROCESSING
                    scope.launch {
                        val success = viewModel.processVoiceCommand(result, selectedModel)
                        commandStatus = if (success) CommandStatus.SUCCESS else CommandStatus.ERROR
                        if (!success) errorMessage = "Unknown command"
                    }
                } else {
                    commandStatus = CommandStatus.IDLE
                }
            }

            override fun onPartialResults(partialResults: Bundle?) {
                val matches = partialResults?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                transcript = matches?.firstOrNull() ?: ""
            }

            override fun onEvent(eventType: Int, params: Bundle?) {}
        })

        onDispose {
            speechRecognizer.destroy()
        }
    }

    fun startRecording() {
        if (!micPermission.status.isGranted) {
            micPermission.launchPermissionRequest()
            return
        }

        view.performHapticFeedback(HapticFeedbackConstants.LONG_PRESS)
        isRecording = true
        transcript = ""
        commandStatus = CommandStatus.LISTENING

        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, "en-US")
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
        }
        speechRecognizer.startListening(intent)
    }

    fun stopRecording() {
        view.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
        speechRecognizer.stopListening()
        isRecording = false
    }

    // Reset status after delay
    LaunchedEffect(commandStatus) {
        if (commandStatus == CommandStatus.SUCCESS || commandStatus == CommandStatus.ERROR) {
            kotlinx.coroutines.delay(2000)
            commandStatus = CommandStatus.IDLE
            transcript = ""
            errorMessage = null
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        "Voice",
                        modifier = Modifier.semantics { heading() }
                    )
                },
                navigationIcon = {
                    IconButton(
                        onClick = {
                            view.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
                            onBack()
                        },
                        modifier = Modifier
                            .minTouchTarget()
                            .semantics {
                                contentDescription = "Go back"
                                role = Role.Button
                            }
                    ) {
                        Icon(
                            Icons.Default.ArrowBack,
                            contentDescription = null // Handled by parent semantics
                        )
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = Void)
            )
        },
        containerColor = Void
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            // Model selector
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.End
            ) {
                ModelSelector(
                    selectedModel = selectedModel,
                    onModelSelected = { model ->
                        selectedModel = model
                        ModelSelection.setSelectedModel(context, model)
                    }
                )
            }

            Spacer(modifier = Modifier.height(16.dp))

            // Status indicator
            StatusIndicator(
                commandStatus = commandStatus,
                isRecording = isRecording
            )

            Spacer(modifier = Modifier.height(24.dp))

            // Transcript display
            TranscriptDisplay(
                transcript = transcript,
                isRecording = isRecording,
                errorMessage = errorMessage
            )

            Spacer(modifier = Modifier.height(32.dp))

            // Record button
            RecordButton(
                isRecording = isRecording,
                onStartRecording = { startRecording() },
                onStopRecording = { stopRecording() }
            )

            Spacer(modifier = Modifier.height(16.dp))

            // Last command
            if (lastCommand.isNotEmpty()) {
                Column(
                    horizontalAlignment = Alignment.CenterHorizontally,
                    modifier = Modifier.semantics(mergeDescendants = true) {
                        contentDescription = "Last command was: $lastCommand"
                    }
                ) {
                    Text(
                        text = "Last command",
                        style = MaterialTheme.typography.labelSmall,
                        color = Color.White.copy(alpha = 0.65f),
                        modifier = Modifier.clearAndSetSemantics { }
                    )
                    Text(
                        text = lastCommand,
                        style = MaterialTheme.typography.bodySmall,
                        color = Crystal,
                        modifier = Modifier.clearAndSetSemantics { }
                    )
                }
            }

            Spacer(modifier = Modifier.weight(1f))

            // Command hints
            CommandHints()
        }
    }
}

@Composable
fun StatusIndicator(commandStatus: CommandStatus, isRecording: Boolean) {
    val accessibilityConfig = LocalAccessibilityConfig.current
    val animationDuration = if (accessibilityConfig.isReducedMotionEnabled) 0 else 300

    val statusColor by animateColorAsState(
        targetValue = when (commandStatus) {
            CommandStatus.IDLE -> Crystal
            CommandStatus.LISTENING -> Spark
            CommandStatus.PROCESSING -> Beacon
            CommandStatus.SUCCESS -> SafetyOk
            CommandStatus.ERROR -> SafetyViolation
        },
        animationSpec = tween(animationDuration),
        label = "statusColor"
    )

    val scale by animateFloatAsState(
        targetValue = if (isRecording && !accessibilityConfig.isReducedMotionEnabled) 1.2f else 1f,
        animationSpec = spring(dampingRatio = 0.5f),
        label = "statusScale"
    )

    val statusIcon = when (commandStatus) {
        CommandStatus.IDLE -> Icons.Default.Mic
        CommandStatus.LISTENING -> Icons.Default.Mic
        CommandStatus.PROCESSING -> Icons.Filled.Refresh
        CommandStatus.SUCCESS -> Icons.Filled.Check
        CommandStatus.ERROR -> Icons.Filled.Warning
    }

    val statusText = when (commandStatus) {
        CommandStatus.IDLE -> "Tap and hold to speak"
        CommandStatus.LISTENING -> "Listening..."
        CommandStatus.PROCESSING -> "Processing..."
        CommandStatus.SUCCESS -> "Command executed"
        CommandStatus.ERROR -> "Command failed"
    }

    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        modifier = Modifier.semantics(mergeDescendants = true) {
            contentDescription = "Status: $statusText"
            stateDescription = statusText
        }
    ) {
        Box(
            modifier = Modifier
                .size(100.dp)
                .scale(scale)
                .clip(CircleShape)
                .background(statusColor.copy(alpha = 0.2f)),
            contentAlignment = Alignment.Center
        ) {
            Icon(
                imageVector = statusIcon,
                contentDescription = null, // Handled by parent semantics
                tint = statusColor,
                modifier = Modifier.size(36.dp)
            )
        }

        Spacer(modifier = Modifier.height(12.dp))

        Text(
            text = statusText,
            style = MaterialTheme.typography.bodySmall,
            color = Color.White.copy(alpha = 0.6f),
            modifier = Modifier.clearAndSetSemantics { }
        )
    }
}

@Composable
fun TranscriptDisplay(
    transcript: String,
    isRecording: Boolean,
    errorMessage: String?
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .semantics {
                contentDescription = when {
                    errorMessage != null -> "Error: $errorMessage"
                    transcript.isEmpty() && !isRecording -> "Ready for voice command. Say a command like Movie mode or Lights to 50"
                    transcript.isEmpty() -> "Listening for speech"
                    else -> "You said: $transcript"
                }
            },
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = VoidLight)
    ) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .padding(20.dp),
            contentAlignment = Alignment.Center
        ) {
            when {
                errorMessage != null -> {
                    Text(
                        text = errorMessage,
                        style = MaterialTheme.typography.bodyMedium,
                        color = SafetyViolation,
                        textAlign = TextAlign.Center
                    )
                }
                transcript.isEmpty() && !isRecording -> {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text(
                            text = "Say a command like:",
                            style = MaterialTheme.typography.labelSmall,
                            color = Color.White.copy(alpha = 0.65f)
                        )
                        Text(
                            text = "\"Movie mode\" or \"Lights to 50\"",
                            style = MaterialTheme.typography.bodyMedium,
                            color = Color.White.copy(alpha = 0.8f)
                        )
                    }
                }
                else -> {
                    Text(
                        text = transcript.ifEmpty { "..." },
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Medium,
                        color = Color.White,
                        textAlign = TextAlign.Center
                    )
                }
            }
        }
    }
}

@Composable
fun RecordButton(
    isRecording: Boolean,
    onStartRecording: () -> Unit,
    onStopRecording: () -> Unit
) {
    val accessibilityConfig = LocalAccessibilityConfig.current

    val scale by animateFloatAsState(
        targetValue = if (isRecording && !accessibilityConfig.isReducedMotionEnabled) 1.15f else 1f,
        animationSpec = spring(dampingRatio = 0.5f),
        label = "buttonScale"
    )

    val buttonColor by animateColorAsState(
        targetValue = if (isRecording) Spark else Crystal,
        animationSpec = tween(if (accessibilityConfig.isReducedMotionEnabled) 0 else 233),
        label = "buttonColor"
    )

    val buttonDescription = buildRecordButtonDescription(isRecording)

    Box(
        modifier = Modifier
            .size(80.dp) // Already larger than 48dp minimum
            .scale(scale)
            .clip(CircleShape)
            .background(buttonColor)
            .pointerInput(Unit) {
                detectTapGestures(
                    onPress = {
                        onStartRecording()
                        tryAwaitRelease()
                        onStopRecording()
                    }
                )
            }
            .semantics {
                contentDescription = buttonDescription
                role = Role.Button
                stateDescription = if (isRecording) "Recording" else "Not recording"
            },
        contentAlignment = Alignment.Center
    ) {
        Icon(
            imageVector = if (isRecording) Icons.Default.Stop else Icons.Default.Mic,
            contentDescription = null, // Handled by parent semantics
            tint = Color.White,
            modifier = Modifier.size(32.dp)
        )
    }
}

@Composable
fun CommandHints() {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .semantics(mergeDescendants = true) {
                contentDescription = "Voice command examples: Movie mode, Goodnight, Lights on, Fireplace"
            },
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = VoidLight.copy(alpha = 0.5f))
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(
                text = "Try saying:",
                style = MaterialTheme.typography.labelSmall,
                color = Color.White.copy(alpha = 0.65f),
                modifier = Modifier.clearAndSetSemantics { }
            )

            Spacer(modifier = Modifier.height(8.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceEvenly
            ) {
                CommandHintChip(Icons.Filled.PlayCircle, "Movie mode")
                CommandHintChip(Icons.Filled.DarkMode, "Goodnight")
            }

            Spacer(modifier = Modifier.height(8.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceEvenly
            ) {
                CommandHintChip(Icons.Filled.LightMode, "Lights on")
                CommandHintChip(Icons.Filled.LocalFireDepartment, "Fireplace")
            }
        }
    }
}

@Composable
fun CommandHintChip(icon: androidx.compose.ui.graphics.vector.ImageVector, text: String) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = Modifier
            .background(VoidLight, RoundedCornerShape(8.dp))
            .padding(horizontal = 12.dp, vertical = 6.dp)
            .defaultMinSize(minHeight = MinTouchTargetSize)
            .clearAndSetSemantics { } // Parent has merged description
    ) {
        Icon(
            imageVector = icon,
            contentDescription = null,
            tint = Color.White.copy(alpha = 0.6f),
            modifier = Modifier.size(14.dp)
        )
        Spacer(modifier = Modifier.width(6.dp))
        Text(
            text = text,
            style = MaterialTheme.typography.labelSmall,
            color = Color.White.copy(alpha = 0.7f)
        )
    }
}

/*
 * Mirror
 * h(x) >= 0. Always.
 */
