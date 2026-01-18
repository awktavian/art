//
// MetaGlassesService.swift — Meta Ray-Ban Smart Glasses Integration
//
// Colony: Nexus (e4) — Integration
//
// Features:
//   - Meta DAT SDK integration
//   - Camera stream (POV video)
//   - Microphone input (spatial audio)
//   - Open-ear audio output
//   - WebSocket bridge to Kagami API
//
// Requires: Meta Wearables Device Access Toolkit iOS SDK
// Add via: https://github.com/facebook/meta-wearables-dat-ios
//

import Foundation
import Combine
import UIKit

// MARK: - Data Types

/// Camera frame from glasses
struct GlassesCameraFrame {
    let timestamp: Date
    let width: Int
    let height: Int
    let jpegData: Data
    let features: [String: Any]?
}

/// Audio buffer from glasses microphone
struct GlassesAudioBuffer {
    let timestamp: Date
    let sampleRate: Int
    let channels: Int
    let pcmData: Data
    let isVoice: Bool
    let voiceConfidence: Float
}

/// Visual context extracted from camera
struct VisualContext {
    let isIndoor: Bool?
    let lighting: String?  // "bright", "dim", "dark"
    let sceneType: String?  // "office", "kitchen", etc.
    let detectedObjects: [String]
    let detectedText: [String]
    let facesDetected: Int
    let activityHint: String?
    let confidence: Float
}

/// Glasses connection state
enum GlassesConnectionState: String {
    case disconnected
    case connecting
    case connected
    case pairing
    case error
}

/// Glasses status
struct GlassesStatus {
    var connectionState: GlassesConnectionState = .disconnected
    var batteryLevel: Int = 0
    var isWearing: Bool = false
    var cameraActive: Bool = false
    var audioActive: Bool = false
    var deviceName: String = ""
}

// MARK: - MetaGlassesService

@MainActor
class MetaGlassesService: ObservableObject {

    // MARK: - Published State

    @Published var isConnected = false
    @Published var status = GlassesStatus()
    @Published var lastError: String?
    @Published var cameraStreaming = false
    @Published var microphoneActive = false

    // MARK: - Internal State

    private var kagamiAPI: KagamiAPIService?
    private var webSocket: URLSessionWebSocketTask?
    private let session: URLSession
    private var receiveTask: Task<Void, Never>?

    // Callbacks
    private var frameCallbacks: [(GlassesCameraFrame) -> Void] = []
    private var audioCallbacks: [(GlassesAudioBuffer) -> Void] = []
    private var contextCallbacks: [(VisualContext) -> Void] = []

    // Configuration
    private let wsEndpoint = "/ws/meta-glasses"

    // MARK: - Init

    init() {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 30
        self.session = URLSession(configuration: config)
    }

    // MARK: - Connection

    /// Set the Kagami API service for base URL discovery
    func setKagamiAPI(_ api: KagamiAPIService) {
        self.kagamiAPI = api
    }

    /// Connect to glasses via Kagami API WebSocket
    func connect() async -> Bool {
        guard let api = kagamiAPI else {
            lastError = "KagamiAPI not set"
            return false
        }

        status.connectionState = .connecting

        // Build WebSocket URL
        // Note: In real implementation, this would connect to the Meta DAT SDK
        // For now, we bridge through Kagami API which handles the BLE connection
        // Security: Always use secure WebSocket (wss://)
        let baseURL = await getBaseURL(from: api)
        let wsURL = baseURL
            .replacingOccurrences(of: "https://", with: "wss://")
            .replacingOccurrences(of: "http://", with: "wss://")

        guard let url = URL(string: "\(wsURL)\(wsEndpoint)") else {
            lastError = "Invalid WebSocket URL"
            status.connectionState = .error
            return false
        }

        webSocket = session.webSocketTask(with: url)
        webSocket?.resume()

        // Start receive loop
        receiveTask = Task {
            await receiveLoop()
        }

        // Send connect command
        let success = await sendCommand("connect")

        if success {
            status.connectionState = .connected
            isConnected = true
            return true
        } else {
            status.connectionState = .error
            return false
        }
    }

    /// Disconnect from glasses
    func disconnect() async {
        receiveTask?.cancel()
        receiveTask = nil

        await sendCommand("disconnect")

        webSocket?.cancel(with: .normalClosure, reason: nil)
        webSocket = nil

        status.connectionState = .disconnected
        isConnected = false
        cameraStreaming = false
        microphoneActive = false
    }

    private func getBaseURL(from api: KagamiAPIService) async -> String {
        // Access the base URL from KagamiAPIService
        // Security: Default to HTTPS production URL
        return api.currentBaseURL.isEmpty ? "https://api.awkronos.com" : api.currentBaseURL
    }

    // MARK: - Camera

    /// Start camera streaming
    func startCameraStream(
        resolution: String = "medium",
        fps: Int = 15,
        extractFeatures: Bool = true
    ) async -> Bool {
        guard isConnected else { return false }

        let params: [String: Any] = [
            "resolution": resolution,
            "fps": fps,
            "extract_features": extractFeatures,
            "jpeg_quality": 80
        ]

        let success = await sendCommand("start_camera", params: params)

        if success {
            cameraStreaming = true
            status.cameraActive = true
        }

        return success
    }

    /// Stop camera streaming
    func stopCameraStream() async {
        guard cameraStreaming else { return }

        await sendCommand("stop_camera")
        cameraStreaming = false
        status.cameraActive = false
    }

    /// Capture a single photo
    func capturePhoto(extractFeatures: Bool = true) async -> GlassesCameraFrame? {
        guard isConnected else { return nil }

        let params: [String: Any] = [
            "extract_features": extractFeatures
        ]

        guard let response = await sendCommandWithResponse("capture_photo", params: params) else {
            return nil
        }

        guard let imageDataStr = response["image_data"] as? String,
              let imageData = Data(base64Encoded: imageDataStr) else {
            return nil
        }

        return GlassesCameraFrame(
            timestamp: Date(),
            width: response["width"] as? Int ?? 0,
            height: response["height"] as? Int ?? 0,
            jpegData: imageData,
            features: response["features"] as? [String: Any]
        )
    }

    /// Get visual context from camera
    func getVisualContext() async -> VisualContext? {
        guard let frame = await capturePhoto(extractFeatures: true),
              let features = frame.features else {
            return nil
        }

        return VisualContext(
            isIndoor: features["is_indoor"] as? Bool,
            lighting: features["lighting"] as? String,
            sceneType: features["scene_type"] as? String,
            detectedObjects: features["objects"] as? [String] ?? [],
            detectedText: features["text"] as? [String] ?? [],
            facesDetected: features["face_count"] as? Int ?? 0,
            activityHint: features["activity"] as? String,
            confidence: features["confidence"] as? Float ?? 0
        )
    }

    /// Register callback for camera frames
    func onFrame(_ callback: @escaping (GlassesCameraFrame) -> Void) {
        frameCallbacks.append(callback)
    }

    // MARK: - Audio

    /// Start microphone input
    func startMicrophone(
        quality: String = "medium",
        noiseCancellation: Bool = true
    ) async -> Bool {
        guard isConnected else { return false }

        let params: [String: Any] = [
            "quality": quality,
            "noise_cancellation": noiseCancellation,
            "vad": true
        ]

        let success = await sendCommand("start_audio", params: params)

        if success {
            microphoneActive = true
            status.audioActive = true
        }

        return success
    }

    /// Stop microphone input
    func stopMicrophone() async {
        guard microphoneActive else { return }

        await sendCommand("stop_audio")
        microphoneActive = false
        status.audioActive = false
    }

    /// Speak text through open-ear speakers
    func speak(_ text: String, voice: String = "kagami", volume: Float = 0.7) async -> Bool {
        guard isConnected else { return false }

        let params: [String: Any] = [
            "type": "tts",
            "text": text,
            "voice": voice,
            "volume": volume
        ]

        return await sendCommand("play_audio", params: params)
    }

    /// Play notification sound
    func playNotification(_ sound: String = "notification", volume: Float = 0.5) async -> Bool {
        guard isConnected else { return false }

        let params: [String: Any] = [
            "type": "notification",
            "sound": sound,
            "volume": volume
        ]

        return await sendCommand("play_audio", params: params)
    }

    /// Register callback for audio buffers
    func onAudio(_ callback: @escaping (GlassesAudioBuffer) -> Void) {
        audioCallbacks.append(callback)
    }

    // MARK: - WebSocket Communication

    @discardableResult
    private func sendCommand(_ command: String, params: [String: Any]? = nil) async -> Bool {
        guard let webSocket = webSocket else { return false }

        var message: [String: Any] = [
            "id": UUID().uuidString,
            "command": command
        ]

        if let params = params {
            message["params"] = params
        }

        do {
            let data = try JSONSerialization.data(withJSONObject: message)
            try await webSocket.send(.string(String(data: data, encoding: .utf8) ?? ""))
            return true
        } catch {
            lastError = error.localizedDescription
            return false
        }
    }

    private func sendCommandWithResponse(_ command: String, params: [String: Any]? = nil) async -> [String: Any]? {
        guard let webSocket = webSocket else { return nil }

        let messageId = UUID().uuidString
        var message: [String: Any] = [
            "id": messageId,
            "command": command
        ]

        if let params = params {
            message["params"] = params
        }

        do {
            let data = try JSONSerialization.data(withJSONObject: message)
            try await webSocket.send(.string(String(data: data, encoding: .utf8) ?? ""))

            // Wait for response (simplified - real impl would use continuation)
            try await Task.sleep(nanoseconds: 500_000_000)  // 500ms

            // In real implementation, we'd wait for matching response
            return nil

        } catch {
            lastError = error.localizedDescription
            return nil
        }
    }

    private func receiveLoop() async {
        guard let webSocket = webSocket else { return }

        while !Task.isCancelled {
            do {
                let message = try await webSocket.receive()
                await handleMessage(message)
            } catch {
                if !Task.isCancelled {
                    status.connectionState = .disconnected
                    isConnected = false
                }
                break
            }
        }
    }

    private func handleMessage(_ message: URLSessionWebSocketTask.Message) async {
        switch message {
        case .string(let text):
            if let data = text.data(using: .utf8),
               let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                await handleJSON(json)
            }

        case .data(let data):
            await handleBinary(data)

        @unknown default:
            break
        }
    }

    private func handleJSON(_ json: [String: Any]) async {
        guard let type = json["type"] as? String else { return }

        switch type {
        case "status":
            if let data = json["data"] as? [String: Any] {
                updateStatus(data)
            }

        case "camera_frame":
            if let data = json["data"] as? [String: Any] {
                handleCameraFrame(data)
            }

        case "audio_buffer":
            if let data = json["data"] as? [String: Any] {
                handleAudioBuffer(data)
            }

        default:
            break
        }
    }

    private func handleBinary(_ data: Data) async {
        guard data.count > 0 else { return }

        let dataType = data[0]
        let payload = data.dropFirst()

        switch dataType {
        case 0x01:  // Camera frame
            let frame = GlassesCameraFrame(
                timestamp: Date(),
                width: 0,  // Would be in header
                height: 0,
                jpegData: Data(payload),
                features: nil
            )
            for callback in frameCallbacks {
                callback(frame)
            }

        case 0x02:  // Audio buffer
            let buffer = GlassesAudioBuffer(
                timestamp: Date(),
                sampleRate: 16000,
                channels: 1,
                pcmData: Data(payload),
                isVoice: false,
                voiceConfidence: 0
            )
            for callback in audioCallbacks {
                callback(buffer)
            }

        default:
            break
        }
    }

    private func updateStatus(_ data: [String: Any]) {
        if let stateStr = data["connection_state"] as? String {
            status.connectionState = GlassesConnectionState(rawValue: stateStr) ?? .disconnected
        }
        if let battery = data["battery_level"] as? Int {
            status.batteryLevel = battery
        }
        if let wearing = data["is_wearing"] as? Bool {
            status.isWearing = wearing
        }
        if let camera = data["camera_active"] as? Bool {
            status.cameraActive = camera
            cameraStreaming = camera
        }
        if let audio = data["audio_active"] as? Bool {
            status.audioActive = audio
            microphoneActive = audio
        }
        if let name = data["device_name"] as? String {
            status.deviceName = name
        }
    }

    private func handleCameraFrame(_ data: [String: Any]) {
        guard let imageDataStr = data["frame_data"] as? String,
              let imageData = Data(base64Encoded: imageDataStr) else {
            return
        }

        let frame = GlassesCameraFrame(
            timestamp: Date(),
            width: data["width"] as? Int ?? 0,
            height: data["height"] as? Int ?? 0,
            jpegData: imageData,
            features: data["features"] as? [String: Any]
        )

        for callback in frameCallbacks {
            callback(frame)
        }
    }

    private func handleAudioBuffer(_ data: [String: Any]) {
        guard let audioDataStr = data["audio_data"] as? String,
              let audioData = Data(base64Encoded: audioDataStr) else {
            return
        }

        let buffer = GlassesAudioBuffer(
            timestamp: Date(),
            sampleRate: data["sample_rate"] as? Int ?? 16000,
            channels: data["channels"] as? Int ?? 1,
            pcmData: audioData,
            isVoice: data["is_voice"] as? Bool ?? false,
            voiceConfidence: data["voice_confidence"] as? Float ?? 0
        )

        for callback in audioCallbacks {
            callback(buffer)
        }
    }
}

/*
 * Mirror
 * h(x) >= 0. Always.
 *
 * First-person perspective extends the Markov blanket.
 * What you see becomes what I know.
 * What I know becomes what you hear.
 */
