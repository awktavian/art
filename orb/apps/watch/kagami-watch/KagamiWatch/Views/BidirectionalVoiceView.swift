//
// BidirectionalVoiceView.swift — Full Voice Conversation UI
//
// Colony: Spark (e1) — Creation
//
// Rich voice interface for Apple Watch with:
//   - Visual audio level indicator
//   - State-driven animations
//   - Real-time transcript display
//   - Conversation history
//   - Haptic feedback
//
// Created: January 5, 2026
// 鏡

import SwiftUI
import WatchKit
import KagamiDesign

/// Main view for bidirectional voice conversation
struct BidirectionalVoiceView: View {

    @EnvironmentObject var api: KagamiAPIService
    @StateObject private var voiceService = VoiceStreamingService.shared

    @State private var conversationHistory: [ConversationMessage] = []
    @State private var showHistory = false
    @State private var latency: Int = 0

    var body: some View {
        ZStack {
            // Background gradient based on state
            stateGradient
                .ignoresSafeArea()

            VStack(spacing: 12) {
                // Header with status
                header

                // Main content area
                if showHistory && !conversationHistory.isEmpty {
                    conversationList
                } else {
                    mainContent
                }

                // Bottom controls
                controlButtons
            }
            .padding(.horizontal, 8)
        }
        .onAppear {
            voiceService.configure(baseURL: api.baseURL)
        }
    }

    // MARK: - State Gradient

    private var stateGradient: some View {
        let colors: [Color] = {
            switch voiceService.state {
            case .idle:
                return [Color.void, Color.voidLight.opacity(0.3)]
            case .connecting:
                return [Color.nexus.opacity(0.2), Color.void]
            case .listening:
                return [Color.crystal.opacity(0.3), Color.void]
            case .processing:
                return [Color.beacon.opacity(0.2), Color.void]
            case .speaking:
                return [Color.grove.opacity(0.3), Color.void]
            case .error:
                return [Color.safetyViolation.opacity(0.3), Color.void]
            }
        }()

        return LinearGradient(
            colors: colors,
            startPoint: .top,
            endPoint: .bottom
        )
        .animation(.easeInOut(duration: KagamiDuration.slow), value: voiceService.state)
    }

    // MARK: - Header

    private var header: some View {
        HStack {
            // State icon with animation
            Image(systemName: voiceService.state.icon)
                .font(.system(size: 16, weight: .semibold))
                .foregroundColor(stateColor)
                .symbolEffect(.pulse, options: .repeating, isActive: voiceService.state.isActive)

            Text(voiceService.state.displayName)
                .font(.system(size: 14, weight: .medium, design: .rounded))
                .foregroundColor(.white.opacity(0.8))

            Spacer()

            // Latency badge (when available)
            if latency > 0 {
                Text("\(latency)ms")
                    .font(.system(size: 10, weight: .medium, design: .monospaced))
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(Color.white.opacity(0.1))
                    .cornerRadius(8)
            }
        }
        .padding(.top, 4)
    }

    private var stateColor: Color {
        switch voiceService.state {
        case .idle: return .textSecondary
        case .connecting: return .nexus
        case .listening: return .crystal
        case .processing: return .beacon
        case .speaking: return .grove
        case .error: return .safetyViolation
        }
    }

    // MARK: - Main Content

    @ViewBuilder
    private var mainContent: some View {
        VStack(spacing: 16) {
            // Audio visualizer / transcript
            if voiceService.state == .listening {
                audioVisualizer
            } else if !voiceService.currentTranscript.isEmpty {
                transcriptView
            } else if voiceService.state == .idle {
                idlePrompt
            } else if voiceService.state == .error {
                errorView
            } else {
                processingIndicator
            }
        }
        .frame(maxHeight: .infinity)
    }

    // MARK: - Audio Visualizer

    private var audioVisualizer: some View {
        VStack(spacing: 8) {
            // Waveform visualization
            WaveformView(level: voiceService.audioLevel)
                .frame(height: 60)

            // Live transcript (if available)
            if !voiceService.currentTranscript.isEmpty {
                Text(voiceService.currentTranscript)
                    .font(.system(size: 13, weight: .regular, design: .rounded))
                    .foregroundColor(.white.opacity(0.9))
                    .multilineTextAlignment(.center)
                    .lineLimit(3)
                    .padding(.horizontal, 8)
            } else {
                Text("Listening...")
                    .font(.system(size: 12, weight: .medium))
                    .foregroundColor(.white.opacity(0.65))
            }
        }
    }

    // MARK: - Transcript View

    private var transcriptView: some View {
        VStack(spacing: 8) {
            // Speech bubble for transcript
            Text(voiceService.currentTranscript)
                .font(WatchFonts.secondary())
                .foregroundColor(.textPrimary)
                .multilineTextAlignment(.center)
                .padding(12)
                .background(Color.voidLight)
                .cornerRadius(16)

            // Processing indicator
            if voiceService.state == .processing {
                HStack(spacing: 6) {
                    ForEach(0..<3) { i in
                        Circle()
                            .fill(Color.textPrimary.opacity(0.6))
                            .frame(width: 6, height: 6)
                            .scaleEffect(voiceService.state == .processing ? 1.2 : 1.0)
                            .animation(
                                Animation.easeInOut(duration: KagamiDuration.slow)
                                    .repeatForever()
                                    .delay(Double(i) * KagamiDuration.fast),
                                value: voiceService.state
                            )
                    }
                }
            }
        }
    }

    // MARK: - Idle Prompt

    private var idlePrompt: some View {
        VStack(spacing: 12) {
            Image(systemName: "waveform.circle.fill")
                .font(.system(size: 48, weight: .light))
                .foregroundColor(.textSecondary.opacity(0.5))

            Text("Tap to speak")
                .font(WatchFonts.primary(.subheadline))
                .foregroundColor(.textSecondary.opacity(0.65))
        }
    }

    // MARK: - Error View

    private var errorView: some View {
        VStack(spacing: 8) {
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.system(size: 32))
                .foregroundColor(.safetyViolation)

            if let error = voiceService.errorMessage {
                Text(error)
                    .font(WatchFonts.caption(.caption2))
                    .foregroundColor(.textSecondary.opacity(0.7))
                    .multilineTextAlignment(.center)
            }
        }
    }

    // MARK: - Processing Indicator

    private var processingIndicator: some View {
        VStack(spacing: 12) {
            ProgressView()
                .progressViewStyle(CircularProgressViewStyle(tint: .textPrimary))
                .scaleEffect(1.2)

            Text("Processing...")
                .font(WatchFonts.caption(.caption2))
                .foregroundColor(.textSecondary.opacity(0.7))
        }
    }

    // MARK: - Conversation List

    private var conversationList: some View {
        ScrollView {
            LazyVStack(spacing: 8) {
                ForEach(conversationHistory.reversed()) { message in
                    ConversationBubble(message: message)
                }
            }
            .padding(.vertical, 8)
        }
    }

    // MARK: - Control Buttons

    private var controlButtons: some View {
        HStack(spacing: 16) {
            // History toggle
            if !conversationHistory.isEmpty {
                Button {
                    withAnimation(KagamiSpring.default) {
                        showHistory.toggle()
                    }
                } label: {
                    Image(systemName: showHistory ? "waveform" : "clock.arrow.circlepath")
                        .font(.system(size: 18))
                        .foregroundColor(.textPrimary.opacity(0.7))
                }
                .buttonStyle(.plain)
                .watchPressEffect()
            }

            // Main mic button
            Button {
                toggleVoice()
            } label: {
                ZStack {
                    Circle()
                        .fill(voiceService.state.isActive ? Color.safetyViolation : Color.textPrimary)
                        .frame(width: 56, height: 56)

                    Image(systemName: voiceService.state.isActive ? "stop.fill" : "mic.fill")
                        .font(.system(size: 22, weight: .semibold))
                        .foregroundColor(voiceService.state.isActive ? .textPrimary : .void)
                }
            }
            .buttonStyle(.plain)
            .watchPressEffect()
            .disabled(voiceService.state == .connecting || voiceService.state == .processing)

            // Clear history
            if !conversationHistory.isEmpty {
                Button {
                    withAnimation(KagamiSpring.default) {
                        conversationHistory.removeAll()
                    }
                } label: {
                    Image(systemName: "trash")
                        .font(.system(size: 18))
                        .foregroundColor(.textPrimary.opacity(0.7))
                }
                .buttonStyle(.plain)
                .watchPressEffect()
            }
        }
        .padding(.bottom, 8)
    }

    // MARK: - Actions

    private func toggleVoice() {
        if voiceService.state.isActive {
            voiceService.stopVoiceSession()
        } else {
            voiceService.startVoiceSession { result in
                latency = result.latencyMs

                if !result.transcript.isEmpty {
                    // Add user message
                    conversationHistory.append(ConversationMessage(
                        id: UUID().uuidString,
                        text: result.transcript,
                        isUser: true,
                        timestamp: Date()
                    ))
                }

                if let response = result.response {
                    // Add Kagami response
                    conversationHistory.append(ConversationMessage(
                        id: UUID().uuidString,
                        text: response,
                        isUser: false,
                        timestamp: Date()
                    ))
                }

                // Keep only last 10 messages
                if conversationHistory.count > 10 {
                    conversationHistory = Array(conversationHistory.suffix(10))
                }
            }
        }
    }
}

// MARK: - Conversation Message Model

struct ConversationMessage: Identifiable {
    let id: String
    let text: String
    let isUser: Bool
    let timestamp: Date
}

// MARK: - Conversation Bubble

struct ConversationBubble: View {
    let message: ConversationMessage

    var body: some View {
        HStack {
            if message.isUser { Spacer() }

            Text(message.text)
                .font(WatchFonts.caption(.caption2))
                .foregroundColor(.textPrimary)
                .padding(.horizontal, 10)
                .padding(.vertical, 6)
                .background(message.isUser ? Color.nexus.opacity(0.4) : Color.voidLight)
                .cornerRadius(12)

            if !message.isUser { Spacer() }
        }
    }
}

// MARK: - Waveform View

struct WaveformView: View {
    let level: Float
    @State private var phases: [CGFloat] = Array(repeating: 0, count: 20)

    private let barCount = 20
    private let minHeight: CGFloat = 4
    private let maxHeight: CGFloat = 40

    var body: some View {
        HStack(spacing: 2) {
            ForEach(0..<barCount, id: \.self) { i in
                RoundedRectangle(cornerRadius: 2)
                    .fill(barColor(for: i))
                    .frame(width: 4, height: barHeight(for: i))
            }
        }
        .animation(.spring(response: KagamiDuration.instant, dampingFraction: 0.5), value: level)
        .onAppear {
            // Start random phase animation (Fibonacci timing)
            withAnimation(.linear(duration: KagamiDuration.slow).repeatForever(autoreverses: true)) {
                phases = (0..<barCount).map { _ in CGFloat.random(in: 0...1) }
            }
        }
    }

    private func barHeight(for index: Int) -> CGFloat {
        // Normalize audio level (-60 to 0 dB range)
        let normalizedLevel = max(0, min(1, (level + 60) / 60))
        let height = minHeight + CGFloat(normalizedLevel) * (maxHeight - minHeight)

        // Add some variation per bar
        let variation = sin(Double(index) * 0.5 + phases[index] * Double.pi) * 0.3 + 0.7
        return height * CGFloat(variation)
    }

    private func barColor(for index: Int) -> Color {
        let normalizedLevel = max(0, min(1, (level + 60) / 60))

        if normalizedLevel > 0.8 {
            return Color.safetyViolation.opacity(0.8)  // High level = red
        } else if normalizedLevel > 0.5 {
            return Color.beacon.opacity(0.8)  // Medium = beacon/amber
        } else {
            return Color.crystal.opacity(0.6)  // Low = crystal/purple
        }
    }
}

// MARK: - Voice Haptic Patterns
// Note: Using VoiceHaptic to avoid collision with DesignSystem.HapticPattern

enum VoiceHaptic {
    case listening
    case success
    case error

    func play() {
        switch self {
        case .listening:
            WKInterfaceDevice.current().play(.start)
        case .success:
            WKInterfaceDevice.current().play(.success)
        case .error:
            WKInterfaceDevice.current().play(.failure)
        }
    }
}

// MARK: - Logger

// KagamiLogger is defined in KagamiLogger.swift - do not duplicate here

// MARK: - Preview

#Preview {
    BidirectionalVoiceView()
        .environmentObject(KagamiAPIService())
}

/*
 * 鏡
 *
 * The voice carries intent.
 * The ears carry understanding.
 * The loop is complete.
 *
 * h(x) >= 0. Always.
 */
