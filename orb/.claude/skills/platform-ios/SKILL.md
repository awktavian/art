# iOS Platform Skill

**100/100 Quality by Default** - Patterns for production-ready iOS apps.

## When to Use

- Creating or modifying iOS apps in `apps/ios/`
- Ensuring iOS-specific quality standards
- Byzantine audit remediation for iOS

## Required Files (P0)

Every iOS app MUST have these files implemented (not empty):

```
KagamiIOS/
├── KagamiIOSApp.swift              # App entry point
├── ContentView.swift               # Main TabView (CRITICAL)
├── DesignSystem.swift              # Design tokens
├── DesignTokens.generated.swift    # Generated tokens
├── Views/
│   ├── RoomsView.swift             # Room controls
│   ├── ScenesView.swift            # Scene activation
│   ├── SettingsView.swift          # Settings
│   └── OnboardingView.swift        # First run
├── Services/
│   ├── KagamiAPIService.swift      # API client
│   ├── KagamiNetworkService.swift  # Network layer
│   ├── KeychainService.swift       # Secure storage
│   └── KagamiWebSocketService.swift # Real-time
├── CarPlay/
│   └── KagamiCarPlaySceneDelegate.swift
├── AccessibilityIdentifiers.swift  # Test identifiers
└── AccessibilityModifiers.swift    # Accessibility helpers
```

## Critical Patterns

### 1. ContentView (MANDATORY)

```swift
import SwiftUI

struct ContentView: View {
    @StateObject private var appModel = AppModel()
    @State private var selectedTab: Tab = .home

    enum Tab: String, CaseIterable {
        case home, rooms, scenes, settings
    }

    var body: some View {
        TabView(selection: $selectedTab) {
            HomeView()
                .tabItem {
                    Label("Home", systemImage: "house.fill")
                }
                .tag(Tab.home)

            RoomsView()
                .tabItem {
                    Label("Rooms", systemImage: "square.grid.2x2.fill")
                }
                .tag(Tab.rooms)

            ScenesView()
                .tabItem {
                    Label("Scenes", systemImage: "sparkles")
                }
                .tag(Tab.scenes)

            SettingsView()
                .tabItem {
                    Label("Settings", systemImage: "gearshape.fill")
                }
                .tag(Tab.settings)
        }
        .environmentObject(appModel)
        .preferredColorScheme(.dark)
        .onAppear {
            Task {
                await appModel.initialize()
            }
        }
    }
}
```

### 2. Design Tokens (MANDATORY)

```swift
import SwiftUI

enum KagamiSpacing {
    static let xxSmall: CGFloat = 2
    static let xSmall: CGFloat = 4
    static let small: CGFloat = 8
    static let medium: CGFloat = 16
    static let large: CGFloat = 24
    static let xLarge: CGFloat = 40
    static let xxLarge: CGFloat = 64
}

enum KagamiAnimation {
    static let instant: Double = 0.089  // 89ms
    static let fast: Double = 0.144     // 144ms
    static let normal: Double = 0.233   // 233ms
    static let slow: Double = 0.377     // 377ms
    static let slower: Double = 0.610   // 610ms
}

enum KagamiRadius {
    static let small: CGFloat = 4
    static let medium: CGFloat = 8
    static let large: CGFloat = 16
    static let pill: CGFloat = 999
}

// Colony Colors (WCAG AA compliant)
extension Color {
    static let sparkPrimary = Color(red: 1.0, green: 0.42, blue: 0.21)
    static let forgePrimary = Color(red: 0.13, green: 0.59, blue: 0.95)
    static let flowPrimary = Color(red: 0.30, green: 0.69, blue: 0.31)
    static let guardPrimary = Color(red: 0.96, green: 0.26, blue: 0.21)
}
```

### 3. API Service Pattern (MANDATORY)

```swift
import Foundation
import Combine

@MainActor
final class KagamiAPIService: ObservableObject {
    static let shared = KagamiAPIService()

    @Published private(set) var isConnected = false
    @Published private(set) var safetyScore: Double?
    @Published private(set) var rooms: [Room] = []
    @Published private(set) var scenes: [Scene] = []

    private let networkService: KagamiNetworkService
    private let keychainService: KeychainService

    private init(
        networkService: KagamiNetworkService = .shared,
        keychainService: KeychainService = .shared
    ) {
        self.networkService = networkService
        self.keychainService = keychainService
    }

    func connect() async throws {
        // 1. Service discovery
        let serverURL = try await discoverServer()

        // 2. Health check
        let health = try await healthCheck(baseURL: serverURL)
        safetyScore = health.safetyScore

        // 3. Authenticate if needed
        if keychainService.getAuthToken() == nil {
            try await authenticate()
        }

        // 4. Fetch initial data
        rooms = try await fetchRooms()
        scenes = try await fetchScenes()

        isConnected = true
    }

    func activateScene(_ sceneId: String) async throws {
        guard let token = keychainService.getAuthToken() else {
            throw APIError.unauthorized
        }
        try await networkService.post(
            "/home/scenes/\(sceneId)/activate",
            token: token
        )
    }
}
```

### 4. Keychain Service (MANDATORY)

```swift
import Security
import Foundation

final class KeychainService {
    static let shared = KeychainService()

    private let service = "com.kagami.ios"

    func save(key: String, value: String) throws {
        guard let data = value.data(using: .utf8) else {
            throw KeychainError.encodingError
        }

        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key,
            kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlockedThisDeviceOnly
        ]

        // Delete existing item first
        SecItemDelete(query as CFDictionary)

        let status = SecItemAdd(query as CFDictionary, nil)
        guard status == errSecSuccess else {
            throw KeychainError.saveError(status)
        }
    }

    func get(key: String) -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]

        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)

        guard status == errSecSuccess,
              let data = result as? Data,
              let string = String(data: data, encoding: .utf8) else {
            return nil
        }

        return string
    }

    func delete(key: String) {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key
        ]
        SecItemDelete(query as CFDictionary)
    }
}
```

### 5. Accessibility (MANDATORY)

```swift
import SwiftUI

// Accessibility identifiers for testing
enum AccessibilityIdentifier {
    static let homeTab = "tab.home"
    static let roomsTab = "tab.rooms"
    static let scenesTab = "tab.scenes"
    static let settingsTab = "tab.settings"
    static let sceneActivateButton = "scene.activate"
    static let roomControlSlider = "room.control.slider"
}

// View modifier for accessible buttons
struct AccessibleButton: ViewModifier {
    let label: String
    let hint: String?

    func body(content: Content) -> some View {
        content
            .accessibilityLabel(label)
            .accessibilityHint(hint ?? "")
            .accessibilityAddTraits(.isButton)
    }
}

extension View {
    func accessibleButton(label: String, hint: String? = nil) -> some View {
        modifier(AccessibleButton(label: label, hint: hint))
    }

    // Minimum 44pt touch target
    func minTouchTarget() -> some View {
        self.frame(minWidth: 44, minHeight: 44)
    }
}
```

### 6. Widget Pattern (MANDATORY)

```swift
import WidgetKit
import SwiftUI

struct KagamiWidgetEntry: TimelineEntry {
    let date: Date
    let safetyScore: Double
    let activeScenes: [String]
    let isConnected: Bool
}

struct KagamiTimelineProvider: TimelineProvider {
    typealias Entry = KagamiWidgetEntry

    func placeholder(in context: Context) -> Entry {
        Entry(date: .now, safetyScore: 0.95, activeScenes: [], isConnected: true)
    }

    func getSnapshot(in context: Context, completion: @escaping (Entry) -> Void) {
        completion(placeholder(in: context))
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<Entry>) -> Void) {
        Task {
            let entry = await fetchCurrentState()
            let nextUpdate = Calendar.current.date(byAdding: .minute, value: 5, to: .now)!
            let timeline = Timeline(entries: [entry], policy: .after(nextUpdate))
            completion(timeline)
        }
    }

    private func fetchCurrentState() async -> Entry {
        // Fetch from API or App Group shared data
        Entry(date: .now, safetyScore: 0.95, activeScenes: [], isConnected: true)
    }
}
```

## Testing Requirements

### Unit Tests (Required)

```swift
import XCTest
@testable import KagamiIOS

final class KagamiAPIServiceTests: XCTestCase {
    var sut: KagamiAPIService!

    override func setUp() {
        super.setUp()
        // Setup with mock network
    }

    func testHealthCheckSuccess() async throws {
        // Given
        let mockResponse = HealthResponse(safetyScore: 0.95)
        mockNetwork.enqueue(mockResponse)

        // When
        let health = try await sut.healthCheck()

        // Then
        XCTAssertEqual(health.safetyScore, 0.95)
    }

    func testSceneActivationUpdatesState() async throws {
        // Test scene activation
    }
}
```

### Snapshot Tests (Required)

```swift
import XCTest
import SnapshotTesting
@testable import KagamiIOS

final class SnapshotTests: XCTestCase {
    func testHomeViewSnapshot() {
        let view = HomeView()
            .environmentObject(AppModel.preview)
            .preferredColorScheme(.dark)

        assertSnapshot(of: view, as: .image(layout: .device(config: .iPhone15Pro)))
    }

    func testHomeViewReducedMotion() {
        let view = HomeView()
            .environmentObject(AppModel.preview)
            .environment(\.accessibilityReduceMotion, true)

        assertSnapshot(of: view, as: .image(layout: .device(config: .iPhone15Pro)))
    }
}
```

### UI Tests (Required)

```swift
import XCTest

final class OnboardingFlowTests: XCTestCase {
    let app = XCUIApplication()

    override func setUpWithError() throws {
        continueAfterFailure = false
        app.launchArguments = ["--uitesting", "--reset-state"]
        app.launch()
    }

    func testOnboardingFlowCompletes() throws {
        // Given: Fresh install state
        let welcomeText = app.staticTexts["Welcome to Kagami"]
        XCTAssertTrue(welcomeText.waitForExistence(timeout: 5))

        // When: Complete onboarding
        app.buttons["Get Started"].tap()
        // ... continue flow

        // Then: Arrives at home
        XCTAssertTrue(app.tabBars.buttons[AccessibilityIdentifier.homeTab].exists)
    }
}
```

## Security Requirements

1. **Keychain** for all sensitive data (never UserDefaults)
2. **App Transport Security** properly configured
3. **No hardcoded secrets** in code or Info.plist
4. **Certificate pinning** for production
5. **Entitlements** properly scoped

### Info.plist Security

```xml
<key>NSAppTransportSecurity</key>
<dict>
    <key>NSExceptionDomains</key>
    <dict>
        <key>kagami.local</key>
        <dict>
            <key>NSExceptionAllowsInsecureHTTPLoads</key>
            <true/>
            <key>NSIncludesSubdomains</key>
            <true/>
        </dict>
    </dict>
</dict>
```

## Build Verification

```bash
# Verify iOS build passes
cd apps/ios/kagami-ios

# Build
xcodebuild -scheme KagamiIOS build \
    -destination 'platform=iOS Simulator,name=iPhone 15 Pro'

# Run tests
xcodebuild test -scheme KagamiIOS \
    -destination 'platform=iOS Simulator,name=iPhone 15 Pro'

# Run UI tests
xcodebuild test -scheme KagamiIOSUITests \
    -destination 'platform=iOS Simulator,name=iPhone 15 Pro'
```

## Quality Checklist

Before any iOS commit:

- [ ] `ContentView.swift` has full TabView implementation
- [ ] All Views compile without errors
- [ ] `KagamiAPIService` uses async/await properly
- [ ] `KeychainService` stores tokens securely
- [ ] All buttons have 44pt minimum touch targets
- [ ] All interactive elements have accessibilityLabel
- [ ] Snapshot tests pass
- [ ] UI tests pass
- [ ] No hardcoded secrets in code
- [ ] Dark mode enforced

## Common Issues & Fixes

### Empty ContentView
- **Symptom**: App shows blank screen
- **Fix**: Implement full TabView with all tabs

### Keychain Access Denied
- **Symptom**: Token save fails
- **Fix**: Check entitlements and accessibility level

### UI Tests Flaky
- **Symptom**: Tests pass sometimes, fail others
- **Fix**: Add proper `waitForExistence` calls

---

*100/100 or don't ship.*
