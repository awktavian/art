/**
 * Kagami Composer Bar — Material 3 Command Input
 *
 * Bottom-anchored input with slash commands and @ mentions.
 * Follows Material Design 3 patterns with delightful microanimations.
 *
 * Colony: Forge (e2) — Implementation
 */

package com.kagami.android.ui.components

import com.kagami.android.services.KagamiApiService
import android.view.HapticFeedbackConstants
import androidx.compose.animation.*
import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.kagami.android.services.CommandRegistry
import com.kagami.android.services.CommandSuggestion
import com.kagami.android.ui.LocalAccessibilityConfig
import com.kagami.android.ui.MinTouchTargetSize
import com.kagami.android.ui.theme.*
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

@Composable
fun ComposerBar(
    modifier: Modifier = Modifier
) {
    var input by remember { mutableStateOf("") }
    var suggestions by remember { mutableStateOf<List<CommandSuggestion>>(emptyList()) }
    var selectedIndex by remember { mutableIntStateOf(-1) }
    var statusMessage by remember { mutableStateOf<String?>(null) }
    var showSuccess by remember { mutableStateOf(false) }

    val focusRequester = remember { FocusRequester() }
    val scope = rememberCoroutineScope()
    val view = LocalView.current

    // Update suggestions when input changes
    LaunchedEffect(input) {
        suggestions = when {
            input.startsWith("/") -> CommandRegistry.getSuggestions(input)
            input.contains("@") -> {
                val atIndex = input.lastIndexOf("@")
                val afterAt = input.substring(atIndex + 1)
                val parts = afterAt.split(":", limit = 2)
                val type = parts.firstOrNull()
                val query = if (parts.size > 1) parts[1] else (type ?: "")

                CommandRegistry.getMentionSuggestions(
                    type = if (parts.size > 1) type else null,
                    query = if (parts.size > 1) query else (type ?: "")
                ).map {
                    CommandSuggestion(
                        label = it.label,
                        secondary = it.secondary,
                        icon = it.icon,
                        value = it.value
                    )
                }
            }
            else -> emptyList()
        }
        selectedIndex = if (suggestions.isNotEmpty()) 0 else -1
    }

    Column(modifier = modifier) {
        // Suggestions (above input)
        AnimatedVisibility(
            visible = suggestions.isNotEmpty(),
            enter = fadeIn(kagamiTween(KagamiDurations.fast)) +
                    slideInVertically(kagamiTween(KagamiDurations.normal)) { it },
            exit = fadeOut(kagamiTween(KagamiDurations.fast)) +
                   slideOutVertically(kagamiTween(KagamiDurations.fast)) { it }
        ) {
            SuggestionsPanel(
                suggestions = suggestions,
                selectedIndex = selectedIndex,
                onSelect = { suggestion ->
                    // Haptic
                    view.performHapticFeedback(HapticFeedbackConstants.KEYBOARD_TAP)

                    if (input.startsWith("/")) {
                        input = suggestion.value
                    } else if (input.contains("@")) {
                        val atIndex = input.lastIndexOf("@")
                        input = input.substring(0, atIndex) + suggestion.value + " "
                    }
                    suggestions = emptyList()
                }
            )
        }

        // Input Bar
        Surface(
            color = VoidLight,
            tonalElevation = 3.dp,
            modifier = Modifier.fillMaxWidth()
        ) {
            Column {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = KagamiSpacing.md, vertical = KagamiSpacing.md),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    // Animated Prompt
                    val promptScale by animateFloatAsState(
                        targetValue = if (input.isNotEmpty()) 1.1f else 1f,
                        animationSpec = KagamiSpring.micro,
                        label = "prompt_scale"
                    )

                    Text(
                        text = "›",
                        style = TextStyle(
                            fontSize = 16.sp,
                            fontFamily = androidx.compose.ui.text.font.FontFamily.Monospace,
                            color = Crystal.copy(alpha = if (input.isNotEmpty()) 0.8f else 0.5f)
                        ),
                        modifier = Modifier.scale(promptScale)
                    )

                    Spacer(modifier = Modifier.width(KagamiSpacing.md))

                    // Text Input
                    BasicTextField(
                        value = input,
                        onValueChange = { input = it },
                        modifier = Modifier
                            .weight(1f)
                            .focusRequester(focusRequester),
                        textStyle = TextStyle(
                            fontSize = 15.sp,
                            color = TextPrimary
                        ),
                        singleLine = true,
                        cursorBrush = SolidColor(Crystal),
                        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Send),
                        keyboardActions = KeyboardActions(
                            onSend = {
                                // Haptic
                                view.performHapticFeedback(HapticFeedbackConstants.CONFIRM)

                                scope.launch {
                                    handleSubmit(
                                        input = input,
                                        onSuccess = {
                                            showSuccess = true
                                            scope.launch {
                                                delay(500)
                                                showSuccess = false
                                            }
                                        },
                                        onStatus = { message ->
                                            statusMessage = message
                                            scope.launch {
                                                delay(2000)
                                                statusMessage = null
                                            }
                                        },
                                        onError = {
                                            view.performHapticFeedback(HapticFeedbackConstants.REJECT)
                                        }
                                    )
                                    input = ""
                                    suggestions = emptyList()
                                }
                            }
                        ),
                        decorationBox = { innerTextField ->
                            Box {
                                if (input.isEmpty()) {
                                    Text(
                                        text = "Type / for commands, @ for context...",
                                        style = TextStyle(
                                            fontSize = 15.sp,
                                            color = TextTertiary
                                        )
                                    )
                                }
                                innerTextField()
                            }
                        }
                    )

                    Spacer(modifier = Modifier.width(KagamiSpacing.sm))

                    // Success Checkmark (animated)
                    AnimatedVisibility(
                        visible = showSuccess,
                        enter = scaleIn(KagamiSpring.micro) + fadeIn(),
                        exit = scaleOut(KagamiSpring.micro) + fadeOut()
                    ) {
                        Icon(
                            imageVector = Icons.Default.CheckCircle,
                            contentDescription = "Success",
                            tint = StatusSuccess,
                            modifier = Modifier.size(20.dp)
                        )
                    }

                    Spacer(modifier = Modifier.width(KagamiSpacing.sm))

                    // Voice Button
                    VoiceButton()
                }

                // Status message
                AnimatedVisibility(
                    visible = statusMessage != null,
                    enter = fadeIn(kagamiTween(KagamiDurations.fast)) + expandVertically(),
                    exit = fadeOut(kagamiTween(KagamiDurations.fast)) + shrinkVertically()
                ) {
                    statusMessage?.let { message ->
                        Text(
                            text = message,
                            style = MaterialTheme.typography.bodySmall,
                            color = TextSecondary,
                            modifier = Modifier
                                .fillMaxWidth()
                                .background(Color.Black.copy(alpha = 0.3f))
                                .padding(horizontal = KagamiSpacing.md, vertical = KagamiSpacing.sm)
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun VoiceButton() {
    var isRecording by remember { mutableStateOf(false) }
    val view = LocalView.current

    // Pulse animation for recording state
    val infiniteTransition = rememberInfiniteTransition(label = "voice_pulse")
    val pulseScale by infiniteTransition.animateFloat(
        initialValue = 1f,
        targetValue = if (isRecording) 1.3f else 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(987, easing = EaseInOutSine),
            repeatMode = RepeatMode.Reverse
        ),
        label = "pulse_scale"
    )

    val interactionSource = remember { MutableInteractionSource() }
    val isPressed by interactionSource.collectIsPressedAsState()
    val buttonScale by animateFloatAsState(
        targetValue = if (isPressed) 0.9f else 1f,
        animationSpec = KagamiSpring.micro,
        label = "button_scale"
    )

    Box(contentAlignment = Alignment.Center) {
        // Pulse ring when recording
        if (isRecording) {
            Box(
                modifier = Modifier
                    .size(36.dp)
                    .scale(pulseScale)
                    .clip(CircleShape)
                    .background(Color.Magenta.copy(alpha = 0.3f * (2 - pulseScale)))
            )
        }

        // Button
        IconButton(
            onClick = {
                view.performHapticFeedback(HapticFeedbackConstants.KEYBOARD_TAP)
                isRecording = !isRecording
            },
            interactionSource = interactionSource,
            modifier = Modifier
                .size(32.dp)
                .scale(buttonScale)
                .clip(CircleShape)
                .background(
                    if (isRecording) Color.Magenta.copy(alpha = 0.2f)
                    else Color.White.copy(alpha = 0.05f)
                )
        ) {
            Icon(
                imageVector = Icons.Default.Mic,
                contentDescription = "Voice input",
                tint = if (isRecording) Color.Magenta else TextSecondary,
                modifier = Modifier.size(16.dp)
            )
        }
    }
}

@Composable
private fun SuggestionsPanel(
    suggestions: List<CommandSuggestion>,
    selectedIndex: Int,
    onSelect: (CommandSuggestion) -> Unit
) {
    Surface(
        color = VoidLight,
        shape = RoundedCornerShape(topStart = KagamiRadius.md, topEnd = KagamiRadius.md),
        tonalElevation = 6.dp,
        modifier = Modifier
            .fillMaxWidth()
            .heightIn(max = 200.dp)
    ) {
        LazyColumn {
            itemsIndexed(suggestions) { index, suggestion ->
                SuggestionRow(
                    suggestion = suggestion,
                    isSelected = index == selectedIndex,
                    onClick = { onSelect(suggestion) },
                    animationDelay = staggeredDelay(index)
                )
            }
        }
    }
}

@Composable
private fun SuggestionRow(
    suggestion: CommandSuggestion,
    isSelected: Boolean,
    onClick: () -> Unit,
    animationDelay: Int = 0
) {
    // Entrance animation
    var visible by remember { mutableStateOf(false) }
    LaunchedEffect(Unit) {
        delay(animationDelay.toLong())
        visible = true
    }

    val offsetY by animateFloatAsState(
        targetValue = if (visible) 0f else 8f,
        animationSpec = kagamiTween(KagamiDurations.normal, delayMillis = animationDelay),
        label = "row_offset"
    )

    val alpha by animateFloatAsState(
        targetValue = if (visible) 1f else 0f,
        animationSpec = kagamiTween(KagamiDurations.normal, delayMillis = animationDelay),
        label = "row_alpha"
    )

    // Press effect
    val interactionSource = remember { MutableInteractionSource() }
    val isPressed by interactionSource.collectIsPressedAsState()
    val scale by animateFloatAsState(
        targetValue = if (isPressed) 0.98f else 1f,
        animationSpec = KagamiSpring.micro,
        label = "row_scale"
    )

    val alphaValue = alpha  // Capture for lambda
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .scale(scale)
            .offset(y = offsetY.dp)
            .graphicsLayer { this.alpha = alphaValue }
            .clickable(
                interactionSource = interactionSource,
                indication = null,
                onClick = onClick
            )
            .background(if (isSelected) Color.White.copy(alpha = 0.08f) else Color.Transparent)
            .padding(horizontal = KagamiSpacing.md, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        // Icon
        Box(
            modifier = Modifier.width(24.dp),
            contentAlignment = Alignment.Center
        ) {
            Text(
                text = suggestion.icon,
                fontSize = 14.sp,
                color = TextSecondary
            )
        }

        Spacer(modifier = Modifier.width(KagamiSpacing.md))

        // Content
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = suggestion.label,
                style = MaterialTheme.typography.bodyMedium,
                color = TextPrimary
            )
            suggestion.secondary?.let { secondary ->
                Text(
                    text = secondary,
                    style = MaterialTheme.typography.bodySmall,
                    color = TextSecondary,
                    maxLines = 1
                )
            }
        }
    }
}

private suspend fun handleSubmit(
    input: String,
    onSuccess: () -> Unit,
    onStatus: (String) -> Unit,
    onError: () -> Unit
) {
    if (input.isBlank()) return

    if (input.startsWith("/")) {
        val apiService = KagamiApiService.getInstance()
        if (apiService == null) {
            onError()
            onStatus("Not connected")
            return
        }
        val result = CommandRegistry.executeSlashCommand(input, apiService)
        if (result.success) {
            onSuccess()
            onStatus(result.message ?: "✓ Done")
        } else {
            onError()
            onStatus(result.message ?: "Error")
        }
    } else {
        onStatus("Processing...")
    }
}
