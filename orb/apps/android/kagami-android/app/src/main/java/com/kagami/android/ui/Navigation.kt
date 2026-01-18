/**
 * Kagami Navigation - App Navigation Graph
 *
 * Colony: Nexus (e4) - Integration
 *
 * Features:
 * - Deep links (kagami://room/{id}, kagami://scene/{id})
 * - Hilt ViewModel injection
 * - Predictive back gesture support
 * - Accessibility configuration via CompositionLocal
 */

package com.kagami.android.ui

import androidx.compose.animation.AnimatedContentTransitionScope
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.MeetingRoom
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Theaters
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavDestination.Companion.hierarchy
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import androidx.navigation.navDeepLink
import kotlinx.coroutines.launch
import com.kagami.android.hub.HubScreen
import com.kagami.android.services.KagamiApiService
import com.kagami.android.ui.screens.*
import com.kagami.android.ui.AccessibilityConfig
import com.kagami.android.ui.LocalAccessibilityConfig
import com.kagami.android.ui.minTouchTarget

sealed class Screen(val route: String, val label: String? = null, val icon: ImageVector? = null) {
    data object Login : Screen("login")
    data object Onboarding : Screen("onboarding")
    data object Home : Screen("home", "Home", Icons.Default.Home)
    data object Rooms : Screen("rooms", "Rooms", Icons.Default.MeetingRoom)
    data object Scenes : Screen("scenes", "Scenes", Icons.Default.Theaters)
    data object Settings : Screen("settings", "Settings", Icons.Default.Settings)
    data object Voice : Screen("voice")
    data object Hub : Screen("hub")
    data object RoomDetail : Screen("room/{roomId}")
    data object SceneDetail : Screen("scene/{sceneId}")
}

private val bottomNavItems = listOf(Screen.Home, Screen.Rooms, Screen.Scenes, Screen.Settings)

/**
 * Determines if user is authenticated based on stored tokens.
 */
private fun isAuthenticated(apiService: KagamiApiService): Boolean {
    return apiService.isAuthenticated()
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun KagamiNavHost(
    apiService: KagamiApiService = hiltViewModel<NavViewModel>().apiService
) {
    val context = LocalContext.current
    val prefs = context.getSharedPreferences("kagami_prefs", android.content.Context.MODE_PRIVATE)

    // Auth state using the injected service
    var isLoggedIn by remember { mutableStateOf(isAuthenticated(apiService)) }
    var hasCompletedOnboarding by remember {
        mutableStateOf(prefs.getBoolean("hasCompletedOnboarding", false))
    }

    val navController = rememberNavController()

    // Determine start destination based on auth and onboarding state
    val startDestination = when {
        !isLoggedIn -> Screen.Login.route
        !hasCompletedOnboarding -> Screen.Onboarding.route
        else -> Screen.Home.route
    }

    // Check if we should show bottom nav (not on login/onboarding screens)
    val navBackStackEntry by navController.currentBackStackEntryAsState()
    val currentDestination = navBackStackEntry?.destination
    val showBottomNav = currentDestination?.route !in listOf(
        Screen.Login.route,
        Screen.Onboarding.route,
        Screen.Voice.route
    )

    CompositionLocalProvider(LocalAccessibilityConfig provides AccessibilityConfig()) {
        Scaffold(
            bottomBar = {
                if (showBottomNav) {
                    NavigationBar {
                        bottomNavItems.forEach { screen ->
                            val selected = currentDestination?.hierarchy?.any { it.route == screen.route } == true

                            NavigationBarItem(
                                icon = {
                                    screen.icon?.let {
                                        Icon(
                                            imageVector = it,
                                            contentDescription = null
                                        )
                                    }
                                },
                                label = { screen.label?.let { Text(it) } },
                                selected = selected,
                                onClick = {
                                    navController.navigate(screen.route) {
                                        popUpTo(navController.graph.findStartDestination().id) {
                                            saveState = true
                                        }
                                        launchSingleTop = true
                                        restoreState = true
                                    }
                                },
                                modifier = Modifier
                                    .minTouchTarget()
                                    .semantics {
                                        contentDescription = "${screen.label} tab" +
                                                if (selected) ", currently selected" else ""
                                        role = Role.Tab
                                    }
                            )
                        }
                    }
                }
            }
        ) { innerPadding ->
            NavHost(
                navController = navController,
                startDestination = startDestination,
                modifier = Modifier.padding(innerPadding),
                enterTransition = {
                    slideIntoContainer(
                        AnimatedContentTransitionScope.SlideDirection.Left,
                        animationSpec = tween(233)
                    )
                },
                exitTransition = {
                    slideOutOfContainer(
                        AnimatedContentTransitionScope.SlideDirection.Left,
                        animationSpec = tween(233)
                    )
                },
                popEnterTransition = {
                    slideIntoContainer(
                        AnimatedContentTransitionScope.SlideDirection.Right,
                        animationSpec = tween(233)
                    )
                },
                popExitTransition = {
                    slideOutOfContainer(
                        AnimatedContentTransitionScope.SlideDirection.Right,
                        animationSpec = tween(233)
                    )
                }
            ) {
                // Login Screen - uses Hilt-injected ViewModel
                composable(Screen.Login.route) {
                    val loginViewModel: LoginViewModelDI = hiltViewModel()

                    // Initialize server URL from stored value
                    LaunchedEffect(Unit) {
                        apiService.getServerUrl()?.let { loginViewModel.updateServerUrl(it) }
                        loginViewModel.trackScreenView()
                    }

                    LoginScreen(
                        viewModel = loginViewModel,
                        onLoginSuccess = { accessToken, refreshToken ->
                            val serverUrl = loginViewModel.state.value.serverUrl
                            // Call non-suspend version or launch in coroutine
                            kotlinx.coroutines.MainScope().launch {
                                apiService.storeAuthTokens(serverUrl, accessToken, refreshToken)
                            }
                            isLoggedIn = true

                            val nextRoute = if (hasCompletedOnboarding) {
                                Screen.Home.route
                            } else {
                                Screen.Onboarding.route
                            }
                            navController.navigate(nextRoute) {
                                popUpTo(Screen.Login.route) { inclusive = true }
                            }
                        },
                        onCreateAccount = { }
                    )
                }

                // Onboarding Wizard Screen - uses Hilt-injected ViewModel
                composable(Screen.Onboarding.route) {
                    val onboardingViewModel: OnboardingViewModelDI = hiltViewModel()

                    // Track screen view
                    LaunchedEffect(Unit) {
                        onboardingViewModel.trackScreenView("start")
                    }

                    OnboardingScreen(
                        viewModel = onboardingViewModel,
                        onComplete = {
                            prefs.edit().putBoolean("hasCompletedOnboarding", true).apply()
                            hasCompletedOnboarding = true
                            navController.navigate(Screen.Home.route) {
                                popUpTo(Screen.Onboarding.route) { inclusive = true }
                            }
                        }
                    )
                }

                // Home Screen
                composable(Screen.Home.route) {
                    HomeScreen(
                        onNavigateToRooms = { navController.navigate(Screen.Rooms.route) },
                        onNavigateToScenes = { navController.navigate(Screen.Scenes.route) },
                        onNavigateToSettings = { navController.navigate(Screen.Settings.route) },
                        onNavigateToVoice = { navController.navigate(Screen.Voice.route) },
                        onNavigateToHub = { navController.navigate(Screen.Hub.route) }
                    )
                }

                // Rooms Screen
                composable(Screen.Rooms.route) {
                    RoomsScreen(onBack = { navController.popBackStack() })
                }

                // Scenes Screen
                composable(Screen.Scenes.route) {
                    ScenesScreen(onBack = { navController.popBackStack() })
                }

                // Settings Screen
                composable(Screen.Settings.route) {
                    SettingsScreen(
                        onBack = { navController.popBackStack() },
                        onLogout = {
                            apiService.clearAuthTokens()
                            isLoggedIn = false
                            navController.navigate(Screen.Login.route) {
                                popUpTo(0) { inclusive = true }
                            }
                        }
                    )
                }

                // Voice Command Screen
                composable(Screen.Voice.route) {
                    VoiceCommandScreen(onBack = { navController.popBackStack() })
                }

                // Hub Screen
                composable(Screen.Hub.route) {
                    HubScreen()
                }

                // Deep link for room detail
                composable(
                    route = Screen.RoomDetail.route,
                    arguments = listOf(navArgument("roomId") { type = NavType.StringType }),
                    deepLinks = listOf(
                        navDeepLink { uriPattern = "kagami://room/{roomId}" },
                        navDeepLink { uriPattern = "https://kagami.local/room/{roomId}" }
                    )
                ) { backStackEntry ->
                    val roomId = backStackEntry.arguments?.getString("roomId") ?: ""
                    RoomDetailScreen(
                        roomId = roomId,
                        onBack = { navController.popBackStack() }
                    )
                }

                // Deep link for scene detail
                composable(
                    route = Screen.SceneDetail.route,
                    arguments = listOf(navArgument("sceneId") { type = NavType.StringType }),
                    deepLinks = listOf(
                        navDeepLink { uriPattern = "kagami://scene/{sceneId}" },
                        navDeepLink { uriPattern = "https://kagami.local/scene/{sceneId}" }
                    )
                ) { backStackEntry ->
                    val sceneId = backStackEntry.arguments?.getString("sceneId") ?: ""
                    SceneDetailScreen(
                        sceneId = sceneId,
                        onBack = { navController.popBackStack() }
                    )
                }
            }
        }
    }
}

/*
 * Mirror
 * h(x) >= 0. Always.
 */
