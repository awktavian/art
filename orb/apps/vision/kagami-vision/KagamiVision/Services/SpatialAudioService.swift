//
// SpatialAudioService.swift — 3D Audio for Spatial UI with BBC Orchestra Earcons
//
// Colony: Nexus (e₄) — Integration
//
// Features:
//   - BBC Symphony Orchestra earcons for rich audio feedback
//   - Spatial audio sources in 3D space via PHASE engine
//   - Audio feedback for interactions with orchestral quality
//   - Ambient soundscapes tied to room state
//   - Head-tracked audio rendering
//   - Fallback tone synthesis when earcons unavailable
//
// Architecture:
//   UI Events → SpatialAudioService → PHASE Engine (earcons) → Spatial Speakers
//                                   ↘ AVAudioEngine (fallback)
//
// Earcon Tiers:
//   - Tier 1 (14 core): Bundled with app for instant playback
//   - Tier 2 (22 extended): Lazy-loaded from CDN
//
// Created: December 31, 2025
// Updated: January 12, 2026 — BBC Orchestra earcon integration
// 鏡

import Foundation
import AVFoundation
import PHASE
import Combine
import os.log

/// Manages spatial audio for immersive UI feedback
@MainActor
class SpatialAudioService: ObservableObject {

    // MARK: - Published State

    @Published var isInitialized = false
    @Published var isMuted = false
    @Published var masterVolume: Double = 0.8

    // MARK: - Types

    /// Audio event types for UI feedback
    /// Maps to BBC Symphony Orchestra earcons for rich audio
    enum AudioEvent: String, CaseIterable {
        case tap = "tap"
        case select = "select"
        case success = "success"
        case error = "error"
        case notification = "notification"
        case ambientPulse = "ambient_pulse"
        case orbActivate = "orb_activate"
        case sceneChange = "scene_change"
        case lightOn = "light_on"
        case lightOff = "light_off"
        case shadeOpen = "shade_open"
        case shadeClose = "shade_close"
        case arrival = "arrival"
        case departure = "departure"
        case lockEngaged = "lock_engaged"
        case securityArm = "security_arm"
        case voiceAcknowledge = "voice_acknowledge"
        case voiceComplete = "voice_complete"
        case celebration = "celebration"
        case warning = "warning"

        /// Maps to BBC Orchestra earcon name
        var earconName: String {
            switch self {
            case .tap: return "focus"
            case .select: return "focus"
            case .success: return "success"
            case .error: return "error"
            case .notification: return "notification"
            case .ambientPulse: return "room_enter"
            case .orbActivate: return "voice_acknowledge"
            case .sceneChange: return "success"
            case .lightOn: return "door_open"
            case .lightOff: return "door_close"
            case .shadeOpen: return "door_open"
            case .shadeClose: return "door_close"
            case .arrival: return "arrival"
            case .departure: return "departure"
            case .lockEngaged: return "lock_engaged"
            case .securityArm: return "security_arm"
            case .voiceAcknowledge: return "voice_acknowledge"
            case .voiceComplete: return "voice_complete"
            case .celebration: return "celebration"
            case .warning: return "alert"
            }
        }

        /// Whether this earcon is Tier 1 (bundled)
        var isTier1: Bool {
            let tier1 = ["notification", "success", "error", "alert", "arrival", "departure",
                        "celebration", "settling", "awakening", "cinematic", "focus",
                        "security_arm", "package", "meeting_soon"]
            return tier1.contains(earconName)
        }

        /// Fallback synthesized tone parameters (used when earcon unavailable)
        var toneParams: ToneParameters {
            switch self {
            case .tap:
                return ToneParameters(frequency: 880, duration: 0.05, envelope: .sharp)
            case .select:
                return ToneParameters(frequency: 1047, duration: 0.1, envelope: .soft)
            case .success:
                return ToneParameters(frequency: 1318, duration: 0.2, envelope: .soft)
            case .error:
                return ToneParameters(frequency: 220, duration: 0.3, envelope: .harsh)
            case .notification:
                return ToneParameters(frequency: 659, duration: 0.15, envelope: .soft)
            case .ambientPulse:
                return ToneParameters(frequency: 330, duration: 1.0, envelope: .ambient)
            case .orbActivate:
                return ToneParameters(frequency: 523, duration: 0.25, envelope: .soft)
            case .sceneChange:
                return ToneParameters(frequency: 440, duration: 0.5, envelope: .soft)
            case .lightOn:
                return ToneParameters(frequency: 698, duration: 0.1, envelope: .soft)
            case .lightOff:
                return ToneParameters(frequency: 349, duration: 0.1, envelope: .soft)
            case .shadeOpen:
                return ToneParameters(frequency: 392, duration: 0.2, envelope: .soft)
            case .shadeClose:
                return ToneParameters(frequency: 262, duration: 0.2, envelope: .soft)
            case .arrival:
                return ToneParameters(frequency: 523, duration: 0.4, envelope: .soft)
            case .departure:
                return ToneParameters(frequency: 392, duration: 0.4, envelope: .soft)
            case .lockEngaged:
                return ToneParameters(frequency: 880, duration: 0.15, envelope: .sharp)
            case .securityArm:
                return ToneParameters(frequency: 659, duration: 0.2, envelope: .soft)
            case .voiceAcknowledge:
                return ToneParameters(frequency: 784, duration: 0.1, envelope: .soft)
            case .voiceComplete:
                return ToneParameters(frequency: 1047, duration: 0.15, envelope: .soft)
            case .celebration:
                return ToneParameters(frequency: 1318, duration: 0.5, envelope: .soft)
            case .warning:
                return ToneParameters(frequency: 440, duration: 0.3, envelope: .harsh)
            }
        }
    }

    struct ToneParameters {
        let frequency: Float
        let duration: TimeInterval
        let envelope: ToneEnvelope

        enum ToneEnvelope {
            case sharp   // Quick attack/release
            case soft    // Smooth attack/release
            case harsh   // Sharp attack, medium release
            case ambient // Very slow attack/release
        }
    }

    /// A positioned audio source in 3D space
    struct SpatialSource: Identifiable {
        let id: UUID
        var position: SIMD3<Float>
        let event: AudioEvent
        var isPlaying: Bool
    }

    // MARK: - Internal State

    private var phaseEngine: PHASEEngine?
    private var listener: PHASEListener?
    private var spatialMixerDefinition: PHASESpatialMixerDefinition?
    private var activeSources: [UUID: PHASESource] = [:]

    // Audio synthesis (fallback)
    private var audioEngine: AVAudioEngine?
    private var tonePlayer: AVAudioPlayerNode?
    private var spatialMixer: AVAudioEnvironmentNode?

    // BBC Orchestra earcon playback
    private var earconPlayer: AVAudioPlayerNode?
    private var earconCache: [String: AVAudioPCMBuffer] = [:]
    private var earconLoadingTasks: [String: Task<Void, Never>] = [:]
    @Published var earconsLoaded = false

    // CDN base URL for Tier 2 earcons
    private let earconCDNBase = "https://storage.googleapis.com/kagami-media-public/earcons/v1/aac"

    // Hand tracking integration for dynamic listener positioning
    private weak var handTrackingService: HandTrackingService?
    private var handTrackingCancellables = Set<AnyCancellable>()

    // Accessibility: Audio-only navigation mode
    @Published var audioOnlyModeEnabled = false
    @Published var spatialDescriptionsEnabled = false

    // Prefer earcons over synthesized tones
    @Published var preferEarcons = true

    // MARK: - Init

    init() {
        Task {
            await initialize()
        }
    }

    // MARK: - Initialization

    func initialize() async {
        do {
            // Initialize PHASE engine for spatial audio
            phaseEngine = PHASEEngine(updateMode: .automatic)

            guard let engine = phaseEngine else {
                KagamiLogger.spatialAudio.error("Failed to create PHASE engine")
                return
            }

            // Create listener (represents the user's head position)
            listener = PHASEListener(engine: engine)
            listener?.transform = matrix_identity_float4x4
            try engine.rootObject.addChild(listener!)

            // Create spatial mixer for 3D positioning
            // Note: In visionOS 1.0, use channel mixer for simpler stereo spatialization
            // Full spatial pipeline requires visionOS 2.0+ APIs
            let channelLayout = AVAudioChannelLayout(layoutTag: kAudioChannelLayoutTag_Stereo)!
            let channelMixerDefinition = PHASEChannelMixerDefinition(channelLayout: channelLayout)
            // Use channel mixer instead of spatial mixer for visionOS 1.0 compatibility
            _ = channelMixerDefinition  // Store for later use if needed

            // Start the engine
            try engine.start()
            isInitialized = true
            KagamiLogger.spatialAudio.info("PHASE spatial audio initialized")

            // Also initialize AVAudioEngine for tone synthesis
            await initializeToneSynthesis()

        } catch {
            KagamiLogger.logError("Failed to initialize spatial audio", error: error, logger: KagamiLogger.spatialAudio)
            // Fallback to non-spatial audio
            await initializeFallbackAudio()
        }
    }

    private func initializeToneSynthesis() async {
        audioEngine = AVAudioEngine()
        tonePlayer = AVAudioPlayerNode()
        earconPlayer = AVAudioPlayerNode()
        spatialMixer = AVAudioEnvironmentNode()

        guard let engine = audioEngine,
              let player = tonePlayer,
              let earconPlayer = earconPlayer,
              let mixer = spatialMixer else { return }

        engine.attach(player)
        engine.attach(earconPlayer)
        engine.attach(mixer)

        // Connect: players -> spatial mixer -> main output
        let format = AVAudioFormat(standardFormatWithSampleRate: 48000, channels: 2)!
        engine.connect(player, to: mixer, format: format)
        engine.connect(earconPlayer, to: mixer, format: format)
        engine.connect(mixer, to: engine.mainMixerNode, format: format)

        // Configure spatial environment
        mixer.listenerPosition = AVAudio3DPoint(x: 0, y: 0, z: 0)
        mixer.listenerAngularOrientation = AVAudio3DAngularOrientation(yaw: 0, pitch: 0, roll: 0)
        mixer.renderingAlgorithm = .auto

        do {
            try engine.start()
            KagamiLogger.spatialAudio.info("Audio engine started (earcons + synthesis)")

            // Preload Tier 1 earcons for instant playback
            await preloadTier1Earcons()

        } catch {
            KagamiLogger.logError("Failed to start audio engine", error: error, logger: KagamiLogger.spatialAudio)
        }
    }

    /// Preload Tier 1 (core) earcons from bundle for instant playback
    private func preloadTier1Earcons() async {
        let tier1Earcons = ["notification", "success", "error", "alert", "arrival",
                          "departure", "celebration", "settling", "awakening",
                          "cinematic", "focus", "security_arm", "package", "meeting_soon"]

        var loadedCount = 0

        for name in tier1Earcons {
            if await loadEarconFromBundle(name: name) {
                loadedCount += 1
            }
        }

        earconsLoaded = loadedCount > 0
        KagamiLogger.spatialAudio.info("Loaded \(loadedCount)/\(tier1Earcons.count) Tier 1 earcons")
    }

    /// Load an earcon from the app bundle
    private func loadEarconFromBundle(name: String) async -> Bool {
        // Check if already cached
        if earconCache[name] != nil { return true }

        // Look for the earcon in the bundle (m4a format for iOS/visionOS)
        guard let url = Bundle.main.url(forResource: name, withExtension: "m4a", subdirectory: "Earcons") else {
            KagamiLogger.spatialAudio.debug("Earcon not in bundle: \(name)")
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
            earconCache[name] = buffer

            KagamiLogger.spatialAudio.debug("Loaded earcon: \(name) (\(frameCount) frames)")
            return true

        } catch {
            KagamiLogger.logError("Failed to load earcon: \(name)", error: error, logger: KagamiLogger.spatialAudio)
            return false
        }
    }

    /// Load an earcon from CDN (for Tier 2)
    private func loadEarconFromCDN(name: String) async -> Bool {
        // Check if already loading
        if earconLoadingTasks[name] != nil { return false }

        let url = URL(string: "\(earconCDNBase)/\(name).m4a")!

        do {
            let (data, _) = try await URLSession.shared.data(from: url)

            // Write to temporary file for AVAudioFile
            let tempURL = FileManager.default.temporaryDirectory.appendingPathComponent("\(name).m4a")
            try data.write(to: tempURL)

            let file = try AVAudioFile(forReading: tempURL)
            let format = file.processingFormat
            let frameCount = AVAudioFrameCount(file.length)

            guard let buffer = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: frameCount) else {
                return false
            }

            try file.read(into: buffer)
            earconCache[name] = buffer

            // Clean up temp file
            try? FileManager.default.removeItem(at: tempURL)

            KagamiLogger.spatialAudio.info("Downloaded earcon from CDN: \(name)")
            return true

        } catch {
            KagamiLogger.logError("Failed to download earcon: \(name)", error: error, logger: KagamiLogger.spatialAudio)
            return false
        }
    }

    private func initializeFallbackAudio() async {
        // Simple fallback without spatial positioning
        audioEngine = AVAudioEngine()
        tonePlayer = AVAudioPlayerNode()

        guard let engine = audioEngine, let player = tonePlayer else { return }

        engine.attach(player)
        engine.connect(player, to: engine.mainMixerNode, format: nil)

        do {
            try engine.start()
            KagamiLogger.spatialAudio.info("Fallback audio initialized")
        } catch {
            KagamiLogger.logError("Fallback audio failed", error: error, logger: KagamiLogger.spatialAudio)
        }
    }

    // MARK: - Playback

    /// Plays a spatial audio event at a position using BBC Orchestra earcons
    func play(_ event: AudioEvent, at position: SIMD3<Float>? = nil) {
        guard !isMuted else { return }

        let pos = position ?? SIMD3<Float>(0, 0, -0.5)  // Default in front of user

        // Update spatial mixer position
        if let mixer = spatialMixer {
            let avPosition = AVAudio3DPoint(x: pos.x, y: pos.y, z: pos.z)
            mixer.position = avPosition
        }

        // Try to play earcon first, fall back to synthesized tone
        if preferEarcons {
            Task {
                let earconPlayed = await playEarcon(event.earconName, at: pos)
                if !earconPlayed {
                    // Fallback to synthesized tone
                    await MainActor.run {
                        playTone(event.toneParams)
                    }
                }
            }
        } else {
            // Use synthesized tones only
            playTone(event.toneParams)
        }
    }

    /// Plays an earcon by name with spatial positioning
    func playEarcon(_ name: String, at position: SIMD3<Float>? = nil) async -> Bool {
        // Check cache first
        if let buffer = earconCache[name] {
            return await playEarconBuffer(buffer, at: position)
        }

        // Try to load from bundle
        if await loadEarconFromBundle(name: name) {
            if let buffer = earconCache[name] {
                return await playEarconBuffer(buffer, at: position)
            }
        }

        // Try CDN for Tier 2 earcons (fire and forget, play tone this time)
        Task {
            _ = await loadEarconFromCDN(name: name)
        }

        return false
    }

    /// Play an earcon buffer with spatial positioning
    private func playEarconBuffer(_ buffer: AVAudioPCMBuffer, at position: SIMD3<Float>?) async -> Bool {
        guard let player = earconPlayer, let mixer = spatialMixer else { return false }

        // Update spatial position
        if let pos = position {
            mixer.position = AVAudio3DPoint(x: pos.x, y: pos.y, z: pos.z)
        }

        // Stop any current playback
        if player.isPlaying {
            player.stop()
        }

        // Schedule and play
        await player.scheduleBuffer(buffer, at: nil, options: .interrupts)
        player.play()

        return true
    }

    /// Plays multiple tones in sequence (for complex events like scene changes)
    func playSequence(_ events: [AudioEvent], at position: SIMD3<Float>? = nil) {
        guard !isMuted else { return }

        Task {
            for (index, event) in events.enumerated() {
                await MainActor.run {
                    play(event, at: position)
                }
                try? await Task.sleep(nanoseconds: UInt64(event.toneParams.duration * 1_000_000_000))
            }
        }
    }

    /// Plays ambient spatial audio around the user
    func playAmbient(radius: Float = 2.0) {
        guard !isMuted else { return }

        // Play subtle tones in a circle around user
        let positions: [SIMD3<Float>] = [
            SIMD3<Float>(radius, 0, 0),
            SIMD3<Float>(-radius, 0, 0),
            SIMD3<Float>(0, 0, radius),
            SIMD3<Float>(0, 0, -radius),
        ]

        for pos in positions {
            Task {
                await MainActor.run {
                    play(.ambientPulse, at: pos)
                }
            }
        }
    }

    // MARK: - Tone Synthesis

    private func playTone(_ params: ToneParameters) {
        guard let engine = audioEngine, let player = tonePlayer else { return }

        let sampleRate = 44100.0
        let frameCount = AVAudioFrameCount(params.duration * sampleRate)

        guard let buffer = AVAudioPCMBuffer(
            pcmFormat: AVAudioFormat(standardFormatWithSampleRate: sampleRate, channels: 2)!,
            frameCapacity: frameCount
        ) else { return }

        buffer.frameLength = frameCount

        let amplitude = Float(masterVolume * 0.3)  // Keep it subtle
        let frequency = params.frequency

        guard let leftChannel = buffer.floatChannelData?[0],
              let rightChannel = buffer.floatChannelData?[1] else { return }

        for frame in 0..<Int(frameCount) {
            let progress = Float(frame) / Float(frameCount)
            let envelope = calculateEnvelope(progress, type: params.envelope)

            let sample = sinf(2.0 * .pi * frequency * Float(frame) / Float(sampleRate))
            let value = sample * amplitude * envelope

            leftChannel[frame] = value
            rightChannel[frame] = value
        }

        if player.isPlaying {
            player.stop()
        }

        player.scheduleBuffer(buffer, at: nil, options: .interrupts)
        player.play()
    }

    private func calculateEnvelope(_ progress: Float, type: ToneParameters.ToneEnvelope) -> Float {
        switch type {
        case .sharp:
            // Quick attack, quick release
            if progress < 0.1 { return progress * 10 }
            if progress > 0.7 { return (1 - progress) / 0.3 }
            return 1.0

        case .soft:
            // Sine-based smooth envelope
            return sinf(.pi * progress)

        case .harsh:
            // Sharp attack, medium release
            if progress < 0.05 { return progress * 20 }
            return max(0, 1 - (progress - 0.05) / 0.95)

        case .ambient:
            // Very slow attack and release
            if progress < 0.3 { return progress / 0.3 * 0.5 }
            if progress > 0.7 { return (1 - progress) / 0.3 * 0.5 }
            return 0.5
        }
    }

    // MARK: - Listener Position

    /// Updates the listener (head) position for spatial audio
    func updateListenerPosition(_ position: SIMD3<Float>, forward: SIMD3<Float>) {
        // Update PHASE listener
        if let listener = listener {
            var transform = matrix_identity_float4x4
            transform.columns.3 = SIMD4<Float>(position.x, position.y, position.z, 1)
            listener.transform = transform
        }

        // Update AVAudioEnvironmentNode
        if let mixer = spatialMixer {
            mixer.listenerPosition = AVAudio3DPoint(x: position.x, y: position.y, z: position.z)

            // Calculate yaw from forward vector
            let yaw = atan2(forward.x, -forward.z) * 180 / .pi
            mixer.listenerAngularOrientation = AVAudio3DAngularOrientation(yaw: yaw, pitch: 0, roll: 0)
        }
    }

    // MARK: - Volume Control

    func setMasterVolume(_ volume: Double) {
        masterVolume = max(0, min(1, volume))
        audioEngine?.mainMixerNode.outputVolume = Float(masterVolume)
    }

    func mute() {
        isMuted = true
    }

    func unmute() {
        isMuted = false
    }

    // MARK: - Hand Tracking Integration

    /// Connects spatial audio to hand tracking for dynamic listener positioning
    func connectToHandTracking(_ service: HandTrackingService) {
        self.handTrackingService = service

        // Subscribe to hand position updates for spatial audio positioning
        service.$leftHandPosition
            .combineLatest(service.$rightHandPosition)
            .receive(on: DispatchQueue.main)
            .sink { [weak self] leftPos, rightPos in
                self?.updateListenerFromHandPosition(leftPos, rightPos)
            }
            .store(in: &handTrackingCancellables)

        // Use gesture detection for audio feedback
        service.$currentGesture
            .receive(on: DispatchQueue.main)
            .sink { [weak self] gesture in
                self?.handleGestureAudioFeedback(gesture)
            }
            .store(in: &handTrackingCancellables)

        KagamiLogger.spatialAudio.info("Spatial audio connected to hand tracking")
    }

    /// Updates listener position based on hand tracking data
    private func updateListenerFromHandPosition(_ leftPos: SIMD3<Float>?, _ rightPos: SIMD3<Float>?) {
        // Calculate center point between hands (or use single hand if only one detected)
        var referencePosition: SIMD3<Float>?

        if let left = leftPos, let right = rightPos {
            referencePosition = (left + right) / 2
        } else if let left = leftPos {
            referencePosition = left
        } else if let right = rightPos {
            referencePosition = right
        }

        guard let position = referencePosition else { return }

        // Use hand position to influence audio spatialization
        // The listener represents head position, but we can use hand proximity
        // to create dynamic audio effects relative to user's hands
        if let mixer = spatialMixer {
            // Subtle adjustment: audio sources near hands become slightly louder
            let handInfluence: Float = 0.1
            let adjustedPosition = AVAudio3DPoint(
                x: position.x * handInfluence,
                y: position.y * handInfluence,
                z: position.z * handInfluence
            )

            // Apply subtle offset to create hand-relative audio awareness
            mixer.listenerPosition = AVAudio3DPoint(
                x: mixer.listenerPosition.x + adjustedPosition.x,
                y: mixer.listenerPosition.y + adjustedPosition.y,
                z: mixer.listenerPosition.z + adjustedPosition.z
            )
        }
    }

    /// Provides audio feedback for recognized gestures
    private func handleGestureAudioFeedback(_ gesture: HandTrackingService.HandGesture) {
        guard !isMuted else { return }

        switch gesture {
        case .pinch:
            play(.tap, at: handTrackingService?.rightHandPosition ?? SIMD3<Float>(0, 0, -0.3))
        case .point:
            // Subtle directional audio cue when pointing
            if spatialDescriptionsEnabled {
                play(.notification, at: handTrackingService?.rightHandPosition)
            }
        case .openPalm:
            // Ready state - very subtle audio
            break
        case .fist, .thumbsUp, .none:
            break
        }
    }

    // MARK: - Audio-Only Accessibility Mode

    /// Enables audio-only navigation mode for blind/low vision users
    func enableAudioOnlyMode() {
        audioOnlyModeEnabled = true
        spatialDescriptionsEnabled = true

        // Announce mode activation
        speakAccessibilityDescription("Audio-only navigation mode enabled. Use gestures to explore.")

        // Play spatial orientation sound
        playAmbient(radius: 1.5)
    }

    /// Disables audio-only navigation mode
    func disableAudioOnlyMode() {
        audioOnlyModeEnabled = false
        speakAccessibilityDescription("Audio-only mode disabled")
    }

    /// Announces spatial description of a room or area
    func announceSpatialDescription(_ description: String, at position: SIMD3<Float>? = nil) {
        guard spatialDescriptionsEnabled else { return }

        // Play a spatial cue at the position
        if let pos = position {
            play(.notification, at: pos)
        }

        // Use VoiceOver or speech synthesis for the description
        speakAccessibilityDescription(description)
    }

    /// Announces device state with spatial audio
    func announceDeviceState(name: String, state: String, at position: SIMD3<Float>) {
        guard audioOnlyModeEnabled else { return }

        // Play audio at device location
        play(.notification, at: position)

        // Speak the device state
        speakAccessibilityDescription("\(name): \(state)")
    }

    /// Provides spatial audio feedback for navigation in immersive space
    func playNavigationCue(direction: NavigationDirection, distance: Float) {
        guard audioOnlyModeEnabled else { return }

        let basePosition: SIMD3<Float>
        switch direction {
        case .forward:
            basePosition = SIMD3<Float>(0, 0, -distance)
        case .backward:
            basePosition = SIMD3<Float>(0, 0, distance)
        case .left:
            basePosition = SIMD3<Float>(-distance, 0, 0)
        case .right:
            basePosition = SIMD3<Float>(distance, 0, 0)
        case .up:
            basePosition = SIMD3<Float>(0, distance, 0)
        case .down:
            basePosition = SIMD3<Float>(0, -distance, 0)
        }

        play(.notification, at: basePosition)
    }

    /// Navigation directions for audio cues
    enum NavigationDirection {
        case forward, backward, left, right, up, down
    }

    /// Plays a sequence of spatial sounds to help orient the user in space
    func playOrientationSoundscape() {
        guard audioOnlyModeEnabled else { return }

        // Create a 3D soundscape to help user understand spatial layout
        Task {
            // Front
            play(.tap, at: SIMD3<Float>(0, 0, -1))
            try? await Task.sleep(nanoseconds: 300_000_000)

            // Left
            play(.tap, at: SIMD3<Float>(-1, 0, 0))
            try? await Task.sleep(nanoseconds: 300_000_000)

            // Right
            play(.tap, at: SIMD3<Float>(1, 0, 0))
            try? await Task.sleep(nanoseconds: 300_000_000)

            // Behind
            play(.tap, at: SIMD3<Float>(0, 0, 1))
        }
    }

    /// Uses speech synthesis for accessibility descriptions
    private func speakAccessibilityDescription(_ text: String) {
        let utterance = AVSpeechUtterance(string: text)
        utterance.voice = AVSpeechSynthesisVoice(language: "en-US")
        utterance.rate = 0.5
        utterance.pitchMultiplier = 1.0

        let synthesizer = AVSpeechSynthesizer()
        synthesizer.speak(utterance)
    }

    // MARK: - Cleanup

    func shutdown() {
        handTrackingCancellables.removeAll()
        phaseEngine?.stop()
        audioEngine?.stop()
        tonePlayer = nil
        spatialMixer = nil
        audioEngine = nil
        phaseEngine = nil
        isInitialized = false
    }
}

// MARK: - Convenience Extensions

extension SpatialAudioService {
    /// Plays appropriate audio for a home control action
    func playHomeControlAudio(action: String, success: Bool) {
        if !success {
            play(.error)
            return
        }

        switch action {
        case "lights_on":
            play(.lightOn)
        case "lights_off":
            play(.lightOff)
        case "shades_open":
            play(.shadeOpen)
        case "shades_close":
            play(.shadeClose)
        case "scene":
            playSequence([.notification, .sceneChange])
        default:
            play(.success)
        }
    }

    /// Plays orb interaction audio
    func playOrbAudio(state: String) {
        switch state {
        case "tap":
            play(.orbActivate, at: SIMD3<Float>(0.3, 1.2, -0.8))
        case "activate":
            playSequence([.orbActivate, .notification], at: SIMD3<Float>(0.3, 1.2, -0.8))
        default:
            play(.tap)
        }
    }
}

/*
 * 鏡
 * h(x) >= 0. Always.
 *
 * Sound anchors space in perception.
 * Spatial audio makes the invisible visible.
 * The ears complete what the eyes begin.
 */
