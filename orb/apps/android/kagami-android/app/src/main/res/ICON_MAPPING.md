# Android Vector Drawable Mapping

## Icon Naming Convention

All icons use the `ic_` prefix followed by category and name:
- `ic_fano_plane` - Brand mark
- `ic_colony_{name}` - Colony icons
- `ic_action_{name}` - Action icons
- `ic_status_{name}` - Status icons
- `ic_nav_{name}` - Navigation icons

## Available Icons

### Brand Mark

| Name | File |
|------|------|
| Fano Plane | `ic_fano_plane.xml` |

### Action Icons

| Action | File |
|--------|------|
| Lights | `ic_action_lights.xml` |
| Shades | `ic_action_shades.xml` |
| TV | `ic_action_tv.xml` |
| Fireplace | `ic_action_fireplace.xml` |
| Lock | `ic_action_lock.xml` |
| Movie Mode | `ic_action_movie_mode.xml` |
| Goodnight | `ic_action_goodnight.xml` |
| Welcome Home | `ic_action_welcome_home.xml` |
| Away | `ic_action_away.xml` |

### Status Icons

| Status | File |
|--------|------|
| Safe | `ic_status_safe.xml` |
| Caution | `ic_status_caution.xml` |
| Violation | `ic_status_violation.xml` |
| Connected | `ic_status_connected.xml` |
| Offline | `ic_status_offline.xml` |
| Listening | `ic_status_listening.xml` |

### Navigation Icons

| Nav | File |
|-----|------|
| Home | `ic_nav_home.xml` |
| Rooms | `ic_nav_rooms.xml` |
| Scenes | `ic_nav_scenes.xml` |
| Settings | `ic_nav_settings.xml` |
| Voice | `ic_nav_voice.xml` |

### Colony Icons

| Colony | File |
|--------|------|
| Spark | `ic_colony_spark.xml` |
| Forge | `ic_colony_forge.xml` |
| Flow | `ic_colony_flow.xml` |
| Nexus | `ic_colony_nexus.xml` |
| Beacon | `ic_colony_beacon.xml` |
| Grove | `ic_colony_grove.xml` |
| Crystal | `ic_colony_crystal.xml` |

## Usage in Compose

```kotlin
// Using painterResource
Icon(
    painter = painterResource(id = R.drawable.ic_fano_plane),
    contentDescription = "Kagami",
    tint = Crystal
)

// Using ImageVector (if converted)
Icon(
    imageVector = Icons.Kagami.FanoPlane,
    contentDescription = "Kagami",
    tint = Crystal
)
```

## Color Application

All vector drawables use `?attr/colorOnSurface` for stroke/fill colors.
In Compose, override with the `tint` parameter:

```kotlin
Icon(
    painter = painterResource(id = R.drawable.ic_colony_spark),
    contentDescription = "Spark",
    tint = Spark // #ff6b35
)

Icon(
    painter = painterResource(id = R.drawable.ic_status_safe),
    contentDescription = "Safe",
    tint = Pass // #00ff88
)
```

## Converting from SVG

The SVG icons in `apps/desktop/kagami-client/src/assets/icons/` can be converted to Android Vector Drawables using:

1. Android Studio: File > New > Vector Asset > Local file
2. Online: svg2android.com or shapeshifter.design

---

鏡
