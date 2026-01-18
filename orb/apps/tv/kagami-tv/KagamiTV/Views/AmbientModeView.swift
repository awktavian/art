//
// AmbientModeView.swift -- Ambient Display Mode for tvOS
//
// Kagami TV -- Beautiful ambient display when idle
//
// Features:
// - Subtle room status visualization
// - Clock display with home state
// - Safety score ambient glow
// - Photo frame mode integration
// - Weather and time of day theming
// - Energy efficient rendering
// - Burn-in prevention with subtle motion
//

import SwiftUI
import KagamiDesign

// MARK: - Ambient Mode View

/// Full-screen ambient display for when the TV is idle
struct AmbientModeView: View {
    @EnvironmentObject var appModel: TVAppModel
    @Environment(\.colorScheme) private var colorScheme

    @State private var currentTime = Date()
    @State private var timeOfDay: TimeOfDay = .day
    @State private var breathingPhase: Double = 0
    @State private var offsetX: CGFloat = 0
    @State private var offsetY: CGFloat = 0

    // Timer for clock updates
    let clockTimer = Timer.publish(every: 1, on: .main, in: .common).autoconnect()
    // Timer for burn-in prevention
    let burnInTimer = Timer.publish(every: 60, on: .main, in: .common).autoconnect()

    var body: some View {
        GeometryReader { geometry in
            ZStack {
                // Background gradient based on time of day
                timeOfDayGradient
                    .ignoresSafeArea()

                // Animated ambient particles
                AmbientParticlesView(timeOfDay: timeOfDay)
                    .opacity(0.3)

                // Main content with burn-in offset
                VStack(spacing: 40) {
                    Spacer()

                    // Clock display
                    ClockDisplay(time: currentTime, timeOfDay: timeOfDay)

                    Spacer()

                    // Room status overview
                    AmbientRoomStatusView(rooms: appModel.rooms)
                        .padding(.horizontal, 100)

                    Spacer()

                    // Safety status indicator
                    SafetyAmbientIndicator(
                        safetyScore: appModel.safetyScore ?? 1.0,
                        breathingPhase: breathingPhase
                    )

                    Spacer()
                }
                .offset(x: offsetX, y: offsetY)

                // Kagami presence orb (subtle)
                KagamiAmbientOrb(
                    isConnected: appModel.isConnected,
                    breathingPhase: breathingPhase
                )
                .position(x: geometry.size.width * 0.9, y: geometry.size.height * 0.1)
            }
        }
        .onReceive(clockTimer) { time in
            currentTime = time
            updateTimeOfDay()
        }
        .onReceive(burnInTimer) { _ in
            updateBurnInOffset()
        }
        .onAppear {
            updateTimeOfDay()
            startBreathingAnimation()
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Ambient mode. \(formattedTime). \(appModel.rooms.count) rooms active.")
    }

    // MARK: - Time of Day

    enum TimeOfDay {
        case dawn, day, dusk, night

        var gradientColors: [Color] {
            switch self {
            case .dawn:
                return [Color(hex: "#1a1a2e"), Color(hex: "#16213e"), Color(hex: "#e94560")]
            case .day:
                return [Color(hex: "#0f0f1a"), Color(hex: "#1a1a2e"), Color(hex: "#2d3436")]
            case .dusk:
                return [Color(hex: "#0d0d14"), Color(hex: "#1a1a2e"), Color(hex: "#d63031")]
            case .night:
                return [Color(hex: "#000000"), Color(hex: "#0a0a14"), Color(hex: "#0d0d1a")]
            }
        }
    }

    private var timeOfDayGradient: LinearGradient {
        LinearGradient(
            colors: timeOfDay.gradientColors,
            startPoint: .top,
            endPoint: .bottom
        )
    }

    private func updateTimeOfDay() {
        let hour = Calendar.current.component(.hour, from: currentTime)

        switch hour {
        case 5..<8:
            timeOfDay = .dawn
        case 8..<17:
            timeOfDay = .day
        case 17..<20:
            timeOfDay = .dusk
        default:
            timeOfDay = .night
        }
    }

    // MARK: - Burn-In Prevention

    private func updateBurnInOffset() {
        withAnimation(.easeInOut(duration: 5)) {
            offsetX = CGFloat.random(in: -20...20)
            offsetY = CGFloat.random(in: -15...15)
        }
    }

    // MARK: - Breathing Animation

    private func startBreathingAnimation() {
        withAnimation(
            .easeInOut(duration: 4.0)
                .repeatForever(autoreverses: true)
        ) {
            breathingPhase = 1.0
        }
    }

    // MARK: - Helpers

    private var formattedTime: String {
        let formatter = DateFormatter()
        formatter.timeStyle = .short
        return formatter.string(from: currentTime)
    }
}

// MARK: - Clock Display

struct ClockDisplay: View {
    let time: Date
    let timeOfDay: AmbientModeView.TimeOfDay

    private var timeString: String {
        let formatter = DateFormatter()
        formatter.dateFormat = "h:mm"
        return formatter.string(from: time)
    }

    private var periodString: String {
        let formatter = DateFormatter()
        formatter.dateFormat = "a"
        return formatter.string(from: time)
    }

    private var dateString: String {
        let formatter = DateFormatter()
        formatter.dateFormat = "EEEE, MMMM d"
        return formatter.string(from: time)
    }

    var body: some View {
        VStack(spacing: 12) {
            HStack(alignment: .top, spacing: 8) {
                Text(timeString)
                    .font(.system(size: 180, weight: .ultraLight, design: .default))
                    .foregroundColor(.white.opacity(0.9))

                Text(periodString)
                    .font(.system(size: 48, weight: .light))
                    .foregroundColor(.white.opacity(0.6))
                    .padding(.top, 24)
            }

            Text(dateString)
                .font(.system(size: 36, weight: .light))
                .foregroundColor(.white.opacity(0.5))
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(timeString) \(periodString), \(dateString)")
    }
}

// MARK: - Ambient Room Status

struct AmbientRoomStatusView: View {
    let rooms: [RoomModel]

    private var activeRooms: [RoomModel] {
        rooms.filter { $0.occupied || $0.avgLightLevel > 0 }
    }

    var body: some View {
        if activeRooms.isEmpty {
            Text("All rooms quiet")
                .font(.system(size: 28, weight: .light))
                .foregroundColor(.white.opacity(0.4))
        } else {
            HStack(spacing: 40) {
                ForEach(activeRooms.prefix(5)) { room in
                    AmbientRoomPill(room: room)
                }

                if activeRooms.count > 5 {
                    Text("+\(activeRooms.count - 5) more")
                        .font(.system(size: 20, weight: .light))
                        .foregroundColor(.white.opacity(0.4))
                }
            }
        }
    }
}

struct AmbientRoomPill: View {
    let room: RoomModel

    private var statusColor: Color {
        if room.occupied {
            return .green.opacity(0.6)
        } else if room.avgLightLevel > 50 {
            return .yellow.opacity(0.5)
        } else if room.avgLightLevel > 0 {
            return .orange.opacity(0.4)
        }
        return .gray.opacity(0.3)
    }

    var body: some View {
        HStack(spacing: 12) {
            Circle()
                .fill(statusColor)
                .frame(width: 10, height: 10)

            Text(room.name)
                .font(.system(size: 22, weight: .light))
                .foregroundColor(.white.opacity(0.7))

            if room.avgLightLevel > 0 {
                Text("\(room.avgLightLevel)%")
                    .font(.system(size: 18, weight: .light))
                    .foregroundColor(.white.opacity(0.4))
            }
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 12)
        .background(
            Capsule()
                .fill(Color.white.opacity(0.05))
                .overlay(
                    Capsule()
                        .stroke(statusColor.opacity(0.3), lineWidth: 1)
                )
        )
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(room.name), \(room.occupied ? "occupied" : "empty"), lights at \(room.avgLightLevel) percent")
    }
}

// MARK: - Safety Ambient Indicator

struct SafetyAmbientIndicator: View {
    let safetyScore: Double
    let breathingPhase: Double

    private var safetyColor: Color {
        if safetyScore >= 0.9 { return .green }
        if safetyScore >= 0.5 { return .yellow }
        return .red
    }

    private var safetyText: String {
        if safetyScore >= 0.9 { return "All systems secure" }
        if safetyScore >= 0.5 { return "Caution" }
        return "Alert"
    }

    var body: some View {
        HStack(spacing: 16) {
            // Breathing safety orb
            Circle()
                .fill(
                    RadialGradient(
                        colors: [safetyColor.opacity(0.8), safetyColor.opacity(0.2)],
                        center: .center,
                        startRadius: 0,
                        endRadius: 20
                    )
                )
                .frame(width: 16 + breathingPhase * 4, height: 16 + breathingPhase * 4)
                .shadow(color: safetyColor.opacity(0.5), radius: 10 + breathingPhase * 5)

            Text(safetyText)
                .font(.system(size: 24, weight: .light))
                .foregroundColor(.white.opacity(0.5))

            Text("Safety: \(String(format: "%.0f", safetyScore * 100))%")
                .font(.system(size: 18, weight: .light, design: .rounded))
                .foregroundColor(safetyColor.opacity(0.7))
        }
        .accessibilityLabel("Safety status: \(safetyText), score \(String(format: "%.0f", safetyScore * 100)) percent")
    }
}

// MARK: - Kagami Ambient Orb

struct KagamiAmbientOrb: View {
    let isConnected: Bool
    let breathingPhase: Double

    private var orbColor: Color {
        isConnected ? .cyan : .orange
    }

    var body: some View {
        ZStack {
            // Outer glow
            Circle()
                .fill(
                    RadialGradient(
                        colors: [orbColor.opacity(0.3), orbColor.opacity(0)],
                        center: .center,
                        startRadius: 0,
                        endRadius: 60
                    )
                )
                .frame(width: 120, height: 120)
                .scaleEffect(1 + breathingPhase * 0.1)

            // Inner orb
            Circle()
                .fill(
                    RadialGradient(
                        colors: [orbColor, orbColor.opacity(0.6)],
                        center: .center,
                        startRadius: 0,
                        endRadius: 25
                    )
                )
                .frame(width: 50, height: 50)
                .shadow(color: orbColor.opacity(0.5), radius: 15 + breathingPhase * 5)

            // Kagami kanji
            Text("鏡")
                .font(.system(size: 18, weight: .bold))
                .foregroundColor(.white.opacity(0.8))
        }
        .accessibilityLabel("Kagami status: \(isConnected ? "connected" : "offline")")
    }
}

// MARK: - Ambient Particles

struct AmbientParticlesView: View {
    let timeOfDay: AmbientModeView.TimeOfDay

    @State private var particles: [AmbientParticle] = []
    let particleTimer = Timer.publish(every: 0.1, on: .main, in: .common).autoconnect()

    struct AmbientParticle: Identifiable {
        let id = UUID()
        var x: CGFloat
        var y: CGFloat
        var size: CGFloat
        var opacity: Double
        var speed: CGFloat
    }

    var body: some View {
        GeometryReader { geometry in
            Canvas { context, size in
                for particle in particles {
                    let rect = CGRect(
                        x: particle.x * size.width,
                        y: particle.y * size.height,
                        width: particle.size,
                        height: particle.size
                    )

                    let color = particleColor.opacity(particle.opacity)
                    context.fill(
                        Circle().path(in: rect),
                        with: .color(color)
                    )
                }
            }
        }
        .onAppear {
            initializeParticles()
        }
        .onReceive(particleTimer) { _ in
            updateParticles()
        }
    }

    private var particleColor: Color {
        switch timeOfDay {
        case .dawn: return .pink
        case .day: return .white
        case .dusk: return .orange
        case .night: return .blue
        }
    }

    private func initializeParticles() {
        particles = (0..<30).map { _ in
            AmbientParticle(
                x: CGFloat.random(in: 0...1),
                y: CGFloat.random(in: 0...1),
                size: CGFloat.random(in: 1...4),
                opacity: Double.random(in: 0.1...0.4),
                speed: CGFloat.random(in: 0.0001...0.001)
            )
        }
    }

    private func updateParticles() {
        for i in 0..<particles.count {
            particles[i].y -= particles[i].speed
            particles[i].x += CGFloat.random(in: -0.0005...0.0005)

            // Wrap around
            if particles[i].y < 0 {
                particles[i].y = 1
                particles[i].x = CGFloat.random(in: 0...1)
            }
        }
    }
}

// MARK: - Color Extension

extension Color {
    init(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let r, g, b: UInt64
        switch hex.count {
        case 6:
            (r, g, b) = (int >> 16, int >> 8 & 0xFF, int & 0xFF)
        default:
            (r, g, b) = (0, 0, 0)
        }
        self.init(.sRGB, red: Double(r)/255, green: Double(g)/255, blue: Double(b)/255)
    }
}

// MARK: - Preview

#Preview {
    AmbientModeView()
        .environmentObject(TVAppModel())
}

/*
 * Mirror
 * h(x) >= 0. Always.
 *
 * The screen breathes with the home.
 * Ambient presence, subtle awareness.
 * Beauty in stillness.
 */
