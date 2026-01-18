//
// CommandPaletteView.swift
// KagamiVision
//
// Floating command palette for spatial computing.
// Appears on gesture or voice activation.
// Positioned dynamically relative to user's head position.
//
// visionOS 2 Features:
//   - Dynamic window placement relative to user head
//   - VoiceOver support for command input
//   - Spatial gesture hints with .spatialGestureHint()
//   - Reduced motion for pulse effects
//   - Consistent .hoverEffect() on all interactive elements
//   - 60pt minimum touch targets per Apple HIG
//

import SwiftUI
import CoreHaptics

struct CommandPaletteView: View {
    @EnvironmentObject var appModel: AppModel
    @EnvironmentObject var spatialServices: SpatialServicesContainer
    @Environment(\.dismiss) private var dismiss
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.openWindow) private var openWindow

    @State private var commandText = ""
    @State private var isListening = false
    @State private var showCommandHistory = false
    @State private var commandHistory: [String] = []
    @FocusState private var isInputFocused: Bool

    // Haptic engine for feedback
    @State private var hapticEngine: CHHapticEngine?

    // Minimum touch target size per Apple HIG (60pt = 0.06m in spatial)
    private let minTouchTargetSize: CGFloat = 60

    var body: some View {
        VStack(spacing: 12) {
            // Main command bar
            HStack(spacing: 16) {
                // Kagami icon with hover effect
                Text("mirror")
                    .font(.system(size: 24))
                    .foregroundColor(.crystal)
                    .frame(width: minTouchTargetSize, height: minTouchTargetSize)
                    .contentShape(.hoverEffect, .rect(cornerRadius: 12))
                    .hoverEffect(.highlight)
                    .accessibilityHidden(true)

                // Command input with minimum font size 16pt
                TextField("Speak or type a command...", text: $commandText)
                    .textFieldStyle(.plain)
                    .font(.system(size: 18, design: .monospaced))
                    .focused($isInputFocused)
                    .onSubmit {
                        executeCommand()
                    }
                    .accessibilityLabel("Command input")
                    .accessibilityHint("Type a command like 'movie mode', 'goodnight', or 'lights on'")

                // Voice button with hover effect and proper touch target
                Button(action: toggleVoice) {
                    Image(systemName: isListening ? "waveform" : "mic.fill")
                        .font(.system(size: 22))
                        .foregroundColor(isListening ? .spark : .crystal)
                        .symbolEffect(.pulse, isActive: isListening && !reduceMotion)
                }
                .frame(width: minTouchTargetSize, height: minTouchTargetSize)
                .contentShape(.hoverEffect, .circle)
                .hoverEffect(.lift)
                .buttonStyle(.plain)
                .accessibilityLabel(isListening ? "Stop voice input" : "Start voice input")
                .accessibilityHint(isListening ? "Tap to stop listening" : "Tap to speak a command")
                .spatialGestureHint(.lookAndPinch)

                // Dismiss button with hover effect
                Button(action: { dismiss() }) {
                    Image(systemName: "xmark.circle.fill")
                        .font(.system(size: 22))
                        .foregroundColor(.secondary)
                }
                .frame(width: minTouchTargetSize, height: minTouchTargetSize)
                .contentShape(.hoverEffect, .circle)
                .hoverEffect(.lift)
                .buttonStyle(.plain)
                .accessibilityLabel("Dismiss command palette")
                .spatialGestureHint(.lookAndPinch)
            }

            // Quick command suggestions
            if commandText.isEmpty && !showCommandHistory {
                HStack(spacing: 12) {
                    QuickCommandButton(icon: "film", label: "Movie", action: {
                        commandText = "movie mode"
                        executeCommand()
                    })

                    QuickCommandButton(icon: "moon.fill", label: "Goodnight", action: {
                        commandText = "goodnight"
                        executeCommand()
                    })

                    QuickCommandButton(icon: "lightbulb.slash", label: "Lights Off", action: {
                        commandText = "lights off"
                        executeCommand()
                    })

                    QuickCommandButton(icon: "flame", label: "Fireplace", action: {
                        commandText = "fireplace"
                        executeCommand()
                    })
                }
                .padding(.top, 8)
            }

            // Command history
            if showCommandHistory && !commandHistory.isEmpty {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Recent Commands")
                        .font(.system(size: 14, weight: .medium))
                        .foregroundColor(.secondary)

                    ForEach(commandHistory.prefix(5), id: \.self) { command in
                        Button(action: {
                            commandText = command
                            showCommandHistory = false
                        }) {
                            HStack {
                                Image(systemName: "clock.arrow.circlepath")
                                    .foregroundColor(.secondary)
                                Text(command)
                                    .font(.system(size: 16))
                                Spacer()
                            }
                            .padding(.vertical, 8)
                        }
                        .frame(minHeight: minTouchTargetSize)
                        .contentShape(.hoverEffect, .rect(cornerRadius: 8))
                        .hoverEffect(.highlight)
                        .buttonStyle(.plain)
                    }
                }
                .padding(.top, 8)
            }
        }
        .padding(.horizontal, 24)
        .padding(.vertical, 20)
        .glassBackgroundEffect()
        .onAppear {
            isInputFocused = true
            prepareHaptics()
            loadCommandHistory()
        }
        .accessibilityElement(children: .contain)
        .accessibilityLabel("Command palette")
    }

    // MARK: - Quick Command Button

    struct QuickCommandButton: View {
        let icon: String
        let label: String
        let action: () -> Void

        private let minTouchTargetSize: CGFloat = 60

        var body: some View {
            Button(action: action) {
                VStack(spacing: 4) {
                    Image(systemName: icon)
                        .font(.system(size: 18))
                        .foregroundColor(.crystal)
                    Text(label)
                        .font(.system(size: 14))
                        .foregroundColor(.secondary)
                }
                .frame(width: minTouchTargetSize, height: minTouchTargetSize)
            }
            .contentShape(.hoverEffect, .rect(cornerRadius: 12))
            .hoverEffect(.lift)
            .buttonStyle(.plain)
            .accessibilityLabel(label)
        }
    }

    // MARK: - Voice Control

    private func toggleVoice() {
        isListening.toggle()
        playHapticFeedback(isListening ? .start : .stop)

        if isListening {
            // Start voice recognition via Speech framework
            startVoiceRecognition()
        } else {
            // Stop and process
            stopVoiceRecognition()
            if !commandText.isEmpty {
                executeCommand()
            }
        }
    }

    private func startVoiceRecognition() {
        // Integration point for Speech framework
        // In production, would use SFSpeechRecognizer
    }

    private func stopVoiceRecognition() {
        // Stop speech recognition
    }

    // MARK: - Command Execution

    private func executeCommand() {
        let text = commandText.lowercased().trimmingCharacters(in: .whitespaces)
        guard !text.isEmpty else { return }

        // Save to history
        saveToHistory(text)

        // Play haptic feedback
        playHapticFeedback(.action)

        Task {
            if text.contains("movie") {
                await appModel.apiService.executeScene("movie_mode")
            } else if text.contains("goodnight") || text.contains("good night") {
                await appModel.apiService.executeScene("goodnight")
            } else if text.contains("welcome") {
                await appModel.apiService.executeScene("welcome_home")
            } else if text.contains("lights") {
                if text.contains("off") {
                    await appModel.apiService.setLights(0)
                } else if text.contains("dim") {
                    await appModel.apiService.setLights(30)
                } else {
                    await appModel.apiService.setLights(100)
                }
            } else if text.contains("fireplace") {
                await appModel.apiService.toggleFireplace()
            } else if text.contains("shades") || text.contains("blinds") {
                if text.contains("open") {
                    await appModel.apiService.controlShades("open")
                } else {
                    await appModel.apiService.controlShades("close")
                }
            }

            // Clear and dismiss
            commandText = ""
            dismiss()
        }
    }

    // MARK: - Command History

    private func loadCommandHistory() {
        commandHistory = UserDefaults.standard.stringArray(forKey: "kagami.commandHistory") ?? []
    }

    private func saveToHistory(_ command: String) {
        // Remove if already exists to avoid duplicates
        commandHistory.removeAll { $0.lowercased() == command.lowercased() }

        // Add to front
        commandHistory.insert(command, at: 0)

        // Keep only last 20
        if commandHistory.count > 20 {
            commandHistory = Array(commandHistory.prefix(20))
        }

        UserDefaults.standard.set(commandHistory, forKey: "kagami.commandHistory")
    }

    // MARK: - Haptic Feedback

    enum HapticType {
        case start
        case stop
        case action
    }

    private func prepareHaptics() {
        guard CHHapticEngine.capabilitiesForHardware().supportsHaptics else { return }

        do {
            hapticEngine = try CHHapticEngine()
            try hapticEngine?.start()
        } catch {
            print("Failed to create haptic engine: \(error)")
        }
    }

    private func playHapticFeedback(_ type: HapticType) {
        guard CHHapticEngine.capabilitiesForHardware().supportsHaptics,
              let engine = hapticEngine else { return }

        let intensity: Float
        let sharpness: Float

        switch type {
        case .start:
            intensity = 0.6
            sharpness = 0.5
        case .stop:
            intensity = 0.4
            sharpness = 0.3
        case .action:
            intensity = 0.8
            sharpness = 0.7
        }

        let event = CHHapticEvent(
            eventType: .hapticTransient,
            parameters: [
                CHHapticEventParameter(parameterID: .hapticIntensity, value: intensity),
                CHHapticEventParameter(parameterID: .hapticSharpness, value: sharpness)
            ],
            relativeTime: 0
        )

        do {
            let pattern = try CHHapticPattern(events: [event], parameters: [])
            let player = try engine.makePlayer(with: pattern)
            try player.start(atTime: 0)
        } catch {
            print("Failed to play haptic: \(error)")
        }
    }
}

#Preview(windowStyle: .plain) {
    CommandPaletteView()
        .environmentObject(AppModel())
        .environmentObject(SpatialServicesContainer())
}

/*
 * Command palette provides natural language interface to Kagami.
 * Dynamic positioning keeps it accessible in spatial space.
 * Hover effects provide visual feedback per visionOS guidelines.
 */
