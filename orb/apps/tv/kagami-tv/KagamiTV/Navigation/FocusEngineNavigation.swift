//
// FocusEngineNavigation.swift -- Proper tvOS Focus Engine Integration
//
// Kagami TV -- Focus navigation system for tvOS
//
// Colony: Flow (e3) -- Execution
//
// Per KAGAMI_REDESIGN_PLAN.md: Implement proper focus engine navigation
//
// Features:
// - Focus environment integration with SwiftUI
// - Custom focus guides for complex layouts
// - Focus restoration across navigation
// - Visual focus indicators with Fibonacci timing
// - Sound effects on focus change
// - VoiceOver integration
//
// h(x) >= 0. Always.
//

import SwiftUI
import AVFoundation

// MARK: - Focus Navigation Manager

/// Manages focus state and navigation across the tvOS app
@MainActor
class FocusNavigationManager: ObservableObject {

    // MARK: - Published State

    @Published var currentFocusZone: FocusZone = .home
    @Published var focusHistory: [FocusZone] = []
    @Published var lastFocusedItem: [FocusZone: String] = [:]
    @Published var isFocusDebugEnabled = false

    // MARK: - Types

    /// Focus zones within the app
    enum FocusZone: String, CaseIterable, Identifiable {
        case home = "home"
        case rooms = "rooms"
        case quickActions = "quick_actions"
        case scenes = "scenes"
        case settings = "settings"
        case roomDetail = "room_detail"
        case deviceControl = "device_control"
        case tabBar = "tab_bar"

        var id: String { rawValue }

        /// User-friendly name for VoiceOver
        var accessibilityLabel: String {
            switch self {
            case .home: return "Home Dashboard"
            case .rooms: return "Room Controls"
            case .quickActions: return "Quick Actions"
            case .scenes: return "Scenes"
            case .settings: return "Settings"
            case .roomDetail: return "Room Detail"
            case .deviceControl: return "Device Control"
            case .tabBar: return "Navigation"
            }
        }
    }

    // MARK: - Audio Feedback

    private var focusSoundPlayer: AVAudioPlayer?
    private var selectSoundPlayer: AVAudioPlayer?

    // MARK: - Init

    init() {
        setupAudioFeedback()
    }

    private func setupAudioFeedback() {
        // Focus change sound
        if let url = Bundle.main.url(forResource: "focus_change", withExtension: "m4a") {
            focusSoundPlayer = try? AVAudioPlayer(contentsOf: url)
            focusSoundPlayer?.prepareToPlay()
            focusSoundPlayer?.volume = 0.3
        }

        // Selection sound
        if let url = Bundle.main.url(forResource: "select", withExtension: "m4a") {
            selectSoundPlayer = try? AVAudioPlayer(contentsOf: url)
            selectSoundPlayer?.prepareToPlay()
            selectSoundPlayer?.volume = 0.5
        }
    }

    // MARK: - Focus Management

    /// Navigate to a focus zone
    func navigateTo(_ zone: FocusZone) {
        // Save current zone to history
        if currentFocusZone != zone {
            focusHistory.append(currentFocusZone)

            // Keep history limited
            if focusHistory.count > 10 {
                focusHistory.removeFirst()
            }
        }

        currentFocusZone = zone
        playFocusSound()

        if isFocusDebugEnabled {
            print("[FocusNav] Navigated to: \(zone.rawValue)")
        }
    }

    /// Go back to previous focus zone
    func navigateBack() -> Bool {
        guard let previousZone = focusHistory.popLast() else {
            return false
        }

        currentFocusZone = previousZone
        playFocusSound()
        return true
    }

    /// Remember last focused item in a zone
    func rememberFocusedItem(_ itemId: String, in zone: FocusZone) {
        lastFocusedItem[zone] = itemId
    }

    /// Get last focused item in a zone
    func getLastFocusedItem(in zone: FocusZone) -> String? {
        return lastFocusedItem[zone]
    }

    // MARK: - Audio

    func playFocusSound() {
        focusSoundPlayer?.currentTime = 0
        focusSoundPlayer?.play()
    }

    func playSelectSound() {
        selectSoundPlayer?.currentTime = 0
        selectSoundPlayer?.play()
    }
}

// MARK: - Focus Zone Environment Key

private struct FocusZoneKey: EnvironmentKey {
    static let defaultValue: FocusNavigationManager.FocusZone = .home
}

extension EnvironmentValues {
    var focusZone: FocusNavigationManager.FocusZone {
        get { self[FocusZoneKey.self] }
        set { self[FocusZoneKey.self] = newValue }
    }
}

// MARK: - Focusable Card Style

/// A card style that properly responds to tvOS focus engine
struct TVFocusableCardStyle: ButtonStyle {
    let color: Color
    let cornerRadius: CGFloat

    init(color: Color = .white.opacity(0.1), cornerRadius: CGFloat = 16) {
        self.color = color
        self.cornerRadius = cornerRadius
    }

    @Environment(\.isFocused) private var isFocused

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .padding(24)
            .background(
                RoundedRectangle(cornerRadius: cornerRadius)
                    .fill(configuration.isPressed ? color.opacity(0.4) : color)
            )
            .overlay(
                RoundedRectangle(cornerRadius: cornerRadius)
                    .stroke(
                        Color.white.opacity(configuration.isPressed ? 0.6 : 0.2),
                        lineWidth: configuration.isPressed ? 3 : 1
                    )
            )
            .scaleEffect(configuration.isPressed ? 0.96 : 1.0)
            .animation(.easeOut(duration: 0.144), value: configuration.isPressed) // Fibonacci 144ms
    }
}

// MARK: - Focus Scale Effect Modifier

/// Applies proper tvOS focus scaling with Fibonacci timing
struct TVFocusScaleModifier: ViewModifier {
    @Environment(\.isFocused) private var isFocused
    let scale: CGFloat
    let shadowRadius: CGFloat

    init(scale: CGFloat = 1.08, shadowRadius: CGFloat = 20) {
        self.scale = scale
        self.shadowRadius = shadowRadius
    }

    func body(content: Content) -> some View {
        content
            .scaleEffect(isFocused ? scale : 1.0)
            .shadow(
                color: .white.opacity(isFocused ? 0.3 : 0),
                radius: isFocused ? shadowRadius : 0
            )
            .animation(.spring(response: 0.233, dampingFraction: 0.8), value: isFocused) // Fibonacci 233ms
            .accessibilityAddTraits(isFocused ? .isSelected : [])
    }
}

extension View {
    /// Applies standard tvOS focus scaling effect
    func tvFocusScale(_ scale: CGFloat = 1.08, shadowRadius: CGFloat = 20) -> some View {
        modifier(TVFocusScaleModifier(scale: scale, shadowRadius: shadowRadius))
    }
}

// MARK: - Focus Guide View

/// Creates a focus guide region for directing focus movement
struct FocusGuideView: View {
    let targets: [FocusGuideTarget]

    var body: some View {
        GeometryReader { geometry in
            ForEach(targets) { target in
                Rectangle()
                    .fill(Color.clear)
                    .frame(width: target.size.width, height: target.size.height)
                    .position(target.position)
                    .focusable(true)
                    .onMoveCommand { direction in
                        handleMove(direction, from: target)
                    }
            }
        }
    }

    private func handleMove(_ direction: MoveCommandDirection, from target: FocusGuideTarget) {
        // Handle custom focus movement based on direction
        switch direction {
        case .up: break
        case .down: break
        case .left: break
        case .right: break
        @unknown default: break
        }
    }
}

struct FocusGuideTarget: Identifiable {
    let id: String
    let position: CGPoint
    let size: CGSize
    let redirectsTo: String?
}

// MARK: - Focusable Grid Section

/// A grid section with proper focus handling for tvOS
struct TVFocusableGrid<Content: View, Item: Identifiable>: View {
    let items: [Item]
    let columns: Int
    let spacing: CGFloat
    let zone: FocusNavigationManager.FocusZone
    let content: (Item) -> Content

    @EnvironmentObject private var focusManager: FocusNavigationManager
    @FocusState private var focusedItemId: Item.ID?

    init(
        items: [Item],
        columns: Int = 4,
        spacing: CGFloat = 32,
        zone: FocusNavigationManager.FocusZone = .home,
        @ViewBuilder content: @escaping (Item) -> Content
    ) {
        self.items = items
        self.columns = columns
        self.spacing = spacing
        self.zone = zone
        self.content = content
    }

    var body: some View {
        let gridColumns = Array(repeating: GridItem(.flexible(), spacing: spacing), count: columns)

        LazyVGrid(columns: gridColumns, spacing: spacing) {
            ForEach(items) { item in
                content(item)
                    .focusable(true)
                    .focused($focusedItemId, equals: item.id)
                    .tvFocusScale()
                    .onChange(of: focusedItemId) { _, newValue in
                        if let id = newValue, String(describing: id) == String(describing: item.id) {
                            focusManager.rememberFocusedItem(String(describing: item.id), in: zone)
                            focusManager.playFocusSound()
                        }
                    }
            }
        }
        .environment(\.focusZone, zone)
        .onAppear {
            // Restore last focused item
            if let lastId = focusManager.getLastFocusedItem(in: zone) {
                // Try to restore focus
                for item in items {
                    if String(describing: item.id) == lastId {
                        focusedItemId = item.id
                        break
                    }
                }
            }
        }
    }
}

// MARK: - Focus Section Header

/// A section header that can receive focus for VoiceOver navigation
struct TVFocusSectionHeader: View {
    let title: String
    let zone: FocusNavigationManager.FocusZone

    var body: some View {
        Text(title)
            .font(.system(size: 32, weight: .semibold))
            .foregroundColor(.white.opacity(0.8))
            .frame(maxWidth: .infinity, alignment: .leading)
            .accessibilityAddTraits(.isHeader)
            .accessibilityLabel("\(title) section")
    }
}

// MARK: - Focus Debug Overlay

/// Debug overlay showing current focus state (only in DEBUG builds)
struct FocusDebugOverlay: View {
    @EnvironmentObject private var focusManager: FocusNavigationManager

    var body: some View {
        #if DEBUG
        if focusManager.isFocusDebugEnabled {
            VStack(alignment: .leading, spacing: 8) {
                Text("Focus Debug")
                    .font(.headline)
                    .foregroundColor(.yellow)

                Text("Zone: \(focusManager.currentFocusZone.rawValue)")
                    .font(.caption)
                    .foregroundColor(.white)

                Text("History: \(focusManager.focusHistory.count) items")
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.7))
            }
            .padding()
            .background(Color.black.opacity(0.8))
            .cornerRadius(8)
            .padding()
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .bottomLeading)
        }
        #endif
    }
}

// MARK: - Focus Restoration Modifier

/// Ensures focus is properly restored when navigating
struct FocusRestorationModifier: ViewModifier {
    let zone: FocusNavigationManager.FocusZone
    @EnvironmentObject private var focusManager: FocusNavigationManager

    func body(content: Content) -> some View {
        content
            .environment(\.focusZone, zone)
            .onAppear {
                focusManager.navigateTo(zone)
            }
    }
}

extension View {
    /// Marks this view as a focus zone for proper restoration
    func focusZone(_ zone: FocusNavigationManager.FocusZone) -> some View {
        modifier(FocusRestorationModifier(zone: zone))
    }
}

// MARK: - Focus Sound Player

/// Plays focus change sounds using system audio
class FocusSoundPlayer {
    static let shared = FocusSoundPlayer()

    private var audioEngine: AVAudioEngine?
    private var playerNode: AVAudioPlayerNode?

    private init() {
        setupAudioEngine()
    }

    private func setupAudioEngine() {
        audioEngine = AVAudioEngine()
        playerNode = AVAudioPlayerNode()

        guard let engine = audioEngine, let player = playerNode else { return }

        engine.attach(player)
        engine.connect(player, to: engine.mainMixerNode, format: nil)

        do {
            try engine.start()
        } catch {
            print("[FocusSound] Failed to start audio engine: \(error)")
        }
    }

    /// Play a focus tick sound
    func playFocusTick() {
        // Generate a subtle tick sound
        guard let engine = audioEngine, let player = playerNode else { return }

        let sampleRate = 44100.0
        let duration = 0.05 // 50ms
        let frequency: Float = 880 // A5

        guard let format = AVAudioFormat(standardFormatWithSampleRate: sampleRate, channels: 1),
              let buffer = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: AVAudioFrameCount(sampleRate * duration)) else {
            return
        }

        buffer.frameLength = buffer.frameCapacity

        guard let floatData = buffer.floatChannelData?[0] else { return }

        for frame in 0..<Int(buffer.frameLength) {
            let progress = Float(frame) / Float(buffer.frameLength)
            let envelope = sinf(.pi * progress) // Smooth envelope
            let sample = sinf(2.0 * .pi * frequency * Float(frame) / Float(sampleRate))
            floatData[frame] = sample * envelope * 0.1 // Low volume
        }

        player.scheduleBuffer(buffer, at: nil, options: .interrupts)
        player.play()
    }

    /// Play a select sound
    func playSelect() {
        guard let engine = audioEngine, let player = playerNode else { return }

        let sampleRate = 44100.0
        let duration = 0.1
        let frequency: Float = 1320 // E6

        guard let format = AVAudioFormat(standardFormatWithSampleRate: sampleRate, channels: 1),
              let buffer = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: AVAudioFrameCount(sampleRate * duration)) else {
            return
        }

        buffer.frameLength = buffer.frameCapacity

        guard let floatData = buffer.floatChannelData?[0] else { return }

        for frame in 0..<Int(buffer.frameLength) {
            let progress = Float(frame) / Float(buffer.frameLength)
            let envelope = sinf(.pi * progress)
            let sample = sinf(2.0 * .pi * frequency * Float(frame) / Float(sampleRate))
            floatData[frame] = sample * envelope * 0.15
        }

        player.scheduleBuffer(buffer, at: nil, options: .interrupts)
        player.play()
    }
}

// MARK: - Focus View Modifier for Sound

/// Plays sound on focus change
struct FocusSoundModifier: ViewModifier {
    @Environment(\.isFocused) private var isFocused
    @State private var wasEverFocused = false

    func body(content: Content) -> some View {
        content
            .onChange(of: isFocused) { _, newValue in
                if newValue && wasEverFocused {
                    FocusSoundPlayer.shared.playFocusTick()
                }
                wasEverFocused = true
            }
    }
}

extension View {
    /// Plays a focus sound when this view receives focus
    func focusSound() -> some View {
        modifier(FocusSoundModifier())
    }
}

/*
 * Mirror
 * h(x) >= 0. Always.
 *
 * Focus is intent made visible.
 * The highlight follows attention.
 * Navigation without friction.
 */
