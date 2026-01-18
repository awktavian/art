//
// ComposerBar.swift — Minimal Composer Input
//
// Bottom-anchored input with slash commands and @ mentions.
// Follows Cursor/Spotlight design patterns with delightful microanimations.
//
// Colony: Forge (e2) — Implementation
//

import SwiftUI
import KagamiDesign

struct ComposerBar: View {
    @StateObject private var registry = CommandRegistry.shared
    @EnvironmentObject var theme: KagamiTheme

    @State private var input: String = ""
    @State private var suggestions: [CommandSuggestion] = []
    @State private var selectedIndex: Int = -1
    @State private var isExpanded: Bool = false
    @State private var statusMessage: String? = nil
    @State private var showSuccess: Bool = false

    @FocusState private var isFocused: Bool

    var body: some View {
        VStack(spacing: 0) {
            // Suggestions (above input)
            // Catastrophe easing: swallowtail for modal-like entrances (overshoot creates anticipation)
            if !suggestions.isEmpty && isExpanded {
                SuggestionsView(
                    suggestions: suggestions,
                    selectedIndex: selectedIndex,
                    onSelect: selectSuggestion
                )
                .transition(.asymmetric(
                    insertion: .move(edge: .bottom).combined(with: .opacity).animation(KagamiMotion.swallowtail),
                    removal: .opacity.animation(KagamiMotion.fastSpring)
                ))
            }

            // Input Bar
            HStack(spacing: KagamiSpacing.md) {
                // Prompt with animation
                Text("›")
                    .font(.system(size: 16, weight: .medium, design: .monospaced))
                    .foregroundColor(Color.crystal.opacity(isFocused ? 0.8 : 0.5))
                    .scaleEffect(isFocused ? 1.1 : 1.0)
                    .animation(KagamiMotion.microSpring, value: isFocused)

                // Text Field
                TextField("Type / for commands, @ for context...", text: $input)
                    .font(.system(size: 15))
                    .foregroundColor(.textPrimary)
                    .focused($isFocused)
                    .submitLabel(.send)
                    .onSubmit(handleSubmit)
                    .onChange(of: input) { _, newValue in
                        Task { await updateSuggestions(newValue) }
                    }

                // Success Checkmark (animated)
                if showSuccess {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundColor(.statusSuccess)
                        .font(.system(size: 16))
                        .transition(.scale.combined(with: .opacity))
                }

                // Voice Button
                VoiceButton()
            }
            .padding(.horizontal, KagamiSpacing.md)
            .padding(.vertical, KagamiSpacing.md)
            .background(Color.voidLight)
            .overlay(
                Rectangle()
                    .fill(Color.white.opacity(0.06))
                    .frame(height: 1),
                alignment: .top
            )

            // Status message with slide animation
            if let message = statusMessage {
                StatusBar(message: message)
                    .transition(.move(edge: .bottom).combined(with: .opacity))
            }
        }
        .animation(KagamiMotion.defaultSpring, value: isExpanded)
        .animation(KagamiMotion.fastSpring, value: statusMessage != nil)
        .animation(KagamiMotion.microSpring, value: showSuccess)
    }

    // MARK: - Actions

    private func updateSuggestions(_ text: String) async {
        if text.hasPrefix("/") {
            suggestions = await registry.getSuggestions(for: text)
            selectedIndex = suggestions.isEmpty ? -1 : 0
            withAnimation(KagamiMotion.fastSpring) {
                isExpanded = !suggestions.isEmpty
            }
        } else if text.contains("@") {
            if let atIndex = text.lastIndex(of: "@") {
                let afterAt = String(text[text.index(after: atIndex)...])
                let parts = afterAt.split(separator: ":", maxSplits: 1)
                let type = parts.first.map(String.init)
                let query = parts.count > 1 ? String(parts[1]) : ""

                let mentionItems = await registry.getMentionSuggestions(
                    type: parts.count > 1 ? type : nil,
                    query: parts.count > 1 ? query : (type ?? "")
                )

                suggestions = mentionItems.map {
                    CommandSuggestion(
                        label: $0.label,
                        secondary: $0.secondary,
                        icon: $0.icon,
                        value: $0.value
                    )
                }
                selectedIndex = suggestions.isEmpty ? -1 : 0
                withAnimation(KagamiMotion.fastSpring) {
                    isExpanded = !suggestions.isEmpty
                }
            }
        } else {
            withAnimation(KagamiMotion.fastSpring) {
                suggestions = []
                selectedIndex = -1
                isExpanded = false
            }
        }
    }

    private func selectSuggestion(_ suggestion: CommandSuggestion) {
        // Haptic feedback
        let impact = UIImpactFeedbackGenerator(style: .light)
        impact.impactOccurred()

        if input.hasPrefix("/") {
            input = suggestion.value
        } else if input.contains("@") {
            if let atIndex = input.lastIndex(of: "@") {
                input = String(input[..<atIndex]) + suggestion.value + " "
            }
        }

        withAnimation(KagamiMotion.fastSpring) {
            suggestions = []
            isExpanded = false
        }
    }

    private func handleSubmit() {
        guard !input.trimmingCharacters(in: .whitespaces).isEmpty else { return }

        // Haptic feedback
        let impact = UIImpactFeedbackGenerator(style: .medium)
        impact.impactOccurred()

        Task {
            if input.hasPrefix("/") {
                do {
                    let result = try await registry.executeSlashCommand(input)

                    // Show success animation
                    withAnimation(KagamiMotion.microSpring) {
                        showSuccess = true
                    }

                    statusMessage = result.message ?? "✓ Done"
                    input = ""

                    // Clear after delay
                    try? await Task.sleep(nanoseconds: 500_000_000)
                    withAnimation(KagamiMotion.microSpring) {
                        showSuccess = false
                    }

                    try? await Task.sleep(nanoseconds: 1_500_000_000)
                    withAnimation(KagamiMotion.fastSpring) {
                        statusMessage = nil
                    }
                } catch {
                    // Error haptic
                    let notif = UINotificationFeedbackGenerator()
                    notif.notificationOccurred(.error)

                    statusMessage = error.localizedDescription
                    try? await Task.sleep(nanoseconds: 3_000_000_000)
                    withAnimation {
                        statusMessage = nil
                    }
                }
            } else {
                statusMessage = "Processing..."
                input = ""
                try? await Task.sleep(nanoseconds: 1_000_000_000)
                withAnimation {
                    statusMessage = nil
                }
            }
        }

        withAnimation(KagamiMotion.fastSpring) {
            suggestions = []
            isExpanded = false
        }
    }
}

// MARK: - Voice Button

struct VoiceButton: View {
    @Environment(\.accessibilityReduceMotion) var reduceMotion
    @State private var isRecording = false
    @State private var pulseScale: CGFloat = 1.0

    var body: some View {
        Button {
            withAnimation(reduceMotion ? nil : KagamiMotion.microSpring) {
                isRecording.toggle()
            }

            // Haptic
            let impact = UIImpactFeedbackGenerator(style: .light)
            impact.impactOccurred()
        } label: {
            ZStack {
                // Pulse ring when recording (respects reduce motion)
                if isRecording && !reduceMotion {
                    Circle()
                        .stroke(Color.purple.opacity(0.3), lineWidth: 2)
                        .scaleEffect(pulseScale)
                        .opacity(2 - pulseScale)
                }

                // Button
                Image(systemName: isRecording ? "mic.fill" : "mic")
                    .font(.system(size: 12))
                    .foregroundColor(isRecording ? .purple : .accessibleTextSecondary)
                    .frame(width: 44, height: 44) // Minimum touch target
                    .background(isRecording ? Color.purple.opacity(0.2) : Color.white.opacity(0.05))
                    .clipShape(Circle())
                    .overlay(
                        Circle()
                            .stroke(isRecording ? Color.purple : Color.clear, lineWidth: 1)
                    )
            }
            .frame(width: 44, height: 44) // Minimum touch target
        }
        .pressEffect()
        .accessibilityLabel(isRecording ? "Stop recording" : "Start voice recording")
        .accessibilityHint(isRecording ? "Double tap to stop" : "Double tap to start voice input")
        .onChange(of: isRecording) { _, recording in
            guard !reduceMotion else { return }
            if recording {
                withAnimation(Animation.easeOut(duration: 1).repeatForever(autoreverses: false)) {
                    pulseScale = 2.0
                }
            } else {
                pulseScale = 1.0
            }
        }
    }
}

// MARK: - Status Bar

struct StatusBar: View {
    let message: String

    var body: some View {
        HStack {
            Text(message)
                .font(KagamiFont.caption())
                .foregroundColor(.accessibleTextSecondary)
            Spacer()
        }
        .padding(.horizontal, KagamiSpacing.md)
        .padding(.vertical, KagamiSpacing.sm)
        .background(Color.black.opacity(0.3))
        .accessibilityLabel("Status: \(message)")
        .accessibilityAddTraits(.updatesFrequently)
    }
}

// MARK: - Suggestions View

struct SuggestionsView: View {
    let suggestions: [CommandSuggestion]
    let selectedIndex: Int
    let onSelect: (CommandSuggestion) -> Void

    var body: some View {
        ScrollView {
            LazyVStack(spacing: 0) {
                ForEach(Array(suggestions.enumerated()), id: \.element.id) { index, suggestion in
                    SuggestionRow(
                        suggestion: suggestion,
                        isSelected: index == selectedIndex,
                        onTap: { onSelect(suggestion) }
                    )
                    .slideUpEntrance(delay: Double(index) * 0.03)
                }
            }
        }
        .frame(maxHeight: 200)
        .background(Color.voidLight)
        .overlay(
            Rectangle()
                .fill(Color.white.opacity(0.06))
                .frame(height: 1),
            alignment: .bottom
        )
    }
}

struct SuggestionRow: View {
    let suggestion: CommandSuggestion
    let isSelected: Bool
    let onTap: () -> Void

    @State private var isHovered = false

    var body: some View {
        Button(action: onTap) {
            HStack(spacing: KagamiSpacing.md) {
                // Icon
                Group {
                    if suggestion.icon.count == 1 {
                        Text(suggestion.icon)
                            .font(.system(.subheadline))
                            .accessibilityHidden(true)
                    } else {
                        Image(systemName: suggestion.icon)
                            .font(.system(.footnote))
                            .foregroundColor(.accessibleTextSecondary)
                            .accessibilityHidden(true)
                    }
                }
                .frame(width: 24)

                // Content
                VStack(alignment: .leading, spacing: 2) {
                    Text(suggestion.label)
                        .font(KagamiFont.subheadline(weight: .medium))
                        .foregroundColor(.accessibleTextPrimary)

                    if let secondary = suggestion.secondary {
                        Text(secondary)
                            .font(KagamiFont.caption2())
                            .foregroundColor(.accessibleTextSecondary)
                            .lineLimit(1)
                    }
                }

                Spacer()
            }
            .padding(.horizontal, KagamiSpacing.md)
            .frame(minHeight: 44) // Minimum touch target
            .background(isSelected ? Color.white.opacity(0.08) : Color.clear)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .pressEffect()
        .accessibilityLabel(suggestion.label)
        .accessibilityHint(suggestion.secondary ?? "Double tap to select")
    }
}

// MARK: - Preview

#Preview {
    VStack {
        Spacer()
        ComposerBar()
            .environmentObject(KagamiTheme.shared)
    }
    .background(Color.void)
}
