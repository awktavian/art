package com.kagami.wear.presentation

import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.wear.compose.navigation.SwipeDismissableNavHost
import androidx.wear.compose.navigation.composable
import androidx.wear.compose.navigation.rememberSwipeDismissableNavController
import com.kagami.wear.ActionResult

/**
 * Wear OS Navigation
 *
 * Colony: Beacon (e5) - Planning
 *
 * Navigation structure:
 * - Home: Hero action + status
 * - Scenes: All scenes grid
 * - Rooms: Room list
 * - Settings: Connection + preferences
 */
@Composable
fun KagamiWearNavigation(
    actionResult: ActionResult? = null,
    onActionResultConsumed: () -> Unit = {}
) {
    val navController = rememberSwipeDismissableNavController()

    SwipeDismissableNavHost(
        navController = navController,
        startDestination = "home"
    ) {
        composable("home") {
            HomeScreen(
                onNavigateToScenes = { navController.navigate("scenes") },
                onNavigateToRooms = { navController.navigate("rooms") },
                onNavigateToSettings = { navController.navigate("settings") },
                actionResult = actionResult,
                onActionResultConsumed = onActionResultConsumed
            )
        }

        composable("scenes") {
            ScenesScreen()
        }

        composable("rooms") {
            RoomsScreen()
        }

        composable("settings") {
            SettingsScreen()
        }
    }
}
