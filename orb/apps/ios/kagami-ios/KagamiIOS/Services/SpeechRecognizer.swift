//
// SpeechRecognizer.swift -- Speech Recognition Service for Kagami iOS
//
// Colony: Spark (e1) -- Ideation
//
// Features:
//   - Apple Speech framework integration
//   - Real-time speech transcription
//   - Authorization handling with graceful degradation
//   - Audio session management
//   - Accessibility-aware design
//
// Usage:
//   let recognizer = SpeechRecognizer()
//   recognizer.requestAuthorization()
//   recognizer.startTranscribing { transcript in print(transcript) }
//   recognizer.stopTranscribing()
//
// h(x) >= 0. Always.
//

import Foundation
import Speech
import AVFoundation

// MARK: - Speech Recognition Error

/// Errors that can occur during speech recognition
enum SpeechRecognitionError: Error, LocalizedError {
    case notAuthorized
    case speechRecognizerUnavailable
    case audioEngineFailure(Error)
    case recognitionFailed(Error)
    case microphoneAccessDenied
    case audioSessionError(Error)

    var errorDescription: String? {
        switch self {
        case .notAuthorized:
            return "Speech recognition is not authorized. Please enable it in Settings."
        case .speechRecognizerUnavailable:
            return "Speech recognition is not available on this device."
        case .audioEngineFailure(let error):
            return "Audio engine error: \(error.localizedDescription)"
        case .recognitionFailed(let error):
            return "Recognition failed: \(error.localizedDescription)"
        case .microphoneAccessDenied:
            return "Microphone access is required for voice commands."
        case .audioSessionError(let error):
            return "Audio session error: \(error.localizedDescription)"
        }
    }

    var recoverySuggestion: String? {
        switch self {
        case .notAuthorized, .microphoneAccessDenied:
            return "Go to Settings > Kagami > Speech Recognition to enable."
        case .speechRecognizerUnavailable:
            return "Try restarting the app or your device."
        case .audioEngineFailure, .recognitionFailed, .audioSessionError:
            return "Please try again."
        }
    }
}

// MARK: - Speech Recognizer State

/// Represents the current state of the speech recognizer
enum SpeechRecognizerState: Equatable {
    case idle
    case authorizing
    case authorized
    case listening
    case processing
    case error(String)

    var isActive: Bool {
        switch self {
        case .listening, .processing:
            return true
        default:
            return false
        }
    }
}

// MARK: - Speech Recognizer

/// Speech recognition service using Apple's Speech framework
///
/// Thread Safety: This class is MainActor-isolated and all public methods
/// must be called from the main thread.
@MainActor
class SpeechRecognizer: ObservableObject {

    // MARK: - Published State

    /// Whether the user has authorized speech recognition
    @Published private(set) var isAuthorized = false

    /// Current state of the recognizer
    @Published private(set) var state: SpeechRecognizerState = .idle

    /// Current transcript (updated in real-time during recognition)
    @Published private(set) var transcript: String = ""

    /// Last error that occurred
    @Published private(set) var lastError: SpeechRecognitionError?

    // MARK: - Private Properties

    private var audioEngine: AVAudioEngine?
    private var recognitionRequest: SFSpeechAudioBufferRecognitionRequest?
    private var recognitionTask: SFSpeechRecognitionTask?
    private let speechRecognizer: SFSpeechRecognizer?

    /// Callback for real-time transcription updates
    private var onTranscriptUpdate: ((String) -> Void)?

    /// Callback for errors
    private var onError: ((SpeechRecognitionError) -> Void)?

    // MARK: - Init

    init(locale: Locale = Locale(identifier: "en-US")) {
        self.speechRecognizer = SFSpeechRecognizer(locale: locale)

        // Check initial authorization status
        updateAuthorizationStatus(SFSpeechRecognizer.authorizationStatus())
    }

    // MARK: - Authorization

    /// Request authorization for speech recognition
    ///
    /// Call this before attempting to use speech recognition. The user will
    /// be prompted to grant permission if they haven't already.
    func requestAuthorization() {
        guard state != .authorizing else { return }

        state = .authorizing

        SFSpeechRecognizer.requestAuthorization { [weak self] status in
            DispatchQueue.main.async {
                self?.updateAuthorizationStatus(status)
            }
        }
    }

    private func updateAuthorizationStatus(_ status: SFSpeechRecognizerAuthorizationStatus) {
        switch status {
        case .authorized:
            isAuthorized = true
            state = .authorized
            lastError = nil

        case .denied, .restricted:
            isAuthorized = false
            state = .error("Speech recognition not authorized")
            lastError = .notAuthorized

        case .notDetermined:
            isAuthorized = false
            state = .idle

        @unknown default:
            isAuthorized = false
            state = .idle
        }
    }

    // MARK: - Transcription

    /// Start transcribing speech
    ///
    /// - Parameters:
    ///   - onResult: Callback invoked with each transcription update
    ///   - onError: Optional callback for error handling
    ///
    /// - Note: You must call `requestAuthorization()` first and ensure
    ///         `isAuthorized` is true before calling this method.
    func startTranscribing(
        onResult: @escaping (String) -> Void,
        onError: ((SpeechRecognitionError) -> Void)? = nil
    ) {
        // Validate authorization
        guard isAuthorized else {
            let error = SpeechRecognitionError.notAuthorized
            handleError(error)
            onError?(error)
            return
        }

        // Validate recognizer availability
        guard let speechRecognizer = speechRecognizer, speechRecognizer.isAvailable else {
            let error = SpeechRecognitionError.speechRecognizerUnavailable
            handleError(error)
            onError?(error)
            return
        }

        // Store callbacks
        self.onTranscriptUpdate = onResult
        self.onError = onError

        // Reset state
        transcript = ""
        lastError = nil

        // Configure audio session
        do {
            try configureAudioSession()
        } catch {
            let speechError = SpeechRecognitionError.audioSessionError(error)
            handleError(speechError)
            onError?(speechError)
            return
        }

        // Set up audio engine
        audioEngine = AVAudioEngine()
        guard let audioEngine = audioEngine else {
            let error = SpeechRecognitionError.audioEngineFailure(
                NSError(domain: "SpeechRecognizer", code: -1, userInfo: [
                    NSLocalizedDescriptionKey: "Failed to create audio engine"
                ])
            )
            handleError(error)
            onError?(error)
            return
        }

        // Create recognition request
        recognitionRequest = SFSpeechAudioBufferRecognitionRequest()
        guard let recognitionRequest = recognitionRequest else { return }

        // Configure for real-time results
        recognitionRequest.shouldReportPartialResults = true
        recognitionRequest.taskHint = .dictation

        // iOS 16+: Enable on-device recognition for better privacy
        if #available(iOS 16.0, *) {
            if speechRecognizer.supportsOnDeviceRecognition {
                recognitionRequest.requiresOnDeviceRecognition = true
            }
        }

        // Set up audio input tap
        let inputNode = audioEngine.inputNode
        let recordingFormat = inputNode.outputFormat(forBus: 0)

        // Verify recording format is valid
        guard recordingFormat.sampleRate > 0 && recordingFormat.channelCount > 0 else {
            let error = SpeechRecognitionError.audioEngineFailure(
                NSError(domain: "SpeechRecognizer", code: -2, userInfo: [
                    NSLocalizedDescriptionKey: "Invalid audio format"
                ])
            )
            handleError(error)
            onError?(error)
            return
        }

        inputNode.installTap(onBus: 0, bufferSize: 1024, format: recordingFormat) { [weak self] buffer, _ in
            self?.recognitionRequest?.append(buffer)
        }

        // Start audio engine
        audioEngine.prepare()
        do {
            try audioEngine.start()
        } catch {
            let speechError = SpeechRecognitionError.audioEngineFailure(error)
            handleError(speechError)
            onError?(speechError)
            return
        }

        // Update state
        state = .listening

        // Start recognition task
        recognitionTask = speechRecognizer.recognitionTask(with: recognitionRequest) { [weak self] result, error in
            guard let self = self else { return }

            Task { @MainActor in
                if let result = result {
                    let transcription = result.bestTranscription.formattedString
                    self.transcript = transcription
                    self.onTranscriptUpdate?(transcription)

                    // Check if final result
                    if result.isFinal {
                        self.state = .processing
                    }
                }

                if let error = error {
                    // Don't report cancellation as an error
                    let nsError = error as NSError
                    if nsError.domain == "kAFAssistantErrorDomain" && nsError.code == 216 {
                        // User cancelled - not an error
                        return
                    }

                    let speechError = SpeechRecognitionError.recognitionFailed(error)
                    self.handleError(speechError)
                    self.onError?(speechError)
                }
            }
        }
    }

    /// Stop transcribing and clean up resources
    func stopTranscribing() {
        // Stop audio engine
        audioEngine?.stop()
        audioEngine?.inputNode.removeTap(onBus: 0)

        // End recognition
        recognitionRequest?.endAudio()
        recognitionTask?.cancel()

        // Clean up
        audioEngine = nil
        recognitionRequest = nil
        recognitionTask = nil

        // Update state
        if state == .listening || state == .processing {
            state = .authorized
        }

        // Clear callbacks
        onTranscriptUpdate = nil
        onError = nil

        // Deactivate audio session
        deactivateAudioSession()
    }

    // MARK: - Audio Session Management

    private func configureAudioSession() throws {
        let audioSession = AVAudioSession.sharedInstance()

        try audioSession.setCategory(
            .record,
            mode: .measurement,
            options: .duckOthers
        )

        try audioSession.setActive(true, options: .notifyOthersOnDeactivation)
    }

    private func deactivateAudioSession() {
        do {
            try AVAudioSession.sharedInstance().setActive(
                false,
                options: .notifyOthersOnDeactivation
            )
        } catch {
            // Log but don't report - this is a cleanup operation
            #if DEBUG
            print("[SpeechRecognizer] Failed to deactivate audio session: \(error)")
            #endif
        }
    }

    // MARK: - Error Handling

    private func handleError(_ error: SpeechRecognitionError) {
        lastError = error
        state = .error(error.localizedDescription)

        // Clean up on error
        stopTranscribing()
    }

    // MARK: - Cleanup

    deinit {
        // Note: Cannot call stopTranscribing() here as it's @MainActor
        // The audio engine and recognition task will be cleaned up automatically
        // when references are released
    }
}

// MARK: - Convenience Extensions

extension SpeechRecognizer {
    /// Check if speech recognition is available on this device
    var isAvailable: Bool {
        speechRecognizer?.isAvailable ?? false
    }

    /// Check if currently recording
    var isRecording: Bool {
        state == .listening
    }

    /// Get the final transcript (after stopTranscribing)
    var finalTranscript: String {
        transcript
    }
}

/*
 * Mirror
 * Voice is intention made audible.
 * h(x) >= 0. Always.
 */
