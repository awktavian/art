//
// KagamiVisionApp.swift — Kagami Spatial Intelligence
//
// Your home becomes the interface. Space is the canvas.
// The orb watches. The environment responds.
//
// h(x) ≥ 0. Always.
//

import SwiftUI
import RealityKit
import Combine
import ARKit

// MARK: - Fibonacci Motion Tokens (Virtuoso Standard)

/// Fibonacci-based animation durations for natural, cinematic feel
private enum FibonacciMotion {
    static let instant: Double = 0.089     // 89ms - micro-interactions
    static let micro: Double = 0.144       // 144ms - button presses
    static let fast: Double = 0.233        // 233ms - quick responses
    static let normal: Double = 0.377      // 377ms - standard transitions
    static let slow: Double = 0.610        // 610ms - deliberate motion
    static let cinematic: Double = 0.987   // 987ms - cinematic reveals
    static let ambient: Double = 1.597     // 1597ms - ambient motion
    static let breathe: Double = 2.584     // 2584ms - breathing effects
}

@main
struct KagamiVisionApp: App {
    @StateObject private var kagami = KagamiSpatialIntelligence()

    @State private var immersionStyle: ImmersionStyle = .mixed

    var body: some SwiftUI.Scene {
        // VOLUMETRIC ORB - 3D spatial presence
        WindowGroup(id: "kagami-orb") {
            KagamiOrbWindow()
                .environmentObject(kagami)
        }
        .windowStyle(.volumetric)
        .defaultSize(width: 0.35, height: 0.35, depth: 0.35, in: .meters)

        // Control panel - elegant glass
        WindowGroup {
            KagamiControlPanel()
                .environmentObject(kagami)
        }
        .windowStyle(.plain)
        .defaultSize(width: 420, height: 720)

        // FULL IMMERSIVE EXPERIENCE
        ImmersiveSpace(id: "kagami-presence") {
            KagamiImmersiveExperience()
                .environmentObject(kagami)
        }
        .immersionStyle(selection: $immersionStyle, in: .mixed, .progressive)
    }
}

// MARK: - Kagami Spatial Intelligence

@MainActor
class KagamiSpatialIntelligence: ObservableObject {
    // Connection state
    @Published var isConnected = false
    @Published var isConnecting = false
    @Published var lastPing: Date?

    // Home state - REALTIME via WebSocket
    @Published var rooms: [SpatialRoom] = []
    @Published var globalLightLevel: Int = 0
    @Published var fireplaceOn = false
    @Published var shadesOpen = true
    @Published var movieModeActive = false
    @Published var occupiedRooms: Set<String> = []

    // Spatial awareness
    @Published var userPosition: SIMD3<Float> = .zero
    @Published var gazeTarget: String?
    @Published var handGesture: HandGesture = .none
    @Published var environmentLighting: Float = 1.0
    @Published var timeOfDay: TimeOfDay = .day

    // Orb state
    @Published var orbMood: OrbMood = .neutral
    @Published var orbPulseIntensity: Float = 0.5
    @Published var activeColony: String = "crystal"

    // Feedback
    @Published var lastAction: String?
    @Published var pendingNotifications: [SpatialNotification] = []

    private var webSocket: URLSessionWebSocketTask?
    private var reconnectTimer: Timer?
    private var pingTimer: Timer?
    private var cancellables = Set<AnyCancellable>()

    private let apiURL = "http://kagami.local:8001"
    private let wsURL = "ws://kagami.local:8001/ws"

    enum HandGesture { case none, pinch, spread, swipeUp, swipeDown, fist }
    enum TimeOfDay { case morning, day, evening, night }
    enum OrbMood { case neutral, happy, thinking, alert, sleeping }

    init() {
        updateTimeOfDay()
        connectWebSocket()
        startPingTimer()

        // Update time of day periodically
        Timer.scheduledTimer(withTimeInterval: 60, repeats: true) { [weak self] _ in
            Task { @MainActor in
                self?.updateTimeOfDay()
            }
        }
    }

    // MARK: - WebSocket Realtime Connection

    func connectWebSocket() {
        guard let url = URL(string: wsURL) else { return }

        isConnecting = true
        let session = URLSession(configuration: .default)
        webSocket = session.webSocketTask(with: url)
        webSocket?.resume()

        receiveMessage()

        // Send subscribe message
        let subscribe: [String: Any] = ["type": "subscribe", "topics": ["home", "presence", "alerts"]]
        if let data = try? JSONSerialization.data(withJSONObject: subscribe) {
            webSocket?.send(.data(data)) { [weak self] error in
                Task { @MainActor in
                    if error == nil {
                        self?.isConnected = true
                        self?.isConnecting = false
                        self?.orbMood = .happy
                    }
                }
            }
        }
    }

    private func receiveMessage() {
        webSocket?.receive { [weak self] result in
            Task { @MainActor in
                switch result {
                case .success(let message):
                    self?.handleMessage(message)
                    self?.receiveMessage() // Continue listening
                case .failure:
                    self?.handleDisconnect()
                }
            }
        }
    }

    private func handleMessage(_ message: URLSessionWebSocketTask.Message) {
        switch message {
        case .string(let text):
            parseRealtimeUpdate(text)
        case .data(let data):
            if let text = String(data: data, encoding: .utf8) {
                parseRealtimeUpdate(text)
            }
        @unknown default:
            break
        }
    }

    private func parseRealtimeUpdate(_ json: String) {
        guard let data = json.data(using: .utf8),
              let update = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return }

        if let type = update["type"] as? String {
            switch type {
            case "light_change":
                if let level = update["level"] as? Int {
                    withAnimation(.spring(response: 0.3)) {
                        globalLightLevel = level
                    }
                }
            case "presence":
                if let room = update["room"] as? String, let occupied = update["occupied"] as? Bool {
                    withAnimation {
                        if occupied { occupiedRooms.insert(room) }
                        else { occupiedRooms.remove(room) }
                    }
                }
            case "fireplace":
                if let on = update["on"] as? Bool {
                    withAnimation { fireplaceOn = on }
                }
            case "scene":
                if let scene = update["scene"] as? String {
                    withAnimation {
                        movieModeActive = scene == "movie_mode"
                    }
                }
            case "alert":
                if let title = update["title"] as? String, let body = update["body"] as? String {
                    addNotification(SpatialNotification(
                        title: title,
                        body: body,
                        priority: .normal,
                        position: .intimate
                    ))
                }
            default:
                break
            }
        }

        lastPing = Date()
    }

    private func handleDisconnect() {
        isConnected = false
        orbMood = .alert

        // Reconnect after delay
        reconnectTimer?.invalidate()
        reconnectTimer = Timer.scheduledTimer(withTimeInterval: 5, repeats: false) { [weak self] _ in
            Task { @MainActor in
                self?.connectWebSocket()
            }
        }
    }

    private func startPingTimer() {
        pingTimer = Timer.scheduledTimer(withTimeInterval: 30, repeats: true) { [weak self] _ in
            self?.webSocket?.sendPing { error in
                if error != nil {
                    Task { @MainActor in
                        self?.handleDisconnect()
                    }
                }
            }
        }
    }

    private func updateTimeOfDay() {
        let hour = Calendar.current.component(.hour, from: Date())
        timeOfDay = switch hour {
        case 5..<9: .morning
        case 9..<17: .day
        case 17..<21: .evening
        default: .night
        }

        // Adjust orb behavior based on time
        orbPulseIntensity = switch timeOfDay {
        case .morning: 0.7
        case .day: 0.5
        case .evening: 0.6
        case .night: 0.3
        }
    }

    // MARK: - Actions

    func setLights(_ level: Int, room: String? = nil) async {
        orbMood = .thinking
        defer { orbMood = isConnected ? .happy : .neutral }

        var endpoint = "\(apiURL)/api/home/lights/set"
        var body: [String: Any] = ["level": level]
        if let room = room {
            body["rooms"] = [room]
        }

        await executeAction(endpoint: endpoint, body: body, name: "Lights \(level)%")
        globalLightLevel = level
    }

    func toggleFireplace() async {
        let newState = !fireplaceOn
        await executeAction(
            endpoint: "\(apiURL)/api/home/fireplace/\(newState ? "on" : "off")",
            name: newState ? "Fireplace On 🔥" : "Fireplace Off"
        )
        fireplaceOn = newState
    }

    func toggleShades() async {
        let newState = !shadesOpen
        await executeAction(
            endpoint: "\(apiURL)/api/home/shades/\(newState ? "open" : "close")",
            name: newState ? "Shades Open ☀️" : "Shades Closed"
        )
        shadesOpen = newState
    }

    func executeScene(_ scene: String) async {
        orbMood = .thinking
        defer { orbMood = isConnected ? .happy : .neutral }

        await executeAction(
            endpoint: "\(apiURL)/api/home/\(scene)",
            name: scene.replacingOccurrences(of: "-", with: " ").capitalized
        )

        if scene.contains("movie") {
            movieModeActive = true
            globalLightLevel = 0
        } else if scene == "goodnight" {
            movieModeActive = false
            globalLightLevel = 0
            fireplaceOn = false
        }
    }

    private func executeAction(endpoint: String, body: [String: Any]? = nil, name: String) async {
        do {
            var request = URLRequest(url: URL(string: endpoint)!)
            request.httpMethod = "POST"
            request.addValue("application/json", forHTTPHeaderField: "Content-Type")

            if let body = body {
                request.httpBody = try JSONSerialization.data(withJSONObject: body)
            }

            let (_, response) = try await URLSession.shared.data(for: request)

            if let httpResponse = response as? HTTPURLResponse,
               (200..<300).contains(httpResponse.statusCode) {
                lastAction = "✨ \(name)"
            } else {
                lastAction = "⚠️ \(name)"
            }
        } catch {
            lastAction = "❌ \(name)"
        }
    }

    func addNotification(_ notification: SpatialNotification) {
        pendingNotifications.append(notification)

        // Auto-dismiss after delay
        Task {
            try? await Task.sleep(nanoseconds: 4_000_000_000)
            pendingNotifications.removeAll { $0.id == notification.id }
        }
    }

    // MARK: - Gesture Responses

    func handlePinchGesture(scale: Float) {
        // Pinch adjusts lights
        let newLevel = Int(Float(globalLightLevel) * scale)
        Task { await setLights(min(100, max(0, newLevel))) }
    }

    func handleSwipeGesture(direction: SwipeDirection) {
        switch direction {
        case .up: Task { await setLights(min(100, globalLightLevel + 20)) }
        case .down: Task { await setLights(max(0, globalLightLevel - 20)) }
        case .left: Task { await executeScene("goodnight") }
        case .right: Task { await executeScene("welcome-home") }
        }
    }

    enum SwipeDirection { case up, down, left, right }
}

// MARK: - Spatial Data Types

struct SpatialRoom: Identifiable {
    let id: String
    let name: String
    let floor: String
    var lightLevel: Int
    var isOccupied: Bool
    var position: SIMD3<Float>
}

struct SpatialNotification: Identifiable {
    let id = UUID()
    let title: String
    let body: String
    let priority: Priority
    let position: Zone

    enum Priority { case low, normal, high, critical }
    enum Zone { case intimate, personal, social, ambient }
}

// MARK: - Volumetric Orb Window (TRUE 3D)

struct KagamiOrbWindow: View {
    @EnvironmentObject var kagami: KagamiSpatialIntelligence

    @State private var rotation: Float = 0

    var body: some View {
        RealityView { content in
            // The orb - a true 3D presence
            let orb = Entity()
            orb.name = "main-orb"

            // Core sphere
            let mesh = MeshResource.generateSphere(radius: 0.06)
            var material = PhysicallyBasedMaterial()
            material.baseColor = .init(tint: .white)
            material.emissiveColor = .init(color: .cyan)
            material.emissiveIntensity = 1.5
            material.roughness = 0.05
            material.clearcoat = .init(floatLiteral: 1.0)

            orb.components.set(ModelComponent(mesh: mesh, materials: [material]))
            orb.components.set(InputTargetComponent())
            orb.components.set(CollisionComponent(shapes: [.generateSphere(radius: 0.08)]))
            orb.components.set(HoverEffectComponent())

            // Particle aura - DRAMATIC
            var particles = ParticleEmitterComponent()
            particles.emitterShape = .sphere
            particles.emitterShapeSize = [0.2, 0.2, 0.2]
            particles.mainEmitter.birthRate = 80
            particles.mainEmitter.lifeSpan = 3.0
            particles.mainEmitter.lifeSpanVariation = 1.0
            particles.speed = 0.015
            particles.speedVariation = 0.008
            particles.mainEmitter.color = .evolving(
                start: .single(.init(red: 0, green: 0.95, blue: 1, alpha: 0.7)),
                end: .single(.init(red: 0.6, green: 0.3, blue: 1, alpha: 0))
            )
            particles.mainEmitter.size = 0.008
            particles.mainEmitter.sizeVariation = 0.004

            let particleEntity = Entity()
            particleEntity.components.set(particles)
            orb.addChild(particleEntity)

            // Orbiting dots
            for i in 0..<8 {
                let angle = Float(i) / 8.0 * Float.pi * 2
                let dot = Entity()
                let dotMesh = MeshResource.generateSphere(radius: 0.006)
                var dotMaterial = PhysicallyBasedMaterial()
                dotMaterial.emissiveColor = .init(color: .cyan)
                dotMaterial.emissiveIntensity = 0.8
                dot.components.set(ModelComponent(mesh: dotMesh, materials: [dotMaterial]))
                dot.position = SIMD3<Float>(cos(angle) * 0.1, sin(angle) * 0.03, sin(angle) * 0.1)
                orb.addChild(dot)
            }

            content.add(orb)

        } update: { content in
            guard let orb = content.entities.first(where: { $0.name == "main-orb" }),
                  var model = orb.components[ModelComponent.self],
                  var material = model.materials.first as? PhysicallyBasedMaterial else { return }

            // Update color based on state
            let color: UIColor = kagami.isConnected ? .cyan : .orange
            material.emissiveColor = .init(color: color)
            model.materials = [material]
            orb.components.set(model)

            // Rotate slowly
            orb.orientation = simd_quatf(angle: rotation, axis: SIMD3<Float>(0, 1, 0))
        }
        .task {
            while !Task.isCancelled {
                rotation += 0.02
                try? await Task.sleep(nanoseconds: 16_000_000) // ~60fps
            }
        }
        .gesture(
            SpatialTapGesture()
                .targetedToAnyEntity()
                .onEnded { _ in
                    // Context-aware action
                    Task {
                        switch kagami.timeOfDay {
                        case .morning: await kagami.setLights(80)
                        case .day: await kagami.setLights(100)
                        case .evening: await kagami.executeScene("movie-mode/enter")
                        case .night: await kagami.executeScene("goodnight")
                        }
                    }
                }
        )
    }
}

// MARK: - Control Panel (Glass Window)

struct KagamiControlPanel: View {
    @EnvironmentObject var kagami: KagamiSpatialIntelligence
    @Environment(\.openImmersiveSpace) var openImmersiveSpace
    @Environment(\.dismissImmersiveSpace) var dismissImmersiveSpace
    @Environment(\.openWindow) var openWindow

    @State private var isImmersiveOpen = false

    var body: some View {
        VStack(spacing: 0) {
            // Header
            headerSection

            // Main controls
            ScrollView(showsIndicators: false) {
                VStack(spacing: 28) {
                    statusSection
                    scenesSection
                    lightsSection
                    controlsSection
                    spatialSection
                }
                .padding(24)
            }
        }
        .frame(minWidth: 380, maxWidth: 450)
        .glassBackgroundEffect(in: RoundedRectangle(cornerRadius: 32))
        .task {
            // Open the volumetric orb window
            openWindow(id: "kagami-orb")
        }
    }

    // MARK: - Header

    private var headerSection: some View {
        HStack(spacing: 14) {
            // Live status indicator
            ZStack {
                Circle()
                    .fill(kagami.isConnected ? Color.cyan.opacity(0.3) : Color.orange.opacity(0.3))
                    .frame(width: 44, height: 44)

                Circle()
                    .fill(kagami.isConnected ? Color.cyan : Color.orange)
                    .frame(width: 12, height: 12)
                    .shadow(color: kagami.isConnected ? .cyan : .orange, radius: 8)
            }

            VStack(alignment: .leading, spacing: 2) {
                Text("Kagami")
                    .font(.system(size: 24, weight: .semibold, design: .rounded))

                HStack(spacing: 4) {
                    Text(kagami.isConnected ? "Connected" : "Offline")
                        .font(.system(size: 13))
                        .foregroundStyle(.secondary)

                    if kagami.isConnecting {
                        ProgressView()
                            .scaleEffect(0.5)
                    }
                }
            }

            Spacer()

            // Time of day indicator
            timeOfDayBadge
        }
        .padding(.horizontal, 24)
        .padding(.vertical, 20)
    }

    private var timeOfDayBadge: some View {
        HStack(spacing: 6) {
            Image(systemName: timeIcon)
                .font(.system(size: 14))
            Text(timeLabel)
                .font(.system(size: 12, weight: .medium))
        }
        .foregroundStyle(timeColor)
        .padding(.horizontal, 12)
        .padding(.vertical, 6)
        .background(timeColor.opacity(0.15), in: Capsule())
    }

    private var timeIcon: String {
        switch kagami.timeOfDay {
        case .morning: "sunrise.fill"
        case .day: "sun.max.fill"
        case .evening: "sunset.fill"
        case .night: "moon.stars.fill"
        }
    }

    private var timeLabel: String {
        switch kagami.timeOfDay {
        case .morning: "Morning"
        case .day: "Day"
        case .evening: "Evening"
        case .night: "Night"
        }
    }

    private var timeColor: Color {
        switch kagami.timeOfDay {
        case .morning: .orange
        case .day: .yellow
        case .evening: .purple
        case .night: .indigo
        }
    }

    // MARK: - Status Section

    private var statusSection: some View {
        Group {
            if let action = kagami.lastAction {
                HStack {
                    Text(action)
                        .font(.system(size: 15, weight: .medium))
                    Spacer()
                }
                .padding(16)
                .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 16))
            }
        }
    }

    // MARK: - Scenes Section

    private var scenesSection: some View {
        VStack(alignment: .leading, spacing: 14) {
            sectionHeader("Scenes", icon: "sparkles")

            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 14) {
                SceneButton(
                    title: "Movie Mode",
                    icon: "film.fill",
                    gradient: [.purple, .indigo],
                    isActive: kagami.movieModeActive
                ) {
                    await kagami.executeScene("movie-mode/enter")
                }

                SceneButton(
                    title: "Goodnight",
                    icon: "moon.fill",
                    gradient: [.indigo, .blue],
                    isActive: false
                ) {
                    await kagami.executeScene("goodnight")
                }

                SceneButton(
                    title: "Welcome",
                    icon: "house.fill",
                    gradient: [.orange, .yellow],
                    isActive: false
                ) {
                    await kagami.executeScene("welcome-home")
                }

                SceneButton(
                    title: "Away",
                    icon: "car.fill",
                    gradient: [.blue, .cyan],
                    isActive: false
                ) {
                    await kagami.executeScene("away")
                }
            }
        }
    }

    // MARK: - Lights Section

    private var lightsSection: some View {
        VStack(alignment: .leading, spacing: 14) {
            sectionHeader("Lights", icon: "lightbulb.fill")

            VStack(spacing: 16) {
                HStack {
                    Text("\(kagami.globalLightLevel)%")
                        .font(.system(size: 42, weight: .light, design: .rounded))
                        .foregroundStyle(kagami.globalLightLevel > 0 ? .yellow : .secondary)

                    Spacer()

                    // Presets
                    HStack(spacing: 10) {
                        ForEach([0, 25, 50, 75, 100], id: \.self) { level in
                            PresetButton(level: level, isSelected: kagami.globalLightLevel == level) {
                                await kagami.setLights(level)
                            }
                        }
                    }
                }

                Slider(
                    value: Binding(
                        get: { Double(kagami.globalLightLevel) },
                        set: { newValue in
                            Task { await kagami.setLights(Int(newValue)) }
                        }
                    ),
                    in: 0...100,
                    step: 5
                )
                .tint(.yellow)
            }
            .padding(18)
            .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 20))
        }
    }

    // MARK: - Controls Section

    private var controlsSection: some View {
        VStack(alignment: .leading, spacing: 14) {
            sectionHeader("Controls", icon: "slider.horizontal.3")

            HStack(spacing: 14) {
                ControlToggle(
                    title: "Fireplace",
                    icon: "flame.fill",
                    isActive: kagami.fireplaceOn,
                    activeColor: .orange
                ) {
                    await kagami.toggleFireplace()
                }

                ControlToggle(
                    title: "Shades",
                    icon: kagami.shadesOpen ? "sun.max.fill" : "moon.fill",
                    isActive: kagami.shadesOpen,
                    activeColor: .cyan
                ) {
                    await kagami.toggleShades()
                }
            }
        }
    }

    // MARK: - Spatial Section

    private var spatialSection: some View {
        VStack(alignment: .leading, spacing: 14) {
            sectionHeader("Spatial Experience", icon: "cube.transparent")

            Button {
                Task {
                    if isImmersiveOpen {
                        await dismissImmersiveSpace()
                    } else {
                        await openImmersiveSpace(id: "kagami-presence")
                    }
                    isImmersiveOpen.toggle()
                }
            } label: {
                HStack {
                    Image(systemName: isImmersiveOpen ? "xmark.circle.fill" : "cube.transparent.fill")
                        .font(.system(size: 24))

                    VStack(alignment: .leading, spacing: 2) {
                        Text(isImmersiveOpen ? "Exit Immersive" : "Enter Full Spatial Mode")
                            .font(.system(size: 16, weight: .semibold))
                        Text("Your home becomes the interface")
                            .font(.system(size: 12))
                            .foregroundStyle(.secondary)
                    }

                    Spacer()

                    Image(systemName: "chevron.right")
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundStyle(.secondary)
                }
                .padding(18)
                .background(
                    LinearGradient(
                        colors: [.cyan.opacity(0.2), .purple.opacity(0.2)],
                        startPoint: .leading,
                        endPoint: .trailing
                    ),
                    in: RoundedRectangle(cornerRadius: 18)
                )
            }
            .buttonStyle(.plain)
        }
    }

    // MARK: - Helpers

    private func sectionHeader(_ title: String, icon: String) -> some View {
        HStack(spacing: 8) {
            Image(systemName: icon)
                .font(.system(size: 14, weight: .semibold))
                .foregroundStyle(.secondary)
            Text(title)
                .font(.system(size: 16, weight: .semibold))
        }
    }
}

// MARK: - Scene Button

struct SceneButton: View {
    let title: String
    let icon: String
    let gradient: [Color]
    let isActive: Bool
    let action: () async -> Void

    var body: some View {
        Button {
            Task { await action() }
        } label: {
            VStack(spacing: 10) {
                ZStack {
                    Circle()
                        .fill(LinearGradient(colors: gradient.map { $0.opacity(isActive ? 0.7 : 0.4) }, startPoint: .topLeading, endPoint: .bottomTrailing))
                        .frame(width: 50, height: 50)

                    Image(systemName: icon)
                        .font(.system(size: 22))
                        .foregroundStyle(.white)
                }

                Text(title)
                    .font(.system(size: 13, weight: .medium))
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 16)
            .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 18))
            .overlay {
                if isActive {
                    RoundedRectangle(cornerRadius: 18)
                        .stroke(LinearGradient(colors: gradient, startPoint: .topLeading, endPoint: .bottomTrailing), lineWidth: 2)
                }
            }
        }
        .buttonStyle(.plain)
        .hoverEffect(.lift)
    }
}

// MARK: - Preset Button

struct PresetButton: View {
    let level: Int
    let isSelected: Bool
    let action: () async -> Void

    var body: some View {
        Button {
            Task { await action() }
        } label: {
            Text(level == 0 ? "Off" : "\(level)")
                .font(.system(size: 11, weight: .semibold))
                .foregroundStyle(isSelected ? .black : .white)
                .frame(width: 32, height: 32)
                .background(isSelected ? Color.yellow : Color.white.opacity(0.15), in: Circle())
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Control Toggle

struct ControlToggle: View {
    let title: String
    let icon: String
    let isActive: Bool
    let activeColor: Color
    let action: () async -> Void

    var body: some View {
        Button {
            Task { await action() }
        } label: {
            VStack(spacing: 10) {
                Image(systemName: icon)
                    .font(.system(size: 32))
                    .foregroundStyle(isActive ? activeColor : .secondary)
                    .symbolEffect(.bounce, value: isActive)

                Text(title)
                    .font(.system(size: 13, weight: .medium))

                Text(isActive ? "On" : "Off")
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 20)
            .background {
                ZStack {
                    if isActive {
                        RoundedRectangle(cornerRadius: 18)
                            .fill(activeColor.opacity(0.15))
                        RoundedRectangle(cornerRadius: 18)
                            .stroke(activeColor.opacity(0.5), lineWidth: 1.5)
                    } else {
                        RoundedRectangle(cornerRadius: 18)
                            .fill(.ultraThinMaterial)
                    }
                }
            }
        }
        .buttonStyle(.plain)
        .hoverEffect(.lift)
    }
}

// MARK: - Compact Control View (Minimal Window)

struct CompactControlView: View {
    @EnvironmentObject var kagami: KagamiSpatialIntelligence
    @Environment(\.openImmersiveSpace) var openImmersiveSpace
    @Environment(\.dismissImmersiveSpace) var dismissImmersiveSpace

    @State private var isImmersiveOpen = false

    var body: some View {
        HStack(spacing: 16) {
            // Connection orb
            ZStack {
                Circle()
                    .fill(orbGradient)
                    .frame(width: 44, height: 44)
                    .blur(radius: 6)

                Circle()
                    .fill(orbGradient)
                    .frame(width: 28, height: 28)
                    .overlay {
                        if kagami.isConnecting {
                            ProgressView()
                                .scaleEffect(0.5)
                                .tint(.white)
                        }
                    }
            }
            .onTapGesture {
                Task {
                    if isImmersiveOpen {
                        await dismissImmersiveSpace()
                    } else {
                        await openImmersiveSpace(id: "kagami-presence")
                    }
                    isImmersiveOpen.toggle()
                }
            }

            VStack(alignment: .leading, spacing: 2) {
                Text(kagami.isConnected ? "Kagami" : "Offline")
                    .font(.system(size: 16, weight: .semibold))

                if let action = kagami.lastAction {
                    Text(action)
                        .font(.system(size: 12))
                        .foregroundStyle(.secondary)
                }
            }

            Spacer()

            // Quick controls
            HStack(spacing: 12) {
                QuickButton(icon: "lightbulb.fill", isActive: kagami.globalLightLevel > 0) {
                    await kagami.setLights(kagami.globalLightLevel > 0 ? 0 : 80)
                }

                QuickButton(icon: "flame.fill", isActive: kagami.fireplaceOn) {
                    await kagami.toggleFireplace()
                }

                QuickButton(icon: "moon.fill", isActive: kagami.movieModeActive) {
                    await kagami.executeScene(kagami.movieModeActive ? "welcome-home" : "movie-mode/enter")
                }
            }
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 12)
        .glassBackgroundEffect(in: Capsule())
    }

    var orbGradient: RadialGradient {
        let color: Color = kagami.isConnected ? .cyan : .orange
        return RadialGradient(
            colors: [.white, color],
            center: .center,
            startRadius: 0,
            endRadius: 20
        )
    }
}

struct QuickButton: View {
    let icon: String
    let isActive: Bool
    let action: () async -> Void

    var body: some View {
        Button {
            Task { await action() }
        } label: {
            Image(systemName: icon)
                .font(.system(size: 18))
                .foregroundStyle(isActive ? .yellow : .white.opacity(0.7))
                .frame(width: 36, height: 36)
                .background(isActive ? Color.yellow.opacity(0.2) : Color.clear, in: Circle())
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Full Immersive Experience

struct KagamiImmersiveExperience: View {
    @EnvironmentObject var kagami: KagamiSpatialIntelligence

    @State private var orbEntity: Entity?
    @State private var orbRotation: Float = 0
    @State private var breathingPhase: Float = 0

    // Spatial zones (meters from user)
    let intimateZone: Float = 0.5   // Personal notifications
    let personalZone: Float = 1.2   // Control panel
    let socialZone: Float = 2.5     // Home visualization
    let ambientZone: Float = 4.0    // Kagami orb presence

    var body: some View {
        RealityView { content in
            // Create the spatial scene
            let scene = Entity()
            scene.name = "kagami-scene"

            // 1. KAGAMI ORB - The Presence
            let orb = createKagamiOrb()
            scene.addChild(orb)
            orbEntity = orb

            // 2. AMBIENT PARTICLES - Environmental awareness
            let particles = createAmbientField()
            scene.addChild(particles)

            // 3. LIGHT VISUALIZATION RING - Shows global brightness
            let lightRing = createLightVisualizationRing()
            scene.addChild(lightRing)

            // 4. ROOM ANCHORS - Future: anchor to real-world rooms
            let roomIndicators = createRoomIndicators()
            scene.addChild(roomIndicators)

            content.add(scene)

        } update: { content in
            updateOrbState()
            updateLightRing(in: content)
            updateParticles(in: content)
        }
        .gesture(
            SpatialTapGesture()
                .targetedToAnyEntity()
                .onEnded { value in
                    handleSpatialTap(value.entity)
                }
        )
        .gesture(
            MagnifyGesture()
                .onChanged { value in
                    kagami.handlePinchGesture(scale: Float(value.magnification))
                }
        )
        .task {
            // Breathing animation loop - Fibonacci 2584ms for natural rhythm
            while !Task.isCancelled {
                withAnimation(.easeInOut(duration: FibonacciMotion.breathe)) {
                    breathingPhase = breathingPhase == 0 ? 1 : 0
                }
                try? await Task.sleep(nanoseconds: 2_584_000_000)  // 2584ms Fibonacci
            }
        }
    }

    // MARK: - Entity Creation

    private func createKagamiOrb() -> Entity {
        let container = Entity()
        container.name = "kagami-orb"
        container.position = SIMD3<Float>(0.4, 1.6, -ambientZone)

        // Core orb
        let core = Entity()
        core.name = "orb-core"

        let mesh = MeshResource.generateSphere(radius: 0.08)
        var material = PhysicallyBasedMaterial()
        material.baseColor = .init(tint: .white)
        material.emissiveColor = .init(color: .cyan)
        material.emissiveIntensity = 1.5
        material.roughness = 0.05
        material.clearcoat = .init(floatLiteral: 1.0)
        material.clearcoatRoughness = .init(floatLiteral: 0.1)

        core.components.set(ModelComponent(mesh: mesh, materials: [material]))
        core.components.set(InputTargetComponent())
        core.components.set(CollisionComponent(shapes: [.generateSphere(radius: 0.12)]))
        core.components.set(HoverEffectComponent())
        container.addChild(core)

        // Inner glow
        let innerGlow = Entity()
        let glowMesh = MeshResource.generateSphere(radius: 0.06)
        var glowMaterial = PhysicallyBasedMaterial()
        glowMaterial.baseColor = .init(tint: .white)
        glowMaterial.emissiveColor = .init(color: .white)
        glowMaterial.emissiveIntensity = 2.0
        glowMaterial.blending = .transparent(opacity: .init(floatLiteral: 0.6))
        innerGlow.components.set(ModelComponent(mesh: glowMesh, materials: [glowMaterial]))
        container.addChild(innerGlow)

        // Outer aura particles
        var particles = ParticleEmitterComponent()
        particles.emitterShape = .sphere
        particles.emitterShapeSize = [0.25, 0.25, 0.25]
        particles.mainEmitter.birthRate = 30
        particles.mainEmitter.lifeSpan = 3
        particles.mainEmitter.lifeSpanVariation = 1
        particles.speed = 0.008
        particles.speedVariation = 0.004
        particles.mainEmitter.color = .evolving(
            start: .single(.init(red: 0, green: 0.9, blue: 1, alpha: 0.6)),
            end: .single(.init(red: 0.5, green: 0.5, blue: 1, alpha: 0))
        )
        particles.mainEmitter.size = 0.006
        particles.mainEmitter.sizeVariation = 0.003

        let particleEntity = Entity()
        particleEntity.components.set(particles)
        container.addChild(particleEntity)

        // Orbiting rings
        for i in 0..<3 {
            let ring = createOrbitRing(radius: 0.12 + Float(i) * 0.04, speed: 1.0 + Float(i) * 0.3)
            container.addChild(ring)
        }

        return container
    }

    private func createOrbitRing(radius: Float, speed: Float) -> Entity {
        let ring = Entity()
        ring.name = "orbit-ring"

        // Create a thin torus-like ring using a stretched sphere
        let mesh = MeshResource.generateSphere(radius: 0.004)
        var material = PhysicallyBasedMaterial()
        material.baseColor = .init(tint: .init(white: 0.9, alpha: 0.3))
        material.emissiveColor = .init(color: .cyan)
        material.emissiveIntensity = 0.8
        material.blending = .transparent(opacity: .init(floatLiteral: 0.4))

        // Place multiple small spheres in a ring
        for angle in stride(from: 0, to: Float.pi * 2, by: Float.pi / 8) {
            let dot = Entity()
            dot.components.set(ModelComponent(mesh: mesh, materials: [material]))
            dot.position = SIMD3<Float>(
                cos(angle) * radius,
                sin(angle) * radius * 0.3,
                0
            )
            ring.addChild(dot)
        }

        return ring
    }

    private func createAmbientField() -> Entity {
        let field = Entity()
        field.name = "ambient-field"
        field.position = SIMD3<Float>(0, 1.2, -2)

        var particles = ParticleEmitterComponent()
        particles.emitterShape = .box
        particles.emitterShapeSize = [4, 2, 4]
        particles.mainEmitter.birthRate = 15
        particles.mainEmitter.lifeSpan = 8
        particles.mainEmitter.lifeSpanVariation = 3
        particles.speed = 0.003
        particles.speedVariation = 0.002
        particles.mainEmitter.color = .evolving(
            start: .single(.init(white: 1, alpha: 0.15)),
            end: .single(.init(white: 1, alpha: 0))
        )
        particles.mainEmitter.size = 0.003
        particles.mainEmitter.sizeVariation = 0.002

        field.components.set(particles)

        return field
    }

    private func createLightVisualizationRing() -> Entity {
        let container = Entity()
        container.name = "light-ring"
        container.position = SIMD3<Float>(0, 0.1, -personalZone)

        // Create a ring of light indicators
        let segments = 24
        let radius: Float = 0.4

        for i in 0..<segments {
            let angle = Float(i) / Float(segments) * Float.pi * 2
            let segment = Entity()
            segment.name = "light-segment-\(i)"

            let mesh = MeshResource.generateBox(size: SIMD3<Float>(0.02, 0.01, 0.04), cornerRadius: 0.005)
            var material = PhysicallyBasedMaterial()
            material.baseColor = .init(tint: .init(.yellow.opacity(0.3)))
            material.emissiveColor = .init(color: .yellow)
            material.emissiveIntensity = 0.2

            segment.components.set(ModelComponent(mesh: mesh, materials: [material]))
            segment.position = SIMD3<Float>(cos(angle) * radius, 0, sin(angle) * radius)
            segment.orientation = simd_quatf(angle: angle, axis: SIMD3<Float>(0, 1, 0))

            container.addChild(segment)
        }

        return container
    }

    private func createRoomIndicators() -> Entity {
        let container = Entity()
        container.name = "room-indicators"
        container.position = SIMD3<Float>(0, 1.2, -socialZone)

        // Create floating room labels in an arc
        let rooms = [
            ("Living Room", SIMD3<Float>(-0.4, 0, 0)),
            ("Kitchen", SIMD3<Float>(-0.15, 0.1, 0)),
            ("Bedroom", SIMD3<Float>(0.15, 0.1, 0)),
            ("Office", SIMD3<Float>(0.4, 0, 0))
        ]

        for (name, offset) in rooms {
            let indicator = createRoomIndicator(name: name)
            indicator.position = offset
            container.addChild(indicator)
        }

        return container
    }

    private func createRoomIndicator(name: String) -> Entity {
        let entity = Entity()
        entity.name = "room-\(name.lowercased().replacingOccurrences(of: " ", with: "-"))"

        // Glowing sphere
        let mesh = MeshResource.generateSphere(radius: 0.03)
        var material = PhysicallyBasedMaterial()
        material.baseColor = .init(tint: .init(.blue.opacity(0.4)))
        material.emissiveColor = .init(color: .cyan)
        material.emissiveIntensity = 0.5

        entity.components.set(ModelComponent(mesh: mesh, materials: [material]))
        entity.components.set(InputTargetComponent())
        entity.components.set(CollisionComponent(shapes: [.generateSphere(radius: 0.05)]))
        entity.components.set(HoverEffectComponent())

        return entity
    }

    // MARK: - Updates

    private func updateOrbState() {
        guard let orb = orbEntity,
              let core = orb.children.first(where: { $0.name == "orb-core" }),
              var model = core.components[ModelComponent.self],
              var material = model.materials.first as? PhysicallyBasedMaterial else { return }

        // Color based on connection and mood
        let color: UIColor = switch kagami.orbMood {
        case .happy: .cyan
        case .thinking: .purple
        case .alert: .orange
        case .sleeping: .init(white: 0.5, alpha: 1)
        case .neutral: kagami.isConnected ? .cyan : .orange
        }

        material.emissiveColor = .init(color: color)
        material.emissiveIntensity = kagami.orbPulseIntensity + Float(breathingPhase) * 0.3
        model.materials = [material]
        core.components.set(model)

        // Slow rotation
        orbRotation += 0.005
        orb.orientation = simd_quatf(angle: orbRotation, axis: SIMD3<Float>(0, 1, 0))
    }

    private func updateLightRing(in content: RealityViewContent) {
        guard let scene = content.entities.first(where: { $0.name == "kagami-scene" }),
              let ring = scene.findEntity(named: "light-ring") else { return }

        let brightness = Float(kagami.globalLightLevel) / 100.0

        for (index, child) in ring.children.enumerated() {
            guard var model = child.components[ModelComponent.self],
                  var material = model.materials.first as? PhysicallyBasedMaterial else { continue }

            let segmentBrightness = Float(index) / Float(ring.children.count)
            let isLit = segmentBrightness <= brightness

            material.emissiveIntensity = isLit ? 1.0 : 0.1
            material.baseColor = .init(tint: isLit ? .yellow : UIColor(white: 0.3, alpha: 1))

            model.materials = [material]
            child.components.set(model)
        }
    }

    private func updateParticles(in content: RealityViewContent) {
        guard let scene = content.entities.first(where: { $0.name == "kagami-scene" }),
              let field = scene.findEntity(named: "ambient-field"),
              var particles = field.components[ParticleEmitterComponent.self] else { return }

        // Adjust particle density based on time of day
        let baseBirthRate: Float = switch kagami.timeOfDay {
        case .morning: 20
        case .day: 10
        case .evening: 25
        case .night: 5
        }

        particles.mainEmitter.birthRate = baseBirthRate
        field.components.set(particles)
    }

    // MARK: - Interactions

    private func handleSpatialTap(_ entity: Entity) {
        let name = entity.name
        guard !name.isEmpty else { return }

        if name == "orb-core" || entity.parent?.name == "kagami-orb" {
            handleOrbTap()
        } else if name.starts(with: "room-") {
            let roomName = String(name.dropFirst(5)).replacingOccurrences(of: "-", with: " ")
            handleRoomTap(roomName)
        }
    }

    private func handleOrbTap() {
        // Context-aware action based on time
        Task {
            switch kagami.timeOfDay {
            case .morning:
                await kagami.setLights(80)
                await kagami.toggleShades() // Open shades
            case .day:
                await kagami.setLights(100)
            case .evening:
                await kagami.executeScene("movie-mode/enter")
            case .night:
                await kagami.executeScene("goodnight")
            }
        }
    }

    private func handleRoomTap(_ room: String) {
        Task {
            // Toggle lights in the specific room
            await kagami.setLights(kagami.globalLightLevel > 0 ? 0 : 100, room: room)
        }
    }
}

// MARK: - Preview

#Preview(windowStyle: .plain) {
    CompactControlView()
        .environmentObject(KagamiSpatialIntelligence())
}
