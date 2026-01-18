/**
 * Kagami Voice Command ViewModel - Proper DI replacing KagamiApp.instance
 *
 * Colony: Spark (e1) - Ideation
 *
 * Follows Clean Architecture:
 * - Injected dependencies via Hilt
 * - Clean separation of API access
 */

package com.kagami.android.ui.screens

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.kagami.android.services.KagamiApiService
import com.kagami.android.ui.components.UserModelKey
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class VoiceCommandViewModel @Inject constructor(
    private val apiService: KagamiApiService
) : ViewModel() {

    /**
     * Process voice command and execute appropriate action.
     * Returns true if command was recognized and executed.
     */
    suspend fun processVoiceCommand(
        text: String,
        model: UserModelKey = UserModelKey.AUTO
    ): Boolean {
        val lower = text.lowercase()

        // For complex commands, use the NL endpoint with model preference
        // Simple commands bypass LLM for speed

        // Scenes
        if (lower.contains("movie")) {
            apiService.executeScene("movie_mode")
            return true
        }

        if (lower.contains("good night") || lower.contains("goodnight")) {
            apiService.executeScene("goodnight")
            return true
        }

        if (lower.contains("welcome") || lower.contains("home")) {
            apiService.executeScene("welcome_home")
            return true
        }

        // Fireplace
        if (lower.contains("fire") || lower.contains("fireplace")) {
            apiService.toggleFireplace()
            return true
        }

        // Lights
        if (lower.contains("light")) {
            when {
                lower.contains("off") -> apiService.setLights(0)
                lower.contains("dim") -> apiService.setLights(30)
                else -> {
                    val level = extractNumber(lower) ?: 100
                    apiService.setLights(level)
                }
            }
            return true
        }

        // TV
        if (lower.contains("tv")) {
            when {
                lower.contains("down") || lower.contains("lower") -> apiService.tvControl("lower")
                lower.contains("up") || lower.contains("raise") -> apiService.tvControl("raise")
            }
            return true
        }

        // Shades
        if (lower.contains("shade") || lower.contains("blind")) {
            when {
                lower.contains("open") -> apiService.controlShades("open")
                lower.contains("close") -> apiService.controlShades("close")
            }
            return true
        }

        return false
    }

    private fun extractNumber(text: String): Int? {
        val regex = Regex("\\d+")
        return regex.find(text)?.value?.toIntOrNull()?.coerceIn(0, 100)
    }
}

/*
 * Mirror
 * h(x) >= 0. Always.
 */
