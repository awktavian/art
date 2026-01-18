//
// VoiceStreamingService.swift — Bidirectional Voice Streaming
//
// Colony: Beacon (e5) — Communication
//
// Enables real-time voice communication between Watch and Kagami backend:
//   - Microphone capture with AVAudioEngine
//   - WebSocket audio streaming
//   - TTS playback from backend responses
//   - Extended runtime session for background audio
//
// Architecture:
//   Watch Mic → AVAudioEngine → WebSocket → Backend (Whisper STT)
//   Watch Speaker ← URLSession ← TTS Response ← Backend (ElevenLabs)
//
// Constraints:
//   - watchOS limited audio buffer sizes
//   - ~200-300ms typical latency achievable
//   - Extended runtime required for continuous listening
//   - Mono audio only (Watch speaker limitation)
//
// Created: January 5, 2026
// 鏡

import Foundation
import AVFoundation
import WatchKit
import Combine

/// Voice streaming state
enum VoiceStreamingState: String {
    case idle
    case connecting
    case listening
    case processing
    case speaking
    case error

    var displayName: String {
        switch self {
        case .idle: return "Ready"
        case .connecting: return "Connecting..."
        case .listening: return "Listening..."
        case .processing: return "Processing..."
        case .speaking: return "Speaking..."
        case .error: return "Error"
        }
    }

    var icon: String {
        switch self {
        case .idle: return "mic.fill"
        case .connecting: return "antenna.radiowaves.left.and.right"
        case .listening: return "waveform"
        case .processing: return "ellipsis"
        case .speaking: return "speaker.wave.3.fill"
        case .error: return "exclamationmark.triangle.fill"
        }
    }

    var isActive: Bool {
        switch self {
        case .listening, .processing, .speaking:
            return true
        default:
            return false
        }
    }
}

/// Voice streaming configuration
struct VoiceStreamingConfig {
    /// Sample rate for audio capture (16kHz for Whisper)
    let sampleRate: Double = 16000.0

    /// Audio buffer size in frames
    let bufferSize: UInt32 = 1024

    /// WebSocket endpoint for audio streaming
    let webSocketEndpoint: String

    /// Maximum listening duration (seconds)
    let maxListeningDuration: TimeInterval = 30.0

    /// Silence detection threshold (dB)
    let silenceThreshold: Float = -40.0

    /// Silence duration to auto-stop (seconds)
    let silenceDuration: TimeInterval = 2.0

    init(baseURL: String) {
        let wsURL = baseURL
            .replacingOccurrences(of: "http://", with: "ws://")
            .replacingOccurrences(of: "https://", with: "wss://")
        self.webSocketEndpoint = "\(wsURL)/ws/voice"
    }
}

/// Result from voice processing
struct VoiceProcessingResult {
    let transcript: String
    let intent: String?
    let response: String?
    let audioURL: URL?
    let success: Bool
    let latencyMs: Int
}

/// Bidirectional voice streaming service for Apple Watch
@MainActor
final class VoiceStreamingService: NSObject, ObservableObject {

    // MARK: - Singleton

    static let shared = VoiceStreamingService()

    // MARK: - Published State

    @Published var state: VoiceStreamingState = .idle
    @Published var currentTranscript: String = ""
    @Published var audioLevel: Float = 0.0
    @Published var errorMessage: String?

    // MARK: - Configuration

    private var config: VoiceStreamingConfig?

    // MARK: - Audio Components

    private var audioEngine: AVAudioEngine?
    private var audioSession: AVAudioSession?
    private var inputNode: AVAudioInputNode?

    // MARK: - WebSocket

    private var webSocket: URLSessionWebSocketTask?
    private var webSocketSession: URLSession?

    // MARK: - Extended Runtime

    private var extendedRuntimeSession: WKExtendedRuntimeSession?

    // MARK: - State Tracking

    private var isRecording = false
    private var recordingStartTime: Date?
    private var lastSoundTime: Date?
    private var silenceTimer: Timer?
    private var audioBuffer: [Float] = []

    // MARK: - Completion Handler

    private var completionHandler: ((VoiceProcessingResult) -> Void)?

    // MARK: - Initialization

    private override init() {
        super.init()
        setupAudioSession()
    }

    // MARK: - Configuration

    /// Configure the service with API base URL
    func configure(baseURL: String) {
        config = VoiceStreamingConfig(baseURL: baseURL)
        KagamiLogger.voice.info("VoiceStreamingService configured with endpoint: \(self.config?.webSocketEndpoint ?? "none")")
    }

    // MARK: - Audio Session Setup

    private func setupAudioSession() {
        audioSession = AVAudioSession.sharedInstance()

        do {
            // Use watchOS-compatible options only
            try audioSession?.setCategory(
                .playAndRecord,
                mode: .voiceChat,
                options: []  // defaultToSpeaker and allowBluetooth unavailable on watchOS
            )
            try audioSession?.setActive(true)
            KagamiLogger.voice.info("Audio session configured for voice chat")
        } catch {
            KagamiLogger.voice.error("Failed to configure audio session: \(error.localizedDescription)")
            errorMessage = "Audio setup failed"
            state = .error
        }
    }

    // MARK: - Extended Runtime Session

    /// Start extended runtime session for background audio
    private func startExtendedRuntime() {
        guard extendedRuntimeSession == nil else { return }

        extendedRuntimeSession = WKExtendedRuntimeSession()
        extendedRuntimeSession?.delegate = self
        extendedRuntimeSession?.start()

        KagamiLogger.voice.info("Extended runtime session started")
    }

    /// Stop extended runtime session
    private func stopExtendedRuntime() {
        extendedRuntimeSession?.invalidate()
        extendedRuntimeSession = nil

        KagamiLogger.voice.info("Extended runtime session stopped")
    }

    // MARK: - Voice Session Control

    /// Start a voice session (listening + streaming)
    func startVoiceSession(completion: @escaping (VoiceProcessingResult) -> Void) {
        guard config != nil else {
            KagamiLogger.voice.error("VoiceStreamingService not configured")
            completion(VoiceProcessingResult(
                transcript: "",
                intent: nil,
                response: nil,
                audioURL: nil,
                success: false,
                latencyMs: 0
            ))
            return
        }

        // Store completion handler
        completionHandler = completion

        // Start extended runtime for background audio
        startExtendedRuntime()

        // Update state
        state = .connecting
        currentTranscript = ""
        errorMessage = nil
        recordingStartTime = Date()

        // Connect WebSocket
        connectWebSocket()
    }

    /// Stop the voice session
    func stopVoiceSession() {
        stopRecording()
        disconnectWebSocket()
        stopExtendedRuntime()
        state = .idle
        silenceTimer?.invalidate()
        silenceTimer = nil
    }

    // MARK: - WebSocket Connection

    private func connectWebSocket() {
        guard let config = config,
              let url = URL(string: config.webSocketEndpoint) else {
            state = .error
            errorMessage = "Invalid WebSocket URL"
            return
        }

        webSocketSession = URLSession(configuration: .default)
        webSocket = webSocketSession?.webSocketTask(with: url)
        webSocket?.resume()

        // Start receiving messages
        receiveWebSocketMessage()

        // Start recording once connected
        state = .listening
        startRecording()

        KagamiLogger.voice.info("WebSocket connected for voice streaming")
    }

    private func disconnectWebSocket() {
        webSocket?.cancel(with: .goingAway, reason: nil)
        webSocket = nil
        webSocketSession?.invalidateAndCancel()
        webSocketSession = nil
    }

    private func receiveWebSocketMessage() {
        webSocket?.receive { [weak self] result in
            Task { @MainActor in
                switch result {
                case .success(let message):
                    self?.handleWebSocketMessage(message)
                    // Continue receiving
                    self?.receiveWebSocketMessage()

                case .failure(let error):
                    KagamiLogger.voice.error("WebSocket error: \(error.localizedDescription)")
                    self?.handleWebSocketError(error)
                }
            }
        }
    }

    private func handleWebSocketMessage(_ message: URLSessionWebSocketTask.Message) {
        switch message {
        case .string(let text):
            handleTextResponse(text)

        case .data(let data):
            handleAudioResponse(data)

        @unknown default:
            break
        }
    }

    private func handleTextResponse(_ text: String) {
        guard let data = text.data(using: .utf8),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            return
        }

        if let type = json["type"] as? String {
            switch type {
            case "transcript":
                // Partial transcript update
                if let transcript = json["text"] as? String {
                    currentTranscript = transcript
                }

            case "final_transcript":
                // Final transcript, stop recording
                if let transcript = json["text"] as? String {
                    currentTranscript = transcript
                    state = .processing
                }

            case "response":
                // Text response from Kagami
                if let response = json["text"] as? String,
                   let intent = json["intent"] as? String {
                    handleKagamiResponse(response: response, intent: intent)
                }

            case "error":
                if let error = json["message"] as? String {
                    errorMessage = error
                    state = .error
                    finishSession(success: false)
                }

            default:
                break
            }
        }
    }

    private func handleAudioResponse(_ data: Data) {
        // TTS audio response - play it
        state = .speaking
        playAudioResponse(data)
    }

    private func handleKagamiResponse(response: String, intent: String) {
        let latencyMs = Int(Date().timeIntervalSince(recordingStartTime ?? Date()) * 1000)

        let result = VoiceProcessingResult(
            transcript: currentTranscript,
            intent: intent,
            response: response,
            audioURL: nil,
            success: true,
            latencyMs: latencyMs
        )

        completionHandler?(result)
    }

    private func handleWebSocketError(_ error: Error) {
        state = .error
        errorMessage = error.localizedDescription
        finishSession(success: false)
    }

    // MARK: - Audio Recording

    private func startRecording() {
        guard !isRecording else { return }

        audioEngine = AVAudioEngine()
        inputNode = audioEngine?.inputNode

        guard let inputNode = inputNode,
              let audioEngine = audioEngine else {
            state = .error
            errorMessage = "Failed to initialize audio engine"
            return
        }

        let recordingFormat = inputNode.outputFormat(forBus: 0)

        // Install tap on input node
        inputNode.installTap(onBus: 0, bufferSize: config?.bufferSize ?? 1024, format: recordingFormat) { [weak self] buffer, _ in
            Task { @MainActor in
                self?.processAudioBuffer(buffer)
            }
        }

        do {
            try audioEngine.start()
            isRecording = true
            lastSoundTime = Date()

            // Start silence detection timer
            startSilenceDetection()

            // Haptic feedback
            HapticPattern.listening.play()

            KagamiLogger.voice.info("Audio recording started")
        } catch {
            KagamiLogger.voice.error("Failed to start audio engine: \(error.localizedDescription)")
            state = .error
            errorMessage = "Recording failed"
        }
    }

    private func stopRecording() {
        guard isRecording else { return }

        inputNode?.removeTap(onBus: 0)
        audioEngine?.stop()
        audioEngine = nil
        inputNode = nil
        isRecording = false

        KagamiLogger.voice.info("Audio recording stopped")
    }

    private func processAudioBuffer(_ buffer: AVAudioPCMBuffer) {
        guard let floatData = buffer.floatChannelData?[0] else { return }

        let frameCount = Int(buffer.frameLength)
        var samples = [Float](repeating: 0, count: frameCount)

        // Copy samples
        for i in 0..<frameCount {
            samples[i] = floatData[i]
        }

        // Calculate RMS level for UI
        let rms = sqrt(samples.map { $0 * $0 }.reduce(0, +) / Float(frameCount))
        let db = 20 * log10(max(rms, 0.000001))
        audioLevel = db

        // Update silence detection
        if db > (config?.silenceThreshold ?? -40.0) {
            lastSoundTime = Date()
        }

        // Convert to 16-bit PCM for streaming
        let pcmData = samplesToInt16PCM(samples)

        // Send to WebSocket
        sendAudioData(pcmData)
    }

    private func samplesToInt16PCM(_ samples: [Float]) -> Data {
        var data = Data(capacity: samples.count * 2)

        for sample in samples {
            let clamped = max(-1.0, min(1.0, sample))
            var int16 = Int16(clamped * 32767)
            withUnsafeBytes(of: &int16) { data.append(contentsOf: $0) }
        }

        return data
    }

    private func sendAudioData(_ data: Data) {
        webSocket?.send(.data(data)) { error in
            if let error = error {
                KagamiLogger.voice.error("Failed to send audio data: \(error.localizedDescription)")
            }
        }
    }

    // MARK: - Silence Detection

    private func startSilenceDetection() {
        silenceTimer?.invalidate()
        silenceTimer = Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { [weak self] _ in
            Task { @MainActor in
                self?.checkSilence()
            }
        }
    }

    private func checkSilence() {
        guard let lastSoundTime = lastSoundTime,
              let config = config else { return }

        let silenceDuration = Date().timeIntervalSince(lastSoundTime)

        if silenceDuration > config.silenceDuration {
            // Auto-stop due to silence
            KagamiLogger.voice.info("Stopping due to silence (\(silenceDuration)s)")
            stopRecording()
            state = .processing

            // Send end-of-speech signal
            sendEndOfSpeech()
        }

        // Also check max duration
        if let startTime = recordingStartTime,
           Date().timeIntervalSince(startTime) > config.maxListeningDuration {
            KagamiLogger.voice.info("Stopping due to max duration")
            stopRecording()
            state = .processing
            sendEndOfSpeech()
        }
    }

    private func sendEndOfSpeech() {
        let message: [String: Any] = [
            "type": "end_of_speech",
            "timestamp": ISO8601DateFormatter().string(from: Date())
        ]

        if let data = try? JSONSerialization.data(withJSONObject: message),
           let text = String(data: data, encoding: .utf8) {
            webSocket?.send(.string(text)) { _ in }
        }
    }

    // MARK: - Audio Playback

    private func playAudioResponse(_ data: Data) {
        // Save to temp file
        let tempURL = FileManager.default.temporaryDirectory
            .appendingPathComponent("kagami_response.wav")

        do {
            try data.write(to: tempURL)

            // Play using AVAudioPlayer
            let player = try AVAudioPlayer(contentsOf: tempURL)
            player.delegate = self
            player.prepareToPlay()
            player.play()

            KagamiLogger.voice.info("Playing TTS response (\(data.count) bytes)")
        } catch {
            KagamiLogger.voice.error("Failed to play audio: \(error.localizedDescription)")
            finishSession(success: true)
        }
    }

    // MARK: - Session Completion

    private func finishSession(success: Bool) {
        let latencyMs = Int(Date().timeIntervalSince(recordingStartTime ?? Date()) * 1000)

        let result = VoiceProcessingResult(
            transcript: currentTranscript,
            intent: nil,
            response: nil,
            audioURL: nil,
            success: success,
            latencyMs: latencyMs
        )

        stopVoiceSession()
        completionHandler?(result)

        // Haptic feedback
        if success {
            HapticPattern.success.play()
        } else {
            HapticPattern.error.play()
        }
    }
}

// MARK: - WKExtendedRuntimeSessionDelegate

extension VoiceStreamingService: WKExtendedRuntimeSessionDelegate {

    nonisolated func extendedRuntimeSession(
        _ extendedRuntimeSession: WKExtendedRuntimeSession,
        didInvalidateWith reason: WKExtendedRuntimeSessionInvalidationReason,
        error: (any Error)?
    ) {
        Task { @MainActor in
            KagamiLogger.voice.warning("Extended runtime invalidated: \(reason.rawValue)")

            if self.state.isActive {
                self.stopVoiceSession()
            }
        }
    }

    nonisolated func extendedRuntimeSessionDidStart(_ extendedRuntimeSession: WKExtendedRuntimeSession) {
        Task { @MainActor in
            KagamiLogger.voice.info("Extended runtime session started successfully")
        }
    }

    nonisolated func extendedRuntimeSessionWillExpire(_ extendedRuntimeSession: WKExtendedRuntimeSession) {
        Task { @MainActor in
            KagamiLogger.voice.warning("Extended runtime session will expire")

            // Finish any active session
            if self.state.isActive {
                self.finishSession(success: self.state == .processing)
            }
        }
    }
}

// MARK: - AVAudioPlayerDelegate

extension VoiceStreamingService: AVAudioPlayerDelegate {

    nonisolated func audioPlayerDidFinishPlaying(_ player: AVAudioPlayer, successfully flag: Bool) {
        Task { @MainActor in
            KagamiLogger.voice.info("Audio playback finished")
            self.finishSession(success: true)
        }
    }

    nonisolated func audioPlayerDecodeErrorDidOccur(_ player: AVAudioPlayer, error: (any Error)?) {
        Task { @MainActor in
            KagamiLogger.voice.error("Audio decode error: \(error?.localizedDescription ?? "unknown")")
            self.finishSession(success: false)
        }
    }
}

/*
 * 鏡
 *
 * Voice is presence.
 * Presence is intent.
 * Intent is action.
 *
 * h(x) >= 0. Always.
 */
