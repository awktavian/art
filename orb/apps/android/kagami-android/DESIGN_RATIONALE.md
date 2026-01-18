# Android Design Rationale

**Material Design 3 implementation with Kagami identity.**

## Overview

The Android client implements Material Design 3 while maintaining visual parity with iOS. This document explains the design decisions.

## Design System Parity

### iOS → Android Mapping

| iOS Component | Android Equivalent | Notes |
|---------------|-------------------|-------|
| SwiftUI View | @Composable | 100% Compose |
| SF Symbols | Material Icons | + Custom |
| UIKit Colors | Material Color Scheme | Colony palette |
| HIG Typography | Material Typography | Matched scale |
| HIG Spacing | 8pt Grid | Consistent |

### Colony Colors (Identical)

```kotlin
// Same hex values as iOS
val Spark = Color(0xFFFF6B35)
val Forge = Color(0xFFE63946)
val Flow = Color(0xFF457B9D)
val Nexus = Color(0xFF2A9D8F)
val Beacon = Color(0xFFF4A261)
val Grove = Color(0xFF52B788)
val Crystal = Color(0xFF9D4EDD)
```

## Material Design 3 Integration

### Dynamic Color

M3 supports dynamic color from wallpaper. Kagami uses:
- **Fixed colony colors** — Identity consistency
- **Dynamic neutrals** — System integration
- **Safety colors fixed** — Critical visibility

### Typography Scale

| M3 Role | Size | iOS Equivalent |
|---------|------|----------------|
| Display Large | 57sp | Large Title |
| Headline Medium | 28sp | Title 1 |
| Title Medium | 16sp | Headline |
| Body Large | 16sp | Body |
| Label Medium | 12sp | Caption |

### Shapes

M3 shape system with Kagami adjustments:
- **Cards**: 16dp corner radius (matches iOS)
- **Buttons**: 12dp corner radius
- **Chips**: 8dp corner radius
- **Sheets**: 24dp top corners

## Jetpack Compose Architecture

### 100% Compose Target

No XML layouts. All UI in Compose:

```kotlin
@Composable
fun HomeScreen(viewModel: HomeViewModel) {
    KagamiTheme {
        Scaffold(
            topBar = { KagamiTopBar() },
            bottomBar = { KagamiNavigationBar() },
        ) { padding ->
            HomeContent(
                modifier = Modifier.padding(padding),
                state = viewModel.state,
            )
        }
    }
}
```

### State Management

Following UDF (Unidirectional Data Flow):

```kotlin
// ViewModel
class HomeViewModel : ViewModel() {
    private val _state = MutableStateFlow(HomeState())
    val state: StateFlow<HomeState> = _state.asStateFlow()

    fun onAction(action: HomeAction) {
        when (action) {
            is HomeAction.SetLights -> setLights(action.level)
            is HomeAction.ActivateScene -> activateScene(action.scene)
        }
    }
}

// UI
@Composable
fun HomeScreen(viewModel: HomeViewModel) {
    val state by viewModel.state.collectAsState()

    HomeContent(
        state = state,
        onAction = viewModel::onAction,
    )
}
```

## Navigation

### Bottom Navigation

5 items matching iOS:

```kotlin
@Composable
fun KagamiNavigationBar(
    currentRoute: String,
    onNavigate: (String) -> Unit,
) {
    NavigationBar {
        KagamiNavItem(
            route = Routes.HOME,
            icon = Icons.Outlined.Home,
            selectedIcon = Icons.Filled.Home,
            label = "Home",
            selected = currentRoute == Routes.HOME,
            onClick = { onNavigate(Routes.HOME) },
        )
        // ... Rooms, Voice, Scenes, Settings
    }
}
```

### Navigation Graph

```kotlin
@Composable
fun KagamiNavHost(navController: NavHostController) {
    NavHost(navController, startDestination = Routes.HOME) {
        composable(Routes.HOME) { HomeScreen() }
        composable(Routes.ROOMS) { RoomsScreen() }
        composable(Routes.VOICE) { VoiceScreen() }
        composable(Routes.SCENES) { ScenesScreen() }
        composable(Routes.SETTINGS) { SettingsScreen() }

        // Detail screens
        composable("${Routes.ROOM}/{roomId}") { backStackEntry ->
            RoomDetailScreen(roomId = backStackEntry.arguments?.getString("roomId"))
        }
    }
}
```

## Native Animations

### Shared Element Transitions

```kotlin
@OptIn(ExperimentalSharedTransitionApi::class)
@Composable
fun RoomCard(
    room: Room,
    onClick: () -> Unit,
    sharedTransitionScope: SharedTransitionScope,
    animatedVisibilityScope: AnimatedVisibilityScope,
) {
    with(sharedTransitionScope) {
        Card(
            modifier = Modifier
                .sharedElement(
                    state = rememberSharedContentState(key = "room-${room.id}"),
                    animatedVisibilityScope = animatedVisibilityScope,
                )
                .clickable(onClick = onClick),
        ) {
            // Card content
        }
    }
}
```

### Motion Specs

Following M3 motion:

| Animation | Duration | Easing |
|-----------|----------|--------|
| Enter | 350ms | EmphasizedDecelerate |
| Exit | 250ms | EmphasizedAccelerate |
| Fade | 150ms | Linear |
| Scale | 300ms | EmphasizedDecelerate |

```kotlin
object KagamiMotion {
    val EnterDuration = 350
    val ExitDuration = 250
    val FadeDuration = 150

    val EmphasizedEasing = CubicBezierEasing(0.2f, 0f, 0f, 1f)
    val EmphasizedDecelerate = CubicBezierEasing(0.05f, 0.7f, 0.1f, 1f)
    val EmphasizedAccelerate = CubicBezierEasing(0.3f, 0f, 0.8f, 0.15f)
}
```

## Accessibility

### TalkBack Support

```kotlin
@Composable
fun SafetyIndicator(hx: Float) {
    val status = when {
        hx >= 0.5f -> "Safe"
        hx >= 0.0f -> "Caution"
        else -> "Warning"
    }

    Icon(
        imageVector = Icons.Filled.Security,
        contentDescription = "Safety status: $status. Value: ${(hx * 100).toInt()} percent",
        tint = safetyColor(hx),
        modifier = Modifier.semantics {
            stateDescription = status
        }
    )
}
```

### Dynamic Type

```kotlin
// Respects system font scale
@Composable
fun KagamiTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        typography = KagamiTypography, // Uses sp units
        content = content
    )
}
```

## Widget Support

### Glance Widgets (Jetpack)

```kotlin
class KagamiWidget : GlanceAppWidget() {
    override suspend fun provideGlance(context: Context, id: GlanceId) {
        provideContent {
            KagamiWidgetContent()
        }
    }
}

@Composable
private fun KagamiWidgetContent() {
    Column(
        modifier = GlanceModifier
            .fillMaxSize()
            .background(GlanceTheme.colors.surface),
    ) {
        // Hero action
        // Quick controls
        // Safety indicator
    }
}
```

## References

- [Material Design 3](https://m3.material.io/)
- [Jetpack Compose](https://developer.android.com/jetpack/compose)
- [Android Design Guidelines](https://developer.android.com/design)

---

*Same Kagami, native Android.*

💎 Crystal Colony
