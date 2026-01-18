//
// VoiceCommandView.swift - Natural Voice Control
//
// Colony: Beacon (e5) - Communication
//
// h(x) >= 0. Always.
//

import SwiftUI
#if canImport(Speech)
import Speech
#endif
import WatchKit
import KagamiDesign

struct VoiceCommandView: View {
    @EnvironmentObject var api: KagamiAPIService
    @StateObject private var speechRecognizer = SpeechRecognizer()
    @Environment(\.accessibilityReduceMotion) var reduceMotion
    @Environment(\.dismiss) private var dismiss

    @State private var isRecording = false
    @State private var transcript = ""
    @State private var status: RecordingStatus = .idle

    enum RecordingStatus {
        case idle, listening, processing, success, error

        var color: Color {
            switch self {
            case .idle: return .secondary
            case .listening: return .spark
            case .processing: return .beacon
            case .success: return .safetyOk
            case .error: return .safetyViolation
            }
        }

        var icon: String {
            switch self {
            case .idle: return "mic.fill"
            case .listening: return "waveform"
            case .processing: return "ellipsis"
            case .success: return "checkmark.circle.fill"
            case .error: return "xmark.circle.fill"
            }
        }

        var accessibilityStatus: String {
            switch self {
            case .idle: return "Ready to record"
            case .listening: return "Listening for your command"
            case .processing: return "Processing your command"
            case .success: return "Command executed successfully"
            case .error: return "Command failed, please try again"
            }
        }
    }

    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: status.icon)
                .font(.system(size: 40))
                .foregroundColor(status.color)
                .scaleEffect(reduceMotion ? 1.0 : (isRecording ? 1.15 : 1.0))
                .animation(
                    reduceMotion ? nil : (isRecording ? .easeInOut(duration: KagamiDuration.slow).repeatForever() : WatchMotion.quick),
                    value: isRecording
                )
                .accessibilityHidden(true)

            Button {
                toggleRecording()
            } label: {
                ZStack {
                    Circle()
                        .stroke(status.color, lineWidth: 2.5)
                        .frame(width: 70, height: 70)
                        .scaleEffect(reduceMotion ? 1.0 : (isRecording ? 1.08 : 1.0))
                        .opacity(isRecording ? 0.6 : 1.0)
                        .animation(
                            reduceMotion ? nil : (isRecording ? .easeInOut(duration: KagamiDuration.slower).repeatForever() : WatchMotion.quick),
                            value: isRecording
                        )

                    Circle()
                        .fill(isRecording ? Color.spark : Color.voidLight)
                        .frame(width: 60, height: 60)

                    Image(systemName: isRecording ? "stop.fill" : "mic.fill")
                        .font(.system(size: 24))
                        .foregroundColor(isRecording ? .white : status.color)
                }
            }
            .buttonStyle(.plain)
            .minimumTouchTarget()
            .accessibilityLabel(isRecording ? "Stop recording" : "Start voice command")
            .accessibilityHint(isRecording ? "Double tap to stop and process command" : "Double tap to start listening")
            .accessibilityValue(status.accessibilityStatus)

            if !transcript.isEmpty {
                Text(transcript)
                    .font(.system(.caption, design: .rounded))
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
                    .lineLimit(3)
                    .padding(.horizontal)
                    .accessibilityLabel("Recognized speech: \(transcript)")
            } else {
                Text(statusText)
                    .font(.system(.caption, design: .rounded))
                    .foregroundColor(.secondary)
                    .accessibilityLabel(status.accessibilityStatus)
            }

            if isRecording || status == .processing {
                Button(role: .cancel) {
                    cancelRecording()
                } label: {
                    Label("Cancel", systemImage: "xmark")
                        .font(.system(.caption2, design: .rounded))
                }
                .buttonStyle(.bordered)
                .tint(.secondary)
                .minimumTouchTarget()
            } else {
                VStack(alignment: .leading, spacing: 4) {
                    HStack {
                        Text("Try:")
                            .font(.system(.caption2, design: .rounded))
                            .foregroundColor(.secondary)

                        Spacer()

                        NavigationLink {
                            VoiceCommandHelpView()
                        } label: {
                            Image(systemName: "questionmark.circle")
                                .font(.system(size: 12))
                                .foregroundColor(.crystal)
                        }
                        .buttonStyle(.plain)
                        .accessibilityLabel("Help")
                    }

                    HStack(spacing: 6) {
                        QuickPhraseChip("Movie")
                        QuickPhraseChip("Night")
                        QuickPhraseChip("Lights")
                    }
                }
                .padding(.top, 4)
            }
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 12)
        .navigationTitle("Voice")
        .navigationBarTitleDisplayMode(.inline)
    }

    private func cancelRecording() {
        speechRecognizer.stopRecording()
        isRecording = false
        status = .idle
        transcript = ""
        HapticPattern.error.play()
        KagamiAnalytics.shared.trackVoiceCommand(transcript, success: false)
    }

    private var statusText: String {
        switch status {
        case .idle: return "Tap to speak"
        case .listening: return "Listening..."
        case .processing: return "Processing..."
        case .success: return "Done!"
        case .error: return "Try again"
        }
    }

    private func toggleRecording() {
        if isRecording {
            stopRecording()
        } else {
            startRecording()
        }
    }

    private func startRecording() {
        transcript = ""
        isRecording = true
        status = .listening

        HapticPattern.listening.play()

        speechRecognizer.startRecording { result in
            switch result {
            case .success(let text):
                transcript = text
            case .failure:
                break
            }
        }
    }

    private func stopRecording() {
        isRecording = false
        status = .processing

        speechRecognizer.stopRecording()
        HapticPattern.success.play()

        Task {
            if !transcript.isEmpty {
                let success = await api.processVoiceCommand(transcript)

                await MainActor.run {
                    status = success ? .success : .error
                    KagamiAnalytics.shared.trackVoiceCommand(transcript, success: success)

                    if success {
                        HapticPattern.sceneActivated.play()
                    } else {
                        HapticPattern.error.play()
                    }

                    DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
                        status = .idle
                        transcript = ""
                    }
                }
            } else {
                status = .idle
            }
        }
    }
}

// MARK: - Quick Phrase Chip

struct QuickPhraseChip: View {
    let text: String

    init(_ text: String) {
        self.text = text
    }

    var body: some View {
        Text(text)
            .font(WatchFonts.caption(.caption2))
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(Color.voidLight)
            .cornerRadius(8)
            .accessibilityHidden(true) // Parent handles accessibility
    }
}

// MARK: - Voice Command Help View

/// Shows all available voice commands organized by category
struct VoiceCommandHelpView: View {
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                // Scenes
                CommandCategoryView(
                    title: "Scenes",
                    icon: "sparkles",
                    commands: [
                        ("Movie mode", "Start movie mode"),
                        ("Goodnight", "Prepare for bed"),
                        ("Welcome home", "Activate arrival scene"),
                        ("I'm leaving", "Activate away mode")
                    ]
                )

                // Lights
                CommandCategoryView(
                    title: "Lights",
                    icon: "lightbulb.fill",
                    commands: [
                        ("Lights on", "Turn on lights"),
                        ("Lights off", "Turn off lights"),
                        ("Dim the lights", "Set lights to 30%"),
                        ("Bright lights", "Set lights to 100%")
                    ]
                )

                // Fireplace
                CommandCategoryView(
                    title: "Fireplace",
                    icon: "flame.fill",
                    commands: [
                        ("Turn on fireplace", "Start the fire"),
                        ("Fire", "Toggle fireplace")
                    ]
                )

                // TV
                CommandCategoryView(
                    title: "TV",
                    icon: "tv.fill",
                    commands: [
                        ("TV up", "Raise the TV"),
                        ("TV down", "Lower the TV"),
                        ("Raise TV", "Move TV up"),
                        ("Lower TV", "Move TV down")
                    ]
                )

                // Shades
                CommandCategoryView(
                    title: "Shades",
                    icon: "blinds.horizontal.open",
                    commands: [
                        ("Open shades", "Open window shades"),
                        ("Close shades", "Close window shades"),
                        ("Blinds up", "Open blinds"),
                        ("Curtains down", "Close curtains")
                    ]
                )
            }
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
        }
        .navigationTitle("What can I say?")
        .navigationBarTitleDisplayMode(.inline)
    }
}

/// A category of voice commands with title and list
struct CommandCategoryView: View {
    let title: String
    let icon: String
    let commands: [(String, String)]

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            // Category header
            HStack(spacing: 6) {
                Image(systemName: icon)
                    .font(.system(size: 12))
                    .foregroundColor(.crystal)
                Text(title)
                    .font(WatchFonts.primary(.caption))
                    .foregroundColor(.white)
            }

            // Commands list
            ForEach(commands, id: \.0) { command, description in
                HStack(alignment: .top, spacing: 8) {
                    Text("\"\(command)\"")
                        .font(WatchFonts.caption(.caption2))
                        .foregroundColor(.beacon)
                        .lineLimit(1)
                }
            }
        }
        .padding(10)
        .background(Color.voidLight)
        .cornerRadius(10)
    }
}

#Preview("Voice Help") {
    NavigationStack {
        VoiceCommandHelpView()
    }
}

// MARK: - Speech Recognizer

#if canImport(Speech)
import AVFAudio

class SpeechRecognizer: ObservableObject {
    private var recognitionTask: SFSpeechRecognitionTask?
    private var audioEngine: AVAudioEngine?
    private var recognitionRequest: SFSpeechAudioBufferRecognitionRequest?

    private let speechRecognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US"))

    func startRecording(completion: @escaping (Result<String, Error>) -> Void) {
        // Request authorization
        SFSpeechRecognizer.requestAuthorization { [weak self] status in
            guard status == .authorized else {
                completion(.failure(NSError(domain: "Speech", code: 1, userInfo: [NSLocalizedDescriptionKey: "Not authorized"])))
                return
            }

            DispatchQueue.main.async {
                self?.beginRecording(completion: completion)
            }
        }
    }

    private func beginRecording(completion: @escaping (Result<String, Error>) -> Void) {
        // Cancel any existing task
        recognitionTask?.cancel()
        recognitionTask = nil

        // Configure audio session
        let audioSession = AVAudioSession.sharedInstance()
        do {
            try audioSession.setCategory(.record, mode: .measurement, options: .duckOthers)
            try audioSession.setActive(true, options: .notifyOthersOnDeactivation)
        } catch {
            completion(.failure(error))
            return
        }

        audioEngine = AVAudioEngine()

        guard let audioEngine = audioEngine,
              let speechRecognizer = speechRecognizer,
              speechRecognizer.isAvailable else {
            completion(.failure(NSError(domain: "Speech", code: 2, userInfo: [NSLocalizedDescriptionKey: "Speech recognizer unavailable"])))
            return
        }

        recognitionRequest = SFSpeechAudioBufferRecognitionRequest()

        guard let recognitionRequest = recognitionRequest else {
            completion(.failure(NSError(domain: "Speech", code: 3, userInfo: [NSLocalizedDescriptionKey: "Could not create request"])))
            return
        }

        recognitionRequest.shouldReportPartialResults = true

        let inputNode = audioEngine.inputNode
        let recordingFormat = inputNode.outputFormat(forBus: 0)

        inputNode.installTap(onBus: 0, bufferSize: 1024, format: recordingFormat) { buffer, _ in
            recognitionRequest.append(buffer)
        }

        audioEngine.prepare()

        do {
            try audioEngine.start()
        } catch {
            completion(.failure(error))
            return
        }

        recognitionTask = speechRecognizer.recognitionTask(with: recognitionRequest) { result, error in
            if let result = result {
                completion(.success(result.bestTranscription.formattedString))
            }

            if error != nil || result?.isFinal == true {
                self.stopRecording()
            }
        }
    }

    func stopRecording() {
        audioEngine?.stop()
        audioEngine?.inputNode.removeTap(onBus: 0)
        recognitionRequest?.endAudio()
        recognitionTask?.cancel()

        audioEngine = nil
        recognitionRequest = nil
        recognitionTask = nil
    }
}
#else
// Fallback for watchOS where full Speech framework is not available
class SpeechRecognizer: ObservableObject {
    func startRecording(completion: @escaping (Result<String, Error>) -> Void) {
        // On watchOS, speech recognition is done through VoiceStreamingService
        completion(.failure(NSError(domain: "Speech", code: 2, userInfo: [NSLocalizedDescriptionKey: "Use voice streaming service on watchOS"])))
    }

    func stopRecording() {
        // No-op on watchOS
    }
}
#endif

#Preview {
    VoiceCommandView()
        .environmentObject(KagamiAPIService())
}

/*
 * 鏡
 * Voice is intention.
 */
