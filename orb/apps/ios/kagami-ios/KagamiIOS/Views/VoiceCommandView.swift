//
// VoiceCommandView.swift — Voice Command Interface for iOS
//
// Colony: Spark (e₁) — Ideation
//
// Design Philosophy:
//   - Hold to record
//   - Visual feedback during recording
//   - Instant command execution
//   - Natural language processing
//

import SwiftUI
import Speech
import AVFoundation

struct VoiceCommandView: View {
    @StateObject private var speechRecognizer = SpeechRecognizer()
    @StateObject private var modelSelection = ModelSelection.shared
    @State private var isRecording = false
    @State private var transcript = ""
    @State private var lastCommand = ""
    @State private var commandStatus: CommandStatus = .idle

    enum CommandStatus {
        case idle
        case listening
        case processing
        case success
        case error(String)
    }

    var body: some View {
        VStack(spacing: 24) {
            // Model selector
            HStack {
                Spacer()
                ModelSelectorView(selectedModel: $modelSelection.selectedModel)
            }

            // Status indicator
            statusIndicator

            // Transcript display
            transcriptDisplay

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
        .padding()
        .background(Color.void)
        .navigationTitle("Voice")
        .onAppear {
            speechRecognizer.requestAuthorization()
        }
    }

    // MARK: - Status Indicator

    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    private var statusIndicator: some View {
        VStack(spacing: 8) {
            ZStack {
                // Pulsing ring when recording (respects reduce motion)
                if isRecording && !reduceMotion {
                    Circle()
                        .stroke(Color.spark.opacity(0.3), lineWidth: 3)
                        .frame(width: 100, height: 100)
                        .scaleEffect(isRecording ? 1.3 : 1.0)
                        .opacity(isRecording ? 0 : 1)
                        .animation(.easeOut(duration: 1).repeatForever(autoreverses: false), value: isRecording)
                }

                Circle()
                    .fill(statusColor.opacity(0.2))
                    .frame(width: 80, height: 80)

                Text(statusIcon)
                    .font(.system(.largeTitle))
                    .accessibilityHidden(true)
            }

            Text(statusText)
                .font(KagamiFont.caption())
                .foregroundColor(.accessibleTextSecondary)
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Voice status: \(statusText)")
        .accessibilityAddTraits(.updatesFrequently)
    }

    private var statusIcon: String {
        switch commandStatus {
        case .idle: return "🎤"
        case .listening: return "👂"
        case .processing: return "⏳"
        case .success: return "✓"
        case .error: return "⚠️"
        }
    }

    private var statusColor: Color {
        switch commandStatus {
        case .idle: return .crystal
        case .listening: return .spark
        case .processing: return .beacon
        case .success: return .grove
        case .error: return .safetyViolation
        }
    }

    private var statusText: String {
        switch commandStatus {
        case .idle: return "Tap and hold to speak"
        case .listening: return "Listening..."
        case .processing: return "Processing..."
        case .success: return "Command executed"
        case .error(let msg): return msg
        }
    }

    // MARK: - Transcript Display

    private var transcriptDisplay: some View {
        VStack(spacing: 4) {
            if transcript.isEmpty && !isRecording {
                Text("Say a command like:")
                    .font(KagamiFont.caption())
                    .foregroundColor(.accessibleTextSecondary)
                Text("\"Movie mode\" or \"Lights to 50\"")
                    .font(KagamiFont.body())
                    .foregroundColor(.accessibleTextPrimary.opacity(0.8))
            } else {
                Text(transcript.isEmpty ? "..." : transcript)
                    .font(KagamiFont.title3(weight: .medium))
                    .foregroundColor(.accessibleTextPrimary)
                    .multilineTextAlignment(.center)
                    .frame(minHeight: 60)
            }
        }
        .frame(maxWidth: .infinity)
        .padding()
        .background(Color.voidLight)
        .cornerRadius(16)
        .accessibilityElement(children: .combine)
        .accessibilityLabel(transcript.isEmpty ? "Voice command hint: Say movie mode or lights to 50" : "Transcript: \(transcript)")
        .accessibilityAddTraits(.updatesFrequently)
    }

    // MARK: - Record Button

    private var recordButton: some View {
        Button(action: {}) {
            ZStack {
                Circle()
                    .fill(isRecording ? Color.spark : Color.crystal)
                    .frame(width: 72, height: 72)

                Image(systemName: isRecording ? "stop.fill" : "mic.fill")
                    .font(.system(size: 28))
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
        .scaleEffect(isRecording && !reduceMotion ? 1.1 : 1.0)
        .reducedMotionAnimation(.spring(response: 0.3, dampingFraction: 0.6), value: isRecording)
        .accessibilityLabel(isRecording ? "Stop recording" : "Hold to speak")
        .accessibilityHint(isRecording ? "Release to stop recording" : "Press and hold to start voice command")
    }

    // MARK: - Command Hints

    private var commandHints: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Try saying:")
                .font(KagamiFont.caption())
                .foregroundColor(.accessibleTextSecondary)

            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 8) {
                CommandHint(text: "Movie mode", icon: "🎬")
                CommandHint(text: "Goodnight", icon: "🌙")
                CommandHint(text: "Lights on", icon: "💡")
                CommandHint(text: "Turn on fireplace", icon: "🔥")
            }
        }
        .padding()
        .background(Color.voidLight.opacity(0.5))
        .cornerRadius(12)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Voice command suggestions: Movie mode, Goodnight, Lights on, Turn on fireplace")
    }

    // MARK: - Recording Functions

    private func startRecording() {
        guard speechRecognizer.isAuthorized else {
            commandStatus = .error("Mic permission needed")
            return
        }

        UIImpactFeedbackGenerator(style: .medium).impactOccurred()
        isRecording = true
        transcript = ""
        commandStatus = .listening

        speechRecognizer.startTranscribing { result in
            transcript = result
        }
    }

    private func stopRecording() {
        guard isRecording else { return }

        UIImpactFeedbackGenerator(style: .light).impactOccurred()
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
            let success = await processVoiceCommand(text, model: modelSelection.selectedModel)

            await MainActor.run {
                if success {
                    UINotificationFeedbackGenerator().notificationOccurred(.success)
                    commandStatus = .success
                } else {
                    UINotificationFeedbackGenerator().notificationOccurred(.error)
                    commandStatus = .error("Unknown command")
                }

                // Reset after delay
                DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
                    commandStatus = .idle
                    transcript = ""
                }
            }
        }
    }

    private func processVoiceCommand(_ text: String, model: UserModelKey = .auto) async -> Bool {
        let lower = text.lowercased()

        // For complex commands, use the NL endpoint with model preference
        // Simple commands bypass LLM for speed

        // Scenes
        if lower.contains("movie") {
            await KagamiAPIService.shared.executeScene("movie_mode")
            return true
        }

        if lower.contains("good night") || lower.contains("goodnight") {
            await KagamiAPIService.shared.executeScene("goodnight")
            return true
        }

        if lower.contains("welcome") || lower.contains("home") {
            await KagamiAPIService.shared.executeScene("welcome_home")
            return true
        }

        // Fireplace
        if lower.contains("fire") || lower.contains("fireplace") {
            await KagamiAPIService.shared.toggleFireplace(on: true)
            return true
        }

        // Lights
        if lower.contains("light") {
            if lower.contains("off") {
                await KagamiAPIService.shared.setLights(0)
            } else if lower.contains("dim") {
                await KagamiAPIService.shared.setLights(30)
            } else if let level = extractNumber(from: lower) {
                await KagamiAPIService.shared.setLights(level)
            } else {
                await KagamiAPIService.shared.setLights(100)
            }
            return true
        }

        // TV
        if lower.contains("tv") {
            if lower.contains("down") || lower.contains("lower") {
                await KagamiAPIService.shared.tvControl("lower")
            } else if lower.contains("up") || lower.contains("raise") {
                await KagamiAPIService.shared.tvControl("raise")
            }
            return true
        }

        // Shades
        if lower.contains("shade") || lower.contains("blind") {
            if lower.contains("open") {
                await KagamiAPIService.shared.controlShades("open")
            } else if lower.contains("close") {
                await KagamiAPIService.shared.controlShades("close")
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

// MARK: - Command Hint

struct CommandHint: View {
    let text: String
    let icon: String

    var body: some View {
        HStack(spacing: 6) {
            Text(icon)
                .font(KagamiFont.caption())
                .accessibilityHidden(true)
            Text(text)
                .font(KagamiFont.caption2())
                .foregroundColor(.accessibleTextSecondary)
        }
        .padding(.horizontal, 8)
        .frame(minHeight: 44) // Minimum touch target
        .background(Color.voidLight)
        .cornerRadius(8)
        .accessibilityLabel(text)
    }
}

// MARK: - Speech Recognizer
//
// Note: SpeechRecognizer is defined in Services/SpeechRecognizer.swift
// It provides speech recognition with proper authorization handling,
// error management, and audio session configuration.

#Preview {
    NavigationStack {
        VoiceCommandView()
    }
}

/*
 * 鏡
 * Voice is intention made audible.
 */
