//
// SpatialToolbar.swift -- Spatial Toolbar Ornament for visionOS
//
// Kagami Vision -- Customizable ornament-based toolbar
//
// Colony: Crystal (e7) -- Verification & Polish
//
// Features:
// - Reusable ornament toolbar for any window
// - Primary/secondary action slots
// - Quick action orbital layout
// - Accessibility support with VoiceOver labels
// - Animation with Fibonacci timing
// - Glass material styling
//
// visionOS 2 Features Used:
// - .ornament() modifier
// - .glassBackgroundEffect()
// - .hoverEffect()
// - AccessibilityLabeledPairRole
//
// Created: January 11, 2026
// Mirror
//

import SwiftUI

// MARK: - Spatial Toolbar

/// A configurable ornament toolbar for visionOS windows.
/// Attach to any view using the `.spatialToolbar()` modifier.
struct SpatialToolbar<Content: View>: View {
    let actions: [SpatialToolbarAction]
    let position: SpatialToolbarPosition
    @ViewBuilder let customContent: () -> Content

    @State private var hoveredAction: String?

    init(
        actions: [SpatialToolbarAction],
        position: SpatialToolbarPosition = .bottom,
        @ViewBuilder customContent: @escaping () -> Content = { EmptyView() }
    ) {
        self.actions = actions
        self.position = position
        self.customContent = customContent
    }

    var body: some View {
        HStack(spacing: 16) {
            // Custom content slot
            customContent()

            if actions.count <= 4 {
                // Standard horizontal layout for few actions
                horizontalLayout
            } else {
                // Orbital layout for many actions
                orbitalLayout
            }
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 12)
        .glassBackgroundEffect()
        .clipShape(Capsule())
        .accessibilityElement(children: .contain)
        .accessibilityLabel("Toolbar")
    }

    // MARK: - Layouts

    private var horizontalLayout: some View {
        ForEach(actions) { action in
            SpatialToolbarButton(
                action: action,
                isHovered: hoveredAction == action.id
            )
            .onHover { isHovered in
                withAnimation(.spring(response: 0.233, dampingFraction: 0.85)) {
                    hoveredAction = isHovered ? action.id : nil
                }
            }
        }
    }

    @ViewBuilder
    private var orbitalLayout: some View {
        let primaryActions = actions.filter { $0.isPrimary }
        let secondaryActions = actions.filter { !$0.isPrimary }

        // Primary actions always visible
        ForEach(primaryActions) { action in
            SpatialToolbarButton(
                action: action,
                isHovered: hoveredAction == action.id
            )
        }

        // Secondary actions in a menu
        if !secondaryActions.isEmpty {
            Menu {
                ForEach(secondaryActions) { action in
                    Button(action: action.handler) {
                        Label(action.label, systemImage: action.icon)
                    }
                }
            } label: {
                Image(systemName: "ellipsis.circle.fill")
                    .font(.system(size: 24))
                    .foregroundStyle(.secondary)
            }
            .menuStyle(.borderlessButton)
            .accessibilityLabel("More actions")
        }
    }
}

// MARK: - Toolbar Button

struct SpatialToolbarButton: View {
    let action: SpatialToolbarAction
    let isHovered: Bool

    // Minimum touch target per Apple HIG
    private let minTouchTarget: CGFloat = 60

    var body: some View {
        Button(action: action.handler) {
            VStack(spacing: 4) {
                Image(systemName: action.icon)
                    .font(.system(size: 20, weight: .medium))
                    .foregroundStyle(action.color)

                if isHovered || action.showLabel {
                    Text(action.label)
                        .font(.system(size: 12, weight: .medium))
                        .foregroundStyle(.secondary)
                        .transition(.opacity.combined(with: .scale(scale: 0.9)))
                }
            }
            .frame(minWidth: minTouchTarget, minHeight: minTouchTarget)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .hoverEffect(.highlight)
        .accessibilityLabel(action.label)
        .accessibilityHint(action.accessibilityHint ?? "")
        .accessibilityAddTraits(.isButton)
        .scaleEffect(isHovered ? 1.1 : 1.0)
        .animation(.spring(response: 0.144, dampingFraction: 0.8), value: isHovered)
    }
}

// MARK: - Types

/// Position for the spatial toolbar ornament
enum SpatialToolbarPosition {
    case top
    case bottom
    case leading
    case trailing

    var attachmentAnchor: UnitPoint {
        switch self {
        case .top: return .top
        case .bottom: return .bottom
        case .leading: return .leading
        case .trailing: return .trailing
        }
    }

    var contentAlignment: Alignment {
        switch self {
        case .top: return .bottom
        case .bottom: return .top
        case .leading: return .trailing
        case .trailing: return .leading
        }
    }
}

/// An action for the spatial toolbar
struct SpatialToolbarAction: Identifiable {
    let id: String
    let icon: String
    let label: String
    let color: Color
    let isPrimary: Bool
    let showLabel: Bool
    let accessibilityHint: String?
    let handler: () -> Void

    init(
        id: String,
        icon: String,
        label: String,
        color: Color = .crystal,
        isPrimary: Bool = true,
        showLabel: Bool = false,
        accessibilityHint: String? = nil,
        handler: @escaping () -> Void
    ) {
        self.id = id
        self.icon = icon
        self.label = label
        self.color = color
        self.isPrimary = isPrimary
        self.showLabel = showLabel
        self.accessibilityHint = accessibilityHint
        self.handler = handler
    }
}

// MARK: - View Modifier

/// Modifier to add a spatial toolbar ornament to a view
struct SpatialToolbarModifier: ViewModifier {
    let actions: [SpatialToolbarAction]
    let position: SpatialToolbarPosition

    func body(content: Content) -> some View {
        content
            .ornament(
                visibility: .visible,
                attachmentAnchor: .scene(position.attachmentAnchor),
                contentAlignment: position.contentAlignment
            ) {
                SpatialToolbar(actions: actions, position: position) {
                    EmptyView()
                }
            }
    }
}

extension View {
    /// Adds a spatial toolbar ornament to the view.
    ///
    /// - Parameters:
    ///   - actions: The toolbar actions to display.
    ///   - position: Where to attach the toolbar (default: .bottom).
    /// - Returns: The view with the toolbar ornament attached.
    ///
    /// Example:
    /// ```swift
    /// ContentView()
    ///     .spatialToolbar(actions: [
    ///         SpatialToolbarAction(
    ///             id: "lights",
    ///             icon: "lightbulb.fill",
    ///             label: "Lights",
    ///             color: .beacon
    ///         ) {
    ///             // Toggle lights
    ///         }
    ///     ])
    /// ```
    func spatialToolbar(
        actions: [SpatialToolbarAction],
        position: SpatialToolbarPosition = .bottom
    ) -> some View {
        modifier(SpatialToolbarModifier(actions: actions, position: position))
    }
}

// MARK: - Predefined Actions

extension SpatialToolbarAction {
    /// Predefined action for toggling all lights
    static func lightsToggle(handler: @escaping () -> Void) -> SpatialToolbarAction {
        SpatialToolbarAction(
            id: "lights_toggle",
            icon: "lightbulb.fill",
            label: "Lights",
            color: .beacon,
            accessibilityHint: "Toggle all lights on or off",
            handler: handler
        )
    }

    /// Predefined action for movie mode
    static func movieMode(handler: @escaping () -> Void) -> SpatialToolbarAction {
        SpatialToolbarAction(
            id: "movie_mode",
            icon: "film.fill",
            label: "Movie",
            color: .forge,
            accessibilityHint: "Activate movie mode for dim lights and closed shades",
            handler: handler
        )
    }

    /// Predefined action for goodnight
    static func goodnight(handler: @escaping () -> Void) -> SpatialToolbarAction {
        SpatialToolbarAction(
            id: "goodnight",
            icon: "moon.zzz.fill",
            label: "Goodnight",
            color: .nexus,
            accessibilityHint: "Turn off all lights and lock doors",
            handler: handler
        )
    }

    /// Predefined action for settings
    static func settings(handler: @escaping () -> Void) -> SpatialToolbarAction {
        SpatialToolbarAction(
            id: "settings",
            icon: "gearshape.fill",
            label: "Settings",
            color: .crystal,
            isPrimary: false,
            accessibilityHint: "Open settings",
            handler: handler
        )
    }

    /// Predefined action for voice command
    static func voiceCommand(handler: @escaping () -> Void) -> SpatialToolbarAction {
        SpatialToolbarAction(
            id: "voice",
            icon: "mic.fill",
            label: "Voice",
            color: .grove,
            accessibilityHint: "Activate voice command input",
            handler: handler
        )
    }

    /// Predefined action for entering immersive space
    static func enterImmersive(handler: @escaping () -> Void) -> SpatialToolbarAction {
        SpatialToolbarAction(
            id: "immersive",
            icon: "cube.fill",
            label: "Immersive",
            color: .crystal,
            accessibilityHint: "Enter full immersive space",
            handler: handler
        )
    }
}

// MARK: - Preview

#Preview {
    VStack {
        Text("Main Content")
            .font(.largeTitle)
    }
    .frame(width: 400, height: 300)
    .glassBackgroundEffect()
    .spatialToolbar(actions: [
        .lightsToggle { print("Lights toggled") },
        .movieMode { print("Movie mode") },
        .goodnight { print("Goodnight") },
        .voiceCommand { print("Voice") },
        .settings { print("Settings") },
    ])
}

/*
 * Mirror
 * h(x) >= 0. Always.
 *
 * The toolbar floats beneath the window,
 * actions within arm's reach, always ready.
 * Spatial interaction at its finest.
 */
