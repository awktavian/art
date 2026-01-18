/**
 * ModelSelector.kt — Mode & Model Selection for Android
 *
 * Mode selector (Ask/Plan/Agent) with brand colors.
 * Model selector (text-only, no icons).
 *
 * Created: December 30, 2025
 */

package com.kagami.android.ui.components

import android.content.Context
import androidx.compose.animation.*
import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.kagami.android.ui.MinTouchTargetSize
import com.kagami.android.ui.theme.*

// =============================================================================
// MODE DEFINITIONS
// =============================================================================

enum class KagamiMode(
    val key: String,
    val displayName: String,
    val description: String,
    val colonyColor: Color
) {
    ASK("ask", "Ask", "Get answers", Grove),
    PLAN("plan", "Plan", "Think it through", Beacon),
    AGENT("agent", "Agent", "Make it happen", Forge);

    companion object {
        fun fromKey(key: String): KagamiMode =
            entries.find { it.key == key } ?: ASK
    }
}

// =============================================================================
// MODEL DEFINITIONS (Text Only)
// =============================================================================

enum class UserModelKey(
    val key: String,
    val displayName: String
) {
    AUTO("auto", "Auto"),
    CLAUDE("claude", "Claude"),
    GPT4O("gpt4o", "GPT-4o"),
    DEEPSEEK("deepseek", "DeepSeek"),
    GEMINI("gemini", "Gemini"),
    LOCAL("local", "Local");

    companion object {
        fun fromKey(key: String): UserModelKey =
            entries.find { it.key == key } ?: AUTO
    }
}

// =============================================================================
// MODE SELECTOR COMPOSABLE
// =============================================================================

@Composable
fun ModeSelector(
    selectedMode: KagamiMode,
    onModeSelected: (KagamiMode) -> Unit,
    modifier: Modifier = Modifier
) {
    Row(
        horizontalArrangement = Arrangement.spacedBy(2.dp),
        modifier = modifier
            .clip(RoundedCornerShape(20.dp))
            .background(Color.White.copy(alpha = 0.03f))
            .border(1.dp, Color.White.copy(alpha = 0.06f), RoundedCornerShape(20.dp))
            .padding(2.dp)
    ) {
        KagamiMode.entries.forEach { mode ->
            ModePill(
                mode = mode,
                isSelected = mode == selectedMode,
                onClick = { onModeSelected(mode) }
            )
        }
    }
}

@Composable
private fun ModePill(
    mode: KagamiMode,
    isSelected: Boolean,
    onClick: () -> Unit
) {
    Surface(
        onClick = onClick,
        shape = RoundedCornerShape(16.dp),
        color = if (isSelected) mode.colonyColor else Color.Transparent
    ) {
        Text(
            text = mode.displayName,
            color = if (isSelected) Void else Color.White.copy(alpha = 0.6f),
            fontSize = 11.sp,
            fontWeight = if (isSelected) FontWeight.SemiBold else FontWeight.Medium,
            fontFamily = FontFamily.Monospace,
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp)
        )
    }
}

// =============================================================================
// MODEL SELECTOR COMPOSABLE (Text Only)
// =============================================================================

@Composable
fun ModelSelector(
    selectedModel: UserModelKey,
    onModelSelected: (UserModelKey) -> Unit,
    modifier: Modifier = Modifier
) {
    var isExpanded by remember { mutableStateOf(false) }

    Box(modifier = modifier) {
        // Trigger
        Surface(
            onClick = { isExpanded = true },
            shape = RoundedCornerShape(8.dp),
            color = Color.White.copy(alpha = 0.03f),
            border = androidx.compose.foundation.BorderStroke(
                1.dp,
                Color.White.copy(alpha = 0.08f)
            )
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp)
            ) {
                Text(
                    text = "MODEL",
                    color = Color.White.copy(alpha = 0.4f),
                    fontSize = 10.sp,
                    fontWeight = FontWeight.Medium,
                    fontFamily = FontFamily.Monospace
                )
                Spacer(modifier = Modifier.width(6.dp))
                Text(
                    text = selectedModel.displayName,
                    color = Color.White.copy(alpha = 0.8f),
                    fontSize = 11.sp,
                    fontWeight = FontWeight.Medium,
                    fontFamily = FontFamily.Monospace
                )
                Spacer(modifier = Modifier.width(4.dp))
                Icon(
                    imageVector = Icons.Default.KeyboardArrowDown,
                    contentDescription = null,
                    tint = Color.White.copy(alpha = 0.4f),
                    modifier = Modifier.size(14.dp)
                )
            }
        }

        // Dropdown menu
        DropdownMenu(
            expanded = isExpanded,
            onDismissRequest = { isExpanded = false }
        ) {
            UserModelKey.entries.forEach { model ->
                DropdownMenuItem(
                    text = {
                        Text(
                            text = model.displayName,
                            fontFamily = FontFamily.Monospace,
                            fontSize = 12.sp
                        )
                    },
                    onClick = {
                        onModelSelected(model)
                        isExpanded = false
                    },
                    trailingIcon = {
                        if (model == selectedModel) {
                            Icon(
                                imageVector = Icons.Default.Check,
                                contentDescription = "Selected",
                                modifier = Modifier.size(16.dp)
                            )
                        }
                    }
                )
            }
        }
    }
}

// =============================================================================
// COMBINED COMPOSER CONTROLS
// =============================================================================

@Composable
fun ComposerControls(
    selectedMode: KagamiMode,
    onModeSelected: (KagamiMode) -> Unit,
    selectedModel: UserModelKey,
    onModelSelected: (UserModelKey) -> Unit,
    modifier: Modifier = Modifier
) {
    Row(
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
        modifier = modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 8.dp)
    ) {
        ModeSelector(
            selectedMode = selectedMode,
            onModeSelected = onModeSelected
        )

        ModelSelector(
            selectedModel = selectedModel,
            onModelSelected = onModelSelected
        )
    }
}

// =============================================================================
// SELECTION PERSISTENCE
// =============================================================================

object ComposerSelection {
    private const val PREF_NAME = "kagami_prefs"
    private const val MODE_KEY = "kagami-mode-selection"
    private const val MODEL_KEY = "kagami-model-selection"

    fun getSelectedMode(context: Context): KagamiMode {
        val prefs = context.getSharedPreferences(PREF_NAME, Context.MODE_PRIVATE)
        val key = prefs.getString(MODE_KEY, KagamiMode.ASK.key) ?: KagamiMode.ASK.key
        return KagamiMode.fromKey(key)
    }

    fun setSelectedMode(context: Context, mode: KagamiMode) {
        val prefs = context.getSharedPreferences(PREF_NAME, Context.MODE_PRIVATE)
        prefs.edit().putString(MODE_KEY, mode.key).apply()
    }

    fun getSelectedModel(context: Context): UserModelKey {
        val prefs = context.getSharedPreferences(PREF_NAME, Context.MODE_PRIVATE)
        val key = prefs.getString(MODEL_KEY, UserModelKey.AUTO.key) ?: UserModelKey.AUTO.key
        return UserModelKey.fromKey(key)
    }

    fun setSelectedModel(context: Context, model: UserModelKey) {
        val prefs = context.getSharedPreferences(PREF_NAME, Context.MODE_PRIVATE)
        prefs.edit().putString(MODEL_KEY, model.key).apply()
    }
}

/** Alias for backward compatibility - VoiceCommandScreen references ModelSelection */
typealias ModelSelection = ComposerSelection

// =============================================================================
// COMPOSABLE STATE HELPERS
// =============================================================================

@Composable
fun rememberModeSelection(): MutableState<KagamiMode> {
    val context = LocalContext.current
    return remember {
        mutableStateOf(ComposerSelection.getSelectedMode(context))
    }
}

@Composable
fun rememberModelSelection(): MutableState<UserModelKey> {
    val context = LocalContext.current
    return remember {
        mutableStateOf(ComposerSelection.getSelectedModel(context))
    }
}

// =============================================================================
// PREVIEW
// =============================================================================

@Preview(showBackground = true, backgroundColor = 0xFF0F0F23)
@Composable
fun ComposerControlsPreview() {
    Column(
        modifier = Modifier
            .background(Void)
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(24.dp)
    ) {
        Text("Mode Selector", color = Color.White.copy(alpha = 0.65f), fontSize = 12.sp)
        var selectedMode by remember { mutableStateOf(KagamiMode.ASK) }
        ModeSelector(
            selectedMode = selectedMode,
            onModeSelected = { selectedMode = it }
        )

        Text("Model Selector", color = Color.White.copy(alpha = 0.65f), fontSize = 12.sp)
        var selectedModel by remember { mutableStateOf(UserModelKey.AUTO) }
        ModelSelector(
            selectedModel = selectedModel,
            onModelSelected = { selectedModel = it }
        )

        Text("Combined Controls", color = Color.White.copy(alpha = 0.65f), fontSize = 12.sp)
        ComposerControls(
            selectedMode = KagamiMode.PLAN,
            onModeSelected = {},
            selectedModel = UserModelKey.CLAUDE,
            onModelSelected = {}
        )
    }
}

/*
 * Mode shapes intent. Model shapes response.
 * Typography-first. Color secondary.
 */
