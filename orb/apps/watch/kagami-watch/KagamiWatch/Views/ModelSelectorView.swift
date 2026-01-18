//
// ModelSelectorView.swift — Model Selection for watchOS
//
// Colony: Nexus (e₄) — Integration
//
// Simplified model selector for Apple Watch.
// Uses Digital Crown for selection (3 options only for space).
//
// Created: December 30, 2025
//

import SwiftUI

// MARK: - Watch Model Options (Simplified)

enum WatchModelKey: String, CaseIterable, Identifiable {
    case auto = "auto"
    case claude = "claude"
    case local = "local"

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .auto: return "Auto"
        case .claude: return "Claude"
        case .local: return "Local"
        }
    }

    var icon: String {
        switch self {
        case .auto: return "cpu"
        case .claude: return "sparkles"
        case .local: return "iphone"
        }
    }

    var colonyColor: Color {
        switch self {
        case .auto: return .crystal
        case .claude: return .nexus
        case .local: return .flow
        }
    }
}

// MARK: - Watch Model Selector

struct WatchModelSelector: View {
    @Binding var selectedModel: WatchModelKey
    @State private var crownValue: Double = 0

    var body: some View {
        VStack(spacing: 4) {
            HStack(spacing: 4) {
                Image(systemName: selectedModel.icon)
                    .font(.system(size: 14))
                Text(selectedModel.displayName)
                    .font(.system(.caption, design: .rounded).weight(.medium))
            }
            .foregroundColor(selectedModel.colonyColor)
            .padding(.horizontal, 10)
            .padding(.vertical, 6)
            .background(selectedModel.colonyColor.opacity(0.15))
            .cornerRadius(12)

            Text("Crown to change")
                .font(.system(.caption2, design: .rounded))
                .foregroundColor(.secondary)
        }
        .focusable()
        .digitalCrownRotation(
            $crownValue,
            from: 0,
            through: Double(WatchModelKey.allCases.count - 1),
            by: 1,
            sensitivity: .medium,
            isContinuous: false,
            isHapticFeedbackEnabled: true
        )
        .onChange(of: crownValue) { _, newValue in
            let index = Int(newValue.rounded()) % WatchModelKey.allCases.count
            let newModel = WatchModelKey.allCases[index]
            if newModel != selectedModel {
                selectedModel = newModel
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("AI Model: \(selectedModel.displayName)")
        .accessibilityHint("Use the Digital Crown to change the model")
        .accessibilityValue(selectedModel.displayName)
    }
}

// MARK: - Compact Model Pill for Watch

struct WatchModelPill: View {
    let model: WatchModelKey
    let onTap: () -> Void

    var body: some View {
        Button(action: onTap) {
            HStack(spacing: 2) {
                Image(systemName: model.icon)
                    .font(.system(size: 10))
                Text(model.displayName)
                    .font(.system(.caption2, design: .rounded))
            }
            .foregroundColor(model.colonyColor)
            .padding(.horizontal, 6)
            .padding(.vertical, 3)
            .background(model.colonyColor.opacity(0.15))
            .cornerRadius(8)
        }
        .buttonStyle(.plain)
        .minimumTouchTarget()
        .accessibilityLabel("Select \(model.displayName) model")
        .accessibilityHint("Double tap to select this AI model")
    }
}

// MARK: - Model Picker Sheet

struct ModelPickerSheet: View {
    @Binding var selectedModel: WatchModelKey
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        List {
            ForEach(WatchModelKey.allCases) { model in
                Button {
                    selectedModel = model
                    WKInterfaceDevice.current().play(.click)
                    dismiss()
                } label: {
                    HStack {
                        Image(systemName: model.icon)
                            .font(.system(size: 16))
                            .foregroundColor(model.colonyColor)

                        Text(model.displayName)
                            .font(.system(.subheadline, design: .rounded).weight(.medium))

                        Spacer()

                        if model == selectedModel {
                            Image(systemName: "checkmark")
                                .font(.system(size: 12, weight: .semibold))
                                .foregroundColor(.crystal)
                        }
                    }
                    .foregroundColor(model == selectedModel ? model.colonyColor : .white)
                }
                .minimumTouchTarget()
                .accessibilityLabel("\(model.displayName) model")
                .accessibilityValue(model == selectedModel ? "Selected" : "Not selected")
                .accessibilityHint("Double tap to select")
            }
        }
        .navigationTitle("Model")
    }
}

// MARK: - Selection Storage

class WatchModelSelection: ObservableObject {
    static let shared = WatchModelSelection()

    @Published var selectedModel: WatchModelKey {
        didSet {
            UserDefaults.standard.set(selectedModel.rawValue, forKey: "kagami-watch-model")
        }
    }

    private init() {
        if let saved = UserDefaults.standard.string(forKey: "kagami-watch-model"),
           let model = WatchModelKey(rawValue: saved) {
            self.selectedModel = model
        } else {
            self.selectedModel = .auto
        }
    }
}

// MARK: - Preview

#Preview {
    VStack(spacing: 16) {
        WatchModelSelector(selectedModel: .constant(.auto))
        WatchModelPill(model: .claude, onTap: {})
    }
    .background(Color.void)
}

/*
 * 鏡
 * Simple choices for small screens.
 */
