//
// ModelSelectorView.swift — Mode & Model Selection for iOS
//
// Colony: Nexus (e₄) — Integration
//
// Mode selector (Ask/Plan/Agent) with colony colors.
// Model selector (text-only, no icons).
//
// Created: December 30, 2025
//

import SwiftUI

// MARK: - Mode Definitions

enum KagamiMode: String, CaseIterable, Identifiable {
    case ask = "ask"
    case plan = "plan"
    case agent = "agent"

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .ask: return "Ask"
        case .plan: return "Plan"
        case .agent: return "Agent"
        }
    }

    var description: String {
        switch self {
        case .ask: return "Get answers"
        case .plan: return "Think it through"
        case .agent: return "Make it happen"
        }
    }

    var colonyColor: Color {
        switch self {
        case .ask: return .grove
        case .plan: return .beacon
        case .agent: return .forge
        }
    }
}

// MARK: - Model Definitions (Text Only)

enum UserModelKey: String, CaseIterable, Identifiable {
    case auto = "auto"
    case claude = "claude"
    case gpt4o = "gpt4o"
    case deepseek = "deepseek"
    case gemini = "gemini"
    case local = "local"

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .auto: return "Auto"
        case .claude: return "Claude"
        case .gpt4o: return "GPT-4o"
        case .deepseek: return "DeepSeek"
        case .gemini: return "Gemini"
        case .local: return "Local"
        }
    }
}

// MARK: - Mode Selector View

struct ModeSelectorView: View {
    @Binding var selectedMode: KagamiMode

    var body: some View {
        HStack(spacing: 2) {
            ForEach(KagamiMode.allCases) { mode in
                ModePill(
                    mode: mode,
                    isSelected: mode == selectedMode,
                    onSelect: {
                        withAnimation(.spring(response: 0.2)) {
                            selectedMode = mode
                        }
                        UIImpactFeedbackGenerator(style: .light).impactOccurred()
                    }
                )
            }
        }
        .padding(2)
        .background(Color.white.opacity(0.03))
        .cornerRadius(20)
        .overlay(
            RoundedRectangle(cornerRadius: 20)
                .stroke(Color.white.opacity(0.06), lineWidth: 1)
        )
    }
}

// MARK: - Mode Pill

struct ModePill: View {
    let mode: KagamiMode
    let isSelected: Bool
    let onSelect: () -> Void

    var body: some View {
        Button(action: onSelect) {
            Text(mode.displayName)
                .font(KagamiFont.mono(.caption2, weight: isSelected ? .semibold : .medium))
                .foregroundColor(isSelected ? Color.void : Color.accessibleTextSecondary)
                .padding(.horizontal, 12)
                .frame(minHeight: 44) // Minimum touch target
                .background(isSelected ? mode.colonyColor : Color.clear)
                .cornerRadius(16)
        }
        .buttonStyle(.plain)
        .accessibilityLabel("\(mode.displayName) mode")
        .accessibilityHint(mode.description)
        .accessibilityAddTraits(isSelected ? .isSelected : [])
    }
}

// MARK: - Model Selector View (Text Only)

struct ModelSelectorView: View {
    @Binding var selectedModel: UserModelKey
    @State private var isExpanded = false

    var body: some View {
        Menu {
            ForEach(UserModelKey.allCases) { model in
                Button {
                    selectedModel = model
                    UIImpactFeedbackGenerator(style: .light).impactOccurred()
                } label: {
                    HStack {
                        Text(model.displayName)
                        if model == selectedModel {
                            Image(systemName: "checkmark")
                        }
                    }
                }
            }
        } label: {
            HStack(spacing: 4) {
                Text("Model")
                    .font(KagamiFont.mono(.caption2, weight: .medium))
                    .foregroundColor(.accessibleTextTertiary)
                    .textCase(.uppercase)
                Text(selectedModel.displayName)
                    .font(KagamiFont.mono(.caption2, weight: .medium))
                    .foregroundColor(.accessibleTextPrimary.opacity(0.8))
                Image(systemName: "chevron.down")
                    .font(.system(size: 8, weight: .semibold))
                    .foregroundColor(.accessibleTextTertiary)
            }
            .padding(.horizontal, 10)
            .frame(minHeight: 44) // Minimum touch target
            .background(Color.white.opacity(0.03))
            .cornerRadius(8)
            .overlay(
                RoundedRectangle(cornerRadius: 8)
                    .stroke(Color.white.opacity(0.08), lineWidth: 1)
            )
        }
        .accessibilityLabel("Model selector: \(selectedModel.displayName)")
        .accessibilityHint("Double tap to change AI model")
    }
}

// MARK: - Combined Composer Controls

struct ComposerControlsView: View {
    @Binding var selectedMode: KagamiMode
    @Binding var selectedModel: UserModelKey

    var body: some View {
        HStack {
            ModeSelectorView(selectedMode: $selectedMode)

            Spacer()

            ModelSelectorView(selectedModel: $selectedModel)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
    }
}

// MARK: - Combined Selection Storage

class ComposerSelection: ObservableObject {
    static let shared = ComposerSelection()

    @Published var selectedMode: KagamiMode {
        didSet {
            UserDefaults.standard.set(selectedMode.rawValue, forKey: "kagami-mode-selection")
        }
    }

    @Published var selectedModel: UserModelKey {
        didSet {
            UserDefaults.standard.set(selectedModel.rawValue, forKey: "kagami-model-selection")
        }
    }

    private init() {
        // Load mode
        if let savedMode = UserDefaults.standard.string(forKey: "kagami-mode-selection"),
           let mode = KagamiMode(rawValue: savedMode) {
            self.selectedMode = mode
        } else {
            self.selectedMode = .ask
        }

        // Load model
        if let savedModel = UserDefaults.standard.string(forKey: "kagami-model-selection"),
           let model = UserModelKey(rawValue: savedModel) {
            self.selectedModel = model
        } else {
            self.selectedModel = .auto
        }
    }
}

// MARK: - Preview

#Preview {
    ZStack {
        Color.void.ignoresSafeArea()

        VStack(spacing: 24) {
            Text("Mode Selector")
                .font(.caption)
                .foregroundColor(.white.opacity(0.65))
            ModeSelectorView(selectedMode: .constant(.ask))

            Divider().background(Color.white.opacity(0.1))

            Text("Model Selector")
                .font(.caption)
                .foregroundColor(.white.opacity(0.65))
            ModelSelectorView(selectedModel: .constant(.auto))

            Divider().background(Color.white.opacity(0.1))

            Text("Combined Controls")
                .font(.caption)
                .foregroundColor(.white.opacity(0.65))
            ComposerControlsView(
                selectedMode: .constant(.plan),
                selectedModel: .constant(.claude)
            )
        }
        .padding()
    }
}

/*
 * 鏡
 * Mode shapes intent. Model shapes response.
 * Typography-first. Fano plane secondary.
 */
