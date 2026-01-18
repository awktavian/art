# KagamiWatchOS — Apple Watch Companion App

## Overview

Minimal WatchKit app providing quick access to Kagami scenes and safety status on Apple Watch.

## Features

- **Glanceable Safety Score**: See h(x) at a glance
- **Quick Scenes**: Activate scenes with one tap
- **Complications**: Safety indicator and hero scene
- **Haptic Feedback**: Feel scene activation

## Architecture

```
KagamiWatchOS/
├── KagamiWatchOSApp.swift      # App entry point
├── ContentView.swift           # Main watch view
├── SceneListView.swift         # Scene grid
├── SafetyView.swift            # Safety status display
├── ComplicationController.swift # Watch complications
└── WatchConnectivity/
    └── WatchSessionManager.swift # iPhone communication
```

## Watch Connectivity

Uses WCSession for iPhone communication:
- Automatic context sync (safety score, scenes)
- Message passing for scene activation
- Background refresh support

### iPhone Side (existing)

```swift
// In KagamiIOS/Services/WatchConnectivityService.swift
class WatchConnectivityService: NSObject, WCSessionDelegate {
    static let shared = WatchConnectivityService()

    func activate() {
        if WCSession.isSupported() {
            WCSession.default.delegate = self
            WCSession.default.activate()
        }
    }

    func sendContext() {
        guard WCSession.default.activationState == .activated else { return }

        let context: [String: Any] = [
            "safetyScore": KagamiAPIService.shared.lastSafetyScore ?? 0.85,
            "heroScene": determineHeroScene(),
            "timestamp": Date().timeIntervalSince1970
        ]

        try? WCSession.default.updateApplicationContext(context)
    }
}
```

### Watch Side

```swift
// KagamiWatchOSApp.swift
import SwiftUI
import WatchConnectivity

@main
struct KagamiWatchOSApp: App {
    @StateObject private var sessionManager = WatchSessionManager.shared

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(sessionManager)
        }
    }
}

// WatchSessionManager.swift
class WatchSessionManager: NSObject, ObservableObject, WCSessionDelegate {
    static let shared = WatchSessionManager()

    @Published var safetyScore: Double = 0.85
    @Published var heroScene: String = "Movie Mode"
    @Published var isConnected: Bool = false

    override init() {
        super.init()
        if WCSession.isSupported() {
            WCSession.default.delegate = self
            WCSession.default.activate()
        }
    }

    func session(_ session: WCSession, activationDidCompleteWith state: WCSessionActivationState, error: Error?) {
        DispatchQueue.main.async {
            self.isConnected = state == .activated
        }
    }

    func session(_ session: WCSession, didReceiveApplicationContext context: [String: Any]) {
        DispatchQueue.main.async {
            if let score = context["safetyScore"] as? Double {
                self.safetyScore = score
            }
            if let scene = context["heroScene"] as? String {
                self.heroScene = scene
            }
        }
    }

    func activateScene(_ sceneName: String) {
        WCSession.default.sendMessage(
            ["action": "activateScene", "scene": sceneName],
            replyHandler: nil,
            errorHandler: nil
        )

        // Haptic feedback
        WKInterfaceDevice.current().play(.success)
    }
}
```

## Complications

### Supported Families

- `.graphicCircular` - Safety gauge
- `.graphicCorner` - Safety score with icon
- `.graphicRectangular` - Full status with scene
- `.modularSmall` - Safety number
- `.utilitarianSmall` - Safety indicator

### Implementation

```swift
// ComplicationController.swift
import ClockKit

class ComplicationController: NSObject, CLKComplicationDataSource {

    func getCurrentTimelineEntry(
        for complication: CLKComplication,
        withHandler handler: @escaping (CLKComplicationTimelineEntry?) -> Void
    ) {
        let safetyScore = WatchSessionManager.shared.safetyScore

        switch complication.family {
        case .graphicCircular:
            let template = CLKComplicationTemplateGraphicCircularClosedGaugeText(
                gaugeProvider: CLKSimpleGaugeProvider(
                    style: .fill,
                    gaugeColor: safetyColor(for: safetyScore),
                    fillFraction: Float(safetyScore)
                ),
                centerTextProvider: CLKSimpleTextProvider(text: "鏡")
            )
            handler(CLKComplicationTimelineEntry(date: Date(), complicationTemplate: template))

        case .graphicCorner:
            let template = CLKComplicationTemplateGraphicCornerGaugeText(
                gaugeProvider: CLKSimpleGaugeProvider(
                    style: .fill,
                    gaugeColor: safetyColor(for: safetyScore),
                    fillFraction: Float(safetyScore)
                ),
                outerTextProvider: CLKSimpleTextProvider(text: String(format: "%.0f", safetyScore * 100))
            )
            handler(CLKComplicationTimelineEntry(date: Date(), complicationTemplate: template))

        default:
            handler(nil)
        }
    }

    private func safetyColor(for score: Double) -> UIColor {
        if score >= 0.5 { return UIColor(red: 0, green: 1, blue: 0.53, alpha: 1) } // #00ff88
        if score >= 0 { return UIColor(red: 1, green: 0.84, blue: 0, alpha: 1) }   // #ffd700
        return UIColor(red: 1, green: 0.27, blue: 0.27, alpha: 1)                  // #ff4444
    }
}
```

## Adding Watch Target

1. In Xcode: File > New > Target > watchOS > Watch App
2. Name: KagamiWatchOS
3. Bundle ID: com.kagami.ios.watchos
4. Add WatchKit extension
5. Enable Watch Connectivity in both targets

## Design Guidelines

- Use dark backgrounds (void colors)
- Large tap targets (44pt minimum)
- Clear typography (SF Pro Rounded)
- Colony accent colors
- Haptic feedback for all actions

## h(x) >= 0. Always.
