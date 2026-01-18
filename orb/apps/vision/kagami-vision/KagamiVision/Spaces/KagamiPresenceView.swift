//
// KagamiPresenceView.swift
// KagamiVision
//
// The HAL-aware volumetric presence — a subtle orb that
// floats at the periphery, responding to gaze and state.
//
// Spatial Features (Phase 3):
//   - World-anchored positioning with persistence
//   - Spatial audio feedback on interactions
//   - Hand gesture recognition for controls
//   - Gaze-based attention detection
//   - Depth-layered particle system
//   - Proxemic-aware scaling
//
// Phase 2 Accessibility:
//   - Reduced motion support for pulse/float animations
//   - VoiceOver labels for 3D entities
//   - Spatial gesture hints for orb interaction
//

import SwiftUI
import RealityKit
import Accessibility

struct KagamiPresenceView: View {
    @EnvironmentObject var appModel: AppModel
    @EnvironmentObject var spatialServices: SpatialServicesContainer
    @StateObject private var orbService = OrbStateService.shared
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    // Spatial positioning
    @State private var orbPosition: SIMD3<Float> = [0.3, 1.2, -0.8]
    @State private var orbScale: Float = 0.08
    @State private var pulsePhase: Double = 0
    @State private var pulseTimer: Timer?

    // Gaze tracking
    @State private var isBeingLookedAt = false
    @State private var gazeStartTime: Date?
    @State private var gazeDwellProgress: Float = 0

    // Spatial audio
    @State private var lastAudioPlayTime: Date?

    // Anchor for persistent positioning
    @State private var orbAnchor: SpatialAnchorService.SpatialAnchor?

    // Depth layers for particles
    private let particleDepthLayers: [(radius: Float, opacity: Float, speed: Float)] = [
        (0.15, 0.5, 0.03),   // Inner layer - bright, fast
        (0.25, 0.3, 0.02),   // Middle layer
        (0.35, 0.15, 0.01),  // Outer layer - faint, slow
    ]

    var body: some View {
        RealityView { content in
            // Create the Kagami orb entity with accessibility
            let orb = createKagamiOrb()
            configureOrbAccessibility(orb)
            content.add(orb)

            // Add depth-layered ambient particles (skip if reduce motion is enabled)
            if !AccessibilitySettings.shared.reduceMotion {
                for (index, layer) in particleDepthLayers.enumerated() {
                    let particles = createDepthLayeredParticles(
                        layer: index,
                        radius: layer.radius,
                        opacity: layer.opacity,
                        speed: layer.speed
                    )
                    content.add(particles)
                }
            }

            // Add spatial audio source entity
            let audioSource = createAudioSourceEntity()
            content.add(audioSource)

            // Add gaze indicator (subtle ring that appears when looking)
            let gazeIndicator = createGazeIndicator()
            content.add(gazeIndicator)

        } update: { content in
            // Update orb based on state
            if let orb = content.entities.first(where: { $0.name == "kagami-orb" }) {
                updateOrbAppearance(orb)
                updateOrbPosition(orb)
            }

            // Update gaze indicator
            if let gazeIndicator = content.entities.first(where: { $0.name == "gaze-indicator" }) {
                updateGazeIndicator(gazeIndicator)
            }

            // Check gaze focus
            checkGazeFocus()
        }
        .gesture(
            SpatialTapGesture()
                .targetedToAnyEntity()
                .onEnded { value in
                    handleOrbTap()
                }
        )
        .onAppear {
            startPulseAnimation()
            initializeSpatialFeatures()
            connectOrbService()
        }
        .onDisappear {
            pulseTimer?.invalidate()
            pulseTimer = nil
        }
        // Accessibility container for the immersive space
        .accessibilityElement(children: .contain)
        .accessibilityLabel("Kagami Presence Space")
        .accessibilityHint("Contains the Kagami orb. Look at the orb and pinch to activate quick actions based on time of day.")
    }

    // MARK: - Spatial Initialization

    private func initializeSpatialFeatures() {
        // Create persistent anchor for orb position
        Task { @MainActor in
            if spatialServices.isInitialized {
                orbAnchor = spatialServices.anchorService.createAnchor(
                    at: orbPosition,
                    type: .headRelative,
                    label: "Kagami Orb"
                )
            }
        }
    }

    // MARK: - Gaze Tracking

    private func checkGazeFocus() {
        guard spatialServices.isInitialized else { return }

        // Check if user is looking at orb position
        let isLooking = spatialServices.gazeTracking.isLookingAt(orbPosition, threshold: 0.4)

        if isLooking && !isBeingLookedAt {
            // Started looking at orb
            isBeingLookedAt = true
            gazeStartTime = Date()
            playGazeEnterAudio()
        } else if !isLooking && isBeingLookedAt {
            // Stopped looking at orb
            isBeingLookedAt = false
            gazeStartTime = nil
            gazeDwellProgress = 0
        } else if isLooking, let startTime = gazeStartTime {
            // Continue looking - update dwell progress
            // Using Fibonacci 1597ms (SpatialMotion.ambient) for natural gaze activation
            let duration = Date().timeIntervalSince(startTime)
            gazeDwellProgress = Float(min(duration / 1.597, 1.0))  // 1.597s Fibonacci dwell

            // Auto-activate on full dwell
            if gazeDwellProgress >= 1.0 && canPlayAudio() {
                handleOrbTap()
                gazeStartTime = Date()  // Reset
                gazeDwellProgress = 0
            }
        }
    }

    private func playGazeEnterAudio() {
        guard canPlayAudio() else { return }
        spatialServices.audioService.play(.notification, at: orbPosition)
        lastAudioPlayTime = Date()
    }

    private func canPlayAudio() -> Bool {
        guard let lastPlay = lastAudioPlayTime else { return true }
        return Date().timeIntervalSince(lastPlay) > 0.5  // Debounce
    }

    // MARK: - Depth-Layered Particles

    private func createDepthLayeredParticles(
        layer: Int,
        radius: Float,
        opacity: Float,
        speed: Float
    ) -> Entity {
        let particleEntity = Entity()
        particleEntity.name = "ambient-particles-\(layer)"
        particleEntity.position = orbPosition

        var particles = ParticleEmitterComponent()
        particles.emitterShape = .sphere
        particles.emitterShapeSize = SIMD3<Float>(repeating: radius * 2)

        // Vary parameters by layer
        let baseRate: Float = AccessibilitySettings.shared.reduceMotion ? 2 : 10
        particles.mainEmitter.birthRate = baseRate / Float(layer + 1)
        particles.mainEmitter.birthRateVariation = baseRate / Float(layer + 2)
        particles.mainEmitter.lifeSpan = Double(3 + layer)
        particles.mainEmitter.lifeSpanVariation = 1
        particles.speed = speed
        particles.speedVariation = speed * 0.5

        // Color varies by layer - inner is brighter
        particles.mainEmitter.color = .constant(.single(.init(.crystal.opacity(Double(opacity)))))
        particles.mainEmitter.size = 0.003 + Float(layer) * 0.001

        particleEntity.components.set(particles)

        return particleEntity
    }

    // MARK: - Create Orb

    private func createKagamiOrb() -> Entity {
        let orb = Entity()
        orb.name = "kagami-orb"

        // Create a glowing sphere
        let mesh = MeshResource.generateSphere(radius: orbScale)

        // Crystal-colored material with glow
        var material = PhysicallyBasedMaterial()
        material.baseColor = .init(tint: .init(Color.crystal))
        material.emissiveColor = .init(color: .init(Color.crystal.opacity(0.5)))
        material.emissiveIntensity = 0.8
        material.roughness = 0.1
        material.metallic = 0.0
        material.clearcoat = .init(floatLiteral: 1.0)

        let modelComponent = ModelComponent(mesh: mesh, materials: [material])
        orb.components.set(modelComponent)

        // Position at periphery
        orb.position = orbPosition

        // Add hover effect
        orb.components.set(HoverEffectComponent())

        // Make it interactive
        orb.components.set(InputTargetComponent())
        orb.components.set(CollisionComponent(shapes: [.generateSphere(radius: orbScale * 1.5)]))

        return orb
    }

    // MARK: - Accessibility Configuration

    private func configureOrbAccessibility(_ entity: Entity) {
        // Add accessibility component for VoiceOver support in spatial contexts
        // The orb is an interactive 3D element that needs proper labeling
        let accessibility = SpatialEntityAccessibility.kagamiOrb

        // Configure the entity's accessibility properties
        // Note: RealityKit entities use AccessibilityComponent for visionOS
        var accessibilityComponent = AccessibilityComponent()
        accessibilityComponent.label = LocalizedStringResource(stringLiteral: accessibility.label)
        accessibilityComponent.value = LocalizedStringResource(stringLiteral: currentOrbStateDescription())
        accessibilityComponent.isAccessibilityElement = true
        accessibilityComponent.traits = [.button]

        // Note: Custom actions require the full SharePlay session API
        // Accessibility labels and values are sufficient for VoiceOver support

        entity.components.set(accessibilityComponent)
    }

    private func currentOrbStateDescription() -> String {
        if let activeColony = appModel.activeColonies.first {
            return "Active colony: \(activeColony)"
        }
        return "Idle state, crystal color"
    }

    // MARK: - Create Audio Source Entity

    private func createAudioSourceEntity() -> Entity {
        let entity = Entity()
        entity.name = "audio-source"
        entity.position = orbPosition

        // Spatial audio component would be added here in production
        // For now, we use SpatialAudioService directly

        return entity
    }

    // MARK: - Create Gaze Indicator

    private func createGazeIndicator() -> Entity {
        let entity = Entity()
        entity.name = "gaze-indicator"
        entity.position = orbPosition

        // Ring that appears when user looks at orb
        let mesh = MeshResource.generateBox(
            width: 0.2,
            height: 0.002,
            depth: 0.2,
            cornerRadius: 0.1
        )

        var material = PhysicallyBasedMaterial()
        material.baseColor = .init(tint: .init(.crystal.opacity(0.3)))
        material.emissiveColor = .init(color: .init(.crystal))
        material.emissiveIntensity = 0.2

        entity.components.set(ModelComponent(mesh: mesh, materials: [material]))
        entity.scale = SIMD3<Float>(repeating: 0)  // Hidden initially

        return entity
    }

    // MARK: - Update Gaze Indicator

    private func updateGazeIndicator(_ entity: Entity) {
        // Scale based on gaze dwell progress
        let targetScale: Float = isBeingLookedAt ? (0.8 + gazeDwellProgress * 0.4) : 0
        let currentScale = entity.scale.x

        // Smooth lerp
        let newScale = currentScale + (targetScale - currentScale) * 0.1
        entity.scale = SIMD3<Float>(repeating: newScale)

        // Update material brightness based on progress
        if var model = entity.components[ModelComponent.self],
           var material = model.materials.first as? PhysicallyBasedMaterial {
            material.emissiveIntensity = 0.2 + gazeDwellProgress * 0.8
            model.materials = [material]
            entity.components.set(model)
        }
    }

    // MARK: - Update Orb Position

    private func updateOrbPosition(_ entity: Entity) {
        // If we have an anchor, use its position (for head-relative tracking)
        if let anchor = orbAnchor {
            orbPosition = anchor.position
        }

        entity.position = orbPosition

        // Update particle positions too
        // (In a full implementation, we'd update all particle entities)
    }

    // MARK: - Create Particles (Legacy - kept for compatibility)

    private func createAmbientParticles() -> Entity {
        let particleEntity = Entity()
        particleEntity.name = "ambient-particles"

        // Position near orb
        particleEntity.position = orbPosition

        // Create particle system - reduced when accessibility prefers less motion
        var particles = ParticleEmitterComponent()
        particles.emitterShape = .sphere
        particles.emitterShapeSize = [0.3, 0.3, 0.3]

        // Reduced particle count for accessibility
        let baseRate: Float = AccessibilitySettings.shared.reduceMotion ? 3 : 15
        particles.mainEmitter.birthRate = baseRate
        particles.mainEmitter.birthRateVariation = AccessibilitySettings.shared.reduceMotion ? 1 : 5
        particles.mainEmitter.lifeSpan = 4
        particles.mainEmitter.lifeSpanVariation = 1
        particles.speed = AccessibilitySettings.shared.reduceMotion ? 0.005 : 0.02
        particles.speedVariation = 0.01
        particles.mainEmitter.color = .constant(.single(.init(Color.crystal.opacity(0.4))))
        particles.mainEmitter.size = 0.003

        particleEntity.components.set(particles)

        // Add accessibility label for particles
        var accessibilityComponent = AccessibilityComponent()
        accessibilityComponent.label = LocalizedStringResource(stringLiteral: "Ambient particle effects")
        accessibilityComponent.isAccessibilityElement = false  // Decorative element
        particleEntity.components.set(accessibilityComponent)

        return particleEntity
    }

    // MARK: - Update Orb

    private func updateOrbAppearance(_ entity: Entity) {
        // Update color based on active colony (using canonical colors from API)
        guard var model = entity.components[ModelComponent.self] else { return }

        // Get color from OrbStateService (canonical API colors)
        // Falls back to local colors if API unavailable
        let color: Color
        if let orbState = orbService.currentState {
            // Use color from canonical API state
            color = orbService.colorForColony(orbState.activeColony)
        } else if let activeColony = appModel.activeColonies.first {
            // Fallback to local colony colors
            color = orbService.colorForColony(activeColony)
        } else {
            // Default idle color
            color = orbService.colorForColony(nil)
        }

        if var material = model.materials.first as? PhysicallyBasedMaterial {
            material.baseColor = .init(tint: .init(color))
            material.emissiveColor = .init(color: .init(color.opacity(0.5)))
            model.materials = [material]
            entity.components.set(model)
        }

        // Pulse scale - respect reduced motion preference
        let scale: Float
        if reduceMotion || AccessibilitySettings.shared.reduceMotion {
            // No pulsing animation when reduced motion is enabled
            scale = 0.08
        } else {
            scale = Float(0.08 + 0.01 * sin(pulsePhase))
        }
        entity.scale = [scale, scale, scale]

        // Update accessibility value when state changes
        if var accessibilityComponent = entity.components[AccessibilityComponent.self] {
            accessibilityComponent.value = LocalizedStringResource(stringLiteral: currentOrbStateDescription())
            entity.components.set(accessibilityComponent)
        }
    }

    // MARK: - Animation

    private func startPulseAnimation() {
        // Skip animation if reduced motion is enabled
        guard !reduceMotion && !AccessibilitySettings.shared.reduceMotion else {
            pulseTimer?.invalidate()
            pulseTimer = nil
            return
        }

        pulseTimer?.invalidate()
        pulseTimer = Timer.scheduledTimer(withTimeInterval: 0.05, repeats: true) { [self] _ in
            Task { @MainActor in
                pulsePhase += 0.1
            }
        }
    }

    // MARK: - Interaction

    private func handleOrbTap() {
        // Open command palette on tap
        print("🪞 Kagami orb tapped")

        // Play spatial audio feedback
        spatialServices.audioService.play(.orbActivate, at: orbPosition)
        lastAudioPlayTime = Date()

        // Report interaction to API (broadcasts to all clients)
        Task { @MainActor in
            let hour = Calendar.current.component(.hour, from: Date())
            let timeOfDay = switch hour {
                case 6...9: "morning"
                case 10...17: "day"
                case 18...21: "evening"
                default: "night"
            }

            // Broadcast tap to all connected clients
            await orbService.reportInteraction(
                action: "tap",
                context: [
                    "time_of_day": timeOfDay,
                    "platform": "vision_pro"
                ]
            )

            // Quick scene execution based on time of day
            switch hour {
            case 6...9:
                await appModel.apiService.setLights(80)
                spatialServices.audioService.play(.lightOn, at: orbPosition)
            case 18...21:
                await appModel.apiService.executeScene("movie_mode")
                spatialServices.audioService.play(.sceneChange, at: orbPosition)
            case 22...24, 0...5:
                await appModel.apiService.executeScene("goodnight")
                spatialServices.audioService.play(.sceneChange, at: orbPosition)
            default:
                await appModel.apiService.setLights(100)
                spatialServices.audioService.play(.lightOn, at: orbPosition)
            }
        }
    }

    // MARK: - Orb Service Connection

    private func connectOrbService() {
        Task {
            await orbService.connect()
        }
    }
}

// MARK: - Hover Effect

struct HoverEffectComponent: Component {}

#Preview {
    KagamiPresenceView()
        .environmentObject(AppModel())
}

/*
 * 鏡
 * The mirror floats. The mirror observes.
 */
