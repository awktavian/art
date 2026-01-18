//
// VoiceCommandView.swift — Spatial Voice Interface for Vision Pro
//
// Colony: Spark (e₁) — Ideation
//
// Design Philosophy:
//   - Spatial voice interaction
//   - Visual feedback with glass morphism
//   - Natural hand gesture to activate
//   - Command processing with feedback
//
// Phase 2 Accessibility:
//   - VoiceOver support for all status elements
//   - Reduced motion for pulsing animations
//   - Enhanced contrast for glass panels
//   - Meaningful labels for voice interaction
//

import SwiftUI
import Speech
import AVFoundation

struct VoiceCommandView: View {
    @EnvironmentObject var appModel: AppModel
    @StateObject private var speechRecognizer = VisionSpeechRecognizer()
    @State private var isRecording = false
    @State private var transcript = ""
    @State private var lastCommand = ""
    @State private var commandStatus: VisionCommandStatus = .idle

    enum VisionCommandStatus: Equatable {
        case idle
        case listening
        case processing
        case success
        case commandNotUnderstood(String)
        case error(String)

        static func == (lhs: VisionCommandStatus, rhs: VisionCommandStatus) -> Bool {
            switch (lhs, rhs) {
            case (.idle, .idle), (.listening, .listening), (.processing, .processing), (.success, .success):
                return true
            case (.commandNotUnderstood(let l), .commandNotUnderstood(let r)):
                return l == r
            case (.error(let l), .error(let r)):
                return l == r
            default:
                return false
            }
        }
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 32) {
                // Status orb
                statusOrb

                // Transcript display
                transcriptCard

                // Record button
                recordButton

                // Last command
                if !lastCommand.isEmpty {
                    VStack(spacing: 4) {
                        Text("Last command")
                            .font(.caption)
                            .foregroundColor(.secondary)
                        Text(lastCommand)
                            .font(.caption)
                            .foregroundColor(.crystal)
                    }
                }

                Spacer()

                // Command hints
                commandHints
            }
            .padding(32)
            .navigationTitle("Voice")
        }
        .glassBackgroundEffect()
        .onAppear {
            speechRecognizer.requestAuthorization()
        }
    }

    // MARK: - Status Orb

    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    private var statusOrb: some View {
        VStack(spacing: 12) {
            ZStack {
                // Pulsing ring when recording (skip if reduce motion enabled)
                // Using Fibonacci 987ms for cinematic pulse effect
                if isRecording && !reduceMotion {
                    Circle()
                        .stroke(Color.spark.opacity(0.4), lineWidth: 4)
                        .frame(width: 120, height: 120)
                        .scaleEffect(isRecording ? 1.4 : 1.0)
                        .opacity(isRecording ? 0 : 1)
                        .animation(.easeOut(duration: 0.987).repeatForever(autoreverses: false), value: isRecording)
                }

                Circle()
                    .fill(
                        AccessibilitySettings.shared.increaseContrast
                            ? AnyShapeStyle(.thinMaterial)
                            : AnyShapeStyle(.ultraThinMaterial)
                    )
                    .frame(width: 100, height: 100)
                    .overlay(
                        Circle()
                            .stroke(
                                statusColor.opacity(AccessibilitySettings.shared.increaseContrast ? 0.7 : 0.5),
                                lineWidth: AccessibilitySettings.shared.increaseContrast ? 3 : 2
                            )
                    )

                Image(systemName: statusIcon)
                    .font(.system(size: 36))
                    .foregroundColor(statusColor)
                    .accessibilityHidden(true)
            }

            Text(statusText)
                .font(.subheadline)
                .foregroundColor(.secondary)
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Voice command status")
        .accessibilityValue(statusText)
    }

    private var statusIcon: String {
        switch commandStatus {
        case .idle: return "mic.fill"
        case .listening: return "ear"
        case .processing: return "hourglass"
        case .success: return "checkmark.circle.fill"
        case .commandNotUnderstood: return "questionmark.circle.fill"
        case .error: return "exclamationmark.triangle.fill"
        }
    }

    private var isStatusIconSystemImage: Bool {
        return true
    }

    private var statusColor: Color {
        switch commandStatus {
        case .idle: return .crystal
        case .listening: return .spark
        case .processing: return .beacon
        case .success: return .grove
        case .commandNotUnderstood: return .nexus
        case .error: return .red
        }
    }

    private var statusText: String {
        switch commandStatus {
        case .idle: return "Tap and hold to speak"
        case .listening: return "Listening..."
        case .processing: return "Processing..."
        case .success: return "Command executed"
        case .commandNotUnderstood(let text): return "Didn't understand: \"\(text)\""
        case .error(let msg): return msg
        }
    }

    // MARK: - Transcript Card

    private var transcriptCard: some View {
        VStack(spacing: 8) {
            if case .commandNotUnderstood(let text) = commandStatus {
                // Command not understood feedback
                CommandNotUnderstoodView(attemptedCommand: text)
            } else if transcript.isEmpty && !isRecording {
                Text("Say a command like:")
                    .font(.caption)
                    .foregroundColor(.secondary)
                Text("\"Movie mode\" or \"Lights to 50\"")
                    .font(.body)
                    .foregroundColor(.white.opacity(0.8))
            } else {
                Text(transcript.isEmpty ? "..." : transcript)
                    .font(.title3)
                    .fontWeight(.medium)
                    .foregroundColor(.white)
                    .multilineTextAlignment(.center)
            }
        }
        .frame(maxWidth: .infinity, minHeight: 80)
        .padding(20)
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 20))
    }

    // MARK: - Record Button

    private var recordButton: some View {
        Button(action: {}) {
            ZStack {
                Circle()
                    .fill(isRecording ? Color.spark : Color.crystal)
                    .frame(width: 80, height: 80)

                Image(systemName: isRecording ? "stop.fill" : "mic.fill")
                    .font(.system(size: 32))
                    .foregroundColor(.white)
            }
        }
        .buttonStyle(.plain)
        .simultaneousGesture(
            DragGesture(minimumDistance: 0)
                .onChanged { _ in
                    if !isRecording {
                        startRecording()
                    }
                }
                .onEnded { _ in
                    stopRecording()
                }
        )
        .scaleEffect(reduceMotion ? 1.0 : (isRecording ? 1.15 : 1.0))
        .reducedMotionAnimation(isRecording, defaultAnimation: .spring(response: 0.3, dampingFraction: 0.6))
        .hoverEffect(.lift)
        .accessibilityLabel(isRecording ? "Stop recording" : "Start recording")
        .accessibilityHint(isRecording ? "Release to stop recording and process command" : "Press and hold to record voice command")
        .accessibilityAddTraits(.startsMediaSession)
    }

    // MARK: - Command Hints

    private var commandHints: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Try saying:")
                .font(.caption)
                .foregroundColor(.secondary)

            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                VisionCommandHint(text: "Movie mode", systemIcon: SceneIcon.movieMode)
                VisionCommandHint(text: "Goodnight", systemIcon: SceneIcon.goodnight)
                VisionCommandHint(text: "Lights on", systemIcon: SceneIcon.lights)
                VisionCommandHint(text: "Turn on fireplace", systemIcon: SceneIcon.fireplace)
            }
        }
        .padding(20)
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 16))
    }

    // MARK: - Recording Functions

    private func startRecording() {
        guard speechRecognizer.isAuthorized else {
            commandStatus = .error("Mic permission needed")
            return
        }

        isRecording = true
        transcript = ""
        commandStatus = .listening

        speechRecognizer.startTranscribing { result in
            transcript = result
        }
    }

    private func stopRecording() {
        guard isRecording else { return }

        isRecording = false
        speechRecognizer.stopTranscribing()

        if !transcript.isEmpty {
            processCommand(transcript)
        } else {
            commandStatus = .idle
        }
    }

    private func processCommand(_ text: String) {
        commandStatus = .processing
        lastCommand = text

        Task {
            let success = await processVoiceCommand(text)

            await MainActor.run {
                if success {
                    commandStatus = .success
                } else {
                    commandStatus = .commandNotUnderstood(text)
                }

                // Reset after delay (longer for not understood to show suggestions)
                let resetDelay: Double = success ? 2.0 : 4.0
                DispatchQueue.main.asyncAfter(deadline: .now() + resetDelay) {
                    commandStatus = .idle
                    transcript = ""
                }
            }
        }
    }

    private func processVoiceCommand(_ text: String) async -> Bool {
        let lower = text.lowercased()

        // Scenes
        if lower.contains("movie") {
            await appModel.apiService.executeScene("movie_mode")
            return true
        }

        if lower.contains("good night") || lower.contains("goodnight") {
            await appModel.apiService.executeScene("goodnight")
            return true
        }

        if lower.contains("welcome") || lower.contains("home") {
            await appModel.apiService.executeScene("welcome_home")
            return true
        }

        // Fireplace
        if lower.contains("fire") || lower.contains("fireplace") {
            await appModel.apiService.toggleFireplace()
            return true
        }

        // Lights
        if lower.contains("light") {
            if lower.contains("off") {
                await appModel.apiService.setLights(0)
            } else if lower.contains("dim") {
                await appModel.apiService.setLights(30)
            } else if let level = extractNumber(from: lower) {
                await appModel.apiService.setLights(level)
            } else {
                await appModel.apiService.setLights(100)
            }
            return true
        }

        // TV
        if lower.contains("tv") {
            if lower.contains("down") || lower.contains("lower") {
                await appModel.apiService.tvControl("lower")
            } else if lower.contains("up") || lower.contains("raise") {
                await appModel.apiService.tvControl("raise")
            }
            return true
        }

        // Shades
        if lower.contains("shade") || lower.contains("blind") {
            if lower.contains("open") {
                await appModel.apiService.controlShades("open")
            } else if lower.contains("close") {
                await appModel.apiService.controlShades("close")
            }
            return true
        }

        return false
    }

    private func extractNumber(from text: String) -> Int? {
        let numbers = text.components(separatedBy: CharacterSet.decimalDigits.inverted)
            .compactMap { Int($0) }
            .filter { $0 >= 0 && $0 <= 100 }
        return numbers.first
    }
}

// MARK: - Vision Command Hint

struct VisionCommandHint: View {
    let text: String
    let systemIcon: String

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: systemIcon)
                .font(.body)
                .foregroundColor(.crystal)
                .accessibilityHidden(true)
            Text(text)
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(
            AccessibilitySettings.shared.increaseContrast
                ? AnyShapeStyle(.thinMaterial)
                : AnyShapeStyle(.ultraThinMaterial),
            in: RoundedRectangle(cornerRadius: 10)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 10)
                .stroke(Color.adaptiveGlassBorder, lineWidth: AccessibilitySettings.shared.increaseContrast ? 1 : 0)
        )
        .accessibilityLabel("Example command: \(text)")
    }
}

// MARK: - Command Not Understood View

/// Distinct visual pattern when a voice command is not recognized.
/// Shows helpful suggestions for similar valid commands.
struct CommandNotUnderstoodView: View {
    let attemptedCommand: String

    var body: some View {
        VStack(spacing: 12) {
            // Visual indicator
            HStack(spacing: 8) {
                Image(systemName: "questionmark.circle.fill")
                    .foregroundColor(.nexus)
                Text("I didn't understand that")
                    .font(.headline)
                    .foregroundColor(.white)
            }

            // Show what was heard
            Text("You said: \"\(attemptedCommand)\"")
                .font(.caption)
                .foregroundColor(.secondary)

            // Suggestions
            VStack(alignment: .leading, spacing: 8) {
                Text("Try saying:")
                    .font(.caption)
                    .foregroundColor(.secondary)

                let suggestions = getSuggestions(for: attemptedCommand)
                ForEach(suggestions, id: \.self) { suggestion in
                    HStack(spacing: 4) {
                        Image(systemName: "arrow.turn.down.right")
                            .font(.caption2)
                            .foregroundColor(.crystal)
                        Text("\"\(suggestion)\"")
                            .font(.caption)
                            .foregroundColor(.crystal)
                    }
                }
            }
        }
        .padding(16)
        .background(Color.nexus.opacity(0.1), in: RoundedRectangle(cornerRadius: 12))
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(Color.nexus.opacity(0.3), lineWidth: 1)
        )
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Command not understood. You said: \(attemptedCommand)")
    }

    private func getSuggestions(for input: String) -> [String] {
        let lower = input.lowercased()

        // Context-aware suggestions based on what was attempted
        if lower.contains("light") {
            return ["Lights on", "Lights to 50 percent", "Turn off lights"]
        } else if lower.contains("movie") || lower.contains("tv") || lower.contains("watch") {
            return ["Movie mode", "Lower TV", "Raise TV"]
        } else if lower.contains("night") || lower.contains("sleep") || lower.contains("bed") {
            return ["Goodnight", "Turn off all lights"]
        } else if lower.contains("shade") || lower.contains("blind") || lower.contains("window") {
            return ["Open shades", "Close shades"]
        } else if lower.contains("fire") || lower.contains("warm") {
            return ["Turn on fireplace", "Turn off fireplace"]
        } else {
            // Default suggestions
            return ["Movie mode", "Goodnight", "Lights on"]
        }
    }
}

// MARK: - Vision Speech Recognizer

@MainActor
class VisionSpeechRecognizer: ObservableObject {
    @Published var isAuthorized = false

    private var audioEngine: AVAudioEngine?
    private var recognitionRequest: SFSpeechAudioBufferRecognitionRequest?
    private var recognitionTask: SFSpeechRecognitionTask?
    private let speechRecognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US"))

    func requestAuthorization() {
        SFSpeechRecognizer.requestAuthorization { [weak self] status in
            DispatchQueue.main.async {
                self?.isAuthorized = status == .authorized
            }
        }
    }

    func startTranscribing(onResult: @escaping (String) -> Void) {
        guard let speechRecognizer = speechRecognizer, speechRecognizer.isAvailable else {
            return
        }

        // Configure audio session
        let audioSession = AVAudioSession.sharedInstance()
        try? audioSession.setCategory(.record, mode: .measurement, options: .duckOthers)
        try? audioSession.setActive(true, options: .notifyOthersOnDeactivation)

        audioEngine = AVAudioEngine()
        guard let audioEngine = audioEngine else { return }

        recognitionRequest = SFSpeechAudioBufferRecognitionRequest()
        guard let recognitionRequest = recognitionRequest else { return }

        recognitionRequest.shouldReportPartialResults = true

        let inputNode = audioEngine.inputNode
        let recordingFormat = inputNode.outputFormat(forBus: 0)

        inputNode.installTap(onBus: 0, bufferSize: 1024, format: recordingFormat) { buffer, _ in
            self.recognitionRequest?.append(buffer)
        }

        audioEngine.prepare()
        try? audioEngine.start()

        recognitionTask = speechRecognizer.recognitionTask(with: recognitionRequest) { result, error in
            if let result = result {
                let transcript = result.bestTranscription.formattedString
                onResult(transcript)
            }

            if error != nil || result?.isFinal == true {
                self.stopTranscribing()
            }
        }
    }

    func stopTranscribing() {
        audioEngine?.stop()
        audioEngine?.inputNode.removeTap(onBus: 0)
        recognitionRequest?.endAudio()
        recognitionTask?.cancel()

        audioEngine = nil
        recognitionRequest = nil
        recognitionTask = nil
    }
}

#Preview(windowStyle: .plain) {
    VoiceCommandView()
        .environmentObject(AppModel())
}

/*
 * 鏡
 * Voice is intention made spatial.
 */
