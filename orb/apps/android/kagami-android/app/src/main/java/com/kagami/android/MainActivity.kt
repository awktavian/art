/**
 * Kagami Android - Main Activity
 *
 * Colony: Nexus (e4) - Integration
 */

package com.kagami.android

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import com.google.firebase.analytics.FirebaseAnalytics
import com.kagami.android.ui.KagamiNavHost
import com.kagami.android.ui.theme.KagamiTheme
import dagger.hilt.android.AndroidEntryPoint
import javax.inject.Inject

@AndroidEntryPoint
class MainActivity : ComponentActivity() {

    @Inject
    lateinit var analytics: FirebaseAnalytics

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        // Handle deep links
        handleDeepLink(intent)

        setContent {
            KagamiTheme(dynamicColor = true) {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    KagamiNavHost()
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleDeepLink(intent)
    }

    private fun handleDeepLink(intent: Intent?) {
        intent?.data?.let { uri ->
            when (uri.host) {
                "room" -> {
                    val roomId = uri.lastPathSegment
                    analytics.logEvent("deep_link_room", Bundle().apply {
                        putString("room_id", roomId)
                    })
                    // Navigation will be handled by NavHost
                }
                "scene" -> {
                    val sceneId = uri.lastPathSegment
                    analytics.logEvent("deep_link_scene", Bundle().apply {
                        putString("scene_id", sceneId)
                    })
                }
            }
        }
    }
}

/*
 * Mirror
 * h(x) >= 0. Always.
 */
