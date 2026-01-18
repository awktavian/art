//
// EarconService.swift — BBC Symphony Orchestra Earcons for iOS
//
// Colony: Nexus (e₄) — Integration
//
// Features:
//   - 36 BBC Symphony Orchestra earcons (REAPER + BBC SO VST)
//   - Tier 1 earcons bundled with app for instant playback
//   - Tier 2 earcons lazy-loaded from CDN
//   - Integrated with KagamiHaptics for coordinated feedback
//   - Spatial audio support via AVAudioEngine
//
// Architecture:
//   Event → EarconService → AVAudioEngine → Spatial Output
//                        → KagamiHaptics → Taptic Engine
//
// Created: January 12, 2026
// 鏡

import AVFoundation
import Combine

/// Service for playing BBC Symphony Orchestra earcons
@MainActor
final class EarconService: ObservableObject {

    // MARK: - Singleton

    static let shared = EarconService()

    // MARK: - Published State

    @Published var isInitialized = false
    @Published var isMuted = false
    @Published var masterVolume: Float = 0.7
    @Published var tier1Loaded = false

    // MARK: - Types

    /// Available earcons (36 total)
    enum Earcon: String, CaseIterable {
        // Tier 1 — Core (14 bundled)
        case notification
        case success
        case error
        case alert
        case arrival
        case departure
        case celebration
        case settling
        case awakening
        case cinematic
        case focus
        case securityArm = "security_arm"
        case package
        case meetingSoon = "meeting_soon"

        // Tier 2 — Extended (22 CDN)
        case roomEnter = "room_enter"
        case doorOpen = "door_open"
        case doorClose = "door_close"
        case lockEngaged = "lock_engaged"
        case voiceAcknowledge = "voice_acknowledge"
        case voiceComplete = "voice_complete"
        case washerComplete = "washer_complete"
        case coffeeReady = "coffee_ready"
        case morningSequence = "morning_sequence"
        case eveningTransition = "evening_transition"
        case midnight
        case stormApproaching = "storm_approaching"
        case rainStarting = "rain_starting"
        case motionDetected = "motion_detected"
        case cameraAlert = "camera_alert"
        case messageReceived = "message_received"
        case homeEmpty = "home_empty"
        case firstHome = "first_home"
        case ovenPreheat = "oven_preheat"
        case dishwasherComplete = "dishwasher_complete"
        case dryerComplete = "dryer_complete"

        /// Whether this earcon is bundled (Tier 1)
        var isTier1: Bool {
            switch self {
            case .notification, .success, .error, .alert, .arrival, .departure,
                 .celebration, .settling, .awakening, .cinematic, .focus,
                 .securityArm, .package, .meetingSoon:
                return true
            default:
                return false
            }
        }

        /// Corresponding haptic pattern
        var hapticPattern: HapticPattern {
            switch self {
            case .success, .celebration, .arrival:
                return .success
            case .error:
                return .error
            case .alert, .cameraAlert:
                return .warning
            case .notification, .messageReceived, .package:
                return .mediumImpact
            case .focus, .roomEnter:
                return .lightImpact
            case .lockEngaged, .securityArm:
                return .heavyImpact
            case .departure, .settling, .homeEmpty:
                return .softImpact
            case .voiceAcknowledge:
                return .selection
            case .voiceComplete:
                return .success
            default:
                return .lightImpact
            }
        }
    }

    /// Semantic feedback events that map to earcons
    enum FeedbackEvent: String {
        case tap
        case select
        case sceneActivated
        case lightsOn
        case lightsOff
        case shadeOpen
        case shadeClose

        var earcon: Earcon {
            switch self {
            case .tap, .select:
                return .focus
            case .sceneActivated:
                return .success
            case .lightsOn, .shadeOpen:
                return .doorOpen
            case .lightsOff, .shadeClose:
                return .doorClose
            }
        }
    }

    // MARK: - Private State

    private var audioEngine: AVAudioEngine?
    private var playerNode: AVAudioPlayerNode?
    private var mixerNode: AVAudioMixerNode?
    private var environmentNode: AVAudioEnvironmentNode?

    /// Cached audio buffers
    private var bufferCache: [String: AVAudioPCMBuffer] = [:]

    /// Loading tasks
    private var loadingTasks: [String: Task<Bool, Never>] = [:]

    /// CDN base URL
    private let cdnBaseURL = "https://storage.googleapis.com/kagami-media-public/earcons/v1/aac"

    // MARK: - Init

    private init() {
        Task {
            await initialize()
        }
    }

    // MARK: - Initialization

    func initialize() async {
        guard !isInitialized else { return }

        do {
            // Configure audio session
            let session = AVAudioSession.sharedInstance()
            try session.setCategory(.playback, mode: .default, options: [.mixWithOthers])
            try session.setActive(true)

            // Setup audio engine
            audioEngine = AVAudioEngine()
            playerNode = AVAudioPlayerNode()
            environmentNode = AVAudioEnvironmentNode()

            guard let engine = audioEngine,
                  let player = playerNode,
                  let environment = environmentNode else {
                print("EarconService: Failed to create audio nodes")
                return
            }

            engine.attach(player)
            engine.attach(environment)

            // Connect: player -> environment -> main output
            let format = AVAudioFormat(standardFormatWithSampleRate: 48000, channels: 2)!
            engine.connect(player, to: environment, format: format)
            engine.connect(environment, to: engine.mainMixerNode, format: format)

            // Configure spatial environment
            environment.listenerPosition = AVAudio3DPoint(x: 0, y: 0, z: 0)
            environment.renderingAlgorithm = .auto

            try engine.start()

            isInitialized = true
            print("EarconService: Initialized")

            // Preload Tier 1 earcons
            await preloadTier1()

        } catch {
            print("EarconService: Initialization failed - \(error)")
        }
    }

    /// Preload all Tier 1 earcons from bundle
    func preloadTier1() async {
        let tier1Earcons = Earcon.allCases.filter { $0.isTier1 }

        var loadedCount = 0
        for earcon in tier1Earcons {
            if await loadFromBundle(earcon.rawValue) {
                loadedCount += 1
            }
        }

        tier1Loaded = loadedCount > 0
        print("EarconService: Loaded \(loadedCount)/\(tier1Earcons.count) Tier 1 earcons")
    }

    // MARK: - Playback

    /// Play an earcon with optional haptic feedback
    /// - Parameters:
    ///   - earcon: The earcon to play
    ///   - withHaptic: Whether to also trigger haptic feedback
    ///   - position: Optional 3D position for spatial audio
    func play(_ earcon: Earcon, withHaptic: Bool = true, position: AVAudio3DPoint? = nil) {
        guard isInitialized, !isMuted else { return }

        // Play haptic first (lower latency)
        if withHaptic {
            KagamiHaptics.shared.play(earcon.hapticPattern)
        }

        // Play audio
        Task {
            await playAudio(earcon.rawValue, at: position)
        }
    }

    /// Play a semantic feedback event
    func play(_ event: FeedbackEvent, withHaptic: Bool = true) {
        play(event.earcon, withHaptic: withHaptic)
    }

    /// Play an earcon by name (for dynamic usage)
    func play(named name: String, withHaptic: Bool = true) {
        guard let earcon = Earcon(rawValue: name) else {
            print("EarconService: Unknown earcon: \(name)")
            return
        }
        play(earcon, withHaptic: withHaptic)
    }

    // MARK: - Audio Playback

    private func playAudio(_ name: String, at position: AVAudio3DPoint?) async {
        guard let player = playerNode, let environment = environmentNode else { return }

        // Get or load buffer
        let buffer: AVAudioPCMBuffer?
        if let cached = bufferCache[name] {
            buffer = cached
        } else {
            // Try bundle first, then CDN
            var loaded = await loadFromBundle(name)
            if !loaded {
                loaded = await loadFromCDN(name)
            }
            if loaded {
                buffer = bufferCache[name]
            } else {
                print("EarconService: Failed to load earcon: \(name)")
                return
            }
        }

        guard let audioBuffer = buffer else { return }

        // Set spatial position
        if let pos = position {
            environment.listenerPosition = pos
        }

        // Set volume
        player.volume = masterVolume

        // Stop any current playback
        if player.isPlaying {
            player.stop()
        }

        // Play
        await player.scheduleBuffer(audioBuffer, at: nil, options: .interrupts)
        player.play()
    }

    // MARK: - Loading

    private func loadFromBundle(_ name: String) async -> Bool {
        guard bufferCache[name] == nil else { return true }

        guard let url = Bundle.main.url(forResource: name, withExtension: "m4a", subdirectory: "Earcons") else {
            return false
        }

        do {
            let file = try AVAudioFile(forReading: url)
            let format = file.processingFormat
            let frameCount = AVAudioFrameCount(file.length)

            guard let buffer = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: frameCount) else {
                return false
            }

            try file.read(into: buffer)
            bufferCache[name] = buffer

            print("EarconService: Loaded from bundle: \(name)")
            return true

        } catch {
            print("EarconService: Bundle load failed for \(name): \(error)")
            return false
        }
    }

    private func loadFromCDN(_ name: String) async -> Bool {
        guard bufferCache[name] == nil else { return true }

        // Check for existing task
        if let existingTask = loadingTasks[name] {
            return await existingTask.value
        }

        let task = Task<Bool, Never> {
            guard let url = URL(string: "\(cdnBaseURL)/\(name).m4a") else {
                print("EarconService: Invalid CDN URL for \(name)")
                return false
            }

            do {
                let (data, response) = try await URLSession.shared.data(from: url)

                guard let httpResponse = response as? HTTPURLResponse,
                      httpResponse.statusCode == 200 else {
                    return false
                }

                // Write to temp file
                let tempURL = FileManager.default.temporaryDirectory.appendingPathComponent("\(name).m4a")
                try data.write(to: tempURL)

                let file = try AVAudioFile(forReading: tempURL)
                let format = file.processingFormat
                let frameCount = AVAudioFrameCount(file.length)

                guard let buffer = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: frameCount) else {
                    return false
                }

                try file.read(into: buffer)
                bufferCache[name] = buffer

                // Clean up
                try? FileManager.default.removeItem(at: tempURL)

                print("EarconService: Downloaded from CDN: \(name)")
                return true

            } catch {
                print("EarconService: CDN download failed for \(name): \(error)")
                return false
            }
        }

        loadingTasks[name] = task
        let result = await task.value
        loadingTasks.removeValue(forKey: name)
        return result
    }

    // MARK: - Volume Control

    func setVolume(_ volume: Float) {
        masterVolume = max(0, min(1, volume))
    }

    func mute() {
        isMuted = true
    }

    func unmute() {
        isMuted = false
    }

    // MARK: - Utility

    /// Check if an earcon is loaded
    func isLoaded(_ earcon: Earcon) -> Bool {
        bufferCache[earcon.rawValue] != nil
    }

    /// Preload specific earcons
    func preload(_ earcons: [Earcon]) async {
        for earcon in earcons {
            if !bufferCache.keys.contains(earcon.rawValue) {
                _ = earcon.isTier1
                    ? await loadFromBundle(earcon.rawValue)
                    : await loadFromCDN(earcon.rawValue)
            }
        }
    }

    /// Clear cache (for memory pressure)
    func clearCache() {
        let tier1Names = Set(Earcon.allCases.filter { $0.isTier1 }.map { $0.rawValue })
        // Keep Tier 1, clear Tier 2
        bufferCache = bufferCache.filter { tier1Names.contains($0.key) }
    }
}

/*
 * 鏡
 * h(x) >= 0. Always.
 *
 * BBC Symphony Orchestra earcons provide virtuoso audio feedback.
 * Each earcon is a complete musical phrase with emotional intent.
 * Coordinated with haptics for multi-sensory experience.
 */
