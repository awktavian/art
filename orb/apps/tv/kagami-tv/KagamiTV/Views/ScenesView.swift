//
// ScenesView.swift -- Scene Activation for tvOS
//
// Kagami TV -- Large, TV-friendly scene buttons
//
// Features:
// - Grid of scene cards with icons and descriptions
// - Focus-based navigation
// - Visual feedback during execution
// - High-contrast design for TV viewing
//

import SwiftUI
import KagamiDesign

// MARK: - Scenes View

struct ScenesView: View {
    // Scenes using colony colors for semantic meaning
    let scenes = [
        TVScene(id: "movie_mode", name: "Movie Mode", icon: "film.fill", description: "Dim lights, lower TV, close shades", color: .forge),      // e2 - Implementation
        TVScene(id: "goodnight", name: "Goodnight", icon: "moon.fill", description: "All lights off, lock doors", color: .nexus),               // e4 - Integration
        TVScene(id: "welcome_home", name: "Welcome Home", icon: "house.fill", description: "Warm lights, open shades", color: .crystal),
        TVScene(id: "away", name: "Away Mode", icon: "lock.fill", description: "Secure house, reduce energy", color: .nexus),                   // e4 - Integration
        TVScene(id: "focus", name: "Focus Mode", icon: "target", description: "Bright lights, minimize distractions", color: .beacon),          // e5 - Planning
        TVScene(id: "relax", name: "Relax", icon: "flame.fill", description: "Dim lights, fireplace on", color: .spark),                        // e1 - Ideation
        TVScene(id: "coffee", name: "Coffee Time", icon: "cup.and.saucer.fill", description: "Bright kitchen lights", color: .forge),           // e2 - Implementation
        TVScene(id: "exit_movie_mode", name: "Exit Movie", icon: "xmark.circle.fill", description: "Return to normal lighting", color: .flow),  // e3 - Adaptation
    ]

    private let columns = [
        GridItem(.flexible(), spacing: TVDesign.gridSpacing),
        GridItem(.flexible(), spacing: TVDesign.gridSpacing),
        GridItem(.flexible(), spacing: TVDesign.gridSpacing),
        GridItem(.flexible(), spacing: TVDesign.gridSpacing)
    ]

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: TVDesign.sectionSpacing) {
                    // Header
                    Text("Activate a scene to transform your home")
                        .font(.system(size: TVDesign.bodySize))
                        .foregroundColor(.white.opacity(0.7))

                    // Scenes Grid
                    LazyVGrid(columns: columns, spacing: TVDesign.gridSpacing) {
                        ForEach(scenes) { scene in
                            TVSceneButton(
                                icon: scene.icon,
                                title: scene.name,
                                description: scene.description,
                                color: scene.color
                            ) {
                                await KagamiAPIService.shared.executeScene(scene.id)
                            }
                        }
                    }

                    // Safety Footer
                    SafetyFooter()
                }
                .padding(TVDesign.contentPadding)
            }
            .background(Color.black.ignoresSafeArea())
            .navigationTitle("Scenes")
        }
    }
}

// MARK: - TV Scene Model

struct TVScene: Identifiable {
    let id: String
    let name: String
    let icon: String
    let description: String
    let color: Color
}

// MARK: - Safety Footer

struct SafetyFooter: View {
    var body: some View {
        HStack {
            Spacer()
            Text("Safety First")
                .font(.system(size: TVDesign.captionSize))
                .foregroundColor(TVDesign.primaryColor.opacity(0.65))  // Increased from 0.5 for WCAG compliance
            Spacer()
        }
        .padding(.top, TVDesign.sectionSpacing)
        .accessibilityLabel("Safety First")
    }
}

// MARK: - Preview

#Preview {
    ScenesView()
}

/*
 * Kagami - Smart Home Scenes
 */
