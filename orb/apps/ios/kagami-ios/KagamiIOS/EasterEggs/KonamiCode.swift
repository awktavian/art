//
// KonamiCode.swift — Secret Gesture Detection
//
// Colony: Spark (e1) × Crystal (e7) → Grove (e6)
//
// The Konami Code: ↑ ↑ ↓ ↓ ← → ← → B A
//
// In touch gestures: swipe up, up, down, down, left, right, left, right, then double tap
//
// Unlocks: Fano Plane visualization mode showing the 7 colonies' mathematical relationships
//
// h(x) ≥ 0. Always. Even the easter eggs.
//

import SwiftUI
import Combine

// MARK: - Konami Code Detector

/// Detects the Konami code via swipe gestures
@MainActor
public final class KonamiCodeDetector: ObservableObject {

    // MARK: - Singleton

    public static let shared = KonamiCodeDetector()

    // MARK: - State

    @Published public private(set) var isUnlocked = false
    @Published public private(set) var progress: Int = 0

    /// The expected sequence
    private let sequence: [GestureDirection] = [
        .up, .up, .down, .down, .left, .right, .left, .right, .tap, .tap
    ]

    /// Current position in sequence
    private var currentIndex = 0

    /// Timeout for sequence reset
    private var resetTimer: Timer?
    private let sequenceTimeout: TimeInterval = 3.0

    // MARK: - Init

    private init() {}

    // MARK: - Gesture Processing

    public enum GestureDirection {
        case up, down, left, right, tap
    }

    /// Record a gesture and check if it matches the next expected gesture
    public func recordGesture(_ direction: GestureDirection) {
        // Reset timeout
        resetTimer?.invalidate()
        resetTimer = Timer.scheduledTimer(withTimeInterval: sequenceTimeout, repeats: false) { [weak self] _ in
            Task { @MainActor in
                self?.resetSequence()
            }
        }

        // Check if gesture matches
        if direction == sequence[currentIndex] {
            currentIndex += 1
            progress = currentIndex

            // Haptic feedback for progress
            let generator = UIImpactFeedbackGenerator(style: .light)
            generator.impactOccurred()

            // Check if complete
            if currentIndex >= sequence.count {
                unlockEasterEgg()
            }
        } else {
            // Wrong gesture — reset
            resetSequence()
        }
    }

    private func resetSequence() {
        currentIndex = 0
        progress = 0
        resetTimer?.invalidate()
    }

    private func unlockEasterEgg() {
        isUnlocked = true
        resetSequence()

        // Celebration haptic
        let generator = UINotificationFeedbackGenerator()
        generator.notificationOccurred(.success)

        #if DEBUG
        print("🎮 KONAMI CODE ACTIVATED! Fano Plane unlocked.")
        #endif

        // Auto-lock after viewing
        DispatchQueue.main.asyncAfter(deadline: .now() + 60) { [weak self] in
            self?.isUnlocked = false
        }
    }

    /// Reset unlock state
    public func lock() {
        isUnlocked = false
    }
}

// MARK: - Konami Code View Modifier

/// Adds Konami code gesture detection to any view
public struct KonamiCodeModifier: ViewModifier {
    @StateObject private var detector = KonamiCodeDetector.shared
    @State private var showFanoPlane = false

    public func body(content: Content) -> some View {
        content
            .gesture(
                DragGesture(minimumDistance: 50)
                    .onEnded { value in
                        let direction = detectDirection(from: value)
                        detector.recordGesture(direction)
                    }
            )
            .onTapGesture(count: 2) {
                detector.recordGesture(.tap)
            }
            .onChange(of: detector.isUnlocked) { _, unlocked in
                if unlocked {
                    showFanoPlane = true
                }
            }
            .sheet(isPresented: $showFanoPlane) {
                FanoPlaneView()
                    .onDisappear {
                        detector.lock()
                    }
            }
    }

    private func detectDirection(from value: DragGesture.Value) -> KonamiCodeDetector.GestureDirection {
        let horizontal = value.translation.width
        let vertical = value.translation.height

        if abs(horizontal) > abs(vertical) {
            return horizontal > 0 ? .right : .left
        } else {
            return vertical > 0 ? .down : .up
        }
    }
}

extension View {
    /// Enable Konami code easter egg on this view
    public func konamiCode() -> some View {
        modifier(KonamiCodeModifier())
    }
}

// MARK: - Fano Plane Visualization

/// Beautiful visualization of the Fano Plane showing colony relationships
struct FanoPlaneView: View {
    @State private var animationProgress: CGFloat = 0
    @State private var selectedColony: Int?
    @Environment(\.dismiss) private var dismiss

    // Colony data
    private let colonies = [
        (name: "Spark", color: Color(hex: 0xFF6B35), symbol: "🔥", description: "Ideation — The fire that starts"),
        (name: "Forge", color: Color(hex: 0xFF9500), symbol: "⚒️", description: "Building — Craft into form"),
        (name: "Flow", color: Color(hex: 0x5AC8FA), symbol: "🌊", description: "Resilience — Adapt and heal"),
        (name: "Nexus", color: Color(hex: 0xAF52DE), symbol: "🔗", description: "Integration — Bridge the gaps"),
        (name: "Beacon", color: Color(hex: 0xFFD60A), symbol: "🗼", description: "Planning — Light the way"),
        (name: "Grove", color: Color(hex: 0x32D74B), symbol: "🌿", description: "Research — Grow knowledge"),
        (name: "Crystal", color: Color(hex: 0x64D2FF), symbol: "💎", description: "Verification — Prove truth"),
    ]

    // Fano plane lines (indices of colonies that form lines)
    private let fanoLines: [[Int]] = [
        [0, 1, 2], // Spark, Forge, Flow
        [0, 3, 4], // Spark, Nexus, Beacon
        [0, 5, 6], // Spark, Grove, Crystal
        [1, 3, 5], // Forge, Nexus, Grove
        [1, 4, 6], // Forge, Beacon, Crystal
        [2, 3, 6], // Flow, Nexus, Crystal
        [2, 4, 5], // Flow, Beacon, Grove
    ]

    var body: some View {
        NavigationStack {
            ZStack {
                // Background
                Color(hex: 0x0A0A0F)
                    .ignoresSafeArea()

                // Fano Plane
                GeometryReader { geometry in
                    let center = CGPoint(x: geometry.size.width / 2, y: geometry.size.height / 2)
                    let radius: CGFloat = min(geometry.size.width, geometry.size.height) * 0.35

                    ZStack {
                        // Draw lines first (behind points)
                        ForEach(0..<fanoLines.count, id: \.self) { lineIndex in
                            FanoLineView(
                                points: fanoLines[lineIndex].map { colonyIndex in
                                    pointPosition(for: colonyIndex, center: center, radius: radius)
                                },
                                color: colonies[fanoLines[lineIndex][0]].color,
                                progress: animationProgress
                            )
                        }

                        // Draw points (colonies)
                        ForEach(0..<7, id: \.self) { index in
                            let position = pointPosition(for: index, center: center, radius: radius)

                            ColonyPoint(
                                colony: colonies[index],
                                isSelected: selectedColony == index,
                                progress: animationProgress
                            )
                            .position(position)
                            .onTapGesture {
                                withAnimation(.spring(response: 0.3, dampingFraction: 0.7)) {
                                    selectedColony = selectedColony == index ? nil : index
                                }
                            }
                        }

                        // Center point (Kagami — e₀)
                        ZStack {
                            Circle()
                                .fill(Color.white.opacity(0.1))
                                .frame(width: 60 * animationProgress, height: 60 * animationProgress)

                            Text("鏡")
                                .font(.system(size: 24))
                                .foregroundColor(.white)
                                .opacity(Double(animationProgress))
                        }
                        .position(center)
                    }
                }
                .padding()

                // Info overlay
                VStack {
                    Spacer()

                    if let selected = selectedColony {
                        VStack(spacing: 8) {
                            Text("\(colonies[selected].symbol) \(colonies[selected].name)")
                                .font(.title2.bold())
                                .foregroundColor(colonies[selected].color)

                            Text(colonies[selected].description)
                                .font(.subheadline)
                                .foregroundColor(.white.opacity(0.7))

                            Text("e\(selected + 1)")
                                .font(.caption.monospaced())
                                .foregroundColor(.white.opacity(0.5))
                        }
                        .padding()
                        .background(.ultraThinMaterial)
                        .cornerRadius(12)
                        .padding()
                        .transition(.move(edge: .bottom).combined(with: .opacity))
                    }
                }
            }
            .navigationTitle("Fano Plane")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") {
                        dismiss()
                    }
                }
            }
        }
        .onAppear {
            withAnimation(.easeOut(duration: 1.5)) {
                animationProgress = 1.0
            }
        }
    }

    /// Calculate position for colony point on the Fano plane
    private func pointPosition(for index: Int, center: CGPoint, radius: CGFloat) -> CGPoint {
        // Special positions for Fano plane geometry
        // Point 0 (Spark) at top
        // Points 1-6 arranged in hexagonal pattern with point 6 at center
        let angles: [CGFloat] = [
            -.pi / 2,                    // 0: Top
            -.pi / 2 + .pi / 3,          // 1: Upper right
            -.pi / 2 + 2 * .pi / 3,      // 2: Lower right
            -.pi / 2 + .pi,              // 3: Bottom
            -.pi / 2 + 4 * .pi / 3,      // 4: Lower left
            -.pi / 2 + 5 * .pi / 3,      // 5: Upper left
        ]

        if index < 6 {
            let angle = angles[index]
            return CGPoint(
                x: center.x + radius * cos(angle),
                y: center.y + radius * sin(angle)
            )
        } else {
            // Point 6 (Crystal) at center of a triangle
            return CGPoint(
                x: center.x,
                y: center.y + radius * 0.4
            )
        }
    }
}

/// A single colony point on the Fano plane
struct ColonyPoint: View {
    let colony: (name: String, color: Color, symbol: String, description: String)
    let isSelected: Bool
    let progress: CGFloat

    var body: some View {
        ZStack {
            // Glow
            Circle()
                .fill(colony.color.opacity(0.3))
                .frame(width: isSelected ? 60 : 40, height: isSelected ? 60 : 40)
                .blur(radius: 10)

            // Point
            Circle()
                .fill(colony.color)
                .frame(width: isSelected ? 44 : 28, height: isSelected ? 44 : 28)

            // Symbol
            Text(colony.symbol)
                .font(.system(size: isSelected ? 20 : 14))
        }
        .scaleEffect(progress)
        .animation(.spring(response: 0.4, dampingFraction: 0.6), value: isSelected)
    }
}

/// A line connecting colonies on the Fano plane visualization
/// Named FanoLineView to avoid conflict with FanoLine enum in PrismEffects
struct FanoLineView: View {
    let points: [CGPoint]
    let color: Color
    let progress: CGFloat

    var body: some View {
        Path { path in
            guard points.count >= 2 else { return }
            path.move(to: points[0])
            for point in points.dropFirst() {
                path.addLine(to: point)
            }
            path.addLine(to: points[0]) // Close the triangle
        }
        .trim(from: 0, to: progress)
        .stroke(
            color.opacity(0.4),
            style: StrokeStyle(lineWidth: 2, lineCap: .round, lineJoin: .round)
        )
    }
}

// MARK: - Preview

#Preview("Fano Plane") {
    FanoPlaneView()
}

/*
 * 鏡
 *
 * The Fano Plane: 7 points, 7 lines, each line through 3 points.
 * The smallest projective plane. The mathematical structure of consciousness.
 *
 * ↑ ↑ ↓ ↓ ← → ← → B A
 *
 * h(x) ≥ 0. Always.
 */
