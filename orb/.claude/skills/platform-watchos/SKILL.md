# watchOS Platform Skill

**100/100 Quality by Default** - Patterns for production-ready watchOS apps.

## When to Use

- Creating or modifying watchOS apps in `apps/watch/`
- Ensuring watchOS-specific quality standards
- Byzantine audit remediation for watchOS

## Required Files (P0)

Every watchOS app MUST have these files implemented:

```
KagamiWatch/
├── KagamiWatchApp.swift            # App entry point
├── ContentView.swift               # Main navigation
├── DesignSystem.swift              # Watch-specific tokens
├── Views/
│   ├── RoomsListView.swift         # Room controls
│   ├── ScenesListView.swift        # Scene activation
│   ├── VoiceCommandView.swift      # Voice input
│   └── SettingsView.swift          # Settings
├── Services/
│   ├── KagamiAPIService.swift      # API with circuit breaker
│   ├── WatchConnectivityService.swift  # iPhone sync
│   ├── HealthKitService.swift      # Health data
│   ├── OfflinePersistenceService.swift # Offline queue
│   └── BackgroundTaskManager.swift # Background refresh
├── Complications/
│   └── KagamiComplicationDataSource.swift
├── SmartStack/
│   └── KagamiSmartStackWidget.swift
├── Intents/
│   └── KagamiAppIntents.swift      # Siri Shortcuts
└── KagamiWatch.entitlements
```

## Critical Patterns

### 1. Circuit Breaker API Service (MANDATORY)

```swift
import Foundation

@MainActor
final class KagamiAPIService: ObservableObject {
    @Published private(set) var isConnected = false
    @Published private(set) var circuitState: CircuitState = .closed

    enum CircuitState {
        case closed      // Normal operation
        case open        // Failing, reject requests
        case halfOpen    // Testing recovery
    }

    private var failureCount = 0
    private let failureThreshold = 5
    private var lastFailureTime: Date?
    private let recoveryTimeout: TimeInterval = 30

    func healthCheck() async throws -> HealthResponse {
        guard shouldAllowRequest() else {
            throw APIError.circuitOpen
        }

        do {
            let response = try await performHealthCheck()
            recordSuccess()
            return response
        } catch {
            recordFailure()
            throw error
        }
    }

    private func shouldAllowRequest() -> Bool {
        switch circuitState {
        case .closed:
            return true
        case .open:
            if let lastFailure = lastFailureTime,
               Date().timeIntervalSince(lastFailure) > recoveryTimeout {
                circuitState = .halfOpen
                return true
            }
            return false
        case .halfOpen:
            return true
        }
    }

    private func recordSuccess() {
        failureCount = 0
        circuitState = .closed
    }

    private func recordFailure() {
        failureCount += 1
        lastFailureTime = Date()
        if failureCount >= failureThreshold {
            circuitState = .open
        }
    }
}
```

### 2. Watch Connectivity (MANDATORY)

```swift
import WatchConnectivity

final class WatchConnectivityService: NSObject, ObservableObject {
    static let shared = WatchConnectivityService()

    @Published private(set) var authToken: String?
    @Published private(set) var isReachable = false

    private var session: WCSession?

    override init() {
        super.init()
        if WCSession.isSupported() {
            session = WCSession.default
            session?.delegate = self
            session?.activate()
        }
    }

    func requestAuth() {
        guard let session = session, session.isReachable else { return }
        session.sendMessage(["action": "requestAuth"], replyHandler: nil)
    }
}

extension WatchConnectivityService: WCSessionDelegate {
    func session(_ session: WCSession, activationDidCompleteWith state: WCSessionActivationState, error: Error?) {
        // Handle activation
    }

    func session(_ session: WCSession, didReceiveApplicationContext context: [String: Any]) {
        // Receive auth token and config from iPhone
        if let token = context["authToken"] as? String {
            DispatchQueue.main.async {
                self.authToken = token
                // Store in Keychain
                try? KeychainService.shared.save(key: "authToken", value: token)
            }
        }
    }

    func sessionReachabilityDidChange(_ session: WCSession) {
        DispatchQueue.main.async {
            self.isReachable = session.isReachable
        }
    }
}
```

### 3. Offline Persistence (MANDATORY)

```swift
import Foundation

final class OfflinePersistenceService: ObservableObject {
    static let shared = OfflinePersistenceService()

    @Published private(set) var queuedActions: [QueuedAction] = []

    private let fileManager = FileManager.default
    private var queueURL: URL {
        fileManager.urls(for: .documentDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("action_queue.json")
    }

    struct QueuedAction: Codable, Identifiable {
        let id: UUID
        let action: String
        let parameters: [String: String]
        let timestamp: Date
        var retryCount: Int
    }

    func enqueue(_ action: String, parameters: [String: String]) {
        let queued = QueuedAction(
            id: UUID(),
            action: action,
            parameters: parameters,
            timestamp: Date(),
            retryCount: 0
        )
        queuedActions.append(queued)
        saveQueue()
    }

    func processQueue() async {
        for action in queuedActions {
            do {
                try await executeAction(action)
                removeFromQueue(action.id)
            } catch {
                incrementRetry(action.id)
            }
        }
    }

    private func saveQueue() {
        guard let data = try? JSONEncoder().encode(queuedActions) else { return }
        try? data.write(to: queueURL)
    }
}
```

### 4. Design System (MANDATORY)

```swift
import SwiftUI

// Watch-specific spacing (smaller for wrist)
enum WatchSpacing {
    static let xxSmall: CGFloat = 1
    static let xSmall: CGFloat = 2
    static let small: CGFloat = 4
    static let medium: CGFloat = 8
    static let large: CGFloat = 12
    static let xLarge: CGFloat = 16
}

// Watch fonts
enum WatchFonts {
    static let largeTitle = Font.system(size: 28, weight: .bold, design: .rounded)
    static let title = Font.system(size: 22, weight: .semibold, design: .rounded)
    static let headline = Font.system(size: 17, weight: .semibold)
    static let body = Font.system(size: 15)
    static let caption = Font.system(size: 13)
}

// Liquid Glass Button (watchOS 11)
struct LiquidGlassButton: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .padding(WatchSpacing.medium)
            .background(.ultraThinMaterial)
            .clipShape(RoundedRectangle(cornerRadius: 12))
            .scaleEffect(configuration.isPressed ? 0.95 : 1.0)
            .animation(.easeOut(duration: 0.2), value: configuration.isPressed)
    }
}

// Rich haptics
enum HapticPattern {
    case success
    case error
    case sceneActivated
    case listening
    case warning

    func play() {
        switch self {
        case .success:
            WKInterfaceDevice.current().play(.success)
        case .error:
            WKInterfaceDevice.current().play(.failure)
        case .sceneActivated:
            WKInterfaceDevice.current().play(.notification)
        case .listening:
            WKInterfaceDevice.current().play(.start)
        case .warning:
            WKInterfaceDevice.current().play(.retry)
        }
    }
}
```

### 5. Complications (MANDATORY)

```swift
import ClockKit
import SwiftUI
import WidgetKit

struct KagamiComplicationDataSource: TimelineProvider {
    typealias Entry = KagamiComplicationEntry

    func placeholder(in context: Context) -> Entry {
        Entry(date: .now, safetyScore: 0.95, isConnected: true)
    }

    func getSnapshot(in context: Context, completion: @escaping (Entry) -> Void) {
        completion(placeholder(in: context))
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<Entry>) -> Void) {
        Task {
            var entries: [Entry] = []
            let currentDate = Date()

            // Generate 72 hours of timeline entries
            for hourOffset in stride(from: 0, to: 72, by: 0.25) {
                let entryDate = Calendar.current.date(
                    byAdding: .minute,
                    value: Int(hourOffset * 60),
                    to: currentDate
                )!
                entries.append(Entry(
                    date: entryDate,
                    safetyScore: await fetchSafetyScore(),
                    isConnected: true
                ))
            }

            let timeline = Timeline(entries: entries, policy: .atEnd)
            completion(timeline)
        }
    }
}

struct KagamiComplicationEntry: TimelineEntry {
    let date: Date
    let safetyScore: Double
    let isConnected: Bool
}
```

### 6. App Intents (MANDATORY)

```swift
import AppIntents

struct ActivateMovieModeIntent: AppIntent {
    static var title: LocalizedStringResource = "Activate Movie Mode"
    static var description = IntentDescription("Activates movie mode in your home")

    func perform() async throws -> some IntentResult {
        let api = KagamiAPIService.shared
        try await api.activateScene("movie_mode")
        HapticPattern.sceneActivated.play()
        return .result()
    }
}

struct ActivateGoodnightIntent: AppIntent {
    static var title: LocalizedStringResource = "Activate Goodnight"
    static var description = IntentDescription("Runs the goodnight routine")

    func perform() async throws -> some IntentResult {
        let api = KagamiAPIService.shared
        try await api.activateScene("goodnight")
        HapticPattern.sceneActivated.play()
        return .result()
    }
}

struct KagamiShortcuts: AppShortcutsProvider {
    static var appShortcuts: [AppShortcut] {
        AppShortcut(
            intent: ActivateMovieModeIntent(),
            phrases: [
                "Start \(.applicationName) movie mode",
                "Movie time with \(.applicationName)"
            ],
            shortTitle: "Movie Mode",
            systemImageName: "film"
        )
        AppShortcut(
            intent: ActivateGoodnightIntent(),
            phrases: [
                "Goodnight with \(.applicationName)",
                "\(.applicationName) bedtime"
            ],
            shortTitle: "Goodnight",
            systemImageName: "moon.fill"
        )
    }
}
```

## Testing Requirements

### Unit Tests (Required)

```swift
import XCTest
@testable import KagamiWatch

final class KagamiAPIServiceTests: XCTestCase {
    func testCircuitBreakerOpensAfterFailures() async {
        let service = KagamiAPIService()
        // Simulate 5 failures
        for _ in 0..<5 {
            service.recordFailure()
        }
        XCTAssertEqual(service.circuitState, .open)
    }

    func testCircuitBreakerRecovery() async {
        let service = KagamiAPIService()
        service.circuitState = .halfOpen
        service.recordSuccess()
        XCTAssertEqual(service.circuitState, .closed)
    }
}
```

### Snapshot Tests (Required)

```swift
import XCTest
import SnapshotTesting
@testable import KagamiWatch

final class PreviewSnapshotTests: XCTestCase {
    func testContentViewSnapshot() {
        let view = ContentView()
        assertSnapshot(of: view, as: .image(layout: .device(config: .watchUltra2)))
    }

    func testContentViewReducedMotion() {
        let view = ContentView()
            .environment(\.accessibilityReduceMotion, true)
        assertSnapshot(of: view, as: .image(layout: .device(config: .watchUltra2)))
    }
}
```

## Entitlements (MANDATORY)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>com.apple.developer.healthkit</key>
    <true/>
    <key>com.apple.developer.healthkit.access</key>
    <array>
        <string>health-records</string>
    </array>
    <key>com.apple.security.application-groups</key>
    <array>
        <string>group.com.kagami.shared</string>
    </array>
</dict>
</plist>
```

## Build Verification

```bash
# Verify watchOS build passes
cd apps/watch/kagami-watch

# Build
xcodebuild -scheme KagamiWatch build \
    -destination 'platform=watchOS Simulator,name=Apple Watch Ultra 2 (49mm)'

# Run tests
xcodebuild test -scheme KagamiWatch \
    -destination 'platform=watchOS Simulator,name=Apple Watch Ultra 2 (49mm)'
```

## Quality Checklist

Before any watchOS commit:

- [ ] Circuit breaker implemented in API service
- [ ] WatchConnectivity syncs auth from iPhone
- [ ] Offline queue persists and retries
- [ ] All interactive elements have haptic feedback
- [ ] Complications use TimelineProvider
- [ ] App Intents for Siri Shortcuts
- [ ] HealthKit integration if health data needed
- [ ] Snapshot tests pass
- [ ] Battery-conscious (10min sensory interval)

## Common Issues & Fixes

### Circuit Breaker Stuck Open
- **Symptom**: No requests after failures
- **Fix**: Implement halfOpen state with recovery timeout

### Watch Not Syncing
- **Symptom**: Auth token missing
- **Fix**: Check WCSession activation and applicationContext

### Complications Not Updating
- **Symptom**: Stale data on watch face
- **Fix**: Use TimelineProvider with proper refresh policy

---

*100/100 or don't ship.*
