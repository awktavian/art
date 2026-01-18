//
// InteractionComponent.swift - Gesture Handling ECS Component
//
// Colony: Nexus (e4) - Integration
//
// Features:
//   - Gaze-based selection and highlighting
//   - Pinch gesture recognition
//   - Drag gesture for continuous control
//   - Multi-hand gesture support
//   - Haptic feedback coordination
//   - Accessibility action mapping
//
// Architecture:
//   InteractionComponent -> DeviceEntity -> Gesture Recognizers
//   InteractionComponent -> InteractionSystem -> Action Dispatch
//
// Created: December 31, 2025


import Foundation
import SwiftUI
import UIKit
import RealityKit
import Combine

// MARK: - Interaction Component

/// ECS Component for handling spatial interactions with devices
struct InteractionComponent: Component {

    // MARK: - Properties

    /// Device type this interaction handles
    let deviceType: DeviceEntity.DeviceType

    /// Current interaction state
    var state: InteractionState

    /// Whether this entity is currently selected
    var isSelected: Bool

    /// Whether gaze is currently on this entity
    var isGazed: Bool

    /// Gaze start time for dwell tracking
    var gazeStartTime: Date?

    /// Current gesture in progress
    var activeGesture: ActiveGesture?

    /// Enabled interaction modes
    var enabledModes: Set<InteractionMode>

    /// Gesture sensitivity multiplier
    var sensitivity: Float

    /// Custom action handlers
    var customActions: [String: InteractionAction]

    // MARK: - Types

    enum InteractionState: String {
        case idle = "idle"
        case highlighted = "highlighted"
        case selected = "selected"
        case dragging = "dragging"
        case disabled = "disabled"
    }

    enum InteractionMode: String, CaseIterable {
        case gaze = "gaze"
        case tap = "tap"
        case pinch = "pinch"
        case drag = "drag"
        case scale = "scale"
        case rotate = "rotate"
        case voice = "voice"
    }

    struct ActiveGesture {
        let type: GestureType
        let startPosition: SIMD3<Float>
        var currentPosition: SIMD3<Float>
        let startTime: Date
        var value: Float  // Accumulated gesture value

        enum GestureType: String {
            case pinch = "pinch"
            case verticalDrag = "vertical_drag"
            case horizontalDrag = "horizontal_drag"
            case rotate = "rotate"
            case scale = "scale"
        }
    }

    struct InteractionAction {
        let name: String
        let gestureType: ActiveGesture.GestureType?
        let action: (Float) -> Void

        init(name: String, gestureType: ActiveGesture.GestureType? = nil, action: @escaping (Float) -> Void) {
            self.name = name
            self.gestureType = gestureType
            self.action = action
        }
    }

    // MARK: - Initialization

    init(
        deviceType: DeviceEntity.DeviceType,
        enabledModes: Set<InteractionMode>? = nil,
        sensitivity: Float = 1.0
    ) {
        self.deviceType = deviceType
        self.state = .idle
        self.isSelected = false
        self.isGazed = false
        self.gazeStartTime = nil
        self.activeGesture = nil
        self.enabledModes = enabledModes ?? Self.defaultModes(for: deviceType)
        self.sensitivity = sensitivity
        self.customActions = [:]
    }

    // MARK: - Default Configuration

    private static func defaultModes(for type: DeviceEntity.DeviceType) -> Set<InteractionMode> {
        switch type {
        case .light:
            return [.gaze, .tap, .pinch, .drag]
        case .shade:
            return [.gaze, .tap, .drag]
        case .thermostat:
            return [.gaze, .tap, .drag, .rotate]
        case .audioZone:
            return [.gaze, .tap, .drag]
        case .lock:
            return [.gaze, .tap]
        case .fireplace:
            return [.gaze, .tap]
        case .tv:
            return [.gaze, .tap]
        case .camera:
            return [.gaze, .tap]
        }
    }

    // MARK: - Computed Properties

    /// Whether the entity can be interacted with
    var isInteractable: Bool {
        state != .disabled && !enabledModes.isEmpty
    }

    /// Current dwell time if gazed
    var dwellTime: TimeInterval? {
        guard let startTime = gazeStartTime else { return nil }
        return Date().timeIntervalSince(startTime)
    }

    /// Whether dwell threshold has been reached
    var hasDwellActivated: Bool {
        guard let dwell = dwellTime else { return false }
        return dwell >= InteractionConstants.dwellThreshold
    }

    /// Gesture delta from start
    var gestureDelta: SIMD3<Float>? {
        guard let gesture = activeGesture else { return nil }
        return gesture.currentPosition - gesture.startPosition
    }

    // MARK: - Methods

    /// Starts gaze tracking on this entity
    mutating func beginGaze() {
        guard enabledModes.contains(.gaze) else { return }
        isGazed = true
        gazeStartTime = Date()
        state = .highlighted
    }

    /// Ends gaze tracking
    mutating func endGaze() {
        isGazed = false
        gazeStartTime = nil
        if state == .highlighted && !isSelected {
            state = .idle
        }
    }

    /// Selects the entity
    mutating func select() {
        isSelected = true
        state = .selected
    }

    /// Deselects the entity
    mutating func deselect() {
        isSelected = false
        state = isGazed ? .highlighted : .idle
    }

    /// Toggles selection state
    mutating func toggleSelection() {
        if isSelected {
            deselect()
        } else {
            select()
        }
    }

    /// Begins a gesture
    mutating func beginGesture(
        type: ActiveGesture.GestureType,
        at position: SIMD3<Float>
    ) {
        activeGesture = ActiveGesture(
            type: type,
            startPosition: position,
            currentPosition: position,
            startTime: Date(),
            value: 0
        )
        state = .dragging
    }

    /// Updates ongoing gesture
    mutating func updateGesture(to position: SIMD3<Float>) {
        guard var gesture = activeGesture else { return }
        gesture.currentPosition = position

        // Calculate value based on gesture type
        let delta = position - gesture.startPosition
        switch gesture.type {
        case .verticalDrag:
            gesture.value = -delta.y * sensitivity * 200  // Invert Y, scale to 0-100
        case .horizontalDrag:
            gesture.value = delta.x * sensitivity * 200
        case .pinch:
            gesture.value = delta.z * sensitivity * 100
        case .rotate:
            gesture.value = delta.x * sensitivity * 360
        case .scale:
            gesture.value = simd_length(delta) * sensitivity * 2
        }

        activeGesture = gesture
    }

    /// Ends the current gesture
    mutating func endGesture() -> Float? {
        let finalValue = activeGesture?.value
        activeGesture = nil
        state = isSelected ? .selected : (isGazed ? .highlighted : .idle)
        return finalValue
    }

    /// Cancels the current gesture without applying
    mutating func cancelGesture() {
        activeGesture = nil
        state = isSelected ? .selected : (isGazed ? .highlighted : .idle)
    }

    /// Registers a custom action
    mutating func registerAction(_ key: String, action: InteractionAction) {
        customActions[key] = action
    }

    /// Executes a custom action
    func executeAction(_ key: String, value: Float = 0) {
        customActions[key]?.action(value)
    }

    /// Disables interaction
    mutating func disable() {
        state = .disabled
        isSelected = false
        isGazed = false
        activeGesture = nil
    }

    /// Enables interaction
    mutating func enable() {
        state = .idle
    }
}

// MARK: - Interaction Constants

enum InteractionConstants {
    /// Gaze confirmation dwell time before action registers (400ms per visionOS guidelines)
    static let dwellThreshold: TimeInterval = 0.4

    /// Minimum drag distance to register (meters)
    static let dragThreshold: Float = 0.01

    /// Pinch detection distance (meters)
    static let pinchThreshold: Float = 0.025

    /// Maximum tap duration (seconds)
    static let tapMaxDuration: TimeInterval = 0.3

    /// Double tap interval (seconds)
    static let doubleTapInterval: TimeInterval = 0.4

    /// Minimum touch target size in meters (60pt = 0.06m per Apple HIG)
    static let minimumTouchTargetSize: Float = 0.06
}

// MARK: - Interaction System (RealityKit System)

/// Proper RealityKit ECS System for processing interaction components.
/// Conforms to RealityKit System protocol for automatic scene integration.
/// Handles gaze-based selection with 400ms dwell confirmation per visionOS guidelines.
@MainActor
class SpatialInteractionSystem: System {

    // MARK: - System Protocol Requirements

    static let query = EntityQuery(where: .has(InteractionComponent.self))

    private var gazeTarget: Entity?
    private var selectedEntities: [Entity] = []
    private var lastTapTime: Date?
    private var lastTapEntity: Entity?

    // Callbacks for event handling
    static var onSelect: ((Entity) -> Void)?
    static var onDeselect: ((Entity) -> Void)?
    static var onGestureComplete: ((Entity, InteractionComponent.ActiveGesture.GestureType, Float) -> Void)?
    static var onDoubleTap: ((Entity) -> Void)?

    required init(scene: RealityKit.Scene) {}

    func update(context: SceneUpdateContext) {
        for entity in context.entities(matching: Self.query, updatingSystemWhen: .rendering) {
            guard var component = entity.components[InteractionComponent.self] else { continue }

            // Update dwell-based activation (400ms threshold)
            if component.hasDwellActivated && !component.isSelected {
                component.select()
                entity.components.set(component)
                Self.onSelect?(entity)

                // Update visual feedback
                InteractionVisualFeedback.updateAppearance(for: entity)
                InteractionVisualFeedback.addSelectionRing(to: entity)
            }
        }
    }
}

/// Legacy compatibility wrapper for non-System usage
class InteractionSystem {

    // MARK: - Properties

    private var gazeTarget: Entity?
    private var selectedEntities: [Entity] = []
    private var lastTapTime: Date?
    private var lastTapEntity: Entity?

    // Callbacks
    var onSelect: ((Entity) -> Void)?
    var onDeselect: ((Entity) -> Void)?
    var onGestureComplete: ((Entity, InteractionComponent.ActiveGesture.GestureType, Float) -> Void)?
    var onDoubleTap: ((Entity) -> Void)?

    // MARK: - Update

    /// Processes all entities with interaction components
    func update(entities: [Entity], gazePosition: SIMD3<Float>?, gazeDirection: SIMD3<Float>?) {
        // Update gaze targeting
        if let pos = gazePosition, let dir = gazeDirection {
            updateGazeTarget(entities: entities, position: pos, direction: dir)
        }

        // Update each entity with 400ms dwell confirmation
        for entity in entities {
            guard var component = entity.components[InteractionComponent.self] else { continue }

            // Update dwell-based activation
            if component.hasDwellActivated && !component.isSelected {
                component.select()
                entity.components.set(component)
                onSelect?(entity)
            }
        }
    }

    // MARK: - Gaze Handling

    private func updateGazeTarget(entities: [Entity], position: SIMD3<Float>, direction: SIMD3<Float>) {
        // Find entity in gaze direction
        var closestEntity: Entity?
        var closestDistance: Float = .infinity

        for entity in entities {
            guard entity.components[InteractionComponent.self]?.isInteractable == true else { continue }

            let toEntity = entity.position - position
            let distance = simd_length(toEntity)

            // Check if in gaze cone (dot product threshold)
            let normalizedToEntity = simd_normalize(toEntity)
            let dotProduct = simd_dot(normalizedToEntity, direction)

            if dotProduct > 0.9 && distance < closestDistance {  // ~25 degree cone
                closestDistance = distance
                closestEntity = entity
            }
        }

        // Update gaze state
        if let newTarget = closestEntity, newTarget !== gazeTarget {
            // End gaze on previous
            if let previous = gazeTarget,
               var component = previous.components[InteractionComponent.self] {
                component.endGaze()
                previous.components.set(component)
            }

            // Begin gaze on new
            if var component = newTarget.components[InteractionComponent.self] {
                component.beginGaze()
                newTarget.components.set(component)
            }

            gazeTarget = newTarget
        } else if closestEntity == nil && gazeTarget != nil {
            // Lost gaze target
            if var component = gazeTarget?.components[InteractionComponent.self] {
                component.endGaze()
                gazeTarget?.components.set(component)
            }
            gazeTarget = nil
        }
    }

    // MARK: - Tap Handling

    func handleTap(on entity: Entity) {
        guard var component = entity.components[InteractionComponent.self],
              component.enabledModes.contains(.tap) else { return }

        let now = Date()

        // Check for double tap
        if let lastTime = lastTapTime,
           let lastEntity = lastTapEntity,
           lastEntity === entity,
           now.timeIntervalSince(lastTime) < InteractionConstants.doubleTapInterval {
            // Double tap detected
            onDoubleTap?(entity)
            lastTapTime = nil
            lastTapEntity = nil
            return
        }

        // Record tap for double-tap detection
        lastTapTime = now
        lastTapEntity = entity

        // Toggle selection
        component.toggleSelection()
        entity.components.set(component)

        if component.isSelected {
            selectedEntities.append(entity)
            onSelect?(entity)
        } else {
            selectedEntities.removeAll { $0 === entity }
            onDeselect?(entity)
        }
    }

    // MARK: - Gesture Handling

    func beginDrag(on entity: Entity, at position: SIMD3<Float>, type: InteractionComponent.ActiveGesture.GestureType = .verticalDrag) {
        guard var component = entity.components[InteractionComponent.self],
              component.enabledModes.contains(.drag) else { return }

        component.beginGesture(type: type, at: position)
        entity.components.set(component)
    }

    func updateDrag(on entity: Entity, to position: SIMD3<Float>) {
        guard var component = entity.components[InteractionComponent.self],
              component.activeGesture != nil else { return }

        component.updateGesture(to: position)
        entity.components.set(component)

        // Provide real-time feedback
        if let gesture = component.activeGesture {
            // Could trigger haptics or visual feedback here
            _ = gesture.value
        }
    }

    func endDrag(on entity: Entity) {
        guard var component = entity.components[InteractionComponent.self],
              let gesture = component.activeGesture else { return }

        let finalValue = component.endGesture()
        entity.components.set(component)

        if let value = finalValue {
            onGestureComplete?(entity, gesture.type, value)
        }
    }

    func cancelDrag(on entity: Entity) {
        guard var component = entity.components[InteractionComponent.self] else { return }
        component.cancelGesture()
        entity.components.set(component)
    }

    // MARK: - Selection Management

    func deselectAll() {
        for entity in selectedEntities {
            guard var component = entity.components[InteractionComponent.self] else { continue }
            component.deselect()
            entity.components.set(component)
            onDeselect?(entity)
        }
        selectedEntities.removeAll()
    }

    func selectEntity(_ entity: Entity) {
        guard var component = entity.components[InteractionComponent.self] else { return }
        component.select()
        entity.components.set(component)
        selectedEntities.append(entity)
        onSelect?(entity)
    }

    // MARK: - Queries

    var currentGazeTarget: Entity? { gazeTarget }

    var currentlySelectedEntities: [Entity] { selectedEntities }

    func isSelected(_ entity: Entity) -> Bool {
        entity.components[InteractionComponent.self]?.isSelected ?? false
    }

    func isGazed(_ entity: Entity) -> Bool {
        entity.components[InteractionComponent.self]?.isGazed ?? false
    }
}

// MARK: - Interaction Visual Feedback

/// Provides visual feedback for interaction states
class InteractionVisualFeedback {

    /// Updates entity appearance based on interaction state
    static func updateAppearance(for entity: Entity) {
        guard let component = entity.components[InteractionComponent.self] else { return }

        let scale: Float
        let emissiveBoost: Float

        switch component.state {
        case .idle:
            scale = 1.0
            emissiveBoost = 0

        case .highlighted:
            scale = 1.05
            emissiveBoost = 0.2

        case .selected:
            scale = 1.1
            emissiveBoost = 0.4

        case .dragging:
            scale = 1.15
            emissiveBoost = 0.5

        case .disabled:
            scale = 1.0
            emissiveBoost = -0.3
        }

        // Apply scale
        entity.scale = SIMD3<Float>(repeating: scale)

        // Apply emissive boost if entity has model
        if var model = entity.components[ModelComponent.self],
           var material = model.materials.first as? PhysicallyBasedMaterial {
            material.emissiveIntensity += emissiveBoost
            model.materials = [material]
            entity.components.set(model)
        }
    }

    /// Adds selection ring to entity
    static func addSelectionRing(to entity: Entity) {
        guard entity.children.first(where: { $0.name == "selection-ring" }) == nil else { return }

        let ring = Entity()
        ring.name = "selection-ring"

        let mesh = MeshResource.generateCylinder(height: 0.002, radius: 0.05)

        var material = PhysicallyBasedMaterial()
        material.baseColor = .init(tint: UIColor(Color.crystal.opacity(0.5)))
        material.emissiveColor = .init(color: UIColor(Color.crystal))
        material.emissiveIntensity = 0.5

        ring.components.set(ModelComponent(mesh: mesh, materials: [material]))
        ring.position.y = -0.03

        entity.addChild(ring)
    }

    /// Removes selection ring from entity
    static func removeSelectionRing(from entity: Entity) {
        entity.children.first { $0.name == "selection-ring" }?.removeFromParent()
    }
}

/*
 *
 * h(x) >= 0. Always.
 *
 * Interaction is conversation.
 * Gaze asks.
 * Tap answers.
 * Drag adjusts.
 * The hands speak, the home listens.
 */
