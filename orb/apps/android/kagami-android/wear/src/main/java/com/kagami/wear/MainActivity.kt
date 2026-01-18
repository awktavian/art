package com.kagami.wear

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import com.kagami.wear.presentation.KagamiWearNavigation
import com.kagami.wear.services.KagamiWearApiService
import com.kagami.wear.theme.KagamiWearTheme
import com.kagami.wear.util.HapticFeedback
import dagger.hilt.android.AndroidEntryPoint

/**
 * Main Activity for Kagami Wear OS
 *
 * Colony: Nexus (e4) - Integration
 *
 * Handles:
 * - Standard app launch
 * - Tile quick action intents (scene/action extras)
 * - Complication tap intents
 */
@AndroidEntryPoint
class MainActivity : ComponentActivity() {

    private var pendingScene: String? = null
    private var pendingAction: String? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Handle tile/complication intents
        handleIntent(intent)

        setContent {
            KagamiWearTheme {
                var actionResult by remember { mutableStateOf<ActionResult?>(null) }

                // Execute pending actions from tile
                LaunchedEffect(pendingScene, pendingAction) {
                    pendingScene?.let { scene ->
                        actionResult = executeSceneAction(scene)
                        pendingScene = null
                    }
                    pendingAction?.let { action ->
                        actionResult = executeQuickAction(action)
                        pendingAction = null
                    }
                }

                KagamiWearNavigation(
                    actionResult = actionResult,
                    onActionResultConsumed = { actionResult = null }
                )
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleIntent(intent)
    }

    private fun handleIntent(intent: Intent?) {
        intent?.let {
            // Scene from tile hero action
            it.getStringExtra("scene")?.let { scene ->
                pendingScene = scene
            }

            // Action from tile quick action buttons
            it.getStringExtra("action")?.let { action ->
                pendingAction = action
            }

            // Complication tap
            it.getStringExtra("complication_action")?.let { action ->
                pendingAction = action
            }
        }
    }

    private suspend fun executeSceneAction(sceneId: String): ActionResult {
        return try {
            val success = KagamiWearApiService.executeScene(sceneId)
            if (success) {
                HapticFeedback.success(this)
                ActionResult.Success(getSceneLabel(sceneId))
            } else {
                HapticFeedback.error(this)
                ActionResult.Error("Failed to activate $sceneId")
            }
        } catch (e: Exception) {
            HapticFeedback.error(this)
            ActionResult.Error(e.message ?: "Unknown error")
        }
    }

    private suspend fun executeQuickAction(actionId: String): ActionResult {
        return try {
            val success = when (actionId) {
                "lights_on" -> KagamiWearApiService.setLights(80)
                "lights_off" -> KagamiWearApiService.setLights(0)
                "refresh_status" -> {
                    KagamiWearApiService.fetchHealth()
                    true
                }
                else -> false
            }

            if (success) {
                HapticFeedback.success(this)
                ActionResult.Success(getActionLabel(actionId))
            } else {
                HapticFeedback.error(this)
                ActionResult.Error("Action failed")
            }
        } catch (e: Exception) {
            HapticFeedback.error(this)
            ActionResult.Error(e.message ?: "Unknown error")
        }
    }

    private fun getSceneLabel(sceneId: String): String = when (sceneId) {
        "movie_mode" -> "Movie Mode activated"
        "goodnight" -> "Goodnight scene activated"
        "welcome_home" -> "Welcome Home activated"
        "away" -> "Away mode activated"
        "good_morning" -> "Good Morning activated"
        "focus" -> "Focus mode activated"
        "sleep" -> "Sleep mode activated"
        else -> "Scene activated"
    }

    private fun getActionLabel(actionId: String): String = when (actionId) {
        "lights_on" -> "Lights turned on"
        "lights_off" -> "Lights turned off"
        "refresh_status" -> "Status refreshed"
        else -> "Action completed"
    }
}

sealed class ActionResult {
    data class Success(val message: String) : ActionResult()
    data class Error(val message: String) : ActionResult()
}
