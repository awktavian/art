# App Improvement Skill

Cross-platform app improvement methodology for the Kagami ecosystem.

## When to Use

- Improving any app in `apps/` directory
- Implementing features from audit document
- Cross-platform feature parity work
- Platform-native feature implementation

## Master Plan

**Read first**: `.claude/tasks/RALPH.md`

Contains:
- Business models (self-hosted, enterprise, hub, cloud)
- Deployment architecture (Docker, K8s, Hub image)
- Auth & multi-tenancy implementation
- Per-platform fixes with code examples
- CI/CD pipeline
- Execution timeline

## Platform Reference

### iOS (`apps/ios/kagami-ios/`)

| Key File | Purpose |
|----------|---------|
| `ContentView.swift` | Main UI structure |
| `KagamiAPIService.swift` | API client |
| `KagamiIOSApp.swift` | App entry point |
| `Views/*.swift` | Screen views |
| `Intents/*.swift` | Siri Shortcuts |
| `KagamiWidget/` | Widget extensions |
| `CarPlay/` | CarPlay UI |

**P0 Tasks**:
1. Implement Siri Shortcuts (AppIntents framework)
2. Make widgets dynamic with TimelineProvider
3. Implement CarPlay dashboard
4. Replace DemoDataProvider with real API
5. Add Control Center toggle

**Build Command**:
```bash
cd apps/ios/kagami-ios
xcodebuild -scheme KagamiIOS build
```

### Android (`apps/android/kagami-android/`)

| Key File | Purpose |
|----------|---------|
| `ui/screens/HomeScreen.kt` | Main UI |
| `services/KagamiApiService.kt` | API client |
| `widgets/*.kt` | Glance widgets |
| `tiles/QuickSettingsTiles.kt` | Quick Settings |

**P0 Tasks**:
1. Implement Google Assistant Actions
2. Complete Quick Settings tiles
3. Add Android Device Controls API
4. Replace demo data with real API
5. Improve Wear OS app

**Build Command**:
```bash
cd apps/android/kagami-android
./gradlew assembleDebug
```

### Watch (`apps/watch/kagami-watch/`)

| Key File | Purpose |
|----------|---------|
| `ContentView.swift` | Main interface |
| `KagamiAPIService.swift` | API client |
| `Complications/ColonyComplication.swift` | Complications |
| `SmartStack/KagamiSmartStackWidget.swift` | Smart Stack |

**P0 Tasks**:
1. Add Smart Stack Widget
2. Make complications interactive
3. Implement Digital Crown controls
4. Add offline mode
5. Background App Refresh

**Build Command**:
```bash
cd apps/watch/kagami-watch
xcodebuild -scheme KagamiWatch build
```

### Desktop (`apps/desktop/kagami-client/`)

| Key File | Purpose |
|----------|---------|
| `src-tauri/src/main.rs` | Rust entry point |
| `src-tauri/src/commands.rs` | Tauri commands |
| `src-tauri/src/audio.rs` | Voice pipeline |
| `src/index.html` | Main UI |
| `src/js/*.js` | Frontend logic |
| `src/css/*.css` | Styling |

**P0 Tasks**:
1. Modernize UI with proper CSS framework
2. Add full keyboard navigation
3. Implement voice pipeline (wake word + STT)
4. Add auto-update mechanism
5. Multi-monitor support

**Build Command**:
```bash
cd apps/desktop/kagami-client
npm run tauri build
```

### Hub (`apps/hub/kagami-hub/`)

| Key File | Purpose |
|----------|---------|
| `src/main.rs` | Entry point |
| `src/voice_pipeline.rs` | Voice processing |
| `src/wake_word.rs` | Wake word detection |
| `src/led_ring.rs` | LED control |
| `src/web_server.rs` | Phone config server |

**P0 Tasks (CRITICAL)**:
1. Implement wake word detection (Porcupine)
2. Implement STT (Whisper integration)
3. Implement TTS (ElevenLabs streaming via hub relay)
4. Test on actual Raspberry Pi hardware
5. Create setup documentation

**Build Command**:
```bash
cd apps/hub/kagami-hub
cargo build --release --features rpi
```

### Vision Pro (`apps/vision/kagami-vision/`)

| Key File | Purpose |
|----------|---------|
| `ContentView.swift` | Main spatial UI |
| `Spaces/*.swift` | Immersive spaces |

**P0 Tasks**:
1. Redesign for spatial depth (3D card hierarchy)
2. Add pass-through highlights for devices
3. Implement spatial audio for announcements
4. Voice-first interaction
5. Room-scale Kagami presence

**Build Command**:
```bash
xcodebuild -scheme KagamiVision build
```

## API Feature Parity

Every app should call these endpoints:

| Endpoint | Purpose | Priority |
|----------|---------|----------|
| `/health` | Connection check | Required |
| `/home/clients/register` | Device registration | Required |
| `/home/clients/*/sense` | Sensory upload | Required |
| `/home/rooms` | Room data | Required |
| `/home/lights/set` | Light control | Required |
| `/home/shades/*` | Shade control | Required |
| `/home/tv/*` | TV mount control | Required |
| `/home/fireplace/*` | Fireplace control | Required |
| `/home/movie-mode/*` | Theater mode | Required |
| `/home/goodnight` | Goodnight scene | Required |
| `/home/welcome-home` | Welcome scene | Required |
| `/home/announce` | TTS announcements | Platform-dependent |
| `/home/locks/*` | Lock control | Platform-dependent |
| `/home/temp/*` | HVAC control | Optional |
| `/home/weather` | Weather data | Optional |

## Implementation Checklist

For each platform improvement:

### Before Starting
- [ ] Read audit document section for platform
- [ ] Understand current state
- [ ] Identify P0 tasks
- [ ] Check API endpoints needed

### During Implementation
- [ ] Replace demo data with real API calls
- [ ] Add proper error handling
- [ ] Implement offline caching
- [ ] Add accessibility labels
- [ ] Test with screen reader

### After Implementation
- [ ] Verify feature works end-to-end
- [ ] Check API latency
- [ ] Verify accessibility compliance
- [ ] Update audit document status

## Common Patterns

### API Service Pattern (Swift)

```swift
@MainActor
class KagamiAPIService: ObservableObject {
    @Published var isConnected = false
    @Published var safetyScore: Double?

    private var baseURL = "http://kagami.local:8001"

    func connect() async {
        // 1. Service discovery
        // 2. Health check
        // 3. Client registration
        // 4. WebSocket connection
        // 5. Start sensory uploads
    }
}
```

### API Service Pattern (Kotlin)

```kotlin
class KagamiApiService {
    private val _isConnected = MutableStateFlow(false)
    val isConnected: StateFlow<Boolean> = _isConnected

    suspend fun connect() {
        // 1. Service discovery
        // 2. Health check
        // 3. Client registration
        // 4. WebSocket connection
        // 5. Start sensory uploads
    }
}
```

### Widget Pattern (iOS)

```swift
struct KagamiWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(
            kind: "KagamiWidget",
            provider: KagamiTimelineProvider()
        ) { entry in
            KagamiWidgetEntryView(entry: entry)
        }
        .configurationDisplayName("Kagami")
        .description("Control your smart home")
        .supportedFamilies([.systemSmall, .systemMedium])
    }
}
```

### Quick Settings Tile Pattern (Android)

```kotlin
class KagamiTileService : TileService() {
    override fun onClick() {
        scope.launch {
            apiService.executeScene("movie_mode")
        }
    }
}
```

## Success Metrics

| Platform | Metric | Target |
|----------|--------|--------|
| iOS | Siri Shortcuts | 5+ shortcuts working |
| iOS | Widget updates | Real-time (5s refresh) |
| Android | Quick Settings | 4 tiles functional |
| Android | Assistant | Voice commands working |
| Watch | Smart Stack | Interactive widget |
| Watch | Complications | Live data |
| Desktop | Keyboard nav | Tab through all |
| Desktop | Voice | Wake word responsive |
| Hub | Wake word | <500ms response |
| Hub | STT | <1s transcription |
| Vision | Spatial depth | 3 layer hierarchy |
| Vision | Voice | Primary interaction |

## Memory Tags

When completing work, tag in Memory MCP:

```python
mcp__memory__create_entities(entities=[
    {
        "name": "iOS_P0_Dec31_2025",
        "entityType": "PlatformImprovement",
        "observations": [
            "Platform: iOS",
            "Tasks: Siri, Widgets, CarPlay",
            "Status: COMPLETED",
            "Date: 2025-12-31"
        ]
    }
])
```

---

*For each platform, make it excellent on that platform's terms.*
