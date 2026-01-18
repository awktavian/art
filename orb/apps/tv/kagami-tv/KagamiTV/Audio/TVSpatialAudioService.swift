//
// TVSpatialAudioService.swift -- Spatial Audio Integration for tvOS
//
// Kagami TV -- Immersive audio feedback on Apple TV
//
// Colony: Nexus (e4) -- Integration
//
// Per KAGAMI_REDESIGN_PLAN.md: Add spatial audio integration hooks
//
// Features:
// - Dolby Atmos support for compatible audio systems
// - 3D positional audio for UI feedback
// - Multi-channel speaker array integration
// - HomePod integration for home theater setups
// - Audio zones matching room layout
// - BBC Orchestra earcons integration
//
// h(x) >= 0. Always.
//

import Foundation
import AVFoundation
import AVFAudio
import Combine

/// Manages spatial audio for tvOS with multi-channel speaker support
@MainActor
class TVSpatialAudioService: ObservableObject {

    // MARK: - Published State

    @Published var isInitialized = false
    @Published var isSpatialAudioAvailable = false
    @Published var isAtmosAvailable = false
    @Published var isMuted = false
    @Published var masterVolume: Double = 0.8

    // MARK: - Audio Types

    /// Audio events for UI feedback with spatial positioning
    enum AudioEvent: String, CaseIterable {
        // Navigation
        case focusChange = "focus_change"
        case selection = "selection"
        case back = "back"
        case tabSwitch = "tab_switch"

        // Home control
        case lightsOn = "lights_on"
        case lightsOff = "lights_off"
        case sceneActivate = "scene_activate"
        case lockEngaged = "lock_engaged"
        case thermostatAdjust = "thermostat_adjust"

        // Status
        case success = "success"
        case error = "error"
        case notification = "notification"
        case alert = "alert"

        // Ambient
        case ambientPulse = "ambient_pulse"
        case roomEnter = "room_enter"
        case roomExit = "room_exit"

        /// BBC Orchestra earcon mapping
        var earconName: String {
            switch self {
            case .focusChange: return "focus"
            case .selection: return "success"
            case .back: return "departure"
            case .tabSwitch: return "focus"
            case .lightsOn: return "door_open"
            case .lightsOff: return "door_close"
            case .sceneActivate: return "cinematic"
            case .lockEngaged: return "lock_engaged"
            case .thermostatAdjust: return "settling"
            case .success: return "success"
            case .error: return "error"
            case .notification: return "notification"
            case .alert: return "alert"
            case .ambientPulse: return "room_enter"
            case .roomEnter: return "arrival"
            case .roomExit: return "departure"
            }
        }

        /// Fallback synthesized tone parameters
        var toneParams: ToneParams {
            switch self {
            case .focusChange: return ToneParams(frequency: 880, duration: 0.05, amplitude: 0.15)
            case .selection: return ToneParams(frequency: 1047, duration: 0.1, amplitude: 0.2)
            case .back: return ToneParams(frequency: 659, duration: 0.08, amplitude: 0.15)
            case .tabSwitch: return ToneParams(frequency: 784, duration: 0.06, amplitude: 0.15)
            case .lightsOn: return ToneParams(frequency: 698, duration: 0.12, amplitude: 0.2)
            case .lightsOff: return ToneParams(frequency: 440, duration: 0.12, amplitude: 0.18)
            case .sceneActivate: return ToneParams(frequency: 523, duration: 0.25, amplitude: 0.25)
            case .lockEngaged: return ToneParams(frequency: 880, duration: 0.15, amplitude: 0.2)
            case .thermostatAdjust: return ToneParams(frequency: 587, duration: 0.1, amplitude: 0.15)
            case .success: return ToneParams(frequency: 1318, duration: 0.2, amplitude: 0.2)
            case .error: return ToneParams(frequency: 220, duration: 0.3, amplitude: 0.25)
            case .notification: return ToneParams(frequency: 659, duration: 0.15, amplitude: 0.2)
            case .alert: return ToneParams(frequency: 440, duration: 0.4, amplitude: 0.3)
            case .ambientPulse: return ToneParams(frequency: 330, duration: 1.0, amplitude: 0.08)
            case .roomEnter: return ToneParams(frequency: 523, duration: 0.3, amplitude: 0.15)
            case .roomExit: return ToneParams(frequency: 392, duration: 0.3, amplitude: 0.12)
            }
        }
    }

    struct ToneParams {
        let frequency: Float
        let duration: TimeInterval
        let amplitude: Float
    }

    /// Spatial position for audio events
    struct SpatialPosition {
        let x: Float  // -1 (left) to 1 (right)
        let y: Float  // -1 (below) to 1 (above)
        let z: Float  // -1 (behind) to 1 (in front)

        static let center = SpatialPosition(x: 0, y: 0, z: 1)
        static let left = SpatialPosition(x: -0.8, y: 0, z: 0.5)
        static let right = SpatialPosition(x: 0.8, y: 0, z: 0.5)
        static let topCenter = SpatialPosition(x: 0, y: 0.5, z: 0.8)
        static let bottomLeft = SpatialPosition(x: -0.6, y: -0.3, z: 0.6)
        static let bottomRight = SpatialPosition(x: 0.6, y: -0.3, z: 0.6)

        /// Creates a position from screen coordinates (0-1 range)
        static func fromScreenPosition(x: Float, y: Float) -> SpatialPosition {
            return SpatialPosition(
                x: (x - 0.5) * 2, // Convert to -1 to 1
                y: (0.5 - y) * 0.6, // Subtle vertical offset
                z: 0.8 // Fixed depth
            )
        }
    }

    // MARK: - Internal State

    private var audioEngine: AVAudioEngine?
    private var environmentNode: AVAudioEnvironmentNode?
    private var playerNode: AVAudioPlayerNode?
    private var earconPlayer: AVAudioPlayerNode?
    private var earconCache: [String: AVAudioPCMBuffer] = [:]

    // Multi-channel output format
    private var outputFormat: AVAudioFormat?
    private var channelCount: Int = 2

    // Room layout mapping
    private var roomPositions: [String: SpatialPosition] = [:]

    // MARK: - Singleton

    static let shared = TVSpatialAudioService()

    // MARK: - Init

    init() {
        Task {
            await initialize()
        }
    }

    // MARK: - Initialization

    func initialize() async {
        do {
            // Configure audio session for spatial audio
            let session = AVAudioSession.sharedInstance()

            // Check for spatial audio capability
            isSpatialAudioAvailable = session.currentRoute.outputs.contains { output in
                output.portType == .airPlay || output.portType == .HDMI
            }

            // Activate session
            try session.setCategory(.playback, mode: .moviePlayback, options: [.mixWithOthers])
            try session.setActive(true)

            // Check channel count
            channelCount = session.outputNumberOfChannels

            // Create audio engine
            audioEngine = AVAudioEngine()
            environmentNode = AVAudioEnvironmentNode()
            playerNode = AVAudioPlayerNode()
            earconPlayer = AVAudioPlayerNode()

            guard let engine = audioEngine,
                  let environment = environmentNode,
                  let player = playerNode,
                  let earconPlayer = earconPlayer else {
                return
            }

            // Attach nodes
            engine.attach(player)
            engine.attach(earconPlayer)
            engine.attach(environment)

            // Create output format
            outputFormat = engine.outputNode.outputFormat(forBus: 0)

            // Connect nodes for spatial audio
            // Player -> Environment -> Main Output
            let stereoFormat = AVAudioFormat(standardFormatWithSampleRate: 48000, channels: 2)!
            engine.connect(player, to: environment, format: stereoFormat)
            engine.connect(earconPlayer, to: environment, format: stereoFormat)
            engine.connect(environment, to: engine.mainMixerNode, format: outputFormat)

            // Configure environment node
            environment.listenerPosition = AVAudio3DPoint(x: 0, y: 0, z: 0)
            environment.listenerAngularOrientation = AVAudio3DAngularOrientation(yaw: 0, pitch: 0, roll: 0)
            environment.renderingAlgorithm = .auto
            environment.distanceAttenuationParameters.referenceDistance = 1.0
            environment.distanceAttenuationParameters.maximumDistance = 10.0
            environment.reverbParameters.enable = true
            environment.reverbParameters.level = -20 // Subtle reverb

            // Start engine
            try engine.start()

            isInitialized = true

            // Check for Atmos support
            isAtmosAvailable = channelCount > 6

            // Preload bundled earcons
            await preloadEarcons()

            print("[TVSpatialAudio] Initialized - Channels: \(channelCount), Spatial: \(isSpatialAudioAvailable), Atmos: \(isAtmosAvailable)")

        } catch {
            print("[TVSpatialAudio] Initialization failed: \(error)")
        }
    }

    /// Preload bundled BBC Orchestra earcons
    private func preloadEarcons() async {
        let earconNames = ["focus", "success", "error", "notification", "alert",
                         "arrival", "departure", "cinematic", "settling",
                         "door_open", "door_close", "lock_engaged", "room_enter"]

        for name in earconNames {
            _ = await loadEarcon(name: name)
        }
    }

    /// Load an earcon from bundle
    private func loadEarcon(name: String) async -> Bool {
        if earconCache[name] != nil { return true }

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
            earconCache[name] = buffer
            return true

        } catch {
            print("[TVSpatialAudio] Failed to load earcon '\(name)': \(error)")
            return false
        }
    }

    // MARK: - Playback

    /// Play an audio event at a spatial position
    func play(_ event: AudioEvent, at position: SpatialPosition = .center) {
        guard isInitialized, !isMuted else { return }

        // Try earcon first
        if let buffer = earconCache[event.earconName] {
            playBuffer(buffer, at: position)
        } else {
            // Fall back to synthesized tone
            playTone(event.toneParams, at: position)
        }
    }

    /// Play audio at a screen position (e.g., where a button was pressed)
    func playAtScreenPosition(_ event: AudioEvent, x: Float, y: Float) {
        let position = SpatialPosition.fromScreenPosition(x: x, y: y)
        play(event, at: position)
    }

    /// Play audio in a specific room
    func playInRoom(_ event: AudioEvent, roomId: String) {
        let position = roomPositions[roomId] ?? .center
        play(event, at: position)
    }

    /// Play a buffer at a spatial position
    private func playBuffer(_ buffer: AVAudioPCMBuffer, at position: SpatialPosition) {
        guard let player = earconPlayer, let environment = environmentNode else { return }

        // Update spatial position
        let avPosition = AVAudio3DPoint(x: position.x, y: position.y, z: position.z)
        environment.listenerPosition = AVAudio3DPoint(x: 0, y: 0, z: 0)

        // For spatial audio, we need to position the source
        // Since AVAudioEnvironmentNode works with attached sources,
        // we simulate position through pan and distance
        let pan = position.x // -1 to 1
        player.pan = pan

        // Volume based on distance
        let distance = sqrt(position.x * position.x + position.y * position.y + position.z * position.z)
        let volumeMultiplier = max(0.3, min(1.0, 1.0 / distance))
        player.volume = Float(masterVolume) * volumeMultiplier

        // Schedule and play
        if player.isPlaying {
            player.stop()
        }

        player.scheduleBuffer(buffer, at: nil, options: .interrupts)
        player.play()
    }

    /// Generate and play a synthesized tone
    private func playTone(_ params: ToneParams, at position: SpatialPosition) {
        guard let player = playerNode else { return }

        let sampleRate = 48000.0
        let frameCount = AVAudioFrameCount(params.duration * sampleRate)

        guard let format = AVAudioFormat(standardFormatWithSampleRate: sampleRate, channels: 2),
              let buffer = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: frameCount) else {
            return
        }

        buffer.frameLength = frameCount

        guard let leftChannel = buffer.floatChannelData?[0],
              let rightChannel = buffer.floatChannelData?[1] else {
            return
        }

        // Calculate stereo panning from position
        let leftGain = (1 - position.x) / 2 * params.amplitude * Float(masterVolume)
        let rightGain = (1 + position.x) / 2 * params.amplitude * Float(masterVolume)

        for frame in 0..<Int(frameCount) {
            let progress = Float(frame) / Float(frameCount)
            let envelope = sinf(.pi * progress) // Smooth envelope

            let sample = sinf(2.0 * .pi * params.frequency * Float(frame) / Float(sampleRate))

            leftChannel[frame] = sample * envelope * leftGain
            rightChannel[frame] = sample * envelope * rightGain
        }

        if player.isPlaying {
            player.stop()
        }

        player.scheduleBuffer(buffer, at: nil, options: .interrupts)
        player.play()
    }

    // MARK: - Room Position Mapping

    /// Configure room positions for spatial audio
    func configureRoomPositions(_ rooms: [String: SpatialPosition]) {
        roomPositions = rooms
    }

    /// Set position for a single room
    func setRoomPosition(_ roomId: String, position: SpatialPosition) {
        roomPositions[roomId] = position
    }

    // MARK: - Ambient Audio

    /// Play ambient soundscape for a room state
    func playAmbientSoundscape(for roomState: String) {
        // Create subtle ambient audio based on room state
        switch roomState {
        case "occupied":
            play(.ambientPulse, at: .center)
        case "movie_mode":
            // Subtle surround presence
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) { [weak self] in
                self?.play(.ambientPulse, at: .left)
            }
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) { [weak self] in
                self?.play(.ambientPulse, at: .right)
            }
        default:
            break
        }
    }

    // MARK: - Volume Control

    func setVolume(_ volume: Double) {
        masterVolume = max(0, min(1, volume))
        audioEngine?.mainMixerNode.outputVolume = Float(masterVolume)
    }

    func mute() {
        isMuted = true
    }

    func unmute() {
        isMuted = false
    }

    // MARK: - Cleanup

    func shutdown() {
        audioEngine?.stop()
        audioEngine = nil
        playerNode = nil
        earconPlayer = nil
        environmentNode = nil
        earconCache.removeAll()
        isInitialized = false
    }
}

// MARK: - SwiftUI Integration

import SwiftUI

/// View modifier that plays spatial audio on button press
struct TVSpatialAudioButtonModifier: ViewModifier {
    let event: TVSpatialAudioService.AudioEvent
    @State private var buttonFrame: CGRect = .zero

    func body(content: Content) -> some View {
        content
            .background(
                GeometryReader { geometry in
                    Color.clear.onAppear {
                        buttonFrame = geometry.frame(in: .global)
                    }
                }
            )
            .simultaneousGesture(
                TapGesture().onEnded { _ in
                    // Calculate screen position
                    let screenSize = UIScreen.main.bounds.size
                    let x = Float(buttonFrame.midX / screenSize.width)
                    let y = Float(buttonFrame.midY / screenSize.height)
                    TVSpatialAudioService.shared.playAtScreenPosition(event, x: x, y: y)
                }
            )
    }
}

extension View {
    /// Plays spatial audio when this button is pressed
    func spatialAudio(_ event: TVSpatialAudioService.AudioEvent) -> some View {
        modifier(TVSpatialAudioButtonModifier(event: event))
    }
}

/*
 * Mirror
 * h(x) >= 0. Always.
 *
 * Sound fills the room.
 * Audio guides attention.
 * The space becomes alive.
 */
